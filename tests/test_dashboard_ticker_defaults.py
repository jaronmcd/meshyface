import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_css import build_dashboard_css
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


def test_dashboard_js_defaults_live_update_ticker_to_disabled() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "update_ticker_enabled: false," in js
    assert "raw.update_ticker_enabled" in js
    assert "function topbarUpdateTickerEnabled() {" in js
    assert "prefs.update_ticker_enabled = !!liveUpdateToggle.checked;" in js
    assert "topbarUpdateTickerHasRenderableContent" not in js
    assert "if (topbarUpdateTickerEnabled()) {" in js
    assert "setTopbarUpdateTickerVisibility(tickerEl, topbarUpdateTickerEnabled());" in js
    assert "if (!topbarUpdateTickerEnabled()) {" in js
    assert "Ticker preferences saved locally." not in js
    assert "Live update ticker shown." not in js
    assert "Live update ticker hidden." not in js
    assert "Ticker preferences reset to defaults." not in js


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


def test_render_html_widens_ticker_cards_for_phone_swipe_scrolling() -> None:
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

    assert "@media (max-width: 760px) {" in html
    assert "grid-auto-columns: minmax(168px, 82vw);" in html
    assert "scroll-snap-type: x proximity;" in html
    assert ".topbar .summary-ticker-item {" in html
    assert "scroll-snap-align: start;" in html


def test_render_html_exposes_live_update_ticker_toggle_in_settings() -> None:
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

    assert 'id="settings-ticker-live-update-enabled"' in html
    assert "Show live update ticker" in html
    assert "sideways scrolling live-update bar" in html


def test_dashboard_js_renders_local_identity_in_target_ticker() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'targetLabel.textContent = hasLocalIdentity ? "Node" : "Target";' in js
    assert 'targetMetric.classList.add("target-node-value", "node-ticker-value");' in js
    assert 'nameRow.className = "target-node-name";' in js
    assert 'badgeMark.className = "target-node-mark";' in js
    assert 'nameText.className = "target-node-name-text";' in js
    assert 'idRow.className = "target-node-id";' in js
    assert 'targetMetric.textContent = targetDisplay;' in js


def test_render_html_styles_local_identity_target_ticker() -> None:
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

    assert ".topbar .summary-ticker-item-target .value.target-node-value {" in html
    assert ".target-node-name {" in html
    assert ".target-node-mark {" in html
    assert ".target-node-name-text {" in html
    assert ".target-node-id {" in html


def test_target_ticker_id_uses_muted_light_mode_text() -> None:
    css = build_dashboard_css(theme_css="")
    target_id_section = css.split(
        ".topbar .summary-ticker-item-target .value.target-node-value .target-node-id {",
        1,
    )[1].split("}", 1)[0]

    assert "color-mix(in srgb, var(--muted) 84%, var(--ink) 16%)" in target_id_section
    assert "rgba(230, 248, 237, 0.84)" not in target_id_section
