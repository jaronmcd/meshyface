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
    assert 'id="network-graph-svg"' in html


def test_dashboard_js_supports_network_graph_subview() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'return clean === "overview" || clean === "graph" || clean === "sensors" ? clean : "map";' in js
    assert 'function renderNetworkGraphView(state = latestState)' in js
    assert 'activeNetworkSubview === "graph"' in js


def test_network_layout_uses_single_row_map_track() -> None:
    css = build_dashboard_css(theme_css="")

    assert ".layout.view-network {" in css
    assert "grid-template-rows: minmax(0, 1fr);" in css
    assert ".layout.view-network .map {" in css
    assert "grid-row: 1;" in css
