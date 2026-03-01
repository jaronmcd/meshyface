from meshdash.dashboard_loaders import DashboardRuntimeLoaders, build_dashboard_runtime_loaders
from meshdash.dashboard_runtime_loader_contracts import DashboardRuntimeLoaderDependencies
from meshdash.dashboard_runtime_loaders import build_dashboard_runtime_loaders_with_dependencies
from meshdash.revision import RevisionInfo


def test_build_dashboard_runtime_loaders_wires_all_loader_factories():
    captured = {}

    def _state_snapshot_loader(**kwargs):
        captured["state"] = kwargs
        return lambda: {"state": True}

    def _node_history_loader(**kwargs):
        captured["node_history"] = kwargs
        return lambda *_a, **_k: {"node_history": True}

    def _online_loader(**kwargs):
        captured["online"] = kwargs
        return lambda *_a, **_k: {"online": True}

    def _send_chat_loader(**kwargs):
        captured["send"] = kwargs
        return lambda **_k: {"send": True}

    def _summary_loader(**kwargs):
        captured["summary"] = kwargs
        return lambda *_a, **_k: {"summary": True}

    result = build_dashboard_runtime_loaders(
        iface="iface",
        tracker="tracker",
        send_lock="lock",
        started_at=123.0,
        target="target",
        show_secrets=False,
        history_db_path="/tmp/db.sqlite3",
        revision_info=RevisionInfo(version="0.1.0", commit="abc", label="L", title="T"),
        history_store="history",
        default_node_history_hours=72,
        default_node_history_points=1440,
        send_chat_message_fn="send_chat_message_fn",
        send_reaction_packet_fn="send_reaction_packet_fn",
        get_local_node_id_fn="get_local_node_id_fn",
        default_chat_max_bytes=220,
        normalize_single_emoji_fn="normalize_single_emoji_fn",
        to_int_fn="to_int_fn",
        utc_now_fn="utc_now_fn",
        build_state_fn="build_state_fn",
        build_state_snapshot_loader_fn=_state_snapshot_loader,
        build_node_history_loader_fn=_node_history_loader,
        build_online_activity_loader_fn=_online_loader,
        build_summary_metrics_loader_fn=_summary_loader,
        build_send_chat_loader_fn=_send_chat_loader,
    )

    assert isinstance(result, DashboardRuntimeLoaders)
    assert callable(result.state_fn)
    assert callable(result.node_history_fn)
    assert callable(result.online_activity_fn)
    assert callable(result.summary_metrics_fn)
    assert callable(result.send_chat_fn)
    assert captured["state"]["iface"] == "iface"
    assert captured["state"]["build_state_fn"] == "build_state_fn"
    assert captured["node_history"]["default_hours"] == 72
    assert captured["node_history"]["default_points"] == 1440
    assert captured["online"]["default_hours"] == 72
    assert captured["summary"]["default_hours"] == 72
    assert captured["send"]["chat_max_bytes"] == 220
    assert captured["send"]["send_lock"] == "lock"


def test_build_dashboard_runtime_loaders_with_dependencies_wires_all_loader_factories():
    captured = {}

    def _state_snapshot_loader(**kwargs):
        captured["state"] = kwargs
        return lambda: {"state": True}

    def _node_history_loader(**kwargs):
        captured["node_history"] = kwargs
        return lambda *_a, **_k: {"node_history": True}

    def _online_loader(**kwargs):
        captured["online"] = kwargs
        return lambda *_a, **_k: {"online": True}

    def _send_chat_loader(**kwargs):
        captured["send"] = kwargs
        return lambda **_k: {"send": True}

    def _summary_loader(**kwargs):
        captured["summary"] = kwargs
        return lambda *_a, **_k: {"summary": True}

    deps = DashboardRuntimeLoaderDependencies(
        iface="iface",
        tracker="tracker",
        send_lock="lock",
        started_at=123.0,
        target="target",
        show_secrets=False,
        history_db_path="/tmp/db.sqlite3",
        revision_info=RevisionInfo(version="0.1.0", commit="abc", label="L", title="T"),
        history_store="history",
        default_node_history_hours=72,
        default_node_history_points=1440,
        send_chat_message_fn="send_chat_message_fn",
        send_reaction_packet_fn="send_reaction_packet_fn",
        get_local_node_id_fn="get_local_node_id_fn",
        default_chat_max_bytes=220,
        normalize_single_emoji_fn="normalize_single_emoji_fn",
        to_int_fn="to_int_fn",
        utc_now_fn="utc_now_fn",
        build_state_fn="build_state_fn",
        build_state_snapshot_loader_fn=_state_snapshot_loader,
        build_node_history_loader_fn=_node_history_loader,
        build_online_activity_loader_fn=_online_loader,
        build_summary_metrics_loader_fn=_summary_loader,
        build_send_chat_loader_fn=_send_chat_loader,
    )

    result = build_dashboard_runtime_loaders_with_dependencies(dependencies=deps)

    assert isinstance(result, DashboardRuntimeLoaders)
    assert callable(result.state_fn)
    assert callable(result.node_history_fn)
    assert callable(result.online_activity_fn)
    assert callable(result.summary_metrics_fn)
    assert callable(result.send_chat_fn)
    assert captured["state"]["iface"] == "iface"
    assert captured["state"]["build_state_fn"] == "build_state_fn"
    assert captured["node_history"]["default_hours"] == 72
    assert captured["node_history"]["default_points"] == 1440
    assert captured["online"]["default_hours"] == 72
    assert captured["summary"]["default_hours"] == 72
    assert captured["send"]["chat_max_bytes"] == 220
    assert captured["send"]["send_lock"] == "lock"


def test_build_dashboard_runtime_loaders_persists_summary_metrics_when_store_supports_it():
    saved = []

    class _HistoryStore:
        def save_summary_metrics(self, summary):
            saved.append(dict(summary))

    def _state_snapshot_loader(**_kwargs):
        return lambda: {"summary": {"node_count": 5, "live_packet_count": 11}}

    result = build_dashboard_runtime_loaders(
        iface="iface",
        tracker="tracker",
        send_lock="lock",
        started_at=123.0,
        target="target",
        show_secrets=False,
        history_db_path="/tmp/db.sqlite3",
        revision_info=RevisionInfo(version="0.1.0", commit="abc", label="L", title="T"),
        history_store=_HistoryStore(),
        default_node_history_hours=72,
        default_node_history_points=1440,
        send_chat_message_fn="send_chat_message_fn",
        send_reaction_packet_fn="send_reaction_packet_fn",
        get_local_node_id_fn="get_local_node_id_fn",
        default_chat_max_bytes=220,
        normalize_single_emoji_fn="normalize_single_emoji_fn",
        to_int_fn="to_int_fn",
        utc_now_fn="utc_now_fn",
        build_state_fn="build_state_fn",
        build_state_snapshot_loader_fn=_state_snapshot_loader,
        build_node_history_loader_fn=lambda **_kwargs: (lambda *_a, **_k: {}),
        build_online_activity_loader_fn=lambda **_kwargs: (lambda *_a, **_k: {}),
        build_summary_metrics_loader_fn=lambda **_kwargs: (lambda *_a, **_k: {}),
        build_send_chat_loader_fn=lambda **_kwargs: (lambda **_k: {}),
    )

    payload = result.state_fn()
    assert payload["summary"]["node_count"] == 5
    assert saved and saved[0]["node_count"] == 5
