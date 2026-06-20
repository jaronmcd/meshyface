from collections.abc import Callable, Sequence

import pytest


POLL_RENDER_SKIP_TOKEN_GROUPS: tuple[tuple[str, Sequence[str]], ...] = (
    (
        "poll-structural-skip",
        (
            'let chatPollStructuralSignature = "";',
            "const chatPollStructuralRefreshMs = 15000;",
            "function buildChatPollStructuralSignature(state = latestState) {",
            'runPollStep("renderChat.workspace", () => renderChat(state, { allowPollSkip: true }));',
            "function refreshUnchangedChatWorkspace(state = latestState",
            "refreshUnchangedChatWorkspace(latestState, Math.floor(Date.now() / 1000));",
            "chatMaintainedThisPoll304 = true;",
            '"/api/state?lite=1&profile=chat"',
            '"/api/state?lite=1&profile=network"',
            '"/api/state?lite=1&profile=network-graph"',
            '"/api/state?lite=1&profile=network-map"',
            '"/api/state?lite=1&profile=status"',
            '"/api/state?lite=1&profile=console"',
            'function statePollProfile() {',
            'latestStatePollProfile = pollProfile;',
            'let stateEtagProfile = "";',
            "const previousStateEtagProfile = String(stateEtagProfile || \"\");",
            "&& previousStateEtagProfile === pollProfile",
            "stateEtagProfile = pollProfile;",
            'networkGraphActive304 && latestStatePollProfile === "network-graph"',
            'if (activeLayoutView === "bbs") {',
            'return "network-map";',
            'return "network-graph";',
            'if (activeLayoutView === "settings") {',
            'if (activeLayoutView === "console") {',
            'if (clean === "links") return "graph";',
            "&& pollStructuralSignature === chatPollStructuralSignature",
            "&& pollStructuralAgeMs < chatPollStructuralRefreshMs",
            'markRenderChatPhase("poll-skip");',
            '!chatRenderedThisPoll304',
            "chatMaintained: chatMaintainedThisPoll304",
            '!chatRenderedThisPoll',
            'const stableNetworkSubviewName = (typeof normalizeNetworkSubview === "function")',
            "window.setTimeout(() => {",
            'hash = hashMixStr(hash, normalizeNodeId(selectedNodeId || ""));',
        ),
    ),
    (
        "poll-perf-instrumentation",
        (
            "function pollPerfEnabled() {",
            "function startPollPerfRun() {",
            "function markPollPerfPhase(run, phaseName, extra = null) {",
            "function finishPollPerfRun(run, status, extra = null) {",
            "window.__meshPollPerfStats = store;",
            "const pollFreshnessUiThrottleMs = 12000;",
            "function maybeTickFreshnessUIForPoll(state = latestState",
            "pollFreshnessUiLastStateKey",
            'markPollPerfPhase(pollPerfRun, "fetch"',
            'markPollPerfPhase(pollPerfRun, "json");',
            'markPollPerfPhase(pollPerfRun, "state-normalize"',
            'markPollPerfPhase(pollPerfRun, "render-summary"',
            'markPollPerfPhase(pollPerfRun, "render-map"',
            'markPollPerfPhase(pollPerfRun, "render-network"',
            'markPollPerfPhase(pollPerfRun, "summary-wait"',
            'markPollPerfPhase(pollPerfRun, "render-chat-block"',
            "freshnessTicked",
            "finishPollPerfRun(pollPerfRun, pollPerfStatus, pollPerfExtra);",
        ),
    ),
    (
        "drawer-refresh-gates",
        (
            'syncChatNodeDetailsDrawer(state, {',
            'const needsChatSection = !renderChatInDrawer || activeDrawerTab === "chat";',
            'const linksSection = needsLinksSection && linkStats',
            "renderChatChangeSummary(nowUnix);",
            "networkSubviewUsesMap(activeNetworkSubviewName)",
            'if (latestState && (activeLayoutView !== "network" || networkMapVisible)) {',
            'const shouldPrefetchNodeHistory = !!(',
            'activeTab === "history"',
            'if (activeLayoutView === "saved" || networkMapVisible) {',
            "function setDrawerElementTextIfChanged(element, nextText) {",
            'function setDrawerElementHtmlIfChanged(element, nextHtml, cacheKey = "default") {',
            "function syncDrawerTabButtonState(button, isActive) {",
            "function syncDrawerPanelHiddenState(panel, isActive) {",
        ),
    ),
    (
        "selection-perf",
        (
            'const selectedId = normalizeNodeId(selectedNodeId || "");',
            'if (selectedId && selectedId !== fromId && nodeMap.has(selectedId)) {',
            "const nodeSelectionUiState = {",
            "const nodeSelectionPerfState = {",
            "nodeSelectionPerfStore();",
            '"saved-node-details-shell"',
            '"saved-node-sections"',
            "function beginNodeSelectionPerf(nodeId, meta = {}) {",
            'function markNodeSelectionPerf(token, phase, startedAtMs, extra = null) {',
            'function finishNodeSelectionPerf(token, status = "complete", extra = null) {',
            "function scheduleNodeSelectionUiRefresh(options = null) {",
            "function flushNodeSelectionUiRefresh() {",
            "highlightNodeSelection(previousSelectedId, normalized);",
            'scheduleNodeSelectionUiRefresh({ shouldFocus: focusSelection, perfToken });',
            'markNodeSelectionPerf(perfToken, "selection.graph_render", perfStartMs',
            'markNodeSelectionPerf(perfToken, "selection.drawer_sync", perfStartMs',
            'markNodeSelectionPerf(perfToken, "selection.history_refresh", perfStartMs',
        ),
    ),
    (
        "network-graph-patch-path",
        (
            "function syncNetworkGraphSceneSelection(svg, options = {}) {",
            "function buildNetworkGraphSceneStructureSignature(scene) {",
            "function syncNetworkGraphSceneData(svg, scene) {",
            'const portsData = (traffic.port_counts || []).slice(0, 30);',
            'const linksData = (traffic.edges || []).slice(0, 60);',
            'if (linksHash !== trafficLinksTableLastHash) {',
            'if (portsHash !== trafficPortsTableLastHash) {',
            "const canPatchSelectionOnly = !!(",
            "const canSkipSceneRender = !!(",
            "const canPatchSceneDataOnly = !!(",
            "forceCenteredFitOnce: false,",
            "skipSceneAnimationOnce: false,",
            "const shouldForceCenteredFit = !!networkGraphViewState.forceCenteredFitOnce;",
            "const shouldSkipSceneAnimation = !!networkGraphViewState.skipSceneAnimationOnce;",
            "networkGraphViewState.skipSceneAnimationOnce = true;",
            "syncNetworkGraphSceneSelection(svg, { rootId, selectedId });",
            'data-network-graph-edge-key="${escAttr(edgeKey)}"',
            "syncNetworkGraphSceneData(svg, scene);",
        ),
    ),
)


@pytest.fixture
def poll_dashboard_js(dashboard_js_factory: Callable[..., str]) -> str:
    return dashboard_js_factory(refresh_ms=3000)


@pytest.mark.parametrize(
    ("group_name", "tokens"),
    POLL_RENDER_SKIP_TOKEN_GROUPS,
    ids=[group_name for group_name, _ in POLL_RENDER_SKIP_TOKEN_GROUPS],
)
def test_dashboard_js_skips_redundant_chat_workspace_poll_renders(
    poll_dashboard_js: str,
    assert_tokens_present: Callable[[str, Sequence[str]], None],
    group_name: str,
    tokens: Sequence[str],
) -> None:
    del group_name
    assert_tokens_present(poll_dashboard_js, tokens)


def test_dashboard_js_limits_history_only_roster_seeding_to_direct_chat(
    poll_dashboard_js: str,
    assert_tokens_present: Callable[[str, Sequence[str]], None],
) -> None:
    assert_tokens_present(
        poll_dashboard_js,
        (
            'if (activeChatChannel === "direct" && historyCapsById instanceof Map) {',
            'if (activeChatChannel === "direct" && historyCapsById && typeof historyCapsById.keys === "function") {',
        ),
    )
