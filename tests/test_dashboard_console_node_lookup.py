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
    assert 'return selectedCandidate ? [selectedCandidate] : [];' in js
    assert 'return String(normalizedCandidate.displayText || normalizedCandidate.insertText || "");' in js
    assert "resolveConsoleAutocompleteCandidates(context, state)" in js
    assert 'if (ev.key === "Tab" && !ev.ctrlKey && !ev.metaKey && !ev.altKey)' in js
    assert 'class="console-completion-ghost"' in js
