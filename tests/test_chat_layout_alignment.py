import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_css import build_dashboard_css
from meshdash.html_js import build_dashboard_js
from meshdash.html_sections import build_html_shell


def test_chat_layout_spacing_matches_tighter_network_style() -> None:
    css = build_dashboard_css(theme_css="")

    assert ".workspace-main > .layout.view-chat," in css
    assert ".workspace-main > .layout.view-console {" in css
    assert "grid-row: 1 / -1;" in css
    assert ".chat-shell {" in css
    assert "padding: 8px 10px;" in css
    assert ".chat-main-pane {" in css
    assert "row-gap: 0;" in css
    assert ".chat-log-scroll {" in css
    assert "padding: 0;" in css
    assert ".chat-compose-shell {" in css
    assert "margin-top: 6px;" in css
    assert "background: transparent;" in css
    assert "border: 0;" in css
    assert "border-radius: 0;" in css
    assert "padding: 0;" in css
    assert "gap: 0;" in css
    assert ".chat-left-bottom-bar {" in css
    assert "--chat-user-search-inline-start: 6px;" in css
    assert "--chat-user-search-inline-end: 6px;" in css
    assert "margin: 0 var(--chat-user-search-inline-end) 6px var(--chat-user-search-inline-start);" in css
    assert "border: 0;" in css
    assert "[data-theme=\"dark\"] .chat-left-panel," in css
    assert "[data-theme=\"dark\"] .card.chat .body," in css
    assert "[data-theme=\"dark\"] .card.chat .chat-shell {" in css
    assert "[data-theme=\"dark\"] .chat-left-bottom-bar {" in css
    assert "background: #07140d !important;" in css
    assert "[data-theme=\"dark\"] #chat-emoji-btn," in css
    assert "[data-theme=\"dark\"] #chat-send-btn {" in css
    assert "border-color: #2b8a59 !important;" in css
    assert ".list-search-input,\n    #chat-input {" in css
    assert "#chat-input:hover {" not in css
    assert "[data-theme=\"dark\"] #chat-input:hover {" not in css
    assert "[data-theme=\"dark\"] #chat-input:focus {" not in css


def test_chat_compose_notices_float_above_composer_shell() -> None:
    html = build_html_shell(
        app_title="Meshyface",
        app_heading="Meshyface",
        style_css="",
        app_js="",
        revision_title="rev",
        revision_label="rev",
        safety_label="safe",
        packet_limit=100,
        history_label="history",
        refresh_ms=1000,
    )
    css = build_dashboard_css(theme_css="")

    assert '<div id="chat-compose-notices" class="chat-compose-notices" hidden>' in html
    assert 'id="chat-channel-mismatch-warning"' in html
    assert 'id="chat-send-status"' in html
    assert 'class="chat-notice-viewport"' in html
    assert 'class="chat-notice-track"' in html
    assert 'class="chat-notice-item chat-notice-item-primary"' in html
    assert 'class="chat-notice-item chat-notice-item-secondary"' in html
    assert ".chat-compose-shell {" in css
    assert ".chat-compose-notices {" in css
    assert "padding: 6px 10px 0 10px;" in css
    assert ".chat-notice-track {" in css
    assert "animation: chatNoticeTickerScroll" in css
    assert "@keyframes chatNoticeTickerScroll {" in css


def test_chat_compose_controls_order_matches_current_layout() -> None:
    html = build_html_shell(
        app_title="Meshyface",
        app_heading="Meshyface",
        style_css="",
        app_js="",
        revision_title="rev",
        revision_label="rev",
        safety_label="safe",
        packet_limit=100,
        history_label="history",
        refresh_ms=1000,
    )

    channel_idx = html.index('id="chat-send-channel-menu-btn"')
    input_idx = html.index('id="chat-input"')
    send_idx = html.index('id="chat-send-btn"')
    emoji_idx = html.index('id="chat-emoji-btn"')

    assert channel_idx < input_idx < send_idx < emoji_idx


def test_chat_send_channel_compact_dot_trigger_geometry() -> None:
    css = build_dashboard_css(theme_css="")

    assert ".chat-composer-input-row {" in css
    assert "gap: 6px;" in css
    assert ".chat-send-channel-wrap {" in css
    assert "flex: 0 0 27px;" in css
    assert "min-width: 27px;" in css
    assert "max-width: 27px;" in css
    assert "border-radius: 999px;" in css
    assert ".chat-send-channel-menu-btn {" in css
    assert "position: absolute;" in css
    assert "inset: 0;" in css
    assert ".chat-send-channel-dot {" in css
    assert "pointer-events: none;" in css


def test_chat_node_search_syncs_to_live_navigator_row_bounds() -> None:
    js_src = Path("meshdash/assets/dashboard.js.chat.state.messaging.peers.tmpl").read_text()

    assert "function syncChatNodeNavigatorSearchBounds() {" in js_src
    assert 'document.querySelector(".chat-left-bottom-bar")' in js_src
    assert 'roomList.querySelector(".chat-member-item, .chat-member-empty")' in js_src
    assert 'bottomBar.style.setProperty("--chat-user-search-inline-start",' in js_src
    assert 'bottomBar.style.setProperty("--chat-user-search-inline-end",' in js_src
    assert 'window.addEventListener("resize", scheduleChatNodeNavigatorSearchBoundsSync);' in js_src


def test_chat_click_selection_keeps_same_node_selected() -> None:
    bindings_src = Path("meshdash/assets/dashboard.js.chat.events.bindings.tmpl").read_text()
    peers_src = Path("meshdash/assets/dashboard.js.chat.state.messaging.peers.tmpl").read_text()
    selection_src = Path("meshdash/assets/dashboard.js.chat.events.map_selection.tmpl").read_text()

    assert 'selectNode(nodeId, true, false);' in bindings_src
    assert "function chatFeedSelectionKeyForItem(item) {" in bindings_src
    assert "const sameExactChat = (" in bindings_src
    assert "clearNodeSelection();" in bindings_src
    assert "chatFeedRepeatToggleMessageKey = messageSelectionKey;" in bindings_src
    assert """if (!isSelectableNodeId(nodeId)) {{
          selectNode(nodeId, true);
          return;
        }}
        selectNode(nodeId, true);""" in peers_src
    assert 'if (!chatFeedSelectionSyncInProgress && typeof clearChatFeedRepeatToggleState === "function") {' in selection_src
    assert 'if (typeof clearChatFeedRepeatToggleState === "function") {' in selection_src


def test_chat_reaction_anchor_reuses_same_button_for_more_and_less_states() -> None:
    emoji_src = Path("meshdash/assets/dashboard.js.chat.state.messaging.emoji_ui.tmpl").read_text()
    bindings_src = Path("meshdash/assets/dashboard.js.chat.events.bindings.tmpl").read_text()
    css = build_dashboard_css(theme_css="")

    assert "function syncChatReactionAnchorLabels() {{" in emoji_src
    assert 'function setChatReactionPickerExpanded(expanded, focusSearch = false) {{' in emoji_src
    assert "function isChatReactionAnchorToggleSource(anchor) {{" in emoji_src
    assert "function animateChatEmojiPanelTransition(previousRect = null, options = null) {{" in emoji_src
    assert "function animateChatEmojiPanelClose(options = null) {{" in emoji_src
    assert "function finalizeChatEmojiPanelClose(panel = null) {{" in emoji_src
    assert '"Less reactions"' in emoji_src
    assert '"More reactions"' in emoji_src
    assert "const reactionExpandedFromAnchor = (" in emoji_src
    assert "reactToggleRow.hidden = true;" in emoji_src
    assert 'const reactionAnchorGap = reactionAnchorOwnsToggle ? 0 : 6;' in emoji_src
    assert 'const availableAbove = Math.max(220, Math.round(anchorRect.top - minTop + 2));' in emoji_src
    assert 'if (target.closest(".chat-reaction-summary") || target.closest(".chat-react-btn")) return;' in emoji_src
    assert 'animateChatEmojiPanelTransition(previousRect, {{' in emoji_src
    assert 'animateChatEmojiPanelClose({{' in emoji_src
    assert 'openReactionPickerFromAnchor(summary, {{ expand: true, toggleExpanded: true }});' in bindings_src
    assert 'openReactionPickerFromAnchor(anchor, {{ expand: false }});' in bindings_src
    assert ".chat-reaction-summary.is-empty.is-reaction-preview," in css
    assert ".chat-emoji-panel.is-closing {" in css
    assert "@keyframes chatEmojiPanelContentIn {" in css
    assert "transition: background 140ms ease, border-color 140ms ease, color 140ms ease, box-shadow 180ms ease, transform 180ms ease;" in css
    assert "[data-theme=\"dark\"] .card.chat .chat-reaction-summary.is-empty.is-reaction-preview," in css


def test_chat_node_list_can_collapse_into_compact_rail() -> None:
    html = build_html_shell(
        app_title="Meshyface",
        app_heading="Meshyface",
        style_css="",
        app_js="",
        revision_title="rev",
        revision_label="rev",
        safety_label="safe",
        packet_limit=100,
        history_label="history",
        refresh_ms=1000,
    )
    css = build_dashboard_css(theme_css="")
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'id="chat-panel-collapse-btn"' in html
    assert 'id="chat-panel-collapse-glyph"' in html
    assert "--chat-panel-collapsed-width: 96px;" in css
    assert ".workspace-shell.chat-panel-open.chat-panel-collapsed {" in css
    assert ".workspace-shell.chat-panel-collapsed .chat-users-head-view-btn," in css
    assert ".workspace-shell.chat-panel-collapsed .chat-member-meta-row," in css
    assert "const chatPanelCollapsedStorageKey = \"meshDashboardChatPanelCollapsedV1\";" in js
    assert "let chatPanelCollapsed = false;" in js
    assert "function applyChatPanelCollapseState() {" in js
    assert "function setChatPanelCollapsed(nextCollapsed, options = null) {" in js
    assert "function loadChatPanelCollapseState() {" in js
    assert "function persistChatPanelCollapseState() {" in js
    assert "function bindChatPanelCollapseToggle() {" in js
    assert 'window.localStorage.setItem(chatPanelCollapsedStorageKey, chatPanelCollapsed ? "1" : "0");' in js
    assert 'loadChatPanelCollapseState();' in js
    assert 'bindChatPanelCollapseToggle();' in js
