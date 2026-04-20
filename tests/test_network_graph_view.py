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
    assert 'id="network-graph-back-btn"' not in html
    assert 'id="network-graph-home-btn"' not in html
    assert 'id="network-graph-reset-view-btn"' not in html
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
    assert 'function syncNetworkGraphTextZoom(svg, rawViewBox)' in js
    assert 'const zoomFactor = Math.max(1, zoomRatio);' in js
    assert 'data-network-graph-label-offset-y="${labelOffsetY.toFixed(1)}"' in js
    assert 'data-network-graph-node-radius="${Number(item.radius).toFixed(1)}"' in js
    assert 'const labelOffsetRaw = item && item.labelOffsetY;' in js
    assert 'const labelEls = svg.querySelectorAll(".network-graph-node-label");' in js
    assert 'const baseRadius = Math.max(0, Number(labelEl.getAttribute("data-network-graph-node-radius") || 0));' in js
    assert 'const ridesUnderEmoji = !!(nodeGroup && nodeGroup.classList.contains("has-emoji-glyph"));' in js
    assert 'const radiusFactor = ridesUnderEmoji ? 0.58 : 0.72;' in js
    assert 'Math.min(ridesUnderEmoji ? 4.2 : 5.4, baseGap * 0.55)' in js
    assert '(baseRadius * radiusFactor) + (pinnedGapPx / zoomFactor)' in js
    assert 'labelEl.setAttribute("y", `${(adjustedMagnitude * direction).toFixed(2)}`);' in js
    assert 'svg.dataset.labelDensity = labelDensity;' in js
    assert 'function buildNetworkGraphSceneMarkup(scene)' in js
    assert 'class="network-graph-region' in js
    assert 'function animateNetworkGraphScene(svg, fromLayout, toLayout, options = {})' in js
    assert 'function resolveNetworkGraphNodeEmoji(item)' in js
    assert 'function resolveMapNodeEmoji(nodeId, state = latestState)' in js
    assert 'function createMapNodeMarker(lat, lon, nodeId, isSelected, markerKind = "actual", markerConfidence = 0.45, state = latestState)' in js
    assert 'function refreshMapNodeMarkerPresentation(marker, nodeId, isSelected, markerKind = "actual", markerConfidence = 0.45, state = latestState)' in js
    assert 'return (typeof nodeVisualEmojiForNode === "function")' in js
    assert 'settingsBadgeEmojiChoiceSet.has(String(settingsBadgeEmoji || "").trim())' in js
    assert '"has-emoji-glyph"' in js
    assert 'class="network-graph-node-emoji-fo"' in js
    assert 'label-priority-${labelPriority}' in js
    assert 'network-graph-node-label is-priority-${labelPriority}' in js
    assert 'className: "map-node-emoji-icon"' in js
    assert 'function buildNetworkGraphNodeSignalMeta(nodeMap, recentPackets)' in js
    assert 'const networkGraphModeStorageKey = "meshDashboardNetworkGraphModeV1";' in js
    assert 'const networkGraphLayoutStorageKey = "meshDashboardNetworkGraphLayoutV1";' in js
    assert 'let networkGraphEdgeMode = "history";' in js
    assert 'let networkGraphLayoutMode = "radial";' in js
    assert 'const networkGraphOverlayFitZoomOutScale = 1.03;' in js
    assert 'const networkGraphOverlaySafeInsetTop = 10;' in js
    assert 'function normalizeNetworkGraphEdgeMode(raw)' in js
    assert 'function normalizeNetworkGraphLayoutMode(raw)' in js
    assert 'clean === "community"' in js
    assert 'function loadPreferredNetworkGraphEdgeMode()' in js
    assert 'function loadPreferredNetworkGraphLayoutMode()' in js
    assert 'function persistPreferredNetworkGraphEdgeMode(modeName)' in js
    assert 'function persistPreferredNetworkGraphLayoutMode(modeName)' in js
    assert 'const graphSvg = document.getElementById("network-graph-svg");' in js
    assert 'graphSvg instanceof Element' in js
    assert 'graphToolbar.classList.toggle("is-overlay-docked", useOverlayGraphSummary);' in js
    assert 'graphStage.classList.toggle("is-overlay-docked", useOverlayGraphSummary);' in js
    assert 'topSafeInset: resolveNetworkGraphTopSafeInset(svg),' in js
    assert 'networkGraphViewState.resetBounds = {' in js
    assert 'networkGraphViewState.resetCenter = rootPosition' in js
    assert 'networkGraphEdgeMode = loadPreferredNetworkGraphEdgeMode();' in js
    assert 'persistPreferredNetworkGraphEdgeMode(networkGraphEdgeMode);' not in js
    assert 'const networkGraphZoomBounds = Object.freeze({ minScale: 0.42, maxScale: 5.5 });' in js
    assert 'function networkGraphNodeHasLinkPeers(nodeId, adjacency, nodeMap = null)' in js
    assert 'function networkGraphAverageParentOrder(nodeId, parentHintsByNodeId, layerOrderIndexByNodeId)' in js
    assert 'function compareNetworkGraphLayerIds(' in js
    assert 'function buildNetworkGraphPlaceholderNode(nodeId, caps = null)' in js
    assert 'function buildNetworkGraphNodeMap(nodes, historyCapsRaw, rawEdges, options = {})' in js
    assert 'const includeAllLiveNodes = !(options && options.includeAllLiveNodes === false);' in js
    assert 'const pinnedNodeIds = Array.isArray(options && options.pinnedNodeIds)' in js
    assert 'function filterNetworkGraphRawEdgesByMode(rawEdges, mode = networkGraphEdgeMode)' in js
    assert 'function collectNetworkGraphAncestorScores(nodeId, targetLayer, layerByNodeId, parentHintsByNodeId, memo = new Map())' in js
    assert 'function resolveNetworkGraphBestClusterCandidate(candidateScores, degreeMeta, fallbackId = "")' in js
    assert 'function chunkNetworkGraphNodeIds(nodeIds, chunkSize = 1)' in js
    assert 'function compareNetworkGraphDisconnectedCandidates(candidateA, candidateB, degreeMeta, nodeMap)' in js
    assert 'function limitNetworkGraphDisconnectedNodeIds(' in js
    assert 'function doesNetworkGraphViewBoxContainBounds(viewBox, bounds, paddingRatio = 0.04)' in js
    assert 'const excludeDisconnected = !!(options && options.excludeDisconnected);' in js
    assert 'if (excludeDisconnected && item.disconnected) continue;' in js
    assert 'if (excludeDisconnected && includedCount <= 0) {' in js
    assert 'function resolveNetworkGraphResetViewBox(svg, options = {}) {' in js
    assert 'function resolveNetworkGraphStage(svg = null) {' in js
    assert 'function isNetworkGraphOverlayDocked(svg = null) {' in js
    assert 'function resolveNetworkGraphFitZoomOutScale(svg = null) {' in js
    assert 'function resolveNetworkGraphTopSafeInset(svg = null) {' in js
    assert 'function bindNetworkGraphSummaryControls()' in js
    assert 'function syncNetworkGraphLayoutSelector()' in js
    assert 'function bindNetworkGraphLayoutSelector()' in js
    assert 'function setNetworkGraphEdgeMode(modeName, options = {})' in js
    assert 'function setNetworkGraphLayoutMode(modeName, options = {})' in js
    assert 'function setNetworkGraphRootNode(nodeId, options = {})' in js
    assert 'function navigateNetworkGraphBack()' in js
    assert 'function focusNetworkGraphNodeFromSelection(nodeId, options = {})' in js
    assert 'const graphOpen = activeLayoutView === "network" && activeNetworkSubview === "graph";' in js
    assert 'selectNode(row.dataset.nodeId || "", true, !graphOpen);' in js
    assert 'selectNode(nodeId, true, !graphOpen && unreadDirectCount <= 0);' in js
    assert 'function recenterNetworkGraphView(svg, options = {})' in js
    assert 'return fitNetworkGraphViewBoxToBounds(bounds, svg);' in js
    assert 'const localNodeHasLinkPeers = localNodeAvailable' in js
    assert 'if (localNodeAvailable && (localNodeHasLinkPeers || bestDegree <= 0)) {' in js
    assert 'const parentHintsByNodeId = new Map();' in js
    assert 'const layerOrderIndexByNodeId = new Map([[rootId, 0]]);' in js
    assert 'const rootClusterIdSet = new Set(rootClusterIds);' in js
    assert 'const clusterIdByNodeId = new Map([[rootId, rootId]]);' in js
    assert 'const clusterLabelNodeIds = new Set();' in js
    assert 'const preferredVisibleCount = Math.max(0, (totalDisconnectedCount * 2) - safeConnectedCount);' in js
    assert 'const visibleCount = Math.max(preservedNodeIds.size, preferredVisibleCount);' in js
    assert 'const disconnectedVisibility = limitNetworkGraphDisconnectedNodeIds(' in js
    assert 'const visibleBroadcastOnlyDisconnected = Array.isArray(disconnectedVisibility.broadcastOnlyNodeIds)' in js
    assert 'const disconnectedRingCount = (visibleBroadcastOnlyDisconnected.length ? 1 : 0) + (visibleDisconnected.length ? 1 : 0);' in js
    assert 'const subclusterMembersById = new Map([[clusterId, [clusterId]]]);' in js
    assert 'const branchDescriptors = Array.from(subclusterMembersById.entries())' in js
    assert 'const cellDescriptors = [];' in js
    assert 'const branchWeightTotal = branchDescriptors.reduce((sum, branchDescriptor) => sum + branchDescriptor.weight, 0) || 1;' in js
    assert 'const cellWeightTotal = cellDescriptors.reduce((sum, cellDescriptor) => sum + cellDescriptor.weight, 0) || 1;' in js
    assert 'clusterLabelNodeIds.add(branchDescriptor.subclusterId);' in js
    assert 'for (const nodeId of clusterLabelNodeIds) {' in js
    assert 'Object.entries((historyCapsRaw && typeof historyCapsRaw === "object") ? historyCapsRaw : {})' in js
    assert 'buildNetworkGraphPlaceholderNode(clean, historyCapsById.get(clean) || null)' in js
    assert 'const filteredRawEdges = filterNetworkGraphRawEdgesByMode(rawEdges, edgeMode);' in js
    assert 'const filteredRawEdges = filterNetworkGraphRawEdgesByMode(rawEdges, networkGraphEdgeMode);' in js
    assert 'includeAllLiveNodes: edgeMode !== "live",' in js
    assert 'includeAllLiveNodes: normalizeNetworkGraphEdgeMode(networkGraphEdgeMode) !== "live",' in js
    assert 'buildNetworkGraphNodeMap(nodes, historyCaps, filteredRawEdges, {' in js
    assert 'buildNetworkGraphNodeMap(liveNodes, historyCaps, filteredRawEdges, {' in js
    assert 'const parsedWeight = useSessionWeight ? parsedSession : parsedLifetime;' in js
    assert 'empty.textContent = edgeMode === "live"' in js
    assert '<button id="network-graph-mode-chip" class="network-graph-chip network-graph-mode-chip"' in js
    assert 'summary.innerHTML = `<label class="network-graph-layout-control history-metric-wrap history-select-chip-hide-label" for="network-graph-layout-select">' in js
    assert '<button id="network-graph-reset-view-btn" class="network-graph-chip network-graph-action-chip"' in js
    assert 'bindNetworkGraphLayoutSelector();' in js
    assert 'syncNetworkGraphLayoutSelector();' in js
    assert 'label class="network-graph-layout-control history-metric-wrap history-select-chip-hide-label" for="network-graph-layout-select"' in js
    assert '<span class="network-graph-chip-label history-metric-label">View</span>' in js
    assert '<select id="network-graph-layout-select" class="network-graph-layout-select history-metric-select" aria-label="Network links layout">' in js
    assert '>Community</option>' in js
    assert 'bindNetworkGraphSummaryControls();' in js
    assert 'const resetBtn = document.getElementById("network-graph-reset-view-btn");' in js
    assert 'resetNetworkGraphView(svg);' in js
    assert 'Avg packet hops: ${edge.avgHops == null ? "n/a" : edge.avgHops}' in js
    assert '${item.layer} hop${item.layer === 1 ? "" : "s"} away' in js
    assert 'last packet hops away:' in js
    assert 'label: `${layer} hop${layer === 1 ? "" : "s"}`,' in js
    assert 'Switch Links view between stored history topology and the current session topology' in js
    assert '<span class="network-graph-chip-label">1 Hop</span>' not in js
    assert 'Click to refocus, scroll to zoom, and use Reset view from the header controls.' in js
    assert 'Numbered hop rings show shortest graph distance from the current root, not literal packet-route hops.' in js
    assert 'first-hop neighborhoods split into branch sub-clusters from the current root' in js
    assert 'const networkGraphActive304 = activeLayoutView === "network" && activeNetworkSubview === "graph";' in js
    assert 'const weeklySummaryPromise = (activeLayoutView === "history" || activeLayoutView === "network")' in js
    assert 'if (weeklySummaryPromise) {' in js
    assert 'const networkGraphActive = next === "network" && activeNetworkSubview === "graph";' in js
    assert 'const rootChanged = networkGraphViewState.lastRootId !== rootId;' in js
    assert 'hiddenBroadcastOnlyCount: Math.max(0, Number(disconnectedVisibility.hiddenBroadcastOnlyCount) || 0),' in js
    assert 'hiddenDisconnectedCount: Math.max(0, Number(disconnectedVisibility.hiddenDetachedCount) || 0),' in js
    assert '&& !doesNetworkGraphViewBoxContainBounds(networkGraphViewState.viewBox, networkGraphViewState.bounds, 0.05)' in js
    assert 'const shouldRefitForModeChange = !!(' in js
    assert 'animateNetworkGraphViewBox(svg, fittedViewBox);' in js
    assert '} else if (rootChanged) {' in js
    assert 'layoutMode === "tree"' in js
    assert 'layoutMode === "cluster"' in js
    assert 'layoutMode === "community"' in js
    assert 'function resolveTreeLabelOffset(index, radius, amplitude = 16) {' in js
    assert 'return radius + amplitude + 2;' in js
    assert 'const localId = normalizeNodeId(resolveLocalNodeId(latestState || {}) || "");' in js
    assert 'const isLocalNode = item.nodeId === localId;' in js
    assert 'position.labelOffsetY == null' in js
    assert 'class="network-graph-node-emoji"' in js
    assert '<span class="network-graph-swatch is-local"></span>Your node / local radio' in js
    assert 'is-broadcast-only' in js
    assert 'pointerDownNodeId' in js
    assert 'svg.addEventListener("wheel"' in js
    assert 'cancelNetworkGraphViewAnimation();' in js
    assert 'svg.addEventListener("pointerup", finishPan);' in js
    assert 'syncNetworkGraphTextZoom(svg, networkGraphViewState.viewBox);' in js


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
    assert ".network-graph-stage.is-overlay-docked #network-graph-svg {" in css
    assert ".network-graph-mode-chip," in css
    assert ".network-graph-action-chip {" in css
    assert ".network-graph-layout-control {" in css
    assert ".network-graph-layout-select {" in css
    assert "[data-theme=\"dark\"] .network-graph-layout-control {" in css
    assert "[data-theme=\"dark\"] .network-graph-layout-select {" in css
    assert "--network-graph-label-font-size: 10px;" in css
    assert ".network-graph-region {" in css
    assert ".network-graph-region-label {" in css
    assert ".network-graph-swatch.is-broadcast-only {" in css
    assert ".network-graph-swatch.is-local {" in css
    assert ".network-graph-ring.is-broadcast-only {" in css
    assert ".network-graph-node.is-local .network-graph-node-core {" in css
    assert ".network-graph-node-emoji-fo {" in css
    assert ".network-graph-node-emoji {" in css
    assert ".network-graph-node.is-local .network-graph-node-emoji {" in css
    assert ".network-graph-node.is-local.has-emoji-glyph .network-graph-node-core {" in css
    assert ".network-graph-node-label.is-below {" in css
    assert "dominant-baseline: hanging;" in css
    assert ".network-graph-node-label.is-above {" in css
    assert "dominant-baseline: ideographic;" in css
    assert ".map-node-emoji-marker {" in css
    assert ".map-node-emoji-glyph {" in css
    assert ".network-graph-node.is-broadcast-only .network-graph-node-core {" in css
    assert "padding: 0;" in graph_panel_css
    assert "pointer-events: auto;" in graph_label_css
    assert "position: absolute;" in graph_toolbar_css
    assert ".network-graph-toolbar.is-overlay-docked {" in css
    assert "display: none;" in graph_legend_css
