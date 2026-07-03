import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_js import build_dashboard_js


def test_dashboard_js_registers_console_node_lookup_commands() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'name: "node"' in js
    assert 'usage: "node <id|name>"' in js
    assert 'name: "lookup"' in js
    assert 'usage: "lookup <id|name>"' in js
    assert 'resolveConsoleNodeLookupMatches' in js


def test_dashboard_js_registers_console_nodes_aliases() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'name: "nodes"' in js
    assert 'usage: "nodes [-v|-vv|-vvv|-vvvv] [pattern]' in js
    assert 'name: "--nodes"' in js
    assert 'usage: "--nodes [-v|-vv|-vvv|-vvvv] [pattern]' in js
    assert 'name: "list"' not in js
    assert "runConsoleNodeListCommand" in js


def test_dashboard_js_registers_console_traceroute_commands() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'name: "traceroute"' in js
    assert 'usage: "traceroute <id|name|num>' in js
    assert 'name: "--traceroute"' in js
    assert 'usage: "--traceroute <id|name|num>' in js
    assert "resolveConsoleNodeTarget" in js
    assert "postNetworkToolCommand" in js


def test_dashboard_js_registers_console_ping_and_position_commands() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'name: "ping"' in js
    assert 'usage: "ping <id|name|num>' in js
    assert 'name: "--ping"' in js
    assert 'name: "send-node-info"' in js
    assert 'usage: "send-node-info [--ch-index=<n>] [--hop-limit=<n>]"' in js
    assert 'name: "--send-node-info"' in js
    assert 'name: "send-alert"' in js
    assert 'usage: "send-alert <id|name|num> <text>' in js
    assert 'name: "--send-alert"' in js
    assert 'name: "sendtext"' in js
    assert 'usage: "sendtext <id|name|num> <text>' in js
    assert 'name: "--sendtext"' in js
    assert 'name: "request-position"' in js
    assert 'usage: "request-position <id|name|num>' in js
    assert 'name: "--request-position"' in js
    assert 'name: "where"' in js
    assert 'name: "request-telemetry"' in js
    assert 'name: "--request-telemetry"' in js
    assert 'name: "telemetry"' in js
    assert 'name: "request-config"' in js
    assert 'name: "--request-config"' in js
    assert 'name: "request-channels"' in js
    assert 'name: "--request-channels"' in js
    assert 'name: "device-metadata"' in js
    assert 'name: "--device-metadata"' in js
    assert 'name: "reset-nodedb"' in js
    assert 'name: "--reset-nodedb"' in js
    assert 'name: "factory-reset"' in js
    assert 'name: "--factory-reset"' in js
    assert 'name: "factory-reset-device"' in js
    assert 'name: "--factory-reset-device"' in js
    assert 'name: "reboot"' in js
    assert 'name: "--reboot"' in js
    assert 'name: "shutdown"' in js
    assert 'name: "--shutdown"' in js
    assert 'name: "set-time"' in js
    assert 'name: "--set-time"' in js
    assert "runConsolePingCommand" in js
    assert "runConsoleSendNodeInfoCommand" in js
    assert "runConsoleSendAlertCommand" in js
    assert "runConsoleSendTextCommand" in js
    assert "runConsoleRequestPositionCommand" in js
    assert "runConsoleRequestTelemetryCommand" in js
    assert "runConsoleRequestConfigCommand" in js
    assert "runConsoleRequestChannelsCommand" in js
    assert "runConsoleDeviceMetadataCommand" in js
    assert "runConsoleResetNodeDbCommand" in js
    assert "runConsoleFactoryResetCommand" in js
    assert "runConsoleFactoryResetDeviceCommand" in js
    assert "runConsoleRebootCommand" in js
    assert "runConsoleShutdownCommand" in js
    assert "runConsoleSetTimeCommand" in js
    assert "runConsoleNetworkNodeCommand" in js


def test_dashboard_js_includes_console_tab_autocomplete() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "let consoleAutocompleteState = null;" in js
    assert "function parseConsoleTokenRanges(line)" in js
    assert "function normalizeConsoleAutocompleteCandidate(candidate)" in js
    assert "function resolveConsoleSelectedNodeAutocompleteCandidate(state = latestState)" in js
    assert "function handleConsoleTabAutocomplete(inputEl, state = latestState, reverse = false)" in js
    assert "function resolveConsoleAutocompleteGhostSuffix(inputEl, state = latestState)" in js
    assert "function resolveConsoleAutocompleteGhostRemainder(rawToken, candidate)" in js
    assert "function acceptConsoleAutocompleteGhost(inputEl, state = latestState)" in js
    assert "let consoleAutocompleteMenuSelectedIndex = 0;" in js
    assert "function consoleAutocompleteSuppressedByRunningCommand()" in js
    assert "if (consoleAutocompleteSuppressedByRunningCommand())" in js
    assert "function renderConsoleAutocompleteMenu(inputEl = null, state = latestState)" in js
    assert "function moveConsoleAutocompleteMenuSelection(delta)" in js
    assert "function applyConsoleAutocompleteMenuSelection(inputEl = null, state = latestState)" in js
    enter_block_start = js.rindex('if (ev.key === "Enter" && !ev.shiftKey && !ev.ctrlKey && !ev.metaKey && !ev.altKey)')
    enter_block_end = js.index('if (ev.key === "ArrowUp" && !ev.shiftKey && !ev.ctrlKey && !ev.metaKey && !ev.altKey)', enter_block_start)
    enter_block = js[enter_block_start:enter_block_end]
    assert "runConsoleCommandLine(cmdLine)" in enter_block
    assert "applyConsoleAutocompleteMenuSelection" not in enter_block
    assert "Tab accepts, Enter runs" in js
    assert "function buildConsoleNodeAutocompleteCandidate(row)" in js
    assert "function consoleNodeAutocompleteEmoji(row)" in js
    assert "function collectConsoleNodeTagLookupVariants(row)" in js
    assert "function buildConsoleNodeRowsFromState(state = latestState)" in js
    assert "function refreshConsoleNodeRowsCache(state = latestState)" in js
    assert "function resolveConsoleCachedNodeRow(rawNodeId, state = latestState)" in js
    assert 'kind: "node"' in js
    assert "nodeName," in js
    assert "nodeEmoji: consoleNodeAutocompleteEmoji(safeRow)" in js
    assert 'typeof nodeTagEntryForNode === "function"' in js
    assert "push(nodeTagLabelForNode(nodeId));" in js
    assert "...collectConsoleNodeTagLookupVariants(row)," in js
    assert "if (!prefix) {" in js
    assert "if (clean.startsWith(\"!\"))" in js
    assert "const matchId = (value) =>" in js
    assert "const matchName = (value) =>" in js
    assert "const includeHidden = prefix.startsWith(\"--\");" in js
    assert "const names = Array.from(consoleCommandRegistry.values())" in js
    assert ".filter((entry) => includeHidden || !entry.hiddenFromHelp)" in js
    assert ".filter((name) => name.startsWith(prefix))" in js
    assert 'const text = leadingSlash ? `/${name}` : name;' in js
    assert "resolveConsoleAutocompleteCandidates(context, state)" in js
    assert 'if (ev.key === "Tab" && !ev.ctrlKey && !ev.metaKey && !ev.altKey)' in js
    assert 'if (ev.key === "ArrowRight" && !ev.shiftKey && !ev.ctrlKey && !ev.metaKey && !ev.altKey)' in js
    assert 'if (ev.key === "ArrowDown" && !ev.shiftKey && !ev.ctrlKey && !ev.metaKey && !ev.altKey && isConsoleAutocompleteMenuOpen())' in js
    assert 'if (ev.key === "Enter" && !ev.shiftKey && !ev.ctrlKey && !ev.metaKey && !ev.altKey)' in js
    assert 'className = `console-autocomplete-item console-autocomplete-item-${kind}${kind === "node" ? " is-node" : ""}${index === selectedIndex ? " is-selected" : ""}`' in js
    assert 'className = "console-autocomplete-node-name"' in js
    assert 'className = "console-autocomplete-node-id"' in js
    assert 'class="console-completion-ghost"' in js


def test_dashboard_js_hides_cli_style_aliases_from_default_command_lists() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'name: "--ping"' in js
    assert 'name: "--request-position"' in js
    assert 'hiddenFromHelp: name.startsWith("--") || commandDef.hiddenFromHelp === true' in js
    assert ".filter((def) => def && !def.hiddenFromHelp)" in js
    assert "hiddenFromHelp: entry.hiddenFromHelp === true" in js
    assert "const includeHidden = cleanQuery.startsWith(\"--\");" in js
    assert "const visibleSource = includeHidden" in js
    assert "source.filter((entry) => entry && !entry.hiddenFromHelp)" in js


def test_dashboard_js_supports_self_target_macro_for_console_commands() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'const consoleSelfTargetMacro = "%self";' in js
    assert "function isConsoleSelfTargetMacro(rawTarget)" in js
    assert "function resolveConsoleSelfTargetId(state = latestState)" in js
    assert "normalizeNodeId(resolveLocalNodeId(state) || \"\")" in js
    assert "function buildConsoleSelfMacroAutocompleteCandidate(state = latestState)" in js
    assert "insertText: consoleSelfTargetMacro" in js
    assert "if (clean.startsWith(\"%\"))" in js
    assert "consoleSelfTargetMacro.startsWith(clean)" in js
    assert "if (isConsoleSelfTargetMacro(rawTarget))" in js
    assert "return { ok: true, destination: selfDestination };" in js
    assert "%self is unavailable: local radio ID is not known yet." in js
    assert "target macros: %self resolves to the radio ID connected to the server" in js
