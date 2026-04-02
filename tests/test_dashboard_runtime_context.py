import argparse

import meshdash.dashboard_runtime_context as runtime_context_mod
from meshdash.dashboard_loaders import DashboardRuntimeLoaders
from meshdash.dashboard_runtime_context import (
    DashboardRuntimeContext,
    build_dashboard_runtime_context,
)
from meshdash.revision import RevisionInfo


def test_build_dashboard_runtime_context_wires_runtime_dependencies():
    args = argparse.Namespace(
        history_db="state/history.sqlite3",
        no_history=False,
        seed_from_node_db=True,
        history_max_rows=5000,
        history_retention_days=7,
        history_event_max_rows=200000,
        history_event_retention_days=30,
        history_rollup_retention_days=365,
        packet_limit=250,
        show_secrets=False,
        node_history_hours=72,
        node_history_max_points=1440,
    )
    calls = {}

    iface = object()
    history_store = object()
    history_store_cls = object()
    send_state = lambda: {"ok": True}
    send_node_history = lambda *_a, **_k: {"ok": True}
    send_online = lambda *_a, **_k: {"ok": True}
    send_summary = lambda *_a, **_k: {"ok": True}
    send_chat = lambda *_a, **_k: {"ok": True}
    local_node_id_fn = lambda _iface: "!ABCDEF12"
    revision_info = RevisionInfo(version="0.1.0", commit="abc", label="Rev", title="Rev Title")

    def _mesh_target_label(_args):
        calls["mesh_target_args"] = _args
        return "192.168.1.10:4403 (tcp)"

    def _open_mesh_interface(_args):
        calls["open_mesh_interface_args"] = _args
        return iface

    def _open_optional_history_store(_args, **kwargs):
        calls["open_optional_history_store"] = (_args, kwargs)
        return history_store

    class _Tracker:
        def __init__(self, packet_limit, history_store):
            self.packet_limit = packet_limit
            self.history_store = history_store
            self.bootstrap_iface = None

        def on_receive(self, _packet, _interface):
            return None

        def on_connection_established(self, interface, **_kwargs):
            return interface

        def on_connection_lost(self, interface, **_kwargs):
            return interface

        def bootstrap_connection_state(self, iface_obj):
            self.bootstrap_iface = iface_obj

    def _subscribe(callback, topic):
        calls.setdefault("subscribe", []).append((callback, topic))

    def _seed_tracker_if_empty(tracker, iface_obj, **kwargs):
        calls["seed_tracker_if_empty"] = (tracker, iface_obj, kwargs)

    def _build_dashboard_runtime_loaders(**kwargs):
        calls["build_dashboard_runtime_loaders"] = kwargs
        return DashboardRuntimeLoaders(
            state_fn=send_state,
            node_history_fn=send_node_history,
            online_activity_fn=send_online,
            summary_metrics_fn=send_summary,
            send_chat_fn=send_chat,
        )

    printed = []
    context = build_dashboard_runtime_context(
        args,
        mesh_target_label_fn=_mesh_target_label,
        open_mesh_interface_fn=_open_mesh_interface,
        history_store_cls=history_store_cls,
        dashboard_tracker_cls=_Tracker,
        subscribe_fn=_subscribe,
        seed_tracker_fn="seed-fn",
        revision_info_fn=lambda: revision_info,
        send_chat_message_fn="send-chat-message-fn",
        send_reaction_packet_fn="send-reaction-packet-fn",
        get_local_node_id_fn=local_node_id_fn,
        normalize_single_emoji_fn="normalize-single-emoji-fn",
        to_int_fn="to-int-fn",
        utc_now_fn="utc-now-fn",
        build_state_fn="build-state-fn",
        build_state_snapshot_loader_fn="build-state-snapshot-loader-fn",
        build_node_history_loader_fn="build-node-history-loader-fn",
        build_online_activity_loader_fn="build-online-activity-loader-fn",
        build_summary_metrics_loader_fn="build-summary-metrics-loader-fn",
        build_send_chat_loader_fn="build-send-chat-loader-fn",
        default_chat_max_bytes=220,
        print_fn=printed.append,
        lock_factory=lambda: "send-lock",
        now_unix_fn=lambda: 123.5,
        resolve_history_db_path_fn=lambda path: f"/abs/{path}",
        open_optional_history_store_fn=_open_optional_history_store,
        seed_tracker_if_empty_fn=_seed_tracker_if_empty,
        build_dashboard_runtime_loaders_fn=_build_dashboard_runtime_loaders,
    )

    assert printed == ["Connecting to 192.168.1.10:4403 (tcp) ..."]
    assert isinstance(context, DashboardRuntimeContext)
    assert context.target == "192.168.1.10:4403 (tcp)"
    assert context.iface is iface
    assert context.history_db_path == "/abs/state/history.radio-abcdef12.sqlite3"
    assert context.history_store is history_store
    assert isinstance(context.tracker, _Tracker)
    assert context.tracker.packet_limit == 250
    assert context.tracker.history_store is history_store
    assert context.send_lock == "send-lock"
    assert context.started_at == 123.5
    assert context.revision_info is revision_info
    assert context.state_fn is send_state
    assert context.node_history_fn is send_node_history
    assert context.online_activity_fn is send_online
    assert context.summary_metrics_fn is send_summary
    assert context.send_chat_fn is send_chat
    assert context.history_enabled is True

    assert calls["mesh_target_args"] is args
    assert calls["open_mesh_interface_args"] is args

    open_args, open_kwargs = calls["open_optional_history_store"]
    assert open_args is args
    assert open_kwargs == {
        "history_store_cls": history_store_cls,
        "history_db_path": "/abs/state/history.radio-abcdef12.sqlite3",
    }

    subscribe_topics = [topic for _callback, topic in calls["subscribe"]]
    assert subscribe_topics == [
        "meshtastic.receive",
        "meshtastic.connection.established",
        "meshtastic.connection.lost",
        "meshtastic.receive",
    ]
    subscribe_methods = [callback.__func__.__name__ for callback, _topic in calls["subscribe"]]
    assert subscribe_methods == [
        "on_receive",
        "on_connection_established",
        "on_connection_lost",
        "on_receive",
    ]
    for callback, _topic in calls["subscribe"][:3]:
        assert callback.__self__ is context.tracker
    assert calls["subscribe"][3][0].__self__ is not context.tracker
    assert context.tracker.bootstrap_iface is iface

    seeded_tracker, seeded_iface, seed_kwargs = calls["seed_tracker_if_empty"]
    assert seeded_tracker is context.tracker
    assert seeded_iface is iface
    assert seed_kwargs == {"seed_tracker_fn": "seed-fn"}

    assert calls["build_dashboard_runtime_loaders"] == {
        "iface": iface,
        "tracker": context.tracker,
        "send_lock": "send-lock",
        "started_at": 123.5,
        "target": "192.168.1.10:4403 (tcp)",
        "show_secrets": False,
        "history_db_path": "/abs/state/history.radio-abcdef12.sqlite3",
        "revision_info": revision_info,
        "history_store": history_store,
        "default_node_history_hours": 72,
        "default_node_history_points": 1440,
        "send_chat_message_fn": "send-chat-message-fn",
        "send_reaction_packet_fn": "send-reaction-packet-fn",
        "get_local_node_id_fn": local_node_id_fn,
        "default_chat_max_bytes": 220,
        "normalize_single_emoji_fn": "normalize-single-emoji-fn",
        "to_int_fn": "to-int-fn",
        "utc_now_fn": "utc-now-fn",
        "build_state_fn": "build-state-fn",
        "build_state_snapshot_loader_fn": "build-state-snapshot-loader-fn",
        "build_node_history_loader_fn": "build-node-history-loader-fn",
        "build_online_activity_loader_fn": "build-online-activity-loader-fn",
        "build_summary_metrics_loader_fn": "build-summary-metrics-loader-fn",
        "build_send_chat_loader_fn": "build-send-chat-loader-fn",
    }


def test_build_dashboard_runtime_context_uses_typed_loader_dependency_path_by_default():
    args = argparse.Namespace(
        history_db="state/history.sqlite3",
        no_history=False,
        seed_from_node_db=False,
        history_max_rows=5000,
        history_retention_days=7,
        history_event_max_rows=200000,
        history_event_retention_days=30,
        history_rollup_retention_days=365,
        packet_limit=250,
        show_secrets=False,
        node_history_hours=72,
        node_history_max_points=1440,
    )
    calls = {}

    iface = object()
    history_store = object()
    history_store_cls = object()
    send_state = lambda: {"ok": True}
    send_node_history = lambda *_a, **_k: {"ok": True}
    send_online = lambda *_a, **_k: {"ok": True}
    send_summary = lambda *_a, **_k: {"ok": True}
    send_chat = lambda *_a, **_k: {"ok": True}
    local_node_id_fn = lambda _iface: "!ABCDEF12"
    revision_info = RevisionInfo(version="0.1.0", commit="abc", label="Rev", title="Rev Title")

    def _mesh_target_label(_args):
        return "192.168.1.10:4403 (tcp)"

    def _open_mesh_interface(_args):
        return iface

    def _open_optional_history_store(_args, **_kwargs):
        return history_store

    class _Tracker:
        def __init__(self, packet_limit, history_store):
            self.packet_limit = packet_limit
            self.history_store = history_store

        def on_receive(self, _packet, _interface):
            return None

    def _build_runtime_loader_dependencies(**kwargs):
        calls["build_runtime_loader_dependencies"] = kwargs
        return {"deps": True}

    def _build_runtime_loaders_with_dependencies(*, dependencies):
        calls["build_runtime_loaders_with_dependencies"] = dependencies
        return DashboardRuntimeLoaders(
            state_fn=send_state,
            node_history_fn=send_node_history,
            online_activity_fn=send_online,
            summary_metrics_fn=send_summary,
            send_chat_fn=send_chat,
        )

    context = build_dashboard_runtime_context(
        args,
        mesh_target_label_fn=_mesh_target_label,
        open_mesh_interface_fn=_open_mesh_interface,
        history_store_cls=history_store_cls,
        dashboard_tracker_cls=_Tracker,
        subscribe_fn=lambda *_a: None,
        seed_tracker_fn="seed-fn",
        revision_info_fn=lambda: revision_info,
        send_chat_message_fn="send-chat-message-fn",
        send_reaction_packet_fn="send-reaction-packet-fn",
        get_local_node_id_fn=local_node_id_fn,
        normalize_single_emoji_fn="normalize-single-emoji-fn",
        to_int_fn="to-int-fn",
        utc_now_fn="utc-now-fn",
        build_state_fn="build-state-fn",
        build_state_snapshot_loader_fn="build-state-snapshot-loader-fn",
        build_node_history_loader_fn="build-node-history-loader-fn",
        build_online_activity_loader_fn="build-online-activity-loader-fn",
        build_summary_metrics_loader_fn="build-summary-metrics-loader-fn",
        build_send_chat_loader_fn="build-send-chat-loader-fn",
        default_chat_max_bytes=220,
        lock_factory=lambda: "send-lock",
        now_unix_fn=lambda: 123.5,
        resolve_history_db_path_fn=lambda path: f"/abs/{path}",
        open_optional_history_store_fn=_open_optional_history_store,
        seed_tracker_if_empty_fn=lambda *_a, **_k: None,
        build_dashboard_runtime_loader_dependencies_from_legacy_args_fn=_build_runtime_loader_dependencies,
        build_dashboard_runtime_loaders_with_dependencies_fn=_build_runtime_loaders_with_dependencies,
    )

    assert isinstance(context, DashboardRuntimeContext)
    assert context.state_fn is send_state
    assert context.node_history_fn is send_node_history
    assert context.online_activity_fn is send_online
    assert context.summary_metrics_fn is send_summary
    assert context.send_chat_fn is send_chat
    assert calls["build_runtime_loader_dependencies"]["iface"] is iface
    assert calls["build_runtime_loader_dependencies"]["history_store"] is history_store
    assert calls["build_runtime_loader_dependencies"]["revision_info"] is revision_info
    assert calls["build_runtime_loaders_with_dependencies"] == {"deps": True}


def test_build_dashboard_runtime_context_skips_node_db_seed_by_default():
    args = argparse.Namespace(
        history_db="state/history.sqlite3",
        no_history=False,
        history_max_rows=5000,
        history_retention_days=7,
        history_event_max_rows=200000,
        history_event_retention_days=30,
        history_rollup_retention_days=365,
        packet_limit=250,
        show_secrets=False,
        node_history_hours=72,
        node_history_max_points=1440,
    )

    calls = {"seed": 0}
    iface = object()
    history_store = object()
    local_node_id_fn = lambda _iface: "!ABCDEF12"

    class _Tracker:
        def __init__(self, packet_limit, history_store):
            self.packet_limit = packet_limit
            self.history_store = history_store

        def on_receive(self, _packet, _interface):
            return None

    def _seed_tracker_if_empty(*_args, **_kwargs):
        calls["seed"] += 1

    build_dashboard_runtime_context(
        args,
        mesh_target_label_fn=lambda _args: "192.168.1.10:4403 (tcp)",
        open_mesh_interface_fn=lambda _args: iface,
        history_store_cls=object(),
        dashboard_tracker_cls=_Tracker,
        subscribe_fn=lambda *_a: None,
        seed_tracker_fn="seed-fn",
        revision_info_fn=lambda: RevisionInfo(version="0.1.0", commit="abc", label="Rev", title="Rev Title"),
        send_chat_message_fn="send-chat-message-fn",
        send_reaction_packet_fn="send-reaction-packet-fn",
        get_local_node_id_fn=local_node_id_fn,
        normalize_single_emoji_fn="normalize-single-emoji-fn",
        to_int_fn="to-int-fn",
        utc_now_fn="utc-now-fn",
        build_state_fn="build-state-fn",
        build_state_snapshot_loader_fn="build-state-snapshot-loader-fn",
        build_node_history_loader_fn="build-node-history-loader-fn",
        build_online_activity_loader_fn="build-online-activity-loader-fn",
        build_summary_metrics_loader_fn="build-summary-metrics-loader-fn",
        build_send_chat_loader_fn="build-send-chat-loader-fn",
        default_chat_max_bytes=220,
        lock_factory=lambda: "send-lock",
        now_unix_fn=lambda: 123.5,
        resolve_history_db_path_fn=lambda path: f"/abs/{path}",
        open_optional_history_store_fn=lambda *_a, **_k: history_store,
        seed_tracker_if_empty_fn=_seed_tracker_if_empty,
        build_dashboard_runtime_loaders_fn=lambda **_kwargs: DashboardRuntimeLoaders(
            state_fn=lambda: {"ok": True},
            node_history_fn=lambda *_a, **_k: {"ok": True},
            online_activity_fn=lambda *_a, **_k: {"ok": True},
            summary_metrics_fn=lambda *_a, **_k: {"ok": True},
            send_chat_fn=lambda *_a, **_k: {"ok": True},
        ),
    )

    assert calls["seed"] == 0


def test_build_dashboard_runtime_context_passes_chat_limit_to_bot_builder(monkeypatch):
    args = argparse.Namespace(
        history_db="state/history.sqlite3",
        no_history=False,
        seed_from_node_db=False,
        history_max_rows=5000,
        history_retention_days=7,
        history_event_max_rows=200000,
        history_event_retention_days=30,
        history_rollup_retention_days=365,
        packet_limit=250,
        show_secrets=False,
        node_history_hours=72,
        node_history_max_points=1440,
    )
    calls = {}
    iface = object()
    history_store = object()

    class _Tracker:
        def __init__(self, packet_limit, history_store):
            self.packet_limit = packet_limit
            self.history_store = history_store

        def on_receive(self, _packet, _interface):
            return None

    class _FakeBot:
        def on_receive(self, _packet, _interface, **_kwargs):
            return None

        def bot_settings(self):
            return {"commands": []}

        def recent_requests(self):
            return []

        def configure(self, **_kwargs):
            return {"ok": True}

    fake_bot = _FakeBot()

    def _build_bot(**kwargs):
        calls["build_bot"] = kwargs
        return fake_bot

    monkeypatch.setattr(runtime_context_mod, "_build_mesh_response_bot_from_env", _build_bot)

    send_state = lambda: {"ok": True}
    send_chat = lambda *_a, **_k: {"ok": True}
    context = build_dashboard_runtime_context(
        args,
        mesh_target_label_fn=lambda _args: "192.168.1.10:4403 (tcp)",
        open_mesh_interface_fn=lambda _args: iface,
        history_store_cls=object(),
        dashboard_tracker_cls=_Tracker,
        subscribe_fn=lambda *_a: None,
        seed_tracker_fn="seed-fn",
        revision_info_fn=lambda: RevisionInfo(version="0.1.0", commit="abc", label="Rev", title="Rev Title"),
        send_chat_message_fn="send-chat-message-fn",
        send_reaction_packet_fn="send-reaction-packet-fn",
        get_local_node_id_fn=lambda _iface: "!ABCDEF12",
        normalize_single_emoji_fn="normalize-single-emoji-fn",
        to_int_fn="to-int-fn",
        utc_now_fn="utc-now-fn",
        build_state_fn="build-state-fn",
        build_state_snapshot_loader_fn="build-state-snapshot-loader-fn",
        build_node_history_loader_fn="build-node-history-loader-fn",
        build_online_activity_loader_fn="build-online-activity-loader-fn",
        build_summary_metrics_loader_fn="build-summary-metrics-loader-fn",
        build_send_chat_loader_fn="build-send-chat-loader-fn",
        default_chat_max_bytes=220,
        lock_factory=lambda: "send-lock",
        now_unix_fn=lambda: 123.5,
        resolve_history_db_path_fn=lambda path: f"/abs/{path}",
        open_optional_history_store_fn=lambda *_a, **_k: history_store,
        seed_tracker_if_empty_fn=lambda *_a, **_k: None,
        build_dashboard_runtime_loaders_fn=lambda **_kwargs: DashboardRuntimeLoaders(
            state_fn=send_state,
            node_history_fn=lambda *_a, **_k: {"ok": True},
            online_activity_fn=lambda *_a, **_k: {"ok": True},
            summary_metrics_fn=lambda *_a, **_k: {"ok": True},
            send_chat_fn=send_chat,
        ),
    )

    assert isinstance(context, DashboardRuntimeContext)
    assert calls["build_bot"]["send_chat_fn"] is send_chat
    assert callable(calls["build_bot"]["get_local_node_id_fn"])
    assert calls["build_bot"]["chat_max_bytes"] == 220
    assert callable(calls["build_bot"]["record_fault_fn"])
    assert getattr(context.state_fn, "bot_responder") is fake_bot
    assert callable(getattr(context.state_fn, "fault_history_fn"))


def test_build_dashboard_runtime_context_attaches_standalone_zork_service(monkeypatch):
    args = argparse.Namespace(
        history_db="state/history.sqlite3",
        no_history=False,
        seed_from_node_db=False,
        history_max_rows=5000,
        history_retention_days=7,
        history_event_max_rows=200000,
        history_event_retention_days=30,
        history_rollup_retention_days=365,
        packet_limit=250,
        show_secrets=False,
        node_history_hours=72,
        node_history_max_points=1440,
    )
    iface = object()
    history_store = object()

    class _Tracker:
        def __init__(self, packet_limit, history_store):
            self.packet_limit = packet_limit
            self.history_store = history_store

        def on_receive(self, _packet, _interface):
            return None

    class _FakeStandaloneZork:
        def play(self, **_kwargs):
            return {"ok": True}

    fake_service = _FakeStandaloneZork()
    monkeypatch.setattr(runtime_context_mod, "_build_standalone_zork_service", lambda: fake_service)

    send_state = lambda: {"ok": True}
    context = build_dashboard_runtime_context(
        args,
        mesh_target_label_fn=lambda _args: "192.168.1.10:4403 (tcp)",
        open_mesh_interface_fn=lambda _args: iface,
        history_store_cls=object(),
        dashboard_tracker_cls=_Tracker,
        subscribe_fn=lambda *_a: None,
        seed_tracker_fn="seed-fn",
        revision_info_fn=lambda: RevisionInfo(version="0.1.0", commit="abc", label="Rev", title="Rev Title"),
        send_chat_message_fn="send-chat-message-fn",
        send_reaction_packet_fn="send-reaction-packet-fn",
        get_local_node_id_fn=lambda _iface: "!ABCDEF12",
        normalize_single_emoji_fn="normalize-single-emoji-fn",
        to_int_fn="to-int-fn",
        utc_now_fn="utc-now-fn",
        build_state_fn="build-state-fn",
        build_state_snapshot_loader_fn="build-state-snapshot-loader-fn",
        build_node_history_loader_fn="build-node-history-loader-fn",
        build_online_activity_loader_fn="build-online-activity-loader-fn",
        build_summary_metrics_loader_fn="build-summary-metrics-loader-fn",
        build_send_chat_loader_fn="build-send-chat-loader-fn",
        default_chat_max_bytes=220,
        lock_factory=lambda: "send-lock",
        now_unix_fn=lambda: 123.5,
        resolve_history_db_path_fn=lambda path: f"/abs/{path}",
        open_optional_history_store_fn=lambda *_a, **_k: history_store,
        seed_tracker_if_empty_fn=lambda *_a, **_k: None,
        build_dashboard_runtime_loaders_fn=lambda **_kwargs: DashboardRuntimeLoaders(
            state_fn=send_state,
            node_history_fn=lambda *_a, **_k: {"ok": True},
            online_activity_fn=lambda *_a, **_k: {"ok": True},
            summary_metrics_fn=lambda *_a, **_k: {"ok": True},
            send_chat_fn=lambda *_a, **_k: {"ok": True},
        ),
    )

    assert isinstance(context, DashboardRuntimeContext)
    play_fn = getattr(context.state_fn, "play_standalone_zork_fn")
    assert callable(play_fn)
    assert play_fn(text="zork") == {"ok": True}


def test_build_dashboard_runtime_context_attaches_history_search_hook():
    args = argparse.Namespace(
        history_db="state/history.sqlite3",
        no_history=False,
        seed_from_node_db=False,
        history_max_rows=5000,
        history_retention_days=7,
        history_event_max_rows=200000,
        history_event_retention_days=30,
        history_rollup_retention_days=365,
        packet_limit=250,
        show_secrets=False,
        node_history_hours=72,
        node_history_max_points=1440,
    )
    iface = object()
    calls = {}

    class _HistoryStore:
        def search_packets(self, query_text, **kwargs):
            calls["query"] = query_text
            calls["kwargs"] = kwargs
            return {"ok": True, "query": query_text}

    history_store = _HistoryStore()

    class _Tracker:
        def __init__(self, packet_limit, history_store):
            self.packet_limit = packet_limit
            self.history_store = history_store

        def on_receive(self, _packet, _interface):
            return None

    send_state = lambda: {"ok": True}
    context = build_dashboard_runtime_context(
        args,
        mesh_target_label_fn=lambda _args: "192.168.1.10:4403 (tcp)",
        open_mesh_interface_fn=lambda _args: iface,
        history_store_cls=object(),
        dashboard_tracker_cls=_Tracker,
        subscribe_fn=lambda *_a: None,
        seed_tracker_fn="seed-fn",
        revision_info_fn=lambda: RevisionInfo(version="0.1.0", commit="abc", label="Rev", title="Rev Title"),
        send_chat_message_fn="send-chat-message-fn",
        send_reaction_packet_fn="send-reaction-packet-fn",
        get_local_node_id_fn=lambda _iface: "!ABCDEF12",
        normalize_single_emoji_fn="normalize-single-emoji-fn",
        to_int_fn="to-int-fn",
        utc_now_fn="utc-now-fn",
        build_state_fn="build-state-fn",
        build_state_snapshot_loader_fn="build-state-snapshot-loader-fn",
        build_node_history_loader_fn="build-node-history-loader-fn",
        build_online_activity_loader_fn="build-online-activity-loader-fn",
        build_summary_metrics_loader_fn="build-summary-metrics-loader-fn",
        build_send_chat_loader_fn="build-send-chat-loader-fn",
        default_chat_max_bytes=220,
        lock_factory=lambda: "send-lock",
        now_unix_fn=lambda: 123.5,
        resolve_history_db_path_fn=lambda path: f"/abs/{path}",
        open_optional_history_store_fn=lambda *_a, **_k: history_store,
        seed_tracker_if_empty_fn=lambda *_a, **_k: None,
        build_dashboard_runtime_loaders_fn=lambda **_kwargs: DashboardRuntimeLoaders(
            state_fn=send_state,
            node_history_fn=lambda *_a, **_k: {"ok": True},
            online_activity_fn=lambda *_a, **_k: {"ok": True},
            summary_metrics_fn=lambda *_a, **_k: {"ok": True},
            send_chat_fn=lambda *_a, **_k: {"ok": True},
        ),
    )

    search_fn = getattr(context.state_fn, "search_history_packets_fn")
    assert callable(search_fn)
    assert search_fn("needle", limit=12, before=1, after=2) == {"ok": True, "query": "needle"}
    assert calls["query"] == "needle"
    assert calls["kwargs"] == {"limit": 12, "before": 1, "after": 2, "scope": None, "scan_limit": None}
    assert search_fn("needle-chat", source="chat") == {"ok": True, "query": "needle-chat"}
    assert calls["query"] == "needle-chat"
    assert calls["kwargs"] == {"limit": None, "before": None, "after": None, "scope": None, "scan_limit": None, "source": "chat"}
