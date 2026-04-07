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
    assert 'id="network-graph-back-btn"' in html
    assert 'id="network-graph-home-btn"' in html
    assert 'id="network-graph-reset-view-btn"' in html
    assert 'id="network-graph-summary"' in html
    assert 'id="network-graph-legend"' in html


def test_dashboard_js_supports_network_graph_subview() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'return clean === "overview" || clean === "graph" || clean === "sensors" ? clean : "map";' in js
    assert 'function renderNetworkGraphView(state = latestState)' in js
    assert 'activeNetworkSubview === "graph"' in js
    assert 'let networkGraphRootNodeId = "";' in js
    assert 'const networkGraphRootHistory = [];' in js
    assert 'const networkGraphViewState = {' in js
    assert 'emptyRetryTimer: null,' in js
    assert 'emptyRetryCount: 0,' in js
    assert 'pendingEntryViewportSync: false,' in js
    assert 'function bindNetworkGraphInteractions(svg)' in js
    assert 'function getNetworkGraphStageAspectRatio(svg = null)' in js
    assert 'function isNetworkGraphPointVisible(viewBox, x, y, paddingRatio = 0.08)' in js
    assert 'function cancelNetworkGraphViewAnimation()' in js
    assert 'function cancelNetworkGraphSceneAnimation()' in js
    assert 'function clearNetworkGraphEmptyRetry()' in js
    assert 'function scheduleNetworkGraphEmptyRetry()' in js
    assert 'function animateNetworkGraphViewBox(svg, rawViewBox, options = {})' in js
    assert 'function buildNetworkGraphSceneMarkup(scene)' in js
    assert 'function animateNetworkGraphScene(svg, fromLayout, toLayout, options = {})' in js
    assert 'function buildNetworkGraphNodeSignalMeta(nodeMap, recentPackets)' in js
    assert 'function setNetworkGraphRootNode(nodeId, options = {})' in js
    assert 'function navigateNetworkGraphBack()' in js
    assert 'function focusNetworkGraphNodeFromSelection(nodeId, options = {})' in js
    assert 'function recenterNetworkGraphView(svg, options = {})' in js
    assert 'Broadcast only' in js
    assert 'is-broadcast-only' in js
    assert 'pointerDownNodeId' in js
    assert 'svg.addEventListener("wheel"' in js
    assert 'cancelNetworkGraphViewAnimation();' in js
    assert 'svg.addEventListener("pointerup", finishPan);' in js


def test_network_layout_uses_single_row_map_track() -> None:
    css = build_dashboard_css(theme_css="")
    graph_panel_css = css[css.index(".network-graph-panel {"):css.index(".network-graph-card {")]
    graph_label_css = css[css.index(".network-graph-node-label {"):css.index(".network-graph-node-label.is-secondary {")]
    graph_toolbar_css = css[css.index(".network-graph-toolbar {"):css.index(".network-graph-toolbar-actions {")]
    graph_legend_css = css[css.index(".network-graph-legend {"):css.index(".network-graph-legend-item {")]

    assert ".layout.view-network {" in css
    assert "grid-template-rows: minmax(0, 1fr);" in css
    assert ".layout.view-network .map {" in css
    assert "grid-row: 1;" in css
    assert ".network-graph-stage {" in css
    assert "touch-action: none;" in css
    assert ".network-graph-stage.is-panning {" in css
    assert ".network-graph-swatch.is-broadcast-only {" in css
    assert ".network-graph-ring.is-broadcast-only {" in css
    assert ".network-graph-node.is-broadcast-only .network-graph-node-core {" in css
    assert "padding: 0;" in graph_panel_css
    assert "pointer-events: auto;" in graph_label_css
    assert "position: absolute;" in graph_toolbar_css
    assert "display: none;" in graph_legend_css
