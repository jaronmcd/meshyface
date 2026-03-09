from meshdash.html_css import build_dashboard_css
from meshdash.html_js import build_dashboard_js


def test_build_dashboard_css_includes_theme_tokens_and_core_selectors():
    css = build_dashboard_css(theme_css=":root { --test-color: #123456; }")
    assert ":root { --test-color: #123456; }" in css
    assert ".topbar" in css
    assert ".workspace-shell" in css
    assert ".console-select" in css
    assert ".console-terminal-screen" in css
    assert ".console-prompt-label" in css
    assert "#history-chat-table td.history-node-clickable" in css
    assert "#history-chat-table tbody tr.history-node-selectable.selected-node td" in css
    assert ".bots-setting-note" in css
    assert "* { box-sizing: border-box; }" in css
    assert "{{" not in css
    assert "}}" not in css


def test_build_dashboard_js_injects_runtime_values():
    js = build_dashboard_js(
        refresh_ms=3000,
        node_history_hours=72,
        node_history_max_points=1440,
        reset_ticker_scale_on_restart=True,
    )
    assert "const refreshMs = 3000;" in js
    assert "const nodeHistoryHours = 72;" in js
    assert "const nodeHistoryMaxPoints = 1440;" in js
    assert "const resetTickerScaleOnRestart = Number(1) === 1;" in js
    assert "setInterval(pollOnce, refreshMs);" in js
    assert "/^[0-9a-f]{8}$/i.test(hex)" in js
    assert "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" in js
    assert "const chatEmojiQueryKeywordAliases = {" in js
    assert "function tokenizeChatEmojiSearchAliasParts(queryParts)" in js
    assert "function rankChatEmojiSearchMatchesAnyPart(rawQuery, queryParts, allowFuzzy = false)" in js
    assert "function focusChatEmojiSearchInput()" in js
    assert "if ((ev.ctrlKey || ev.metaKey) && !ev.altKey && !ev.shiftKey && key === \"e\") {" in js
    assert "Top matches" in js
    assert "const consoleSessionStorageKey = \"meshDashboardConsoleSessionV1\";" in js
    assert "const storage = window.sessionStorage;" in js
    assert "storage.getItem(consoleSessionStorageKey)" in js
    assert "storage.setItem(consoleSessionStorageKey" in js
    assert "loadConsoleSessionState();" in js
    assert "function isStandaloneConsoleSessionExpiredMessage(value)" in js
    assert "Console mode restored. Type \\\"zork\\\" to start again." in js
    assert "const consoleFontSizeStorageKey = \"meshDashboardConsoleFontSizeV1\";" in js
    assert "loadConsoleFontSizePreference();" in js
    assert "window.localStorage.setItem(consoleFontSizeStorageKey" in js
    assert "const prompt = document.getElementById(\"console-prompt-label\");" in js
    assert "const promptLabel = runningName" in js
    assert "const terminalScreen = document.getElementById(\"console-terminal-screen\");" in js
    assert "async function copyConsoleSelectionToClipboard()" in js
    assert "async function copyChatSelectionToClipboard()" in js
    assert "navigator.clipboard.writeText(text);" in js
    assert "selection.removeAllRanges();" in js
    assert "pre.addEventListener(\"mouseup\", () => {" in js
    assert "void copyChatSelectionToClipboard();" in js
    assert "function bindHistoryChatRowClicks()" in js
    assert "\"from-node-id\": fromNodeId" in js
    assert "className: isSelectableNodeId(fromNodeId) ? \"history-node-clickable\" : \"\"" in js
    assert "selectNodeFromDirectionalRow(" in js
    assert "game_public_start_enabled: false" in js
    assert "raw.game_public_start_enabled ?? raw.gamePublicStartEnabled" in js
    assert "const publicStartInput = document.getElementById(\"bots-game-public-start-enabled\");" in js
    assert "game_public_start_enabled: !!publicStartInput.checked" in js
    assert "const receivedAtMs = Date.now();" in js
    assert "receivedAtMs,\n            true" in js
    assert "function setChannelsStatusText(message)" in js
    assert "const channelsFetchBtn = document.getElementById(\"channels-fetch-settings-btn\");" in js
    assert "const channelsExperimentalToggle = document.getElementById(\"settings-channels-experimental-toggle\");" in js
    assert "allow_experimental: !!channelsExperimentalEnabled" in js
    assert "fallbackCount: 8" in js
    assert 'idx === 0 ? "PRIMARY" : "DISABLED"' in js
    assert "{{" not in js
    assert "}}" not in js
