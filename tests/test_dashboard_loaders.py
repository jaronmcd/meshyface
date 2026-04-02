from meshdash.dashboard_loaders import DashboardRuntimeLoaders, build_dashboard_runtime_loaders
from meshdash import dashboard_runtime_loaders as runtime_loaders_mod
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


def test_build_dashboard_runtime_loaders_does_not_persist_summary_metrics_on_state_reads():
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
    assert saved == []


def test_with_summary_persistence_skips_startup_grace_samples():
    saved = []

    class _Store:
        def save_summary_metrics(self, summary):
            saved.append(dict(summary))

    payloads = iter(
        [
            {"summary": {"node_count": 2, "uptime_seconds": 30}},
            {"summary": {"node_count": 8, "uptime_seconds": 120}},
        ]
    )

    def _base_state_fn():
        return next(payloads)

    wrapped = runtime_loaders_mod._with_summary_persistence(
        base_state_fn=_base_state_fn,
        history_store=_Store(),
    )

    assert wrapped()["summary"]["node_count"] == 2
    assert wrapped()["summary"]["node_count"] == 8
    assert len(saved) == 1
    assert saved[0]["node_count"] == 8


def test_extract_and_copy_state_helpers_cover_mapping_and_attr_paths(monkeypatch):
    assert runtime_loaders_mod._extract_state_summary({"summary": {"ok": True}}) == {"ok": True}
    assert runtime_loaders_mod._extract_state_summary({"summary": "bad"}) is None
    assert runtime_loaders_mod._extract_state_summary(type("_S", (), {"summary": {"x": 1}})()) == {"x": 1}
    assert runtime_loaders_mod._extract_state_summary(type("_S", (), {"summary": "bad"})()) is None

    def _source():
        return {}

    for name in ("etag", "raw_my_info", "raw_metadata", "raw_local_state", "raw_nodes_full", "_sensitive_field_names"):
        setattr(_source, name, lambda *args, **kwargs: None)

    class _Target:
        def __setattr__(self, _name, _value):
            raise RuntimeError("no set")

    target = _Target()
    # Should not raise even when setattr fails.
    runtime_loaders_mod._copy_state_fn_attrs(target, _source)


def test_with_summary_persistence_handles_missing_summary_lite_and_save_errors():
    saved = {"count": 0}

    class _Store:
        def save_summary_metrics(self, _summary):
            saved["count"] += 1
            if saved["count"] == 2:
                raise RuntimeError("save failed")

    def _base_state_fn():
        return {"summary": {"node_count": 2}}

    def _base_lite_fn():
        return {"summary": {"node_count": 1}}

    setattr(_base_state_fn, "etag", lambda: "W/full")
    setattr(_base_state_fn, "lite", _base_lite_fn)
    setattr(_base_lite_fn, "etag", lambda: "W/lite")

    wrapped = runtime_loaders_mod._with_summary_persistence(
        base_state_fn=_base_state_fn,
        history_store=_Store(),
    )
    assert wrapped()["summary"]["node_count"] == 2
    assert wrapped()["summary"]["node_count"] == 2
    assert callable(wrapped.lite)
    assert wrapped.lite()["summary"]["node_count"] == 1
    assert saved["count"] == 3

    passthrough = runtime_loaders_mod._with_summary_persistence(
        base_state_fn=_base_state_fn,
        history_store=object(),
    )
    assert passthrough is _base_state_fn


def test_build_dashboard_runtime_loaders_wrapper_uses_legacy_dependency_builder(monkeypatch):
    captured = {}
    deps = DashboardRuntimeLoaderDependencies(
        iface="iface",
        tracker="tracker",
        send_lock="lock",
        started_at=1.0,
        target="target",
        show_secrets=False,
        history_db_path="/tmp/h.sqlite3",
        revision_info=RevisionInfo(version="0.1.0", commit="abc", label="L", title="T"),
        history_store=None,
        default_node_history_hours=72,
        default_node_history_points=100,
        send_chat_message_fn="send",
        send_reaction_packet_fn="react",
        get_local_node_id_fn="get_local",
        default_chat_max_bytes=220,
        normalize_single_emoji_fn="emoji",
        to_int_fn="to_int",
        utc_now_fn="utc_now",
        build_state_fn="build_state",
        build_state_snapshot_loader_fn=lambda **_kwargs: (lambda: {"summary": {}}),
        build_node_history_loader_fn=lambda **_kwargs: (lambda *_a, **_k: {}),
        build_online_activity_loader_fn=lambda **_kwargs: (lambda *_a, **_k: {}),
        build_summary_metrics_loader_fn=lambda **_kwargs: (lambda *_a, **_k: {}),
        build_send_chat_loader_fn=lambda **_kwargs: (lambda **_k: {}),
    )

    monkeypatch.setattr(
        runtime_loaders_mod,
        "build_dashboard_runtime_loader_dependencies_from_legacy_args",
        lambda **kwargs: (captured.update(kwargs), deps)[1],
    )
    monkeypatch.setattr(
        runtime_loaders_mod,
        "build_dashboard_runtime_loaders_with_dependencies",
        lambda **kwargs: (captured.update({"wrapped": kwargs}), "sentinel")[1],
    )

    result = build_dashboard_runtime_loaders(
        iface="iface",
        tracker="tracker",
        send_lock="lock",
        started_at=1.0,
        target="target",
        show_secrets=False,
        history_db_path="/tmp/h.sqlite3",
        revision_info=deps.revision_info,
        history_store=None,
        default_node_history_hours=72,
        default_node_history_points=100,
        send_chat_message_fn="send",
        send_reaction_packet_fn="react",
        get_local_node_id_fn="get_local",
        default_chat_max_bytes=220,
        normalize_single_emoji_fn="emoji",
        to_int_fn="to_int",
        utc_now_fn="utc_now",
        build_state_fn="build_state",
        build_state_snapshot_loader_fn=deps.build_state_snapshot_loader_fn,
        build_node_history_loader_fn=deps.build_node_history_loader_fn,
        build_online_activity_loader_fn=deps.build_online_activity_loader_fn,
        build_summary_metrics_loader_fn=deps.build_summary_metrics_loader_fn,
        build_send_chat_loader_fn=deps.build_send_chat_loader_fn,
    )
    assert result == "sentinel"
    assert captured["iface"] == "iface"
    assert captured["wrapped"]["dependencies"] is deps


def test_with_summary_persistence_handles_missing_summary_and_lite_setattr_failure(monkeypatch):
    saved = {"count": 0}

    class _Store:
        def save_summary_metrics(self, summary):
            saved["count"] += 1

    def _base_state_fn():
        return {"not_summary": True}

    def _base_lite_fn():
        return {"summary": {"ok": True}}

    setattr(_base_state_fn, "lite", _base_lite_fn)

    import builtins

    original_setattr = builtins.setattr

    def _flaky_setattr(obj, name, value):
        if name == "lite":
            raise RuntimeError("blocked")
        return original_setattr(obj, name, value)

    monkeypatch.setattr(builtins, "setattr", _flaky_setattr)

    wrapped = runtime_loaders_mod._with_summary_persistence(
        base_state_fn=_base_state_fn,
        history_store=_Store(),
    )
    assert wrapped()["not_summary"] is True
    assert saved["count"] == 0
