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

    assert 'id="apps-tabs-bar" class="apps-tabs-bar workspace-chrome-bar workspace-pillbar"' in html
    assert 'class="settings-chrome workspace-chrome-bar"' in html
    assert 'class="settings-toolbar workspace-chrome-row"' in html
    assert 'class="settings-tabbar workspace-pillbar"' in html
    assert 'class="settings-tab-btn workspace-pill-btn is-active"' in html
    assert 'class="btn workspace-action-chip"' in html
    assert 'class="chat-card-head workspace-chrome-bar"' in html
    assert 'class="games-toolbar workspace-chrome-bar"' in html
    assert 'class="games-tab-btn workspace-pill-btn is-active"' in html
    assert "<h2>Files</h2>" not in html
    assert 'id="network-map-chrome" class="network-map-chrome"' in html
    assert 'class="network-map-subview-tabs"' in html

    assert ".workspace-chrome-bar {" in css
    assert ".workspace-pillbar {" in css
    assert ".workspace-chrome-row {" in css
    assert ".network-map-subview-tab,\n    .workspace-pill-btn {" in css
    assert ".workspace-action-chip {" in css
    assert ".settings-chrome {" in css
    assert ".chat-card-head.workspace-chrome-bar {" in css
    assert "[data-theme=\"dark\"] .settings-chrome.workspace-chrome-bar," in css
    assert "[data-theme=\"dark\"] .network-map-subview-tab,\n    [data-theme=\"dark\"] .workspace-pill-btn {" in css


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


def test_network_subviews_follow_workspace_theme_tokens() -> None:
    css = build_dashboard_css(theme_css="")

    overview_panel_section = css.split("[data-theme=\"dark\"] .network-overview-panel {", 1)[1].split("}", 1)[0]
    overview_control_section = css.split("[data-theme=\"dark\"] .network-overview-panel .history-metric-wrap {", 1)[1].split("}", 1)[0]
    overview_chart_section = css.split("[data-theme=\"dark\"] .network-overview-panel #network-overview-chart-wrap {", 1)[1].split("}", 1)[0]
    overview_stat_section = css.split("[data-theme=\"dark\"] .network-overview-panel .overview-item {", 1)[1].split("}", 1)[0]
    sensors_control_section = css.split("[data-theme=\"dark\"] .network-sensors-panel .env-metrics-control-group {", 1)[1].split("}", 1)[0]
    sensors_chart_section = css.split("[data-theme=\"dark\"] .network-sensors-panel #env-metrics-chart-wrap {", 1)[1].split("}", 1)[0]
    diagnostics_pane_section = css.split("[data-theme=\"dark\"] .network-diagnostics-pane {", 1)[1].split("}", 1)[0]
    diagnostics_sender_section = css.split("[data-theme=\"dark\"] .network-diagnostics-sender {", 1)[1].split("}", 1)[0]
    diagnostics_entry_section = css.split("[data-theme=\"dark\"] .network-diagnostics-entry {", 1)[1].split("}", 1)[0]
    diagnostics_payload_section = css.split("[data-theme=\"dark\"] .network-diagnostics-entry-payload {", 1)[1].split("}", 1)[0]
    graph_chip_section = css.split("[data-theme=\"dark\"] .network-graph-chip {", 1)[1].split("}", 1)[0]
    graph_stage_section = css.split("[data-theme=\"dark\"] .network-graph-stage {", 1)[1].split("}", 1)[0]
    graph_edge_section = css.split("[data-theme=\"dark\"] .network-graph-edge {", 1)[1].split("}", 1)[0]
    graph_root_section = css.split("[data-theme=\"dark\"] .network-graph-node.is-root .network-graph-node-core {", 1)[1].split("}", 1)[0]

    assert "var(--workspace-shell-bg-alt)" in overview_panel_section
    assert "var(--workspace-shell-active-bg)" in overview_panel_section
    assert "var(--workspace-shell-border-muted)" in overview_control_section
    assert "var(--workspace-shell-active-bg)" in overview_control_section
    assert "var(--workspace-shell-border)" in overview_chart_section
    assert "var(--workspace-shell-bg-alt)" in overview_chart_section
    assert "var(--workspace-shell-active-bg)" in overview_stat_section
    assert "var(--workspace-shell-border-muted)" in sensors_control_section
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


def test_dark_text_input_variants_share_workspace_shell_tokens() -> None:
    css = build_dashboard_css(theme_css="")

    search_input_section = css.split("[data-theme=\"dark\"] .list-search-input,", 1)[1].split("}", 1)[0]
    shared_text_inputs_section = css.split("[data-theme=\"dark\"] .chat-peer-input,", 1)[1].split("}", 1)[0]
    shared_focus_section = css.split("[data-theme=\"dark\"] .chat-peer-input:focus,", 1)[1].split("}", 1)[0]

    assert "var(--workspace-shell-border-strong)" in search_input_section
    assert "var(--workspace-shell-text)" in search_input_section
    assert "[data-theme=\"dark\"] .settings-textarea," in css
    assert "[data-theme=\"dark\"] .chat-input," in css
    assert "var(--workspace-shell-border)" in shared_text_inputs_section
    assert "var(--workspace-shell-text)" in shared_text_inputs_section
    assert "var(--workspace-shell-border-strong)" in shared_focus_section
    assert "var(--workspace-shell-hover-bg)" in shared_focus_section
    assert "[data-theme=\"dark\"] .settings-textarea::placeholder," in css
    assert "[data-theme=\"dark\"] .bbs-post-input::placeholder {" in css
    assert "opacity: 0.9;" in css


def test_games_boards_follow_runtime_theme_tokens() -> None:
    css = build_dashboard_css(theme_css="")

    board_wrap_section = css.split(".games-board-wrap {", 1)[1].split("}", 1)[0]
    reversi_board_section = css.split(".reversi-board {", 1)[1].split("}", 1)[0]
    reversi_cell_section = css.split(".reversi-cell {", 1)[1].split("}", 1)[0]
    classic_board_section = css.split(".checkers-board,\n    .chess-board {", 1)[1].split("}", 1)[0]
    dark_board_wrap_section = css.split("[data-theme=\"dark\"] .games-board-wrap {", 1)[1].split("}", 1)[0]
    dark_reversi_board_section = css.split("[data-theme=\"dark\"] .reversi-board {", 1)[1].split("}", 1)[0]
    dark_classic_board_section = css.split("[data-theme=\"dark\"] .checkers-board,\n    [data-theme=\"dark\"] .chess-board {", 1)[1].split("}", 1)[0]

    assert "var(--ui-accent-soft, var(--accent, #2f855a))" in board_wrap_section
    assert "var(--games-board-frame)" in board_wrap_section
    assert "var(--reversi-board-accent)" in reversi_board_section
    assert "var(--reversi-board-cell)" in reversi_cell_section
    assert "var(--classic-board-accent)" in classic_board_section
    assert "var(--workspace-shell-bg-alt)" in dark_board_wrap_section
    assert "var(--workspace-shell-border)" in dark_board_wrap_section
    assert "var(--ui-accent)" in dark_reversi_board_section
    assert "var(--workspace-shell-bg)" in dark_classic_board_section
    assert "#173526" not in dark_board_wrap_section
    assert "#113a2b" not in dark_reversi_board_section


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


def test_history_charts_pull_runtime_theme_vars() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "function historyChartThemeColor(name, fallback)" in js
    assert 'historyChartThemeColor("--workspace-shell-border-muted"' in js
    assert 'historyChartThemeColor("--ui-accent"' in js
    assert 'historyChartThemeColor("--workspace-shell-active-text"' in js
    assert 'historyChartThemeColor("--workspace-shell-text-soft"' in js


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
    neutral_section = css.split("[data-theme=\"dark\"] .topbar .summary-ticker-item.metric-state-neutral {", 1)[1].split("}", 1)[0]
    bad_section = css.split("[data-theme=\"dark\"] .topbar .summary-ticker-item.metric-state-bad {", 1)[1].split("}", 1)[0]
    chart_section = css.split("[data-theme=\"dark\"] .topbar .summary-ticker-item .metric-ticker-chart path {", 1)[1].split("}", 1)[0]
    target_status_section = css.split("[data-theme=\"dark\"] .topbar .summary-ticker-item .target-radio-status {", 1)[1].split("}", 1)[0]

    assert "var(--workspace-shell-active-bg)" in topbar_section
    assert "var(--workspace-shell-bg-alt)" in topbar_section
    assert "var(--workspace-shell-bg)" in topbar_section
    assert "var(--workspace-shell-border)" in topbar_section
    assert "#121a25" not in topbar_section
    assert "var(--workspace-shell-border)" in ticker_section
    assert "var(--workspace-shell-bg-alt)" in ticker_section
    assert "var(--workspace-shell-bg)" in ticker_section
    assert "var(--workspace-shell-text)" in ticker_section
    assert "var(--workspace-shell-text-soft)" in neutral_section
    assert "#cf6f6f" in bad_section
    assert "var(--ticker-card-accent)" in chart_section
    assert "var(--workspace-shell-border-muted)" in target_status_section
    assert "var(--workspace-shell-text-soft)" in target_status_section


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
    assert "var(--workspace-shell-border-muted)" in launcher_section
    assert "var(--workspace-shell-border-strong)" in launcher_hover_section
    assert "accent-2" not in launcher_section
    assert "var(--workspace-shell-border)" in update_section
    assert "var(--workspace-shell-bg-alt)" in update_section
    assert "var(--workspace-shell-bg)" in update_section
    assert "var(--workspace-shell-text)" in update_section
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
    dark_screen_section = css.split("[data-theme=\"dark\"] .console-terminal-screen {", 1)[1].split("}", 1)[0]
    dark_overlay_section = css.split("[data-theme=\"dark\"] .console-terminal-screen::before {", 1)[1].split("}", 1)[0]
    dark_live_console_section = css.split("[data-theme=\"dark\"] #live-console {", 1)[1].split("}", 1)[0]

    assert ".layout.view-console .console .body {" in css
    assert "background: transparent;" in body_section
    assert "padding: 0;" in body_section
    assert ".console-terminal-screen {" in css
    assert "border: 1px solid #7ab18a;" in css
    assert "border-radius: 8px;" in css
    assert "var(--workspace-shell-border)" in dark_screen_section
    assert "var(--workspace-shell-bg)" in dark_screen_section
    assert "var(--workspace-shell-bg-alt)" in dark_screen_section
    assert "var(--workspace-shell-active-bg)" in dark_screen_section
    assert "var(--workspace-shell-hover-bg)" in dark_screen_section
    assert "rgba(83, 170, 112, 0.09)" not in dark_screen_section
    assert "var(--workspace-shell-border-muted)" in dark_overlay_section
    assert "var(--workspace-shell-text)" in dark_live_console_section
    assert "var(--workspace-shell-active-text)" in dark_live_console_section


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
