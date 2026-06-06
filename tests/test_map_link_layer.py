import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.history_readers import decode_connections_rows
from meshdash.html_css import build_dashboard_css
from meshdash.html_js import build_dashboard_js
from meshdash.html_sections import build_html_shell
from meshdash.tracker_edges import record_direct_edge_observation
from meshdash.tracker_history_edges import build_historical_edges
from meshdash.tracker_snapshot import build_edge_snapshot_rows


def test_dashboard_html_adds_map_link_layer_toggle() -> None:
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

    assert 'id="map-lines-wrap"' not in html
    assert 'id="map-lines-toggle"' not in html
    assert 'id="map-link-mode-wrap"' not in html
    assert 'id="map-link-mode"' not in html
    assert 'id="map-link-legend"' in html
    assert 'aria-label="Map links legend"' in html
    assert ">Packet Lines</span>" not in html
    assert "Choose whether the link layer shows history links, live links, or both" not in html
    assert 'class="map-control-group map-heatmap-controls"' in html


def test_dashboard_js_supports_map_link_layer_overlay() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'let mapLinkLayerMode = "none";' in js
    assert 'let mapLiveActivityEnabled = true;' in js
    assert 'const nodePacketSeriesDefaults = {' in js
    assert 'all: false,' in js
    assert 'chat: true,' in js
    assert 'telemetry: true,' in js
    assert 'position: true,' in js
    assert 'routing: true,' in js
    assert 'storeforward: true,' in js
    assert 'nodeinfo: true,' in js
    assert 'admin: true,' in js
    assert 'encrypted: true,' in js
    assert 'other: true,' in js
    assert 'let nodePacketSeriesEnabled = { ...nodePacketSeriesDefaults };' in js
    assert "function normalizeNodePacketSeries(raw) {" in js
    assert 'const mapPacketLinesStorageKey = "meshDashboardMapPacketLinesEnabledV1";' in js
    assert 'const mapLinkModeStorageKey = "meshDashboardMapLinkModeV1";' in js
    assert 'const mapLiveActivityStorageKey = "meshDashboardMapLiveActivityEnabledV1";' in js
    assert "function updateMapPacketLinesControl()" in js
    assert "function bindMapPacketLinesControl()" in js
    assert "function updateMapLinkLayerControl()" in js
    assert "function normalizeMapLinkLayerMode(value) {" in js
    assert "function loadMapPacketLinesPreference()" in js
    assert "function loadMapLinkLayerModePreference()" in js
    assert "function bindMapLinkLayerControl()" in js
    assert "function updateMapLiveActivityControl()" in js
    assert "function loadMapLiveActivityPreference()" in js
    assert "function bindMapLiveActivityControl()" in js
    assert "let mapLinkLegendOffsetRaf = null;" in js
    assert "function mapLinkLayerModeParts(modeName = mapLinkLayerMode)" in js
    assert 'estimated: mode !== "none",' in js
    assert "function renderMapLinkLegend(nodes = [], rawEdges = [], estimatedPositions = new Map(), linkOverlay = null)" in js
    assert "function bindMapLinkLegendControls(legend)" in js
    assert 'data-map-link-legend-toggle="packet"' in js
    assert 'data-map-link-legend-toggle="estimated"' in js
    assert "Map layers" in js
    assert "Signal heatmap" in js
    assert "Estimate heatmap" in js
    assert "const signalHeatLegendHtml = signalHeatPointCount > 0" in js
    assert "const estimatedCloudHeatLegendHtml = showEstimatedCloudHeat" in js
    assert "Estimated links" in js
    assert 'renderMapLinkLegend(nodes, mapRenderEdges, estimatedPositions, linkOverlay);' in js
    assert 'mapElement.style.setProperty("--map-link-legend-space"' in js
    assert "networkSubviewUsesMap(activeNetworkSubview)" in js
    assert "mapLinkLayerModeForCurrentView(mapLinkLayerMode)" in js
    assert "networkGraphRawEdgesForMode(edges, spreadEdgeMode)" not in js
    assert "const mapRenderEdges = edges;" in js
    assert 'const effectiveMapLinkMode = (typeof mapLinkLayerModeForCurrentView === "function")' in js
    assert '? (spreadEdgeMode === "live" ? "live" : "history")' not in js
    assert "lastMapSignature = \"\";" in js
    assert "Estimated nodes" in js
    assert "Real nodes" in js
    assert "Real links" in js
    assert 'mapLiveActivityEnabled = true;' in js
    assert 'wrap.hidden = true;' in js
    assert 'toggle.checked = true;' in js
    assert 'toggle.disabled = true;' in js
    assert "function estimatedMarkerStyle(isSelected, confidence = 0.5, isLocal = false)" in js
    assert "function buildMapLinkLayerOverlay(nodes, rawEdges, options = null)" in js
    assert "function buildMapLinkEstimateDensityOverlay(linkOverlay, options = null)" in js
    assert "const signalHeatmapGradientCoverage = {" in js
    assert "const signalHeatmapGradientLiveContrast = {" in js
    assert "function resolveSignalHeatGradient(mode = signalHeatmapMode) {" in js
    assert "Signal heatmap uses a warm colorblind-friendly palette; link-cloud heatmaps stay blue." in js
    assert "const gradient = resolveSignalHeatGradient(signalHeatmapMode);" in js
    assert 'let lastSignalHeatmapSignature = "";' in js
    assert "const heatSignature = `signal-heatmap:${(heatSignatureHash >>> 0).toString(16)}`;" in js
    assert "heatSignature === lastSignalHeatmapSignature && heatLayerPresenceMatches" in js
    assert "hideEstimatedMarkers: false," in js
    assert "hideEstimatedMarkers: clouds.length > 0," in js
    assert "cloudLinks" in js
    assert "cloudLink: true," in js
    assert "nodeMarkerKinds" in js
    assert "nodeMarkerConfidence" in js
    assert "linkEstimateLayer" in js
    assert "let linkEstimateHeatmapLayer = null;" in js
    assert 'const linkEstimateHeatmapPaneName = "linkEstimateHeatmapPane";' in js
    assert "function syncLinkEstimateHeatmapLayer(linkDensity = null, show = false)" in js
    assert "clearLinkEstimateHeatmapLayer();" in js
    assert "syncLinkEstimateHeatmapLayer(linkDensity, true);" in js
    assert "const hideEstimatedLinkDots = !!(" in js
    assert "if (hideEstimatedLinkDots && isEstimated) {" in js
    assert 'Estimated nodes${hideLinkedDots ? " (hidden)" : ""}' in js
    assert "estimateLine && estimateLine.avgHops ??" not in js
    assert "estimateLine && estimateLine.avgSnr ??" not in js
    assert "estimateLine && estimateLine.avgRssi ??" not in js
    assert "No earlier links focus yet" in js
    assert "Links view is already centered on the local node" in js


def test_dashboard_js_suppresses_map_hover_tooltip_while_popup_is_open() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "const closeHoverTooltip = () => {" in js
    assert "const removeHoverTooltip = () => {" in js
    assert 'return !!(typeof marker.isPopupOpen === "function" && marker.isPopupOpen());' in js
    assert "const overlayNodeId = normalizeNodeId(opts.nodeId || (node && node.id) || \"\");" in js
    assert "const hoverTooltipSuppressed = () => {" in js
    assert "!!opts.suppressHoverTooltip || popupIsOpen() || !!(overlayNodeId && selectedId === overlayNodeId)" in js
    assert 'marker.on("popupopen", removeHoverTooltip);' in js
    assert 'marker.on("click", removeHoverTooltip);' in js
    assert 'if (typeof marker.bindTooltip === "function" && !hoverTooltipSuppressed()) {' in js
    assert "if (hoverTooltipSuppressed()) {" in js
    assert "removeHoverTooltip();\n            return;" in js
    assert "if (isSelected) {" in js
    assert "marker.unbindTooltip();" in js
    assert "suppressHoverTooltip: true," in js
    assert "suppressHoverTooltip: isSelected," in js


def test_dashboard_js_binds_programmatic_map_popup_actions() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "function handleMapNodePopupActionClick(clickEv, fallbackNodeId = \"\", closePopupFn = null)" in js
    assert "function bindMapNodePopupActionDelegates()" in js
    assert 'document.body.dataset.mapNodePopupActionsBound = "1";' in js
    assert 'document.addEventListener("click", (clickEv) => {' in js
    assert "handleMapNodePopupActionClick(clickEv);" in js
    assert 'runBootStep("bindMapNodePopupActionDelegates", () => bindMapNodePopupActionDelegates());' in js
    assert "handleMapNodePopupActionClick(clickEv, overlayNodeId, () => {" in js
    assert 'data-map-node-action="${escAttr(cleanAction)}"' in js
    assert 'mapNodePopupActionButtonHtml("Message", "message", actionNodeId)' in js
    assert 'mapNodePopupActionButtonHtml("Trace", "trace", actionNodeId)' in js
    assert 'mapNodePopupActionButtonHtml("Open details", "details", actionNodeId)' in js


def test_dashboard_js_map_popup_actions_use_node_drawer_without_leaving_map() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    action_start = js.index("function runMapNodePopupAction(")
    action_end = js.index("function handleMapNodePopupActionClick(", action_start)
    action_block = js[action_start:action_end]

    message_start = action_block.index('if (cleanAction === "message") {')
    trace_start = action_block.index('if (cleanAction === "trace") {')
    details_start = action_block.index('if (cleanAction === "details") {')
    message_block = action_block[message_start:trace_start]
    trace_block = action_block[trace_start:details_start]

    assert 'applyLayoutView("network", true);' in message_block
    assert 'setActiveNetworkSubview("map", { persist: true });' in message_block
    assert 'selectNode(nodeId, true, false);' in message_block
    assert 'setChatNodeDetailsDrawerTab("messages", { fetchHistory: false });' in message_block
    assert 'tab: "messages",' in message_block
    assert 'setChatNodeDetailsDrawerTab("chat"' not in message_block
    assert 'applyLayoutView("chat", true);' not in message_block
    assert "peerDmActivePeerId = nodeId;" not in message_block

    assert 'applyLayoutView("network", true);' in trace_block
    assert 'setActiveNetworkSubview("map", { persist: true });' in trace_block
    assert 'selectNode(nodeId, true, false);' in trace_block
    assert 'setChatNodeDetailsDrawerTab("telemetry", { fetchHistory: false });' in trace_block
    assert 'tab: "telemetry",' in trace_block
    assert 'void runChatNodeTelemetryTool("traceroute", nodeId);' in trace_block
    assert "openNetworkRoutesLiveTrace(nodeId" not in trace_block
    assert 'setActiveNetworkSubview("routes", { persist: true });' not in trace_block


def test_dashboard_js_does_not_show_native_map_wheel_title_tooltip() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'mapFrameElement.removeAttribute("title");' in js
    assert 'mapFrameElement.setAttribute(\n            "aria-label",' in js
    assert 'mapFrameElement.setAttribute("aria-label", "Map scroll wheel zoom enabled.");' in js
    assert 'mapFrameElement.setAttribute("title", "Scroll wheel zoom is enabled.");' not in js


def test_dashboard_css_positions_map_link_legend_below_zoom() -> None:
    css = build_dashboard_css(theme_css="")

    assert ".map-link-legend {" in css
    assert "#network-map-panel-map #map .leaflet-bottom.leaflet-left {" in css
    assert "bottom: var(--map-link-legend-space, 0px);" in css
    assert ".map-link-legend-input {" in css
    assert ".map-link-legend-swatch.is-node-linked::before {" in css
    assert ".map-link-legend-swatch.is-link-heat::before {" in css
    assert ".map-link-legend-swatch.is-signal-heat::before" in css
    assert ".map-link-legend-swatch.is-cloud-heat::before" in css


def test_dashboard_js_keeps_leaflet_tile_layers_removable_on_theme_swap() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "mapTileLayer.off();" not in js
    assert "settingsFixedMapTileLayer.off();" not in js


def test_dashboard_js_packet_line_fade_tracks_node_freshness_windows() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "const onlineWindowSec = Math.max(0, Number(chatWarnWindowSeconds) || (10 * 60));" in js
    assert "const staleWindowSec = Math.max(" in js
    assert "Number(chatStaleWindowSeconds) || (30 * 60)" in js
    assert "const fadeStartSec = 45 * 60;" not in js
    assert "const fadeFullSec = 24 * 60 * 60;" not in js
    assert "const minOpacity = isReal ? 0.56 : 0.44;" in js
    assert "Math.max(isReal ? 2.2 : 1.7, baseWeight * 0.62)" in js
    assert 'lineCap: "round"' in js
    assert 'lineJoin: "round"' in js


def test_dashboard_js_flashes_network_map_nodes_on_new_packet_activity() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "const mapNodeActivityFlashById = new Map();" in js
    assert "let mapNodeActivityFlashRaf = null;" in js
    assert "let lastNetworkMapPacketTokens = new Set();" in js
    assert "function isNetworkMapActivityFlashVisible()" in js
    assert "function mapPacketActivityToken(packetEntry)" in js
    assert "function mapPacketActivityNodeIds(packetEntry)" in js
    assert "function snapshotNetworkMapPacketActivityTokens(state = latestState)" in js
    assert "function seedNetworkMapPacketActivityTokens(state = latestState)" in js
    assert 'function resolveMapNodeMarkerStyle(nodeId, isSelected, markerKind = "actual", markerConfidence = 0.45, state = latestState)' in js
    assert 'const isLocal = !!(localNodeId && normalizeNodeId(nodeId || "") === localNodeId);' in js
    assert "function scheduleMapNodeActivityFlashUpdate()" in js
    assert "function syncNetworkMapPacketActivity(state = latestState)" in js
    assert "!!mapLiveActivityEnabled" in js
    assert "mapNodeActivityFlashById.set(nodeId, {" in js
    assert "scheduleMapNodeActivityFlashUpdate();" in js
    assert "if (mapLiveActivityEnabled)" in js
    assert "syncNetworkMapPacketActivity(state);" in js


def test_record_direct_edge_observation_tracks_signal_metrics() -> None:
    session_edges: dict[tuple[str, str], dict[str, object]] = {}
    historical_edges: dict[tuple[str, str], dict[str, object]] = {}

    record_direct_edge_observation(
        session_edges=session_edges,
        historical_edges=historical_edges,
        from_id="!a",
        to_id="!b",
        rx_time=100,
        portnum="NODEINFO_APP",
        hops=1,
        rx_snr=7.5,
        rx_rssi=-91,
        include_live_count=True,
    )
    record_direct_edge_observation(
        session_edges=session_edges,
        historical_edges=historical_edges,
        from_id="!a",
        to_id="!b",
        rx_time=110,
        portnum="NODEINFO_APP",
        hops=2,
        rx_snr=1.5,
        rx_rssi=-101,
        include_live_count=True,
    )

    edge = session_edges[("!a", "!b")]
    assert edge["snr_count"] == 2
    assert edge["snr_sum"] == 9.0
    assert edge["snr_min"] == 1.5
    assert edge["snr_max"] == 7.5
    assert edge["rssi_count"] == 2
    assert edge["rssi_sum"] == -192.0
    assert edge["rssi_min"] == -101.0
    assert edge["rssi_max"] == -91.0

    hist_edge = historical_edges[("!a", "!b")]
    assert hist_edge["snr_count"] == 2
    assert hist_edge["rssi_count"] == 2


def test_decode_connections_rows_and_snapshot_expose_link_signal_rollups() -> None:
    decoded_rows = decode_connections_rows(
        [
            (
                "!11111111",
                "!22222222",
                100,
                220,
                6,
                '["NODEINFO_APP","TEXT_MESSAGE_APP"]',
                1,
                7,
                6,
                18.0,
                3,
                2.0,
                9.0,
                -282.0,
                3,
                -104.0,
                -86.0,
            )
        ]
    )

    historical_edges = build_historical_edges(decoded_rows)
    edge_rows, real_edge_count = build_edge_snapshot_rows(
        session_edges={},
        historical_edges=historical_edges,
        nodes_by_id={},
        min_real_link_count=2,
        format_epoch_fn=lambda value: value,
    )

    assert real_edge_count == 1
    assert len(edge_rows) == 1
    row = edge_rows[0]
    assert row["avg_snr"] == 6.0
    assert row["snr_samples"] == 3
    assert row["snr_min"] == 2.0
    assert row["snr_max"] == 9.0
    assert row["avg_rssi"] == -94.0
    assert row["rssi_samples"] == 3
    assert row["rssi_min"] == -104.0
    assert row["rssi_max"] == -86.0


def test_snapshot_falls_back_to_live_signal_metrics_when_history_has_none() -> None:
    session_edges = {
        ("!aaaa0001", "!bbbb0002"): {
            "from": "!aaaa0001",
            "to": "!bbbb0002",
            "count": 2,
            "first_rx_time": 100,
            "last_rx_time": 160,
            "portnums": {"NODEINFO_APP"},
            "last_hops": 1,
            "hops_sum": 2,
            "hops_count": 2,
            "snr_sum": 12.0,
            "snr_count": 2,
            "snr_min": 4.0,
            "snr_max": 8.0,
            "rssi_sum": -186.0,
            "rssi_count": 2,
            "rssi_min": -95.0,
            "rssi_max": -91.0,
        }
    }
    historical_edges = {
        ("!aaaa0001", "!bbbb0002"): {
            "from": "!aaaa0001",
            "to": "!bbbb0002",
            "count": 9,
            "first_rx_time": 50,
            "last_rx_time": 90,
            "portnums": {"NODEINFO_APP"},
            "last_hops": 1,
            "hops_sum": 9,
            "hops_count": 9,
            "snr_sum": 0.0,
            "snr_count": 0,
            "snr_min": None,
            "snr_max": None,
            "rssi_sum": 0.0,
            "rssi_count": 0,
            "rssi_min": None,
            "rssi_max": None,
        }
    }

    edge_rows, real_edge_count = build_edge_snapshot_rows(
        session_edges=session_edges,
        historical_edges=historical_edges,
        nodes_by_id={},
        min_real_link_count=2,
        format_epoch_fn=lambda value: value,
    )

    assert real_edge_count == 1
    row = edge_rows[0]
    assert row["lifetime_count"] == 9
    assert row["session_count"] == 2
    assert row["avg_snr"] == 6.0
    assert row["avg_rssi"] == -93.0
    assert row["snr_samples"] == 2
    assert row["rssi_samples"] == 2
