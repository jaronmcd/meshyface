import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_css import build_dashboard_css
from meshdash.html_js import build_dashboard_js
from meshdash.html_template import render_html


def test_render_html_includes_chat_node_details_notes_tab() -> None:
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

    assert 'id="chat-node-details-tab-notes"' in html
    assert 'data-drawer-tab="notes"' in html
    assert 'id="chat-node-details-panel-notes"' in html
    assert 'id="chat-node-details-notes-host"' in html


def test_render_html_uses_icon_only_close_button_for_node_details_drawer() -> None:
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

    assert 'id="chat-node-details-close-btn"' in html
    assert ">&times;</button>" in html
    assert ">Collapse</button>" not in html


def test_render_html_includes_chat_node_details_location_chat_and_links_tabs() -> None:
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

    assert 'id="chat-node-details-tab-location"' in html
    assert 'data-drawer-tab="location"' in html
    assert 'id="chat-node-details-panel-location"' in html
    assert 'id="chat-node-details-location-host"' in html
    assert 'id="chat-node-details-tab-chat"' in html
    assert 'data-drawer-tab="chat"' in html
    assert 'id="chat-node-details-panel-chat"' in html
    assert 'id="chat-node-details-chat-host"' in html
    assert 'id="chat-node-details-tab-links"' in html
    assert 'data-drawer-tab="links"' in html
    assert 'id="chat-node-details-panel-links"' in html
    assert 'id="chat-node-details-links-host"' in html
    assert 'id="chat-node-details-tab-messages"' in html
    assert 'data-drawer-tab="messages"' in html
    assert 'id="chat-node-details-panel-messages"' in html
    assert 'id="chat-node-details-messages-host"' in html
    assert 'id="chat-node-details-pin-btn"' in html


def test_render_html_places_messages_before_details_and_notes_in_drawer_tabs() -> None:
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

    head_index = html.index('class="chat-node-details-head"')
    tabs_index = html.index('class="chat-node-details-tabs"')
    tag_index = html.index('id="chat-node-details-tab-tag"')
    details_index = html.index('id="chat-node-details-tab-details"')
    telemetry_index = html.index('id="chat-node-details-tab-telemetry"')
    history_index = html.index('id="chat-node-details-tab-history"')
    location_index = html.index('id="chat-node-details-tab-location"')
    chat_index = html.index('id="chat-node-details-tab-chat"')
    links_index = html.index('id="chat-node-details-tab-links"')
    notes_index = html.index('id="chat-node-details-tab-notes"')
    messages_index = html.index('id="chat-node-details-tab-messages"')

    assert head_index < tag_index < tabs_index
    assert messages_index < details_index < telemetry_index < history_index < location_index < chat_index < links_index < notes_index


def test_render_html_places_tag_title_pin_and_mute_actions_in_drawer_header() -> None:
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

    head_index = html.index('class="chat-node-details-head"')
    tag_index = html.index('id="chat-node-details-tab-tag"')
    reset_index = html.index('id="chat-node-details-reset-btn"')
    title_index = html.index('id="chat-node-details-title"')
    pin_index = html.index('id="chat-node-details-pin-btn"')
    mute_index = html.index('id="chat-node-details-mute-btn"')
    tabs_index = html.index('class="chat-node-details-tabs"')

    assert 'id="chat-node-details-dm-btn"' not in html
    assert head_index < tag_index < reset_index < title_index < pin_index < mute_index < tabs_index


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
    assert 'const resetBtn = document.getElementById("chat-node-details-reset-btn");' in js
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
    assert 'iconChip.className = "chat-node-details-icon-chip";' in js
    assert 'iconChip.innerHTML = `<span class="chat-node-details-icon-glyph" aria-hidden="true">${escAttr(effectiveEmoji)}</span>`;' in js
    assert 'let chatEmojiTagTargetInput = null;' in js
    assert 'chatEmojiMode === "tag" && chatEmojiTagTargetInput instanceof HTMLInputElement' in js
    assert 'chatEmojiMode === "tag" && tagTargetInput instanceof HTMLInputElement' in js
    assert 'if (target.closest("#chat-node-details-icon-btn")) return;' in js
    assert 'if (target.closest("#favorite-menu-tag-emoji-input")) return;' in js
    assert 'if (target.closest("#favorite-menu-node-emoji-input")) return;' in js
    assert 'if (target.closest("#chat-node-details-head-icon-input")) return;' in js
    assert 'openChatEmojiPanel("tag", null, emojiInput);' in js
    assert 'openChatEmojiPanel("tag", null, iconBtn, false, iconInput);' in js
    assert 'const hasResettableVisualState = hasTag || hasNodeEmojiOverride;' in js
    assert 'resetBtn.hidden = !hasResettableVisualState;' in js
    assert 'clearNodeTagAndEmojiForNode(nodeId, { persist: true });' in js
    assert 'target.closest("#settings-node-tag-emoji-input")' in js
    assert 'openChatEmojiPanel("tag", null, emojiInput);' in js


def test_dashboard_html_places_messages_tab_first_in_node_drawer() -> None:
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

    assert html.index('id="chat-node-details-tab-messages"') < html.index('id="chat-node-details-tab-details"')


def test_dashboard_js_avoids_rebuilding_saved_node_details_on_unchanged_polls() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'noteInput.dataset.noteEditorBound === "1"' in js
    assert 'detailsMarkupChanged = setElementHtmlIfChanged(host, nextDetailsShellHtml, "saved-node-details-shell");' in js
    assert 'detailsMarkupChanged = setElementHtmlIfChanged(sectionsHost, nextSectionsHtml, "saved-node-sections") || detailsMarkupChanged;' in js
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

    assert 'function savedDetailHtmlValue(html, text = "", fallback = "n/a") {' in js
    assert 'function savedDetailValueMarkup(value, fallback = "n/a") {' in js
    assert 'function savedDetailMapCoordLink(nodeId, lat, lon, title = "Focus GPS position on map") {' in js
    assert 'class="saved-node-inline-link saved-node-coordinate-link"' in js
    assert 'function focusSavedNodeCoordinateOnMap(nodeId, latRaw, lonRaw) {' in js
    assert 'bindSavedNodeCoordinateLinks(locationHost);' in js
    assert 'const topPeerId = normalizeNodeId((linkStats && linkStats.topPeer) || "");' in js
    assert 'const topPeerLabel = savedDetailText(topPeerName || topPeerId, topPeerId || "n/a");' in js
    assert 'class="saved-node-inline-link"' in js
    assert 'bindSavedNodeDetailLinkButtons(host);' in js
    assert 'bindSavedNodeDetailLinkButtons(linksHost);' in js
    assert 'selectNode(nodeId, true, false);' in js
    assert ".saved-node-inline-link {" in css
    assert ".saved-node-inline-link:hover {" in css
    assert "[data-theme=\"dark\"] .saved-node-inline-link:hover {" in css
