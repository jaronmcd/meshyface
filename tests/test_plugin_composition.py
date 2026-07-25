import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from meshdash.file_transfer_protocol import (
    FILE_TRANSFER_PORTNUM,
    build_file_transfer_ack_frame,
    encode_file_transfer_frame,
    parse_file_transfer_frame_text,
)
from meshdash.plugin_composition import PluginSubsystem, _node_snapshot, build_plugin_subsystem
from meshdash.plugin_state import PluginStateStore


class _Tracker:
    def __init__(self) -> None:
        self.listeners: list[object] = []
        self.state_revision = 0

    def add_accepted_packet_listener(self, listener: object) -> None:
        self.listeners.append(listener)

    def remove_accepted_packet_listener(self, listener: object) -> None:
        self.listeners.remove(listener)


class _OutboundCapture:
    def __init__(self) -> None:
        self.acks: list[dict[str, object]] = []
        self.flows: list[dict[str, object]] = []

    def handle_ack(self, **kwargs: object) -> bool:
        self.acks.append(dict(kwargs))
        return True

    def handle_flow(self, **kwargs: object) -> bool:
        self.flows.append(dict(kwargs))
        return True


def _args(tmp_path: Path, **overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "plugins_included_directory": None,
        "plugins_directory": str(tmp_path / "plugins"),
        "plugins_state_db": str(tmp_path / "plugin-state.sqlite3"),
        "plugins_files_directory": str(tmp_path / "files"),
        "plugins_event_queue_size": 8,
        "plugins_handler_timeout": 1.0,
        "plugin_enable": [],
        "plugin_disable": [],
        "file_transfer_enable": False,
        "file_transfer_max_bytes": 4096,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _write_echo_plugin(root: Path, *, default_enabled: bool = False) -> None:
    directory = root / "echo"
    directory.mkdir(parents=True)
    (directory / "plugin.toml").write_text(
        "\n".join(
            (
                "api_version = 1",
                'id = "echo"',
                'name = "Echo"',
                'version = "1.0.0"',
                'entrypoint = "script.py:script"',
                'commands = ["echo"]',
                f"default_enabled = {str(default_enabled).lower()}",
            )
        ),
        encoding="utf-8",
    )
    (directory / "script.py").write_text(
        """
from meshdash.plugins import Script
script = Script(id="echo", name="Echo", version="1.0.0")
@script.command("echo")
def echo(ctx):
    return ctx.reply("echo works")
""",
        encoding="utf-8",
    )


def test_plugin_node_snapshot_exposes_node_list_fields() -> None:
    snapshot = _node_snapshot(
        SimpleNamespace(
            nodesByNum={
                0x01020304: {
                    "user": {
                        "id": "!01020304",
                        "longName": "Long",
                        "shortName": "Shrt",
                        "hwModel": "T-Echo",
                    },
                    "deviceMetrics": {"batteryLevel": 87},
                    "lastHeard": 1_700_000_100,
                    "hopsAway": 2,
                    "snr": 7.5,
                }
            }
        )
    )

    assert snapshot == [
        {
            "id": "!01020304",
            "node_num": 0x01020304,
            "long_name": "Long",
            "short_name": "Shrt",
            "hardware_model": "T-Echo",
            "last_heard": 1_700_000_100,
            "last_heard_unix": 1_700_000_100,
            "snr": 7.5,
            "hops": 2,
            "hops_away": 2,
            "battery_level": 87,
        }
    ]


def _write_config_plugin(root: Path) -> None:
    directory = root / "configured"
    directory.mkdir(parents=True)
    (directory / "plugin.toml").write_text(
        """api_version = 1
id = "configured"
name = "Configured"
version = "1.0.0"
entrypoint = "script.py:script"
commands = ["configured"]
default_enabled = true

[[settings]]
key = "greeting"
label = "Greeting"
type = "text"
default = "hello"
max_length = 20

[[settings]]
key = "allowed_nodes"
label = "Allowed nodes"
type = "node_ids"
default = []
""",
        encoding="utf-8",
    )
    (directory / "script.py").write_text(
        """
from meshdash.plugins import Script
script = Script(id="configured", name="Configured", version="1.0.0")
@script.command("configured")
def configured(ctx):
    locked = False
    try:
        ctx.config["greeting"] = "changed"
    except TypeError:
        locked = True
    return ctx.reply(
        f"{ctx.config['greeting']}|locked={locked}|tuple={isinstance(ctx.config['allowed_nodes'], tuple)}"
    )
""",
        encoding="utf-8",
    )


def _write_ticker_plugin(root: Path) -> None:
    directory = root / "ticker"
    directory.mkdir(parents=True)
    (directory / "plugin.toml").write_text(
        """api_version = 1
id = "ticker"
name = "Ticker"
version = "1.0.0"
entrypoint = "script.py:script"
commands = ["ticker"]
default_enabled = true
""",
        encoding="utf-8",
    )
    (directory / "script.py").write_text(
        """
from meshdash.plugins import Script
script = Script(id="ticker", name="Ticker", version="1.0.0")
script.ticker("activity", label="Ticker", default_enabled=True)
@script.on_start
def start(ctx):
    ctx.set_ticker("activity", value="on")
@script.command("ticker")
def ticker(ctx):
    return ctx.reply("ticker")
""",
        encoding="utf-8",
    )


def _write_view_plugin(root: Path) -> None:
    directory = root / "viewer"
    directory.mkdir(parents=True)
    (directory / "plugin.toml").write_text(
        """api_version = 1
id = "viewer"
name = "Viewer"
version = "1.0.0"
entrypoint = "script.py:script"
commands = []
default_enabled = true

[[views]]
id = "main"
label = "Viewer"
icon = "VW"
description = "Plugin view test"
""",
        encoding="utf-8",
    )
    (directory / "script.py").write_text(
        """
from meshdash.plugins import Script
script = Script(id="viewer", name="Viewer", version="1.0.0")
script.view(
    "main",
    label="Viewer",
    icon="VW",
    description="Plugin view test",
    content="# Viewer\\n\\nRuntime view body.",
)
""",
        encoding="utf-8",
    )


def _write_node_field_plugin(root: Path) -> None:
    directory = root / "nodefields"
    directory.mkdir(parents=True)
    (directory / "plugin.toml").write_text(
        """api_version = 1
id = "nodefields"
name = "Node Fields"
version = "1.0.0"
entrypoint = "script.py:script"
commands = []
default_enabled = true
""",
        encoding="utf-8",
    )
    (directory / "script.py").write_text(
        """
from meshdash.plugins import Script
script = Script(id="nodefields", name="Node Fields", version="1.0.0")
script.node_field(
    "quality",
    label="Quality",
    group="Signal",
    value_type="number",
    render_kinds=("metric", "pill", "bar"),
    default_render_kind="metric",
    default_visible=True,
    sortable=True,
)
@script.on_start
def start(ctx):
    ctx.set_node_field(
        "!01020304",
        "quality",
        value=87,
        sort=87,
        title="Quality: 87",
    )
""",
        encoding="utf-8",
    )


def _wait_until(predicate, timeout: float = 4.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition did not become true")


def _package_digest(subsystem: object, plugin_id: str) -> str:
    status = subsystem.status()  # type: ignore[attr-defined]
    scripts = status["scripts"]
    return str(next(row for row in scripts if row["id"] == plugin_id)["package_digest"])


def test_enabled_master_with_no_enabled_plugins_registers_live_management_listener(
    tmp_path,
) -> None:
    tracker = _Tracker()
    subsystem = build_plugin_subsystem(
        args=_args(tmp_path),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=tracker,
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        status = subsystem.status()
        assert status["enabled"] is True
        assert status["discovered"] == 0
        assert status["directory"] == str(tmp_path / "plugins")
        assert status["runtime"] == {}
        assert len(tracker.listeners) == 1
    finally:
        subsystem.close()


def test_status_exposes_readme_without_local_package_path(tmp_path) -> None:
    plugin_root = tmp_path / "plugins"
    _write_echo_plugin(plugin_root)
    (plugin_root / "echo" / "README.md").write_text(
        "# Echo\n\nUse `!echo` from the console or mesh.",
        encoding="utf-8",
    )
    subsystem = build_plugin_subsystem(
        args=_args(tmp_path),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        script_status = subsystem.status()["scripts"][0]  # type: ignore[index]
        assert script_status["readme"] == {
            "filename": "README.md",
            "content": "# Echo\n\nUse `!echo` from the console or mesh.",
            "truncated": False,
        }
        assert str(tmp_path) not in str(script_status["readme"])
    finally:
        subsystem.close()


def test_individual_enablement_loads_in_worker_and_routes_accepted_event(tmp_path) -> None:
    plugin_root = tmp_path / "plugins"
    _write_echo_plugin(plugin_root)
    tracker = _Tracker()
    sends: list[dict[str, object]] = []
    subsystem = build_plugin_subsystem(
        args=_args(tmp_path, plugin_enable=["echo"]),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=tracker,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)) or {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        assert len(tracker.listeners) == 1, subsystem.status()
        listener = tracker.listeners[0]
        listener(  # type: ignore[operator]
            {
                "from": 1,
                "to": 2,
                "id": 99,
                "channel": 0,
                "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "!echo"},
            },
            object(),
        )
        _wait_until(lambda: bool(sends))
        assert sends[0]["text"] == "echo works"
        status = subsystem.status()
        assert status["enabled_plugins"] == ["echo"]
        assert status["runtime"]["status"] == "running"  # type: ignore[index]
        assert status["runtime"]["worker_alive"] is True  # type: ignore[index]
        assert status["scripts"][0]["runtime_status"] == "running"  # type: ignore[index]
        assert status["scripts"][0]["runtime_error"] == ""  # type: ignore[index]
        assert status["scripts"][0]["restart_required"] is False  # type: ignore[index]
    finally:
        subsystem.close()
    assert tracker.listeners == []


def test_individual_enablement_starts_live_and_persists_for_the_next_runtime(tmp_path) -> None:
    plugin_root = tmp_path / "plugins"
    _write_echo_plugin(plugin_root)
    args = _args(tmp_path)
    first = build_plugin_subsystem(
        args=args,
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        assert first.status()["enabled_plugins"] == []
        assert first.set_plugin_enabled(
            "echo",
            True,
            expected_package_digest=_package_digest(first, "echo"),
        ) == {
            "ok": True,
            "plugin_id": "echo",
            "enabled": True,
            "active": True,
            "restart_required": False,
        }
        _wait_until(
            lambda: first.status()["scripts"][0]["runtime_status"] == "running"  # type: ignore[index]
        )
        script = first.status()["scripts"][0]  # type: ignore[index]
        assert script["active"] is True
        assert script["restart_required"] is False
    finally:
        first.close()

    second = build_plugin_subsystem(
        args=args,
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        assert second.status()["enabled_plugins"] == ["echo"]
    finally:
        second.close()


def test_runtime_master_disable_preserves_enablement_and_persists(tmp_path) -> None:
    plugin_root = tmp_path / "plugins"
    _write_echo_plugin(plugin_root)
    args = _args(tmp_path, plugin_enable=["echo"])
    first = build_plugin_subsystem(
        args=args,
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        _wait_until(
            lambda: first.status()["scripts"][0]["runtime_status"] == "running"  # type: ignore[index]
        )
        assert first.status()["runtime_enabled"] is True
        assert first.status()["enabled_plugins"] == ["echo"]
        assert first.set_runtime_enabled(False) == {
            "ok": True,
            "runtime_enabled": False,
            "enabled_plugins": [],
        }
        disabled_status = first.status()
        disabled_script = disabled_status["scripts"][0]  # type: ignore[index]
        assert disabled_status["runtime_enabled"] is False
        assert disabled_status["enabled_plugins"] == []
        assert disabled_script["enabled"] is True
        assert disabled_script["active"] is False
        assert disabled_script["runtime_status"] == "master_disabled"
        command_result = first.run_console_command(command="echo", text="!echo")
        assert command_result["ok"] is False
        assert command_result["error"]["code"] == "plugin_runtime_disabled"  # type: ignore[index]
    finally:
        first.close()

    reopened = build_plugin_subsystem(
        args=args,
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        reopened_status = reopened.status()
        reopened_script = reopened_status["scripts"][0]  # type: ignore[index]
        assert reopened_status["runtime_enabled"] is False
        assert reopened_script["enabled"] is True
        assert reopened_script["active"] is False
        assert reopened.set_runtime_enabled(True) == {
            "ok": True,
            "runtime_enabled": True,
            "enabled_plugins": ["echo"],
        }
        _wait_until(
            lambda: reopened.status()["scripts"][0]["runtime_status"] == "running"  # type: ignore[index]
        )
    finally:
        reopened.close()


def test_local_manifest_default_true_does_not_self_enable(tmp_path) -> None:
    _write_echo_plugin(tmp_path / "plugins", default_enabled=True)
    subsystem = build_plugin_subsystem(
        args=_args(tmp_path),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        status = subsystem.status()
        script = status["scripts"][0]  # type: ignore[index]
        assert status["enabled_plugins"] == []
        assert script["enabled"] is False
        assert script["default_enabled"] is False
        assert script["declared_default_enabled"] is True
        assert str(script["package_digest"]).startswith("sha256:")
    finally:
        subsystem.close()


def test_management_mutations_require_current_package_identity(tmp_path) -> None:
    _write_echo_plugin(tmp_path / "plugins")
    subsystem = build_plugin_subsystem(
        args=_args(tmp_path),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        initial_script = subsystem.status()["scripts"][0]  # type: ignore[index]
        assert initial_script["approval_status"] == "new"
        assert initial_script["identity_changed"] is False
        with pytest.raises(TypeError, match="expected_package_digest"):
            subsystem.set_plugin_enabled("echo", True)  # type: ignore[call-arg]
        with pytest.raises(TypeError, match="expected_package_digest"):
            subsystem.set_plugin_settings("echo", {})  # type: ignore[call-arg]
        with pytest.raises(TypeError, match="expected_package_digest"):
            subsystem.set_plugin_route_policy(  # type: ignore[call-arg]
                "echo",
                mesh_enabled=False,
                console_enabled=True,
            )
        stale_result = subsystem.set_plugin_enabled(
            "echo",
            True,
            expected_package_digest=f"sha256:{'0' * 64}",
        )
        assert stale_result["ok"] is False
        assert stale_result["error"]["code"] == "plugin_identity_changed"  # type: ignore[index]
        stale_route_result = subsystem.set_plugin_route_policy(
            "echo",
            mesh_enabled=False,
            console_enabled=True,
            expected_package_digest=f"sha256:{'0' * 64}",
        )
        assert stale_route_result["ok"] is False
        assert stale_route_result["error"]["code"] == "plugin_identity_changed"  # type: ignore[index]
        assert subsystem.status()["enabled_plugins"] == []
    finally:
        subsystem.close()


def test_plugin_ticker_policy_filters_runtime_tickers_without_disabling_script(tmp_path) -> None:
    plugin_root = tmp_path / "plugins"
    _write_ticker_plugin(plugin_root)
    tracker = _Tracker()
    subsystem = build_plugin_subsystem(
        args=_args(tmp_path, plugin_enable=["ticker"]),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=tracker,
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        _wait_until(lambda: len(subsystem.status()["runtime"].get("tickers", [])) == 1)  # type: ignore[union-attr]
        status = subsystem.status()
        package_digest = status["scripts"][0]["package_digest"]  # type: ignore[index]
        assert status["scripts"][0]["ticker_enabled"] is True  # type: ignore[index]

        result = subsystem.set_plugin_route_policy(
            "ticker",
            mesh_enabled=True,
            console_enabled=True,
            ticker_enabled=False,
            expected_package_digest=package_digest,
        )

        assert result == {
            "ok": True,
            "plugin_id": "ticker",
            "mesh_enabled": True,
            "console_enabled": True,
            "ticker_enabled": False,
            "view_enabled": True,
        }
        filtered_status = subsystem.status()
        assert filtered_status["enabled_plugins"] == ["ticker"]
        assert filtered_status["scripts"][0]["enabled"] is True  # type: ignore[index]
        assert filtered_status["scripts"][0]["ticker_enabled"] is False  # type: ignore[index]
        assert filtered_status["scripts"][0]["view_enabled"] is True  # type: ignore[index]
        assert filtered_status["runtime"]["tickers"] == []  # type: ignore[index]
    finally:
        subsystem.close()


def test_plugin_status_exposes_manifest_views_with_runtime_content(tmp_path) -> None:
    plugin_root = tmp_path / "plugins"
    _write_view_plugin(plugin_root)
    subsystem = build_plugin_subsystem(
        args=_args(tmp_path, plugin_enable=["viewer"]),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        _wait_until(
            lambda: subsystem.status()["scripts"][0]["runtime_status"] == "running"  # type: ignore[index]
        )
        status = subsystem.status()
        script = status["scripts"][0]  # type: ignore[index]

        assert script["view_enabled"] is True
        assert script["views"] == [
            {
                "id": "main",
                "label": "Viewer",
                "icon": "VW",
                "description": "Plugin view test",
                "plugin_id": "viewer",
                "plugin_name": "Viewer",
                "enabled": True,
                "active": True,
                "runtime_status": "running",
                "content": "# Viewer\n\nRuntime view body.",
            }
        ]
        assert status["runtime"]["plugins"]["viewer"]["views"] == [  # type: ignore[index]
            {
                "id": "main",
                "label": "Viewer",
                "icon": "VW",
                "description": "Plugin view test",
                "content": "# Viewer\n\nRuntime view body.",
            }
        ]

        result = subsystem.set_plugin_route_policy(
            "viewer",
            mesh_enabled=True,
            console_enabled=True,
            ticker_enabled=True,
            view_enabled=False,
            expected_package_digest=script["package_digest"],
        )

        assert result == {
            "ok": True,
            "plugin_id": "viewer",
            "mesh_enabled": True,
            "console_enabled": True,
            "ticker_enabled": True,
            "view_enabled": False,
        }
        disabled_status = subsystem.status()
        disabled_script = disabled_status["scripts"][0]  # type: ignore[index]
        assert disabled_status["enabled_plugins"] == ["viewer"]
        assert disabled_script["enabled"] is True
        assert disabled_script["active"] is True
        assert disabled_script["view_enabled"] is False
        assert disabled_script["views"][0]["content"] == "# Viewer\n\nRuntime view body."
    finally:
        subsystem.close()


def test_plugin_status_exposes_runtime_node_field_definitions(tmp_path) -> None:
    plugin_root = tmp_path / "plugins"
    _write_node_field_plugin(plugin_root)
    subsystem = build_plugin_subsystem(
        args=_args(tmp_path, plugin_enable=["nodefields"]),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        _wait_until(
            lambda: len(subsystem.status()["runtime"].get("node_fields", [])) == 1  # type: ignore[union-attr]
            and len(subsystem.status()["runtime"].get("node_field_values", [])) == 1  # type: ignore[union-attr]
        )
        status = subsystem.status()

        assert status["runtime"]["node_fields"] == [  # type: ignore[index]
            {
                "id": "plugin:nodefields:quality",
                "plugin_id": "nodefields",
                "field_id": "quality",
                "label": "Quality",
                "group": "Signal",
                "value_type": "number",
                "render_kinds": ["metric", "pill", "bar"],
                "default_render_kind": "metric",
                "default_visible": True,
                "sortable": True,
                "runtime_status": "running",
            }
        ]
        assert status["runtime"]["node_field_values"] == [  # type: ignore[index]
            {
                "id": "plugin:nodefields:quality",
                "plugin_id": "nodefields",
                "field_id": "quality",
                "node_id": "!01020304",
                "value": 87,
                "sort": 87,
                "title": "Quality: 87",
                "updated_at": status["runtime"]["node_field_values"][0]["updated_at"],  # type: ignore[index]
                "runtime_status": "running",
            }
        ]
        assert status["runtime"]["plugins"]["nodefields"]["node_fields"] == [  # type: ignore[index]
            {
                "id": "quality",
                "label": "Quality",
                "group": "Signal",
                "value_type": "number",
                "render_kinds": ["metric", "pill", "bar"],
                "default_render_kind": "metric",
                "default_visible": True,
                "sortable": True,
            }
        ]
    finally:
        subsystem.close()


def test_replaced_known_package_preserves_persisted_enablement(tmp_path) -> None:
    plugin_root = tmp_path / "plugins"
    _write_echo_plugin(plugin_root)
    first = build_plugin_subsystem(
        args=_args(tmp_path),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        assert first.set_plugin_enabled(
            "echo",
            True,
            expected_package_digest=_package_digest(first, "echo"),
        )["ok"] is True
    finally:
        first.close()

    script_path = plugin_root / "echo" / "script.py"
    script_path.write_text(
        script_path.read_text(encoding="utf-8").replace(
            "echo works",
            "edited code",
        ),
        encoding="utf-8",
    )
    reopened = build_plugin_subsystem(
        args=_args(tmp_path),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        status = reopened.status()
        assert status["enabled_plugins"] == ["echo"]
        assert status["scripts"][0]["enabled"] is True  # type: ignore[index]
        assert status["scripts"][0]["approval_status"] == "known_enabled"  # type: ignore[index]
        assert status["scripts"][0]["identity_changed"] is False  # type: ignore[index]
    finally:
        reopened.close()


def test_persistent_enable_continues_to_work_across_local_edits(tmp_path) -> None:
    plugin_root = tmp_path / "plugins"
    _write_echo_plugin(plugin_root)
    args = _args(tmp_path, plugin_enable=["echo"])
    first = build_plugin_subsystem(
        args=args,
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        assert first.status()["enabled_plugins"] == ["echo"]
        old_digest = _package_digest(first, "echo")
    finally:
        first.close()

    script_path = plugin_root / "echo" / "script.py"
    script_path.write_text(
        script_path.read_text(encoding="utf-8").replace(
            "echo works",
            "edited code",
        ),
        encoding="utf-8",
    )
    reopened = build_plugin_subsystem(
        args=args,
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        status = reopened.status()
        assert status["enabled_plugins"] == ["echo"]
        assert status["scripts"][0]["enabled"] is True  # type: ignore[index]
        assert status["discovery_errors"] == []
        new_digest = _package_digest(reopened, "echo")
        assert new_digest != old_digest
    finally:
        reopened.close()


def test_live_package_edit_requires_restart_before_enablement_change(tmp_path) -> None:
    plugin_root = tmp_path / "plugins"
    _write_echo_plugin(plugin_root)
    subsystem = build_plugin_subsystem(
        args=_args(tmp_path),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        (plugin_root / "echo" / "new.py").write_text(
            "changed = True\n",
            encoding="utf-8",
        )
        result = subsystem.set_plugin_enabled(
            "echo",
            True,
            expected_package_digest=_package_digest(subsystem, "echo"),
        )
        assert result["ok"] is False
        assert result["error"]["code"] == "plugin_package_changed"  # type: ignore[index]
        assert subsystem.status()["enabled_plugins"] == []
    finally:
        subsystem.close()


def test_malformed_local_package_is_isolated_from_healthy_plugins(tmp_path) -> None:
    root = tmp_path / "plugins"
    _write_echo_plugin(root)
    broken = root / "broken"
    broken.mkdir(parents=True)
    (broken / "plugin.toml").write_text("not = [valid", encoding="utf-8")
    subsystem = build_plugin_subsystem(
        args=_args(tmp_path, plugin_enable=["echo", "broken"]),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        _wait_until(
            lambda: subsystem.status()["scripts"][0]["runtime_status"] == "running"  # type: ignore[index]
        )
        status = subsystem.status()
        assert status["error"] == ""
        assert status["discovered"] == 1
        assert status["enabled_plugins"] == ["echo"]
        assert len(status["discovery_errors"]) == 2  # type: ignore[arg-type]
        assert any(
            "invalid TOML" in error for error in status["discovery_errors"]  # type: ignore[union-attr]
        )
        assert any(
            "--plugin-enable references unknown plugin 'broken'" in error
            for error in status["discovery_errors"]  # type: ignore[union-attr]
        )
        assert str(tmp_path) not in str(status["discovery_errors"])
    finally:
        subsystem.close()


def test_plugin_configuration_is_validated_persisted_and_live_on_next_event(tmp_path) -> None:
    plugin_root = tmp_path / "plugins"
    _write_config_plugin(plugin_root)
    tracker = _Tracker()
    sends: list[dict[str, object]] = []
    subsystem = build_plugin_subsystem(
        args=_args(tmp_path, plugin_enable=["configured"]),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=tracker,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)) or {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )

    def _send(packet_id: int) -> None:
        tracker.listeners[0](
            {
                "from": 1,
                "to": 2,
                "id": packet_id,
                "channel": 0,
                "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "!configured"},
            },
            object(),
        )

    try:
        _wait_until(
            lambda: subsystem.status()["scripts"][0]["runtime_status"] == "running"  # type: ignore[index]
        )
        script_status = subsystem.status()["scripts"][0]  # type: ignore[index]
        assert script_status["settings"] == {"greeting": "hello", "allowed_nodes": []}
        assert [row["type"] for row in script_status["settings_schema"]] == [  # type: ignore[index]
            "text",
            "node_ids",
        ]

        _send(1)
        _wait_until(lambda: len(sends) == 1)
        assert sends[-1]["text"] == "hello|locked=True|tuple=True"

        assert subsystem.set_plugin_settings(
            "configured",
            {"greeting": "updated", "allowed_nodes": ["!AABBCCDD"]},
            expected_package_digest=_package_digest(subsystem, "configured"),
        ) == {
            "ok": True,
            "plugin_id": "configured",
            "settings": {"greeting": "updated", "allowed_nodes": ["!aabbccdd"]},
        }
        assert tracker.state_revision == 1
        _send(2)
        _wait_until(lambda: len(sends) == 2)
        assert sends[-1]["text"] == "updated|locked=True|tuple=True"
    finally:
        subsystem.close()

    reopened = build_plugin_subsystem(
        args=_args(tmp_path),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        assert reopened.status()["scripts"][0]["settings"] == {  # type: ignore[index]
            "greeting": "updated",
            "allowed_nodes": ["!aabbccdd"],
        }
    finally:
        reopened.close()


def test_replacement_package_automatically_inherits_compatible_settings(
    tmp_path,
) -> None:
    root = tmp_path / "plugins"
    _write_config_plugin(root)
    first = build_plugin_subsystem(
        args=_args(tmp_path, plugin_enable=["configured"]),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        assert first.set_plugin_settings(
            "configured",
            {"greeting": "private-value", "allowed_nodes": ["!01020304"]},
            expected_package_digest=_package_digest(first, "configured"),
        )["ok"] is True
    finally:
        first.close()

    script_path = root / "configured" / "script.py"
    script_path.write_text(
        script_path.read_text(encoding="utf-8") + "\n# replacement package\n",
        encoding="utf-8",
    )
    replacement = build_plugin_subsystem(
        args=_args(tmp_path),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        status = replacement.status()
        assert status["enabled_plugins"] == ["configured"]
        assert status["scripts"][0]["settings"] == {  # type: ignore[index]
            "greeting": "private-value",
            "allowed_nodes": ["!01020304"],
        }
    finally:
        replacement.close()


def test_replacement_package_leaves_incompatible_settings_unbound(tmp_path) -> None:
    root = tmp_path / "plugins"
    _write_config_plugin(root)
    first = build_plugin_subsystem(
        args=_args(tmp_path, plugin_enable=["configured"]),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        assert first.set_plugin_settings(
            "configured",
            {"greeting": "private-value", "allowed_nodes": ["!01020304"]},
            expected_package_digest=_package_digest(first, "configured"),
        )["ok"] is True
    finally:
        first.close()

    manifest_path = root / "configured" / "plugin.toml"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            "max_length = 20",
            "max_length = 5",
        ),
        encoding="utf-8",
    )
    replacement = build_plugin_subsystem(
        args=_args(tmp_path),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        assert replacement.status()["enabled_plugins"] == ["configured"]
        assert replacement.status()["scripts"][0]["settings"] == {  # type: ignore[index]
            "greeting": "hello",
            "allowed_nodes": [],
        }
    finally:
        replacement.close()


def test_startup_reconciles_legacy_identity_settings_and_sessions(tmp_path) -> None:
    root = tmp_path / "plugins"
    _write_config_plugin(root)
    state_path = tmp_path / "plugin-state.sqlite3"
    connection = sqlite3.connect(state_path)
    connection.execute(
        """
        CREATE TABLE plugin_settings (
            plugin_id TEXT PRIMARY KEY,
            settings_json TEXT NOT NULL,
            updated_unix INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE plugin_enablement (
            plugin_id TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL,
            updated_unix INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO plugin_settings(plugin_id, settings_json, updated_unix)
        VALUES (?, ?, ?)
        """,
        (
            "configured",
            '{"allowed_nodes":["!01020304"],"greeting":"legacy-value"}',
            100,
        ),
    )
    connection.execute(
        """
        INSERT INTO plugin_enablement(plugin_id, enabled, updated_unix)
        VALUES (?, ?, ?)
        """,
        ("configured", 1, 100),
    )
    connection.commit()
    connection.close()
    legacy_store = PluginStateStore(str(state_path))
    legacy_store.start_session(
        "!00000002",
        "!01020304",
        "configured",
        3,
    )
    legacy_store.close()

    subsystem = build_plugin_subsystem(
        args=_args(tmp_path),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        initial_script = subsystem.status()["scripts"][0]  # type: ignore[index]
        assert initial_script["approval_status"] == "known_enabled"
        assert initial_script["identity_changed"] is False
        assert initial_script["settings"] == {
            "greeting": "legacy-value",
            "allowed_nodes": ["!01020304"],
        }
        assert subsystem._state_store is not None
        assert (
            subsystem._state_store.active_session(
                "!00000002",
                "!01020304",
                3,
            )
            is None
        )
    finally:
        subsystem.close()


def test_individual_disable_stops_live_routing_and_the_last_worker(tmp_path) -> None:
    plugin_root = tmp_path / "plugins"
    _write_echo_plugin(plugin_root)
    tracker = _Tracker()
    sends: list[dict[str, object]] = []
    subsystem = build_plugin_subsystem(
        args=_args(tmp_path, plugins_handler_timeout=5.0),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=tracker,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)) or {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    packet = {
        "from": 1,
        "to": 2,
        "id": 99,
        "channel": 0,
        "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "!echo"},
    }
    try:
        assert subsystem.set_plugin_enabled(
            "echo",
            True,
            expected_package_digest=_package_digest(subsystem, "echo"),
        )["active"] is True
        assert tracker.state_revision == 1
        _wait_until(
            lambda: subsystem.status()["scripts"][0]["runtime_status"] == "running"  # type: ignore[index]
        )
        tracker.listeners[0](packet, object())  # type: ignore[operator]
        _wait_until(lambda: len(sends) == 1)

        disable_started = time.monotonic()
        assert subsystem.set_plugin_enabled(
            "echo",
            False,
            expected_package_digest=_package_digest(subsystem, "echo"),
        ) == {
            "ok": True,
            "plugin_id": "echo",
            "enabled": False,
            "active": False,
            "restart_required": False,
        }
        assert time.monotonic() - disable_started < 2.0
        assert tracker.state_revision == 2
        status = subsystem.status()
        assert status["enabled_plugins"] == []
        assert status["runtime"] == {}
        assert status["scripts"][0]["runtime_status"] == "disabled"  # type: ignore[index]
        assert status["scripts"][0]["approval_status"] == "known_disabled"  # type: ignore[index]
        assert status["scripts"][0]["identity_changed"] is False  # type: ignore[index]

        tracker.listeners[0](packet, object())  # type: ignore[operator]
        time.sleep(0.2)
        assert len(sends) == 1
    finally:
        subsystem.close()


def test_broken_plugin_is_reported_without_preventing_healthy_plugin(tmp_path) -> None:
    root = tmp_path / "plugins"
    _write_echo_plugin(root, default_enabled=True)
    broken = root / "broken"
    broken.mkdir()
    (broken / "plugin.toml").write_text(
        "\n".join(
            (
                "api_version = 1",
                'id = "broken"',
                'name = "Broken"',
                'version = "1.0.0"',
                'entrypoint = "script.py:script"',
                "commands = []",
                "default_enabled = true",
            )
        ),
        encoding="utf-8",
    )
    (broken / "script.py").write_text(
        "raise RuntimeError(f'import failed at {__file__}')\n",
        encoding="utf-8",
    )
    subsystem = build_plugin_subsystem(
        args=_args(tmp_path, plugin_enable=["echo", "broken"]),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        assert subsystem.status()["error"] == ""
        _wait_until(
            lambda: bool(subsystem.status().get("runtime", {}).get("plugins"))  # type: ignore[union-attr]
        )
        status = subsystem.status()
        plugins = status["runtime"]["plugins"]  # type: ignore[index]
        assert status["runtime"]["worker_alive"] is True  # type: ignore[index]
        assert status["runtime"]["status"] == "running"  # type: ignore[index]
        assert "import failed" in plugins["broken"]["error"]
        assert "[path]" in plugins["broken"]["error"]
        assert plugins["echo"].get("error") is None
        scripts = {row["id"]: row for row in status["scripts"]}  # type: ignore[index]
        assert scripts["broken"]["runtime_status"] == "error"
        assert "import failed" in scripts["broken"]["runtime_error"]
        assert scripts["echo"]["runtime_status"] == "running"
        assert scripts["echo"]["runtime_error"] == ""
        assert str(tmp_path) not in str(status["runtime"])
        assert str(tmp_path) not in str(status["scripts"])
    finally:
        subsystem.close()


def test_plugin_file_action_queues_host_managed_outbound_job(tmp_path) -> None:
    root = tmp_path / "plugins"
    directory = root / "files"
    directory.mkdir(parents=True)
    (directory / "plugin.toml").write_text(
        "\n".join(
            (
                "api_version = 1",
                'id = "files"',
                'name = "Files"',
                'version = "1.0.0"',
                'entrypoint = "script.py:script"',
                'commands = ["file"]',
                "default_enabled = true",
            )
        ),
        encoding="utf-8",
    )
    (directory / "script.py").write_text(
        """
from meshdash.plugins import Script
script = Script(id="files", name="Files", version="1.0.0")
@script.command("file")
def send_file(ctx):
    return ctx.mesh.send_file(ctx.message.sender_id, "sample.bin")
""",
        encoding="utf-8",
    )
    approved = tmp_path / "files"
    approved.mkdir()
    (approved / "sample.bin").write_bytes(b"plugin file payload")
    tracker = _Tracker()
    sends: list[dict[str, object]] = []
    subsystem = build_plugin_subsystem(
        args=_args(
            tmp_path,
            file_transfer_enable=True,
            plugins_files_directory=str(approved),
            plugin_enable=["files"],
        ),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=tracker,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)) or {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        tracker.listeners[0](  # type: ignore[operator]
            {
                "from": 1,
                "to": 2,
                "id": 101,
                "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "!file"},
            },
            object(),
        )
        _wait_until(
            lambda: any(str(send.get("text") or "").startswith("MF_FILE_V2|M|") for send in sends)
        )
        metadata_text = next(
            str(send["text"])
            for send in sends
            if str(send.get("text") or "").startswith("MF_FILE_V2|M|")
        )
        metadata = parse_file_transfer_frame_text(metadata_text)
        assert metadata is not None
        transfer_id = str(metadata["transfer_id"])
        total_chunks = int(metadata["total_chunks"])

        def _deliver_ack(received_indexes: object, packet_id: int) -> None:
            ack_text = build_file_transfer_ack_frame(
                transfer_id=transfer_id,
                total_chunks=total_chunks,
                received_indexes=received_indexes,
            )
            ack = parse_file_transfer_frame_text(ack_text)
            assert ack is not None
            tracker.listeners[0](  # type: ignore[operator]
                {
                    "from": 1,
                    "to": 2,
                    "id": packet_id,
                    "channel": 0,
                    "decoded": {
                        "portnum": FILE_TRANSFER_PORTNUM,
                        "payload": encode_file_transfer_frame(ack),
                    },
                },
                object(),
            )

        _deliver_ack((), 201)
        _wait_until(
            lambda: (
                sum(str(send.get("text") or "").startswith("MF_FILE_V2|C|") for send in sends)
                == total_chunks
            )
        )
        _deliver_ack(range(total_chunks), 202)
        _wait_until(
            lambda: subsystem.status()["file_jobs"]["completed_count"] == 1  # type: ignore[index]
        )
        file_status = subsystem.status()["file_jobs"]
        assert file_status["submitted_count"] == 1  # type: ignore[index]
        assert file_status["completed_count"] == 1  # type: ignore[index]
    finally:
        subsystem.close()


def test_file_transfer_control_frames_forward_channel_and_local_destination() -> None:
    outbound = _OutboundCapture()
    subsystem = PluginSubsystem(  # type: ignore[arg-type]
        state_store=None,
        runtime=None,
        outbound_files=outbound,
    )
    ack = parse_file_transfer_frame_text(
        build_file_transfer_ack_frame(
            transfer_id="abcdef123456",
            total_chunks=1,
            received_indexes=(),
        )
    )
    assert ack is not None

    def _packet(frame: dict[str, object]) -> dict[str, object]:
        return {
            "from": 1,
            "to": 2,
            "channel": 4,
            "decoded": {
                "portnum": FILE_TRANSFER_PORTNUM,
                "payload": encode_file_transfer_frame(frame),
            },
        }

    subsystem.on_file_transfer_receive(_packet(ack))
    subsystem.on_file_transfer_receive(
        _packet(
            {
                "kind": "flow",
                "transfer_id": "abcdef123456",
                "action": "cancel",
            }
        )
    )

    assert outbound.acks[0]["sender_id"] == "!00000001"
    assert outbound.acks[0]["destination_id"] == "!00000002"
    assert outbound.acks[0]["channel_index"] == 4
    assert outbound.flows[0]["sender_id"] == "!00000001"
    assert outbound.flows[0]["destination_id"] == "!00000002"
    assert outbound.flows[0]["channel_index"] == 4

    missing_destination = _packet(ack)
    missing_destination.pop("to")
    subsystem.on_file_transfer_receive(missing_destination)
    assert len(outbound.acks) == 1
