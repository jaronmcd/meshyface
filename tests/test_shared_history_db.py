from types import SimpleNamespace

from meshdash.dashboard_runtime_context import build_dashboard_runtime_context
from meshdash.dashboard_runtime_loaders import DashboardRuntimeLoaders


class _RevisionInfo:
    version = "0.1.0"
    commit = "test"
    label = "Rev: test"
    title = "Dashboard revision: test"

    def as_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "commit": self.commit,
            "label": self.label,
            "title": self.title,
        }


class _Tracker:
    def __init__(self, packet_limit: int, history_store: object) -> None:
        self.packet_limit = packet_limit
        self.history_store = history_store

    def on_receive(self, *_args: object, **_kwargs: object) -> None:
        return None


def _args(history_db: str) -> SimpleNamespace:
    return SimpleNamespace(
        history_db=history_db,
        no_history=False,
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
    )


def _loaders(**_kwargs: object) -> DashboardRuntimeLoaders:
    def _state() -> dict[str, object]:
        return {}

    return DashboardRuntimeLoaders(
        state_fn=_state,
        node_history_fn=lambda *_args, **_kwargs: {},
        online_activity_fn=lambda *_args, **_kwargs: {},
        summary_metrics_fn=lambda *_args, **_kwargs: {},
        send_chat_fn=lambda *_args, **_kwargs: {},
    )


def test_runtime_uses_same_history_db_for_different_local_radios(tmp_path) -> None:
    history_db = str(tmp_path / "mesh_dashboard_history.sqlite3")
    stores: list[object] = []

    class _Store:
        def __init__(
            self,
            db_path: str,
            max_rows: int,
            retention_days: int,
            event_max_rows: int,
            event_retention_days: int,
            rollup_retention_days: int,
        ) -> None:
            del max_rows, retention_days, event_max_rows, event_retention_days
            del rollup_retention_days
            self.db_path = db_path
            self.local_node_id = ""
            stores.append(self)

    def _build(local_node_id: str):
        return build_dashboard_runtime_context(
            _args(history_db),
            mesh_target_label_fn=lambda _args: "/dev/ttyUSB0 (serial)",
            open_mesh_interface_fn=lambda _args: object(),
            history_store_cls=_Store,
            dashboard_tracker_cls=_Tracker,
            subscribe_fn=lambda _callback, _topic: None,
            seed_tracker_fn=lambda _tracker, _iface: None,
            revision_info_fn=_RevisionInfo,
            send_chat_message_fn=lambda **_kwargs: {},
            send_reaction_packet_fn=lambda **_kwargs: None,
            get_local_node_id_fn=lambda _iface: local_node_id,
            normalize_single_emoji_fn=lambda _value: (None, None),
            to_int_fn=lambda _value: None,
            utc_now_fn=lambda: "2026-05-02T00:00:00Z",
            build_state_fn=lambda **_kwargs: {},
            build_state_snapshot_loader_fn=lambda *_args, **_kwargs: lambda: {},
            build_node_history_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
            build_online_activity_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
            build_summary_metrics_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
            build_send_chat_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
            default_chat_max_bytes=200,
            resolve_history_db_path_fn=lambda path: path,
            build_dashboard_runtime_loaders_fn=_loaders,
        )

    first = _build("!12345678")
    second = _build("!87654321")

    assert first.history_db_path == history_db
    assert second.history_db_path == history_db
    assert getattr(stores[0], "db_path") == history_db
    assert getattr(stores[1], "db_path") == history_db
    assert getattr(stores[0], "local_node_id") == "!12345678"
    assert getattr(stores[1], "local_node_id") == "!87654321"


def test_runtime_does_not_auto_enable_bots_even_when_games_feature_is_enabled(tmp_path) -> None:
    history_db = str(tmp_path / "mesh_dashboard_history.sqlite3")
    enable_calls: list[object] = []

    class _TrackerWithBots(_Tracker):
        def enable_zork_bot(self, *, send_lock: object | None = None) -> bool:
            enable_calls.append(send_lock)
            return True

    args = _args(history_db)
    args.games_enable = True

    build_dashboard_runtime_context(
        args,
        mesh_target_label_fn=lambda _args: "/dev/ttyUSB0 (serial)",
        open_mesh_interface_fn=lambda _args: object(),
        history_store_cls=lambda **_kwargs: object(),
        dashboard_tracker_cls=_TrackerWithBots,
        subscribe_fn=lambda _callback, _topic: None,
        seed_tracker_fn=lambda _tracker, _iface: None,
        revision_info_fn=_RevisionInfo,
        send_chat_message_fn=lambda **_kwargs: {},
        send_reaction_packet_fn=lambda **_kwargs: None,
        get_local_node_id_fn=lambda _iface: "!12345678",
        normalize_single_emoji_fn=lambda _value: (None, None),
        to_int_fn=lambda _value: None,
        utc_now_fn=lambda: "2026-05-02T00:00:00Z",
        build_state_fn=lambda **_kwargs: {},
        build_state_snapshot_loader_fn=lambda *_args, **_kwargs: lambda: {},
        build_node_history_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        build_online_activity_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        build_summary_metrics_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        build_send_chat_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        default_chat_max_bytes=200,
        resolve_history_db_path_fn=lambda path: path,
        build_dashboard_runtime_loaders_fn=_loaders,
    )

    assert enable_calls == []


def test_runtime_restores_and_persists_bot_runtime_settings(tmp_path) -> None:
    history_db = str(tmp_path / "mesh_dashboard_history.sqlite3")
    stores: list[object] = []
    persisted_writes: list[dict[str, object]] = []

    class _Store:
        def __init__(
            self,
            db_path: str,
            max_rows: int,
            retention_days: int,
            event_max_rows: int,
            event_retention_days: int,
            rollup_retention_days: int,
        ) -> None:
            del max_rows, retention_days, event_max_rows, event_retention_days
            del rollup_retention_days
            self.db_path = db_path
            self.local_node_id = ""
            stores.append(self)

        def get_bot_runtime_settings(self) -> dict[str, object]:
            return {
                "ok": True,
                "settings": {
                    "zork_enabled": True,
                    "ping_enabled": False,
                    "ping_message_only": True,
                },
                "updated_unix": 111,
            }

        def set_bot_runtime_settings(self, settings: object) -> dict[str, object]:
            payload = dict(settings) if isinstance(settings, dict) else {}
            persisted_writes.append(payload)
            return {
                "ok": True,
                "settings": payload,
                "updated_unix": 222,
            }

    class _TrackerWithBots(_Tracker):
        def __init__(self, packet_limit: int, history_store: object) -> None:
            super().__init__(packet_limit, history_store)
            self.zork_enabled = False
            self.ping_enabled = False
            self.ping_message_only = False

        def get_zork_bot_runtime(self) -> dict[str, object]:
            return {
                "available": True,
                "zork": {
                    "enabled": bool(self.zork_enabled),
                    "active_session_count": 0,
                    "sessions": [],
                    "public_start_enabled": bool(self.zork_enabled),
                    "direct_message_enabled": bool(self.zork_enabled),
                },
                "ping": {
                    "enabled": bool(self.ping_enabled),
                    "active_session_count": 0,
                    "sessions": [],
                    "public_start_enabled": not bool(self.ping_message_only),
                    "direct_message_enabled": bool(self.ping_enabled),
                    "message_only": bool(self.ping_message_only),
                },
            }

        def set_zork_bot_enabled(
            self,
            enabled: object,
            *,
            send_lock: object | None = None,
        ) -> dict[str, object]:
            del send_lock
            self.zork_enabled = bool(enabled)
            runtime = self.get_zork_bot_runtime()
            runtime["ok"] = True
            return runtime

        def set_ping_bot_enabled(
            self,
            enabled: object,
            *,
            send_lock: object | None = None,
        ) -> dict[str, object]:
            del send_lock
            self.ping_enabled = bool(enabled)
            runtime = self.get_zork_bot_runtime()
            runtime["ok"] = True
            return runtime

        def set_ping_bot_message_only(self, message_only: object) -> dict[str, object]:
            self.ping_message_only = bool(message_only)
            runtime = self.get_zork_bot_runtime()
            runtime["ok"] = True
            return runtime

    args = _args(history_db)
    args.games_enable = True

    context = build_dashboard_runtime_context(
        args,
        mesh_target_label_fn=lambda _args: "/dev/ttyUSB0 (serial)",
        open_mesh_interface_fn=lambda _args: object(),
        history_store_cls=_Store,
        dashboard_tracker_cls=_TrackerWithBots,
        subscribe_fn=lambda _callback, _topic: None,
        seed_tracker_fn=lambda _tracker, _iface: None,
        revision_info_fn=_RevisionInfo,
        send_chat_message_fn=lambda **_kwargs: {},
        send_reaction_packet_fn=lambda **_kwargs: None,
        get_local_node_id_fn=lambda _iface: "!12345678",
        normalize_single_emoji_fn=lambda _value: (None, None),
        to_int_fn=lambda _value: None,
        utc_now_fn=lambda: "2026-05-02T00:00:00Z",
        build_state_fn=lambda **_kwargs: {},
        build_state_snapshot_loader_fn=lambda *_args, **_kwargs: lambda: {},
        build_node_history_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        build_online_activity_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        build_summary_metrics_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        build_send_chat_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        default_chat_max_bytes=200,
        resolve_history_db_path_fn=lambda path: path,
        build_dashboard_runtime_loaders_fn=_loaders,
    )

    tracker = context.tracker
    assert isinstance(tracker, _TrackerWithBots)
    assert tracker.zork_enabled is True
    assert tracker.ping_enabled is False
    assert tracker.ping_message_only is True
    assert len(stores) == 1
    assert persisted_writes == []

    set_ping_enabled_fn = getattr(context.state_fn, "set_ping_bot_enabled_fn", None)
    assert callable(set_ping_enabled_fn)
    response = set_ping_enabled_fn(True)
    assert isinstance(response, dict)
    assert response.get("ok") is True

    assert persisted_writes[-1] == {
        "zork_enabled": True,
        "ping_enabled": True,
        "ping_message_only": True,
    }
