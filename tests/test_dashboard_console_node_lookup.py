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
    assert 'usage: "nodes [pattern]' in js
    assert 'name: "--nodes"' in js
    assert 'usage: "--nodes [pattern]' in js
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
