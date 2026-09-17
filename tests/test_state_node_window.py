import json
import time
from types import SimpleNamespace

from meshdash import state_service
from meshdash.helpers import to_int
from meshdash.http_routes_get import handle_dashboard_get
from meshdash.revision import RevisionInfo
from meshdash.state_node_contracts import CollectedNodes
from meshdash.state_node_window import (
    DEFAULT_STATE_NODE_WINDOW_DAYS,
    STATE_NODE_WINDOW_DAYS_ENV,
    filter_node_rows_for_window,
    referenced_node_ids,
    state_node_window_seconds,
)
from meshdash.tracker_snapshot_contracts import empty_tracker_snapshot

DAY = 24 * 60 * 60


def _revision() -> RevisionInfo:
    return RevisionInfo(version="test", commit="test", label="test", title="Dashboard revision: test")


def _build_state(rows, *, node_window_seconds, edges=None, capabilities=None):
    snapshot = empty_tracker_snapshot()
    if edges:
        snapshot = type(snapshot)(**{**snapshot.__dict__, "edges": edges})
    return state_service.build_dashboard_state_typed(
        iface=SimpleNamespace(localNode=None),
        tracker=SimpleNamespace(),
        target="test",
        started_at=0,
        storage_probe_path=None,
        revision_info=_revision(),
        collect_nodes_fn=lambda _iface: CollectedNodes(
            rows=[dict(row) for row in rows],
            full=[],
            by_id={row["id"]: dict(row) for row in rows},
            with_position_count=sum(1 for row in rows if row.get("lat") is not None),
        ),
        load_tracker_snapshot_safe_fn=lambda _tracker, _by_id: (snapshot, None),
        load_tracker_node_saved_counts_safe_fn=lambda _tracker: ({}, None),
        load_tracker_node_capabilities_safe_fn=lambda _tracker: (capabilities or {}, None),
        include_debug=False,
        include_nodes_full=False,
        include_node_packet_trends=False,
        node_window_seconds=node_window_seconds,
    )


def test_window_defaults_to_fourteen_days_and_can_be_disabled() -> None:
    assert DEFAULT_STATE_NODE_WINDOW_DAYS == 14
    assert state_node_window_seconds({}) == 14 * DAY
    assert state_node_window_seconds({STATE_NODE_WINDOW_DAYS_ENV: "7"}) == 7 * DAY
    assert state_node_window_seconds({STATE_NODE_WINDOW_DAYS_ENV: "0"}) == 0
    assert state_node_window_seconds({STATE_NODE_WINDOW_DAYS_ENV: "junk"}) == 14 * DAY


def test_filter_keeps_recent_favorite_and_referenced_nodes_in_order() -> None:
    now = 1_800_000_000
    rows = [
        {"id": "!00000001", "last_heard_unix": now - 60},
        {"id": "!00000002", "last_heard_unix": now - 20 * DAY},
        {"id": "!00000003", "last_heard_unix": now - 20 * DAY, "is_favorite": True},
        {"id": "!00000004", "last_heard_unix": now - 20 * DAY},
        {"id": "!00000005"},
        {"id": "!00000006", "last_heard_unix": now - 14 * DAY},
    ]

    kept, omitted = filter_node_rows_for_window(
        rows,
        window_seconds=14 * DAY,
        keep_node_ids={"!00000004"},
        now_unix=now,
    )

    assert [row["id"] for row in kept] == ["!00000001", "!00000003", "!00000004", "!00000006"]
    assert omitted == 2


def test_referenced_node_ids_cover_chat_packets_and_edges() -> None:
    ids = referenced_node_ids(
        recent_chat=[{"from": "!0000000A", "to": "^all"}],
        recent_packets=[{"summary": {"from": "!0000000b"}, "packet": {"toId": "!0000000c"}}],
        edges=[{"from": "!0000000d", "to": "!0000000e"}],
    )

    assert ids == {"!0000000a", "!0000000b", "!0000000c", "!0000000d", "!0000000e"}


def test_lite_state_build_omits_long_unheard_nodes_but_reports_known_count(monkeypatch) -> None:
    monkeypatch.setattr(state_service, "_get_local_node_id_helper", lambda *_args, **_kwargs: "!0000beef")
    now = int(time.time())
    rows = [
        {"id": "!00000001", "last_heard_unix": now - 60, "lat": 45.0, "lon": -93.0},
        {"id": "!00000002", "last_heard_unix": now - 30 * DAY, "lat": 45.1, "lon": -93.1},
        {"id": "!00000003", "last_heard_unix": now - 30 * DAY},
        {"id": "!0000beef", "last_heard_unix": now - 30 * DAY},
    ]
    edges = [{"from": "!00000003", "to": "!00000001"}]

    windowed = _build_state(rows, node_window_seconds=14 * DAY, edges=edges)
    unbounded = _build_state(rows, node_window_seconds=0, edges=edges)

    assert [row["id"] for row in unbounded.nodes] == ["!00000001", "!00000002", "!00000003", "!0000beef"]
    # Kept: recent, referenced by an edge, and the local node; omitted: the stale bystander.
    assert [row["id"] for row in windowed.nodes] == ["!00000001", "!00000003", "!0000beef"]
    assert windowed.summary["known_node_count"] == 4
    assert windowed.summary["node_count"] == 3
    assert windowed.summary["node_window_omitted_count"] == 1
    assert windowed.summary["nodes_with_position"] == 1
    assert unbounded.summary["node_window_omitted_count"] == 0


def test_routine_poll_node_payload_is_bounded_by_the_window_not_by_uptime() -> None:
    # Guard for long radio-link uptimes: thousands of long-unheard nodes must not reach the
    # routine poll payload.
    now = int(time.time())
    recent = [{"id": f"!{index:08x}", "last_heard_unix": now - index} for index in range(300)]
    stale = [{"id": f"!{index + 0x10000:08x}", "last_heard_unix": now - 40 * DAY} for index in range(3000)]

    state = _build_state(recent + stale, node_window_seconds=14 * DAY)

    assert len(state.nodes) == 300
    assert state.summary["known_node_count"] == 3300
    assert state.summary["node_window_omitted_count"] == 3000


def test_search_state_nodes_finds_nodes_outside_the_window_by_name_or_id() -> None:
    now = int(time.time())
    rows = [
        {"id": "!00000001", "short_name": "ALFA", "long_name": "Alpha Base", "last_heard_unix": now},
        {"id": "!00000002", "short_name": "BRVO", "long_name": "Bravo Hill", "last_heard_unix": now - 40 * DAY},
    ]
    capabilities = {
        "!00000009": {"last_long_name": "Bravo Tower", "last_short_name": "BTWR", "last_seen_unix": now - 90 * DAY},
        "!00000002": {"last_long_name": "Bravo Hill", "last_seen_unix": now - 40 * DAY, "private": "drop"},
    }

    result = state_service.search_state_nodes(
        iface=object(),
        tracker=SimpleNamespace(),
        query="bravo",
        limit=10,
        collect_nodes_fn=lambda _iface: CollectedNodes(rows=rows, full=[], by_id={}, with_position_count=0),
        load_tracker_node_capabilities_safe_fn=lambda _tracker: (capabilities, None),
    )

    assert result["ok"] is True
    assert [row["id"] for row in result["nodes"]] == ["!00000002"]
    assert list(result["history_caps"]) == ["!00000002", "!00000009"]
    assert "private" not in json.dumps(result)
    empty = state_service.search_state_nodes(iface=object(), tracker=SimpleNamespace(), query="  ")
    assert empty == {"ok": True, "query": "", "nodes": [], "history_caps": {}}


def test_nodes_search_route_uses_state_search_hook() -> None:
    calls = []
    recorded = []

    class _StateFn:
        def __call__(self):
            return {}

        def search_nodes(self, query, limit):
            calls.append((query, limit))
            return {"ok": True, "query": query, "nodes": [], "history_caps": {}}

    deps = SimpleNamespace(
        state_fn=_StateFn(),
        to_int_fn=to_int,
        write_json_response_fn=lambda handler, *, status_code, payload_obj, no_store=False, **kwargs: recorded.append(
            (status_code, payload_obj, no_store)
        ),
    )

    handle_dashboard_get(object(), path="/api/nodes/search", query="q=bravo%20hill&limit=5", deps=deps)

    assert calls == [("bravo hill", 5)]
    assert recorded == [(200, {"ok": True, "query": "bravo hill", "nodes": [], "history_caps": {}}, True)]


def test_roster_search_asks_server_for_nodes_outside_the_window() -> None:
    from meshdash.html_js import build_dashboard_js

    js = build_dashboard_js(refresh_ms=1000, node_history_hours=24, node_history_max_points=240)

    assert "function requestNodeWindowSearch(queryRaw) {" in js
    assert "`/api/nodes/search?q=${encodeURIComponent(query)}&limit=${nodeWindowSearchLimit}`" in js
    assert "return Number(summary && summary.node_window_omitted_count) > 0;" in js
    assert "if (includeHistoricalOnDemand && nodeWindowSearchActive(safeState)) {" in js
    assert 'if (rosterQuery && typeof nodeWindowSearchActive === "function" && nodeWindowSearchActive(state)) {' in js


def test_state_loader_exposes_node_search_to_routes(monkeypatch) -> None:
    from meshdash import runtime_state_loader
    from meshdash.runtime_state_contracts import StateSnapshotRuntimeDependencies

    calls = []
    monkeypatch.setattr(
        runtime_state_loader,
        "_search_state_nodes",
        lambda **kwargs: calls.append(kwargs) or {"ok": True, "query": kwargs["query"], "nodes": [], "history_caps": {}},
    )
    iface = object()
    tracker = SimpleNamespace(live_packet_count=0, radio_link_changed_unix=0, state_revision=0)
    state_fn = runtime_state_loader.build_state_snapshot_loader_with_dependencies(
        dependencies=StateSnapshotRuntimeDependencies(
            iface=iface,
            tracker=tracker,
            started_at=0,
            target="test",
            show_secrets=False,
            storage_probe_path=None,
            revision_info=_revision(),
        ),
        build_state_fn=lambda **_kwargs: {},
    )

    assert state_fn.search_nodes("bravo", 7)["query"] == "bravo"
    assert calls == [{"iface": iface, "tracker": tracker, "query": "bravo", "limit": 7}]


def test_lite_builder_applies_the_configured_window_and_full_build_does_not(monkeypatch) -> None:
    captured = []
    original = state_service.build_dashboard_state_typed

    def spy(**kwargs):
        captured.append(kwargs.get("node_window_seconds", 0))
        return original(**kwargs)

    monkeypatch.setattr(state_service, "build_dashboard_state_typed", spy)
    common = dict(
        iface=object(),
        tracker=object(),
        started_at=0,
        target="",
        show_secrets=True,
        storage_probe_path=None,
        revision_info={},
        sensitive_field_names=set(),
        collect_nodes_fn=lambda _iface: {"rows": [], "full": [], "by_id": {}, "with_position_count": 0},
        load_tracker_snapshot_safe_fn=lambda _tracker, _nodes_by_id: (empty_tracker_snapshot(), None),
        load_tracker_node_saved_counts_safe_fn=lambda _tracker: ({}, None),
        load_tracker_node_capabilities_safe_fn=lambda _tracker: ({}, None),
        build_summary_payload_fn=lambda **_kwargs: {},
        get_radio_connection_status_fn=lambda _iface: {},
    )

    monkeypatch.delenv(STATE_NODE_WINDOW_DAYS_ENV, raising=False)
    state_service.build_dashboard_state_lite(profile="chat", **common)
    monkeypatch.setenv(STATE_NODE_WINDOW_DAYS_ENV, "3")
    state_service.build_dashboard_state_lite(profile="status", **common)
    state_service.build_dashboard_state(**{key: value for key, value in common.items() if key != "sensitive_field_names"}, sensitive_field_names=set())

    assert captured == [14 * DAY, 3 * DAY, 0]
