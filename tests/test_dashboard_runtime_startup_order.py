from types import SimpleNamespace

from meshdash.dashboard_runtime_context import build_dashboard_runtime_context
from meshdash.dashboard_runtime_loaders import DashboardRuntimeLoaders


class _RevisionInfo:
    version = "0.1.0"
    commit = "test"
    label = "Rev: test"
    title = "Dashboard revision: test"


class _Tracker:
    def __init__(self, packet_limit: int, history_store: object) -> None:
        self.packet_limit = packet_limit
        self.history_store = history_store

    def on_receive(self, *_args: object, **_kwargs: object) -> None:
        return None


def _args(tmp_path):
    return SimpleNamespace(
        history_db=str(tmp_path / "history.sqlite3"),
        no_history=True,
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
        bbs_enable=False,
        file_transfer_enable=False,
        file_transfer_auto_accept=False,
    )


def _loaders(**_kwargs: object) -> DashboardRuntimeLoaders:
    return DashboardRuntimeLoaders(
        state_fn=lambda: {},
        node_history_fn=lambda *_args, **_kwargs: {},
        online_activity_fn=lambda *_args, **_kwargs: {},
        summary_metrics_fn=lambda *_args, **_kwargs: {},
        send_chat_fn=lambda **_kwargs: {"ok": True},
    )


def test_subscribes_to_meshtastic_receive_before_opening_interface(tmp_path) -> None:
    # meshtastic's SerialInterface/TCPInterface replays any packets the radio
    # buffered while no client was attached as soon as it's constructed, via
    # pypubsub's "meshtastic.receive" topic. pypubsub does not replay for late
    # subscribers, so subscribing after opening the interface silently drops
    # that backlog -- e.g. messages received overnight while the dashboard
    # wasn't running (issue #37).
    events: list[str] = []
    iface = object()

    def _open_mesh_interface(_args: object) -> object:
        events.append("open_interface")
        return iface

    def _subscribe(_callback: object, topic: str) -> None:
        if topic == "meshtastic.receive":
            events.append("subscribe_receive")

    build_dashboard_runtime_context(
        _args(tmp_path),
        mesh_target_label_fn=lambda _args: "/dev/ttyUSB0 (serial)",
        open_mesh_interface_fn=_open_mesh_interface,
        history_store_cls=lambda **_kwargs: object(),
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
        build_online_activity_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        build_summary_metrics_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        build_send_chat_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        default_chat_max_bytes=200,
        build_dashboard_runtime_loaders_fn=_loaders,
    )

    assert events == ["subscribe_receive", "open_interface"]
