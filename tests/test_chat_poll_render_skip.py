import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_js import build_dashboard_js


def test_dashboard_js_skips_redundant_chat_workspace_poll_renders() -> None:
    js = build_dashboard_js(
        refresh_ms=3000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'let chatPollStructuralSignature = "";' in js
    assert "const chatPollStructuralRefreshMs = 15000;" in js
    assert "function buildChatPollStructuralSignature(state = latestState) {" in js
    assert 'runPollStep("renderChat.workspace", () => renderChat(state, { allowPollSkip: true }));' in js
    assert "renderChat(latestState, { allowPollSkip: true });" in js
    assert '"/api/state?lite=1&profile=chat"' in js
    assert '"/api/state?lite=1&profile=network"' in js
    assert 'function statePollProfile() {' in js
    assert 'if (clean === "links") return "graph";' in js
    assert "&& pollStructuralSignature === chatPollStructuralSignature" in js
    assert "&& pollStructuralAgeMs < chatPollStructuralRefreshMs" in js
    assert 'markRenderChatPhase("poll-skip");' in js
    assert 'syncChatNodeDetailsDrawer(state, {' in js
    assert "!chatRenderedThisPoll304" in js
    assert "!chatRenderedThisPoll" in js
    assert 'const needsChatSection = !renderChatInDrawer || activeDrawerTab === "chat";' in js
    assert 'const linksSection = needsLinksSection && linkStats' in js
    assert "renderChatChangeSummary(nowUnix);" in js
    assert "function syncNetworkGraphSceneSelection(svg, options = {}) {" in js
    assert "function buildNetworkGraphSceneStructureSignature(scene) {" in js
    assert "function syncNetworkGraphSceneData(svg, scene) {" in js
    assert 'const selectedId = normalizeNodeId(selectedNodeId || "");' in js
    assert 'if (selectedId && nodeMap.has(selectedId)) return selectedId;' in js
    assert "const nodeSelectionUiState = {" in js
    assert "const nodeSelectionPerfState = {" in js
    assert "nodeSelectionPerfStore();" in js
    assert '"saved-node-details-shell"' in js
    assert '"saved-node-sections"' in js
    assert "function beginNodeSelectionPerf(nodeId, meta = {}) {" in js
    assert "function markNodeSelectionPerf(token, phase, startedAtMs, extra = null) {" in js
    assert "function finishNodeSelectionPerf(token, status = \"complete\", extra = null) {" in js
    assert "function scheduleNodeSelectionUiRefresh(options = null) {" in js
    assert "function flushNodeSelectionUiRefresh() {" in js
    assert 'const networkMapVisible = activeLayoutView === "network" && activeNetworkSubviewName === "map";' in js
    assert 'if (latestState && (activeLayoutView !== "network" || networkMapVisible)) {' in js
    assert 'const shouldPrefetchNodeHistory = !!(' in js
    assert 'activeTab === "history"' in js
    assert 'if (activeLayoutView === "saved" || networkMapVisible) {' in js
    assert "function setDrawerElementTextIfChanged(element, nextText) {" in js
    assert "function setDrawerElementHtmlIfChanged(element, nextHtml, cacheKey = \"default\") {" in js
    assert "function syncDrawerTabButtonState(button, isActive) {" in js
    assert "function syncDrawerPanelHiddenState(panel, isActive) {" in js
    assert 'const portsData = (traffic.port_counts || []).slice(0, 30);' in js
    assert 'const linksData = (traffic.edges || []).slice(0, 60);' in js
    assert 'if (linksHash !== trafficLinksTableLastHash) {' in js
    assert 'if (portsHash !== trafficPortsTableLastHash) {' in js
    assert "const canPatchSelectionOnly = !!(" in js
    assert "const canSkipSceneRender = !!(" in js
    assert "const canPatchSceneDataOnly = !!(" in js
    assert "forceCenteredFitOnce: false," in js
    assert "skipSceneAnimationOnce: false," in js
    assert "const shouldForceCenteredFit = !!networkGraphViewState.forceCenteredFitOnce;" in js
    assert "const shouldSkipSceneAnimation = !!networkGraphViewState.skipSceneAnimationOnce;" in js
    assert "networkGraphViewState.skipSceneAnimationOnce = true;" in js
    assert "syncNetworkGraphSceneSelection(svg, { rootId, selectedId });" in js
    assert 'data-network-graph-edge-key="${escAttr(buildNetworkGraphEdgeDomKey(edge))}"' in js
    assert "syncNetworkGraphSceneData(svg, scene);" in js
    assert "highlightNodeSelection(previousSelectedId, normalized);" in js
    assert "scheduleNodeSelectionUiRefresh({ shouldFocus: focusSelection, perfToken });" in js
    assert 'markNodeSelectionPerf(perfToken, "selection.graph_render", perfStartMs' in js
    assert 'markNodeSelectionPerf(perfToken, "selection.drawer_sync", perfStartMs' in js
    assert 'markNodeSelectionPerf(perfToken, "selection.history_refresh", perfStartMs' in js
    assert "const stableNetworkSubviewName = (typeof normalizeNetworkSubview === \"function\")" in js
    assert "window.setTimeout(() => {" in js
    assert "hash = hashMixStr(hash, normalizeNodeId(selectedNodeId || \"\"));" in js


def test_dashboard_js_limits_history_only_roster_seeding_to_direct_chat() -> None:
    js = build_dashboard_js(
        refresh_ms=3000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'if (activeChatChannel === "direct" && historyCapsById instanceof Map) {' in js
    assert 'if (activeChatChannel === "direct" && historyCapsById && typeof historyCapsById.keys === "function") {' in js
