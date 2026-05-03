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


def test_dashboard_js_defaults_live_update_ticker_to_disabled() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "update_ticker_enabled: false," in js
    assert "raw.update_ticker_enabled" in js
    assert "function topbarUpdateTickerEnabled() {" in js
    assert "prefs.update_ticker_enabled = !!liveUpdateToggle.checked;" in js
    assert "topbarUpdateTickerHasRenderableContent" not in js
    assert "if (topbarUpdateTickerEnabled()) {" in js
    assert "setTopbarUpdateTickerVisibility(tickerEl, topbarUpdateTickerEnabled());" in js
    assert "if (!topbarUpdateTickerEnabled()) {" in js
    assert "Ticker preferences saved locally." not in js
    assert "Live update ticker shown." not in js
    assert "Live update ticker hidden." not in js
    assert "Ticker preferences reset to defaults." not in js


def test_dashboard_js_defaults_unique_node_colors_to_off() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "let settingsUniqueNodeColorsEnabled = false;" in js
    assert re.search(
        r"settingsUniqueNodeColorsEnabled = parseBoolToken\(\s*window\.localStorage\.getItem\(settingsUniqueNodeColorsStorageKey\),\s*false\s*\);",
        js,
    )


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
    assert 'summary.real_edge_count ?? summary.live_link_count ?? summary.real_links' in js
    assert 'updateMetricTicker("links", linksMetricValue, {' in js
    assert 'containerId: "ticker-links",' in js
    assert 'id="summary-ticker-links"' in html
    assert 'data-ticker-id="links"' in html
    assert '<div class="label" data-ticker-label>Links</div>' in html
    assert 'id="m-links"' in html
    assert 'id="ticker-chart-links"' in html


def test_compact_tickers_can_open_full_width_detail_tray() -> None:
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

    assert 'id="summary-ticker-detail-tray"' in html
    assert 'id="summary-ticker-detail-label"' in html
    assert 'id="summary-ticker-detail-value"' in html
    assert 'id="summary-ticker-detail-chart"' in html
    assert 'id="summary-ticker-detail-close"' in html
    assert 'function bindCompactTickerDetailTrayControls() {' in js
    assert 'function toggleCompactTickerDetail(id) {' in js
    assert 'return !!id && id !== "self";' in js
    assert 'topbarElement.classList.contains("ticker-expanded")' in js
    assert 'row.addEventListener("click", (ev) => {' in js
    assert 'row.addEventListener("keydown", (ev) => {' in js
    assert 'refreshCompactTickerDetailTray();' in js
    assert ".summary-ticker-detail-tray {" in css
    assert "grid-template-columns: minmax(0, 1fr) minmax(168px, 32vw) auto;" in css
    assert ".topbar.ticker-expanded .summary-ticker-detail-tray {" in css


def test_dashboard_js_merges_summary_hydration_with_persisted_ticker_series() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'function mergeMetricTickerSeries(metricKey, incomingSeries, cutoffMs = Date.now() - metricTickerWindowMs) {' in js
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
        r"\.topbar \.sub \.summary-ticker-row \{\s*display: grid;\s*grid-auto-flow: column;\s*grid-auto-columns: minmax\(124px, 1fr\);\s*gap: 5px;",
        html,
    )
    assert re.search(
        r"\.topbar\.ticker-expanded \.sub \.summary-ticker-row \{\s*display: flex;\s*flex-wrap: wrap;\s*align-items: stretch;",
        html,
    )
    assert "flex: 1 1 min(208px, 100%);" in html
    assert ".topbar.ticker-expanded.ticker-wrap-balanced .summary-ticker-item {" in html
    assert "flex-basis: min(330px, 100%);" in html
    assert re.search(
        r"\.topbar \.summary-ticker-item \{\s*border: 1px solid .*?\s*background: var\(--panel\);\s*border-radius: 7px;\s*padding: 4px 7px;\s*min-width: 0;\s*color: var\(--ink\);\s*display: grid;\s*grid-template-columns: minmax\(54px, auto\) minmax\(0, 1fr\) auto;\s*grid-template-rows: auto;",
        html,
    )
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
    assert "grid-auto-columns: minmax(168px, 82vw);" in html
    assert "scroll-snap-type: x proximity;" in html
    assert ".topbar .summary-ticker-item {" in html
    assert "scroll-snap-align: start;" in html


def test_render_html_exposes_live_update_ticker_toggle_in_settings() -> None:
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

    assert 'id="settings-ticker-live-update-enabled"' in html
    assert "Show live update ticker" in html
    assert "sideways scrolling live-update bar" in html


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
    assert 'const selectedTickerId = normalizeNodeId(selectedNodeId || "");' in js
    assert "const hasSelectedTickerNode = isSelectableNodeId(selectedTickerId);" in js
    assert "const tickerNodeId = hasSelectedTickerNode ? selectedTickerId : localId;" in js
    assert "const tickerShowsSelf = !hasSelectedTickerNode || tickerIsLocal;" in js
    assert 'selfCard.classList.toggle("has-selected-node", hasSelectedTickerNode);' in js
    assert 'selfLabel.textContent = tickerShowsSelf ? "Self" : "Node";' in js
    assert "if (isSelectableNodeId(tickerNodeId))" in js
    assert 'selfCard.setAttribute("aria-label", `Select node ${tickerNodeName || tickerNodeId}`);' in js
    assert 'const cardBaseTitle = `${metricBaseTitle} • Click to select in node list`;' in js
    assert "nearestOfflineCityHintFromCoords(" in js
    assert 'source: "linked",' in js
    assert 'selfMetric.classList.add("self-node-value", "node-ticker-value");' in js
    assert 'nameRow.className = "self-node-name";' in js
    assert "nameRow.appendChild(statusText);" not in js
    assert 'statusGlyph.className = "chat-member-status-emoji-glyph";' not in js
    assert 'selfCard.classList.toggle("has-node-emoji", !!selfEmoji);' in js
    assert "selfCard.dataset.nodeEmoji = selfEmoji;" in js
    assert 'nameText.className = "self-node-name-text";' in js
    assert 'statusText.className = "target-node-status status-unknown";' not in js
    assert 'statusText.id = "m-target-status-inline";' not in js
    assert 'idText.className = "self-node-id";' in js
    assert "nameRow.appendChild(idText);" in js
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
    assert ".topbar .summary-ticker-item-self.has-selected-node {" in html
    assert ".topbar .summary-ticker-item-self.has-selected-node::before" in html
    assert '[data-theme="dark"] .topbar .summary-ticker-item-self.has-selected-node {' in html
    assert ".topbar .summary-ticker-item-self.has-node-emoji::after" in html
    assert "content: attr(data-node-emoji);" in html
    assert ".self-node-name {" in html
    assert ".self-node-status.chat-member-status {" in html
    assert ".self-node-name-text {" in html
    assert ".self-node-id {" in html
    assert ".self-node-city {" in html
    assert ".value.self-node-value.has-self-node-city" in html
    assert ".radio-ticker-status {" in html
    assert ".radio-ticker-status-line {" in html
    assert ".radio-ticker-traffic {" in html
    assert ".radio-ticker-detail {" in html


def test_node_ticker_activation_toggles_selection() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    section = js.split("function bindLocalNodeSummaryCard()", 1)[1].split(
        "function bindChatReactionControls()",
        1,
    )[0]

    assert "selectNode(nodeId, true, true);" in section


def test_self_ticker_id_uses_muted_light_mode_text() -> None:
    css = build_dashboard_css(theme_css="")
    target_id_section = css.split(
        ".topbar .summary-ticker-item-self .value.self-node-value .self-node-id {",
        1,
    )[1].split("}", 1)[0]

    assert "color-mix(in srgb, var(--muted) 84%, var(--ink) 16%)" in target_id_section
    assert "rgba(230, 248, 237, 0.84)" not in target_id_section


def test_self_ticker_id_is_inline_in_compact_mode_and_stacked_when_expanded() -> None:
    css = build_dashboard_css(theme_css="")
    target_item_section = css.split(
        ".topbar .summary-ticker-item-self,",
        1,
    )[1].split("}", 1)[0]
    compact_section = css.split(
        ".topbar .summary-ticker-item-self .value.self-node-value,",
        2,
    )[2].split("}", 1)[0]
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
    link_expanded_section = css.split(
        ".topbar.ticker-expanded .summary-ticker-item#summary-ticker-node .value.node-ticker-value.is-compact {",
        1,
    )[1].split("}", 1)[0]

    assert "grid-column: 2;" in radio_expanded_section
    assert "grid-row: 1;" in radio_expanded_section
    assert "font-size: 18px;" in radio_expanded_section
    assert "line-height: 1.1;" in radio_expanded_section
    assert "text-align: right;" in radio_expanded_section
    assert "grid-column: 1;" in status_section
    assert "font-size: 11px;" in status_section
    assert "font-size: 14px;" in expanded_status_section
    assert "font-size: 18px;" in link_expanded_section
