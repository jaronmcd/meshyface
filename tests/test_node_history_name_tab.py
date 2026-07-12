import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_css import build_dashboard_css
from meshdash.html_js import build_dashboard_js
from meshdash.html_template import render_html


def test_render_html_includes_node_history_names_and_overview_tabs() -> None:
    html = render_html(
        refresh_ms=1000,
        packet_limit=200,
        show_secrets=False,
        history_enabled=True,
        history_max_rows=200,
        history_retention_days=7,
        node_history_hours=24,
        node_history_max_points=240,
        revision_label="test",
        revision_title="test",
    )

    assert 'id="tab-btn-names"' in html
    assert 'data-tab="names"' in html
    assert 'id="tab-panel-names"' in html
    assert 'id="node-name-history-host"' in html
    assert 'id="tab-btn-overview"' in html
    assert 'data-tab="overview"' in html
    assert 'id="tab-panel-overview"' in html
    assert 'id="node-history-overview-host"' in html
    assert 'id="tab-btn-link"' in html
    assert 'data-tab="link"' in html
    assert 'id="tab-panel-link"' in html
    assert 'id="node-link-quality-chart"' in html


def test_render_html_places_overview_first_in_history_tabs() -> None:
    html = render_html(
        refresh_ms=1000,
        packet_limit=200,
        show_secrets=False,
        history_enabled=True,
        history_max_rows=200,
        history_retention_days=7,
        node_history_hours=24,
        node_history_max_points=240,
        revision_label="test",
        revision_title="test",
    )

    overview_index = html.index('id="tab-btn-overview"')
    signal_index = html.index('id="tab-btn-signal"')
    link_index = html.index('id="tab-btn-link"')
    packets_index = html.index('id="tab-btn-packets"')
    online_index = html.index('id="tab-btn-online"')
    names_index = html.index('id="tab-btn-names"')

    assert overview_index < signal_index < link_index < packets_index < online_index < names_index
    assert 'class="history-tabs workspace-pillbar"' in html
    assert 'class="history-tab-btn workspace-pill-btn is-active" id="tab-btn-overview"' in html
    assert 'id="tab-btn-signal" data-tab="signal" type="button" aria-selected="false"' in html
    assert 'id="tab-btn-link" data-tab="link" type="button" aria-selected="false"' in html
    assert 'id="tab-panel-overview" class="history-panel"' in html
    assert 'id="tab-panel-signal" class="history-panel" hidden' in html


def test_dashboard_js_renders_name_history_and_overview_under_history_tab() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'let activeHistoryTab = "overview";' in js
    assert 'nextTab === "signal" || nextTab === "link" || nextTab === "online" || nextTab === "packets" || nextTab === "names" || nextTab === "overview"' in js
    assert ': "overview";' in js
    assert 'btn.classList.toggle("is-active", isActive);' in js
    assert 'btn.setAttribute("aria-selected", isActive ? "true" : "false");' in js
    assert 'const linkPanel = document.getElementById("tab-panel-link");' in js
    assert 'renderNodeLinkQualityChart(signalPoints, historyNodeId);' in js
    assert 'function resolveNodeLinkQualityMetricMeta()' in js
    assert 'target && target.key === "node-link-quality"' in js
    assert 'const namesPanel = document.getElementById("tab-panel-names");' in js
    assert 'const overviewPanel = document.getElementById("tab-panel-overview");' in js
    assert 'renderNodeNameHistoryPanel(nameHistoryEntries);' in js
    assert 'renderNodeNameHistoryPanel([], {' in js
    assert 'const nameHistoryEntries = Array.isArray(history && history.name_history)' in js
    assert 'const host = document.getElementById("node-history-overview-host");' in js
    assert 'renderNodeHistoryOverviewPanel(history, {' in js
    assert 'savedNodeHistoryOverviewSectionHtml(history, {' in js
    assert 'const historySection = nodeDetailsSectionHtml("History",' not in js


def test_render_html_hides_history_caption_inside_drawer_history_view() -> None:
    html = render_html(
        refresh_ms=1000,
        packet_limit=200,
        show_secrets=False,
        history_enabled=True,
        history_max_rows=200,
        history_retention_days=7,
        node_history_hours=24,
        node_history_max_points=240,
        revision_label="test",
        revision_title="test",
    )

    assert '.chat-node-details-history-host #node-history-caption {' in html
    assert 'display: none !important;' in html


def test_render_html_uses_palette_classes_for_node_history_legends() -> None:
    html = render_html(
        refresh_ms=1000,
        packet_limit=200,
        show_secrets=False,
        history_enabled=True,
        history_max_rows=200,
        history_retention_days=7,
        node_history_hours=24,
        node_history_max_points=240,
        revision_label="test",
        revision_title="test",
    )

    assert 'data-signal-legend-metric="avg_snr"><span class="legend-chip-label">Avg SNR (dB)</span><span class="quality-scale-label">Bad</span><span class="quality-scale-track" aria-hidden="true"></span><span class="quality-scale-label">Good</span>' in html
    assert 'data-signal-legend-metric="avg_rssi"><span class="legend-chip-label">Avg RSSI (dBm)</span><span class="quality-scale-label">Bad</span><span class="quality-scale-track" aria-hidden="true"></span><span class="quality-scale-label">Good</span>' in html
    assert 'class="legend-chip is-primary">Packets per minute (history buckets)</span>' in html
    assert 'style="color:#1f6f53;"' not in html
    assert 'style="color:#265d7b;"' not in html


def test_dashboard_css_supports_dynamic_signal_legend_quality_gradient() -> None:
    css = build_dashboard_css(theme_css="")

    assert "grid-template-columns: minmax(0, 1fr);" in css
    assert ".signal-legend .legend-chip.has-dynamic-quality-gradient .quality-scale-track {" in css
    assert ".signal-legend .legend-chip.has-dynamic-quality-gradient.has-average-marker .quality-scale-track::after {" in css
    section = css.split(".signal-legend .legend-chip.has-dynamic-quality-gradient .quality-scale-track {", 1)[1].split("}", 1)[0]
    marker_section = css.split(".signal-legend .legend-chip.has-dynamic-quality-gradient.has-average-marker .quality-scale-track::after {", 1)[1].split("}", 1)[0]

    assert "var(--signal-legend-quality-gradient, currentColor)" in section
    assert "var(--signal-legend-quality-marker-left, 50%)" in marker_section
    assert ".quality-scale-label" in css


def test_dashboard_js_colors_signal_history_by_absolute_signal_quality() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "function resolveSignalChartQualityProfile()" in js
    assert "normalizeSignalForHeat(rawValue, range.min, range.max)" in js
    assert "function signalChartQualityScale(metricKey, chartPalette)" in js
    assert "signalSnrWeak" in js
    assert "signalRssiWeak" in js
    assert "buildSignalChartQualityGradientStops(" in js
    assert "signalChartQualityColor(score, chartPalette, metricKey)" in js
    assert "signal-chart-${safeMetricId}-raw-quality-gradient" in js
    assert "signal-chart-${safeMetricId}-trend-quality-gradient" in js
    assert 'stroke="${escAttr(snrPaths.rawStroke)}"' in js
    assert 'stroke="${escAttr(rssiPaths.trendStroke)}"' in js
    assert 'stroke="${chartPalette.line}" stroke-width="2.15"' not in js
    assert 'stroke="${chartPalette.compare}" stroke-width="2.15"' not in js


def test_dashboard_js_updates_signal_legend_average_quality_colors() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "function updateSignalChartLegendQuality(rows, profile, chartPalette)" in js
    assert "function signalChartQualityLegendGradient(metricKey, chartPalette)" in js
    assert "function signalChartQualityLegendMarkerLeft(score)" in js
    assert "linear-gradient(90deg, ${scale.low}" in js
    assert "quality scale bad to good" in js
    assert '${(quality * 100).toFixed(1)}%' in js
    assert '".signal-legend .legend-chip[data-signal-legend-metric]"' in js
    assert 'chip.classList.add("has-dynamic-quality-gradient");' in js
    assert 'chip.classList.add("has-average-marker");' in js
    assert '"--signal-legend-quality-gradient"' in js
    assert 'chip.style.setProperty("--signal-legend-quality-marker-left", signalChartQualityLegendMarkerLeft(avgQuality));' in js
    assert 'updateSignalChartLegendQuality(plotRows, signalQualityProfile, chartPalette);' in js
    assert "resetSignalChartLegendQuality();" in js


def test_drawer_history_charts_expand_for_node_detail_views() -> None:
    css = build_dashboard_css(theme_css="")

    block = re.search(
        r"\.chat-node-details-history-host #signal-chart-wrap,\n    \.chat-node-details-history-host #node-link-quality-chart-wrap,\n    \.chat-node-details-history-host #node-online-chart-wrap,\n    \.chat-node-details-history-host #node-packets-chart-wrap \{[\s\S]*?\n    \}",
        css,
    )
    assert block
    section = block.group(0)
    assert "height: auto;" in section
    assert "min-height: 0;" in section
    assert "flex: 1 1 auto;" in section


def test_name_history_empty_state_uses_workspace_theme_tokens_in_dark_mode() -> None:
    css = build_dashboard_css(theme_css="")

    assert '[data-theme="dark"] .node-details-name-history-empty {' in css
    assert 'border-color: var(--workspace-shell-border-muted);' in css
    assert 'background: color-mix(in srgb, var(--workspace-shell-bg-alt) 82%, transparent);' in css
    assert 'color: var(--workspace-shell-text-soft);' in css
    block = re.search(r'\[data-theme="dark"\] \.node-details-name-history-empty \{[\s\S]*?\n    \}', css)
    assert block
    assert 'background: #121b24;' not in block.group(0)
