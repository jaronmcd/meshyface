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
            "const pageActivationPollThrottleMs = Math.max(",
            "let lastPageActivationPollMs = 0;",
            "let pageHiddenAtMs = 0;",
            "function requestFreshStateAfterPageActivation(reason = \"page-activation\", options = null) {",
            "const forceFresh = opts.force === true || !latestState;",
            "if (!forceFresh && lastPageActivationPollMs > 0 && (nowMs - lastPageActivationPollMs) < pageActivationPollThrottleMs) {",
            'forceNextStatePollFresh("initial-load");',
            "requestFreshStateAfterPageActivation(\"visibility\", {",
            "requestFreshStateAfterPageActivation(\"focus\");",
            'window.addEventListener("pageshow", (event) => {',
            'event && event.persisted ? "pageshow-persisted" : "pageshow"',
            "force: !!(event && event.persisted)",
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
            'if (networkMapVisible) {',
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
            '"node-details-shell"',
            '"node-details-sections"',
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


def test_dashboard_js_keeps_non_direct_node_selection_out_of_full_chat_render(
    poll_dashboard_js: str,
) -> None:
    select_start = poll_dashboard_js.index(
        "function selectNode(nodeId, shouldFocus = true, toggleIfSelected = true) {"
    )
    clear_start = poll_dashboard_js.index("function clearNodeSelection()", select_start)
    select_block = poll_dashboard_js[select_start:clear_start]
    mark_dispatch_start = select_block.index('markNodeSelectionPerf(perfToken, "selection.dispatch"')
    chat_workspace_start = select_block.index("if (chatWorkspaceSelection) {", mark_dispatch_start)
    schedule_start = select_block.index("scheduleNodeSelectionSummaryRefresh();")
    direct_gate_start = select_block.index('if (activeChatChannel === "direct") {', chat_workspace_start)
    direct_apply_start = select_block.index("applyChatChannel(activeChatChannel, false);", direct_gate_start)
    lightweight_sync_start = select_block.index("syncChatWorkspaceNodeSelectionUi(latestState);", direct_apply_start)

    assert "function scheduleNodeSelectionSummaryRefresh() {" in poll_dashboard_js
    assert "function syncChatWorkspaceNodeSelectionUi(state = latestState) {" in poll_dashboard_js
    assert "const chatWorkspaceSelection = isChatWorkspaceLayoutView(activeLayoutView);" in select_block
    assert schedule_start < mark_dispatch_start < chat_workspace_start
    assert chat_workspace_start < direct_gate_start < direct_apply_start < lightweight_sync_start


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


def test_dashboard_js_defers_heavy_poll_renders_while_text_entry_is_active(
    poll_dashboard_js: str,
    assert_tokens_present: Callable[[str, Sequence[str]], None],
) -> None:
    assert_tokens_present(
        poll_dashboard_js,
        (
            "const dashboardTextEntryRenderIdleMs = 900;",
            "function isDashboardTextEntryTarget(target) {",
            "function bindDashboardTextEntryActivityTracking() {",
            'for (const eventName of ["focusin", "pointerdown", "beforeinput", "input", "keydown", "paste", "compositionstart", "compositionupdate", "compositionend"]) {',
            "function shouldDeferDashboardRenderForTextEntry(run, phaseName) {",
            'markPollPerfPhase(run, phaseName || "text-entry-defer"',
            "requestImmediatePoll(Math.ceil(remainingMs) + 80);",
            'shouldDeferDashboardRenderForTextEntry(pollPerfRun, "text-entry-defer-not-modified")',
            'pollPerfStatus = "text-entry-deferred-not-modified";',
            'shouldDeferDashboardRenderForTextEntry(pollPerfRun, "text-entry-defer-render")',
            'pollPerfStatus = "text-entry-deferred";',
        ),
    )

    full_defer_idx = poll_dashboard_js.index(
        'shouldDeferDashboardRenderForTextEntry(pollPerfRun, "text-entry-defer-render")'
    )
    render_chat_idx = poll_dashboard_js.index('runPollStep("renderChat.workspace"', full_defer_idx)
    render_settings_idx = poll_dashboard_js.index("renderSettings(state);", full_defer_idx)
    render_console_idx = poll_dashboard_js.index("renderConsole(state.traffic || {});", full_defer_idx)

    assert full_defer_idx < render_chat_idx
    assert full_defer_idx < render_settings_idx
    assert full_defer_idx < render_console_idx


def test_dashboard_js_debounces_node_search_dependent_renders(
    dashboard_js: str,
    assert_tokens_present: Callable[[str, Sequence[str]], None],
) -> None:
    assert_tokens_present(
        dashboard_js,
        (
            "let nodeSearchDependentsRenderTimer = null;",
            "let nodeSearchDependentsPendingState = null;",
            "function rerenderNodeSearchDependentsNow(state = latestState) {",
            "function rerenderNodeSearchDependents(state = latestState, options = null) {",
            "const delayMs = Math.max(0, Number(opts.delayMs == null ? 140 : opts.delayMs) || 0);",
            "nodeSearchDependentsPendingState = safeState;",
            "if (nodeSearchDependentsRenderTimer !== null) return;",
            "nodeSearchDependentsRenderTimer = window.setTimeout(() => {",
            "rerenderNodeSearchDependentsNow(pendingState);",
        ),
    )

    debounce_idx = dashboard_js.index("function rerenderNodeSearchDependents(state = latestState")
    bind_idx = dashboard_js.index("function bindNodeListSearchControls()", debounce_idx)
    on_input_idx = dashboard_js.index("rerenderNodeSearchDependents(latestState);", bind_idx)

    assert debounce_idx < bind_idx < on_input_idx


def test_dashboard_js_immediate_polls_respect_text_entry_deferral(
    dashboard_js: str,
    assert_tokens_present: Callable[[str, Sequence[str]], None],
) -> None:
    assert_tokens_present(
        dashboard_js,
        (
            "function requestImmediatePoll(delayMs = 0) {",
            "let waitMs = Math.max(0, Math.trunc(Number(delayMs) || 0));",
            'if (waitMs <= 0 && typeof dashboardTextEntryRenderDeferRemainingMs === "function") {',
            "const textEntryRemainingMs = dashboardTextEntryRenderDeferRemainingMs();",
            "waitMs = Math.ceil(textEntryRemainingMs) + 80;",
        ),
    )

    guard_idx = dashboard_js.index('if (waitMs <= 0 && typeof dashboardTextEntryRenderDeferRemainingMs === "function")')
    timer_idx = dashboard_js.index("chatImmediatePollTimer = window.setTimeout", guard_idx)

    assert guard_idx < timer_idx


def test_dashboard_js_network_graph_profile_switches_do_not_force_cache_busted_poll(
    dashboard_js: str,
) -> None:
    graph_control_idx = dashboard_js.index('if (normalizedView === "network" && next === "graph")')
    graph_poll_idx = dashboard_js.index("requestImmediatePoll(0);", graph_control_idx)
    graph_poll_block = dashboard_js[graph_control_idx:graph_poll_idx]
    assert 'stateEtag = "";' not in graph_poll_block
    assert "forceStateReloadOnce = true;" not in graph_poll_block

    view_switch_idx = dashboard_js.index("const networkMapSubviewActive = next === \"network\"")
    view_switch_graph_idx = dashboard_js.index("networkGraphActive && typeof requestImmediatePoll", view_switch_idx)
    view_switch_poll_idx = dashboard_js.index("requestImmediatePoll(0);", view_switch_graph_idx)
    view_switch_block = dashboard_js[view_switch_graph_idx:view_switch_poll_idx]
    assert 'stateEtag = "";' not in view_switch_block
    assert "forceStateReloadOnce = true;" not in view_switch_block


def test_dashboard_js_bounds_long_lived_client_caches(
    dashboard_js: str,
    assert_tokens_present: Callable[[str, Sequence[str]], None],
) -> None:
    assert_tokens_present(
        dashboard_js,
        (
            "const envMetricsCatalogCacheMaxEntries = 4;",
            "const envMetricsSeriesCacheMaxEntries = 8;",
            "function pruneEnvironmentMetricsCache(cache, ttlMs, maxEntriesRaw, nowMs = Date.now()) {",
            "while (cache.size > maxEntries) {",
            "setEnvironmentMetricsCacheEntry(envMetricsSeriesCache, cacheKey, payload, envMetricsSeriesCacheMaxEntries, ttlMs);",
            "const chatEmojiSearchCacheMaxEntries = 96;",
            "function setBoundedChatEmojiSearchCacheEntry(queryRaw, matches) {",
            "while (chatEmojiSearchCache.size > chatEmojiSearchCacheMaxEntries) {",
            "setBoundedChatEmojiSearchCacheEntry(query, matches);",
        ),
    )
