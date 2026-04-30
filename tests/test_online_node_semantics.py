import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_js import build_dashboard_js
from meshdash.revision import RevisionInfo
from meshdash.state_node_contracts import CollectedNodes
from meshdash.state_service import (
    _count_online_nodes,
    _online_node_count_from_local_stats,
    build_dashboard_state_typed,
)
from meshdash.tracker_snapshot_contracts import empty_tracker_snapshot


class _Tracker:
    def snapshot(self, by_id: dict[str, dict[str, object]]) -> object:
        return empty_tracker_snapshot()

    def load_node_saved_counts(self) -> dict[str, dict[str, object]]:
        return {}

    def load_node_capabilities(self) -> dict[str, dict[str, object]]:
        return {}


class _Object:
    pass


def test_count_online_nodes_uses_meshtastic_two_hour_window() -> None:
    now_unix = 1_800_000_000

    rows = [
        {"id": "!online", "last_heard_unix": now_unix - (2 * 60 * 60) + 1},
        {"id": "!boundary", "last_heard_unix": now_unix - (2 * 60 * 60)},
        {"id": "!offline", "last_heard_unix": now_unix - (2 * 60 * 60) - 1},
    ]

    assert _count_online_nodes(rows, now_unix=now_unix) == 2


def test_local_stats_online_node_count_accepts_meshtastic_shapes() -> None:
    assert (
        _online_node_count_from_local_stats(
            {"local_stats": {"num_online_nodes": 41}}
        )
        == 41
    )
    assert (
        _online_node_count_from_local_stats(
            {"local_node_info": {"localStats": {"numOnlineNodes": 123}}}
        )
        == 123
    )


def test_dashboard_state_prefers_meshtastic_localstats_online_count() -> None:
    rows = [
        {"id": "!online-a", "last_heard_unix": 1_800_000_000},
        {"id": "!online-b", "last_heard_unix": 1_800_000_000},
    ]

    payload = build_dashboard_state_typed(
        iface=_Object(),
        tracker=_Tracker(),
        target="test",
        started_at=1_800_000_000,
        storage_probe_path=None,
        revision_info=RevisionInfo(
            version="0.0.0",
            commit="test",
            label="test",
            title="test",
        ),
        collect_nodes_fn=lambda iface: CollectedNodes(
            rows=rows,
            full=[],
            by_id={row["id"]: row for row in rows},
            with_position_count=0,
        ),
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: (
            {"local_stats": {"num_online_nodes": 99}},
            None,
        ),
        get_radio_connection_status_fn=lambda iface: None,
    )

    assert payload.summary["online_node_count"] == 99
    assert payload.summary["online_node_count_source"] == "local_stats"
    assert payload.summary["online_node_window_seconds"] == 2 * 60 * 60


def test_lite_dashboard_state_uses_iface_localstats_online_count() -> None:
    iface = _Object()
    iface.localNode = _Object()
    iface.localNode.localStats = {"numOnlineNodes": 88}

    payload = build_dashboard_state_typed(
        iface=iface,
        tracker=_Tracker(),
        target="test",
        started_at=1_800_000_000,
        storage_probe_path=None,
        revision_info=RevisionInfo(
            version="0.0.0",
            commit="test",
            label="test",
            title="test",
        ),
        collect_nodes_fn=lambda iface: CollectedNodes(
            rows=[{"id": "!online-a", "last_heard_unix": 1_800_000_000}],
            full=[],
            by_id={},
            with_position_count=0,
        ),
        get_radio_connection_status_fn=lambda iface: None,
        include_debug=False,
        include_nodes_full=False,
    )

    assert payload.summary["online_node_count"] == 88
    assert payload.summary["online_node_count_source"] == "local_stats"


def test_dashboard_js_roster_health_uses_summary_online_count() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "Online uses Meshtastic LocalStats semantics (heard in the past 2 hours)." in js
    assert re.search(
        r'const onlineCount = Math\.max\(\s*0,\s*Math\.min\(totalCount, Math\.trunc\(Number\(s\.online_node_count\) \|\| 0\)\)\s*\);',
        js,
    )
    assert '{ key: "Offline", value: String(offlineCount) }' in js
    assert '{ key: "Total", value: String(totalCount) }' in js


def test_dashboard_js_node_online_history_shows_status_and_official_windows() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "const meshtasticOnlineWindowSeconds = 2 * 60 * 60;" in js
    assert "Status (10m online / 30m stale)" in js
    assert "Official (2h online)" in js
    assert 'Status O/A/S: ${percentText(statusOnlinePercent)} / ${percentText(statusWarnPercent)} / ${percentText(statusStalePercent)}%' in js
    assert 'Official online: ${percentText(officialOnlinePercent)}%' in js
    assert "const rightSummaryX = width - 6;" in js
    assert '<text x="${rightSummaryX.toFixed(2)}" y="${(padTop + 10).toFixed(2)}" font-size="10" text-anchor="end" fill="${chartPalette.label}">' in js
    assert '<tspan x="${rightSummaryX.toFixed(2)}" dy="12">Official online: ${percentText(officialOnlinePercent)}%</tspan>' in js


def test_dashboard_js_keeps_node_history_right_side_labels_inside_chart_frame() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "const rightAxisLabelX = width - 6;" in js
    assert "const rightSummaryX = width - 6;" in js
    assert '<text x="${rightAxisLabelX.toFixed(2)}" y="${padTop + 10}" font-size="10" text-anchor="end" fill="${chartPalette.compareLabel}">${formatMetricValue(rssiMax, 0)}</text>' in js
    assert '<text x="${rightSummaryX.toFixed(2)}" y="${(padTop + 10).toFixed(2)}" font-size="10" text-anchor="end" fill="${chartPalette.label}">' in js
