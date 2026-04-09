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
    assert ".chat-left-head-shell {" in css
    assert "border: 1px solid #d2e1d0;" in css
    assert "background: #edf6ec;" in css
    assert ".chat-left-roster-shell {" in css
    assert "border: 1px solid #d2e1d0;" in css
    assert "background: #f7fcf7;" in css
    assert ".layout.view-chat .chat {" in css
    assert "background: transparent;" in css
    assert "border: 0;" in css
    assert "box-shadow: none;" in css
    assert "overflow: visible;" in css
    assert "gap: 8px;" in css
    assert ".chat-left-panel {" in css
    assert "border: 0;" in css
    assert "background: transparent;" in css
    assert "box-shadow: none;" in css
    assert ".chat-left-section.chat-users-section {" in css
    assert "gap: 0;" in css
    assert ".chat-users-head {" in css
    assert "padding: 0;" in css
    assert "background: transparent;" in css
    assert ".chat-users-head-title {" in css
    assert ".chat-left-panel .chat-member-list {" in css
    assert "background: transparent;" in css
    assert ".layout.view-chat .chat .body {" in css
    assert "padding: 0;" in css
    assert ".layout.view-chat .chat-shell {" in css
    assert "padding: 0;" in css
    assert ".layout.view-chat .chat-compose-notices {" in css
    assert "padding: 0 0 6px 0;" in css
    assert ".layout.view-chat .chat-main-pane {" in css
    assert "row-gap: 8px;" in css
    assert ".layout.view-chat .chat-log-scroll {" in css
    assert "border: 1px solid #d2e1d0;" in css
    assert "border-radius: 10px;" in css
    assert "background: #f7fcf7;" in css
    assert ".layout.view-chat .chat-compose-shell {" in css
    assert "margin-top: 0;" in css
    assert "border: 1px solid #d2e1d0;" in css
    assert "border-radius: 10px;" in css
    assert "background: #edf6ec;" in css
    assert "padding: 6px 8px;" in css
    assert "gap: 0;" in css
    assert ".chat-left-bottom-bar {" in css
    assert "margin: 0;" in css
    assert "border: 1px solid #d2e1d0;" in css
    assert "background: #edf6ec;" in css
    assert ".chat-member-list {" in css
    assert "gap: 0;" in css
    assert ".chat-member-item {" in css
    assert "border-radius: 0;" in css
    assert "border-bottom: 1px solid var(--chat-member-node-border);" in css
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


def test_chat_left_column_uses_distinct_head_and_roster_shells() -> None:
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

    assert 'class="chat-left-head-shell"' in html
    assert 'class="chat-left-section chat-users-section chat-left-roster-shell"' in html
    assert 'id="chat-users-head-title"' in html
    assert 'id="chat-users-head-version"' in html
    assert 'id="chat-users-head-commit"' in html


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


def test_dark_chat_palette_matches_green_workspace_theme() -> None:
    css = build_dashboard_css(theme_css="")

    assert "[data-theme=\"dark\"] .card.chat .chat-card-head {" in css
    assert "background: #0d1711;" in css
    assert "[data-theme=\"dark\"] .layout.view-chat .card.chat {" in css
    assert "border-color: transparent;" in css
    assert "[data-theme=\"dark\"] .chat-left-panel {" in css
    assert "border-color: transparent !important;" in css
    assert "[data-theme=\"dark\"] .chat-left-head-shell {" in css
    assert "[data-theme=\"dark\"] .chat-left-roster-shell {" in css
    assert "[data-theme=\"dark\"] .chat-users-head-title {" in css
    assert "[data-theme=\"dark\"] .card.chat .body {" in css
    assert "[data-theme=\"dark\"] .card.chat .chat-shell {" in css
    assert "background: #08120d;" in css
    assert "background: #08120d !important;" in css
    assert "[data-theme=\"dark\"] .layout.view-chat .card.chat .body," in css
    assert "[data-theme=\"dark\"] .layout.view-chat .card.chat .chat-shell {" in css
    assert "background: transparent !important;" in css
    assert "[data-theme=\"dark\"] .layout.view-chat .card.chat .chat-card-head.workspace-chrome-bar {" in css
    assert "background: var(--workspace-shell-bg-alt);" in css
    assert "[data-theme=\"dark\"] .layout.view-chat .card.chat .chat-log-scroll {" in css
    assert "background: var(--workspace-shell-bg);" in css
    assert "border-color: var(--workspace-shell-border);" in css
    assert "[data-theme=\"dark\"] .layout.view-chat .card.chat .chat-compose-shell {" in css
    assert "background: var(--workspace-shell-bg-alt);" in css
    assert "[data-theme=\"dark\"] .chat-left-bottom-bar {" in css
    assert "[data-theme=\"dark\"] .chat-panel-splitter {" in css
    assert "[data-theme=\"dark\"] .chat-member-pane {" in css
    assert "[data-theme=\"dark\"] .card.chat .chat-feed-item {" in css
    assert "--chat-feed-node-hue: 148;" in css
    assert "--chat-feed-node-tint-end-hue: 170;" in css
    assert "--chat-feed-node-outline-hue: 154;" in css
    assert "--chat-feed-node-gradient: linear-gradient(" in css
    assert "color-mix(in srgb, var(--workspace-shell-bg-alt) 88%, var(--ui-bg-elev) 12%)" in css
    assert "[data-theme=\"dark\"] .chat-feed-item.kind-status {" in css
    assert "rgba(44, 82, 60, 0.58)" in css
    assert "[data-theme=\"dark\"] .card.chat .chat-reaction-chip," in css
    assert "background: #173126;" in css
    assert "[data-theme=\"dark\"] .chat-node-navigator-menu," in css
    assert "background: #0d1711;" in css
    assert "[data-theme=\"dark\"] .chat-member-item {" in css
    assert "--chat-member-node-dark-sat-mult: 1.02;" in css
    assert "--chat-member-node-outline-dark-sat-mult: 1.18;" in css
    assert "calc(44% * var(--chat-member-node-dark-sat-mult, 1))" in css
    assert "calc(18% * var(--chat-member-node-dark-sat-mult, 1))" in css
    assert "color: var(--ui-text);" in css
    assert "[data-theme=\"dark\"] .chat-member-item:hover {" in css
    assert "color-mix(in srgb, var(--chat-member-node-outline) 88%, var(--ui-accent) 12%)" in css
    assert "color-mix(in srgb, var(--workspace-shell-border-strong) 68%, var(--ui-accent) 32%)" in css
    assert "[data-theme=\"dark\"] .chat-member-item.selected-node {" in css
    assert "hsl(var(--chat-member-node-outline-hue, 154) calc(30% * var(--chat-member-node-outline-dark-sat-mult, 1.1))" in css
    assert "hsl(var(--chat-member-node-hue, 145) calc(44% * var(--chat-member-node-dark-sat-mult, 1))" in css


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


def test_chat_ui_flags_nodes_with_malformed_text_payloads() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    css = build_dashboard_css(theme_css="")

    assert "function malformedTextPayloadRecord(packetEntry) {" in js
    assert "function mapMalformedTextPayloadByNode(recentPackets) {" in js
    assert "Malformed text payloads detected:" in js
    assert "Malformed Text Packets" in js
    assert ".chat-member-alert-chip {" in css
    assert "[data-theme=\"dark\"] .chat-member-alert-chip {" in css


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


def test_chat_node_list_uses_same_tint_seed_family_as_feed() -> None:
    peers_src = Path("meshdash/assets/dashboard.js.chat.state.messaging.peers.tmpl").read_text()
    feed_src = Path("meshdash/assets/dashboard.js.chat.render.feed_items.tmpl").read_text()

    assert "const tintSeedNode = (" in peers_src
    assert 'nodesById.get(normalizeNodeId(nodeId))' in peers_src
    assert 'const autoNodeHue = (typeof nodeTintHue === "function") ? nodeTintHue(nodeId, 210) : 210;' in peers_src
    assert "fallbackHue: 210," in peers_src
    assert 'const autoNodeTintHue = (typeof nodeTintHue === "function")' in feed_src
    assert '? nodeTintHue(tintNodeId, 210)' in feed_src
    assert "fallbackHue: 210," in feed_src


def test_chat_reaction_anchor_reuses_same_button_for_more_and_less_states() -> None:
    emoji_src = Path("meshdash/assets/dashboard.js.chat.state.messaging.emoji_ui.tmpl").read_text()
    bindings_src = Path("meshdash/assets/dashboard.js.chat.events.bindings.tmpl").read_text()
    feed_src = Path("meshdash/assets/dashboard.js.chat.render.feed_items.tmpl").read_text()
    layout_src = Path("meshdash/assets/dashboard.js.chat.events.core.navigation.layout.tmpl").read_text()
    css = build_dashboard_css(theme_css="")

    assert "function syncChatReactionAnchorLabels() {{" in emoji_src
    assert 'function setChatReactionPickerExpanded(expanded, focusSearch = false) {{' in emoji_src
    assert "function isChatReactionAnchorToggleSource(anchor) {{" in emoji_src
    assert "function restoreChatReactionContextTooltip() {{" in emoji_src
    assert "function suppressChatReactionContextTooltip(anchor = null) {{" in emoji_src
    assert "function parseChatReactionSummaryGroups(anchor) {{" in emoji_src
    assert "function renderChatEmojiReactionSummaryRow(anchor = null) {{" in emoji_src
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
    assert 'const owner = anchor.closest(".chat-feed-item[title], .chatlabs-message-row[title], [data-message-id][title]");' in emoji_src
    assert 'owner.removeAttribute("title");' in emoji_src
    assert 'animateChatEmojiPanelTransition(previousRect, {{' in emoji_src
    assert 'animateChatEmojiPanelClose({{' in emoji_src
    assert 'const canManageOrder = !usePreferredChoices && chatEmojiMode !== "react";' in emoji_src
    assert 'id="chat-emoji-current-reactions-shell"' in emoji_src
    assert 'target.closest(".chat-emoji-current-reaction-chip")' in emoji_src
    assert '<div class="chat-emoji-top-label">Current reactions</div>' not in emoji_src
    assert "restoreChatReactionContextTooltip();" in emoji_src
    assert "suppressChatReactionContextTooltip(chatEmojiAnchorElement);" in emoji_src
    assert 'openReactionPickerFromAnchor(summary, {{ expand: true, toggleExpanded: true }});' in bindings_src
    assert 'openReactionPickerFromAnchor(anchor, {{ expand: false }});' in bindings_src
    assert 'aria-label="${{escAttr(summaryAria)}}">' in feed_src
    assert 'title="${{escAttr(summaryTitle)}}"' not in feed_src
    assert 'title="${{escAttr(`${{reactionSummaryTitle}} • React to this message`)}}"' not in layout_src
    assert 'title="Add reaction"' not in layout_src
    assert "node.dataset.defaultReactionTitle" not in emoji_src
    assert 'node.setAttribute("title", nextText);' not in emoji_src
    assert ".chat-reaction-summary.is-empty.is-reaction-preview," in css
    assert ".chat-emoji-panel.is-closing {" in css
    assert ".chat-emoji-current-reactions-shell {" in css
    assert "gap: 0;" in css
    assert ".chat-emoji-current-reaction-chip {" in css
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
    assert "--chat-panel-collapsed-width: 160px;" in css
    assert ".workspace-shell.chat-panel-open.chat-panel-collapsed {" in css
    assert ".workspace-shell.chat-panel-collapsed .chat-users-head-title {" in css
    assert ".workspace-shell.chat-panel-collapsed .chat-users-head-view-btn," in css
    assert ".workspace-shell.chat-panel-collapsed .chat-member-meta-row," in css
    assert ".workspace-shell.chat-panel-collapsed #chat-peer-add-toggle-btn," in css
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


def test_launcher_menu_head_tracks_local_radio_identity() -> None:
    js = Path("meshdash/assets/dashboard.js.chat.events.core.identity.node_self.tmpl").read_text()

    assert 'document.getElementById("layout-view-menu-head-mark")' in js
    assert 'document.getElementById("layout-view-menu-head-brand")' in js
    assert 'document.getElementById("layout-view-menu-head-version")' in js
    assert 'document.getElementById("layout-view-menu-head-commit")' in js
    assert 'setLauncherHead("na", "Local radio", "Short name: n/a", "Connected local radio: unavailable", "Connected local radio: unavailable");' in js
    assert "setLauncherHead(launcherShort, launcherPrimary, launcherSecondary, launcherTertiary, profileTitle);" in js
