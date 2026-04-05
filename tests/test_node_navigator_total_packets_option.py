import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_js import build_dashboard_js
from meshdash.html_template import render_html


def test_dashboard_js_labels_saved_history_field_as_total_packets() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'id: "saved", label: "Total Packets", sortable: true, rosterMeta: true' in js
    assert 'id: "saved", label: "Total Packets"' in js


def test_render_html_uses_packets_header_for_nodes_table() -> None:
    html = render_html(
        refresh_ms=1000,
        packet_limit=200,
        show_secrets=False,
        history_enabled=True,
        history_max_rows=200,
        history_retention_days=7,
        node_history_hours=24,
        node_history_max_points=240,
        revision_label="test",
        revision_title="test",
    )

    assert '<th>Packets<div class="col-resizer" data-col="7" aria-hidden="true"></div></th>' in html


def test_render_html_disables_roster_scroll_anchoring() -> None:
    html = render_html(
        refresh_ms=1000,
        packet_limit=200,
        show_secrets=False,
        history_enabled=True,
        history_max_rows=200,
        history_retention_days=7,
        node_history_hours=24,
        node_history_max_points=240,
        revision_label="test",
        revision_title="test",
    )

    assert ".chat-member-list {" in html
    assert "overflow-anchor: none;" in html


def test_dashboard_js_only_applies_saved_peer_pin_sorting_in_direct_mode() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'const pinDiff = activeChatChannel === "direct"' in js
    assert '? (Number(!!(b && b.p2pPinned)) - Number(!!(a && a.p2pPinned)))' in js
    assert '? (Number(!!b.p2pPinned) - Number(!!a.p2pPinned))' in js


def test_dashboard_js_resets_roster_scroll_when_sort_changes() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "const sortChanged = (" in js
    assert "pendingSelectionScroll = false;" in js
    assert "chatNodeNavigatorSelectionScrollLocked = true;" in js
    assert "function resetChatNodeNavigatorViewport()" in js
    assert 'const roomList = document.getElementById("chat-room-list");' in js
    assert "roomList.scrollTop = 0;" in js


def test_dashboard_js_temporarily_suppresses_selected_node_autoscroll_after_sort() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "const suppressChatRosterSelectionScroll = (" in js
    assert "!!chatNodeNavigatorSelectionScrollLocked" in js
    assert "function clearChatNodeNavigatorSelectionScrollLock()" in js
    assert 'targetList.addEventListener("scroll"' in js


def test_dashboard_js_prefers_numeric_roster_sort_for_numeric_like_values() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "const leftNum = Number(left);" in js
    assert "const rightNum = Number(right);" in js
    assert "if (leftHasNum && rightHasNum) {" in js
    assert "return leftNum - rightNum;" in js


def test_dashboard_js_supports_idle_toggle_in_node_navigator() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "let chatNodeNavigatorShowIdle = true;" in js
    assert "function normalizeChatNodeNavigatorShowIdlePref(value) {" in js
    assert 'showIdle: normalizeChatNodeNavigatorShowIdlePref(chatNodeNavigatorShowIdle),' in js
    assert 'const nextShowIdle = normalizeChatNodeNavigatorShowIdlePref(' in js
    assert 'chatNodeNavigatorShowIdle = nextShowIdle;' in js
    assert '<input type="checkbox" data-nav-toggle-id="idle"' in js
    assert '<span>Idle</span>' in js
    assert 'if (toggleId === "idle") {' in js
    assert 'showIdle: !!target.checked,' in js
    assert 'const idleRowHtml = showIdle' in js
    assert 'const memberMetaRowParts = [];' in js
    assert 'const memberMetaRowHtml = memberMetaRowParts.length > 0' in js


def test_dashboard_js_sorts_status_using_visible_freshness_snapshot() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "function chatNodeNavigatorStatusSortValue(item, projection) {" in js
    assert 'const statusKey = normalizeFreshnessKey(item && item.status);' in js
    assert 'return (typeof statusRank === "function") ? statusRank(statusKey) : 99;' in js
    assert "return chatNodeNavigatorStatusSortValue(safeItem, safeProjection);" in js
    assert "chatNodeNavigatorStatusSortValue(a, aProjection)" in js
    assert "chatNodeNavigatorStatusSortValue(b, bProjection)" in js
