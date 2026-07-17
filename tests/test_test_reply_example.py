from __future__ import annotations

import runpy
import shutil
import time
from pathlib import Path
from types import SimpleNamespace

from meshdash.plugin_runtime import PluginRuntime
from meshdash.plugin_state import PluginStateStore
from meshdash.plugins import (
    MessageEvent,
    ReplyAction,
    Script,
    parse_manifest,
    validate_script_against_manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_REPLY_EXAMPLE = REPO_ROOT / "examples" / "plugins" / "test_reply"


class _Mesh:
    def __init__(
        self,
        *,
        nodes: dict[str, dict[str, object]] | None = None,
        city: dict[str, object] | None = None,
    ) -> None:
        self.nodes = nodes if nodes is not None else {
            "!01020304": {
                "id": "!01020304",
                "long_name": "Someone",
                "short_name": "SMON",
                "position": {"latitude": 44.9537, "longitude": -93.09},
            },
            "!00000002": {
                "id": "!00000002",
                "long_name": "Server",
                "short_name": "SRVR",
                "position": {"latitude": 44.98, "longitude": -93.26},
            },
        }
        self.city = city

    def get_node(self, node_id: str):
        return self.nodes.get(node_id)

    def get_node_location(self, node_id: str):
        node = self.get_node(node_id)
        if not node:
            return None
        return node.get("position")

    def nearest_city(self, latitude, longitude):
        if self.city is not None:
            return self.city
        if (latitude, longitude) == (44.9537, -93.09):
            return {
                "name": "Saint Paul",
                "state": "Minnesota",
                "country": "United States of America",
                "distance_km": 1.1,
            }
        return {
            "name": "Minneapolis",
            "state": "Minnesota",
            "country": "United States of America",
            "distance_km": 1.2,
        }


def _wait_until(predicate, *, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition did not become true before timeout")


def _context(
    *,
    text: str = "testing new antenna",
    hops: int | None = 3,
    config: dict[str, object] | None = None,
    is_direct: bool = False,
    is_broadcast: bool = True,
    mesh: _Mesh | None = None,
):
    return SimpleNamespace(
        message=SimpleNamespace(
            text=text,
            sender_id="!01020304",
            local_node_id="!00000002",
            channel_index=0,
            is_direct=is_direct,
            is_broadcast=is_broadcast,
            hops=hops,
            snr=7.5,
            rssi=-81,
        ),
        config=config or {},
        mesh=mesh or _Mesh(),
        reply=lambda value: ReplyAction(value),
    )


def _handler():
    module = runpy.run_path(str(TEST_REPLY_EXAMPLE / "script.py"))
    return module["test_reply"]


def test_test_reply_example_is_copyable_and_matches_its_manifest(tmp_path: Path) -> None:
    installed = tmp_path / "configured-plugins" / "test_reply"
    shutil.copytree(TEST_REPLY_EXAMPLE, installed)

    manifest = parse_manifest(installed / "plugin.toml")
    namespace = runpy.run_path(str(manifest.entrypoint_path))
    script = namespace[manifest.entrypoint_object]

    assert isinstance(script, Script)
    assert validate_script_against_manifest(manifest, script) is script
    assert manifest.id == "test_reply"
    assert manifest.commands == ()
    assert [setting.key for setting in manifest.settings] == [
        "trigger_patterns",
        "response_template",
        "reply_to_broadcast",
        "reply_to_direct",
    ]


def test_test_reply_default_patterns_render_hops_and_nearest_city() -> None:
    action = _handler()(_context())

    assert action == ReplyAction("3 hops to Saint Paul, MN")


def test_test_reply_example_runs_in_spawned_runtime(tmp_path: Path) -> None:
    manifest = parse_manifest(TEST_REPLY_EXAMPLE / "plugin.toml")
    store = PluginStateStore(str(tmp_path / "plugin-state.sqlite3"))
    sends: list[dict[str, object]] = []
    runtime = PluginRuntime(
        manifests=[manifest],
        state_store=store,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)) or {"ok": True},
        node_snapshot_fn=lambda: [
            {
                "id": "!01020304",
                "long_name": "Someone",
                "short_name": "SMON",
                "position": {"latitude": 44.9537, "longitude": -93.09},
            }
        ],
    )
    try:
        runtime.try_enqueue(
            MessageEvent(
                text="testing new antenna",
                sender_id="!01020304",
                destination_id="^all",
                local_node_id="!00000002",
                channel_index=0,
                is_direct=False,
                is_broadcast=True,
                packet_id=123,
                reply_packet_id=None,
                received_at=time.time(),
                hops=3,
            )
        )
        _wait_until(lambda: bool(sends))
    finally:
        runtime.close()
        store.close()

    assert sends[0]["text"] == "3 hops to Saint Paul, MN"
    assert sends[0]["destination"] == "!01020304"
    assert sends[0]["channel_index"] == 0
    assert sends[0]["reply_id"] == 123


def test_test_reply_custom_template_can_use_sender_and_singular_hop() -> None:
    action = _handler()(
        _context(
            text="PING any listeners?",
            hops=1,
            config={
                "trigger_patterns": "ping*, *test*",
                "response_template": "{sender}: {hop_count} {hop_word}",
            },
        )
    )

    assert action == ReplyAction("Someone: 1 hop")


def test_test_reply_ignores_nonmatching_messages_and_disabled_scopes() -> None:
    handler = _handler()

    assert handler(_context(text="weather report")) is None
    assert (
        handler(
            _context(
                config={"reply_to_broadcast": False},
                is_broadcast=True,
                is_direct=False,
            )
        )
        is None
    )


def test_test_reply_degrades_when_hops_and_location_are_unknown() -> None:
    action = _handler()(_context(hops=None, mesh=_Mesh(nodes={})))

    assert action == ReplyAction("unknown hops to unknown city")
