import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_css import build_dashboard_css
from meshdash.html_js import build_dashboard_js
from meshdash.html_sections import build_html_shell


def test_dashboard_html_adds_network_graph_subview() -> None:
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

    assert 'data-network-subview="graph"' in html
    assert 'id="network-map-panel-graph"' in html
    assert 'data-network-subview="diagnostics"' in html
    assert 'hidden disabled aria-hidden="true"' in html
    assert 'id="network-map-panel-diagnostics"' in html
    assert 'hidden aria-hidden="true"' in html
    assert 'id="network-graph-svg"' in html
    assert 'id="network-graph-back-btn"' in html
    assert 'id="network-graph-home-btn"' in html
    assert 'id="network-graph-reset-view-btn"' in html
    assert 'id="network-graph-live-toggle"' in html
    assert 'id="network-graph-summary"' in html
    assert 'id="network-graph-legend"' in html
    assert 'id="network-diagnostics-window"' in html
    assert 'id="network-diagnostics-senders"' in html
    assert 'id="network-diagnostics-entries"' in html


def test_dashboard_html_shows_network_diagnostics_when_debug_mode_enabled() -> None:
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
        network_diagnostics_tab_hidden_attrs="",
        network_diagnostics_panel_hidden_attrs="",
    )

    assert 'data-network-subview="diagnostics"' in html
    assert '>Diagnostics</button>' in html


def test_dashboard_js_supports_network_graph_subview() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'const networkDiagnosticsEnabled = !!Number(0);' in js
    assert 'if (clean === "diag") return networkDiagnosticsEnabled ? "diagnostics" : "map";' in js
    assert 'if (clean === "diagnostics") return networkDiagnosticsEnabled ? "diagnostics" : "map";' in js
    assert 'function renderNetworkGraphView(state = latestState)' in js
    assert 'function refreshNetworkDiagnosticsPanel(force = false)' in js
    assert 'fetch(`/api/history/malformed?${params.toString()}`' in js
    assert 'name: "maltext"' in js
    assert 'activeNetworkSubview === "graph"' in js
    assert 'activeLayoutView !== "network"\n          || activeNetworkSubview === "map"' in js
    assert 'let networkGraphRootNodeId = "";' in js
    assert 'const networkGraphRootHistory = [];' in js
    assert 'const networkGraphViewState = {' in js
    assert 'emptyRetryTimer: null,' in js
    assert 'emptyRetryCount: 0,' in js
    assert 'pendingEntryViewportSync: false,' in js
    assert 'pendingModeViewportSync: false,' in js
    assert 'function bindNetworkGraphInteractions(svg)' in js
    assert 'function getNetworkGraphStageAspectRatio(svg = null)' in js
    assert 'function isNetworkGraphPointVisible(viewBox, x, y, paddingRatio = 0.08)' in js
    assert 'function cancelNetworkGraphViewAnimation()' in js
    assert 'function cancelNetworkGraphSceneAnimation()' in js
    assert 'function clearNetworkGraphEmptyRetry()' in js
    assert 'function scheduleNetworkGraphEmptyRetry()' in js
    assert 'function animateNetworkGraphViewBox(svg, rawViewBox, options = {})' in js
    assert 'function buildNetworkGraphSceneMarkup(scene)' in js
    assert 'function animateNetworkGraphScene(svg, fromLayout, toLayout, options = {})' in js
    assert 'function buildNetworkGraphNodeSignalMeta(nodeMap, recentPackets)' in js
    assert 'const networkGraphModeStorageKey = "meshDashboardNetworkGraphModeV1";' in js
    assert 'let networkGraphEdgeMode = "history";' in js
    assert 'function normalizeNetworkGraphEdgeMode(raw)' in js
    assert 'function loadPreferredNetworkGraphEdgeMode()' in js
    assert 'function persistPreferredNetworkGraphEdgeMode(modeName)' in js
    assert 'const networkGraphZoomBounds = Object.freeze({ minScale: 0.42, maxScale: 5.5 });' in js
    assert 'function networkGraphNodeHasLinkPeers(nodeId, adjacency, nodeMap = null)' in js
    assert 'function buildNetworkGraphPlaceholderNode(nodeId, caps = null)' in js
    assert 'function buildNetworkGraphNodeMap(nodes, historyCapsRaw, rawEdges, options = {})' in js
    assert 'const includeAllLiveNodes = !(options && options.includeAllLiveNodes === false);' in js
    assert 'const pinnedNodeIds = Array.isArray(options && options.pinnedNodeIds)' in js
    assert 'function filterNetworkGraphRawEdgesByMode(rawEdges, mode = networkGraphEdgeMode)' in js
    assert 'function doesNetworkGraphViewBoxContainBounds(viewBox, bounds, paddingRatio = 0.04)' in js
    assert 'function syncNetworkGraphModeToggle()' in js
    assert 'function bindNetworkGraphSummaryControls()' in js
    assert 'function setNetworkGraphEdgeMode(modeName, options = {})' in js
    assert 'function setNetworkGraphRootNode(nodeId, options = {})' in js
    assert 'function navigateNetworkGraphBack()' in js
    assert 'function focusNetworkGraphNodeFromSelection(nodeId, options = {})' in js
    assert 'function recenterNetworkGraphView(svg, options = {})' in js
    assert 'const localNodeHasLinkPeers = localNodeAvailable' in js
    assert 'if (localNodeAvailable && (localNodeHasLinkPeers || bestDegree <= 0)) {' in js
    assert 'Object.entries((historyCapsRaw && typeof historyCapsRaw === "object") ? historyCapsRaw : {})' in js
    assert 'buildNetworkGraphPlaceholderNode(clean, historyCapsById.get(clean) || null)' in js
    assert 'const filteredRawEdges = filterNetworkGraphRawEdgesByMode(rawEdges, edgeMode);' in js
    assert 'const filteredRawEdges = filterNetworkGraphRawEdgesByMode(rawEdges, networkGraphEdgeMode);' in js
    assert 'includeAllLiveNodes: edgeMode !== "live",' in js
    assert 'includeAllLiveNodes: normalizeNetworkGraphEdgeMode(networkGraphEdgeMode) !== "live",' in js
    assert 'const nodeMap = buildNetworkGraphNodeMap(nodes, historyCaps, filteredRawEdges, {' in js
    assert 'const nodeMap = buildNetworkGraphNodeMap(liveNodes, historyCaps, filteredRawEdges, {' in js
    assert 'const parsedWeight = useSessionWeight ? parsedSession : parsedLifetime;' in js
    assert 'empty.textContent = edgeMode === "live"' in js
    assert '<button id="network-graph-mode-chip" class="network-graph-chip network-graph-mode-chip"' in js
    assert 'bindNetworkGraphSummaryControls();' in js
    assert 'Avg packet hops: ${edge.avgHops == null ? "n/a" : edge.avgHops}' in js
    assert '${item.layer} hop${item.layer === 1 ? "" : "s"} away' in js
    assert 'last packet hops away:' in js
    assert 'label: `${layer} hop${layer === 1 ? "" : "s"}`,' in js
    assert 'Switch Links view between stored history topology and the current session topology' in js
    assert '<span class="network-graph-chip-label">1 Hop</span>' in js
    assert 'Numbered hop rings show shortest graph distance from the current root, not literal packet-route hops.' in js
    assert 'const networkGraphActive304 = activeLayoutView === "network" && activeNetworkSubview === "graph";' in js
    assert 'const weeklySummaryPromise = (activeLayoutView === "history" || activeLayoutView === "network")' in js
    assert 'if (weeklySummaryPromise) {' in js
    assert 'const networkGraphActive = next === "network" && activeNetworkSubview === "graph";' in js
    assert 'const fittedViewBox = fitNetworkGraphViewBoxToBounds(networkGraphViewState.bounds, svg);' in js
    assert 'const rootChanged = networkGraphViewState.lastRootId !== rootId;' in js
    assert '&& !doesNetworkGraphViewBoxContainBounds(networkGraphViewState.viewBox, networkGraphViewState.bounds, 0.05)' in js
    assert 'const shouldRefitForModeChange = !!(' in js
    assert 'animateNetworkGraphViewBox(svg, fittedViewBox);' in js
    assert 'Broadcast only' in js
    assert 'is-broadcast-only' in js
    assert 'pointerDownNodeId' in js
    assert 'svg.addEventListener("wheel"' in js
    assert 'cancelNetworkGraphViewAnimation();' in js
    assert 'svg.addEventListener("pointerup", finishPan);' in js


def test_dashboard_js_allows_diagnostics_subview_in_debug_mode() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
        debug_mode=True,
    )

    assert 'const networkDiagnosticsEnabled = !!Number(1);' in js
    assert 'if (clean === "diagnostics") return networkDiagnosticsEnabled ? "diagnostics" : "map";' in js


def test_network_layout_uses_single_row_map_track() -> None:
    css = build_dashboard_css(theme_css="")
    graph_panel_css = css[css.index(".network-graph-panel {"):css.index(".network-graph-card {")]
    graph_label_css = css[css.index(".network-graph-node-label {"):css.index(".network-graph-node-label.is-secondary {")]
    graph_toolbar_css = css[css.index(".network-graph-toolbar {"):css.index(".network-graph-toolbar-actions {")]
    graph_legend_css = css[css.index(".network-graph-legend {"):css.index(".network-graph-legend-item {")]

    assert ".layout.view-network {" in css
    assert "grid-template-rows: minmax(0, 1fr);" in css
    assert ".layout.view-network .map {" in css
    assert "grid-row: 1;" in css
    assert ".network-graph-stage {" in css
    assert "touch-action: none;" in css
    assert ".network-graph-stage.is-panning {" in css
    assert ".network-graph-live-toggle[aria-pressed=\"true\"] {" in css
    assert ".network-graph-mode-chip {" in css
    assert ".network-graph-swatch.is-broadcast-only {" in css
    assert ".network-graph-ring.is-broadcast-only {" in css
    assert ".network-graph-node.is-broadcast-only .network-graph-node-core {" in css
    assert "padding: 0;" in graph_panel_css
    assert "pointer-events: auto;" in graph_label_css
    assert "position: absolute;" in graph_toolbar_css
    assert "display: none;" in graph_legend_css
