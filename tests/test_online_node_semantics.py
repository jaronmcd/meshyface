import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_js import build_dashboard_js
from meshdash.state_service import _count_online_nodes


def test_count_online_nodes_uses_meshtastic_two_hour_window() -> None:
    now_unix = 1_800_000_000

    rows = [
        {"id": "!online", "last_heard_unix": now_unix - (2 * 60 * 60) + 1},
        {"id": "!boundary", "last_heard_unix": now_unix - (2 * 60 * 60)},
        {"id": "!offline", "last_heard_unix": now_unix - (2 * 60 * 60) - 1},
    ]

    assert _count_online_nodes(rows, now_unix=now_unix) == 2


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
