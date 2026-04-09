import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_js import build_dashboard_js
from meshdash.html_template import render_html


def test_dashboard_js_uses_curated_default_ticker_layout() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert re.search(
        r'const tickerDefaultOrder = \[\s*"target",\s*"known_nodes",\s*"online_nodes",\s*"packets_per_min",\s*"channel_util",\s*"node",\s*"battery",',
        js,
    )
    assert re.search(
        r'for \(const id of \[\s*"target",\s*"known_nodes",\s*"online_nodes",\s*"packets_per_min",\s*"channel_util",\s*"node",\s*\]\)',
        js,
    )
    assert 'enabled: { ...tickerDefaultEnabled },' in js
    assert "prefs.enabled[id] = !!defaults.enabled[id];" in js


def test_dashboard_js_defaults_unique_node_colors_to_off() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "let settingsUniqueNodeColorsEnabled = false;" in js
    assert re.search(
        r"settingsUniqueNodeColorsEnabled = parseBoolToken\(\s*window\.localStorage\.getItem\(settingsUniqueNodeColorsStorageKey\),\s*false\s*\);",
        js,
    )


def test_dashboard_js_uses_semantic_ticker_state_profiles() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'function resolveMetricTickerState(latest, delta, trend, config = {}) {' in js
    assert 'item.classList.add(`metric-state-${resolvedState}`);' in js
    assert 'stateProfile: "count_delta"' in js
    assert 'stateProfile: "traffic_delta"' in js
    assert 'stateProfile: "channel_util"' in js
    assert 'stateProfile: "battery_pct"' in js
    assert 'stateProfile: Number.isFinite(nodeRssi) ? "signal_rssi" : "signal_snr"' in js
    assert 'stateProfile: "wifi_rssi"' in js


def test_dashboard_js_normalizes_full_profile_to_core_ui() -> None:
    core_js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
        ui_profile="core-ui",
    )
    full_js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
        ui_profile="full",
    )

    assert full_js == core_js


def test_dashboard_js_normalizes_unknown_profile_to_core_ui() -> None:
    core_js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
        ui_profile="core-ui",
    )
    unknown_js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
        ui_profile="labs-preview",
    )

    assert unknown_js == core_js


def test_render_html_uses_single_row_compact_ticker_strip() -> None:
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

    assert re.search(
        r"\.topbar \.sub \.summary-ticker-row \{\s*display: grid;\s*grid-auto-flow: column;\s*grid-auto-columns: minmax\(112px, 1fr\);\s*gap: 4px;",
        html,
    )
    assert re.search(
        r"\.topbar\.ticker-expanded \.sub \.summary-ticker-row \{\s*grid-auto-flow: row;\s*grid-auto-columns: auto;\s*grid-template-columns: repeat\(auto-fit, minmax\(208px, 1fr\)\);",
        html,
    )
