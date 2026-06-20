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
    assert 'class="map-control-group map-heatmap-controls"' not in html
    assert 'id="map-heatmap-mode"' not in html


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
    assert 'const mapPacketLinesStorageKey = "meshDashboardMapPacketLinesEnabledV2";' in js
    assert "let mapPacketLinesEnabled = false;" in js
    assert 'const mapLinkModeStorageKey = "meshDashboardMapLinkModeV1";' in js
    assert 'const mapNodeLayerVisibilityStorageKey = "meshDashboardMapNodeLayerVisibilityV1";' in js
    assert 'const mapLiveActivityStorageKey = "meshDashboardMapLiveActivityEnabledV1";' in js
    assert "let mapActualNodesEnabled = true;" in js
    assert "let mapLinkInferredNodesEnabled = true;" in js
    assert "let mapRssiTrilateratedNodesEnabled = true;" in js
    assert "function updateMapPacketLinesControl()" in js
    assert "function bindMapPacketLinesControl()" in js
    assert "function updateMapLinkLayerControl()" in js
    assert "function normalizeMapLinkLayerMode(value) {" in js
    assert "function loadMapPacketLinesPreference()" in js
    assert "function loadMapLinkLayerModePreference()" in js
    assert "function persistMapNodeLayerVisibilityPreference()" in js
    assert "function loadMapNodeLayerVisibilityPreference()" in js
    assert 'runBootStep("loadMapNodeLayerVisibilityPreference", () => loadMapNodeLayerVisibilityPreference());' in js
    assert "function bindMapLinkLayerControl()" in js
    assert "function updateMapLiveActivityControl()" in js
    assert "function loadMapLiveActivityPreference()" in js
    assert "function bindMapLiveActivityControl()" in js
    assert "let mapLinkLegendOffsetRaf = null;" in js
    assert "function mapLinkLayerModeParts(modeName = mapLinkLayerMode)" in js
    assert "function mapEstimatedLineTrafficValue(line)" in js
    assert "function mapEstimatedLineTrafficPct(line, maxTrafficValue)" in js
    assert "function mapEstimatedLineCorridorKey(line)" in js
    assert "function mergeMapEstimatedLineCorridors(lines)" in js
    assert "function selectMapEstimatedLinesForRender(lines, options = null)" in js
    assert "function mapEstimatedLinkRenderScore(line, nowUnix)" in js
    assert 'estimated: mode !== "none",' in js
    assert "function renderMapLinkLegend(nodes = [], rawEdges = [], estimatedPositions = new Map(), linkOverlay = null)" in js
    assert "function bindMapLinkLegendControls(legend)" in js
    assert 'data-map-link-legend-toggle="signal-heatmap"' in js
    assert 'data-map-link-legend-toggle="signal-coverage"' not in js
    assert 'data-map-link-legend-toggle="signal-live"' not in js
    assert 'data-map-link-legend-toggle="packet"' in js
    assert 'data-map-link-legend-toggle="estimated-heatmap"' in js
    assert 'data-map-link-legend-toggle="real-nodes"' in js
    assert 'data-map-link-legend-toggle="link-inferred-nodes"' in js
    assert 'data-map-link-legend-toggle="rssi-trilaterated-nodes"' in js
    assert 'data-map-link-legend-toggle="estimated"' in js
    assert "Map layers" in js
    assert "Signal heatmap" in js
    assert 'applySignalHeatmapMode(signalHeatmapToggle.checked ? "both" : "none");' in js
    assert "Inferred heatmap" in js
    assert 'collectSignalHeatmapBuckets(nodes, signalHeatProfile, "coverage")' in js
    assert 'collectSignalHeatmapBuckets(nodes, signalHeatProfile, "live")' in js
    assert "signalCoverageBuckets = maskSignalCoverageBucketsWithLive(signalCoverageBuckets, signalLiveBuckets);" in js
    assert "const signalHeatmapPointCount = (" in js
    assert "+ signalHeatmapBucketPointCount(signalLiveBuckets)" in js
    assert "const inferredHeatmapCount = Math.max(" in js
    assert "Common paths" in js
    assert 'renderMapLinkLegend(nodes, mapRenderEdges, estimatedPositions, linkOverlay);' in js
    assert 'mapElement.style.setProperty("--map-link-legend-space"' in js
    assert "networkSubviewUsesMap(activeNetworkSubview)" in js
    assert "mapLinkLayerModeForCurrentView(mapLinkLayerMode)" in js
    assert "networkGraphRawEdgesForMode(edges, spreadEdgeMode)" not in js
    assert "const mapRenderEdges = edges;" in js
    assert 'const effectiveMapLinkMode = (typeof mapLinkLayerModeForCurrentView === "function")' in js
    assert '? (spreadEdgeMode === "live" ? "live" : "history")' not in js
    assert "lastMapSignature = \"\";" in js
    assert "Link-inferred nodes" in js
    assert "Inferred nodes" not in js
    assert "RSSI trilaterated" in js
    assert "let trilateratedCount = 0;" in js
    assert "let signalHeatmapCoverageEnabled = true;" in js
    assert "let signalHeatmapLiveEnabled = true;" in js
    assert 'let signalHeatmapMode = "both";' in js
    assert 'const legacySignalHeatmapModeStorageKey = "meshDashboardSignalHeatmapModeV1";' in js
    assert 'const signalHeatmapModeStorageKey = "meshDashboardSignalHeatmapModeV2";' in js
    assert "function signalHeatmapModeFromLayerToggles()" in js
    assert 'if (signalHeatmapCoverageEnabled && signalHeatmapLiveEnabled) return "both";' in js
    assert 'signalHeatmapMode = legacyMode === "coverage" ? "both" : legacyMode;' in js
    assert 'style="--map-link-legend-color:#cc79a7;"' in js
    assert "is-node-trilaterated" in js
    assert 'mapActualNodesEnabled ? " checked" : ""' in js
    assert 'mapLinkInferredNodesEnabled ? " checked" : ""' in js
    assert 'mapRssiTrilateratedNodesEnabled ? " checked" : ""' in js
    assert "const markerKindVisible = markerKind === \"actual\"" in js
    assert 'if (!markerKindVisible) continue;' in js
    assert "{ bypassNodeFade: true }" in js
    assert "bypassNodeFade: !!opts.bypassNodeFade," in js
    assert "const bypassNodeFade = !!renderOpts.bypassNodeFade;" in js
    assert "Real nodes" in js
    assert "Real links" in js
    assert 'mapLiveActivityEnabled = true;' in js
    assert 'wrap.hidden = true;' in js
    assert 'toggle.checked = true;' in js
    assert 'toggle.disabled = true;' in js
    assert "function estimatedMarkerStyle(isSelected, confidence = 0.5, isLocal = false)" in js
    assert "function buildMapLinkLayerOverlay(nodes, rawEdges, options = null)" in js
    assert "function buildMapLinkEstimateDensityOverlay(linkOverlay, options = null)" in js
    assert "const mapEstimatedPositionSmoothingById = new Map();" in js
    assert "let mapEstimatedPositionSmoothingActive = false;" in js
    assert "const mapEstimatedPositionSmoothingMaxAgeMs = 600000;" in js
    assert "const mapEstimatedOverlayDriftMs = 18000;" in js
    assert "const mapEstimatedOverlayMaxFrameAdvanceMs = 32;" in js
    assert "const mapEstimatedOverlayMaxDriftMeters = 4800;" in js
    assert "const mapEstimatedOverlayLongJumpFadeMs = 1400;" in js
    assert "const mapHeatLayerFadeInMs = 9000;" in js
    assert "const mapHeatLayerFadeOutMs = 9000;" in js
    assert "const mapHeatLayerDriftMinIntensity = 0.004;" in js
    assert "const mapLinkMinEstimateAnchors = 2;" in js
    assert "const mapLinkMinEstimateConfidence = 0.18;" in js
    assert "const mapLinkMinCityEstimateAnchors = 3;" in js
    assert "const mapLinkMinCityEstimateConfidence = 0.45;" in js
    assert "const mapLinkMinCityEstimateFit = 0.42;" in js
    assert "const mapLinkMinTrilaterationAnchors = 4;" in js
    assert "const mapLinkMinTrilaterationSignalSamples = 2;" in js
    assert "const mapLinkMinTrilaterationConfidence = 0.48;" in js
    assert "const mapLinkMinTrilaterationFit = 0.45;" in js
    assert "const mapLinkMaxTrilaterationHops = 1.25;" in js
    assert "const mapLinkMaxTrilaterationAgeSeconds = 7200;" in js
    assert "function smoothMapEstimatedPosition(nodeId, target, options = null)" in js
    assert "function smoothMapEstimatedPositions(estimates, options = null)" in js
    assert "function smoothMapLinkLineEndpoints(lines, smoothedEstimates)" in js
    assert "function smoothMapLinkLayerOverlay(linkOverlay, options = null)" in js
    assert "function mapLinkEdgeLocationWeight(edge)" in js
    assert "function mapLinkEstimateResidualForNode(nodeId, positions, adjacency)" in js
    assert "function mapLinkConfidenceFromFit(baseConfidence, fitScore, anchorCount)" in js
    assert "function mapLinkRangeFromSignal(edge)" in js
    assert "function solveMapRssiTrilateration(nodeId, seedPosition, anchors)" in js
    assert "function buildMapRssiTrilaterationEstimates(positions, adjacency, options = null)" in js
    assert "function ensureBackendLocationEstimates(modeRaw, options = null)" in js
    assert 'fetch(`/api/history/location_estimates?${params.toString()}`' in js
    assert "function backendLocationEstimateSignature(estimates)" in js
    assert "function updateBackendLocationEstimateSignature(windowName, estimates)" in js
    assert "let networkMapPacketActivityPrimed = false;" in js
    assert "function seedNetworkMapPacketActivityTokens(state = latestState)" in js
    assert "if (networkMapVisible && !networkMapPacketActivityPrimed)" in js
    assert "networkMapPacketActivityPrimed = true;" in js
    assert "let estimates = new Map(backendEstimates);" in js
    assert "if (backendEstimates.size > 0 || (backendRequestPending && !backendCacheKnown))" in js
    assert "const rssiTrilaterationEstimates = buildMapRssiTrilaterationEstimates" in js
    assert 'estimateSource: "rssi_trilateration",' in js
    assert "RSSI trilaterated" in js
    assert "const minEstimateAnchors = Math.max(" in js
    assert "if (estimateAnchorCount < minEstimateAnchors) continue;" in js
    assert "if (adjustedConfidence < minEstimateConfidence) continue;" in js
    assert "confidence: adjustedConfidence," in js
    assert "rawConfidence: meta.confidence," in js
    assert "fitScore," in js
    assert "residualKm: residual && residual.residualKm != null ? residual.residualKm : null," in js
    assert "function animateMapPolylineLatLngs(layer, targetPathRaw, options = null)" in js
    assert "function animateMapMarkerLatLng(marker, targetLatLngRaw, options = null)" in js
    assert "function animateMapHeatLayerLatLngs(layer, targetPointsRaw, options = null)" in js
    assert "function animateMapHeatLayerCanvasOpacity(layer, targetOpacityRaw, options = null)" in js
    assert "function fadeOutMapHeatLayer(layer, options = null)" in js
    assert "function fadeMapNodeMarker(marker, options = null)" in js
    assert "function fadeInMapNodeMarker(marker, options = null)" in js
    assert "function fadeOutMapNodeMarker(marker, options = null)" in js
    assert "function mapNodeMarkerStyleWithOpacityScale(baseStyleRaw, scale)" in js
    assert "function setMapNodeMarkerElementOpacity(marker, opacityRaw)" in js
    assert "function releaseMapNodeMarkerElementOpacityPrime(marker)" in js
    assert "function bindMapNodeMarkerElementOpacitySync(marker)" in js
    assert "function mapNodeMarkerFadeScale(marker, fallbackScale = 1)" in js
    assert "function mapNodeMarkerIsFadingOut(marker)" in js
    assert 'marker.on("add", () => {' in js
    assert (
        'function createMapNodeMarker(lat, lon, nodeId, isSelected, markerKind = "actual", '
        'markerConfidence = 0.45, state = latestState, options = null)'
        in js
    )
    assert 'const mapNodeMarkerPaneName = "mapNodeMarkerPane";' in js
    assert "function ensureMapNodeMarkerPane()" in js
    assert 'pane.style.zIndex = "620";' in js
    assert "pane: mapNodeMarkerPaneName," in js
    assert "markerStyle.pane = mapNodeMarkerPaneName;" in js
    assert 'radius: 6.4,' in js
    assert 'color: "#062f20",' in js
    assert 'fillOpacity: 0.9,' in js
    assert 'weight: 1.8,' in js
    assert "function trilateratedMarkerStyle(isSelected, confidence = 0.5, isLocal = false)" in js
    assert 'color: "#cc79a7",' in js
    assert 'fillColor: "#f4a7c7",' in js
    assert '? (estimateSource === "rssi_trilateration" ? "trilaterated" : "estimated")' in js
    assert "function advanceMapDriftAnimationElapsedMs(state, timestampMs)" in js
    assert "Math.min(frameDeltaMs, maxFrameAdvanceMs)" in js
    assert "const elapsedMs = advanceMapDriftAnimationElapsedMs(state, timestampMs);" in js
    assert "const activeState = layer._meshPolylineDriftAnimation;" in js
    assert "mapLatLngPathsSameEnough(activeState.toPath, targetPath)" in js
    assert "const activeState = marker._meshMarkerDriftAnimation;" in js
    assert "mapLatLngPointsSameEnough(activeState.toPoint, targetPoint)" in js
    assert "const activeState = layer._meshHeatDriftAnimation;" in js
    assert "mapHeatPointsSameEnough(activeState.targetPoints, targetPoints)" in js
    assert "const activeState = layer._meshHeatOpacityAnimation;" in js
    assert "setMapHeatLayerCanvasOpacity(layer, bypassFade ? 1 : 0);" in js
    assert "if (bypassFade) {" in js
    assert "const activeFadeState = (marker._meshMapNodeMarkerFadeAnimation" in js
    assert "const existingMarkerFadingOut = !!(" in js
    assert "&& !existingMarkerFadingOut" in js
    assert "mapNodeMarkerFadeScale(" in js
    assert "} else {\n              const activeFadeBaseStyle = resolveMapNodeMarkerStyle(" in js
    assert "setMapNodeMarkerOpacityScale(marker, activeFadeScale, activeFadeBaseStyle);" in js
    assert "primeElementOpacity: false," in js
    assert "currentScale: fromScale," in js
    assert "state.currentScale = currentScale;" in js
    assert "releaseMapNodeMarkerElementOpacityPrime(marker);" in js
    assert "renderMap(nodes, edges, nodeHistory = null, options = null)" in js
    assert "refreshNetworkMapAfterLegendControlChange(options = null)" in js
    assert "{ bypassHeatmapFade: true }" in js
    assert "let networkMapGraphRenderSeen = false;" in js
    assert "let mapViewportInteractionActive = false;" in js
    assert "let mapHeatLayerViewportSyncRaf = null;" in js
    assert "const allowEstimatedNodeFade = !!networkMapGraphRenderSeen && !bypassNodeFade;" in js
    assert "networkMapGraphRenderSeen = true;" in js
    assert "animate: opts.animate === true," in js
    assert "resetMapViewToMostNodes({ animate: false });" in js
    assert "const snapToTarget = !!opts.snapToTarget || !!mapViewportInteractionActive;" in js
    assert "function requestMapHeatLayersViewportSync()" in js
    assert "function beginMapViewportInteraction()" in js
    assert "function syncMapViewportInteractionFrame()" in js
    assert "function endMapViewportInteraction()" in js
    assert "map.on(\"move\", () => {" in js
    assert "syncSignalHeatmapLayer(nodes, true, { bypassFade: true });" in js
    assert "syncSignalHeatmapLayer(nodes, activeLayoutView === \"saved\", { bypassFade: true });" in js
    assert "animateMapHeatLayerCanvasOpacity(layer, 1, {" in js
    assert "activeState.onComplete = onComplete;" in js
    assert "marker._meshMapNodeMarkerFadeBaseStyle = resolvedStyle;" in js
    assert "setMapNodeMarkerOpacityScale(marker, activeFadeScale, resolvedStyle);" in js
    assert "markerDriftMeters > mapEstimatedOverlayMaxDriftMeters" in js
    assert "cancelMapNodeMarkerFade(existingMarker);\n              cancelMapMarkerDrift(existingMarker);\n              nodeLayer.removeLayer(existingMarker);" in js
    assert "fadeMarkerInitialStyle = mapNodeMarkerStyleWithOpacityScale(fadeMarkerBaseStyle, 0);" in js
    assert "initialStyle: fadeMarkerInitialStyle," in js
    assert "initialElementOpacity: 0," in js
    assert "setMapNodeMarkerElementOpacity(marker, 0);" in js
    assert "setMapNodeMarkerOpacityScale(marker, 0, marker._meshMapNodeMarkerFadeBaseStyle);" in js
    assert "fadeInMapNodeMarker(marker, {" in js
    assert "if (fadeExistingEstimatedMarkerOut && allowEstimatedNodeFade)" in js
    assert "const fadeEstimatedMarkerIn = !!(\n            allowEstimatedNodeFade" in js
    assert 'if ((staleMarkerKind === "estimated" || staleMarkerKind === "trilaterated") && allowEstimatedNodeFade)' in js
    assert 'if (!(typeof mapNodeMarkerIsFadingOut === "function" && mapNodeMarkerIsFadingOut(marker)))' in js
    assert "if (nodeMarkers.get(nodeId) === marker)" in js
    assert "function mapLatLngPathMaxDistanceMeters(a, b)" in js
    assert "function mapHeatPointDistanceMeters(a, b)" in js
    assert "!Number.isFinite(pathDriftMeters) || pathDriftMeters > maxDriftMeters" in js
    assert "!Number.isFinite(driftMeters) || driftMeters > maxDriftMeters" in js
    assert 'key: `${targetPoint.key}:out`,' in js
    assert 'key: `${targetPoint.key}:in`,' in js
    assert "onComplete: typeof opts.onComplete === \"function\"" not in js
    assert "const onComplete = typeof opts.onComplete === \"function\" ? opts.onComplete : null;" in js
    assert "fadeOut: !!opts.fadeOut," in js
    assert "if (state && state.fadeOut) return true;" in js
    assert "function cancelMapPolylineDrift(layer)" in js
    assert "function cancelMapMarkerDrift(marker)" in js
    assert "function cancelMapHeatLayerDrift(layer, clearPoints = false)" in js
    assert "function cancelMapHeatLayerOpacityFade(layer)" in js
    assert "const shouldRenderGraph = graphChanged || !!mapEstimatedPositionSmoothingActive;" in js
    assert "if (!shouldRenderGraph && signature === lastMapSignature)" in js
    assert 'const allowInitialNetworkNodeFade = activeLayoutView === "network" && !networkMapGraphRenderSeen && !bypassNodeFade;' in js
    assert "const fadeInitialMarkerIn = !!(" in js
    assert "durationMs: fadeInitialMarkerIn ? 520 : mapEstimatedOverlayLongJumpFadeMs" in js
    assert "&& effectiveMapLinkMode !== \"both\"" in js
    assert ": rawLinkOverlayUnsmoothed;" in js
    assert "const densitySourceOverlay = smoothMapLinkLayerOverlay(densitySourceOverlayUnsmoothed, {" in js
    assert "const rawLinkOverlay = smoothMapLinkLayerOverlay(rawLinkOverlayUnsmoothed, {" in js
    assert "mapEstimatedPositionSmoothingActive = anyActive;" in js
    assert "rawLat: targetLat," in js
    assert "rawLon: targetLon," in js
    assert "copy.fromLat = Number(fromEstimate.lat);" in js
    assert "copy.toLat = Number(toEstimate.lat);" in js
    assert "const canDriftExistingEstimatedMarker = !!(" in js
    assert "animateMapMarkerLatLng(marker, [markerLat, markerLon], {" in js
    assert "marker._meshMapNodeInfoBinding = {" in js
    assert 'heatPoint._meshHeatKey = `signal-node:${heatNodeId}`;' in js
    assert 'heatPoint._meshHeatKey = `estimate-node:${point.nodeId}`;' in js
    assert "const cloudIdBase = `c${(cloudHash >>> 0).toString(16)}`;" in js
    assert "for (const memberNodeId of cloudNodeIds.slice().sort())" in js
    assert "const estimateLinesToRender = selectMapEstimatedLinesForRender(estimateLinesAvailable, {" in js
    assert "linkOverlay.renderedEstimatedLineCount = estimateLinesToRender.length;" in js
    assert "animateMapPolylineLatLngs(line, linePath, {" in js
    assert "linkEstimateLayer.removeLayer(existingLine);" not in js
    assert "renderTrafficPct: mapEstimatedLineTrafficPct(line, maxTrafficValue)," in js
    assert "key: `corridor::${key}`," in js
    assert "Traffic: ${trafficLabel} weighted packet" in js
    assert "const signalHeatmapGradientCoverage = {" in js
    assert "const signalHeatmapGradientLiveContrast = {" in js
    assert '0.46: "#0a9396",' in js
    assert '1.0: "#caf0f8",' in js
    assert "function resolveSignalHeatGradient(mode = signalHeatmapMode) {" in js
    assert "Signal heatmap is controlled from the map legend." in js
    assert "function signalHeatmapPaneNameForMode(mode = \"coverage\")" in js
    assert 'pane.style.zIndex = key === "live" ? "431" : "430";' in js
    assert "function ensureSignalHeatmapLayers(mode = \"coverage\")" in js
    assert "layer._meshSignalHeatmapMode = key;" in js
    assert "function applySignalHeatmapLayerCanvasStacking(layer, mode = \"coverage\")" in js
    assert 'const zIndex = key === "live" ? 431 : 430;' in js
    assert "canvas.style.zIndex = String(zIndex);" in js
    assert "canvas.dataset.meshSignalHeatmapMode = key;" in js
    assert "collectSignalHeatmapBuckets(nodes, profile, mode)" in js
    assert "collectSavedNodeHeatmapBuckets(nodes, profile, mode)" in js
    assert "function signalHeatmapPointMaskKey(point)" in js
    assert "function signalHeatmapBucketPointCount(buckets)" in js
    assert "function maskSignalCoverageBucketsWithLive(coverageBuckets, liveBuckets)" in js
    assert "function signalHeatmapMapHasDrawableSize()" in js
    assert "const mapDrawable = signalHeatmapMapHasDrawableSize();" in js
    assert "&& mapDrawable" in js
    assert "gradient: resolveSignalHeatGradient(mode)," in js
    assert "gradient: state.gradient," in js
    assert 'let lastSignalHeatmapSignature = "";' in js
    assert "const heatSignature = `signal-heatmap:${(heatSignatureHash >>> 0).toString(16)}`;" in js
    assert "heatSignature === lastSignalHeatmapSignature && heatLayerPresenceMatches" in js
    assert "animateMapHeatLayerLatLngs(layer, state.buckets[i] || [], {" in js
    assert "keyPrefix: `signal:${state.mode}:${i}`," in js
    assert "function syncSignalHeatmapLayer(nodes, forceHide = false, options = null)" in js
    assert "const bypassFade = !!opts.bypassFade;" in js
    assert "coverageState.buckets = maskSignalCoverageBucketsWithLive(coverageState.buckets, liveState.buckets);" in js
    assert "applySignalHeatmapLayerCanvasStacking(layer, state.mode);" in js
    assert 'const liveRadiusMul = state.mode === "live" ? 0.72 : 1;' not in js
    assert 'const liveBlurMul = state.mode === "live" ? 0.68 : 1;' not in js
    assert "const desiredLayerVisible = !!(shouldShow && !(savedSingleNodeMode && i > 0));" in js
    assert "if (!desiredLayerVisible) {" in js
    assert "removeSignalHeatmapLayerSafely(layer, { fade: !bypassFade });" in js
    assert "function removeSignalHeatmapLayerSafely(layer, options = null)" in js
    assert 'fadeOutMapHeatLayer(layer, {' in js
    assert 'keyPrefix: "signal:fade",' in js
    assert "cancelMapHeatLayerDrift(layer, true);" in js
    assert "cancelMapHeatLayerOpacityFade(layer);" in js
    assert "function hideSignalHeatmapLayers()" in js
    assert "function cancelSignalHeatmapLayerFrame(layer)" in js
    assert "typeof hideSignalHeatmapLayers === \"function\"" in js
    assert "typeof clearLinkEstimateHeatmapLayer === \"function\"" in js
    assert "hideEstimatedMarkers: false," in js
    assert "hideEstimatedMarkers: clouds.length > 0," not in js
    assert "cloudLinks" in js
    assert "cloudLink: true," in js
    assert "nodeMarkerKinds" in js
    assert "nodeMarkerConfidence" in js
    assert "linkEstimateLayer" in js
    assert "let linkEstimateHeatmapLayer = null;" in js
    assert 'const linkEstimateHeatmapPaneName = "linkEstimateHeatmapPane";' in js
    assert "function clearLinkEstimateHeatmapLayer(options = null)" in js
    assert "function syncLinkEstimateHeatmapLayer(linkDensity = null, show = false, options = null)" in js
    assert 'typeof signalHeatmapMapHasDrawableSize === "function"' in js
    assert "const shouldShow = !!show && mapDrawable && heatPoints.length > 0;" in js
    assert "clearLinkEstimateHeatmapLayer({ fade: !bypassFade });" in js
    assert "cancelMapHeatLayerDrift(layer, true);" in js
    assert 'keyPrefix: "estimate",' in js
    assert "durationMs: mapHeatLayerFadeOutMs," in js
    assert "animateMapHeatLayerLatLngs(layer, heatPoints, {" in js
    assert "syncLinkEstimateHeatmapLayer(linkDensity, true, { bypassFade: bypassHeatmapFade });" in js
    assert "const useCloudConsolidation" not in js
    assert "Array.isArray(linkOverlay.lines) ? linkOverlay.lines.slice() : []" in js
    assert 'activeLayoutView === "network"' in js
    assert "const hideEstimatedLinkDots = !!(" not in js
    assert 'if (estimateSource !== "rssi_trilateration" && !linkedEstimatedNodeIds.has(nodeId)) continue;' not in js
    assert 'if (hideEstimatedLinkDots && isEstimated && markerKind !== "trilaterated") continue;' not in js
    assert 'Inferred nodes${hideLinkedDots ? " (hidden)" : ""}' not in js
    assert '<span class="map-link-legend-name">Inferred heatmap</span>' in js
    assert '<span class="map-link-legend-name">Link-inferred nodes</span>' in js
    assert '<span class="map-link-legend-name">RSSI trilaterated</span>' in js
    assert "Topology Fit" in js
    assert "Avg Fit Error" in js
    assert 'label: "Inferred",' in js
    assert "Heuristic span" in js
    assert "Inferred endpoints" in js
    assert "live link-inferred location" in js
    assert "estimateMode: \"live\"," in js
    assert "minEstimateAnchors: mapLinkMinCityEstimateAnchors," in js
    assert "minEstimateConfidence: mapLinkMinCityEstimateConfidence," in js
    assert "minEstimateFit: mapLinkMinCityEstimateFit," in js
    assert "estimateLine && estimateLine.avgHops ??" not in js
    assert "estimateLine && estimateLine.avgSnr ??" not in js
    assert "estimateLine && estimateLine.avgRssi ??" not in js
    assert "No earlier links focus yet" in js
    assert "Links view is already centered on the local node" in js


def test_dashboard_js_uses_single_popup_for_map_node_hover_and_click() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    overlay_start = js.index("function bindMapNodeInfoOverlays(")
    overlay_end = js.index("function buildMapEmojiMarkerIcon(", overlay_start)
    overlay_block = js[overlay_start:overlay_end]

    assert 'return !!(typeof marker.isPopupOpen === "function" && marker.isPopupOpen());' in js
    assert "const overlayNodeId = normalizeNodeId(opts.nodeId || (node && node.id) || \"\");" in js
    assert "const hoverPopupSuppressed = () => {" in js
    assert "!!opts.suppressHoverTooltip || popupIsOpen() || !!(overlayNodeId && selectedId === overlayNodeId)" in js
    assert "const popupFadeMs = 180;" in js
    assert "const popupEnterDelayMs = 220;" in js
    assert "const popupLeaveDelayMs = 180;" in js
    assert "let markerHovering = false;" in js
    assert "let popupHovering = false;" in js
    assert "let popupOpenTimer = null;" in js
    assert "const scheduleHoverPopupClose = () => {" in js
    assert "const finishHoverPopupOpen = () => {" in js
    assert "const scheduleHoverPopupOpen = () => {" in js
    assert "popupOpenTimer = window.setTimeout(finishHoverPopupOpen, popupEnterDelayMs);" in js
    assert 'popupEl.classList.add("is-closing");' in js
    assert 'popupEl.classList.remove("is-closing");' in js
    assert "const previousBinding = marker._meshMapNodeInfoBinding;" in js
    assert "previousBinding.clear();" in js
    assert "const onMouseOver = () => {" in js
    assert "const onMouseOut = () => {" in js
    assert "const onPopupClose = () => {" in js
    assert 'marker.on("mouseover", onMouseOver);' in js
    assert 'marker.on("mouseout", onMouseOut);' in js
    assert 'marker.on("popupclose", onPopupClose);' in js
    assert 'marker.off("mouseover", onMouseOver);' in js
    assert 'marker.off("mouseout", onMouseOut);' in js
    assert 'marker.off("popupclose", onPopupClose);' in js
    assert "if (!markerHovering || hoverPopupSuppressed()) return;" in js
    assert "marker.openPopup();" in js
    assert "scheduleHoverPopupOpen();" in js
    assert "onEnter: () => {" in js
    assert "onLeave: () => {" in js
    assert "marker.bindTooltip(" not in overlay_block
    assert "tooltipHtml" not in overlay_block
    assert "map-node-tooltip-measure" not in overlay_block
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
    assert (
        "function prepareMapNodePopupElement(popupEl, fallbackNodeId = \"\", "
        "closePopupFn = null, hoverHandlers = null)"
    ) in js
    assert 'popupEl.style.pointerEvents = "auto";' in js
    assert "L.DomEvent.disableClickPropagation(popupEl);" in js
    assert "L.DomEvent.disableScrollPropagation(popupEl);" in js
    assert 'popupEl.dataset.hoverBound = "1";' in js
    assert "function bindMapNodePopupActionDelegates()" in js
    assert "const includeActions = opts.includeActions !== false;" in js
    assert "const quickActions = includeActions && isSelectableNodeId(actionNodeId)" in js
    assert "const popupHtml = buildMapNodeInfoHtml(node, Object.assign({}, opts, { includeActions: true }));" in js
    assert "marker.bindPopup(popupHtml, {" in js
    assert 'document.body.dataset.mapNodePopupActionsBound = "1";' in js
    assert 'document.body.dataset.mapNodePopupPropagationBound = "1";' in js
    assert 'document.addEventListener("click", (clickEv) => {' in js
    assert "handleMapNodePopupActionClick(clickEv);" in js
    assert 'runBootStep("bindMapNodePopupActionDelegates", () => bindMapNodePopupActionDelegates());' in js
    assert "prepareMapNodePopupElement(popupEl, overlayNodeId, () => {" in js
    assert "closeOnClick: false," in js
    assert "maxWidth: 340," in js
    assert 'data-map-node-action="${escAttr(cleanAction)}"' in js
    assert 'mapNodePopupActionButtonHtml("Message", "message", actionNodeId)' in js
    assert 'mapNodePopupActionButtonHtml("Trace", "trace", actionNodeId)' in js
    assert 'mapNodePopupActionButtonHtml("Open details", "details", actionNodeId)' in js

    css = build_dashboard_css(theme_css="")
    assert ".map-node-popup .map-node-info-action-btn {" in css
    popup_pointer_section = css.split(".map-node-popup,", 1)[1].split("}", 1)[0]
    assert "pointer-events: auto;" in popup_pointer_section
    assert ".map-node-popup.is-closing .leaflet-popup-content-wrapper," in css
    assert "transition: opacity 180ms ease;" in css
    assert "opacity: 0;" in css


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
    assert 'selectNode(nodeId, true, false);' not in trace_block
    assert 'setChatNodeDetailsDrawerTab("telemetry", { fetchHistory: false });' not in trace_block
    assert 'tab: "telemetry",' not in trace_block
    assert "setChatNodeDetailsDrawerExpanded" not in trace_block
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
    assert ".map-link-legend-swatch.is-node-trilaterated::before {" in css
    assert "var(--map-link-legend-color, #cc79a7)" in css
    assert ".map-link-legend-swatch.is-link-heat::before {" in css
    assert ".map-link-legend-swatch.is-signal-heat::before" in css
    assert "#a96800 42%, #0a9396 58%" in css
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
    assert "const mapNodeActivityPositionById = new Map();" in js
    assert "const mapNodeActivityDirectionRecords = new Set();" in js
    assert "const mapNodeActivityDirectionMaxRecords = 48;" in js
    assert "const mapTracePathRecords = new Set();" in js
    assert "const mapTracePathMaxRecords = 8;" in js
    assert "const mapTraceResultFlashById = new Map();" in js
    assert "const mapEstimatedCorridorActivityPathsByKey = new Map();" in js
    assert "const mapNodeTransmitPulseRings = new Set();" in js
    assert "const mapNodeTransmitPulseMaxRings = 72;" in js
    assert "let mapTraceProgressTimer = null;" in js
    assert 'const mapNodeMarkerPaneName = "mapNodeMarkerPane";' in js
    assert 'const mapTransmitPulsePaneName = "mapTransmitPulsePane";' in js
    assert "let mapNodeActivityFlashRaf = null;" in js
    assert "let lastNetworkMapPacketTokens = new Set();" in js
    assert "function isNetworkMapActivityFlashVisible()" in js
    assert "function isNetworkMapTraceProgressVisible()" in js
    assert "function currentNetworkMapTraceProgressState(nowMs = Date.now())" in js
    assert "function mapNodeTraceProgressState(nodeId, nowMs = Date.now())" in js
    assert "function isNetworkMapTraceProgressActive(nowMs = Date.now())" in js
    assert "function triggerNetworkMapTraceResultFlash(rawNodeId, ok, nowMs = Date.now())" in js
    assert "function mapNodeTraceResultFlashState(nodeId, nowMs = Date.now())" in js
    assert "function pruneExpiredMapTraceResultFlashes(nowMs = Date.now())" in js
    assert "function mapPacketActivityToken(packetEntry)" in js
    assert "function mapPacketActivityEndpointIds(packetEntry)" in js
    assert "function mapPacketActivityPortnum(packetEntry)" in js
    assert "function mapPacketActivityShouldAnimateDirection(packetEntry)" in js
    assert "function mapLocalEchoActivityEndpointIds(chatEntry, localNodeId = \"\")" in js
    assert "function mapLocalEchoActivityToken(chatEntry, localNodeId = \"\")" in js
    assert "function isMapLocalEchoActivityEntry(chatEntry, localNodeId = \"\")" in js
    assert "function mapPacketActivityNodeIds(packetEntry)" in js
    assert "function mapPacketActivityTransmitNodeId(packetEntry)" in js
    assert "function mapPacketActivitySignalLevel(packetEntry)" in js
    assert "function mapTransmitPulseRadiusScale(signalLevel = 0.55)" in js
    assert "summary.rx_snr" in js
    assert "summary.rx_rssi" in js
    assert "return 0.65 + (level * 0.9);" in js
    assert "function snapshotNetworkMapPacketActivityTokens(state = latestState)" in js
    assert "function seedNetworkMapPacketActivityTokens(state = latestState)" in js
    assert "function ensureMapTransmitPulsePane()" in js
    assert "function startMapLiveTracerouteOverlay(rawTargetNodeId, payload, options = null)" in js
    assert "function startMapTracePathAnimation(nodeIds, state = latestState, options = null)" in js
    assert "function pruneExpiredMapTracePaths(nowMs = Date.now())" in js
    assert "function clearMapTracePaths()" in js
    assert "function mapTracePathNodeIds(startNodeId, hops, options = null)" in js
    assert "function mapTracePathSegmentsForNodeIds(nodeIds, state = latestState)" in js
    assert "function cacheNetworkMapActivityPositions(nodes = [], estimatedPositions = new Map())" in js
    assert 'kind: String(estimate && estimate.estimateSource || "").trim() === "rssi_trilateration"' in js
    assert '? "trilaterated"' in js
    assert "cacheNetworkMapActivityPositions(nodes, estimatedPositions);" in js
    assert "function mapNodeActivityPosition(nodeId, state = latestState)" in js
    assert "function cacheMapEstimatedCorridorActivityPaths(estimateLines = [])" in js
    assert "function mapPacketActivityCorridorPath(fromNodeId, toNodeId)" in js
    assert "function mapActivityPathSlice(path, startProgress, endProgress)" in js
    assert "function startMapNodeTransmitRipple(nodeId, state = latestState, signalLevel = 0.55)" in js
    assert "function pruneExpiredMapNodeTransmitPulseRings(nowMs = Date.now())" in js
    assert "function startMapPacketDirectionAnimation(fromNodeId, toNodeId, state = latestState, signalLevel = 0.55)" in js
    assert "function pruneExpiredMapNodeActivityDirections(nowMs = Date.now())" in js
    assert "const animatedPath = mapActivityPathSlice(record.path, tailProgress, progress);" in js
    assert "line.setLatLngs(animatedPath.length >= 2 ? animatedPath : [headPoint, headPoint]);" in js
    assert "head.setLatLng(headPoint);" in js
    assert "function applyMapNodeTraceProgressStyle(baseStyle, traceProgress)" in js
    assert "function applyMapNodeTraceResultStyle(baseStyle, resultFlash)" in js
    assert 'function resolveMapNodeMarkerStyle(nodeId, isSelected, markerKind = "actual", markerConfidence = 0.45, state = latestState)' in js
    assert 'const isLocal = !!(localNodeId && normalizeNodeId(nodeId || "") === localNodeId);' in js
    assert "const traceProgress = mapNodeTraceProgressState(nodeId);" in js
    assert "const resultFlash = mapNodeTraceResultFlashState(nodeId);" in js
    assert "return applyMapNodeTraceResultStyle(progressStyle, resultFlash);" in js
    assert "function scheduleMapNodeActivityFlashUpdate()" in js
    assert "const activeTraceProgress = isNetworkMapTraceProgressActive();" in js
    assert "const activeTraceResultCount = pruneExpiredMapTraceResultFlashes();" in js
    assert "mapTraceProgressTimer = window.setTimeout(scheduleMapNodeActivityFlashUpdate, 260);" in js
    assert "function syncNetworkMapPacketActivity(state = latestState)" in js
    assert "const recentChat = Array.isArray(traffic.recent_chat) ? traffic.recent_chat : [];" in js
    assert "!!mapLiveActivityEnabled" in js
    assert "const activePulseCount = pruneExpiredMapNodeTransmitPulseRings();" in js
    assert "const activeDirectionCount = pruneExpiredMapNodeActivityDirections();" in js
    assert "const activeTraceCount = pruneExpiredMapTracePaths();" in js
    assert "activeFlashCount > 0 || activePulseCount > 0 || activeDirectionCount > 0 || activeTraceCount > 0" in js
    assert "mapNodeActivityFlashById.set(nodeId, {" in js
    assert "mapTracePathRecords.add({" in js
    assert "while (mapTracePathRecords.size > mapTracePathMaxRecords)" in js
    assert "dashArray = kind === \"return\" ? \"4 7\" : \"9 6\";" in js
    assert "startMapTracePathAnimation(towardsPath, safeState, {" in js
    assert "startMapTracePathAnimation(backPath, safeState, {" in js
    assert "startMapLiveTracerouteOverlay(targetId, safePayload, {" in js
    assert "const endpoints = mapPacketActivityEndpointIds(packetEntry);" in js
    assert "const signalLevel = mapPacketActivitySignalLevel(packetEntry);" in js
    assert "nodesToRipple.set(" in js
    assert "Math.max(Number(prevSignalLevel), signalLevel)" in js
    assert "directionsToAnimate.push({ fromId: endpoints.fromId, toId: endpoints.toId, signalLevel });" in js
    assert "&& mapPacketActivityShouldAnimateDirection(packetEntry)" in js
    assert "if (!isMapLocalEchoActivityEntry(chatEntry, localNodeId)) continue;" in js
    assert "tokens.add(mapLocalEchoActivityToken(chatEntry, localNodeId));" in js
    assert "const token = mapLocalEchoActivityToken(chatEntry, localNodeId);" in js
    assert "const endpoints = mapLocalEchoActivityEndpointIds(chatEntry, localNodeId);" in js
    assert "nodesToFlash.add(endpoints.fromId);" in js
    assert "nodesToFlash.add(endpoints.toId);" in js
    assert "fromId: endpoints.fromId," in js
    assert "toId: endpoints.toId," in js
    assert "cacheMapEstimatedCorridorActivityPaths(estimateLinesToRender);" in js
    assert "const corridorPath = mapPacketActivityCorridorPath(fromId, toId);" in js
    assert "path: animationPath," in js
    assert "startMapNodeTransmitRipple(nodeId, safeState, signalLevel);" in js
    assert "startMapPacketDirectionAnimation(direction.fromId, direction.toId, safeState, direction.signalLevel);" in js
    assert "pane: mapTransmitPulsePaneName," in js
    assert "const radiusScale = mapTransmitPulseRadiusScale(signalLevel);" in js
    assert "const endRadius = (22 + (idx * 7)) * radiusScale;" in js
    assert "layer.setRadius(easedRadius);" in js
    assert "scheduleMapNodeActivityFlashUpdate();" in js
    assert "mapLiveActivityEnabled\n          && typeof isNetworkMapActivityFlashVisible === \"function\"" in js
    assert "&& !isNetworkMapActivityFlashVisible()" in js
    assert "&& isNetworkMapActivityFlashVisible()" in js
    assert js.index("renderMap(state.nodes || [], (state.traffic || {}).edges || [], cachedHistory);") < js.index(
        "&& isNetworkMapActivityFlashVisible()"
    )
    assert "syncNetworkMapPacketActivity(state);" in js


def test_dashboard_map_emoji_marker_ring_uses_node_marker_color() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    css = build_dashboard_css(theme_css="")

    assert (
        "const markerStyleForRing = resolveMapNodeMarkerStyle(nodeId, isSelected, markerKind, markerConfidence, state);"
        in js
    )
    assert "const ringColor = traceResultFlash" in js
    assert ': String(markerStyleForRing && markerStyleForRing.color ? markerStyleForRing.color : "#86a9ff");' in js
    assert "const traceProgressPct = traceProgress ? Math.max(1, Math.min(99, Number(traceProgress.progressPct) || 1)) : 0;" in js
    assert 'traceProgress ? "is-trace-running" : ""' in js
    assert 'traceResultFlash ? "is-trace-result" : ""' in js
    assert 'traceResultFlash && traceResultFlash.ok === true ? "is-trace-success" : ""' in js
    assert 'traceResultFlash && traceResultFlash.ok !== true ? "is-trace-failed" : ""' in js
    assert "--map-node-ring-color:${escAttr(ringColor)}" in js
    assert "--map-node-ring-width:${ringWidth.toFixed(1)}px" in js
    assert "--map-node-trace-angle:${traceAngleDeg}" in js
    assert "--map-node-trace-result:${traceResultStrength.toFixed(3)}" in js
    assert "--map-node-trace-color:${escAttr(traceResultFlash ? traceResultColor : \"#7dd3fc\")}" in js
    assert "border: var(--map-node-ring-width, 2px) solid var(--map-node-ring-color, #86a9ff);" in css
    assert "background: conic-gradient(" in css
    assert ".map-node-emoji-marker.is-trace-running::before {" in css
    assert ".map-node-emoji-marker.is-trace-result::before {" in css
    assert ".map-node-emoji-marker.is-trace-success::before {" in css
    assert ".map-node-emoji-marker.is-trace-failed::before {" in css
    assert "border-color: var(--map-node-ring-color, #adc0ff);" in css
    assert "border-color: var(--map-node-ring-color, #9db5ff);" in css


def test_dashboard_node_emoji_markers_can_be_disabled() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'const nodeEmojiMarkersStorageKey = "meshDashboardNodeEmojiMarkersEnabledV1";' in js
    assert "let nodeEmojiMarkersEnabled = true;" in js
    assert "function nodeEmojiMarkersAreEnabled() {" in js
    assert "function loadNodeEmojiMarkersPreference() {" in js
    assert "function persistNodeEmojiMarkersPreference() {" in js
    assert 'runBootStep("loadNodeEmojiMarkersPreference", () => loadNodeEmojiMarkersPreference());' in js
    assert 'data-map-link-legend-toggle="emoji-markers"' in js
    assert "nodeEmojiMarkersEnabled = !!emojiMarkersToggle.checked;" in js
    assert 'if (typeof invalidateNetworkGraphRenderCache === "function") {' in js
    assert "refreshNetworkMapAfterLegendControlChange({ bypassNodeFade: true });" in js
    assert 'if (typeof nodeEmojiMarkersAreEnabled === "function" && !nodeEmojiMarkersAreEnabled()) return "";' in js
    assert 'if (typeof nodeEmojiMarkersAreEnabled === "function" && !nodeEmojiMarkersAreEnabled()) return false;' in js


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
