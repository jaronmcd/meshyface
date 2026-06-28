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
    assert 'data-network-subview="spread"' not in html
    assert 'data-network-subview="routes"' in html
    assert 'id="network-map-panel-routes"' in html
    assert 'id="network-routes-primary-controls"' in html
    assert 'id="network-top-nodes-primary-controls"' in html
    assert 'data-network-subview="sensors"' in html
    assert 'id="network-map-panel-sensors"' in html
    assert 'id="network-sensors-host"' in html
    assert 'id="network-sensors-primary-controls"' in html
    assert 'id="network-routes-from"' in html
    assert 'id="network-routes-to"' in html
    assert 'id="network-routes-refresh-btn"' not in html
    assert 'id="network-routes-mode-select"' in html
    assert 'data-network-route-mode=' not in html
    assert 'data-network-subview="diagnostics"' in html
    assert 'hidden disabled aria-hidden="true"' in html
    assert 'id="network-map-panel-diagnostics"' in html
    assert 'hidden aria-hidden="true"' in html
    assert 'id="map-fullscreen-toggle-btn"' in html
    assert 'class="map-fullscreen-toggle-btn network-fullscreen-toggle-btn"' in html
    assert 'aria-label="Enter full screen network view"' in html
    assert 'id="map-heatmap-mode"' not in html
    assert html.index('<div id="map"></div>') < html.index('id="map-basemap-dock"')
    assert html.index('id="map-basemap-status"') < html.index('id="map-link-legend"')
    assert html.index('id="network-map-controls-host"') < html.index('id="map-fullscreen-toggle-btn"')
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
    assert 'function recordNetworkGraphRenderStats(stats)' in js
    assert 'const markNetworkGraphRenderPhase = (name, extra = null) => {' in js
    assert 'function clearNetworkGraphDom()' in js
    assert 'const leavingNetworkGraphSubview = !!(' in js
    assert 'const leavingNetworkGraphLayout = !!(' in js
    assert 'setActiveNetworkSubview(activeNetworkSubview, { persist: false, render: false });' in js
    assert 'latestStatePollProfile === "network-graph"' in js
    assert 'summary.__meshNetworkGraphSummaryHtml = "";' in js
    assert 'function normalizeNetworkRoutesMode(raw)' in js
    assert 'const select = document.getElementById("network-routes-mode-select");' in js
    assert 'networkRoutesModeDefs\n          .map((entry) => `<option value="${escAttr(entry.id)}">${escAttr(entry.label)}</option>`)' in js
    assert 'networkRoutesMode = normalizeNetworkRoutesMode(modeSelect.value || "inferred");' in js
    assert 'function renderNetworkRoutes(state = latestState, options = {})' in js
    assert 'let networkRoutesScopeClickTimer = 0;' in js
    assert 'function networkRoutesFindInferredPath(fromNodeId, toNodeId, adjacency)' in js
    assert 'function networkRoutesEdgeSnrStrengthPct(edge, fallbackWeightPct = 0)' in js
    assert 'function networkRoutesEdgeSnrBarsFromPct(rawPct)' in js
    assert 'function buildNetworkRoutesScopedLinks(route, data)' in js
    assert 'const returnPath = (Array.isArray(route && route.returnPath) ? route.returnPath : [])' in js
    assert 'const edgePct = networkRoutesEdgeSnrStrengthPct(edge, edgeWeightPct);' in js
    assert 'const edgeSignal = networkRoutesEdgeSnrBarsFromPct(edgePct);' in js
    assert 'class="network-route-edge-bars is-${escAttr(edgeSignal.level)}"' in js
    assert 'appendPathEdges(returnPath, returnEdgesRaw, "return");' in js
    assert 'function networkRoutesScopeNodeEmoji(nodeId, node = null)' in js
    assert 'if (typeof nodeEmojiMarkersAreEnabled === "function" && !nodeEmojiMarkersAreEnabled()) return "";' in js
    assert 'function networkRoutesBuildLocationEstimates(data)' in js
    assert 'function networkRoutesScopeNodeLocation(nodeId, node = null, state = latestState, routeLocationEstimates = null)' in js
    assert 'function networkRoutesScopeHtml(route, data, fromNodeId, toNodeId)' in js
    assert 'const isReturnRoute = kind === "return";' in js
    assert 'const bidirectionalEdgeKeys = new Set();' in js
    assert 'const markerDefsHtml = `<defs>' in js
    assert 'marker-end="${markerEnd}"' in js
    assert 'const cityKey = networkTopNodesCityCacheKey(location);' in js
    assert 'const citySource = locationMeta ? String(locationMeta.source || "gps") : "";' in js
    assert 'const cityLabel = cityText && citySource === "estimated" ? `~ ${cityText}` : cityText;' in js
    assert 'data-route-node-city-source="${escAttr(citySource || "gps")}"' in js
    assert 'class="network-route-scope-node-city${citySource === "estimated" ? " is-estimated" : ""}"' in js
    assert 'function hydrateNetworkRoutesScopeNodeCities(root)' in js
    assert 'nearestOfflineCityHintFromCoords(lat, lon)' in js
    assert 'hydrateNetworkRoutesScopeNodeCities(result);' in js
    assert 'result.addEventListener("dblclick", (event) => {' in js
    assert 'activateRouteNodeTarget(target, { retargetScope: true })' in js
    assert 'const display = clean && source === "estimated" ? `~ ${clean}` : clean;' in js
    assert 'hopNodeId === "!local"' in js
    assert 'const nodeEmoji = networkRoutesScopeNodeEmoji(clean, node);' in js
    assert 'nodeEmoji ? "has-emoji-glyph" : ""' in js
    assert 'class="network-route-scope-node-emoji-fo"' in js
    assert 'class="network-route-scope-node-emoji"' in js
    assert '${isRoute && !nodeEmoji ? `<text class="network-route-scope-node-index"' in js
    assert 'function bindNetworkRoutesScopeInteractions(root = document)' in js
    assert 'function syncNetworkRoutesFromSelectedNode()' in js
    assert 'const selectedId = normalizeNodeId(selectedNodeId || "");' in js
    assert 'networkRoutesFromNodeId = selectedId;' in js
    assert 'const nextTo = previousFrom && previousFrom !== selectedId ? previousFrom : "";' in js
    assert 'networkRoutesToNodeId = nextTo;' in js
    assert 'const networkRoutesScopeViewState = {' in js
    assert 'class="network-route-scope"' in js
    assert 'class="network-route-scope-svg"' in js
    assert 'data-route-edge-a="${escAttr(sourceId)}"' in js
    assert 'data-route-scope-reset="1"' in js
    assert 'zoomNetworkRoutesScopeView(svg, event);' in js
    assert 'const maxSideLinks = Math.max(10, Math.min(22, path.length * 4));' in js
    assert 'const maxClusterLinks = 14;' in js
    assert 'const isBidirectionalOverlap = (isPrimaryRoute || isReturnRoute) && bidirectionalEdgeKeys.has(edgeKey);' in js
    assert 'const offsetPx = isBidirectionalOverlap ? 7 : 0;' in js
    assert 'if (keyAlreadyPresent && kind !== "return") continue;' in js
    assert 'const routeLocationEstimates = networkRoutesBuildLocationEstimates(data);' in js
    assert 'returnPath: backRoute.path,' in js
    assert 'returnEdges: backRoute.edges,' in js
    assert 'Live trace is not wired yet.' in js
    assert 'function refreshNetworkDiagnosticsPanel(force = false)' in js
    assert 'fetch(`/api/history/malformed?${params.toString()}`' in js
    assert 'name: "maltext"' in js
    assert 'function getNetworkMapFullscreenTarget()' in js
    assert 'function updateMapFullscreenControl(viewName = activeLayoutView, subviewName = activeNetworkSubview)' in js
    assert 'const showControl = supported && (active || normalizedView === "network");' in js
    assert 'Enter full screen network view' in js
    assert 'function toggleNetworkMapFullscreen()' in js
    assert 'function bindMapFullscreenControl()' in js
    assert 'const controls = document.querySelector(".env-metrics-controls");' in js
    assert 'const networkControlsHost = document.getElementById("network-sensors-primary-controls");' in js
    assert 'const controlsTarget = dockInNetworkSensors ? networkControlsHost : explorer;' in js
    assert 'function syncNetworkRoutesPrimaryControls(viewName = activeLayoutView, subviewName = activeNetworkSubview)' in js
    assert 'const controlsHost = document.getElementById("network-routes-primary-controls");' in js
    assert 'const dockInNetworkRoutes = normalizedView === "network" && normalizedSubview === "routes";' in js
    assert 'function syncNetworkTopNodesPrimaryControls(viewName = activeLayoutView, subviewName = activeNetworkSubview)' in js
    assert 'const controlsHost = document.getElementById("network-top-nodes-primary-controls");' in js
    assert 'const dockInNetworkTopNodes = normalizedView === "network" && normalizedSubview === "top10";' in js
    assert 'runBootStep("bindMapFullscreenControl", () => bindMapFullscreenControl());' in js
    assert 'requestMapResizeStabilized();' in js
    assert 'activeNetworkSubview === "graph"' in js
    assert 'const networkGraphSelectionActive = activeLayoutView === "network" && activeNetworkSubviewName === "graph" && !networkSubviewUsesMap(activeNetworkSubviewName);' in js
    assert "networkSubviewUsesMap(activeNetworkSubviewName)" in js
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
    assert 'function buildNetworkGraphEdgeTitle(edge, nodeMap = null)' in js
    assert 'function buildNetworkGraphNodeTitle(item, nodeMap = null, rootId = "")' in js
    assert 'function hydrateNetworkGraphLazyTitle(rawTarget)' in js
    assert 'svg.addEventListener("pointerover", (event) => {' in js
    assert 'hydrateNetworkGraphLazyTitle(event.target);' in js
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
    assert (
        'function createMapNodeMarker(lat, lon, nodeId, isSelected, markerKind = "actual", '
        'markerConfidence = 0.45, state = latestState, options = null)'
        in js
    )
    assert 'const mapNodeMarkerPaneName = "mapNodeMarkerPane";' in js
    assert "markerStyle.pane = mapNodeMarkerPaneName;" in js
    assert 'function refreshMapNodeMarkerPresentation(marker, nodeId, isSelected, markerKind = "actual", markerConfidence = 0.45, state = latestState)' in js
    assert 'function networkGraphVisibleNodeEmojiForNode(nodeId, node = null)' in js
    assert "networkGraphVisibleNodeEmojiForNode(nodeId, item && item.node)" in js
    assert 'if (typeof nodeEmojiMarkersAreEnabled === "function" && !nodeEmojiMarkersAreEnabled()) return "";' in js
    assert "nodeVisualEmojiForNode(cleanNodeId, null, node)" in js
    assert 'settingsBadgeEmojiChoiceSet.has(String(settingsBadgeEmoji || "").trim())' not in js
    assert '"has-emoji-glyph"' in js
    assert 'class="network-graph-node-emoji-fo"' in js
    assert '<title>${escAttr(buildNetworkGraphEdgeTitle(edge' not in js
    assert '<title>${escAttr(buildNetworkGraphNodeTitle(item' not in js
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
    assert 'networkGraphViewState.lastSceneDataSignature = "";' in js
    assert 'let networkGraphEdgeMode = "7d";' in js
    assert 'let networkGraphLayoutMode = "radial";' in js
    assert 'const networkGraphOverlayFitZoomOutScale = 1.1;' in js
    assert 'const networkGraphOverlaySafeInsetTop = 10;' in js
    assert 'function normalizeNetworkGraphEdgeMode(raw)' in js
    assert 'function networkGraphEdgeModeUsesHistoryFetch(modeName)' in js
    assert 'function normalizeNetworkGraphLayoutMode(raw)' in js
    assert 'clean === "community"' in js
    assert 'clean === "spread"' not in js
    assert 'function buildNetworkGraphSpreadLayout(' not in js
    assert 'function networkGraphSpreadEdgeSignalScore(edge)' not in js
    assert 'function networkGraphSpreadDesiredDistanceMeters(edge)' not in js
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
    assert 'layoutSourceSignature: "",' in js
    assert 'lastSceneDataSignature: "",' in js
    assert 'function buildNetworkGraphLayoutSourceSignature(nodes, historyCapsRaw, rawEdges, state, edgeMode, searchQuery = "")' in js
    assert 'function hydrateNetworkGraphLayoutData(baseLayout, nodeMap, combinedEdges, state)' in js
    assert 'function buildNetworkGraphSceneDataSignature(scene, sourceSignature = "")' in js
    assert 'void sourceSignature;' in js
    assert 'Keep ordinary state-counter churn from forcing an O(edges + nodes) SVG sync.' in js
    assert 'const canSkipSceneDataSync = !!(' in js
    assert 'const graphHistoryEdgesLoading = networkGraphHistoryEdgesLoading(edgeMode);' in js
    assert 'markNetworkGraphRenderPhase("history_loading"' in js
    assert 'action: "history-loading",' in js
    assert 'markNetworkGraphRenderPhase("scene_markup"' in js
    assert 'markNetworkGraphRenderPhase("scene_dom_replace"' in js
    assert 'function resolveNetworkGraphPacketPortnum(packet)' in js
    assert 'safePacket.summary && typeof safePacket.summary === "object"' in js
    assert 'const graphLayoutSourceSignature = buildNetworkGraphLayoutSourceSignature(' in js
    assert 'networkGraphViewState.layoutSourceSignature === graphLayoutSourceSignature' in js
    assert 'networkGraphEdgeMode = loadPreferredNetworkGraphEdgeMode();' in js
    assert 'networkRoutesMode = loadPreferredNetworkRoutesMode();' in js
    assert 'networkRoutesWindow = loadPreferredNetworkRoutesWindow();' in js
    assert 'persistPreferredNetworkGraphEdgeMode(networkGraphEdgeMode);' not in js
    assert 'const networkGraphZoomBounds = Object.freeze({ minScale: 0.22, maxScale: 12 });' in js
    assert 'activePointers: new Map(),' in js
    assert 'pinchStartDistance: 0,' in js
    assert 'pinching: false,' in js
    assert 'const graphCenterX = Number(bounds.minX) + (spanWidth / 2);' in js
    assert 'const graphCenterY = Number(bounds.minY) + (spanHeight / 2);' in js
    assert 'const zoomedOutX = next.width >= (spanWidth * 1.06);' in js
    assert 'const zoomedOutY = next.height >= (spanHeight * 1.06);' in js
    assert 'const preserveRequestedCenter = !!(options && options.preserveRequestedCenter);' in js
    assert 'const panSlackX = Math.max(260, next.width * 0.9, spanWidth * 0.38);' in js
    assert 'const panSlackY = Math.max(220, next.height * 0.9, spanHeight * 0.38);' in js
    assert 'next.x = zoomedOutX' in js
    assert 'next.y = zoomedOutY' in js
    assert 'function getNetworkGraphActivePointers()' in js
    assert 'function beginNetworkGraphPinch(svg)' in js
    assert 'function updateNetworkGraphPinch(svg)' in js
    assert 'const zoomFactor = Math.max(0.05, startDistance / currentDistance);' in js
    assert 'event.pointerType !== "mouse" && activePointers.size >= 2' in js
    assert 'if (networkGraphViewState.pinching) {' in js
    assert 'updateNetworkGraphPinch(svg)' in js
    assert 'manualRootNodeId: "",' in js
    assert 'pendingSelectedNodeCenterId: "",' in js
    assert 'function buildNetworkGraphComponentMeta(nodeMap, adjacency, degreeMeta)' in js
    assert 'function compareNetworkGraphComponents(componentA, componentB, degreeMeta, nodeMap)' in js
    assert 'function networkGraphNodeHasLinkPeers(nodeId, adjacency, nodeMap = null)' in js
    assert 'function networkGraphRootCandidate(nodeId, componentMeta, degreeMeta)' in js
    assert 'function networkGraphComponentIsRelationshipAnchor(candidate, bestComponent)' in js
    assert 'function networkGraphNodeDisplayPriority(nodeId, nodeMap)' in js
    assert 'function networkGraphNodeGroupDisplayPriority(nodeIds, nodeMap)' in js
    assert 'function networkGraphAverageParentOrder(nodeId, parentHintsByNodeId, layerOrderIndexByNodeId)' in js
    assert 'function compareNetworkGraphLayerIds(' in js
    assert 'function buildNetworkGraphPlaceholderNode(nodeId, caps = null)' in js
    assert 'function buildNetworkGraphNodeMap(nodes, historyCapsRaw, rawEdges, options = {})' in js
    assert 'const includeAllLiveNodes = !(options && options.includeAllLiveNodes === false);' in js
    assert 'const pinnedNodeIds = Array.isArray(options && options.pinnedNodeIds)' in js
    assert 'function networkGraphRawEdgesForMode(rawEdges, modeName = networkGraphEdgeMode)' in js
    assert 'function networkGraphHistoryEdgesLoading(modeName = networkGraphEdgeMode)' in js
    assert 'function networkGraphHistoryCapsForMode(historyCapsRaw, modeName = networkGraphEdgeMode)' in js
    assert 'function filterNetworkGraphRawEdgesByMode(rawEdges, mode = networkGraphEdgeMode)' in js
    assert 'fetch(`/api/history/links?${params.toString()}`' in js
    assert 'networkGraphHistoryCapsCache.set(mode, historyCaps);' in js
    assert 'function collectNetworkGraphAncestorScores(nodeId, targetLayer, layerByNodeId, parentHintsByNodeId, memo = new Map())' in js
    assert 'function resolveNetworkGraphBestClusterCandidate(candidateScores, degreeMeta, fallbackId = "")' in js
    assert 'function collectNetworkGraphDisconnectedComponentDescriptors(nodeMap, adjacency, layerByNodeId, degreeMeta)' in js
    assert 'function chunkNetworkGraphNodeIds(nodeIds, chunkSize = 1)' in js
    assert 'function compareNetworkGraphDisconnectedCandidates(candidateA, candidateB, degreeMeta, nodeMap)' in js
    assert 'function limitNetworkGraphDisconnectedNodeIds(' in js
    assert 'function doesNetworkGraphViewBoxContainBounds(viewBox, bounds, paddingRatio = 0.04)' in js
    assert 'const excludeDisconnected = !!(options && options.excludeDisconnected);' in js
    assert 'if (excludeDisconnected && item.disconnected) continue;' in js
    assert 'if (excludeDisconnected && includedCount <= 0) {' in js
    assert 'function resolveNetworkGraphResetViewBox(svg, options = {}) {' in js
    assert 'function resolveNetworkGraphNodeCenterViewBox(svg, nodeId, positions, options = {}) {' in js
    assert 'preserveRequestedCenter: true,' in js
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
    assert 'networkGraphViewState.pendingSelectedNodeCenterId = nextId;' in js
    assert 'invalidateNetworkGraphRenderCache();\n      networkGraphViewState.skipSceneAnimationOnce = true;' in js
    assert 'selectNode(row.dataset.nodeId || "", true, false);' in js
    assert 'selectNode(nodeId, true, false);' in js
    assert 'activeLayoutView === "network"\n        && activeNetworkSubviewName === "routes"' in js
    assert 'syncNetworkRoutesFromSelectedNode(latestState, { preferSelectedTarget: true });\n        renderNetworkRoutes(latestState);' in js
    assert 'const liveTraceRunningForNode = !!(liveTraceState && liveTraceState.running' in js
    assert 'function networkRoutesLiveTraceProgressPct(rawState = networkRoutesLiveTraceState, nowMs = Date.now())' in js
    assert '&& typeof triggerNetworkMapTraceResultFlash === "function"' in js
    assert 'triggerNetworkMapTraceResultFlash(' in js
    assert 'networkRoutesLiveTraceState.ok === true' in js
    assert 'if (typeof scheduleMapNodeActivityFlashUpdate === "function") {' in js
    assert 'scheduleMapNodeActivityFlashUpdate();' in js
    assert 'runBtn.classList.toggle("is-running-trace", !!liveState.running);' in js
    assert 'runBtn.style.setProperty("--network-routes-run-progress", `${progressPct}%`);' in js
    assert 'class="network-routes-run-progress-fill"' in js
    assert 'class="network-routes-run-progress-text">Tracing ${escAttr(String(progressPct))}%' in js
    assert 'const liveTraceProgressPct = liveTraceRunningForNode\n          ? (\n              typeof networkRoutesLiveTraceProgressPct === "function"' in js
    assert 'const showTraceProgress = tool.id === "traceroute" && running && liveTraceProgressPct > 0;' in js
    assert 'class="chat-node-telemetry-tool-progress-fill"' in js
    assert 'class="chat-node-telemetry-tool-progress-text">Tracing ${escAttr(String(liveTraceProgressPct))}%' in js
    assert 'if (tool.id === "traceroute" && typeof setNetworkRoutesLiveTraceState === "function") {' in js
    assert 'telemetryNodeState.summaryMessage = `Running Traceroute for ${targetId}...`;' in js
    assert 'data-drawer-telemetry-shortcut-id="${escAttr(shortcutId)}"' in js
    assert 'runChatNodeTelemetryShortcut(shortcutId, hostNodeId || selectedNodeId);' in js
    assert 'openNetworkRoutesLiveTrace(targetNodeId, { autoRun: false });' in js
    assert 'setActiveNetworkSubview("map", { persist: true });' in js
    assert 'setActiveNetworkSubview("sensors", { persist: true });' in js
    assert 'const startListPx = Number.isFinite(Number(listRect.height)) ? Number(listRect.height) : 0;' in js
    assert 'const nextListPx = startListPx + (Number(clientY) - startY);' in js
    assert 'if (upEv && Number.isFinite(Number(upEv.clientY))) {' in js
    assert 'updateFromClientY(Number(upEv.clientY));' in js
    assert 'function recenterNetworkGraphView(svg, options = {})' in js
    assert 'return fitNetworkGraphViewBoxToBounds(bounds, svg);' in js
    assert 'const componentMeta = buildNetworkGraphComponentMeta(nodeMap, adjacency, degreeMeta);' in js
    assert 'const bestComponent = componentMeta.bestComponent;' in js
    assert 'const manualRootId = normalizeNodeId(networkGraphViewState.manualRootNodeId || "");' in js
    assert 'if (selectedNodeAvailable) return selectedId;' in js
    assert 'if (manualRootCandidate && manualRootCandidate.hasLinks) return manualRootCandidate.nodeId;' in js
    assert 'networkGraphComponentIsRelationshipAnchor(localCandidate, bestComponent)' in js
    assert 'const parentHintsByNodeId = new Map();' in js
    assert 'const layerOrderIndexByNodeId = new Map([[rootId, 0]]);' in js
    assert 'const rootClusterIdSet = new Set(rootClusterIds);' in js
    assert 'const clusterIdByNodeId = new Map([[rootId, rootId]]);' in js
    assert 'const clusterLabelNodeIds = new Set();' in js
    assert 'const externalClusterNodeIds = new Set();' in js
    assert 'const externalClusterComponentNodeIds = new Set();' in js
    assert 'let preferredVisibleCount = Math.max(0, (totalDisconnectedCount * 2) - safeConnectedCount);' in js
    assert 'if (totalDisconnectedCount > 24 && safeConnectedCount <= 3)' in js
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
    assert 'const disconnectedComponentDescriptors = collectNetworkGraphDisconnectedComponentDescriptors(' in js
    assert 'const visibleExternalClusterDescriptors = [];' in js
    assert 'label: `Cluster · ${labelBase}${hiddenLabel}`,' in js
    assert 'orderedNodeIds.forEach((nodeId) => externalClusterComponentNodeIds.add(nodeId));' in js
    assert '.filter((nodeId) => !externalClusterComponentNodeIds.has(nodeId));' in js
    assert 'const residualClusterLabel = group.broadcastOnly' in js
    assert '? `Heard only · ${ids.length}`' in js
    assert ': `Other detached · ${ids.length}`;' in js
    assert 'disconnectedCount: new Set(visibleDisconnected.concat(Array.from(externalClusterNodeIds))).size,' in js
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
    assert 'title="Reset links view" aria-controls="network-graph-svg">Reset view</button>' in js
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
    assert 'const networkGraphActive304 = activeLayoutView === "network" && activeNetworkSubview === "graph" && !networkSubviewUsesMap(activeNetworkSubview);' in js
    assert 'const networkOverviewActive304 = activeLayoutView === "network" && activeNetworkSubview === "overview";' in js
    assert 'const networkRoutesActive304 = activeLayoutView === "network" && activeNetworkSubview === "routes";' in js
    assert 'const networkNodesTableActive304 = activeLayoutView === "network" && (networkMapActive304 || networkOverviewActive304);' in js
    assert 'const historyRelevant304 = (activeLayoutView === "saved" || networkMapActive304 || drawerHistoryVisible304)' in js
    assert 'if (networkNodesTableActive304) {' in js
    assert 'clearHiddenNodesTable();' in js
    assert 'return "network-graph";' in js
    assert '|| networkOverviewActive' in js
    assert 'if (weeklySummaryPromise) {' in js
    assert 'const networkGraphActive = next === "network" && activeNetworkSubview === "graph" && !networkSubviewUsesMap(activeNetworkSubview);' in js
    assert 'const networkRoutesActive = next === "network" && activeNetworkSubview === "routes";' in js
    assert 'const networkMapSubviewActive = next === "network" && networkSubviewUsesMap(activeNetworkSubview);' in js
    assert 'const networkNodesTableActive = next === "network" && (networkMapSubviewActive || activeNetworkSubview === "overview");' in js
    assert 'const historyRelevant = (activeLayoutView === "saved" || networkMapActive || drawerHistoryVisible)' in js
    assert 'if (next === "saved" || networkMapSubviewActive) {' in js
    assert 'if (networkNodesTableActive) {' in js
    assert 'const shouldRefreshSelectedNodeHistoryForView = !!(' in js
    assert 'if (shouldRefreshSelectedNodeHistoryForView) {' in js
    assert 'function clearHiddenNodesTable(message = "Node list is hidden in this view.") {' in js
    assert 'tbody.dataset.meshHiddenNodesPlaceholder === "1"' in js
    assert 'delete tbody.dataset.meshHiddenNodesPlaceholder;' in js
    assert 'const rootChanged = networkGraphViewState.lastRootId !== rootId;' in js
    assert 'const pendingSelectedNodeCenterId = normalizeNodeId(networkGraphViewState.pendingSelectedNodeCenterId || "");' in js
    assert 'const selectedNodeCenterViewBox = shouldCenterSelectedNode' in js
    assert 'applyNetworkGraphViewBox(svg, selectedNodeCenterViewBox, { preserveRequestedCenter: true });' in js
    assert 'hiddenBroadcastOnlyCount: Math.max(0, Number(disconnectedVisibility.hiddenBroadcastOnlyCount) || 0),' in js
    assert 'hiddenDisconnectedCount: Math.max(0, Number(disconnectedVisibility.hiddenDetachedCount) || 0),' in js
    assert '&& !doesNetworkGraphViewBoxContainBounds(networkGraphViewState.viewBox, networkGraphViewState.bounds, 0.05)' in js
    assert 'const shouldRefitForModeChange = !!(' in js
    assert 'animateNetworkGraphViewBox(svg, fittedViewBox);' in js
    assert '} else if (rootChanged) {' in js
    assert 'layoutMode === "tree"' in js
    assert 'layoutMode === "cluster"' in js
    assert 'layoutMode === "community"' in js
    assert 'layoutMode === "spread"' not in js
    assert '<option value="spread"' not in js
    assert 'function resolveTreeLabelOffset(index, radius, amplitude = 16) {' in js
    assert 'return radius + amplitude + 2;' in js
    assert 'const compactSingleHopTree = maxTreeLayer === 1 && connectedCount <= 6;' in js
    assert 'const compactTreeColumnGap = Math.min(220, Math.max(150, treeWidth * 0.22));' in js
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
    graph_svg_css = css[css.index("#network-graph-svg {"):css.index("#network-graph-empty.signal-empty {")]
    assert "touch-action: none;" in graph_svg_css
    assert ".network-graph-stage.is-panning {" in css
    assert ".network-graph-stage.is-overlay-docked #network-graph-svg {" in css
    assert ".network-graph-mode-chip," in css
    assert ".network-graph-action-chip {" in css
    assert ".network-graph-layout-control {" in css
    assert ".network-graph-mode-control {" in css
    assert ".map-fullscreen-toggle-btn {" in css
    assert ".network-fullscreen-toggle-btn {" in css
    assert ".network-routes-primary-controls," in css
    assert ".network-routes-primary-controls .network-routes-toolbar {" in css
    assert ".network-routes-primary-controls .network-routes-toolbar .history-window-wrap {" in css
    assert ".network-graph-summary.is-overlay-docked .network-graph-action-chip {" in css
    assert ".network-top-nodes-primary-controls," in css
    assert ".network-top-nodes-primary-controls .network-top-nodes-toolbar {" in css
    assert ".network-top-nodes-primary-controls .network-top-nodes-refresh-btn {" in css
    assert ".network-sensors-primary-controls {" in css or ".network-sensors-primary-controls," in css
    assert ".network-sensors-primary-controls .env-metrics-controls {" in css
    assert ".network-sensors-primary-controls .env-metric-select {" in css
    assert ".network-map-subviews:fullscreen {" in css
    assert ".layout.view-network #network-map-panel-overview .network-overview-card {" in css
    assert ".layout.view-network #network-map-panel-overview #network-overview-chart-wrap {" in css
    assert ".layout.view-network #network-map-panel-routes .network-routes-card {" in css
    assert ".layout.view-network #network-map-panel-top10 .network-top-nodes-card {" in css
    assert ".layout.view-network #network-map-panel-sensors .env-metrics-explorer {" in css
    assert ".layout.view-network #network-map-panel-sensors #env-metrics-chart-wrap {" in css
    assert "border: 0;" in css
    assert "background: transparent;" in css
    assert '[data-theme="dark"] .map-fullscreen-toggle-btn {' in css
    assert ".network-graph-layout-select {" in css
    assert ".network-graph-mode-select {" in css
    assert ".network-routes-card {" in css
    assert ".network-routes-run-btn.is-running-trace {" in css
    assert ".network-routes-run-progress-fill {" in css
    assert ".network-routes-run-progress-text {" in css
    assert "[data-theme=\"dark\"] .network-routes-run-btn.is-running-trace:disabled {" in css
    assert "[data-theme=\"dark\"] .network-routes-run-progress-fill {" in css
    assert ".chat-node-telemetry-tool-run-btn.is-running-trace {" in css
    assert ".chat-node-telemetry-tool-progress-fill {" in css
    assert ".chat-node-telemetry-tool-progress-text {" in css
    assert "[data-theme=\"dark\"] .chat-node-telemetry-tool-run-btn.is-running-trace:disabled {" in css
    assert ".network-routes-mode-btn {" not in css
    assert ".network-route-scope {" in css
    assert ".network-route-scope-reset-btn {" in css
    assert ".network-route-scope-svg.is-panning {" in css
    assert ".network-route-scope-arrow-marker path {" in css
    assert ".network-route-scope-arrow-marker.is-route path {" in css
    assert ".network-route-scope-arrow-marker.is-return path {" in css
    assert ".network-route-scope-edge.is-route {" in css
    assert ".network-route-scope-edge.is-return {" in css
    assert ".network-route-scope-node-hit {" in css
    assert ".network-route-scope-node-city {" in css
    assert ".network-route-scope-node-city.is-estimated {" in css
    assert ".network-route-scope-node.has-emoji-glyph .network-route-scope-node-core {" in css
    assert ".network-route-scope-node-emoji-fo {" in css
    assert ".network-route-scope-node-emoji {" in css
    assert ".network-route-hop-list {" in css
    assert ".network-route-edge-bar {" in css
    assert ".network-route-edge-bars {" in css
    assert ".network-route-edge-cell.level-4 {" in css
    route_css_start = css.index(".network-routes-card {")
    route_css = css[route_css_start:css.index(".network-routes-toolbar {", route_css_start)]
    assert "rgba(249, 253, 249, 0.94)" in route_css
    route_hop_css_start = css.index(".network-route-hop {")
    route_hop_css = css[route_hop_css_start:css.index(".network-route-hop.is-local {", route_hop_css_start)]
    assert "rgba(255, 255, 255, 0.72)" in route_hop_css
    assert '[data-theme="dark"] .network-routes-card {' in css
    assert '[data-theme="dark"] .network-route-scope {' in css
    assert '[data-theme="dark"] .network-route-scope-reset-btn {' in css
    assert '[data-theme="dark"] .network-route-scope-arrow-marker path {' in css
    assert '[data-theme="dark"] .network-route-scope-arrow-marker.is-route path {' in css
    assert '[data-theme="dark"] .network-route-scope-arrow-marker.is-return path {' in css
    assert '[data-theme="dark"] .network-route-scope-edge.is-route {' in css
    assert '[data-theme="dark"] .network-route-scope-edge.is-return {' in css
    assert '[data-theme="dark"] .network-route-scope-node.has-emoji-glyph .network-route-scope-node-core {' in css
    assert '[data-theme="dark"] .network-route-scope-node-city {' in css
    assert '[data-theme="dark"] .network-route-scope-node-city.is-estimated {' in css
    assert '[data-theme="dark"] .network-route-hop {' in css
    assert '[data-theme="dark"] .network-route-hop-index {' in css
    assert "[data-theme=\"dark\"] .network-graph-layout-control," in css
    assert "[data-theme=\"dark\"] .network-graph-mode-control {" in css
    assert "[data-theme=\"dark\"] .network-graph-layout-select," in css
    assert "[data-theme=\"dark\"] .network-graph-mode-select {" in css
    assert "color-scheme: light;" in css
    assert "color-scheme: dark;" in css
    assert ".network-graph-layout-select option," in css
    assert ".network-graph-mode-select option {" in css
    assert ".network-graph-layout-select option:checked," in css
    assert ".network-graph-mode-select option:checked {" in css
    assert "[data-theme=\"dark\"] .network-graph-layout-select option," in css
    assert "[data-theme=\"dark\"] .network-graph-mode-select option {" in css
    assert ".layout.view-network .history-select-chip-hide-label .history-metric-select option," in css
    assert ".layout.view-network .map-heatmap-mode option {" in css
    assert "[data-theme=\"dark\"] .layout.view-network .history-select-chip-hide-label .history-metric-select option," in css
    assert "[data-theme=\"dark\"] .layout.view-network .map-heatmap-mode option {" in css
    assert "color: var(--ink);" in css
    assert "background: color-mix(in srgb, var(--panel) 92%, var(--bg) 8%);" in css
    assert "background: color-mix(in srgb, var(--panel) 76%, var(--accent) 24%);" in css
    assert "color: var(--workspace-shell-text);" in css
    assert "background: var(--workspace-shell-bg-alt);" in css
    assert "background: var(--workspace-shell-active-bg);" in css
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
    assert ".network-graph-edge.is-spread-link {" not in css
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
    assert "[data-theme=\"dark\"] .network-graph-edge.is-spread-link {" not in css
    assert "stroke: var(--theme-base-color, var(--ui-accent));" in css
    assert "[data-theme=\"dark\"] .network-graph-tag-route {" in css
    assert "[data-theme=\"dark\"] .network-graph-self-path-segment {" in css
    assert "[data-theme=\"dark\"] .network-graph-tag-filter {" in css
    assert ".network-graph-ring.is-broadcast-only {" in css
    assert ".network-graph-node.is-local .network-graph-node-core {" in css
    assert ".network-graph-node.is-tagged .network-graph-node-core {" in css
    assert ".network-graph-node.is-spread-actual" not in css
    assert ".network-graph-node.is-spread-estimated" not in css
    assert "stroke: var(--node-tag-color, #2aa85a);" in css
    assert "[data-theme=\"dark\"] .network-graph-node.is-tagged .network-graph-node-core {" in css
    assert "[data-theme=\"dark\"] .network-graph-node.is-spread-estimated" not in css
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
