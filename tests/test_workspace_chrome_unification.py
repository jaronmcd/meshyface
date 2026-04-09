import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_css import build_dashboard_css
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

    assert "accent-color: var(--accent);" in heatmap_input_section
    assert "var(--accent)" in reset_section
    assert "var(--line)" in zoom_section
    assert "var(--accent)" in tabs_section
    assert "var(--workspace-shell-border)" in dark_heatmap_section
    assert "var(--workspace-shell-bg-alt)" in dark_zoom_section
    assert "var(--workspace-shell-text-soft)" in dark_status_section


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
    assert "#0e1713" not in drawer_section
    assert "#172820" not in tab_section


def test_topbar_tickers_follow_workspace_shell_and_semantic_states() -> None:
    css = build_dashboard_css(theme_css="")

    ticker_section = css.split("[data-theme=\"dark\"] .topbar .summary-ticker-item {", 1)[1].split("}", 1)[0]
    neutral_section = css.split("[data-theme=\"dark\"] .topbar .summary-ticker-item.metric-state-neutral {", 1)[1].split("}", 1)[0]
    bad_section = css.split("[data-theme=\"dark\"] .topbar .summary-ticker-item.metric-state-bad {", 1)[1].split("}", 1)[0]
    chart_section = css.split("[data-theme=\"dark\"] .topbar .summary-ticker-item .metric-ticker-chart path {", 1)[1].split("}", 1)[0]
    target_status_section = css.split("[data-theme=\"dark\"] .topbar .summary-ticker-item .target-radio-status {", 1)[1].split("}", 1)[0]

    assert "var(--workspace-shell-border)" in ticker_section
    assert "var(--workspace-shell-bg-alt)" in ticker_section
    assert "var(--workspace-shell-bg)" in ticker_section
    assert "var(--workspace-shell-text)" in ticker_section
    assert "var(--workspace-shell-text-soft)" in neutral_section
    assert "#cf6f6f" in bad_section
    assert "var(--ticker-card-accent)" in chart_section
    assert "var(--workspace-shell-border-muted)" in target_status_section
    assert "var(--workspace-shell-text-soft)" in target_status_section


def test_console_view_removes_body_shell_and_keeps_terminal_frame() -> None:
    css = build_dashboard_css(theme_css="")
    body_section = css.split(".layout.view-console .console .body {", 1)[1].split("}", 1)[0]

    assert ".layout.view-console .console .body {" in css
    assert "background: transparent;" in body_section
    assert "padding: 0;" in body_section
    assert ".console-terminal-screen {" in css
    assert "border: 1px solid #7ab18a;" in css
    assert "border-radius: 8px;" in css


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
