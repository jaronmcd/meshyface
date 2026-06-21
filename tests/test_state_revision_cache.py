import meshdash.runtime_state_loader as runtime_state_loader
from meshdash.revision import RevisionInfo
from meshdash.runtime_state_contracts import StateSnapshotRuntimeDependencies
from meshdash.runtime_state_loader import build_state_snapshot_loader_with_dependencies
from meshdash.tracker_runtime_impl import DashboardTracker


def _revision() -> RevisionInfo:
    return RevisionInfo(
        version="test",
        commit="test",
        label="test",
        title="Dashboard revision: test",
    )


class _Tracker:
    live_packet_count = 0
    radio_link_changed_unix = 0
    state_revision = 0


def test_state_snapshot_cache_key_includes_tracker_state_revision() -> None:
    tracker = _Tracker()
    calls = []

    def build_state_fn(**_kwargs):
        calls.append("full")
        return {"state_revision": tracker.state_revision}

    def build_lite_chat_fn(**_kwargs):
        calls.append("lite_chat")
        return {"state_revision": tracker.state_revision, "profile": "chat"}

    setattr(build_state_fn, "lite_chat", build_lite_chat_fn)

    def build_lite_status_fn(**_kwargs):
        calls.append("lite_status")
        return {"state_revision": tracker.state_revision, "profile": "status"}

    setattr(build_state_fn, "lite_status", build_lite_status_fn)

    def build_lite_network_graph_fn(**_kwargs):
        calls.append("lite_network_graph")
        return {"state_revision": tracker.state_revision, "profile": "network-graph"}

    setattr(build_state_fn, "lite_network_graph", build_lite_network_graph_fn)

    def build_lite_network_map_fn(**_kwargs):
        calls.append("lite_network_map")
        return {"state_revision": tracker.state_revision, "profile": "network-map"}

    setattr(build_state_fn, "lite_network_map", build_lite_network_map_fn)
    state_fn = build_state_snapshot_loader_with_dependencies(
        dependencies=StateSnapshotRuntimeDependencies(
            iface=object(),
            tracker=tracker,
            started_at=0,
            target="test",
            show_secrets=False,
            storage_probe_path=None,
            revision_info=_revision(),
        ),
        build_state_fn=build_state_fn,
    )

    assert state_fn() == {"state_revision": 0}
    assert state_fn() == {"state_revision": 0}
    assert calls == ["full"]
    first_etag = state_fn.etag()  # type: ignore[attr-defined]

    tracker.state_revision += 1

    assert state_fn() == {"state_revision": 1}
    assert calls == ["full", "full"]
    assert state_fn.etag() != first_etag  # type: ignore[attr-defined]

    lite_chat_fn = state_fn.lite_chat  # type: ignore[attr-defined]
    assert lite_chat_fn() == {"state_revision": 1, "profile": "chat"}
    assert lite_chat_fn() == {"state_revision": 1, "profile": "chat"}
    assert calls == ["full", "full", "lite_chat"]

    tracker.state_revision += 1

    assert lite_chat_fn() == {"state_revision": 2, "profile": "chat"}
    assert calls == ["full", "full", "lite_chat", "lite_chat"]

    lite_status_fn = state_fn.lite_status  # type: ignore[attr-defined]
    assert lite_status_fn() == {"state_revision": 2, "profile": "status"}
    assert lite_status_fn() == {"state_revision": 2, "profile": "status"}
    assert calls == ["full", "full", "lite_chat", "lite_chat", "lite_status"]

    lite_network_graph_fn = state_fn.lite_network_graph  # type: ignore[attr-defined]
    assert lite_network_graph_fn() == {"state_revision": 2, "profile": "network-graph"}
    assert lite_network_graph_fn() == {"state_revision": 2, "profile": "network-graph"}
    assert calls == [
        "full",
        "full",
        "lite_chat",
        "lite_chat",
        "lite_status",
        "lite_network_graph",
    ]

    lite_network_map_fn = state_fn.lite_network_map  # type: ignore[attr-defined]
    assert lite_network_map_fn() == {"state_revision": 2, "profile": "network-map"}
    assert lite_network_map_fn() == {"state_revision": 2, "profile": "network-map"}
    assert calls == [
        "full",
        "full",
        "lite_chat",
        "lite_chat",
        "lite_status",
        "lite_network_graph",
        "lite_network_map",
    ]


def test_state_snapshot_etag_includes_backend_runtime_instance() -> None:
    tracker = _Tracker()

    def build_state_fn(**_kwargs):
        return {"ok": True}

    first = build_state_snapshot_loader_with_dependencies(
        dependencies=StateSnapshotRuntimeDependencies(
            iface=object(),
            tracker=tracker,
            started_at=100.0,
            target="test",
            show_secrets=False,
            storage_probe_path=None,
            revision_info=_revision(),
        ),
        build_state_fn=build_state_fn,
    )
    second = build_state_snapshot_loader_with_dependencies(
        dependencies=StateSnapshotRuntimeDependencies(
            iface=object(),
            tracker=tracker,
            started_at=101.0,
            target="test",
            show_secrets=False,
            storage_probe_path=None,
            revision_info=_revision(),
        ),
        build_state_fn=build_state_fn,
    )

    assert first.etag() != second.etag()  # type: ignore[attr-defined]


def test_state_snapshot_etag_handles_invalid_runtime_revision_inputs(monkeypatch) -> None:
    tracker = _Tracker()
    tracker.live_packet_count = "bad"
    tracker.radio_link_changed_unix = object()
    tracker.state_revision = "bad"
    monkeypatch.setattr(runtime_state_loader.time, "time", lambda: 6_000.0)

    def build_state_fn(**_kwargs):
        return {"ok": True}

    state_fn = build_state_snapshot_loader_with_dependencies(
        dependencies=StateSnapshotRuntimeDependencies(
            iface=object(),
            tracker=tracker,
            started_at="not-a-time",
            target="test",
            show_secrets=False,
            storage_probe_path=None,
            revision_info=_revision(),
        ),
        build_state_fn=build_state_fn,
    )

    assert state_fn() == {"ok": True}
    assert state_fn.etag() == 'W/"full-b0-p0-r0-s0-t100"'  # type: ignore[attr-defined]


def test_record_local_chat_bumps_tracker_state_revision() -> None:
    tracker = DashboardTracker(packet_limit=10)

    before = tracker.state_revision
    tracker.record_local_chat(
        text="hello",
        from_id="!local",
        to_id="^all",
        channel_index=0,
        message_id=123,
    )

    assert tracker.state_revision > before
