from __future__ import annotations

import runpy
import shutil
import time
from pathlib import Path
from types import SimpleNamespace

from meshdash.plugins import (
    ReplyAction,
    Script,
    parse_manifest,
    validate_script_against_manifest,
)
from meshdash.plugin_composition import build_plugin_subsystem
from meshdash.config import DEFAULT_PLUGINS_DIRECTORY


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLUGIN_ROOT = REPO_ROOT / "mesh_dashboard_plugins"
HELLO_EXAMPLE = DEFAULT_PLUGIN_ROOT / "hello"


class _Tracker:
    def __init__(self) -> None:
        self.listeners: list[object] = []

    def add_accepted_packet_listener(self, listener: object) -> None:
        self.listeners.append(listener)

    def remove_accepted_packet_listener(self, listener: object) -> None:
        self.listeners.remove(listener)


def _wait_until(predicate, *, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition did not become true before timeout")


def _example_args(tmp_path: Path, *, enable: bool) -> SimpleNamespace:
    return SimpleNamespace(
        plugins_directory=str(DEFAULT_PLUGIN_ROOT),
        plugins_state_db=str(tmp_path / "plugin-state.sqlite3"),
        plugins_files_directory=str(tmp_path / "plugin-files"),
        plugins_event_queue_size=8,
        plugins_handler_timeout=2.0,
        plugin_enable=["hello"] if enable else [],
        plugin_disable=[],
        file_transfer_enable=False,
        file_transfer_max_bytes=4096,
    )


def _hello_packet(packet_id: int) -> dict[str, object]:
    return {
        "from": 1,
        "to": 2,
        "id": packet_id,
        "channel": 0,
        "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "!hello"},
    }


def test_hello_example_is_copyable_and_matches_its_manifest(tmp_path: Path) -> None:
    installed = tmp_path / "configured-plugins" / "hello"
    shutil.copytree(HELLO_EXAMPLE, installed)

    manifest = parse_manifest(installed / "plugin.toml")
    namespace = runpy.run_path(str(manifest.entrypoint_path))
    script = namespace[manifest.entrypoint_object]

    assert isinstance(script, Script)
    assert validate_script_against_manifest(manifest, script) is script
    assert manifest.id == "hello"
    assert manifest.commands == ("hello",)
    assert manifest.default_enabled is False

    peer_state: dict[str, object] = {}
    context = SimpleNamespace(
        peer_state=peer_state,
        reply=lambda text: ReplyAction(text),
    )
    first = script.commands["hello"](context)
    second = script.commands["hello"](context)

    assert first == ReplyAction("Hello from Meshyface! Visit 1.")
    assert second == ReplyAction("Hello from Meshyface! Visit 2.")
    assert peer_state == {"visits": 2}


def test_hello_example_uses_default_source_checkout_plugin_directory() -> None:
    assert HELLO_EXAMPLE.is_dir()
    assert Path(DEFAULT_PLUGINS_DIRECTORY) == Path("mesh_dashboard_plugins")
    assert not (REPO_ROOT / "meshdash" / "included_plugins" / "hello").exists()


def test_hello_example_runs_in_spawned_runtime_and_persists_peer_state(
    tmp_path: Path,
) -> None:
    sends: list[dict[str, object]] = []
    iface = SimpleNamespace(nodesByNum={})

    def _run_once(*, enable: bool, expected_sends: int) -> None:
        tracker = _Tracker()
        subsystem = build_plugin_subsystem(
            args=_example_args(tmp_path, enable=enable),
            iface=iface,
            tracker=tracker,
            send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)) or {"ok": True},
            local_node_id_fn=lambda: "!00000002",
        )
        try:
            _wait_until(
                lambda: subsystem.status()["scripts"][0]["runtime_status"]
                == "running"  # type: ignore[index]
            )
            assert len(tracker.listeners) == 1
            listener = tracker.listeners[0]
            assert callable(listener)
            listener(_hello_packet(expected_sends), iface)
            _wait_until(lambda: len(sends) >= expected_sends)
        finally:
            subsystem.close()

    _run_once(enable=True, expected_sends=1)
    # The first startup override persists enablement. A later restart needs no
    # repeated override, and the peer-scoped visit count survives with it.
    _run_once(enable=False, expected_sends=2)

    assert [row["text"] for row in sends] == [
        "Hello from Meshyface! Visit 1.",
        "Hello from Meshyface! Visit 2.",
    ]


def test_plugins_docs_define_package_and_script_vocabulary() -> None:
    docs = (REPO_ROOT / "docs" / "plugins.md").read_text(encoding="utf-8")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    for token in (
        "# Plugins and Script API (Alpha)",
        "Apps → Scripts (Alpha)",
        "api_version = 1",
        "meshdash.plugins",
        "--plugins-*",
        "MESH_DASH_PLUGINS_*",
        "mesh_dashboard_plugins/hello",
        "one direct child",
        "## Troubleshooting",
        "There is no filesystem hot reload.",
    ):
        assert token in docs
    assert "default plugin directory" in docs
    assert "--plugin-enable hello" in docs
    assert "**Apps → Scripts (Alpha)**" in readme
