from collections.abc import Callable, Sequence

import pytest


POLL_RENDER_SKIP_TOKEN_GROUPS: tuple[tuple[str, Sequence[str]], ...] = (
    (
        "poll-structural-skip",
        (
            'let chatPollStructuralSignature = "";',
            "const chatPollStructuralRefreshMs = Math.max(",
            "Math.min(180000, Math.trunc(Number(refreshMs) || 3000) * 40)",
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
            'if (typeof requestDashboardLivemapRefit === "function") {',
            "requestDashboardLivemapRefit();",
            'let stateEtagProfile = "";',
            "const previousStateEtagProfile = String(stateEtagProfile || \"\");",
            "&& previousStateEtagProfile === pollProfile",
            "stateEtagProfile = pollProfile;",
            "function forceNextStatePollFresh(reason = \"manual\") {",
            "window.__meshLastForcedStatePollAtMs = Date.now();",
            'window.__meshLastForcedStatePollReason = String(reason || "manual");',
            "const staleStartupStateSuppressWindowMs = 90000;",
            "function shouldSuppressStaleStartupStateOverlay(candidate, previous, rawCandidate = null) {",
            "function stateLooksLikeStartupConnectingOverlay(state) {",
            "const candidateStartupSource = !!(",
            "requestImmediatePoll(Math.min(Math.max(refreshMs, 1000), 3000));",
            'markPollPerfPhase(pollPerfRun, "suppress-stale-startup-state"',
            'pollPerfStatus = "suppressed-stale-startup-state";',
            "function requestFreshStateAfterPageActivation(reason = \"page-activation\") {",
            'forceNextStatePollFresh("initial-load");',
            "requestFreshStateAfterPageActivation(\"visibility\");",
            "requestFreshStateAfterPageActivation(\"focus\");",
            'window.addEventListener("pageshow", (event) => {',
            'event && event.persisted ? "pageshow-persisted" : "pageshow"',
            'networkGraphActive304 && latestStatePollProfile === "network-graph"',
            'return "network-map";',
            'return "network-graph";',
            'if (activeLayoutView === "settings") {',
            'if (activeLayoutView === "console") {',
            'if (clean === "links") return "graph";',
            "&& pollStructuralSignature === chatPollStructuralSignature",
            "&& pollStructuralAgeMs < chatPollStructuralRefreshMs",
            'markRenderChatPhase("poll-skip");',
            "pollStructuralRefreshMs: Math.max(0, Math.trunc(Number(chatPollStructuralRefreshMs) || 0)),",
            '!chatRenderedThisPoll304',
            "chatMaintained: chatMaintainedThisPoll304",
            '!chatRenderedThisPoll',
            "if (entry.countsUnread === false) return false;",
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


def test_dashboard_js_suppresses_stale_startup_state_before_accepting_payload(
    poll_dashboard_js: str,
) -> None:
    json_idx = poll_dashboard_js.index("const rawState = await resp.json();")
    normalize_idx = poll_dashboard_js.index(
        "const state = applyNodeVisibilityFiltersToState(rawState);",
        json_idx,
    )
    guard_idx = poll_dashboard_js.index(
        "if (shouldSuppressStaleStartupStateOverlay(state, latestState, rawState)) {",
        normalize_idx,
    )
    accept_idx = poll_dashboard_js.index("latestRawState = rawState;", guard_idx)

    assert json_idx < normalize_idx < guard_idx < accept_idx
