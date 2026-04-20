import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_css import build_dashboard_css
from meshdash.html_js import build_dashboard_js
from meshdash.html_sections import build_html_shell


def test_workspace_views_share_map_style_chrome_primitives() -> None:
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
    css = build_dashboard_css(theme_css="")

    assert 'id="layout-view-menu-apps-current"' in html
    assert 'id="layout-view-menu-apps-submenu"' in html
    assert 'class="topbar-view-menu-item topbar-view-menu-item-has-submenu"' in html
    assert 'class="topbar-view-submenu-item is-active"' in html
    assert 'data-app-view="bbs"' not in html
    assert 'class="settings-chrome workspace-chrome-bar"' in html
    assert 'class="settings-toolbar workspace-chrome-row"' in html
    assert 'class="settings-tabbar workspace-pillbar"' in html
    assert 'class="settings-tab-btn workspace-pill-btn is-active"' in html
    assert 'class="btn workspace-action-chip"' in html
    assert 'class="chat-card-head workspace-chrome-bar"' in html
    assert 'class="games-toolbar workspace-chrome-bar"' in html
    assert 'id="games-library-select"' in html
    assert 'class="history-tabs workspace-pillbar"' in html
    assert 'class="history-tab-btn workspace-pill-btn is-active"' in html
    assert "<h2>Files</h2>" not in html
    assert 'id="network-map-chrome" class="network-map-chrome"' in html
    assert 'class="network-map-subview-tabs"' in html
    assert 'id="network-overview-primary-controls"' in html
    assert 'id="apps-tabs-bar"' not in html

    assert ".workspace-chrome-bar {" in css
    assert "margin-bottom: 0;" in css
    assert ".workspace-pillbar {" in css
    assert ".workspace-chrome-row {" in css
    assert ".topbar-view-menu-item-context {" in css
    assert ".topbar-view-submenu {" in css
    assert ".topbar-view-submenu-item {" in css
    assert ".chat-users-head-launcher-shell .topbar-view-menu-btn {" in css
    assert "min-height: 27px;" in css
    assert ".chat-users-head-launcher-shell .topbar-view-menu-btn:hover," in css
    assert ".network-map-subview-tab,\n    .workspace-pill-btn {" in css
    assert ".workspace-action-chip {" in css
    assert ".settings-chrome {" in css
    assert ".chat-card-head.workspace-chrome-bar {" in css
    assert ".games-toolbar-picker {" in css
    assert ".settings-status.settings-status-top:empty {" in css
    assert ".apps-tabs-bar.workspace-chrome-bar {" not in css
    workspace_status_section = css.split(".workspace-chrome-status {", 1)[1].split("}", 1)[0]
    assert "position: absolute;" in workspace_status_section
    assert "clip-path: inset(50%);" in workspace_status_section
    assert "white-space: nowrap;" in workspace_status_section
    assert ".layout.view-settings .settings-toolbar.workspace-chrome-row {" in css
    assert ".layout.view-settings .settings-actions.settings-actions-top .workspace-action-chip {" in css
    assert "[data-theme=\"dark\"] .settings-chrome.workspace-chrome-bar," in css
    assert "[data-theme=\"dark\"] .network-map-subview-tab,\n    [data-theme=\"dark\"] .workspace-pill-btn {" in css


def test_apps_views_move_app_switching_into_launcher_submenu() -> None:
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
    css = build_dashboard_css(theme_css="")
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'data-submenu="apps"' in html
    assert 'id="layout-view-menu-apps-current"' in html
    assert 'id="layout-view-menu-apps-meta"' in html
    assert 'id="layout-view-menu-apps-submenu"' in html
    assert 'data-app-view="games"' in html
    assert 'data-app-view="files"' in html
    assert 'data-app-view="bbs"' not in html
    assert 'id="apps-tabs-bar"' not in html

    assert ".topbar-view-menu-item-has-submenu {" in css
    assert ".topbar-view-menu-item-branch {" in css
    assert ".topbar-view-submenu {" in css
    assert ".topbar-view-submenu[data-side=\"overlay\"] {" in css
    assert ".topbar-view-submenu-item {" in css
    assert ".topbar-view-submenu-item.is-active," in css
    assert ".apps-tabs-bar {" not in css
    assert ".apps-tab-btn {" not in css

    assert "function appsLayoutViewLabel(viewName = \"\") {" in js
    assert "function currentWorkspaceLauncherLabel(viewName = activeLayoutView) {" in js
    assert "function closeLayoutViewSubmenus() {" in js
    assert "function openLayoutViewSubmenu(name = \"\") {" in js
    assert "function toggleLayoutViewSubmenu(name = \"\") {" in js
    assert 'document.getElementById("layout-view-menu-apps-current")' in js
    assert 'document.getElementById("layout-view-menu-apps-submenu")' in js
    assert 'submenu.dataset.side = canOpenRight ? "" : "overlay";' in js
    assert 'positionFloatingPanelNearAnchor(submenu, trigger' not in js
    assert 'target.closest("#layout-view-menu .topbar-view-submenu-item")' in js
    assert 'target.closest(\'#layout-view-menu .topbar-view-menu-item[data-submenu="apps"]\')' in js
    assert 'return `Apps · ${currentAppsLauncherLabel(viewName)}`;' in js


def test_workspace_main_gap_stays_uniform_and_lets_apps_views_use_full_width() -> None:
    css = build_dashboard_css(theme_css="")

    workspace_main_section = css.split(".workspace-main {", 1)[1].split("}", 1)[0]
    apps_workspace_main_section = css.split('.workspace-shell[data-layout-view="games"] .workspace-main,', 1)[1].split("}", 1)[0]
    apps_layout_section = css.split('.workspace-shell[data-layout-view="games"] .workspace-main > .layout.view-games,', 1)[1].split("}", 1)[0]
    assert "gap: 8px;" in workspace_main_section
    assert "gap: 0;" not in workspace_main_section
    assert "grid-template-columns: minmax(0, 1fr);" in apps_workspace_main_section
    assert "grid-template-rows: minmax(0, 1fr);" in apps_workspace_main_section
    assert '.workspace-shell[data-layout-view="games"] .workspace-main::before,' not in css
    assert "grid-column: 1;" in apps_layout_section


def test_network_view_keeps_map_frame_and_removes_body_shell() -> None:
    css = build_dashboard_css(theme_css="")
    body_section = css.split(".layout.view-network .map .body {", 1)[1].split("}", 1)[0]
    frame_section = css.split(".layout.view-network .map-frame {", 1)[1].split("}", 1)[0]

    assert ".layout.view-network .map-frame {" in css
    assert "background: transparent;" in body_section
    assert "padding: 0;" in body_section
    assert "border-top: 1px solid var(--network-pane-head-border);" in frame_section
    assert "background: #08110d;" in frame_section
    assert "padding: 1px;" in frame_section


def test_network_overview_hides_bottom_summary_grid_to_prioritize_plot_height() -> None:
    css = build_dashboard_css(theme_css="")
    overview_section = css.split(".layout.view-network #network-overview-overview {", 1)[1].split("}", 1)[0]

    assert "display: none;" in overview_section
    assert ".layout.view-network .network-overview-card .overview-grid {" not in css


def test_network_map_controls_follow_theme_tokens() -> None:
    css = build_dashboard_css(theme_css="")

    heatmap_input_section = css.split(".map-heatmap-wrap input {", 1)[1].split("}", 1)[0]
    reset_section = css.split(".map-reset-view-btn {", 1)[1].split("}", 1)[0]
    zoom_section = css.split(".leaflet-control-zoom {", 1)[1].split("}", 1)[0]
    tabs_section = css.split(".network-map-subview-tabs {", 1)[1].split("}", 1)[0]
    dark_heatmap_section = css.split("[data-theme=\"dark\"] .map-heatmap-wrap {", 1)[1].split("}", 1)[0]
    dark_zoom_section = css.split("[data-theme=\"dark\"] .leaflet-control-zoom {", 1)[1].split("}", 1)[0]
    dark_status_section = css.split("[data-theme=\"dark\"] .map-basemap-status {", 1)[1].split("}", 1)[0]
    dark_leaflet_section = css.rsplit("[data-theme=\"dark\"] .leaflet-container {", 1)[1].split("}", 1)[0]
    dark_offline_leaflet_section = css.split("[data-theme=\"dark\"] .map-frame.map-basemap-offline .leaflet-container {", 1)[1].split("}", 1)[0]
    dark_leaflet_overlay_section = css.split("[data-theme=\"dark\"] .map-frame:not(.map-basemap-offline) .leaflet-container::before {", 1)[1].split("}", 1)[0]

    assert "accent-color: var(--accent);" in heatmap_input_section
    assert "var(--accent)" in reset_section
    assert "var(--line)" in zoom_section
    assert "var(--accent)" in tabs_section
    assert "var(--workspace-shell-border)" in dark_heatmap_section
    assert "var(--workspace-shell-bg-alt)" in dark_zoom_section
    assert "var(--workspace-shell-text-soft)" in dark_status_section
    assert "var(--ui-bg-elev)" in dark_leaflet_section
    assert "var(--workspace-shell-bg)" in dark_offline_leaflet_section
    assert "z-index: 250;" in dark_leaflet_overlay_section
    assert "var(--ui-accent)" in dark_leaflet_overlay_section
    assert "var(--workspace-shell-active-bg)" in dark_leaflet_overlay_section


def test_node_list_names_keep_uniform_color_while_status_dots_remain() -> None:
    css = build_dashboard_css(theme_css="")

    assert ".chat-member-name.status-warn {" not in css
    assert ".chat-member-name.status-stale {" not in css
    assert ".chat-member-name.status-unknown {" not in css
    assert ".chat-member-status.status-warn {" in css
    assert ".chat-member-status.status-stale {" in css
    assert ".chat-member-status.status-unknown {" in css


def test_mobile_network_and_games_shells_expand_to_single_phone_column() -> None:
    css = build_dashboard_css(theme_css="")

    mobile_section = css.split("@media (max-width: 760px) {", 1)[1]

    assert '.workspace-shell[data-layout-view="network"] {' in mobile_section
    assert "height: calc(100dvh - var(--workspace-viewport-offset));" in mobile_section
    assert '.workspace-shell[data-layout-view="network"] .workspace-main {' in mobile_section
    assert "overflow: hidden;" in mobile_section
    assert '.workspace-shell[data-layout-view="network"] .workspace-main > .layout.view-network {' in mobile_section
    assert ".network-map-chrome {" in mobile_section
    assert "left: 6px;" in mobile_section
    assert ".layout.view-network .map .body {" in mobile_section
    assert "height: 100%;" in mobile_section
    assert ".layout.view-network .map," in mobile_section
    assert ".network-map-subview-tabs," in mobile_section
    assert ".network-overview-primary-controls {" in mobile_section
    assert "overflow-x: auto;" in mobile_section
    assert "flex-wrap: nowrap;" in mobile_section
    assert ".games-main {" in mobile_section
    assert "min-height: clamp(280px, 52vh, 420px);" in mobile_section
    assert ".games-main-panel {" in mobile_section
    assert "justify-content: stretch;" in mobile_section


def test_network_subviews_follow_workspace_theme_tokens(extract_css_block) -> None:
    css = build_dashboard_css(theme_css="")

    overview_panel_section = extract_css_block(css, '[data-theme="dark"] .network-overview-panel')
    overview_control_section = extract_css_block(css, '[data-theme="dark"] .network-overview-panel .history-metric-wrap')
    overview_primary_control_section = extract_css_block(css, '[data-theme="dark"] .network-overview-primary-controls .history-metric-wrap')
    overview_chart_section = extract_css_block(css, '[data-theme="dark"] .network-overview-panel #network-overview-chart-wrap')
    overview_stat_section = extract_css_block(css, '[data-theme="dark"] .network-overview-panel .overview-item')
    sensors_panel_section = extract_css_block(css, '[data-theme="dark"] .network-sensors-panel .env-metrics-explorer')
    sensors_control_section = extract_css_block(css, '[data-theme="dark"] .network-sensors-panel .env-metrics-control-group')
    sensors_chart_section = extract_css_block(css, '[data-theme="dark"] .network-sensors-panel #env-metrics-chart-wrap')
    diagnostics_pane_section = extract_css_block(css, '[data-theme="dark"] .network-diagnostics-pane')
    diagnostics_sender_section = extract_css_block(css, '[data-theme="dark"] .network-diagnostics-sender')
    diagnostics_entry_section = extract_css_block(css, '[data-theme="dark"] .network-diagnostics-entry')
    diagnostics_payload_section = extract_css_block(css, '[data-theme="dark"] .network-diagnostics-entry-payload')
    graph_chip_section = extract_css_block(css, '[data-theme="dark"] .network-graph-chip')
    graph_stage_section = extract_css_block(css, '[data-theme="dark"] .network-graph-stage')
    graph_edge_section = extract_css_block(css, '[data-theme="dark"] .network-graph-edge')
    graph_root_section = extract_css_block(css, '[data-theme="dark"] .network-graph-node.is-root .network-graph-node-core')

    assert "var(--workspace-shell-bg-alt)" in overview_panel_section
    assert "var(--workspace-shell-active-bg)" in overview_panel_section
    assert "var(--workspace-shell-border-muted)" in overview_control_section
    assert "var(--workspace-shell-active-bg)" in overview_control_section
    assert "var(--workspace-shell-border-muted)" in overview_primary_control_section
    assert "var(--workspace-shell-active-bg)" in overview_primary_control_section
    assert "var(--workspace-shell-border)" in overview_chart_section
    assert "var(--workspace-shell-bg-alt)" in overview_chart_section
    assert "var(--workspace-shell-active-bg)" in overview_stat_section
    assert "var(--workspace-shell-border)" in sensors_panel_section
    assert "var(--workspace-shell-bg-alt)" in sensors_panel_section
    assert "var(--workspace-shell-border)" in sensors_control_section
    assert "var(--workspace-shell-border)" in sensors_chart_section
    assert "var(--workspace-shell-border)" in diagnostics_pane_section
    assert "var(--workspace-shell-bg-alt)" in diagnostics_pane_section
    assert "var(--workspace-shell-border-muted)" in diagnostics_sender_section
    assert "var(--workspace-shell-active-bg)" in diagnostics_sender_section
    assert "var(--workspace-shell-border-muted)" in diagnostics_entry_section
    assert "var(--workspace-shell-bg)" in diagnostics_payload_section
    assert "var(--workspace-shell-bg-alt)" in graph_chip_section
    assert "var(--workspace-shell-border)" in graph_stage_section
    assert "var(--ui-accent)" in graph_edge_section
    assert "var(--workspace-shell-border-strong)" in graph_root_section


def test_network_overview_primary_controls_only_show_on_overview_subview() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'function syncNetworkOverviewPrimaryControls(viewName = activeLayoutView, subviewName = activeNetworkSubview) {' in js
    assert 'const controls = document.getElementById("network-overview-primary-controls");' in js
    assert 'const showControls = normalizedView === "network" && normalizedSubview === "overview";' in js
    assert "syncNetworkOverviewPrimaryControls(activeLayoutView, next);" in js
    assert "syncNetworkOverviewPrimaryControls(next, activeNetworkSubview);" in js


def test_history_window_controls_trail_and_stay_right_anchored() -> None:
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
    css = build_dashboard_css(theme_css="")

    overview_controls_section = html.split('id="network-overview-primary-controls"', 1)[1].split(
        '<div id="network-map-controls-host"',
        1,
    )[0]
    weekly_controls_section = html.split('<div class="history-metric-controls">', 1)[1].split(
        '<div id="weekly-summary-chart-wrap">',
        1,
    )[0]
    env_controls_section = html.split('<div class="env-metrics-controls">', 1)[1].split(
        '<div class="env-metrics-grid">',
        1,
    )[0]
    diagnostics_actions_section = html.split('<div class="network-diagnostics-toolbar-actions">', 1)[1].split(
        '</div>',
        1,
    )[0]
    window_wrap_section = css.split(".history-window-wrap {", 1)[1].split("}", 1)[0]

    assert overview_controls_section.index('for="network-overview-metric"') < overview_controls_section.index(
        'for="network-overview-window"'
    )
    assert weekly_controls_section.index('for="weekly-summary-metric"') < weekly_controls_section.index(
        'for="weekly-summary-window"'
    )
    assert env_controls_section.index('for="env-metric-select"') < env_controls_section.index('for="env-window-select"')
    assert diagnostics_actions_section.index('network-diagnostics-refresh-btn') < diagnostics_actions_section.index(
        'for="network-diagnostics-window"'
    )
    assert "margin-left: auto;" in window_wrap_section
    assert 'id="network-overview-link-mode-wrap"' in overview_controls_section
    assert 'id="network-overview-node-lines-wrap"' in overview_controls_section
    assert 'id="network-overview-packet-lines-wrap"' in overview_controls_section
    assert 'id="network-overview-sensor-controls-host"' in overview_controls_section
    assert overview_controls_section.index('id="network-overview-link-mode-wrap"') < overview_controls_section.index(
        'for="network-overview-window"'
    )
    assert overview_controls_section.index('id="network-overview-node-lines-wrap"') < overview_controls_section.index(
        'for="network-overview-window"'
    )
    assert overview_controls_section.index('id="network-overview-packet-lines-wrap"') < overview_controls_section.index(
        'for="network-overview-window"'
    )
    assert overview_controls_section.index('id="network-overview-sensor-controls-host"') < overview_controls_section.index(
        'for="network-overview-window"'
    )


def test_select_only_history_chips_hide_redundant_labels() -> None:
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
    css = build_dashboard_css(theme_css="")

    assert 'class="history-metric-wrap history-select-chip-hide-label"' in html
    assert 'class="history-metric-wrap history-window-wrap history-select-chip-hide-label"' in html
    assert 'class="history-metric-wrap history-select-chip-hide-label" hidden' in html
    assert 'class="history-metric-wrap history-window-wrap network-diagnostics-window-wrap history-select-chip-hide-label"' in html
    assert 'class="history-metric-wrap env-metrics-control-group history-select-chip-hide-label"' in html
    assert 'class="history-metric-wrap history-window-wrap env-metrics-control-group history-select-chip-hide-label"' in html
    assert ".history-select-chip-hide-label > .history-metric-label," in css
    assert ".history-select-chip-hide-label > label {" in css
    assert "display: none;" in css.split(".history-select-chip-hide-label > .history-metric-label,", 1)[1].split("}", 1)[0]
    compact_chip_section = css.split(".history-select-chip-hide-label {", 1)[1].split("}", 1)[0]
    assert "gap: 0;" in compact_chip_section
    assert "padding-left: 8px;" in compact_chip_section
    assert "padding-right: 8px;" in compact_chip_section


def test_network_overview_group_chips_hide_titles_in_top_strip() -> None:
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
    css = build_dashboard_css(theme_css="")

    assert 'class="history-metric-wrap history-metric-wrap-lines history-group-chip-hide-title" hidden' in html
    assert ".history-group-chip-hide-title > .history-metric-label {" in css
    assert "display: none;" in css.split(".history-group-chip-hide-title > .history-metric-label {", 1)[1].split("}", 1)[0]
    assert ".network-overview-primary-controls .history-metric-wrap-lines {" in css
    top_lines_section = css.split(".network-overview-primary-controls .history-metric-wrap-lines {", 1)[1].split("}", 1)[0]
    assert "flex-wrap: nowrap;" in top_lines_section
    assert "row-gap: 0;" in top_lines_section


def test_network_sensors_docked_explorer_reuses_overview_light_shell() -> None:
    css = build_dashboard_css(theme_css="")

    explorer_section = css.split(".network-sensors-panel .env-metrics-explorer {", 1)[1].split("}", 1)[0]
    chart_section = css.split(".network-sensors-panel #env-metrics-chart-wrap {", 1)[1].split("}", 1)[0]
    legend_section = css.split(".network-sensors-panel .env-node-legend-card {", 1)[1].split("}", 1)[0]

    assert "border: 1px solid rgba(188, 214, 195, 0.9);" in explorer_section
    assert "background: rgba(249, 253, 249, 0.92);" in explorer_section
    assert "box-shadow: 0 14px 34px rgba(22, 40, 30, 0.08);" in explorer_section
    assert "padding: 14px;" in explorer_section
    assert "gap: 8px;" in explorer_section

    assert "border-color: #d7e5d2;" in chart_section
    assert "linear-gradient(180deg, #fbfffc 0%, #eef8f1 100%)" in chart_section
    assert "padding: 0;" in chart_section
    assert "rgba(18, 29, 39, 0.98)" not in chart_section

    assert "border: 1px solid #d7e5d2;" in legend_section
    assert "background: #f9fdf9;" in legend_section
    assert "color: #193a28;" in legend_section


def test_network_subview_charts_pull_runtime_theme_vars() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'themeColor("--workspace-shell-border-muted"' in js
    assert 'themeColor("--workspace-shell-active-text"' in js
    assert 'themeColor("--workspace-shell-text-soft"' in js
    assert 'themeColor("--ui-accent"' in js


def test_dark_text_input_variants_use_neutral_ui_tokens_for_chat_compose_controls() -> None:
    css = build_dashboard_css(theme_css="")

    search_input_section = css.rsplit("[data-theme=\"dark\"] .list-search-input,", 1)[1].split("}", 1)[0]
    shared_text_inputs_section = css.split("[data-theme=\"dark\"] .chat-peer-input,", 1)[1].split("}", 1)[0]
    shared_focus_section = css.split("[data-theme=\"dark\"] .chat-peer-input:focus,", 1)[1].split("}", 1)[0]

    assert "var(--ui-panel)" in search_input_section
    assert "var(--ui-border)" in search_input_section
    assert "var(--ui-text)" in search_input_section
    assert "[data-theme=\"dark\"] .settings-textarea," in css
    assert "[data-theme=\"dark\"] .chat-input," in css
    assert "var(--ui-panel)" in shared_text_inputs_section
    assert "var(--ui-border)" in shared_text_inputs_section
    assert "var(--ui-text)" in shared_text_inputs_section
    assert "var(--ui-accent)" in shared_focus_section
    assert "var(--ui-panel-alt)" in shared_focus_section
    assert "color-mix(in srgb, var(--ui-accent) 22%, transparent)" in shared_focus_section
    assert "[data-theme=\"dark\"] .settings-textarea::placeholder," in css
    assert "opacity: 0.9;" in css


def test_games_boards_follow_runtime_theme_tokens(extract_css_block) -> None:
    css = build_dashboard_css(theme_css="")

    board_wrap_section = extract_css_block(css, ".games-board-wrap")
    reversi_board_section = extract_css_block(css, ".reversi-board")
    reversi_cell_section = extract_css_block(css, ".reversi-cell")
    classic_board_section = extract_css_block(css, ".checkers-board,\n    .chess-board,\n    .wall-chess-board")
    dark_board_wrap_section = extract_css_block(css, '[data-theme="dark"] .games-board-wrap')
    dark_reversi_board_section = extract_css_block(css, '[data-theme="dark"] .reversi-board')
    dark_classic_board_section = extract_css_block(css, '[data-theme="dark"] .checkers-board')

    assert "var(--ui-accent-soft, var(--accent, #2f855a))" in board_wrap_section
    assert "var(--games-board-frame)" in board_wrap_section
    assert "var(--surface-tint-bg-soft, #f4faf3)" in board_wrap_section
    assert "var(--surface-tint-bg, #edf6ec)" in board_wrap_section
    assert "var(--reversi-board-accent)" in reversi_board_section
    assert "var(--reversi-board-cell)" in reversi_cell_section
    assert "var(--surface-tint-bg-soft, #f4faf3)" in reversi_board_section
    assert "var(--surface-tint-border-strong, #b8cab9)" in reversi_board_section
    assert "var(--classic-board-accent)" in classic_board_section
    assert "var(--surface-tint-bg, #edf6ec)" in classic_board_section
    assert "var(--surface-tint-border-strong, #b8cab9)" in classic_board_section
    assert "var(--workspace-shell-bg-alt)" in dark_board_wrap_section
    assert "var(--workspace-shell-border)" in dark_board_wrap_section
    assert "var(--ui-accent)" in dark_reversi_board_section
    assert "var(--workspace-shell-bg)" in dark_classic_board_section
    assert "#07110c" not in board_wrap_section
    assert "#0c1611" not in reversi_board_section
    assert "#0b140f" not in classic_board_section
    assert "#173526" not in dark_board_wrap_section
    assert "#113a2b" not in dark_reversi_board_section


def test_apps_views_bias_space_toward_primary_canvas() -> None:
    css = build_dashboard_css(theme_css="")

    files_shell_section = css.split(".files-shell {", 1)[1].split("}", 1)[0]
    games_shell_section = css.split(".games-shell {", 1)[1].split("}", 1)[0]
    games_main_section = css.split(".games-main {", 1)[1].split("}", 1)[0]
    games_board_wrap_section = css.split(".games-board-wrap {", 1)[1].split("}", 1)[0]
    reversi_board_section = css.split(".reversi-board {", 1)[1].split("}", 1)[0]
    checkers_board_section = css.split(".checkers-board {", 1)[1].split("}", 1)[0]
    container_query_section = css.split("@supports (width: 1cqi) {", 1)[1]

    assert "height: 100%;" in files_shell_section
    assert "--games-sidebar-width: 220px;" in games_shell_section
    assert "--games-status-width: 176px;" in games_shell_section
    assert "minmax(176px, var(--games-sidebar-width))" in games_shell_section
    assert "var(--splitter-size)" in games_shell_section
    assert "minmax(140px, var(--games-status-width))" in games_shell_section
    assert "gap: 0;" in games_shell_section
    assert "padding: 4px;" in games_main_section
    assert "padding: 4px;" in games_board_wrap_section
    assert "--reversi-cell-size: clamp(32px, min(6.9vw, 8.7vh), 94px);" in reversi_board_section
    assert "--checkers-cell-size: clamp(32px, min(6.9vw, 8.7vh), 94px);" in checkers_board_section
    assert "--chess-cell-size: clamp(32px, min(6.9vw, 8.7vh), 94px);" in css
    assert "--reversi-cell-size: clamp(30px, 14.1cqi, 94px);" in container_query_section
    assert "--checkers-cell-size: clamp(30px, 14.1cqi, 94px);" in container_query_section
    assert "--chess-cell-size: clamp(30px, 14.1cqi, 94px);" in container_query_section


def test_games_workspace_uses_persistent_adjustable_splitters() -> None:
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
    css = build_dashboard_css(theme_css="")
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    mobile_section = css.split("@media (max-width: 1100px) {", 1)[1]
    dark_splitter_section = css.split("[data-theme=\"dark\"] .games-shell-splitter {", 1)[1].split("}", 1)[0]

    assert 'id="games-sidebar-splitter"' in html
    assert 'id="games-status-splitter"' in html
    assert 'data-target="left"' in html
    assert 'data-target="right"' in html
    assert ".games-shell-splitter {" in css
    assert ".games-shell-splitter::before {" in css
    assert "#games-status-splitter {" in css
    assert "display: none;" in mobile_section
    assert "var(--ui-border)" in dark_splitter_section
    assert 'const gamesSidebarSplitStorageKey = "meshDashboardGamesSidebarWidthPx";' in js
    assert 'const gamesStatusSplitStorageKey = "meshDashboardGamesStatusWidthPx";' in js
    assert "let gamesSidebarWidthPx = 220;" in js
    assert "let gamesStatusWidthPx = 176;" in js
    assert "function applyGamesSplitState() {" in js
    assert "function bindGamesSplitters() {" in js
    assert 'runBootStep("loadGamesSidebarSplitState", () => loadGamesSidebarSplitState());' in js
    assert 'runBootStep("loadGamesStatusSplitState", () => loadGamesStatusSplitState());' in js
    assert 'runBootStep("bindGamesSplitters", () => bindGamesSplitters());' in js
    assert "persistGamesSidebarSplitState()" in js
    assert "persistGamesStatusSplitState()" in js
    assert 'if (next === "games" && typeof applyGamesSplitState === "function") {' in js


def test_node_details_drawer_follows_workspace_shell_tokens() -> None:
    css = build_dashboard_css(theme_css="")

    drawer_section = css.split("[data-theme=\"dark\"] .chat-node-details-drawer {", 1)[1].split("}", 1)[0]
    head_section = css.split("[data-theme=\"dark\"] .chat-node-details-head {", 1)[1].split("}", 1)[0]
    tab_section = css.split("[data-theme=\"dark\"] .chat-node-details-tab-btn {", 1)[1].split("}", 1)[0]
    active_tab_section = css.split("[data-theme=\"dark\"] .chat-node-details-tab-btn.is-active {", 1)[1].split("}", 1)[0]
    action_section = css.split("[data-theme=\"dark\"] .chat-node-details-action-btn {", 1)[1].split("}", 1)[0]
    saved_details_section = css.split("[data-theme=\"dark\"] .chat-node-details-drawer .saved-node-details {", 1)[1].split("}", 1)[0]
    saved_section = css.split("[data-theme=\"dark\"] .saved-node-section {", 1)[1].split("}", 1)[0]
    saved_stat_section = css.split("[data-theme=\"dark\"] .saved-node-stat {", 1)[1].split("}", 1)[0]
    splitter_section = css.split("[data-theme=\"dark\"] .chat-node-details-splitter {", 1)[1].split("}", 1)[0]
    splitter_handle_section = css.split("[data-theme=\"dark\"] .chat-node-details-splitter::before {", 1)[1].split("}", 1)[0]

    assert "var(--workspace-shell-border)" in drawer_section
    assert "var(--workspace-shell-bg)" in drawer_section
    assert "var(--workspace-shell-bg-alt)" in head_section
    assert "var(--workspace-shell-text-soft)" in tab_section
    assert "var(--workspace-shell-active-bg)" in active_tab_section
    assert "var(--workspace-shell-active-text)" in active_tab_section
    assert "var(--workspace-shell-border-muted)" in action_section
    assert "var(--workspace-shell-bg)" in saved_details_section
    assert "var(--workspace-shell-bg-alt)" in saved_section
    assert "var(--workspace-shell-border-muted)" in saved_stat_section
    assert "var(--workspace-shell-border)" in splitter_section
    assert "var(--workspace-shell-bg-alt)" in splitter_section
    assert "var(--workspace-shell-bg)" in splitter_section
    assert "var(--workspace-shell-border-muted)" in splitter_handle_section
    assert "#0e1713" not in drawer_section
    assert "#172820" not in tab_section


def test_chat_header_pills_follow_workspace_shell_tab_tokens() -> None:
    css = build_dashboard_css(theme_css="")

    toggle_section = css.split("[data-theme=\"dark\"] .chat-peer-add-toggle-btn {", 1)[1].split("}", 1)[0]
    toggle_active_section = css.split("[data-theme=\"dark\"] .chat-peer-add-toggle-btn[aria-expanded=\"true\"],", 1)[1].split("}", 1)[0]
    collapse_section = css.split("[data-theme=\"dark\"] .chat-panel-collapse-btn {", 1)[1].split("}", 1)[0]
    collapse_active_section = css.split("[data-theme=\"dark\"] .chat-panel-collapse-btn[aria-pressed=\"true\"] {", 1)[1].split("}", 1)[0]
    channel_pill_section = css.split("[data-theme=\"dark\"] .mesh-channel-pill {", 1)[1].split("}", 1)[0]
    channel_pill_active_section = css.split("[data-theme=\"dark\"] .mesh-channel-pill.active {", 1)[1].split("}", 1)[0]

    assert "var(--workspace-shell-border-muted)" in toggle_section
    assert "var(--workspace-shell-bg-alt)" in toggle_section
    assert "var(--workspace-shell-text-soft)" in toggle_section
    assert "var(--workspace-shell-active-bg)" in toggle_active_section
    assert "var(--workspace-shell-active-text)" in toggle_active_section
    assert "var(--workspace-shell-border-muted)" in collapse_section
    assert "var(--workspace-shell-bg-alt)" in collapse_section
    assert "var(--workspace-shell-active-bg)" in collapse_active_section
    assert "var(--workspace-shell-text-soft)" in channel_pill_section
    assert "var(--workspace-shell-border-muted)" in channel_pill_section
    assert "var(--workspace-shell-active-bg)" in channel_pill_active_section
    assert "var(--workspace-shell-active-text)" in channel_pill_active_section
    assert "#16261f" not in toggle_section
    assert "rgba(20, 35, 28, 0.34)" not in channel_pill_section


def test_node_navigator_menu_follows_workspace_shell_tokens() -> None:
    css = build_dashboard_css(theme_css="")

    menu_section = css.split("[data-theme=\"dark\"] .chat-node-navigator-menu,", 1)[1].split("}", 1)[0]
    sort_btn_section = css.split("[data-theme=\"dark\"] .chat-node-navigator-sort-dir-btn,", 1)[1].split("}", 1)[0]
    label_section = css.split("[data-theme=\"dark\"] .chat-node-navigator-label,", 1)[1].split("}", 1)[0]
    head_section = css.split("[data-theme=\"dark\"] .chat-node-navigator-fields-head {", 1)[1].split("}", 1)[0]
    sort_btn_hover_section = css.split("[data-theme=\"dark\"] .chat-node-navigator-sort-dir-btn:hover,", 1)[1].split("}", 1)[0]
    checkbox_section = css.split(".chat-node-navigator-field-option input {", 1)[1].split("}", 1)[0]

    assert "var(--workspace-shell-bg)" in menu_section
    assert "var(--workspace-shell-border)" in menu_section
    assert "var(--workspace-shell-bg-alt)" in sort_btn_section
    assert "var(--workspace-shell-border-muted)" in sort_btn_section
    assert "var(--workspace-shell-text-soft)" in sort_btn_section
    assert "var(--workspace-shell-text)" in label_section
    assert "var(--workspace-shell-text-soft)" in head_section
    assert "var(--workspace-shell-hover-bg)" in sort_btn_hover_section
    assert "var(--workspace-shell-border-strong)" in sort_btn_hover_section
    assert "var(--ui-accent, var(--accent))" in checkbox_section
    assert "#0d1711" not in menu_section
    assert "#16261f" not in sort_btn_section


def test_node_navigator_status_marker_geometry_supports_dot_and_emoji_variants(extract_css_block) -> None:
    css = build_dashboard_css(theme_css="")

    hidden_item_section = extract_css_block(css, ".chat-member-item.status-hidden")
    status_section = extract_css_block(css, ".chat-member-status")
    dot_section = extract_css_block(css, ".chat-member-status-dot")
    emoji_section = extract_css_block(css, ".chat-member-status-emoji")
    ring_section = extract_css_block(css, ".chat-member-status-ring")
    glyph_section = extract_css_block(css, ".chat-member-status-emoji-glyph")

    assert "grid-template-columns: 0 minmax(0, 1fr);" in hidden_item_section
    assert "width: 18px;" in status_section
    assert "min-width: 18px;" in status_section
    assert "height: 18px;" in status_section
    assert "display: inline-flex;" in status_section
    assert "justify-content: center;" in status_section
    assert "font-size: 11px;" in dot_section
    assert "font-size: 13px;" in emoji_section
    assert "isolation: isolate;" in emoji_section
    assert "position: absolute;" in ring_section
    assert "border-radius: 999px;" in ring_section
    assert "border: 1.5px solid currentColor;" in ring_section
    assert "position: relative;" in glyph_section
    assert "transform: translateY(0.2px);" in glyph_section


def test_history_chart_surfaces_follow_workspace_shell_tokens() -> None:
    css = build_dashboard_css(theme_css="")

    toggle_section = css.split("[data-theme=\"dark\"] .history-metric-toggle {", 1)[1].split("}", 1)[0]
    wrap_section = css.split("[data-theme=\"dark\"] #signal-chart-wrap,", 1)[1].split("}", 1)[0]
    empty_section = css.split("[data-theme=\"dark\"] .signal-empty {", 1)[1].split("}", 1)[0]
    track_section = css.split("[data-theme=\"dark\"] .signal-timeline-track {", 1)[1].split("}", 1)[0]
    tick_section = css.split("[data-theme=\"dark\"] .signal-timeline-tick {", 1)[1].split("}", 1)[0]
    major_label_section = css.split("[data-theme=\"dark\"] .signal-timeline-label-major {", 1)[1].split("}", 1)[0]

    assert "var(--ui-accent)" in toggle_section
    assert "var(--workspace-shell-border)" in wrap_section
    assert "var(--workspace-shell-bg-alt)" in wrap_section
    assert "var(--workspace-shell-bg)" in wrap_section
    assert "var(--workspace-shell-text-soft)" in empty_section
    assert "var(--workspace-shell-border-muted)" in track_section
    assert "var(--workspace-shell-border-strong)" in tick_section
    assert "var(--workspace-shell-text)" in major_label_section
    assert "#141c27" not in wrap_section
    assert "#344353" not in track_section


def test_dark_history_legends_reuse_network_plot_palette() -> None:
    css = build_dashboard_css(theme_css="")

    primary_section = css.split("[data-theme=\"dark\"] .signal-legend .legend-chip.is-primary,", 1)[1].split("}", 1)[0]
    compare_section = css.split("[data-theme=\"dark\"] .signal-legend .legend-chip.is-compare {", 1)[1].split("}", 1)[0]

    assert "#009E73" in primary_section
    assert "#56B4E9" in compare_section
    assert "var(--workspace-shell-border-strong)" not in compare_section


def test_history_charts_pull_runtime_theme_vars() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "function historyChartThemeColor(name, fallback)" in js
    assert "function historyChartSeriesPaletteColor(paletteName, fallback)" in js
    assert "function historyChartPalette()" in js
    assert 'historyChartSeriesPaletteColor("bluish green", "#009E73")' in js
    assert 'historyChartSeriesPaletteColor("sky blue", "#56B4E9")' in js
    assert 'historyChartSeriesPaletteColor("orange", "#E69F00")' in js
    assert 'historyChartSeriesPaletteColor("vermillion", "#D55E00")' in js
    assert 'historyChartThemeColor("--workspace-shell-border-muted"' in js


def test_node_row_packet_sparklines_use_layered_chart_markup() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'chat-member-packet-sparkline-raw' in js
    assert 'chat-member-packet-sparkline-trend' in js
    assert 'class="metric-ticker-chart chat-member-packet-sparkline"' in js


def test_dark_row_packet_sparklines_reuse_network_compare_blue() -> None:
    css = build_dashboard_css(theme_css="")

    flat_section = css.split("[data-theme=\"dark\"] .chat-member-packet-trend.metric-ticker.trend-flat {", 1)[1].split("}", 1)[0]

    assert "#56B4E9" in flat_section
    assert "var(--workspace-shell-border-strong)" not in flat_section


def test_saved_node_notes_and_tag_editor_follow_theme_tokens() -> None:
    css = build_dashboard_css(theme_css="")

    note_section = css.split("[data-theme=\"dark\"] .saved-node-note-input {", 1)[1].split("}", 1)[0]
    note_focus_section = css.split("[data-theme=\"dark\"] .saved-node-note-input:focus {", 1)[1].split("}", 1)[0]
    tag_editor_section = css.split("[data-theme=\"dark\"] .favorite-menu-tag-editor {", 1)[1].split("}", 1)[0]
    tag_input_section = css.split("[data-theme=\"dark\"] .favorite-menu-tag-preset-select,", 1)[1].split("}", 1)[0]
    tag_focus_section = css.split("[data-theme=\"dark\"] .favorite-menu-tag-preset-select:focus,", 1)[1].split("}", 1)[0]
    tag_action_section = css.split("[data-theme=\"dark\"] .favorite-menu-tag-editor-actions .btn {", 1)[1].split("}", 1)[0]
    slider_section = css.split(".favorite-menu-tag-vibrance-input {", 1)[1].split("}", 1)[0]

    assert "var(--workspace-shell-border)" in note_section
    assert "var(--workspace-shell-bg)" in note_section
    assert "var(--workspace-shell-bg-alt)" in note_section
    assert "var(--workspace-shell-text)" in note_section
    assert "var(--workspace-shell-border-strong)" in note_focus_section
    assert "var(--workspace-shell-border)" in tag_editor_section
    assert "var(--workspace-shell-bg-alt)" in tag_editor_section
    assert "var(--workspace-shell-border-muted)" in tag_input_section
    assert "var(--workspace-shell-text)" in tag_input_section
    assert "var(--workspace-shell-border-strong)" in tag_focus_section
    assert "var(--workspace-shell-border-muted)" in tag_action_section
    assert "var(--workspace-shell-text)" in tag_action_section
    assert "var(--ui-accent, var(--accent))" in slider_section
    assert "#121b24" not in note_section
    assert "#15281f" not in tag_editor_section


def test_peer_dm_menu_and_popout_follow_workspace_shell_tokens() -> None:
    css = build_dashboard_css(theme_css="")

    menu_section = css.split("[data-theme=\"dark\"] .peer-dm-menu {", 1)[1].split("}", 1)[0]
    menu_list_section = css.split("[data-theme=\"dark\"] .peer-dm-menu-list {", 1)[1].split("}", 1)[0]
    empty_section = css.split("[data-theme=\"dark\"] .peer-dm-menu-empty {", 1)[1].split("}", 1)[0]
    item_hover_section = css.split("[data-theme=\"dark\"] .peer-dm-menu-item:hover {", 1)[1].split("}", 1)[0]
    popout_section = css.split("[data-theme=\"dark\"] .peer-dm-popout-window {", 1)[1].split("}", 1)[0]
    head_section = css.split("[data-theme=\"dark\"] .peer-dm-popout-head {", 1)[1].split("}", 1)[0]
    msg_section = css.split("[data-theme=\"dark\"] .peer-dm-popout-msg {", 1)[1].split("}", 1)[0]
    composer_section = css.split("[data-theme=\"dark\"] .peer-dm-popout-composer {", 1)[1].split("}", 1)[0]
    input_section = css.split("[data-theme=\"dark\"] .peer-dm-popout-input {", 1)[1].split("}", 1)[0]
    send_section = css.split("[data-theme=\"dark\"] .peer-dm-popout-send-btn {", 1)[1].split("}", 1)[0]

    assert "var(--workspace-shell-bg-alt)" in menu_section
    assert "var(--workspace-shell-border)" in menu_section
    assert "var(--workspace-shell-bg)" in menu_list_section
    assert "var(--workspace-shell-text-soft)" in empty_section
    assert "var(--workspace-shell-border-muted)" in empty_section
    assert "var(--workspace-shell-hover-bg)" in item_hover_section
    assert "var(--workspace-shell-border-strong)" in item_hover_section
    assert "var(--workspace-shell-border)" in popout_section
    assert "var(--workspace-shell-bg-alt)" in popout_section
    assert "var(--workspace-shell-bg)" in popout_section
    assert "var(--workspace-shell-border-muted)" in head_section
    assert "var(--workspace-shell-border-muted)" in msg_section
    assert "var(--workspace-shell-text)" in msg_section
    assert "var(--workspace-shell-border-muted)" in composer_section
    assert "var(--workspace-shell-border)" in input_section
    assert "var(--workspace-shell-text)" in input_section
    assert "var(--ui-accent, var(--accent))" in send_section
    assert "black 76%" in send_section
    assert "#13241b" not in menu_list_section
    assert "#152633" not in input_section


def test_lists_and_about_panels_follow_workspace_shell_tokens() -> None:
    css = build_dashboard_css(theme_css="")

    list_section = css.split("[data-theme=\"dark\"] .node-visibility-section {", 1)[1].split("}", 1)[0]
    list_card_section = css.split("[data-theme=\"dark\"] .node-visibility-card,", 1)[1].split("}", 1)[0]
    list_empty_section = css.split("[data-theme=\"dark\"] .node-visibility-card-empty,", 1)[1].split("}", 1)[0]
    list_btn_section = css.split("[data-theme=\"dark\"] .node-visibility-section .btn {", 1)[1].split("}", 1)[0]
    badge_section = css.split("[data-theme=\"dark\"] .node-visibility-badge {", 1)[1].split("}", 1)[0]
    about_meta_section = css.split("[data-theme=\"dark\"] .chat-settings-meta-item {", 1)[1].split("}", 1)[0]
    about_disk_section = css.split("[data-theme=\"dark\"] .settings-system-disk-meter {", 1)[1].split("}", 1)[0]

    assert "var(--workspace-shell-border)" in list_section
    assert "var(--workspace-shell-bg-alt)" in list_section
    assert "var(--workspace-shell-bg)" in list_section
    assert "var(--workspace-shell-border)" in list_card_section
    assert "var(--workspace-shell-text-soft)" in list_empty_section
    assert "var(--workspace-shell-border-muted)" in list_btn_section
    assert "var(--workspace-shell-text)" in list_btn_section
    assert "var(--workspace-shell-active-bg)" in badge_section
    assert "var(--workspace-shell-border-strong)" in badge_section
    assert "var(--workspace-shell-active-text)" in badge_section
    assert "var(--workspace-shell-border-muted)" in about_meta_section
    assert "var(--workspace-shell-text)" in about_meta_section
    assert "var(--workspace-shell-border-muted)" in about_disk_section
    assert "var(--workspace-shell-text)" in about_disk_section
    assert "#13241b" not in about_meta_section
    assert "#15241c" not in list_section


def test_settings_checkboxes_follow_runtime_accent() -> None:
    css = build_dashboard_css(theme_css="")

    settings_checkbox_section = css.split(".settings-panel input[type=\"checkbox\"] {", 1)[1].split("}", 1)[0]
    time_sync_checkbox_section = css.split(".settings-time-sync-toggle input[type=\"checkbox\"] {", 1)[1].split("}", 1)[0]

    assert "accent-color: var(--ui-accent, var(--accent));" in settings_checkbox_section
    assert "accent-color: var(--ui-accent, var(--accent));" in time_sync_checkbox_section
    assert "width: 14px;" in settings_checkbox_section
    assert "#2f855a" not in time_sync_checkbox_section


def test_topbar_tickers_follow_workspace_shell_and_semantic_states() -> None:
    css = build_dashboard_css(theme_css="")

    topbar_section = css.rsplit("[data-theme=\"dark\"] .topbar {", 1)[1].split("}", 1)[0]
    ticker_section = css.split("[data-theme=\"dark\"] .topbar .summary-ticker-item {", 1)[1].split("}", 1)[0]
    hover_section = css.split("[data-theme=\"dark\"] .topbar .summary-ticker-item:hover {", 1)[1].split("}", 1)[0]
    neutral_section = css.split("[data-theme=\"dark\"] .topbar .summary-ticker-item.metric-state-neutral {", 1)[1].split("}", 1)[0]
    bad_section = css.split("[data-theme=\"dark\"] .topbar .summary-ticker-item.metric-state-bad {", 1)[1].split("}", 1)[0]
    chart_section = css.split("[data-theme=\"dark\"] .topbar .summary-ticker-item .metric-ticker-chart path {", 1)[1].split("}", 1)[0]
    target_status_section = css.split("[data-theme=\"dark\"] .topbar .summary-ticker-item .target-radio-status {", 1)[1].split("}", 1)[0]

    assert "var(--floating-stage-bg)" in topbar_section
    assert "border-bottom: 0;" in topbar_section
    assert "box-shadow: none;" in topbar_section
    assert "#121a25" not in topbar_section
    assert "border-color: var(--workspace-shell-border);" in ticker_section
    assert "var(--workspace-shell-border-strong)" in ticker_section
    assert "var(--workspace-shell-active-text)" in ticker_section
    assert "var(--ui-panel)" in ticker_section
    assert "var(--ui-text)" in ticker_section
    assert "box-shadow: none;" in ticker_section
    assert "border-color: var(--workspace-shell-border-strong);" in hover_section
    assert "var(--workspace-shell-hover-bg)" in hover_section
    assert "var(--workspace-shell-text-soft)" in neutral_section
    assert "#cf6f6f" in bad_section
    assert "var(--ticker-card-accent)" in chart_section
    assert "var(--ui-border)" in target_status_section
    assert "var(--ui-panel-alt)" in target_status_section
    assert "var(--ui-text-soft)" in target_status_section


def test_topbar_controls_share_workspace_shell_tokens() -> None:
    css = build_dashboard_css(theme_css="")

    launcher_section = css.split("[data-theme=\"dark\"] .topbar-view-menu-btn {", 1)[1].split("}", 1)[0]
    launcher_hover_section = css.split("[data-theme=\"dark\"] .topbar-view-menu-btn:hover,", 1)[1].split("}", 1)[0]
    update_section = css.split("[data-theme=\"dark\"] .topbar-update-ticker {", 1)[1].split("}", 1)[0]
    update_text_section = css.split("[data-theme=\"dark\"] .topbar-update-text,", 1)[1].split("}", 1)[0]
    icon_section = css.split("[data-theme=\"dark\"] .topbar-chat-change-menu-wrap .chat-change-toggle-btn,", 1)[1].split("}", 1)[0]
    icon_hover_section = css.split("[data-theme=\"dark\"] .topbar-chat-change-menu-wrap .chat-change-toggle-btn:hover,", 1)[1].split("}", 1)[0]
    self_profile_section = css.split("[data-theme=\"dark\"] .topbar-self-profile {", 1)[1].split("}", 1)[0]

    assert "--topbar-shell-border:" not in css
    assert "--topbar-shell-control-bg:" not in css
    assert "var(--workspace-shell-border)" in launcher_section
    assert "var(--workspace-shell-border-strong)" in launcher_hover_section
    assert ".topbar-view-menu-btn-mark" not in css
    assert "accent-2" not in launcher_section
    assert "box-shadow: none;" in launcher_section
    assert "var(--workspace-shell-border)" in update_section
    assert "var(--workspace-shell-bg-alt)" in update_section
    assert "var(--workspace-shell-bg)" in update_section
    assert "var(--workspace-shell-text)" in update_section
    assert "box-shadow: none;" in update_section
    assert "var(--workspace-shell-text-soft)" in update_text_section
    assert "var(--workspace-shell-border)" in icon_section
    assert "var(--workspace-shell-bg-alt)" in icon_section
    assert "var(--workspace-shell-bg)" in icon_section
    assert "var(--workspace-shell-text)" in icon_section
    assert "var(--workspace-shell-border-strong)" in icon_hover_section
    assert "var(--workspace-shell-hover-bg)" in icon_hover_section
    assert "var(--workspace-shell-border)" in self_profile_section
    assert "var(--workspace-shell-bg-alt)" in self_profile_section
    assert "var(--workspace-shell-bg)" in self_profile_section
    assert "var(--workspace-shell-text)" in self_profile_section


def test_console_view_removes_body_shell_and_keeps_terminal_frame() -> None:
    css = build_dashboard_css(theme_css="")
    body_section = css.split(".layout.view-console .console .body {", 1)[1].split("}", 1)[0]
    light_screen_section = css.split("\n    .console-terminal-screen {", 1)[1].split("}", 1)[0]
    dark_screen_section = css.split("[data-theme=\"dark\"] .console-terminal-screen {", 1)[1].split("}", 1)[0]
    dark_overlay_section = css.split("[data-theme=\"dark\"] .console-terminal-screen::before {", 1)[1].split("}", 1)[0]
    dark_live_console_section = css.split("[data-theme=\"dark\"] #live-console {", 1)[1].split("}", 1)[0]

    assert ".layout.view-console .console .body {" in css
    assert "background: transparent;" in body_section
    assert "padding: 0;" in body_section
    assert ".console-terminal-screen {" in css
    assert "border: 1px solid var(--surface-tint-border-strong, #7ab18a);" in light_screen_section
    assert "border-radius: 8px;" in css
    assert "var(--surface-tint-color)" in light_screen_section
    assert "var(--surface-tint-bg-soft," in light_screen_section
    assert "var(--surface-tint-bg-alt," in light_screen_section
    assert "var(--surface-tint-bg," in light_screen_section
    assert "var(--surface-tint-border)" in dark_screen_section
    assert "var(--surface-tint-bg)" in dark_screen_section
    assert "var(--surface-tint-bg-alt)" in dark_screen_section
    assert "var(--surface-tint-color)" in dark_screen_section
    assert "rgba(83, 170, 112, 0.09)" not in dark_screen_section
    assert "var(--surface-tint-border)" in dark_overlay_section
    assert "var(--surface-tint-text)" in dark_live_console_section


def test_settings_view_removes_outer_card_shell_but_keeps_inner_panels() -> None:
    css = build_dashboard_css(theme_css="")
    settings_section = css.split(".layout.view-settings .settings {", 1)[1].split("}", 1)[0]
    body_section = css.split(".layout.view-settings .settings .body {", 1)[1].split("}", 1)[0]

    assert "background: transparent;" in settings_section
    assert "border: 0;" in settings_section
    assert "box-shadow: none;" in settings_section
    assert "overflow: visible;" in settings_section
    assert "background: transparent;" in body_section
    assert "padding: 0;" in body_section
    assert ".settings-chrome {" in css
    assert ".settings-panel {" in css


def test_games_view_removes_outer_card_shell_but_keeps_inner_panels() -> None:
    css = build_dashboard_css(theme_css="")
    games_section = css.split(".layout.view-games .games {", 1)[1].split("}", 1)[0]
    body_section = css.split(".layout.view-games .games .body {", 1)[1].split("}", 1)[0]

    assert "background: transparent;" in games_section
    assert "border: 0;" in games_section
    assert "box-shadow: none;" in games_section
    assert "overflow: visible;" in games_section
    assert "background: transparent;" in body_section
    assert "padding: 0;" in body_section
    assert ".games-toolbar {" in css
    assert ".games-sidebar {" in css
    assert ".games-main {" in css


def test_files_view_removes_outer_card_shell_for_full_app_canvas() -> None:
    css = build_dashboard_css(theme_css="")
    files_section = css.split(".layout.view-files .files {", 1)[1].split("}", 1)[0]
    files_body_section = css.split(".layout.view-files .files .body {", 1)[1].split("}", 1)[0]

    assert "background: transparent;" in files_section
    assert "border: 0;" in files_section
    assert "box-shadow: none;" in files_section
    assert "overflow: visible;" in files_section
    assert "background: transparent;" in files_body_section
    assert "padding: 0;" in files_body_section


def test_files_view_uses_theme_tokens_in_light_and_dark_modes() -> None:
    css = build_dashboard_css(theme_css="")

    light_card_section = css.split(".card.files {", 1)[1].split("}", 1)[0]
    light_controls_section = css.split(".files-controls {", 1)[1].split("}", 1)[0]
    light_console_log_section = css.split(".files-console-log {", 1)[1].split("}", 1)[0]
    light_table_head_section = css.split("#files-transfer-table thead th {", 1)[1].split("}", 1)[0]
    dark_card_section = css.split("[data-theme=\"dark\"] .card.files {", 1)[1].split("}", 1)[0]
    dark_caption_section = css.split("[data-theme=\"dark\"] .files-caption,", 1)[1].split("}", 1)[0]
    dark_console_log_section = css.split("[data-theme=\"dark\"] .files-console-log {", 1)[1].split("}", 1)[0]
    dark_table_head_section = css.rsplit("[data-theme=\"dark\"] #files-transfer-table thead th {", 1)[1].split("}", 1)[0]
    dark_secondary_btn_section = css.split("[data-theme=\"dark\"] .files-controls .btn.btn-secondary {", 1)[1].split("}", 1)[0]

    assert "var(--panel)" in light_card_section
    assert "var(--ui-text" in light_card_section
    assert "#f6fbf5" not in light_card_section
    assert "var(--surface-tint-bg-soft" in light_controls_section
    assert "var(--surface-tint-border" in light_controls_section
    assert "#edf6ec" not in light_controls_section
    assert "var(--surface-tint-color" in light_console_log_section
    assert "var(--surface-tint-border-strong" in light_console_log_section
    assert "#0f1b14" not in light_console_log_section
    assert "var(--surface-tint-text" in light_table_head_section
    assert "var(--surface-tint-border" in light_table_head_section

    assert "var(--workspace-shell-bg)" in dark_card_section
    assert "var(--workspace-shell-text)" in dark_card_section
    assert "#dbece3" not in dark_card_section
    assert "var(--workspace-shell-text-soft)" in dark_caption_section
    assert "#a8c6b7" not in dark_caption_section
    assert "var(--surface-tint-color" in dark_console_log_section
    assert "var(--surface-tint-text" in dark_console_log_section
    assert "var(--workspace-shell-border)" in dark_table_head_section
    assert "var(--workspace-shell-bg-alt)" in dark_table_head_section
    assert "var(--workspace-shell-border-muted)" in dark_secondary_btn_section
    assert "var(--workspace-shell-text-soft)" in dark_secondary_btn_section
