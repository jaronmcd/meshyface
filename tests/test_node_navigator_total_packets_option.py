import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_css import build_dashboard_css
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
    assert 'id: "last_heard", label: "Last Heard", sortable: true, rosterMeta: false' in js


def test_dashboard_js_adds_links_and_location_points_sort_options() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'id: "links", label: "Links", sortable: true, rosterMeta: true' in js
    assert 'id: "links", label: "Links"' in js
    assert 'id: "location_points", label: "Location Points", sortable: true, rosterMeta: true' in js
    assert 'id: "location_points", label: "Location Points"' in js
    assert 'links: { sort: linkCount, text: String(linkCount), title: linkCountTitle }' in js
    assert (
        'location_points: { sort: positionPoints, text: String(positionPoints), title: locationPointsTitle }'
        in js
    )
    assert 'if (sortKey === "links" || sortKey === "location_points") return "desc";' in js
    assert "function chatNodeNavigatorUsesPrioritySections(" in js
    assert "const usePrioritySections = chatNodeNavigatorUsesPrioritySections(chatNodeNavigatorSortKey);" in js
    assert "if (!usePrioritySections) {" in js
    assert "regularRows.push(item);" in js
    assert "const pinnedSectionCount = usePrioritySections" in js


def test_dashboard_js_adds_link_quality_metadata_field_and_sort_option() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'id: "link_quality", label: "Quality", sortable: true, rosterMeta: true' in js
    assert (
        'id: "link_quality", label: "Quality", sortable: true, rosterMeta: true, '
        'rosterDefault: false, rosterSort: true, rosterSortLabel: "Link quality"'
        in js
    )
    assert "function chatNodeNavigatorFieldSortDefs() {" in js
    assert 'source: String(def && def.source || "node_field")' in js
    assert "function buildChatNodeNavigatorLinkQualityByNode(" in js
    assert "function chatNodeNavigatorInferLinkQuality(" in js
    assert 'showLinkQuality = Array.isArray(visibleMetaFieldIds)' in js
    assert 'visibleMetaFieldIds.includes("link_quality")' in js
    assert 'showHops = !nativeHopsRetired && Array.isArray(visibleMetaFieldIds)' in js
    assert 'visibleMetaFieldIds.includes("hops")' in js
    assert 'const hopsInlineHtml = showHops && hopsValue != null' in js
    assert 'showSnr = Array.isArray(visibleMetaFieldIds)' in js
    assert 'visibleMetaFieldIds.includes("snr")' in js
    assert 'class="chat-member-snr-inline"' in js
    assert 'if (snrInlineHtml) memberMetaRowParts.push(snrInlineHtml);' in js
    assert 'if (linkQualityInlineHtml) memberMetaRowParts.push(linkQualityInlineHtml);' not in js
    assert 'const linkQualityRailClass = linkQualityInlineHtml ? " has-link-quality" : "";' in js
    assert "${linkQualityRailClass}${packetSparkClass}" in js
    assert "${statusMarkerHtml}\n          ${linkQualityInlineHtml}\n          <span class=\"chat-member-main\">" in js
    assert 'const specialRosterFieldIds = new Set(["favorite", "hops", "link_quality", "snr", "last_heard"]);' in js
    assert 'showLastHeardMeta = !nativeLastHeardRetired && Array.isArray(visibleMetaFieldIds)' in js
    assert 'visibleMetaFieldIds.includes("last_heard")' in js
    assert 'class="chat-member-link-quality' in js
    assert 'title="${escAttr(linkQualityTitle)}" aria-label="${escAttr(linkQualityAria)}"' in js
    assert "chat-member-link-quality-label" not in js


def test_dashboard_js_optimizes_link_quality_computation_path() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "const chatNodeNavigatorLinkQualityCacheByState = (typeof WeakMap === \"function\")" in js
    assert "function chatNodeNavigatorShouldComputeLinkQuality(" in js
    assert "sortKey === \"link_quality\" || fieldIds.includes(\"link_quality\")" in js
    assert "function chatNodeNavigatorMinHeapPush(" in js
    assert "function chatNodeNavigatorMinHeapPop(" in js
    assert "const structuralPathLimit = Math.max(1, Math.min(pathLimit, sourceDegree, targetDegree));" in js
    assert "const shouldComputeLinkQuality = chatNodeNavigatorShouldComputeLinkQuality(" in js


def test_dashboard_css_styles_chat_member_link_quality_bars() -> None:
    css = build_dashboard_css(theme_css="")

    assert ".chat-member-link-quality {" in css
    assert ".chat-member-snr-inline {" in css
    assert "--chat-member-status-cap-width: 28px;" in css
    assert "--chat-member-status-mark-size: var(--chat-member-status-cap-width);" in css
    assert "--chat-member-link-cap-width: var(--chat-member-status-cap-width);" in css
    assert (
        ".chat-member-item.has-link-quality {\n"
        "      grid-template-columns: var(--chat-member-status-cap-width) "
        "var(--chat-member-link-cap-width) minmax(0, 1fr);\n"
        in css
    )
    assert (
        ".chat-member-item.has-link-quality.has-packet-spark {\n"
        "      grid-template-columns: var(--chat-member-status-cap-width) "
        "var(--chat-member-link-cap-width) minmax(0, 1fr) var(--chat-member-packet-cap-width);\n"
        in css
    )
    assert (
        ".chat-member-link-quality {\n"
        "      flex: 0 0 var(--chat-member-link-cap-width);\n"
        "      display: inline-flex;\n"
        "      align-items: center;\n"
        "      justify-content: center;\n"
        "      min-width: 0;\n"
        "      width: var(--chat-member-link-cap-width);\n"
        "      height: auto;\n"
        "      min-height: 100%;\n"
        "      align-self: stretch;\n"
        in css
    )
    assert "width: var(--chat-member-status-mark-size);" in css
    assert "height: var(--chat-member-status-mark-size);" in css
    assert "aspect-ratio: 1 / 1;" in css
    assert "width: 4px;" in css
    assert ".workspace-shell.chat-panel-collapsed .chat-member-link-quality," in css
    assert ".chat-member-link-quality-label" not in css
    assert ".chat-member-link-quality-bar.level-4" in css
    assert "[data-theme=\"dark\"] .chat-member-snr-inline" in css
    assert "[data-theme=\"dark\"] .chat-member-link-quality-bar {" in css


def test_dashboard_js_uses_persisted_node_packet_trends_for_roster_ticker() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "function buildChatNodeNavigatorPacketTrendMapsFromPayload" in js
    assert "safeState.traffic.node_packet_trends" in js
    assert "nodePacketTrendsRef: nodePacketTrends" in js


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


def test_render_html_adds_unread_and_manual_pin_node_shells() -> None:
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

    assert 'id="chat-room-unread-shell"' in html
    assert 'id="chat-room-unread-list"' in html
    assert 'id="chat-room-unread-count"' in html
    assert 'id="chat-room-meshtastic-shell"' in html
    assert 'id="chat-room-meshtastic-list"' in html
    assert 'id="chat-room-meshtastic-count"' in html
    assert 'id="chat-room-pinned-shell"' in html
    assert 'id="chat-room-pinned-list"' in html
    assert 'id="chat-room-pinned-count"' in html


def test_dashboard_adds_cached_city_hint_to_node_navigator_rows() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
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

    assert "let nodeCityHintCache = new Map();" in js
    assert "let nodeCityHintPending = new Map();" in js
    assert 'id: "city", label: "City", prefKey: "showCity", defaultValue: true' in js
    assert 'let chatNodeNavigatorShowCity = chatNodeNavigatorDefaultToggleOptionValue("city");' in js
    assert "function normalizeChatNodeNavigatorShowCityPref(value) {" in js
    assert 'return normalizeChatNodeNavigatorTogglePref("city", value);' in js
    assert "Object.assign(payload, chatNodeNavigatorTogglePreferencePayload());" in js
    assert 'if (clean === "city") return chatNodeNavigatorShowCity;' in js
    assert 'chatNodeNavigatorShowCity = normalized;' in js
    assert "function chatNodeNavigatorNodeLocation(nodeId, nodesById = null, item = null) {" in js
    assert "function hydrateChatNodeNavigatorCities(root) {" in js
    assert 'class="chat-member-city${memberCitySource === "estimated" ? " is-estimated" : ""}"' in js
    assert 'const nativeCityRetired = (typeof nodeExplorerNodeListPluginProvidesField === "function")' in js
    assert 'nodeExplorerNodeListPluginProvidesField("city", state);' in js
    assert "const showCity = !nativeCityRetired && (" in js
    assert "if (showCity && memberCityHtml) memberMetaRowParts.push(memberCityHtml);" in js
    assert js.index("if (showCity && memberCityHtml) memberMetaRowParts.push(memberCityHtml);") < js.index(
        "if (idleRowHtml) memberMetaRowParts.push(idleRowHtml);"
    )
    assert 'data-nav-option-id="${escAttr(optionId)}"' in js
    assert 'const togglePrefKey = chatNodeNavigatorTogglePrefKey(optionId);' in js
    assert "nextPrefs[togglePrefKey] = !!target.checked;" in js
    assert "hydrateChatNodeNavigatorCities(roomList);" in js
    assert ".chat-member-city {" in html
    assert ".chat-member-city[hidden]" in html
    assert "[data-theme=\"dark\"] .chat-member-city" in html


def test_dashboard_groups_node_navigator_options_from_registry() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    css = build_dashboard_css(theme_css="")
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

    assert "const chatNodeNavigatorOptionGroupDefs = Object.freeze([" in js
    assert 'Object.freeze({ id: "fields", label: "Fields" })' in js
    assert 'Object.freeze({ id: "plugins", label: "Plugins" })' in js
    assert 'Object.freeze({ id: "display", label: "Display" })' in js
    assert 'Object.freeze({ id: "order", label: "Order" })' in js
    assert 'id: "city", label: "City", prefKey: "showCity", defaultValue: true, sortAffects: false, group: "display"' in js
    assert "direct-history" not in js
    assert "DM history first" not in js
    assert "pinDirectHistory" not in js
    assert 'group: fieldId === "favorite" || fieldId === "link_quality"' in js
    assert '? "display"' in js
    assert ': (String(def && def.source || "") === "plugin" ? "plugins" : "fields")' in js
    assert "const optionDefsByGroup = new Map();" in js
    assert 'data-nav-option-group="${escAttr(groupId)}"' in js
    assert 'class="chat-node-navigator-field-option${checkedClass}"' in js
    assert 'aria-label="Node navigator options"' in html
    assert "chat-node-navigator-fields-head\">Options" not in html
    assert ".chat-node-navigator-option-section {" in css
    assert ".chat-node-navigator-option-grid {" in css
    assert ".chat-node-navigator-field-option.is-checked {" in css


def test_dashboard_accepts_plugin_node_fields_for_node_navigator_menu() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "const nodeExplorerPluginFieldIdPattern = /^plugin:" in js
    assert "function nodeExplorerPluginRuntimeFieldRows(state = null) {" in js
    assert "function nodeExplorerPluginRuntimeFieldValueRows(state = null) {" in js
    assert "const nodeExplorerPluginFieldDefsByState = (typeof WeakMap === \"function\") ? new WeakMap() : null;" in js
    assert "const nodeExplorerPluginFieldValueIndexByState = (typeof WeakMap === \"function\") ? new WeakMap() : null;" in js
    assert "function nodeExplorerPluginRuntimeFieldValueIndex(state = null) {" in js
    assert "function nodeExplorerPluginFieldRuntimeValueForNode(nodeId, fieldId, state = null) {" in js
    assert "const nodeValues = nodeExplorerPluginRuntimeFieldValueIndex(state).get(cleanNodeId);" in js
    assert "runtime.node_fields" in js
    assert "runtime.node_field_values" in js
    assert "function nodeExplorerNodeListPluginProvidesField(fieldId, state = null)" in js
    assert "const nodeExplorerNodeListPluginNativeFieldIds = new Set([" in js
    for field_id in (
        "last_heard",
        "id",
        "hardware",
        "snr",
        "hops",
        "links",
        "battery",
        "saved",
        "pos",
        "location_points",
    ):
        assert f'"{field_id}",' in js
    assert "function nodeExplorerNativeFieldReplacementByPlugin(fieldId, state = null)" in js
    assert "plugin:node_list:${cleanFieldId}" in js
    assert "function nodeExplorerNativeFieldIsRetiredByPlugin(fieldId, state = null)" in js
    assert "return !!nodeExplorerNativeFieldReplacementByPlugin(fieldId, state);" in js
    assert (
        'return source === "plugin" || !nodeExplorerNativeFieldIsRetiredByPlugin(fieldId, state);'
        in js
    )
    assert "function chatNodeNavigatorToggleOptionIsRetiredByPlugin(def, state = null)" in js
    assert 'if (optionId === "idle") return nodeExplorerNativeFieldIsRetiredByPlugin("last_heard", state);' in js
    assert 'if (optionId === "city") return nodeExplorerNodeListPluginProvidesField("city", state);' in js
    assert "let migrateNativeCityToggleToPluginField = false;" in js
    assert 'if (optionId === "city" && normalizeChatNodeNavigatorTogglePref(optionId, rawValue))' in js
    assert 'const pluginCityFieldId = normalizeNodeExplorerFieldId("plugin:node_list:city", latestState);' in js
    assert 'const replacementFieldId = (typeof nodeExplorerNativeFieldReplacementByPlugin === "function")' in js
    assert "const effectiveFieldId = replacementFieldId || fieldId;" in js
    assert "normalized.push(effectiveFieldId);" in js
    assert 'nodeExplorerNativeFieldIsRetiredByPlugin("hops", state);' in js
    assert 'nodeExplorerNativeFieldIsRetiredByPlugin("last_heard", state);' in js
    assert "function nodeExplorerPluginFieldIdIsRedundant" not in js
    assert "function nodeExplorerPluginRuntimeFieldIsRedundant" not in js
    assert "function normalizeNodeExplorerRosterLine(value, fallback = 2)" in js
    assert "function nodeExplorerRosterLineForDef(def, fallback = 2)" in js
    assert "const rosterLine = normalizeNodeExplorerRosterLine(row.roster_line, 2);" in js
    assert 'source: "plugin"' in js
    assert 'group: fieldId === "favorite" || fieldId === "link_quality"' in js
    assert ': (String(def && def.source || "") === "plugin" ? "plugins" : "fields")' in js
    assert "rosterLine," in js
    assert "memberMetaRowParts.push(...collectRosterLineFieldHtml(1));" in js
    assert "if (rosterLine <= 1) continue;" in js
    assert 'data-roster-line="${escAttr(String(line))}"' in js
    assert "function chatNodeNavigatorFieldRenderKind(def, fallback = \"chip\") {" in js
    assert "function chatNodeNavigatorFieldRenderShape(renderKind) {" in js
    assert 'if (kind === "text" || kind === "timestamp") return "text";' in js
    assert "function chatNodeNavigatorFieldSuppressVisibleLabel(fieldId, def) {" in js
    assert 'cleanFieldId === "plugin:node_list:city"' in js
    assert 'pluginId === "node_list" && pluginFieldId === "city"' in js
    assert "function buildChatNodeNavigatorMetadataFieldHtml(fieldId, def, field, options = null) {" in js
    assert "const suppressVisibleLabel = chatNodeNavigatorFieldSuppressVisibleLabel(cleanFieldId, def);" in js
    assert "const titleText = suppressVisibleLabel ? title : `${label}: ${title}`;" in js
    assert 'const keyHtml = suppressVisibleLabel' in js
    assert 'class="chat-member-metadata-text"' in js
    assert 'data-node-field-source="${escAttr(source)}"' in js
    assert 'data-node-field-render-kind="${escAttr(renderKind)}"' in js
    assert 'class="chat-member-metadata-chip"' in js
    assert "node.plugin_fields" in js
    assert "nodeExplorerPluginFieldDefsFromState(opts.state || null)" in js
    assert "nodeExplorerPluginFieldRuntimeValueForNode(nodeId, fieldId, opts.state || null)" in js


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


def test_dashboard_js_omits_dm_history_first_toggle_from_node_navigator() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "function chatNodeNavigatorTogglePreferencePayload() {" in js
    assert 'data-nav-option-id="${escAttr(optionId)}"' in js
    assert "nextPrefs[togglePrefKey] = !!target.checked;" in js
    assert "direct-history" not in js
    assert "DM history first" not in js
    assert "pinDirectHistory" not in js
    assert "normalizeChatNodeNavigatorPinDirectHistoryPref" not in js
    assert "chatNodeNavigatorDirectHistoryPeerIds" not in js
    assert "directHistoryPeerIds" not in js
    assert "historyPriorityRows" not in js
    assert "const orderedRoomRows = regularRows;" in js


def test_dashboard_js_windows_chat_roster_dom_for_responsiveness() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    css = build_dashboard_css(theme_css="")

    assert "const chatRosterMaxEntries = 180;" in js
    assert "let chatRosterVisibleLimit = chatRosterMaxEntries;" in js
    assert "const rosterBaseLimit = Math.max(1, Math.trunc(Number(chatRosterMaxEntries) || 180));" in js
    assert "const hasRosterQuery = String(rosterQuery || \"\").trim().length > 0;" in js
    assert "const shouldWindowRoomRows = !hasRosterQuery && orderedRoomRows.length > 0;" in js
    assert "const visibleRoomRows = shouldWindowRoomRows" in js
    assert "selectedRoomRowIndex + 1" in js
    assert "traceRoomRowIndex + 1" in js
    assert 'class="chat-roster-load-btn"' in js
    assert "data-roster-hidden-count" in js
    assert "chatRosterVisibleLimit = currentLimit + Math.max(1, Math.min(baseLimit, hiddenCount || baseLimit));" in js
    assert ".chat-roster-load-row {" in css
    assert "[data-theme=\"dark\"] .chat-roster-load-row {" in css


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

    assert 'id: "idle", label: "Idle / Last Heard", prefKey: "showIdle", defaultValue: false' in js
    assert 'let chatNodeNavigatorShowIdle = chatNodeNavigatorDefaultToggleOptionValue("idle");' in js
    assert "function normalizeChatNodeNavigatorShowIdlePref(value) {" in js
    assert 'return normalizeChatNodeNavigatorTogglePref("idle", value);' in js
    assert "const nextToggleValues = new Map();" in js
    assert 'if (optionId === "idle" && prefs[prefKey] == null && legacyLastHeardMetaAsFreshness)' in js
    assert 'chatNodeNavigatorShowIdle = normalized;' in js
    assert 'data-nav-option-id="${escAttr(optionId)}"' in js
    assert "nextPrefs[togglePrefKey] = !!target.checked;" in js
    assert "function chatNodeNavigatorMetaFieldIdsIncludeLegacyLastHeard(rawIds) {" in js
    assert 'normalizeNodeExplorerFieldId(value) === "last_heard"' in js
    assert "const legacyLastHeardMetaAsFreshness = (" in js
    assert 'if (optionId === "idle" && prefs[prefKey] == null && legacyLastHeardMetaAsFreshness)' in js
    assert "rawValue = true;" in js
    assert "function nodeFreshnessInlineLabel(lastSeenUnix, status" in js
    assert 'text: showLastHeard ? "Last Heard: n/a" : "Idle: n/a"' in js
    assert 'text: `Last Heard: ${lastSeenText}`' in js
    assert 'text: `Idle: ${formatIdleAge(ts, nowUnix)}`' in js
    assert 'const freshnessInline = (showIdle || showLastHeardMeta)' in js
    assert 'data-freshness-inline-mode="${escAttr(freshnessInline.mode || "")}"' in js
    assert 'specialRosterFieldIds.has(fieldId)) continue;' in js
    assert "nodeFreshnessInlineLabel(lastSeenUnix, key, nowUnix)" in js
    assert 'const memberMetaRowParts = [];' in js
    assert 'const memberMetaRowHtml = memberMetaRowParts.length > 0' in js


def test_dashboard_js_labels_node_packet_plot_without_rx_tx_text() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    css = build_dashboard_css(theme_css="")

    assert 'id: "packet-direction", label: "Packet plot", prefKey: "showPacketDirection", defaultValue: false' in js
    assert 'data-nav-option-id="${escAttr(optionId)}"' in js
    assert "TX/RX + Plot" not in js
    assert "packetDirectionHtml" not in js
    assert "chat-member-packet-direction" not in js
    assert "Observed packet activity:" in js
    assert "Packet activity trend:" in js
    assert ".chat-member-packet-direction" not in css


def test_dashboard_js_supports_status_dot_toggle_in_node_navigator() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'id: "status-dots", label: "Status", prefKey: "showStatusDots", defaultValue: true' in js
    assert 'let chatNodeNavigatorShowStatusDots = chatNodeNavigatorDefaultToggleOptionValue("status-dots");' in js
    assert "function normalizeChatNodeNavigatorShowStatusDotsPref(value) {" in js
    assert 'return normalizeChatNodeNavigatorTogglePref("status-dots", value);' in js
    assert "const nextToggleValues = new Map();" in js
    assert 'chatNodeNavigatorShowStatusDots = normalized;' in js
    assert 'data-nav-option-id="${escAttr(optionId)}"' in js
    assert "nextPrefs[togglePrefKey] = !!target.checked;" in js
    assert 'const showStatusDots = (typeof normalizeChatNodeNavigatorShowStatusDotsPref === "function")' in js
    assert 'const statusVisibilityClass = showStatusDots ? "" : " status-hidden";' in js
    assert 'const statusMarkerClass = showStatusDots ? "" : " is-hidden";' in js
    assert 'const statusMarkerAttrs = showStatusDots' in js
    assert "? statusGlyphAttrs" in js
    assert ': \' aria-hidden="true"\';' in js
    assert 'const displayNameEmoji = (typeof normalizeNodeTagEmoji === "function")' not in js
    assert 'const isLocalNode = (typeof isSelfNodeId === "function")' not in js
    assert 'const hasNodeVisualEmoji = !!cleanNodeVisualEmoji;' in js
    assert 'const autoNewStatusEntry = (typeof autoNodeTagEntryForNode === "function")' in js
    assert 'const autoNewClass = autoNewStatusEntry ? " auto-new-node" : "";' in js
    assert "function stripNodeVisualEmojiFromLabel(value, emoji) {" in js
    assert "const statusOverridesNodeVisualEmoji = !!autoNewStatusEntry;" in js
    assert "hasNodeVisualEmoji && showStatusDots && !statusOverridesNodeVisualEmoji && typeof stripNodeVisualEmojiFromLabel === \"function\"" in js
    assert "stripNodeVisualEmojiFromLabel(rawMemberDisplayName, cleanNodeVisualEmoji)" in js
    assert 'nodeTagIconSvgHtml(tagEntry, "chat-member-tag-chip-icon")' not in js
    assert 'nodeTagIconSvgHtml(autoNewStatusEntry, "chat-member-status-new-icon")' not in js
    assert 'const statusMarkerHtml = autoNewStatusEntry' in js
    assert '${autoNewClass}' in js
    assert '<span class="chat-member-status chat-member-status-new status-${statusKey}${statusMarkerClass}"${statusMarkerAttrs}><span class="chat-member-status-core" aria-hidden="true"><span class="chat-member-status-new-text">N</span></span></span>' in js
    assert '<span class="chat-member-status chat-member-status-emoji status-${statusKey}${statusMarkerClass}"${statusMarkerAttrs}>' in js
    assert '<span class="chat-member-status-core" aria-hidden="true">' in js
    assert '<span class="chat-member-status-ring"></span>' in js
    assert '<span class="chat-member-status-emoji-glyph">${escAttr(cleanNodeVisualEmoji)}</span>' in js
    assert '<span class="chat-member-status chat-member-status-dot status-${statusKey}${statusMarkerClass}"${statusMarkerAttrs}><span class="chat-member-status-core" aria-hidden="true">●</span></span>' in js


def test_dashboard_js_sorts_status_using_visible_freshness_snapshot() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "function chatNodeNavigatorStatusSortValue(item, projection) {" in js
    assert 'const statusKey = normalizeFreshnessKey(item && item.status);' in js
    assert 'return (typeof statusRank === "function") ? statusRank(statusKey) : 99;' in js
    assert "const freshnessUnixRaw = Number(opts.freshnessUnix ?? opts.lastSeenUnix);" in js
    assert 'freshnessUnix > 0 && freshnessUnix !== lastHeardUnix && typeof formatLocalChatTime === "function"' in js
    assert "last_heard: { sort: displayLastHeardUnix, text: lastHeardText, title: lastHeardTitle }" in js
    assert "freshnessUnix: entry && entry.lastSeenUnix," in js
    assert "freshnessUnix: snapshot && snapshot.lastSeenUnix," in js
    assert "return chatNodeNavigatorStatusSortValue(safeItem, safeProjection);" in js
    assert "chatNodeNavigatorStatusSortValue(a, aProjection)" in js
    assert "chatNodeNavigatorStatusSortValue(b, bProjection)" in js


def test_dashboard_js_orders_equal_status_nodes_by_latest_received() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    received_tie_break = """if (sortKey === \"status\") {
          const receivedCmp = chatNodeNavigatorCompareSortValues(
            chatNodeNavigatorLastUpdateUnix(b, bProjection),
            chatNodeNavigatorLastUpdateUnix(a, aProjection)
          );
          if (receivedCmp !== 0) return receivedCmp;
        }"""
    assert received_tie_break in js
    assert js.index(received_tie_break) < js.index("const activityCmp = chatNodeNavigatorCompareSortValues(")


def test_dashboard_js_marks_muted_nodes_in_navigator_rows() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'const muted = (typeof isMutedNode === "function") && isMutedNode(nodeId);' in js
    assert 'const mutedClass = muted ? " muted-node" : "";' in js
    assert '`Muted: ${muted ? "yes" : "no"}`' in js
    assert 'const hasDirectHistory = directHistoryPeerIds.has(nodeId);' not in js
    assert 'if (unreadDirectCount > 0) {' in js
    assert 'tooltipLines.splice(4, 0, `Unread direct messages: ${unreadDirectCount}`);' in js
    assert '${mutedClass}' in js
    assert 'data-unread-direct-count="${escAttr(unreadDirectCount)}"' in js


def test_dashboard_js_tracks_unread_direct_counts_and_priority_sections_in_node_navigator() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "const unreadDirectByPeer = new Map();" in js
    assert "function normalizeChatNodeNavigatorUnreadDirectByPeer(source = null) {" in js
    assert 'const unreadShell = document.getElementById("chat-room-unread-shell");' in js
    assert 'const meshtasticShell = document.getElementById("chat-room-meshtastic-shell");' in js
    assert 'const pinnedShell = document.getElementById("chat-room-pinned-shell");' in js
    assert "const meshtasticRows = [];" in js
    assert "const pinnedUnreadRows = [];" in js
    assert "const pinnedManualRows = [];" in js
    assert "const regularRows = [];" in js
    assert "unreadShell.hidden = pinnedUnreadRows.length <= 0;" in js
    assert "meshtasticShell.hidden = false;" in js
    assert "No Meshtastic favorites yet." in js
    assert "pinnedShell.hidden = pinnedManualRows.length <= 0;" in js
    assert 'bindChatNodeNavigatorListInteractions(unreadList);' in js
    assert 'bindChatNodeNavigatorListInteractions(meshtasticList);' in js
    assert 'bindChatNodeNavigatorListInteractions(pinnedList);' in js
    assert "const unreadDirectCount = Math.max(0, Math.trunc(Number(unreadDirectByPeer.get(nodeId) || 0)));" in js
    assert 'tooltipLines.splice(4, 0, `Unread direct messages: ${unreadDirectCount}`);' in js
    assert '`Pinned: ${((typeof isPinnedNode === "function") && isPinnedNode(nodeId)) ? "yes" : "no"}`' in js
    assert 'data-unread-direct-count="${escAttr(unreadDirectCount)}"' in js
    assert 'if (!isSelectableNodeId(nodeId)) return;' in js
    assert 'selectNode(nodeId, true, false);' in js
    assert 'unreadDirectByPeer,' in js
    assert 'directHistoryPeerIds,' not in js
