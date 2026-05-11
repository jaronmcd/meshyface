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
    assert 'data-network-subview="routes"' in html
    assert 'id="network-map-panel-routes"' in html
    assert 'data-network-subview="sensors"' in html
    assert 'id="network-map-panel-sensors"' in html
    assert 'id="network-sensors-host"' in html
    assert 'id="network-routes-from"' in html
    assert 'id="network-routes-to"' in html
    assert 'data-network-route-mode="inferred"' in html
    assert 'data-network-route-mode="live"' in html
    assert 'data-network-subview="diagnostics"' in html
    assert 'hidden disabled aria-hidden="true"' in html
    assert 'id="network-map-panel-diagnostics"' in html
    assert 'hidden aria-hidden="true"' in html
    assert 'id="map-fullscreen-toggle-btn"' in html
    assert 'aria-label="Enter full screen map"' in html
    assert html.index('id="map-heatmap-mode"') < html.index('id="map-fullscreen-toggle-btn"')
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
    assert 'if (clean === "route" || clean === "routes") return "routes";' in js
    assert '|| clean === "top10" || clean === "sensors") return clean;' in js
    assert 'function renderNetworkGraphView(state = latestState)' in js
    assert 'function normalizeNetworkRoutesMode(raw)' in js
    assert 'function renderNetworkRoutes(state = latestState, options = {})' in js
    assert 'function networkRoutesFindInferredPath(fromNodeId, toNodeId, adjacency)' in js
    assert 'function buildNetworkRoutesScopedLinks(route, data)' in js
    assert 'function networkRoutesScopeHtml(route, data, fromNodeId, toNodeId)' in js
    assert 'function bindNetworkRoutesScopeInteractions(root = document)' in js
    assert 'const networkRoutesScopeViewState = {' in js
    assert 'class="network-route-scope"' in js
    assert 'class="network-route-scope-svg"' in js
    assert 'data-route-edge-a="${escAttr(sourceId)}"' in js
    assert 'data-route-scope-reset="1"' in js
    assert 'zoomNetworkRoutesScopeView(svg, event);' in js
    assert 'contextCandidates.slice(0, 12)' in js
    assert 'Live trace is not wired yet.' in js
    assert 'function refreshNetworkDiagnosticsPanel(force = false)' in js
    assert 'fetch(`/api/history/malformed?${params.toString()}`' in js
    assert 'name: "maltext"' in js
    assert 'function getNetworkMapFullscreenTarget()' in js
    assert 'function updateMapFullscreenControl(viewName = activeLayoutView, subviewName = activeNetworkSubview)' in js
    assert 'function toggleNetworkMapFullscreen()' in js
    assert 'function bindMapFullscreenControl()' in js
    assert 'runBootStep("bindMapFullscreenControl", () => bindMapFullscreenControl());' in js
    assert 'requestMapResizeStabilized();' in js
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
    assert 'function networkGraphVisibleNodeEmojiForNode(nodeId, node = null)' in js
    assert "networkGraphVisibleNodeEmojiForNode(nodeId, item && item.node)" in js
    assert "nodeVisualEmojiForNode(cleanNodeId, null, node)" in js
    assert 'settingsBadgeEmojiChoiceSet.has(String(settingsBadgeEmoji || "").trim())' not in js
    assert '"has-emoji-glyph"' in js
    assert 'class="network-graph-node-emoji-fo"' in js
    assert 'label-priority-${labelPriority}' in js
    assert 'network-graph-node-label is-priority-${labelPriority}' in js
    assert 'className: "map-node-emoji-icon"' in js
    assert 'function buildNetworkGraphNodeSignalMeta(nodeMap, recentPackets)' in js
    assert 'const networkGraphModeStorageKey = "meshDashboardNetworkGraphModeV1";' in js
    assert 'const networkGraphLayoutStorageKey = "meshDashboardNetworkGraphLayoutV1";' in js
    assert 'const networkRoutesModeStorageKey = "meshDashboardNetworkRoutesModeV1";' in js
    assert 'const networkRoutesWindowStorageKey = "meshDashboardNetworkRoutesWindowV1";' in js
    assert 'const networkGraphTagRouteVisibilityStorageKey = "meshDashboardNetworkGraphTagRouteVisibilityV1";' in js
    assert 'const networkGraphSelfPathVisibilityStorageKey = "meshDashboardNetworkGraphSelfPathVisibilityV1";' in js
    assert 'const networkGraphHistoryEdgeCache = new Map();' in js
    assert 'const networkGraphHistoryCapsCache = new Map();' in js
    assert 'const networkGraphHistoryEdgeRequests = new Map();' in js
    assert 'let networkGraphEdgeMode = "7d";' in js
    assert 'let networkGraphLayoutMode = "radial";' in js
    assert 'const networkGraphOverlayFitZoomOutScale = 1.1;' in js
    assert 'const networkGraphOverlaySafeInsetTop = 10;' in js
    assert 'function normalizeNetworkGraphEdgeMode(raw)' in js
    assert 'function networkGraphEdgeModeUsesHistoryFetch(modeName)' in js
    assert 'function normalizeNetworkGraphLayoutMode(raw)' in js
    assert 'clean === "community"' in js
    assert 'function loadPreferredNetworkGraphEdgeMode()' in js
    assert 'function loadPreferredNetworkGraphLayoutMode()' in js
    assert 'function loadPreferredNetworkGraphHiddenTagRoutePresetIds()' in js
    assert 'function loadPreferredNetworkGraphSelfPathVisible()' in js
    assert 'function persistPreferredNetworkGraphEdgeMode(modeName)' in js
    assert 'function persistPreferredNetworkGraphLayoutMode(modeName)' in js
    assert 'function persistPreferredNetworkGraphHiddenTagRoutePresetIds(hiddenIds)' in js
    assert 'function persistPreferredNetworkGraphSelfPathVisible(isVisible)' in js
    assert 'const graphSvg = document.getElementById("network-graph-svg");' in js
    assert 'graphSvg instanceof Element' in js
    assert 'graphToolbar.classList.toggle("is-overlay-docked", useOverlayGraphSummary);' in js
    assert 'graphStage.classList.toggle("is-overlay-docked", useOverlayGraphSummary);' in js
    assert 'topSafeInset: resolveNetworkGraphTopSafeInset(svg),' in js
    assert 'networkGraphViewState.resetBounds = {' in js
    assert 'networkGraphViewState.resetCenter = rootPosition' in js
    assert 'networkGraphEdgeMode = loadPreferredNetworkGraphEdgeMode();' in js
    assert 'networkRoutesMode = loadPreferredNetworkRoutesMode();' in js
    assert 'networkRoutesWindow = loadPreferredNetworkRoutesWindow();' in js
    assert 'persistPreferredNetworkGraphEdgeMode(networkGraphEdgeMode);' not in js
    assert 'const networkGraphZoomBounds = Object.freeze({ minScale: 0.42, maxScale: 5.5 });' in js
    assert 'function networkGraphNodeHasLinkPeers(nodeId, adjacency, nodeMap = null)' in js
    assert 'function networkGraphNodeDisplayPriority(nodeId, nodeMap)' in js
    assert 'function networkGraphNodeGroupDisplayPriority(nodeIds, nodeMap)' in js
    assert 'function networkGraphAverageParentOrder(nodeId, parentHintsByNodeId, layerOrderIndexByNodeId)' in js
    assert 'function compareNetworkGraphLayerIds(' in js
    assert 'function buildNetworkGraphPlaceholderNode(nodeId, caps = null)' in js
    assert 'function buildNetworkGraphNodeMap(nodes, historyCapsRaw, rawEdges, options = {})' in js
    assert 'const includeAllLiveNodes = !(options && options.includeAllLiveNodes === false);' in js
    assert 'const pinnedNodeIds = Array.isArray(options && options.pinnedNodeIds)' in js
    assert 'function networkGraphRawEdgesForMode(rawEdges, modeName = networkGraphEdgeMode)' in js
    assert 'function networkGraphHistoryCapsForMode(historyCapsRaw, modeName = networkGraphEdgeMode)' in js
    assert 'function filterNetworkGraphRawEdgesByMode(rawEdges, mode = networkGraphEdgeMode)' in js
    assert 'fetch(`/api/history/links?${params.toString()}`' in js
    assert 'networkGraphHistoryCapsCache.set(mode, historyCaps);' in js
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
    assert 'selectNode(row.dataset.nodeId || "", true, true);' in js
    assert 'selectNode(nodeId, true, true);' in js
    assert 'function recenterNetworkGraphView(svg, options = {})' in js
    assert 'return fitNetworkGraphViewBoxToBounds(bounds, svg);' in js
    assert 'const selectedNodeHasLinkPeers = selectedNodeAvailable' in js
    assert 'if (selectedNodeAvailable && selectedNodeHasLinkPeers) return selectedId;' in js
    assert 'if (graphRootAvailable && graphRootHasLinkPeers) return graphRootId;' in js
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
    assert 'networkGraphNodeGroupDisplayPriority(b.members, nodeMap)' in js
    assert 'for (const nodeId of clusterLabelNodeIds) {' in js
    assert 'function networkGraphNodeRenderPriority(item)' in js
    assert 'const nodeRenderItems = items.map((item, index) => ({ item, index })).sort' in js
    assert 'Object.entries((historyCapsRaw && typeof historyCapsRaw === "object") ? historyCapsRaw : {})' in js
    assert 'buildNetworkGraphPlaceholderNode(clean, historyCapsById.get(clean) || null)' in js
    assert 'const filteredRawEdges = filterNetworkGraphRawEdgesByMode(rawEdges, edgeMode);' in js
    assert 'const filteredRawEdges = filterNetworkGraphRawEdgesByMode(rawEdges, networkGraphEdgeMode);' in js
    assert 'includeAllLiveNodes: edgeMode !== "live",' in js
    assert 'includeAllLiveNodes: normalizeNetworkGraphEdgeMode(networkGraphEdgeMode) !== "live",' in js
    assert 'buildNetworkGraphNodeMap(nodes, historyCaps, filteredRawEdges, {' in js
    assert 'buildNetworkGraphNodeMap(liveNodes, historyCaps, filteredRawEdges, {' in js
    assert 'const parsedWeight = useSessionWeight ? parsedSession : parsedLifetime;' in js
    assert 'Loading ${networkGraphEdgeModeLabel(edgeMode)} link history...' in js
    assert 'const summaryHtml = `<div class="network-graph-summary-main"><label class="network-graph-layout-control history-metric-wrap history-select-chip-hide-label" for="network-graph-layout-select">' in js
    assert 'if (summary.__meshNetworkGraphSummaryHtml !== summaryHtml) {' in js
    assert "summary.__meshNetworkGraphSummaryHtml = summaryHtml;" in js
    assert '<button id="network-graph-reset-view-btn" class="network-graph-chip network-graph-action-chip"' in js
    assert 'bindNetworkGraphLayoutSelector();' in js
    assert 'syncNetworkGraphLayoutSelector();' in js
    assert 'label class="network-graph-layout-control history-metric-wrap history-select-chip-hide-label" for="network-graph-layout-select"' in js
    assert '<span class="network-graph-chip-label history-metric-label">View</span>' in js
    assert '<select id="network-graph-layout-select" class="network-graph-layout-select history-metric-select" aria-label="Network links layout">' in js
    assert '<label class="network-graph-mode-control history-metric-wrap history-select-chip-hide-label" for="network-graph-mode-select"' in js
    assert '<select id="network-graph-mode-select" class="network-graph-mode-select history-metric-select" aria-label="Network links source">' in js
    assert '<span class="network-graph-chip-label history-metric-label">Links</span>' in js
    assert 'id: "7d", label: "7d"' in js
    assert 'id: "max", label: "Max"' in js
    assert '>Community</option>' in js
    assert 'bindNetworkGraphSummaryControls();' in js
    assert 'syncNetworkGraphModeSelector();' in js
    assert 'const resetBtn = document.getElementById("network-graph-reset-view-btn");' in js
    assert 'const modeSelect = document.getElementById("network-graph-mode-select");' in js
    assert 'resetNetworkGraphView(svg);' in js
    assert 'Avg packet hops: ${edge.avgHops == null ? "n/a" : edge.avgHops}' in js
    assert '${item.layer} hop${item.layer === 1 ? "" : "s"} away' in js
    assert 'last packet hops away:' in js
    assert 'label: `${layer} hop${layer === 1 ? "" : "s"}`,' in js
    assert 'Choose the link history window for the Links view' in js
    assert '<span class="network-graph-chip-label">1 Hop</span>' not in js
    assert 'const networkGraphActive304 = activeLayoutView === "network" && activeNetworkSubview === "graph";' in js
    assert 'const networkRoutesActive304 = activeLayoutView === "network" && activeNetworkSubview === "routes";' in js
    assert 'const networkSensorsActive = activeLayoutView === "network" && activeNetworkSubview === "sensors";' in js
    assert '|| (activeLayoutView === "network" && !networkSensorsActive)' in js
    assert 'if (weeklySummaryPromise) {' in js
    assert 'const networkGraphActive = next === "network" && activeNetworkSubview === "graph";' in js
    assert 'const networkRoutesActive = next === "network" && activeNetworkSubview === "routes";' in js
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
    assert 'const isTaggedNode = !!(tagEntry && tagEntry.preset);' in js
    assert 'isTaggedNode ? "is-tagged" : ""' in js
    assert 'nodeEl.classList.toggle("is-tagged", isTaggedNode);' in js
    assert 'nodeEl.setAttribute("style", tagStyleVars);' in js
    assert 'function autoNewNodeTagPreset() {' in js
    assert 'id: "auto-new-node",' in js
    assert 'const nodeTagBuiltInIconPaths = {' in js
    assert '"auto-new-node": "M20,4C21.11,4 22,4.89 22,6' in js
    assert 'function nodeTagIconPathForEntry(tagEntry) {' in js
    assert 'function nodeTagIconSvgHtml(tagEntry, className = "node-tag-inline-icon") {' in js
    assert 'function nodeFirstDiscoveredUnix(nodeId, state = latestState) {' in js
    assert 'function nodeIsAutoNewByFirstDiscovery(nodeId, state = latestState, nowUnix = Math.floor(Date.now() / 1000)) {' in js
    assert 'function autoNodeTagEntryForNode(nodeId, state = latestState) {' in js
    assert 'return manualNodeTagEntryForNode(nodeId) || autoNodeTagEntryForNode(nodeId);' in js
    assert 'selectedTagRouteKey: "",' in js
    assert 'function resolveNetworkGraphShortestPathEdgeKeys(edges, fromNodeId, toNodeId) {' in js
    assert 'function networkGraphSelfPathIsVisible() {' in js
    assert 'function resolveNetworkGraphSelfPathInfo(scene) {' in js
    assert 'selfPathVisible: loadPreferredNetworkGraphSelfPathVisible(),' in js
    assert 'function resolveNetworkGraphTaggedItems(items) {' in js
    assert 'function buildNetworkGraphTagRouteKey(presetId, sourceId, targetId) {' in js
    assert 'function resolveNetworkGraphTaggedRouteSegments(edges, items, rootId, routeAnchorId = "") {' in js
    assert 'const routeStartId = (' in js
    assert 'sourceId: routeStartId,' in js
    assert 'routeKey,' in js
    assert 'hopCount,' in js
    assert 'const hopLabel = hopCount === 1 ? "1 graph hop" : `${hopCount} graph hops`;' in js
    assert '].join("\\n");' in js
    assert '].join("\\\\n");' not in js
    assert 'function resolveNetworkGraphTagRouteLegendItems(edges, items, rootId, routeAnchorId = "") {' in js
    assert 'function buildNetworkGraphTagRouteOverlayMarkup(scene) {' in js
    assert 'function buildNetworkGraphSelfPathOverlayMarkup(scene) {' in js
    assert 'function syncNetworkGraphSelectedTagRoute(svg) {' in js
    assert 'function syncNetworkGraphSelfPathLayer(svg, scene) {' in js
    assert 'function renderNetworkGraphTagRouteLegend(scene) {' in js
    assert 'function bindNetworkGraphTagRouteLegendControls(legend, scene) {' in js
    assert 'nodeTagIconSvgHtml(tagEntry, "network-graph-tag-filter-icon")' in js
    assert 'iconHtml: String(taggedItem.iconHtml || ""),' in js
    assert '<span class="network-graph-tag-filter-name">${item.iconHtml || ""}<span class="network-graph-tag-filter-label">${escAttr(item.label)}</span></span>' in js
    assert 'const stackOffset = Math.max(-11, Math.min(11, (stackIndex - ((stackCount - 1) / 2)) * 2.8));' in js
    assert 'class="network-graph-tag-route"' in js
    assert 'data-network-graph-tag-route-key="${escAttr(segment.routeKey)}"' in js
    assert 'data-network-graph-tag-preset-id="${escAttr(segment.presetId)}"' in js
    assert 'data-network-graph-tag-edge-key="${escAttr(segment.edgeKey)}"' in js
    assert 'data-network-graph-tag-filter-id="${escAttr(item.presetId)}"' in js
    assert 'const canToggle = Number(item.count || 0) > 0 || hasRoutes;' in js
    assert 'const disabledAttr = canToggle ? "" : " disabled";' in js
    assert 'Toggle ${item.label} node highlighting; no current routes from this view' in js
    assert 'localId,' in js
    assert '<g class="network-graph-tag-routes">' in js
    assert '<g class="network-graph-self-path">' in js
    assert 'data-network-graph-self-path-toggle="1"' in js
    assert 'networkGraphViewState.selfPathVisible = !!selfPathInput.checked;' in js
    assert 'syncNetworkGraphSelfPathLayer(svg, safeScene);' in js
    assert 'syncNetworkGraphTagRouteLayer(svg, safeScene);' in js
    assert 'function resolveNetworkGraphTagRouteKeyFromTarget(target) {' in js
    assert 'networkGraphViewState.selectedTagRouteKey = networkGraphViewState.selectedTagRouteKey === routeKey' in js
    assert 'syncNetworkGraphSelectedTagRoute(svg);' in js
    assert 'renderNetworkGraphTagRouteLegend(scene);' in js
    assert 'const edgeRenderItems = edges.map((edge, index) => ({' in js
    assert 'return pathDelta || (itemA.index - itemB.index);' in js
    assert 'localPathEdgeKeys.has(edgeKey) ? "is-local-path" : ""' in js
    assert 'edgeEl.classList.toggle("is-local-path", isLocalPathEdge);' in js
    assert 'localPathEdgeEls.forEach((edgeEl) => linkLayer.appendChild(edgeEl));' in js
    assert 'position.labelOffsetY == null' in js
    assert 'class="network-graph-node-emoji"' in js
    assert '<div class="network-graph-tag-legend-title">Routes</div>' in js
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
    assert ".network-graph-mode-control {" in css
    assert ".map-fullscreen-toggle-btn {" in css
    assert ".network-map-subviews:fullscreen {" in css
    assert '[data-theme="dark"] .map-fullscreen-toggle-btn {' in css
    assert ".network-graph-layout-select {" in css
    assert ".network-graph-mode-select {" in css
    assert ".network-routes-card {" in css
    assert ".network-routes-mode-btn {" in css
    assert ".network-route-scope {" in css
    assert ".network-route-scope-reset-btn {" in css
    assert ".network-route-scope-svg.is-panning {" in css
    assert ".network-route-scope-edge.is-route {" in css
    assert ".network-route-scope-node-hit {" in css
    assert ".network-route-hop-list {" in css
    assert ".network-route-edge-bar {" in css
    route_css = css[css.index(".network-routes-card {"):css.index(".network-top-nodes-toolbar {")]
    assert "rgba(249, 253, 249, 0.94)" in route_css
    assert "rgba(255, 255, 255, 0.72)" in route_css
    assert '[data-theme="dark"] .network-routes-card {' in css
    assert '[data-theme="dark"] .network-route-scope {' in css
    assert '[data-theme="dark"] .network-route-scope-reset-btn {' in css
    assert '[data-theme="dark"] .network-route-scope-edge.is-route {' in css
    assert '[data-theme="dark"] .network-route-hop {' in css
    assert '[data-theme="dark"] .network-route-hop-index {' in css
    assert "[data-theme=\"dark\"] .network-graph-layout-control," in css
    assert "[data-theme=\"dark\"] .network-graph-mode-control {" in css
    assert "[data-theme=\"dark\"] .network-graph-layout-select," in css
    assert "[data-theme=\"dark\"] .network-graph-mode-select {" in css
    assert "position: absolute;" in graph_legend_css
    assert "bottom: 14px;" in graph_legend_css
    assert "pointer-events: auto;" in graph_legend_css
    assert ".network-graph-legend[hidden] {" in css
    assert "--network-graph-label-font-size: 10px;" in css
    assert ".network-graph-region {" in css
    assert ".network-graph-region-label {" in css
    assert ".network-graph-swatch.is-broadcast-only {" in css
    assert ".network-graph-swatch.is-local-path {" in css
    assert ".network-graph-swatch.is-local {" in css
    assert ".network-graph-edge.is-local-path {" in css
    assert "stroke: var(--theme-base-color, var(--accent, #2f855a));" in css
    assert ".network-graph-tag-routes {" in css
    assert ".network-graph-tag-route {" in css
    assert "stroke: var(--network-graph-tag-route-color, var(--node-tag-color, #2aa85a));" in css
    assert "pointer-events: stroke;" in css
    assert "cursor: pointer;" in css
    assert ".network-graph-tag-route.is-muted-by-selection {" in css
    assert ".network-graph-tag-route.is-selected {" in css
    assert "opacity: 0.08;" in css
    assert "stroke-width: 6.4 !important;" in css
    assert "drop-shadow(0 0 9px var(--network-graph-tag-route-color, #2aa85a));" in css
    assert ".network-graph-self-path {" in css
    assert ".network-graph-self-path-segment {" in css
    assert ".network-graph-self-path-segment.is-halo {" in css
    assert ".network-graph-tag-filter-input {" in css
    assert ".network-graph-tag-filter.is-empty {" in css
    assert "appearance: none;" in css
    assert "border: 2px solid var(--network-graph-tag-route-color, #2aa85a);" in css
    assert "accent-color: var(--network-graph-tag-route-color, #2aa85a);" in css
    assert ".network-graph-tag-filter-input:checked {" in css
    assert ".network-graph-tag-filter-input:disabled {" in css
    assert ".network-graph-tag-filter-icon {" in css
    assert "fill: currentColor;" in css
    assert ".network-graph-tag-filter-label {" in css
    assert "[data-theme=\"dark\"] .network-graph-edge.is-local-path {" in css
    assert "stroke: var(--theme-base-color, var(--ui-accent));" in css
    assert "[data-theme=\"dark\"] .network-graph-tag-route {" in css
    assert "[data-theme=\"dark\"] .network-graph-self-path-segment {" in css
    assert "[data-theme=\"dark\"] .network-graph-tag-filter {" in css
    assert ".network-graph-ring.is-broadcast-only {" in css
    assert ".network-graph-node.is-local .network-graph-node-core {" in css
    assert ".network-graph-node.is-tagged .network-graph-node-core {" in css
    assert "stroke: var(--node-tag-color, #2aa85a);" in css
    assert "[data-theme=\"dark\"] .network-graph-node.is-tagged .network-graph-node-core {" in css
    assert "stroke: var(--node-tag-color, #3fb950);" in css
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
