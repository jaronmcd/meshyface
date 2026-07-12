import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_css import build_dashboard_css
from meshdash.html_js import build_dashboard_js
from meshdash.html_template import render_html


def test_dashboard_js_lazily_mounts_chat_node_details_notes_tab() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "function ensureChatNodeDetailsDrawer() {" in js
    assert 'id="chat-node-details-tab-notes"' in js
    assert 'data-drawer-tab="notes"' in js
    assert 'id="chat-node-details-panel-notes"' in js
    assert 'id="chat-node-details-notes-host"' in js


def test_render_html_defers_chat_node_details_drawer_until_needed() -> None:
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
    initial_dom_html = html.split("<!-- mesh-dashboard-app:start -->", 1)[0]

    assert 'id="chat-node-details-inline-host"' in initial_dom_html
    assert 'id="chat-node-details-drawer"' not in initial_dom_html
    assert 'id="chat-node-details-tab-notes"' not in initial_dom_html


def test_dashboard_js_omits_redundant_close_button_for_node_details_drawer() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'id="chat-node-details-close-btn"' not in js
    assert 'class="chat-node-details-close-btn"' not in js
    assert 'const closeBtn = document.getElementById("chat-node-details-close-btn");' not in js
    assert ".chat-node-details-close-btn {" not in build_dashboard_css(theme_css="")


def test_dashboard_js_includes_chat_node_details_location_chat_and_links_tabs() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'id="chat-node-details-tab-location"' in js
    assert 'data-drawer-tab="location"' in js
    assert 'id="chat-node-details-panel-location"' in js
    assert 'id="chat-node-details-location-host"' in js
    assert 'id="chat-node-details-tab-chat"' in js
    assert 'data-drawer-tab="chat"' in js
    assert 'id="chat-node-details-panel-chat"' in js
    assert 'id="chat-node-details-chat-host"' in js
    assert 'id="chat-node-details-tab-links"' in js
    assert 'data-drawer-tab="links"' in js
    assert 'id="chat-node-details-panel-links"' in js
    assert 'id="chat-node-details-links-host"' in js
    assert 'id="chat-node-details-tab-messages"' in js
    assert 'data-drawer-tab="messages"' in js
    assert 'id="chat-node-details-panel-messages"' in js
    assert 'id="chat-node-details-messages-host"' in js
    assert 'id="chat-node-details-pin-btn"' in js
    assert 'id="chat-node-details-theme-try-btn"' in js
    assert 'id="chat-node-details-theme-save-btn"' in js


def test_dashboard_js_places_messages_before_details_and_notes_in_drawer_tabs() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    tabs_index = js.index('class="chat-node-details-tabs"')
    tag_index = js.index('id="chat-node-details-tab-tag"')
    details_index = js.index('id="chat-node-details-tab-details"')
    telemetry_index = js.index('id="chat-node-details-tab-telemetry"')
    history_index = js.index('id="chat-node-details-tab-history"')
    location_index = js.index('id="chat-node-details-tab-location"')
    chat_index = js.index('id="chat-node-details-tab-chat"')
    links_index = js.index('id="chat-node-details-tab-links"')
    notes_index = js.index('id="chat-node-details-tab-notes"')
    messages_index = js.index('id="chat-node-details-tab-messages"')

    assert (
        tabs_index
        < messages_index
        < details_index
        < telemetry_index
        < history_index
        < location_index
        < chat_index
        < links_index
        < notes_index
        < tag_index
    )


def test_dashboard_js_centers_theme_actions_in_existing_drawer_footer() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    head_index = js.index('class="chat-node-details-head"')
    tag_index = js.index('id="chat-node-details-tab-tag"')
    status_index = js.index('id="chat-node-details-status-chip"')
    reset_index = js.index('id="chat-node-details-reset-btn"')
    title_index = js.index('id="chat-node-details-title"')
    theme_try_index = js.index('id="chat-node-details-theme-try-btn"')
    theme_save_index = js.index('id="chat-node-details-theme-save-btn"')
    pin_index = js.index('id="chat-node-details-pin-btn"')
    mute_index = js.index('id="chat-node-details-mute-btn"')
    tabs_index = js.index('class="chat-node-details-tabs"')
    footer_index = js.index('class="chat-node-details-footer-actions"')
    head_markup = js[head_index:tabs_index]
    footer_markup = js[footer_index:]

    assert 'id="chat-node-details-dm-btn"' not in js
    assert 'id="chat-node-details-tab-tag"' not in head_markup
    assert 'id="chat-node-details-pin-btn"' not in head_markup
    assert 'id="chat-node-details-mute-btn"' not in head_markup
    assert 'id="chat-node-details-theme-try-btn"' not in head_markup
    assert 'id="chat-node-details-theme-save-btn"' not in head_markup
    assert 'id="chat-node-details-tab-tag"' in footer_markup
    assert 'id="chat-node-details-pin-btn"' in footer_markup
    assert 'id="chat-node-details-mute-btn"' in footer_markup
    assert 'class="chat-node-details-footer-theme-actions"' in footer_markup
    assert 'id="chat-node-details-theme-try-btn"' in footer_markup
    assert 'id="chat-node-details-theme-save-btn"' in footer_markup
    assert (
        head_index
        < status_index
        < reset_index
        < title_index
        < tabs_index
        < footer_index
        < tag_index
        < theme_try_index
        < theme_save_index
        < pin_index
        < mute_index
    )


def test_entire_node_details_title_strip_is_an_inviting_collapse_control() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    css = build_dashboard_css(theme_css="")

    assert (
        '<button id="chat-node-details-title" class="chat-node-details-title" '
        'type="button" title="Collapse node details" aria-label="Collapse node details">'
    ) in js
    assert (
        '<div class="chat-node-details-head-main" tabindex="0" '
        'title="Collapse node details" aria-label="Collapse node details">'
    ) in js
    assert 'const headMain = document.querySelector("#chat-node-details-drawer .chat-node-details-head-main");' in js
    assert 'headMain.addEventListener("click", (event) => {' in js
    head_binding = js.split('headMain.addEventListener("click", (event) => {', 1)[1].split("}, true);", 1)[0]
    assert "setChatNodeDetailsDrawerExpanded(false" in js
    assert "event.preventDefault();" in head_binding
    assert "event.stopPropagation();" in head_binding
    assert 'closest(".chat-node-details-reset-btn")' not in head_binding
    assert 'headMain.addEventListener("keydown", (event) => {' in js
    head_style = css.rsplit(".chat-node-details-head-main {", 1)[1].split("}", 1)[0]
    head_close_hint = css.split(".chat-node-details-head-main::after {", 1)[1].split("}", 1)[0]
    assert "cursor: pointer;" in head_style
    assert "transition: background-color 120ms ease" in head_style
    assert 'content: "×";' in head_close_hint
    assert "right: 8px;" in head_close_hint
    assert "opacity: 0.38;" in head_close_hint
    assert "pointer-events: none;" in head_close_hint
    assert "#chat-node-details-inline-host > .chat-node-details-drawer.profiled-node .chat-node-details-head::after {" in css
    assert 'content: var(--node-profile-ghost-text, "");' in css
    assert ".chat-node-details-promoted-host .chat-node-details-drawer.profiled-node .chat-node-details-head::after {" not in css
    assert ".chat-node-details-head-main:hover {" in css
    assert ".chat-node-details-head-main:hover::after," in css
    assert ".chat-node-details-head-main:focus-visible," in css


def test_render_html_includes_promoted_node_details_host() -> None:
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
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'id="chat-node-details-inline-host"' in html
    assert 'id="chat-node-details-drawer"' not in html
    assert 'id="chat-node-details-promote-btn"' in js
    assert 'class="chat-node-details-action-btn chat-node-details-promote-btn"' in js
    assert 'id="chat-node-details-promoted-shell"' in html
    assert 'id="chat-node-details-promoted-host"' in html
    assert 'id="chat-node-details-close-btn"' not in js
    assert html.index('class="workspace-main"') < html.index('id="chat-node-details-promoted-shell"')


def test_dashboard_js_routes_drawer_tabs_into_their_panels() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'if (clean === "location") return "location";' in js
    assert 'if (clean === "chat") return "chat";' in js
    assert 'if (clean === "links") return "links";' in js
    assert 'if (clean === "messages") return "messages";' in js
    assert 'const locationTabBtn = document.getElementById("chat-node-details-tab-location");' in js
    assert 'const chatTabBtn = document.getElementById("chat-node-details-tab-chat");' in js
    assert 'const linksTabBtn = document.getElementById("chat-node-details-tab-links");' in js
    assert 'const messagesTabBtn = document.getElementById("chat-node-details-tab-messages");' in js
    assert 'const locationPanel = document.getElementById("chat-node-details-panel-location");' in js
    assert 'const chatPanel = document.getElementById("chat-node-details-panel-chat");' in js
    assert 'const linksPanel = document.getElementById("chat-node-details-panel-links");' in js
    assert 'const messagesPanel = document.getElementById("chat-node-details-panel-messages");' in js
    assert 'const locationHost = document.getElementById("chat-node-details-location-host");' in js
    assert 'const chatHost = document.getElementById("chat-node-details-chat-host");' in js
    assert 'const linksHost = document.getElementById("chat-node-details-links-host");' in js
    assert 'const messagesHost = document.getElementById("chat-node-details-messages-host");' in js
    assert 'if (clean === "notes") return "notes";' in js
    assert 'const notesTabBtn = document.getElementById("chat-node-details-tab-notes");' in js
    assert 'const notesPanel = document.getElementById("chat-node-details-panel-notes");' in js
    assert 'const notesHost = document.getElementById("chat-node-details-notes-host");' in js
    assert 'const pinBtn = document.getElementById("chat-node-details-pin-btn");' in js
    assert 'const themeTryBtn = document.getElementById("chat-node-details-theme-try-btn");' in js
    assert 'const themeSaveBtn = document.getElementById("chat-node-details-theme-save-btn");' in js
    assert 'const resetBtn = document.getElementById("chat-node-details-reset-btn");' in js
    assert "const themeForDrawerButton = (button) => {" in js
    assert 'themeTryBtn.textContent = dashboardPreviewUndoActive ? "Undo look" : "Try look";' in js
    assert "hasMeshyfaceProfileThemeDashboardPreviewUndo()" in js
    assert "void tryMeshyfaceProfileThemeOnDashboard(null, themeTryBtn);" in js
    assert "void tryMeshyfaceProfileThemeOnDashboard(theme, themeTryBtn);" in js
    assert "void saveMeshyfaceProfileThemeAsDashboardTheme(theme, suggested, themeSaveBtn);" in js
    assert 'const renderNotesInDrawer = (' in js
    assert 'const renderLocationInDrawer = (' in js
    assert 'const renderChatInDrawer = (' in js
    assert 'const renderLinksInDrawer = (' in js
    assert 'const nextLocationHtml = renderLocationInDrawer ? locationSection : "";' in js
    assert 'const nextChatHtml = renderChatInDrawer ? chatSection : "";' in js
    assert 'const nextLinksHtml = renderLinksInDrawer ? linksSection : "";' in js
    assert 'const nextNotesHtml = renderNotesInDrawer ? notesSection : "";' in js
    assert 'setDrawerElementHtmlIfChanged(messagesHost, "", "messages");' in js
    assert 'syncDrawerPanelHiddenState(messagesPanel, activeTab === "messages");' in js
    assert 'setChatNodeDetailsDrawerTab("messages"' in js
    assert 'const drawerMessagesHost = document.getElementById("chat-node-details-messages-host");' in js
    assert 'mode: "drawer"' in js
    assert "const showPopoutAction = !!opts.showPopoutAction;" in js
    assert 'data-peer-dm-action="popout"' in js
    assert 'const popoutActionLabel = popoutActiveForPeer ? "Pop in" : "Pop out";' in js
    assert 'const popoutBtn = host.querySelector(\'[data-peer-dm-action="popout"]\');' in js
    assert 'showPopoutAction: true,' in js
    assert "const unreadDirectFocusKeysByPeer = new Map();" in js
    assert "let unreadThreadNoticeAckQueued = false;" in js
    assert "const acknowledgeUnreadThreadNotices = () => {" in js
    assert 'acknowledgeChatChangeNoticesByFocusKey(focusKey, "direct")' in js
    assert "const scheduleBodyScroll = (bodyEl, focusMessageKeysRaw = null) => {" in js
    assert 'const acknowledgeFocusedNotice = (focusKey) => {' in js
    assert 'acknowledgeChatChangeNoticesByFocusKey(matchedFocusKey, "direct")' in js
    assert 'const unreadFocusKeys = Array.isArray(unreadDirectFocusKeysByPeer.get(peerId))' in js
    assert 'const messageKey = String(chatMessageKey(msg) || "").trim();' in js
    assert 'data-message-key="${escAttr(messageKey)}"' in js
    assert 'input.addEventListener("focus", acknowledgeUnreadThreadNotices);' in js
    assert 'input.addEventListener("click", acknowledgeUnreadThreadNotices);' in js
    assert "window.requestAnimationFrame(() => {" in js
    assert "scheduleBodyScroll(bodyEl, unreadFocusKeys);" in js
    assert 'pinBtn.classList.toggle("active", active);' in js
    assert 'const nodeTagEmojiStorageKey = "meshDashboardNodeTagEmojiV1";' in js
    assert 'function normalizeNodeTagEmoji(value, fallback = "") {' in js
    assert 'const emoji = normalizeNodeTagEmoji(base.emoji ?? base.icon ?? base.badge, fallback.emoji);' in js
    assert 'function nodeEmojiOverrideForNode(nodeId) {' in js
    assert 'function localNameEmojiForNode(nodeId, node = null) {' in js
    assert 'function localVisualEmojiForNode(nodeId, node = null) {' in js
    assert 'return localNameEmojiForNode(nodeId, node);' in js
    assert 'function localBadgeEmojiForNode(nodeId)' not in js
    assert 'function nodeVisualEmojiForNode(nodeId, tagEntry = null, node = null) {' in js
    assert 'function saveNodeEmojiOverride(nodeId, rawEmoji, options = null) {' in js
    assert 'function clearNodeTagAndEmojiForNode(nodeId, options = null) {' in js
    assert 'emoji: normalizeNodeTagEmoji(preset.emoji, ""),' in js
    assert 'id="favorite-menu-tag-emoji-input"' in js
    assert 'id="favorite-menu-node-emoji-input"' in js
    assert 'id="settings-node-tag-emoji-input"' in js
    assert 'const iconBtn = document.getElementById("chat-node-details-icon-btn");' in js
    assert 'const iconChip = document.getElementById("chat-node-details-icon-chip");' in js
    assert 'const iconInput = document.getElementById("chat-node-details-head-icon-input");' in js
    assert 'const statusChip = document.getElementById("chat-node-details-status-chip");' in js
    assert 'iconChip.className = "chat-node-details-icon-chip";' in js
    assert 'iconChip.innerHTML = `<span class="chat-node-details-icon-glyph" aria-hidden="true">${escAttr(effectiveEmoji)}</span>`;' in js
    assert 'let chatEmojiTagTargetInput = null;' in js
    assert 'let chatEmojiTextTargetInput = null;' in js
    assert 'chatEmojiMode === "tag" && chatEmojiTagTargetInput instanceof HTMLInputElement' in js
    assert 'chatEmojiMode === "input" && chatEmojiTextTargetInput instanceof HTMLInputElement' in js
    assert 'chatEmojiMode === "tag" && tagTargetInput instanceof HTMLInputElement' in js
    assert 'if (target.closest("#chat-node-details-icon-btn")) return;' in js
    assert 'if (target.closest("[data-chat-emoji-target]")) return;' in js
    assert 'if (target.closest("#favorite-menu-tag-emoji-input")) return;' in js
    assert 'if (target.closest("#favorite-menu-node-emoji-input")) return;' in js
    assert 'if (target.closest("#chat-node-details-head-icon-input")) return;' in js
    assert 'openChatEmojiPanel("tag", null, emojiInput);' in js
    assert 'openChatEmojiPanel("tag", null, iconBtn, false, iconInput);' in js
    assert 'const manualTagEntry = (typeof manualNodeTagEntryForNode === "function")' in js
    assert 'const autoNewStatusEntry = (typeof autoNodeTagEntryForNode === "function")' in js
    assert 'const tagEntry = manualTagEntry;' in js
    assert 'const hasResettableVisualState = !!manualTagEntry || hasNodeEmojiOverride;' in js
    assert 'resetBtn.hidden = !hasResettableVisualState;' in js
    assert 'setDrawerElementTextIfChanged(statusChip, statusLabel);' in js
    assert 'const statusTitle = "New node: first seen in the last 24 hours";' in js
    assert 'clearNodeTagAndEmojiForNode(nodeId, { persist: true });' in js
    assert 'target.closest("#settings-node-tag-emoji-input")' in js
    assert 'openChatEmojiPanel("tag", null, emojiInput);' in js


def test_dashboard_js_promotes_node_details_without_duplicate_drawer_state() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "let chatNodeDetailsPromoted = false;" in js
    assert "function syncChatNodeDetailsDrawerPlacement(drawer, promotedVisible) {" in js
    assert "function syncChatNodeDetailsInlineDockState(activeList = null) {" in js
    assert "function resetChatNodeDetailsInlineHost(inlineHost) {" in js
    assert 'inlineHost.closest(".chat-member-list, .chat-member-pinned-list")' in js
    assert "let forceRosterSectionRender = false;" in js
    assert "forceRosterSectionRender = true;" in js
    assert "!forceRosterSectionRender && (typeof pinnedList.__meshLastInnerHtml_chat_room_pinned_list === \"string\")" in js
    assert "!forceRosterSectionRender && (typeof roomList.__meshLastInnerHtml_chat_room_list === \"string\")" in js
    assert "resetChatNodeDetailsInlineHost(inlineHost);" in js
    assert "syncChatNodeDetailsDrawer(safeState, {" in js
    assert 'const inlineHost = document.getElementById("chat-node-details-inline-host");' in js
    assert 'const promotedShell = document.getElementById("chat-node-details-promoted-shell");' in js
    assert 'const promotedHost = document.getElementById("chat-node-details-promoted-host");' in js
    assert 'const roomList = document.getElementById("chat-room-list");' in js
    assert "section.insertBefore(inlineHost, roomList);" in js
    assert 'inlineHost.dataset.dock = "shared";' in js
    assert "delete inlineHost.dataset.dock;" in js
    assert 'listEl.classList.toggle("has-node-details-inline", listEl === activeListEl);' in js
    assert "target.appendChild(drawer);" in js
    assert 'drawer.dataset.promoted = usePromoted ? "true" : "false";' in js
    assert 'workspaceShell.classList.toggle("has-promoted-node-details", usePromoted);' in js
    assert "const requestedPromoted = expanded && !!chatNodeDetailsPromoted;" in js
    assert "const shouldMountDrawer = expanded && (!chatPanelCollapsed || requestedPromoted);" in js
    assert "drawer = ensureChatNodeDetailsDrawer();" in js
    assert "let promotedVisible = requestedPromoted;" in js
    assert "promotedVisible = syncChatNodeDetailsDrawerPlacement(drawer, promotedVisible);" in js
    assert "const inlineVisible = visibleExpanded && !promotedVisible;" in js
    assert 'usersSection.classList.toggle("has-node-details", inlineVisible);' in js
    assert "promoteBtn.hidden = false;" in js
    assert "promoteBtn.disabled = false;" in js
    assert 'promoteBtn.classList.toggle("active", promotedVisible);' in js
    assert 'promoteBtn.setAttribute("aria-pressed", promotedVisible ? "true" : "false");' in js
    assert "? `Collapse ${titleName} details back into the node list`" in js
    assert 'promotedVisible ? "Collapse" : "Expand"' in js
    assert '"Dock"' not in js
    assert "Return ${titleName} details to the left node list" not in js
    assert "function setChatNodeDetailsPromoted(promoted, options = null) {" in js
    assert "setChatNodeDetailsPromoted(!chatNodeDetailsPromoted, {" in js
    assert "chatNodeDetailsPromoted = false;" in js
    assert 'aria-label="${escAttr(memberTitle)}"' in js
    assert 'title="${escAttr(memberTitle)}"' not in js


def test_drawer_returns_shared_history_panel_before_teardown() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    close_start = js.index(
        'const detailsHost = document.getElementById("chat-node-details-content-host");'
    )
    close_end = js.index("drawer.remove();", close_start)
    close_block = js[close_start:close_end]

    assert close_block.index("syncNodeHistoryDock();") < close_block.index(
        'setDrawerElementHtmlIfChanged(historyHost, "", "history");'
    )


def test_dashboard_css_promoted_node_details_overlays_workspace() -> None:
    css = build_dashboard_css(theme_css="")

    assert ".chat-node-details-promoted-shell {" in css
    assert "position: absolute;" in css
    assert "padding: 8px;" in css
    assert "justify-content: center;" in css
    promoted_shell_section = css.split(".chat-node-details-promoted-shell {", 1)[1].split("}", 1)[0]
    assert "z-index: 2000;" in promoted_shell_section
    assert "var(--theme-background-gradient-start, #eff2f7)" in promoted_shell_section
    assert "var(--theme-background-gradient-end, #eff2f7)" in promoted_shell_section
    assert "isolation: isolate;" in promoted_shell_section
    assert "transform: translateZ(0);" in promoted_shell_section
    assert ".workspace-shell.has-promoted-node-details .workspace-main > .layout {" in css
    assert "pointer-events: none;" in css
    assert ".chat-node-details-promoted-host {" in css
    promoted_host_section = css.split(".chat-node-details-promoted-host {", 1)[1].split("}", 1)[0]
    assert "width: 100%;" in promoted_host_section
    assert "max-width: none;" in promoted_host_section
    assert "min-width: 0;" in promoted_host_section
    assert "position: relative;" in promoted_host_section
    assert "z-index: 1;" in promoted_host_section
    assert "overflow: hidden;" in promoted_host_section
    assert ".chat-node-details-promoted-host .chat-node-details-head-main {" in css
    assert ".chat-node-details-promoted-host .chat-node-details-head-actions {" in css
    promoted_actions_section = css.split(
        ".chat-node-details-promoted-host .chat-node-details-head-actions {", 1
    )[1].split("}", 1)[0]
    assert "display: inline-flex;" in promoted_actions_section
    assert ".chat-node-details-promoted-host .chat-node-details-head-actions > :not(.chat-node-details-promote-btn) {" in css
    assert ".chat-node-details-promoted-host .chat-node-details-tabs {" in css
    assert "padding-right: 38px;" in css
    assert ".chat-node-details-promoted-host .node-details.profiled-node::after," not in css
    assert "var(--workspace-shell-bg, var(--ui-panel))" in promoted_host_section
    assert ".chat-node-details-promoted-host .chat-node-details-drawer {" in css
    assert "height: 100%;" in css
    assert ".chat-node-details-head {" in css
    head_section = css.split("\n    .chat-node-details-head {", 1)[1].split("}", 1)[0]
    assert "grid-template-columns: minmax(0, 1fr) auto;" in head_section
    assert ".chat-node-details-head-main {" in css
    head_main_section = css.rsplit(".chat-node-details-head-main {", 1)[1].split("}", 1)[0]
    assert "width: 100%;" in head_main_section
    assert "grid-template-columns: auto auto auto minmax(0, 1fr);" in head_main_section
    assert "justify-self: stretch;" in head_main_section
    assert ".chat-node-details-footer-actions {" in css
    footer_section = css.split(".chat-node-details-footer-actions {", 1)[1].split("}", 1)[0]
    assert "flex: 0 0 auto;" in footer_section
    assert "display: grid;" in footer_section
    assert "grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);" in footer_section
    assert "border-top: 1px solid" in footer_section
    assert "background: var(--workspace-shell-bg-alt" in footer_section
    theme_action_section = css.split(".chat-node-details-footer-theme-actions {", 1)[1].split("}", 1)[0]
    assert "justify-content: center;" in theme_action_section
    assert ".chat-node-details-promoted-host .chat-node-details-tag-host {" in css
    assert '.chat-left-section.chat-users-section > .chat-node-details-inline-host[data-dock="shared"] {' in css
    assert "padding: 6px 5px 6px 5px;" in css
    assert '.chat-left-section.chat-users-section > .chat-node-details-inline-host[data-dock="shared"] .chat-node-details-drawer {' in css
    shared_drawer_section = css.split(
        '.chat-left-section.chat-users-section > .chat-node-details-inline-host[data-dock="shared"] .chat-node-details-drawer {',
        1,
    )[1].split("}", 1)[0]
    assert "width: 100%;" in shared_drawer_section
    assert "border-top-left-radius: 8px;" in shared_drawer_section
    assert "border-top-right-radius: 8px;" in shared_drawer_section
    assert ".chat-node-details-status-chip {" in css
    assert ".chat-member-item.auto-new-node:not(.tagged-node) {" in css
    assert '.chat-left-section.chat-users-section > .chat-node-details-inline-host[data-dock="priority"] {' not in css
    assert ".chat-member-pinned-shell.has-node-details-inline {" not in css
    assert ".chat-left-section.chat-users-section.has-node-details .chat-member-pinned-shell," in css
    assert ".chat-left-section.chat-users-section.has-node-details .chat-member-list {" in css
    assert "display: none !important;" in css
    assert ".chat-left-section.chat-users-section.has-node-details .chat-node-details-inline-host {" in css
    inline_host_section = css.split(
        ".chat-left-section.chat-users-section.has-node-details .chat-node-details-inline-host {", 1
    )[1].split("}", 1)[0]
    assert "flex: 1 1 auto;" in inline_host_section
    assert "height: 100%;" in inline_host_section
    drawer_section = css.split(
        ".chat-left-section.chat-users-section.has-node-details .chat-node-details-drawer {", 1
    )[1].split("}", 1)[0]
    assert "flex: 1 1 auto;" in drawer_section
    assert "height: 100%;" in drawer_section
    assert "max-height: none;" in drawer_section
    assert ".workspace-shell.chat-panel-collapsed .chat-left-panel .chat-node-details-drawer {" in css
    assert "[data-theme=\"dark\"] .chat-node-details-promote-btn.active {" in css


def test_dashboard_js_places_messages_tab_first_in_node_drawer() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert js.index('id="chat-node-details-tab-messages"') < js.index('id="chat-node-details-tab-details"')


def test_dashboard_js_avoids_rebuilding_node_details_on_unchanged_polls() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'noteInput.dataset.noteEditorBound === "1"' in js
    assert 'detailsMarkupChanged = setElementHtmlIfChanged(host, nextDetailsShellHtml, "node-details-shell");' in js
    assert 'detailsMarkupChanged = setElementHtmlIfChanged(sectionsHost, nextSectionsHtml, "node-details-sections") || detailsMarkupChanged;' in js
    assert 'const notesMarkupChanged = setElementHtmlIfChanged(notesHost, nextNotesHtml, "chat-node-details-notes");' in js
    assert 'if (detailsMarkupChanged || notesMarkupChanged) {' in js
    assert 'if ((detailsMarkupChanged || notesMarkupChanged) && previousNodeId === nodeId) {' in js


def test_dashboard_js_clears_node_details_drawer_when_hidden() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    hidden_start = js.index("if (!visibleExpanded) {")
    hidden_end = js.index("return;", hidden_start)
    hidden_block = js[hidden_start:hidden_end]

    assert 'setDrawerElementTextIfChanged(titleEl, "Node Details");' in hidden_block
    assert 'setDrawerElementTextIfChanged(tagTabLabel, "+tag");' in hidden_block
    assert 'setDrawerElementHtmlIfChanged(detailsHost, "", "details");' in hidden_block
    assert 'setDrawerElementHtmlIfChanged(historyHost, "", "history");' in hidden_block
    assert 'setDrawerElementHtmlIfChanged(tagHost, "", "tag");' in hidden_block


def test_dashboard_js_refreshes_node_tag_drawer_when_tag_state_changes() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    drawer_start = js.index("function syncChatNodeDetailsDrawer(")
    signature_start = js.index("const tagEditorSignature = JSON.stringify({", drawer_start)
    signature_end = js.index("bindFavoriteMenuTagEditorControls(selectedId);", signature_start)
    signature_block = js[signature_start:signature_end]

    assert "manualPresetId:" in signature_block
    assert "effectivePresetId:" in signature_block
    assert "activePresetId:" in signature_block
    assert "currentPreset:" in signature_block
    assert "nodeEmoji:" in signature_block
    assert "tagHost.dataset.tagEditorSignature !== tagEditorSignature" in signature_block
    assert "tagHost.dataset.tagEditorSignature = tagEditorSignature;" in signature_block

    toggle_start = js.index("function toggleFavoriteNode(")
    toggle_end = js.index("function toggleMutedNode(", toggle_start)
    toggle_block = js[toggle_start:toggle_end]

    assert "syncChatNodeDetailsDrawer(latestState, {" in toggle_block
    assert "fetchHistory: false" in toggle_block


def test_dashboard_js_allows_typing_custom_tag_from_default_drawer_preset() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    editor_start = js.index("function favoriteMenuTagEditorHtml(")
    editor_end = js.index("function bindFavoriteMenuTagEditorControls(", editor_start)
    editor_block = js[editor_start:editor_end]

    assert "const selectedPresetLocked = favoriteMenuTagPresetFieldsLocked(selectedPresetId);" in editor_block
    assert "function favoriteMenuTagPresetFieldsLocked(presetId) {" in editor_block
    assert "? isMeshtasticFavoritePresetId(presetId)" in editor_block
    assert 'isNodeTagPresetIdLocked(selectedPresetId)' not in editor_block

    bind_start = js.index("function bindFavoriteMenuTagEditorControls(")
    bind_end = js.index("function renderStarredNodeSelect(", bind_start)
    bind_block = js[bind_start:bind_end]

    assert "const locked = favoriteMenuTagPresetFieldsLocked(presetId);" in bind_block
    assert "const effectivePreferredId = (" in bind_block
    assert "&& isNodeTagPresetIdLocked(preferredPresetId)" in bind_block
    assert "preferredId: effectivePreferredId," in bind_block


def test_dashboard_js_renders_top_peer_as_clickable_node_link() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    css = build_dashboard_css(theme_css="")

    assert 'function nodeDetailsHtmlValue(html, text = "", fallback = "n/a") {' in js
    assert 'function nodeDetailsValueMarkup(value, fallback = "n/a") {' in js
    assert 'function nodeDetailsMapCoordLink(nodeId, lat, lon, title = "Focus GPS position on map") {' in js
    assert 'class="node-details-inline-link node-details-coordinate-link"' in js
    assert 'function focusNodeDetailsCoordinateOnMap(nodeId, latRaw, lonRaw) {' in js
    assert 'bindNodeDetailsCoordinateLinks(locationHost);' in js
    assert 'const topPeerId = normalizeNodeId((linkStats && linkStats.topPeer) || "");' in js
    assert 'const topPeerLabel = nodeDetailsText(topPeerName || topPeerId, topPeerId || "n/a");' in js
    assert 'class="node-details-inline-link"' in js
    assert 'bindNodeDetailsLinkButtons(host);' in js
    assert 'bindNodeDetailsLinkButtons(linksHost);' in js
    assert 'selectNode(nodeId, true, false);' in js
    assert ".node-details-inline-link {" in css
    assert ".node-details-inline-link:hover {" in css
    assert "[data-theme=\"dark\"] .node-details-inline-link:hover {" in css


def test_selected_node_inspector_uses_effective_profile_appearance() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    css = build_dashboard_css(theme_css="")

    assert "function applyNodeAppearanceElementStyle(target, appearanceEntry)" in js
    assert "function clearNodeAppearanceElementStyle(target)" in js
    assert 'host.classList.toggle("has-node-appearance", hasNodeAppearance);' in js
    assert 'host.classList.toggle("profiled-node", profileAppearance);' in js
    assert "applyNodeAppearanceElementStyle(host, appearanceEntry);" in js
    assert 'drawer.classList.toggle("has-node-appearance", hasNodeAppearance);' in js
    assert 'drawer.classList.toggle("profiled-node", profileAppearance);' in js
    assert "applyNodeAppearanceElementStyle(drawer, appearanceEntry);" in js
    assert 'drawer.classList.remove("has-node-appearance", "profiled-node");' in js
    assert ".chat-node-details-drawer.has-node-appearance .chat-node-details-head {" in css
    assert ".chat-node-details-drawer.has-node-appearance .chat-node-details-icon-btn {" in css
    assert ".node-details.has-node-appearance {" in css
    assert ".node-details.has-node-appearance .node-details-section:first-child {" in css
    assert "\n    .node-details.profiled-node {\n" not in css
    assert "\n    .node-details.profiled-node::after,\n" not in css
    assert "\n    .node-details.profiled-node .node-details-section:first-child::after {\n" not in css
