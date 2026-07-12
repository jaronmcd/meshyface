import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_js import build_dashboard_js


def test_dashboard_js_includes_node_arrow_navigation_binding() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "function bindNodeDirectionalKeys()" in js
    assert 'if (ev.key !== "ArrowUp" && ev.key !== "ArrowDown") return;' in js
    assert 'runBootStep("bindNodeDirectionalKeys", () => bindNodeDirectionalKeys());' in js


def test_dashboard_js_uses_hidden_chat_roster_for_arrow_navigation_when_details_fill_list() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "function nodeDirectionalEntriesFrom(containerSelector, itemSelector, options = null)" in js
    assert "function visibleNodeDirectionalEntriesFrom(containerSelector, itemSelector)" in js
    assert "function chatRosterDirectionalEntries({ requireVisible = true } = {})" in js
    assert '["#chat-room-unread-list", ".chat-member-item[data-node-id]"]' in js
    assert '["#chat-room-meshtastic-list", ".chat-member-item[data-node-id]"]' in js
    assert '["#chat-room-pinned-list", ".chat-member-item[data-node-id]"]' in js
    assert '["#chat-room-list", ".chat-member-item[data-node-id]"]' in js
    assert 'const visibleRosterEntries = chatRosterDirectionalEntries({ requireVisible: true });' in js
    assert 'if (visibleRosterEntries.some((entry) => entry.id === selectedId)) {' in js
    assert 'return visibleRosterEntries;' in js
    assert 'const rosterEntries = chatRosterDirectionalEntries({ requireVisible: false });' in js
    assert 'if (rosterEntries.some((entry) => entry.id === selectedId)) {' in js
    assert '&& isChatNodeDetailsDrawerExpanded()' in js
    assert '&& isChatNodeDetailsPromotedActive()' in js
    assert '["#favorites-list", ".favorite-node-item[data-node-id]"]' not in js
    assert '["#nodes-table", "tbody tr.node-selectable[data-node-id]"]' in js
    assert 'target instanceof HTMLInputElement' in js
    assert 'target instanceof HTMLTextAreaElement' in js
    assert 'target instanceof HTMLSelectElement' in js


def test_chat_and_network_rosters_share_retained_node_inclusion() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    helper = js.split(
        "function touchChatNodeNavigatorRetainedNodes(touchNodeById) {", 1
    )[1].split("function buildChatNodeNavigatorDefaultRoster", 1)[0]
    assert "favoriteNodeIds.forEach" in helper
    assert "pinnedNodeIds.forEach" in helper
    assert "nodeNotesById.forEach" in helper
    assert "touchChatNodeNavigatorRetainedNodes(touchNodeById);" in js
    assert "touchChatNodeNavigatorRetainedNodes((nodeId) => {" in js
