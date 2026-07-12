import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_css import build_dashboard_css
from meshdash.html_js import build_dashboard_js
from meshdash.html_template import render_html


def test_dashboard_js_uses_curated_default_ticker_layout() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert re.search(
        r'const tickerDefaultOrder = \[\s*"self",\s*"radio",\s*"known_nodes",\s*"online_nodes",\s*"new_nodes",\s*"packets_per_min",\s*"channel_util",\s*"node",\s*"links",\s*"battery",',
        js,
    )
    assert re.search(
        r'for \(const id of \[\s*"self",\s*"radio",\s*"known_nodes",\s*"online_nodes",\s*"new_nodes",\s*"packets_per_min",\s*"channel_util",\s*"node",\s*"links",\s*\]\)',
        js,
    )
    assert 'if (key === "target") return "self";' in js
    assert 'if (seen.has("self") && !seen.has("radio")) {' in js
    assert 'enabled: { ...tickerDefaultEnabled },' in js
    assert "prefs.enabled[id] = !!defaults.enabled[id];" in js


def test_dashboard_omits_removed_bot_ticker_and_keeps_standalone_zork() -> None:
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

    for token in (
        'id="summary-ticker-bots"',
        'data-ticker-id="bots"',
        'data-app-view="bots"',
        "/api/bots/",
    ):
        assert token not in html
    for token in (
        '{ id: "bots", defaultLabel: "Bots", metric: false }',
        "botTickerAvailableForState",
        "buildBotTickerSummary",
        "botRuntimeFromState",
        'if (id === "bots") return "bots";',
        "/api/bots/",
    ):
        assert token not in js
    assert 'fetch("/api/games/zork"' in js
    assert 'name: "zork"' in js



def test_dashboard_js_does_not_include_live_update_ticker() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "topbarUpdateTicker" not in js
    assert "publishTopbarUpdateTickerEvent" not in js
    assert "update_ticker_enabled" not in js
    assert "updateTickerEnabled" not in js
    assert "show_update_ticker" not in js
    assert "showUpdateTicker" not in js
    assert "node_online_oneshot" not in js
    assert "topbarOneshot" not in js
    assert "Ticker preferences saved locally." not in js
    assert "Live update ticker shown." not in js
    assert "Live update ticker hidden." not in js
    assert "Ticker preferences reset to defaults." not in js


def test_dashboard_js_removes_unique_node_color_settings() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "settingsUniqueNodeColors" not in js
    assert "settingsUniqueChatColors" not in js
    assert "settings-appearance-unique-node-colors" not in js
    assert "settings-appearance-unique-chat-colors" not in js


def test_dashboard_js_uses_semantic_ticker_state_profiles() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'function resolveMetricTickerState(latest, delta, trend, config = {}) {' in js
    assert 'item.classList.add(`metric-state-${resolvedState}`);' in js
    assert 'stateProfile: "count_delta"' in js
    assert 'stateProfile: "traffic_delta"' in js
    assert 'stateProfile: "channel_util"' in js
    assert 'stateProfile: "battery_pct"' in js
    assert 'stateProfile: Number.isFinite(nodeRssi) ? "signal_rssi" : "signal_snr"' in js
    assert 'stateProfile: "wifi_rssi"' in js


def test_dashboard_js_counts_auto_new_nodes_for_ticker() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert '{ id: "new_nodes", defaultLabel: "New Nodes", metric: true }' in js
    assert 'function countAutoNewNodes(state = latestState) {' in js
    assert 'if (autoNodeTagEntryForNode(nodeId, safeState)) count += 1;' in js
    assert 'const autoNewNodeCount = (typeof countAutoNewNodes === "function")' in js
    assert 'setText("m-new-nodes", autoNewNodeCount);' in js
    assert 'updateMetricTicker("new_nodes", autoNewNodeCount, {' in js
    assert 'containerId: "ticker-new-nodes",' in js


def test_render_html_exposes_auto_new_nodes_ticker() -> None:
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

    assert 'id="summary-ticker-new-nodes"' in html
    assert 'data-ticker-id="new_nodes"' in html
    assert '<div class="label" data-ticker-label>New Nodes</div>' in html
    assert 'id="ticker-chart-new-nodes"' in html


def test_dashboard_network_nodes_plot_exposes_new_nodes_series_controls() -> None:
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

    assert 'id="network-overview-node-line-new"' in html
    assert 'id="weekly-summary-node-line-new"' not in html
    assert "Show new nodes (24h) line" in html
    assert re.search(
        r'const weeklySummaryNodeSeriesOrder = \[\s*"online_nodes",\s*"new_nodes",\s*"known_nodes",\s*"saved_nodes",\s*"position_nodes",\s*\];',
        js,
    )
    assert 'new_nodes: "network-overview-node-line-new",' in js
    assert 'new_nodes: "New Nodes (24h)",' in js
    assert 'new_nodes: { tone: "aux3", dashed: false, width: 2.1 },' in js
    assert "function collectNewNodeFirstSeenUnix(state = latestState) {" in js
    assert "function countNewNodesFirstSeenInWindow(firstSeenUnixValues, bucketUnix, windowSeconds = 24 * 60 * 60) {" in js
    assert "const stabilizedRestartGaugeValue = (seriesKey, rawValue, resetBreak) => {" in js
    assert 'const restartGaugeSeries = new Set(["known_nodes", "saved_nodes", "position_nodes"]);' in js
    assert "const knownObservedValue = Number.isFinite(knownRawValue) && Number.isFinite(savedRawValue)" in js
    assert "? Math.max(knownRawValue, savedRawValue)" in js
    assert 'const knownValue = stabilizedRestartGaugeValue("known_nodes", knownObservedValue, resetBreak);' in js
    assert "const newNodeFirstSeenUnixValues = nodesMetric" in js
    assert "countNewNodesFirstSeenInWindow(" in js
    assert "rollingNewNodeCount" not in js
    assert "savedDelta" not in js


def test_dashboard_exposes_mesh_links_ticker() -> None:
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

    assert '{ id: "links", defaultLabel: "Links", metric: true }' in js
    assert 'function buildLinksTickerSummary(state = latestState) {' in js
    assert 'summary.edge_count ?? summary.link_count ?? summary.links' in js
    assert 'summary.real_edge_count ?? summary.real_links ?? summary.confirmed_link_count' in js
    assert 'summary.live_edge_count' in js
    assert 'const text = `${linkText} · ${secondaryLinkText} ${secondaryLinkLabel}`;' in js
    assert 'updateMetricTicker("links", linksMetricValue, {' in js
    assert 'containerId: "ticker-links",' in js
    assert 'id="summary-ticker-links"' in html
    assert 'data-ticker-id="links"' in html
    assert '<div class="label" data-ticker-label>Links</div>' in html
    assert 'id="m-links"' in html
    assert 'id="ticker-chart-links"' in html


def test_compact_tickers_expand_selected_card_below_fixed_row() -> None:
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
    css = build_dashboard_css(theme_css="")

    assert 'id="summary-ticker-detail-tray"' not in html
    assert 'id="summary-ticker-expanded-slot"' in html
    assert 'function bindCompactTickerDetailTrayControls() {' in js
    assert 'function toggleCompactTickerDetail(id) {' in js
    assert 'function toggleExpandedTickerPlotZoom(id) {' in js
    assert 'function compactTickerExpandedSlot() {' in js
    assert 'function renderCompactTickerExpandedSlot(sourceItem, cleanId) {' in js
    assert 'function stripClonedTickerIds(root) {' in js
    assert 'function expandedTickerPlotItemIsZoomable(item) {' in js
    assert 'return !!id && id !== "self";' in js
    assert 'topbarElement.classList.add("has-compact-ticker-detail");' in js
    assert 'item.classList.remove("is-compact-detail-open");' in js
    assert 'item.classList.toggle("is-compact-detail-source", expandable && id === activeCompactTickerDetailId);' in js
    assert 'item.classList.toggle("is-expanded-plot-zoom", zoomable && id === activeExpandedTickerZoomId);' in js
    assert 'toggleExpandedTickerPlotZoom(item.dataset.tickerId || "");' in js
    assert 'clone.classList.add("is-compact-detail-open", "summary-ticker-expanded-card");' in js
    assert "stripClonedTickerIds(clone);" in js
    assert "slot.replaceChildren(clone);" in js
    assert "slot.hidden = false;" in js
    assert "clearCompactTickerExpandedSlot();" in js
    assert "const compactTickerCount = activeTickerConsumesRow ? visibleTickerCount - 1 : visibleTickerCount;" not in js
    assert 'row.style.setProperty("--summary-visible-ticker-count", String(Math.max(1, visibleTickerCount)));' in js
    assert "syncCompactTickerColumnCount(row);" in js
    assert "renderSummary(latestState);" in js
    assert "const compactDetailTickerView = tickerItem instanceof HTMLElement" in js
    assert 'topbarElement.classList.contains("ticker-expanded") || compactDetailTickerView' in js
    assert 'row.addEventListener("click", (ev) => {' in js
    assert 'row.addEventListener("keydown", (ev) => {' in js
    assert 'refreshCompactTickerDetailTray();' in js
    assert ".summary-ticker-detail-tray {" not in css
    assert ".summary-ticker-expanded-slot {" in css
    assert ".summary-ticker-expanded-slot[hidden] {" in css
    assert ".summary-ticker-expanded-slot .summary-ticker-expanded-card {" in css
    assert ".topbar.has-compact-ticker-detail:not(.ticker-expanded) .summary-ticker-item.is-compact-detail-open {" in css
    assert ".summary-ticker-item.is-compact-detail-source {" not in css
    compact_detail_base = re.search(
        r"\.topbar\.has-compact-ticker-detail:not\(\.ticker-expanded\) \.summary-ticker-item\.is-compact-detail-open \{\s*(.*?)\s*\}",
        css,
        re.S,
    )
    assert compact_detail_base is not None
    assert "grid-column:" not in compact_detail_base.group(1)
    assert "grid-row:" not in compact_detail_base.group(1)
    assert "grid-template-rows: auto auto auto;" in compact_detail_base.group(1)
    assert "background:" not in compact_detail_base.group(1)
    assert "border-color:" not in compact_detail_base.group(1)
    assert "box-shadow:" not in compact_detail_base.group(1)
    assert "[data-theme=\"dark\"] .topbar.has-compact-ticker-detail:not(.ticker-expanded) .summary-ticker-item.is-compact-detail-open {" in css
    assert "background: var(--ui-panel);" in css
    assert "border-color: var(--workspace-shell-border);" in css
    assert "color: var(--ui-text);" in css
    assert "box-shadow: none;" in css
    assert '[data-theme="dark"] .topbar:not(.ticker-expanded) .summary-ticker-item[data-ticker-id]:not([data-ticker-id="self"]):hover,' in css
    assert '[data-theme="dark"] .topbar:not(.ticker-expanded) .summary-ticker-item[data-ticker-id]:not([data-ticker-id="self"]):focus-visible {' in css
    assert "background: color-mix(in srgb, var(--workspace-shell-bg-alt) 88%, var(--workspace-shell-hover-bg) 12%);" in css
    assert "border-color: var(--workspace-shell-border-strong);" in css
    assert '[data-theme="dark"] .topbar.has-compact-ticker-detail:not(.ticker-expanded) .summary-ticker-item.is-compact-detail-open:hover,' in css
    assert '[data-theme="dark"] .topbar.has-compact-ticker-detail:not(.ticker-expanded) .summary-ticker-item.is-compact-detail-open:focus-visible {' in css
    assert ".topbar.has-compact-ticker-detail:not(.ticker-expanded) .summary-ticker-item.is-compact-detail-open .metric-ticker {" in css
    assert '.topbar.ticker-expanded .summary-ticker-item[data-ticker-id]:not([data-ticker-id="self"]) {' in css
    assert ".topbar.ticker-expanded .summary-ticker-item.is-expanded-plot-zoom {" in css


def test_metric_state_classes_only_set_ticker_accents() -> None:
    css = build_dashboard_css(theme_css="")

    for state in ("neutral", "good", "warn", "bad"):
        block = re.search(
            rf'\[data-theme="dark"\] \.topbar \.summary-ticker-item\.metric-state-{state} \{{\s*(.*?)\s*\}}',
            css,
            re.S,
        )
        assert block is not None
        body = block.group(1)
        assert "--ticker-card-accent:" in body
        assert "--ticker-card-accent-soft:" in body
        assert "background:" not in body
        assert "border-color:" not in body
        assert "box-shadow:" not in body


def test_dashboard_js_merges_summary_hydration_with_persisted_ticker_series() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'function mergeMetricTickerSeries(metricKey, incomingSeries, cutoffMs = Date.now() - metricTickerRetentionWindowMs()) {' in js
    assert 'const existing = Array.isArray(metricTickerSeries.get(cleanKey))' in js
    assert 'const mergedByBucket = new Map();' in js
    assert 'const merged = Array.from(mergedByBucket.values())' in js
    assert 'const merged = mergeMetricTickerSeries(metricKey, series, cutoffMs);' in js


def test_dashboard_js_flushes_ticker_series_on_page_exit() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'function persistDashboardSessionStateNow() {' in js
    assert 'if (typeof persistMetricTickerSeriesNow === "function") {' in js
    assert 'window.addEventListener("pagehide", () => {' in js
    assert 'window.addEventListener("beforeunload", () => {' in js


def test_dashboard_js_tab_title_uses_chat_unread_only() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'function syncDocumentUnreadTitle(count) {' in js
    assert 'const unreadBadge = unreadCount > 99 ? "99+" : String(unreadCount);' in js
    assert 'const nextTitle = unreadCount > 0' in js
    assert 'const attentionCount = Math.max(unreadCount, systemCount);' not in js
    assert 'const systemCount = Math.max(0, Math.trunc(Number(totalSystemNotificationCount()) || 0));' not in js


def test_dashboard_js_status_rows_do_not_seed_chat_unread() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'countsUnread: kind !== "status" && !senderIsSelf,' in js
    assert "const directRenderedInEveryone = !chatMainDirectModeEnabled" in js
    assert "if (directRenderedInEveryone) return true;" in js
    assert 'if (!chatMainDirectModeEnabled && key === "all") {' in js
    assert "chatUnreadByMeshChannel.direct = Object.create(null);" in js

def test_render_html_uses_single_row_compact_ticker_strip() -> None:
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

    assert re.search(
        r"\.topbar \.sub \.summary-ticker-row \{\s*display: grid;\s*grid-auto-flow: column;\s*grid-template-columns: var\(--topbar-corner-reserve, 36px\) repeat\(var\(--summary-visible-ticker-count, 10\), minmax\(0, 1fr\)\);\s*grid-auto-columns: minmax\(0, 1fr\);\s*gap: 5px;",
        html,
    )
    assert re.search(
        r"\.topbar\.ticker-expanded \.sub \.summary-ticker-row \{\s*display: flex;\s*flex-wrap: wrap;\s*align-items: stretch;",
        html,
    )
    assert "flex: 1 1 min(208px, 100%);" in html
    assert ".topbar.ticker-expanded.ticker-wrap-balanced .summary-ticker-item {" in html
    assert "flex-basis: min(300px, 100%);" in html
    ticker_item_section = html.split(".topbar .summary-ticker-item {", 1)[1].split("}", 1)[0]
    assert "--ticker-text: var(--theme-text-color, var(--ui-text));" in ticker_item_section
    assert "--ticker-text-strong: var(--theme-text-color-strong, var(--ticker-text));" in ticker_item_section
    assert "--ticker-text-soft: var(--theme-text-color-soft, var(--ui-text-soft));" in ticker_item_section
    assert "--ticker-text-muted: var(--theme-text-color-muted, var(--ticker-text-soft));" in ticker_item_section
    assert "color: var(--ticker-text);" in ticker_item_section
    assert re.search(
        r"\.topbar \.summary-ticker-item \{\s*--ticker-text: var\(--theme-text-color, var\(--ui-text\)\);\s*--ticker-text-strong: var\(--theme-text-color-strong, var\(--ticker-text\)\);\s*--ticker-text-soft: var\(--theme-text-color-soft, var\(--ui-text-soft\)\);\s*--ticker-text-muted: var\(--theme-text-color-muted, var\(--ticker-text-soft\)\);\s*border: 1px solid .*?\s*background: var\(--ui-panel\);\s*border-radius: 7px;\s*padding: 4px 7px;\s*min-width: 0;\s*color: var\(--ticker-text\);\s*position: relative;\s*display: grid;\s*grid-template-columns: minmax\(0, 1fr\) auto;\s*grid-template-rows: auto;",
        html,
    )
    assert ".topbar:not(.ticker-expanded) .summary-ticker-item > .label {" in html
    assert "bottom: 2px;" in html
    assert "color: color-mix(in srgb, var(--ticker-text-muted) 12%, transparent);" in html
    assert "font-size: clamp(6px, 0.42vw, 7px);" in html
    assert "text-align: right;" in html
    assert ".topbar:not(.ticker-expanded) .summary-ticker-item > .value," in html
    assert re.search(
        r"\.topbar \.summary-ticker-item \.metric-ticker-chart \{\s*width: 72px;\s*height: 16px;",
        html,
    )


def test_dashboard_js_balances_wrapped_tickers_only_when_needed() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "let visibleTickerCount = 0;" in js
    assert "if (isEnabled) {" in js
    assert "visibleTickerCount += 1;" in js
    assert "syncCompactTickerColumnCount(row);" in js
    assert 'topbarElement.classList.toggle("ticker-wrap-balanced", visibleTickerCount > 8);' in js


def test_render_html_widens_ticker_cards_for_phone_swipe_scrolling() -> None:
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

    assert "@media (max-width: 760px) {" in html
    assert "grid-template-columns: var(--topbar-corner-reserve, 30px) repeat(var(--summary-visible-ticker-count, 10), minmax(168px, 82vw));" in html
    assert "grid-auto-columns: minmax(168px, 82vw);" in html
    assert "scroll-snap-type: x proximity;" in html
    assert ".topbar .summary-ticker-item {" in html
    assert "scroll-snap-align: start;" in html


def test_render_html_omits_live_update_ticker_toggle_in_settings() -> None:
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

    assert 'id="settings-ticker-live-update-enabled"' not in html
    assert "Show live update ticker" not in html
    assert "sideways scrolling live-update bar" not in html
    assert 'id="topbar-update-ticker"' not in html


def test_dashboard_js_renders_selected_or_local_identity_in_node_ticker() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'const selfMetric = document.getElementById("m-self");' in js
    assert 'const selfCard = document.getElementById("summary-ticker-self");' in js
    assert "function resolveSelfNodeCityLocation(state, node, owner, nodeId)" in js
    assert "function resolveSelfNodeNearestCityLabel(location)" in js
    assert 'const selectedTickerCurrentId = normalizeNodeId(selectedNodeId || "");' in js
    assert "selfTickerAlternateNodeId = selectedTickerCurrentId;" in js
    assert "normalizeNodeId(selfTickerAlternateNodeId || \"\") === localId" in js
    assert "const selectedTickerId = (" in js
    assert '? selectedTickerCurrentId' in js
    assert ": normalizeNodeId(selfTickerAlternateNodeId || \"\");" in js
    assert "const hasSelectedTickerNode = isSelectableNodeId(selectedTickerId) && selectedTickerId !== localId;" in js
    assert "const selectedTickerNode = hasSelectedTickerNode" in js
    assert "const resolveTickerIdentityName = (nodeId, node, owner, fallbackName) => {" in js
    assert 'selfCard.classList.remove("has-selected-node", "profiled-node", "has-node-profile-watermark", "has-fallback-node-watermark");' in js
    assert 'selfCard.classList.toggle("has-selected-node", hasSelectedTickerNode);' in js
    assert "clearNodeAppearanceElementStyle(selfCard);" in js
    assert "const selfCardAppearanceEntry = (" in js
    assert "effectiveNodeAppearanceForNode(localId, state)" in js
    assert "selfCard.classList.add(\"profiled-node\");" in js
    assert "applyNodeAppearanceElementStyle(selfCard, selfCardAppearanceEntry);" in js
    assert "normalizeMeshyfaceProfileLastBroadcastChannelIndex(" in js
    assert "selfCard.style.setProperty(\"--self-node-channel-edge-fill\", selfCardChannelMeta.fill);" in js
    assert "meshyfaceProfileGhostForAppearance(selfCardAppearanceEntry)" in js
    assert "selfCard.classList.add(\"has-node-profile-watermark\");" in js
    assert "selfLabel.hidden = hasSelectedTickerNode;" in js
    assert 'selfLabel.classList.remove("is-dual-node-label");' in js
    assert "if (!hasSelectedTickerNode) {" in js
    assert 'selfLabelText.className = "self-node-label-self";' in js
    assert 'selfLabelText.textContent = "Self";' in js
    assert 'selfLabelText.dataset.summaryFocusKind = "self";' in js
    assert 'selectedLabelText.className = "self-node-label-selected";' not in js
    assert "const cardLocalNodeId = isSelectableNodeId(localId) ? localId : \"\";" in js
    assert "const cardSelectedNodeId = (" in js
    assert "selfCard.dataset.localNodeId = cardLocalNodeId;" in js
    assert "selfCard.dataset.selectedNodeId = cardSelectedNodeId;" in js
    assert "Click either side to focus it." in js
    assert 'selfMetric.classList.toggle("is-dual-node-context", hasSelectedTickerNode);' in js
    assert 'const addIdentitySlot = (kind, label, nodeId, node, owner, nodeName, fallbackName) => {' in js
    assert "slot.className = `self-node-identity-slot self-node-identity-${kind}`;" in js
    assert 'effectiveNodeAppearanceForNode(cleanNodeId, state)' in js
    assert 'appearanceEntry.profileAppearance' in js
    assert 'slot.classList.add("profiled-node");' in js
    assert 'slot.setAttribute("style", appearanceStyleVars);' in js
    assert "slot.dataset.nodeId = cleanNodeId;" in js
    assert "slot.dataset.identityKind = targetLabel;" in js
    assert 'slot.setAttribute("role", "button");' in js
    assert 'const localSlot = addIdentitySlot("local", "", localId, localNode, localOwner, localNodeName, "Local node");' in js
    assert "let selectedSlot = null;" in js
    assert 'selectedSlot = addIdentitySlot("selected", "", selectedTickerId, selectedTickerNode, null, selectedNodeName, "Selected node");' in js
    assert '? `${metricBaseTitle} • Click self or selected side to focus that node`' in js
    assert "nearestOfflineCityHintFromCoords(" in js
    assert 'source: "estimated",' in js
    assert "const cityRequests = [];" in js
    assert "addIdentityCityRequest(localSlot, localId, localNode, localOwner);" in js
    assert "addIdentityCityRequest(selectedSlot, selectedTickerId, selectedTickerNode, null);" in js
    assert "const cityRequestKey = String(++selfNodeNearestCityRenderSeq);" in js
    assert 'selfMetric.classList.add("self-node-value", "node-ticker-value");' in js
    assert "const identityFallbackGlyph = (label, nodeId) => {" in js
    assert "const identityWatermark = emoji || identityFallbackGlyph(displayName, cleanNodeId);" in js
    assert "slot.dataset.identityWatermark = identityWatermark;" in js
    assert 'slot.classList.toggle("has-fallback-watermark", !emoji);' in js
    assert 'selfCard.classList.remove("has-node-emoji", "has-dual-node-watermarks", "has-fallback-node-watermark");' in js
    assert 'nameRow.className = "self-node-name";' in js
    assert "nameRow.appendChild(statusText);" not in js
    assert 'statusGlyph.className = "chat-member-status-emoji-glyph";' not in js
    assert "if (!hasSelectedTickerNode && selfCard instanceof HTMLElement && identityWatermark) {" in js
    assert 'selfCard.classList.add("has-node-emoji");' in js
    assert 'selfCard.classList.toggle("has-fallback-node-watermark", !emoji);' in js
    assert "selfCard.dataset.nodeEmoji = identityWatermark;" in js
    assert 'nameText.className = "self-node-name-text";' in js
    assert 'statusText.className = "target-node-status status-unknown";' not in js
    assert 'statusText.id = "m-target-status-inline";' not in js
    assert 'idText.className = "self-node-id";' in js
    assert "slot.appendChild(idText);" in js
    assert 'cityText.className = "self-node-city";' in js
    assert 'selfMetric.dataset.cityRequestKey = cityRequestKey;' in js
    assert 'selfMetric.dataset.baseTitle = metricBaseTitle;' in js
    assert 'selfCard.dataset.baseTitle = cardBaseTitle;' in js
    assert 'selfMetric.textContent = targetDisplay;' in js
    assert "renderRadioStatus(state);" in js


def test_render_html_styles_node_identity_ticker() -> None:
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

    assert 'id="summary-ticker-self"' in html
    assert 'data-ticker-id="self"' in html
    assert '<div class="label" data-ticker-label>Self</div>' in html
    assert 'id="summary-ticker-radio"' in html
    assert 'data-ticker-id="radio"' in html
    assert 'id="m-radio-status"' in html
    assert 'id="ticker-radio"' in html
    assert 'id="ticker-delta-radio"' in html
    assert 'id="ticker-rate-radio"' in html
    assert 'id="ticker-chart-radio"' in html
    assert ".topbar .summary-ticker-item-self .value.self-node-value" in html
    assert ".topbar .summary-ticker-item-self.has-node-emoji::after" in html
    assert ".topbar .summary-ticker-item-self.has-node-emoji.has-fallback-node-watermark::after" in html
    assert "content: attr(data-node-emoji);" in html
    assert "--self-node-watermark-size: 82px;" in html
    assert "--self-node-watermark-local-x: calc((var(--self-node-watermark-size) / 2) + var(--self-node-watermark-edge-inset));" in html
    assert "--self-node-watermark-selected-x: calc(100% - ((var(--self-node-watermark-size) / 2) + var(--self-node-watermark-edge-inset)));" in html
    assert "--self-node-single-watermark-size: var(--self-node-watermark-size);" in html
    assert "--self-node-watermark-single-x: var(--self-node-watermark-local-x);" in html
    assert ".summary-ticker-item-self.has-dual-node-watermarks::before" in html
    assert ".summary-ticker-item-self.has-dual-node-watermarks::after" in html
    assert "content: attr(data-selected-node-emoji);" in html
    assert "content: attr(data-local-node-emoji);" in html
    assert ".summary-ticker-item-self > .label.is-dual-node-label" not in html
    assert "justify-content: space-between;" in html
    assert ".self-node-identity-slot {" in html
    assert ".self-node-slot-label {" in html
    assert ".value.self-node-value.is-dual-node-context" in html
    assert ".value.self-node-value.is-dual-node-context::after" in html
    assert "#m-self.self-node-value.is-dual-node-context" in html
    assert "grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);" in html
    assert "grid-template-columns: minmax(0, 1fr);" in html
    assert "grid-template-rows: minmax(14px, auto) 10px 11px;" in html
    assert ".self-node-identity-slot .self-node-name" in html
    assert ".self-node-identity-slot .self-node-id" in html
    assert "display: flex;" in html
    assert "display: block;" in html
    assert ".self-node-identity-slot .self-node-city[hidden]" in html
    assert ".self-node-identity-slot.profiled-node" in html
    assert ".summary-ticker-item-self.profiled-node" in html
    assert ".summary-ticker-item-self.has-selected-node" in html
    assert ".summary-ticker-item-self.has-selected-node .value.self-node-value.is-dual-node-context .self-node-identity-slot" in html
    assert ".summary-ticker-item-self.profiled-node:not(.has-selected-node) .value.self-node-value .self-node-identity-local.profiled-node" in html
    assert "color-mix(in srgb, var(--ui-panel) 46%, transparent)" in html
    assert "color-mix(in srgb, var(--surface-tint-bg-alt, var(--ui-panel)) 88%, transparent)" in html
    assert ".self-node-identity-local.profiled-node" in html
    assert "background: transparent !important;" in html
    assert ".summary-ticker-item-self.profiled-node.has-node-profile-watermark::before" in html
    assert ".summary-ticker-item-self.profiled-node.has-node-profile-watermark.has-node-emoji:not(.has-dual-node-watermarks)::after" in html
    assert ".self-node-identity-selected.profiled-node" in html
    assert "display: block !important;" in html
    assert "visibility: hidden;" in html
    assert ".self-node-identity-selected {" in html
    assert "position: relative;" in html
    assert "left: var(--self-node-watermark-local-x);" in html
    assert "left: var(--self-node-watermark-selected-x);" in html
    assert "font-size: var(--self-node-watermark-size);" in html
    assert "justify-content: center;" in html
    assert "flex: 0 1 auto;" in html
    assert "text-align: right;" in html
    assert ".self-node-identity-selected .self-node-city" in html
    assert '[data-theme="dark"] .topbar .summary-ticker-item-self.has-dual-node-watermarks::before' in html
    assert ".self-node-name {" in html
    assert ".self-node-status.chat-member-status {" in html
    assert ".self-node-name-text {" in html
    assert ".self-node-identity-slot::before" in html
    assert "content: attr(data-identity-watermark);" in html
    assert ".self-node-identity-slot.has-fallback-watermark::before" in html
    assert ".self-node-id {" in html
    assert ".self-node-city {" in html
    assert ".value.self-node-value.has-self-node-city" in html
    assert ".radio-ticker-status {" in html
    assert ".radio-ticker-status-line {" in html
    assert ".radio-ticker-traffic {" in html
    assert ".radio-ticker-detail {" in html


def test_node_ticker_activation_focuses_current_view() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    section = js.split("function bindLocalNodeSummaryCard()", 1)[1].split(
        "function bindChatReactionControls()",
        1,
    )[0]

    assert "const resolveSlotFocusTarget = (target) => {" in section
    assert "const kind = String(hit && hit.kind ? hit.kind : \"self\").trim().toLowerCase();" in section
    assert "if (kind === \"self\") {" in section
    assert "if (isSelectableNodeId(currentSelectedId) && currentSelectedId === localNodeId) {" in section
    assert "clearNodeSelection();" in section
    assert "selectNode(cleanNodeId, true, false);" in section


def test_self_ticker_id_uses_muted_light_mode_text() -> None:
    css = build_dashboard_css(theme_css="")
    target_id_section = css.split(
        ".topbar .summary-ticker-item-self .value.self-node-value .self-node-id {",
        1,
    )[1].split("}", 1)[0]

    assert "color-mix(in srgb, var(--ticker-text-muted) 84%, var(--ticker-text-strong) 16%)" in target_id_section
    assert "rgba(230, 248, 237, 0.84)" not in target_id_section


def test_self_ticker_id_is_inline_in_compact_mode_and_stacked_when_expanded() -> None:
    css = build_dashboard_css(theme_css="")
    target_item_section = css.split(
        ".topbar .summary-ticker-item-self,",
        1,
    )[1].split("}", 1)[0]
    compact_section = css.split(
        ".topbar .summary-ticker-item-self .value.self-node-value,",
        1,
    )[1].split("}", 1)[0]
    expanded_section = css.split(
        ".topbar.ticker-expanded .summary-ticker-item-self .value.self-node-value,",
        2,
    )[2].split("}", 1)[0]

    assert "grid-template-rows: auto;" in target_item_section
    assert "white-space: nowrap;" in compact_section
    assert "flex-direction: row;" in compact_section
    assert "align-items: center;" in compact_section
    assert "flex-direction: column;" in expanded_section
    assert "align-items: flex-start;" in expanded_section


def test_radio_ticker_uses_rx_tx_metric() -> None:
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

    assert 'id="m-radio"' in html
    assert 'id="m-radio-status"' in html
    assert 'id="ticker-radio"' in html
    assert '{ id: "radio", defaultLabel: "Radio", metric: true }' in js
    assert '{ id: "node", defaultLabel: "Signal", metric: true }' in js
    assert 'id="summary-ticker-node"' in html
    assert '<div class="label" data-ticker-label>Signal</div>' in html
    assert '<span class="settings-label">Signal rows</span>' in html
    assert "m-target-radio-status" not in js
    assert 'const radioMetric = document.getElementById("m-radio");' in js
    assert 'const radioStatusLine = document.getElementById("m-radio-status");' in js
    assert 'const radioCard = document.getElementById("summary-ticker-radio");' in js
    assert "function radioLinkStateFromState(state = latestState) {" in js
    assert "const link = (summary.radio_link && typeof summary.radio_link === \"object\")" in js
    assert "const radioLinkState = radioLinkStateFromState(safeState);" in js
    assert 'let key = radioLinkState.isConnected ? "online" : freshnessKey;' in js
    assert "const trafficMetricText = `RX ${trafficSnap.rxRecent} · TX ${trafficSnap.txRecent}`;" in js
    assert "const trafficMetricTotal = trafficSnap.rxRecent + trafficSnap.txRecent;" in js
    assert 'trafficEl.className = "radio-ticker-traffic";' in js
    assert 'trafficEl.textContent = trafficMetricText;' in js
    assert 'trafficEl.setAttribute("aria-label", `Radio ${inlineText}; ${trafficMetricText}`);' in js
    assert "radioMetric.title = joinTitleParts(trafficMetricText, inlineText, detailText, detailTitle);" in js
    assert 'radioStatusLine.className = `radio-ticker-status-line status-${key}`;' in js
    assert "radioStatusLine.textContent = inlineText;" in js
    assert 'radioStatusLine.setAttribute("aria-label", `Radio status ${inlineText}`);' in js
    assert "radioMetric.appendChild(statusEl);" not in js
    assert 'updateMetricTicker("radio_rx_tx_recent", trafficMetricTotal, {' in js
    assert 'containerId: "ticker-radio",' in js
    assert 'deltaId: "ticker-delta-radio",' in js
    assert 'rateId: "ticker-rate-radio",' in js
    assert 'chartId: "ticker-chart-radio",' in js
    assert 'stateProfile: "traffic_delta",' in js
    assert 'const el = document.getElementById("m-target-status-inline");' not in js


def test_radio_rx_tx_aligns_with_compact_link_value_and_status_is_prominent() -> None:
    css = build_dashboard_css(theme_css="")
    radio_expanded_section = css.rsplit(
        ".topbar.ticker-expanded .summary-ticker-item-radio .value.radio-ticker-value {",
        1,
    )[1].split("}", 1)[0]
    status_section = css.split(
        ".topbar .summary-ticker-item-radio .radio-ticker-status-line {",
        1,
    )[1].split("}", 1)[0]
    expanded_status_section = css.split(
        ".topbar.ticker-expanded .summary-ticker-item-radio .radio-ticker-status-line {",
        1,
    )[1].split("}", 1)[0]
    radio_metric_expanded_section = css.split(
        ".topbar.ticker-expanded .summary-ticker-item-radio .metric-ticker {",
        1,
    )[1].split("}", 1)[0]
    signal_compact_expanded_section = css.split(
        ".topbar.ticker-expanded .summary-ticker-item .value.node-ticker-value.is-compact {",
        1,
    )[1].split("}", 1)[0]
    link_expanded_section = css.split(
        ".topbar.ticker-expanded .summary-ticker-item#summary-ticker-node .value.node-ticker-value.is-compact {",
        1,
    )[1].split("}", 1)[0]
    radio_item_expanded_section = css.rsplit(
        ".topbar.ticker-expanded .summary-ticker-item-radio {",
        1,
    )[1].split("}", 1)[0]

    assert "grid-template-columns: auto minmax(0, 1fr);" in radio_item_expanded_section
    assert "grid-template-rows: auto auto auto;" in radio_item_expanded_section
    assert "grid-column: 1 / -1;" in radio_expanded_section
    assert "grid-row: 2;" in radio_expanded_section
    assert "justify-self: start;" in radio_expanded_section
    assert "font-size: 18px;" in radio_expanded_section
    assert "line-height: 1.1;" in radio_expanded_section
    assert "text-align: left;" in radio_expanded_section
    assert "grid-column: 1;" in status_section
    assert "font-size: 11px;" in status_section
    assert "grid-column: 2;" in expanded_status_section
    assert "grid-row: 1;" in expanded_status_section
    assert "font-size: 14px;" in expanded_status_section
    assert "grid-column: 1 / -1;" in radio_metric_expanded_section
    assert "grid-row: 3;" in radio_metric_expanded_section
    assert "grid-row: 2;" in signal_compact_expanded_section
    assert "font-size: 18px;" in link_expanded_section
