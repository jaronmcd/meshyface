import threading
import time
import sys
from types import ModuleType
from types import SimpleNamespace

from meshdash.dashboard_runtime_context import (
    StartupReceiveBuffer,
    build_dashboard_runtime_context,
)
from meshdash.dashboard_runtime_loaders import DashboardRuntimeLoaders


class _RevisionInfo:
    version = "0.1.0"
    commit = "test"
    label = "Rev: test"
    title = "Dashboard revision: test"


def _args(tmp_path, *, no_history: bool = False):
    return SimpleNamespace(
        history_db=str(tmp_path / "history.sqlite3"),
        no_history=no_history,
        seed_from_node_db=False,
        history_max_rows=1000,
        history_retention_days=7,
        history_event_max_rows=1000,
        history_event_retention_days=30,
        history_rollup_retention_days=365,
        packet_limit=25,
        show_secrets=False,
        debug_mode=False,
        node_history_hours=72,
        node_history_max_points=1440,
        refresh_ms=3000,
        reset_ticker_scale_on_restart=False,
        http_host="127.0.0.1",
        http_port=0,
        games_enable=False,
        bots_enable=False,
        file_transfer_enable=False,
        file_transfer_auto_accept=False,
    )


def _loaders(**_kwargs: object) -> DashboardRuntimeLoaders:
    return DashboardRuntimeLoaders(
        state_fn=lambda: {},
        node_history_fn=lambda *_args, **_kwargs: {},
        summary_metrics_fn=lambda *_args, **_kwargs: {},
        send_chat_fn=lambda **_kwargs: {"ok": True},
    )


def test_startup_receive_replay_waits_for_history_local_node_id(
    tmp_path,
    monkeypatch,
) -> None:
    events: list[tuple[str, object]] = []
    subscriptions: list[object] = []
    iface = object()

    class _Store:
        def __init__(self, **_kwargs: object) -> None:
            self.local_node_id = ""

        def close(self) -> None:
            events.append(("close_store", None))

    class _Tracker:
        def __init__(self, packet_limit: int, history_store: object) -> None:
            del packet_limit
            self.history_store = history_store

        def on_receive(self, packet: object, interface: object) -> None:
            del packet, interface
            events.append(
                ("receive_local_id", getattr(self.history_store, "local_node_id", ""))
            )

    def _subscribe(callback: object, topic: str) -> None:
        if topic == "meshtastic.receive":
            events.append(("subscribe", topic))
            subscriptions.append(callback)

    def _open_mesh_interface(_args: object) -> object:
        events.append(("open_interface", None))
        for callback in list(subscriptions):
            callback({"id": "backlog"}, iface)  # type: ignore[operator]
        return iface

    poison_plugin_composition = ModuleType("meshdash.plugin_composition")

    def _unexpected_plugin_build(**_kwargs: object) -> None:
        raise AssertionError("disabled plugin subsystem must not be composed")

    poison_plugin_composition.build_plugin_subsystem = _unexpected_plugin_build  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules,
        "meshdash.plugin_composition",
        poison_plugin_composition,
    )

    args = _args(tmp_path)
    args.bots_state_db = str(tmp_path / "must-not-exist.sqlite3")
    plugin_directory = tmp_path / "plugins" / "must_not_import"
    plugin_directory.mkdir(parents=True)
    import_marker = tmp_path / "plugin-imported"
    (plugin_directory / "bot.toml").write_text(
        "api_version=1\nid='disabled'\nname='Disabled'\nversion='1'\n"
        "entrypoint='bot.py:bot'\ncommands=[]\ndefault_enabled=true\n",
        encoding="utf-8",
    )
    (plugin_directory / "bot.py").write_text(
        f"from pathlib import Path\nPath({str(import_marker)!r}).touch()\n",
        encoding="utf-8",
    )
    args.bots_directory = str(tmp_path / "plugins")
    context = build_dashboard_runtime_context(
        args,
        mesh_target_label_fn=lambda _args: "/dev/ttyUSB0 (serial)",
        open_mesh_interface_fn=_open_mesh_interface,
        history_store_cls=_Store,
        dashboard_tracker_cls=_Tracker,
        subscribe_fn=_subscribe,
        seed_tracker_fn=lambda _tracker, _iface: None,
        revision_info_fn=_RevisionInfo,
        send_chat_message_fn=lambda **_kwargs: {},
        send_reaction_packet_fn=lambda **_kwargs: None,
        get_local_node_id_fn=lambda _iface: "!12345678",
        normalize_single_emoji_fn=lambda _value: (None, None),
        to_int_fn=lambda _value: None,
        utc_now_fn=lambda: "2026-06-07T00:00:00Z",
        build_state_fn=lambda **_kwargs: {},
        build_state_snapshot_loader_fn=lambda *_args, **_kwargs: lambda: {},
        build_node_history_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        build_summary_metrics_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        build_send_chat_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        default_chat_max_bytes=200,
        build_dashboard_runtime_loaders_fn=_loaders,
    )

    assert events.index(("subscribe", "meshtastic.receive")) < events.index(
        ("open_interface", None)
    )
    assert ("receive_local_id", "!12345678") in events
    assert context.send_chat_fn(text="normal messaging") == {"ok": True}
    assert context.tracker.get_plugin_runtime() == {"enabled": False}
    assert not (tmp_path / "must-not-exist.sqlite3").exists()
    assert not import_marker.exists()
    assert not any(
        thread.name.startswith("meshyface-plugin") for thread in threading.enumerate()
    )


def test_startup_receive_buffer_preserves_order_during_activation() -> None:
    receive_buffer = StartupReceiveBuffer()
    iface = object()
    events: list[str] = []
    live_started = threading.Event()
    live_delivered = threading.Event()

    receive_buffer.on_receive({"id": "buffered"}, iface)

    def _callback(packet: object, _interface: object) -> None:
        packet_id = str(packet.get("id") if isinstance(packet, dict) else "")
        events.append(f"{packet_id}:start")
        if packet_id == "buffered":
            def _send_live_packet() -> None:
                live_started.set()
                receive_buffer.on_receive({"id": "live"}, iface)
                live_delivered.set()

            thread = threading.Thread(target=_send_live_packet)
            thread.start()
            assert live_started.wait(timeout=1.0)
            time.sleep(0.05)
        events.append(f"{packet_id}:done")

    receive_buffer.activate(_callback)

    assert live_delivered.wait(timeout=1.0)
    assert events == [
        "buffered:start",
        "buffered:done",
        "live:start",
        "live:done",
    ]


def test_startup_receive_buffer_is_bounded_and_keeps_latest_packets() -> None:
    receive_buffer = StartupReceiveBuffer(max_packets=2)
    iface = object()
    delivered: list[int] = []

    receive_buffer.on_receive({"id": 1}, iface)
    receive_buffer.on_receive({"id": 2}, iface)
    receive_buffer.on_receive({"id": 3}, iface)
    receive_buffer.activate(
        lambda packet, _interface: delivered.append(int(packet["id"]))
    )

    assert delivered == [2, 3]
    assert receive_buffer.dropped_packets == 1


def test_enabled_plugin_receives_packet_buffered_during_radio_open(tmp_path) -> None:
    plugin = tmp_path / "plugins" / "startup"
    plugin.mkdir(parents=True)
    (plugin / "bot.toml").write_text(
        "api_version=1\nid='startup'\nname='Startup'\nversion='1'\n"
        "entrypoint='bot.py:bot'\ncommands=['hello']\ndefault_enabled=true\n",
        encoding="utf-8",
    )
    (plugin / "bot.py").write_text(
        """
from meshdash.bots import Bot
bot = Bot(id="startup", name="Startup", version="1")
@bot.command("hello")
def hello(ctx):
    return ctx.reply("startup packet handled")
""",
        encoding="utf-8",
    )
    args = _args(tmp_path, no_history=True)
    args.bots_enable = True
    args.bots_directory = str(tmp_path / "plugins")
    args.bots_state_db = str(tmp_path / "plugin-state.sqlite3")
    args.bots_files_directory = str(tmp_path / "plugin-files")
    args.bots_handler_timeout = 2
    args.bots_event_queue_size = 8
    args.bot_enable = []
    args.bot_disable = []
    subscriptions: list[object] = []
    sends: list[dict[str, object]] = []

    class _Iface:
        nodesByNum: dict[int, object] = {}

        def close(self) -> None:
            return

    iface = _Iface()

    class _Tracker:
        def __init__(self, **_kwargs: object) -> None:
            self.listeners: list[object] = []

        def add_accepted_packet_listener(self, listener: object) -> None:
            self.listeners.append(listener)

        def remove_accepted_packet_listener(self, listener: object) -> None:
            self.listeners.remove(listener)

        def on_receive(self, packet: object, interface: object) -> None:
            for listener in tuple(self.listeners):
                listener(packet, interface)  # type: ignore[operator]

    def _subscribe(callback: object, topic: str) -> None:
        if topic == "meshtastic.receive":
            subscriptions.append(callback)

    def _open(_args: object) -> object:
        for callback in tuple(subscriptions):
            callback(  # type: ignore[operator]
                {
                    "from": 1,
                    "to": 2,
                    "id": 77,
                    "decoded": {
                        "portnum": "TEXT_MESSAGE_APP",
                        "text": "!hello",
                    },
                },
                iface,
            )
        return iface

    def _plugin_loaders(**_kwargs: object) -> DashboardRuntimeLoaders:
        return DashboardRuntimeLoaders(
            state_fn=lambda: {},
            node_history_fn=lambda *_args, **_kwargs: {},
            summary_metrics_fn=lambda *_args, **_kwargs: {},
            send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)) or {"ok": True},
        )

    context = build_dashboard_runtime_context(
        args,
        mesh_target_label_fn=lambda _args: "test",
        open_mesh_interface_fn=_open,
        history_store_cls=lambda **_kwargs: object(),
        dashboard_tracker_cls=_Tracker,
        subscribe_fn=_subscribe,
        seed_tracker_fn=lambda _tracker, _iface: None,
        revision_info_fn=_RevisionInfo,
        send_chat_message_fn=lambda **_kwargs: {},
        send_reaction_packet_fn=lambda **_kwargs: None,
        get_local_node_id_fn=lambda _iface: "!00000002",
        normalize_single_emoji_fn=lambda _value: (None, None),
        to_int_fn=lambda _value: None,
        utc_now_fn=lambda: "2026-06-07T00:00:00Z",
        build_state_fn=lambda **_kwargs: {},
        build_state_snapshot_loader_fn=lambda *_args, **_kwargs: lambda: {},
        build_node_history_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        build_summary_metrics_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        build_send_chat_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        default_chat_max_bytes=200,
        build_dashboard_runtime_loaders_fn=_plugin_loaders,
    )
    deadline = time.monotonic() + 4
    while not sends and time.monotonic() < deadline:
        time.sleep(0.02)
    try:
        assert sends and sends[0]["text"] == "startup packet handled"
    finally:
        context.tracker._plugin_subsystem.close()
        context.tracker._startup_receive_buffer.close()
