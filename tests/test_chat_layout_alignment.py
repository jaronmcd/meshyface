import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_css import build_dashboard_css
from meshdash.html_js import build_dashboard_js
from meshdash.html_sections import build_html_shell


def test_chat_layout_spacing_matches_tighter_network_style() -> None:
    css = build_dashboard_css(theme_css="")
    chat_channel_wrap_section = css.split(
        ".layout.view-chat .chat-card-head .chat-mesh-channel-wrap {",
        1,
    )[1].split("}", 1)[0]
    chat_channel_strip_section = css.split(
        ".layout.view-chat .chat-card-head .mesh-channel-pill-strip {",
        1,
    )[1].split("}", 1)[0]

    assert ".workspace-main > .layout.view-chat," in css
    assert ".workspace-main > .layout.view-console {" in css
    assert "grid-row: 1 / -1;" in css
    assert ".chat-left-head-shell {" in css
    assert "border: 1px solid color-mix(in srgb, var(--line) 88%, var(--ink) 12%);" in css
    assert "background: color-mix(in srgb, var(--panel) 78%, var(--bg) 22%);" in css
    assert ".chat-left-roster-shell {" in css
    assert "border: 1px solid color-mix(in srgb, var(--line) 88%, var(--ink) 12%);" in css
    assert "background: color-mix(in srgb, var(--panel) 92%, var(--bg) 8%);" in css
    assert ".layout.view-chat .chat {" in css
    assert "background: transparent;" in css
    assert "border: 0;" in css
    assert "box-shadow: none;" in css
    assert "overflow: visible;" in css
    assert "gap: 8px;" in css
    assert ".chat-left-panel {" in css
    assert "border: 0;" in css
    assert "background: transparent;" in css
    assert "box-shadow: none;" in css
    assert ".chat-left-section.chat-users-section {" in css
    assert "gap: 0;" in css
    assert ".workspace-shell[data-layout-view=\"chat\"] .chat-left-head-shell {" in css
    assert "padding: 8px 10px;" in css
    assert ".chat-users-head {" in css
    assert "padding: 0;" in css
    assert "background: transparent;" in css
    assert ".workspace-shell[data-layout-view=\"chat\"] .chat-users-head {" in css
    assert "border-radius: 0;" in css
    assert "min-height: 27px;" in css
    assert ".chat-users-head-theme-btn {" in css
    assert ".chat-users-head-launcher-shell {" in css
    assert ".workspace-shell[data-layout-view=\"chat\"] .chat-users-head-launcher-shell {" in css
    assert ".workspace-shell[data-layout-view=\"chat\"] .chat-users-head-launcher-shell .topbar-view-menu-btn {" in css
    assert ".workspace-shell[data-layout-view=\"chat\"] .chat-users-head-launcher-shell .topbar-view-menu-btn:hover," in css
    assert ".workspace-shell[data-layout-view=\"chat\"] .chat-users-head-action-btn {" in css
    assert ".chat-left-panel .chat-member-list {" in css
    assert "background: transparent;" in css
    assert ".layout.view-chat .chat .body {" in css
    assert "padding: 0;" in css
    assert ".layout.view-chat .chat-shell {" in css
    assert "padding: 0;" in css
    assert "margin-top: 8px;" in css
    assert ".layout.view-chat .chat-compose-notices:not([hidden]) + .chat-shell {" in css
    assert "margin-top: 0;" in css
    assert ".layout.view-chat .chat-compose-notices {" in css
    assert "padding: 0 0 6px 0;" in css
    assert ".layout.view-chat .chat-main-pane {" in css
    assert "row-gap: 8px;" in css
    assert ".layout.view-chat .chat-log-scroll {" in css
    assert "border: 1px solid color-mix(in srgb, var(--line) 88%, var(--ink) 12%);" in css
    assert "border-radius: 10px;" in css
    assert "background: color-mix(in srgb, var(--panel) 92%, var(--bg) 8%);" in css
    assert ".layout.view-chat .chat-card-head.workspace-chrome-bar {" in css
    assert "margin: 0;" in css
    assert "padding: 8px 10px;" in css
    assert "box-shadow: none;" in css
    assert ".layout.view-chat .chat-card-head.workspace-chrome-bar .chat-card-head-controls {" in css
    assert ".layout.view-chat .chat-card-head.workspace-chrome-bar .workspace-chrome-row {" in css
    assert ".layout.view-chat .chat-card-head .chat-card-head-actions {" in css
    assert "--chat-header-compose-trailing-space: 99px;" in css
    assert "padding-right: var(--chat-header-compose-trailing-space);" in css
    assert ".layout.view-chat .chat-card-head .chat-card-head-actions::before {" in css
    assert ".layout.view-chat .chat-card-head .chat-mesh-channel-wrap {" in css
    assert "flex: 0 1 auto;" in chat_channel_wrap_section
    assert "min-height: 27px;" in chat_channel_wrap_section
    assert "border: 0;" in chat_channel_wrap_section
    assert "background: transparent;" in chat_channel_wrap_section
    assert "padding: 0;" in chat_channel_wrap_section
    assert ".layout.view-chat .chat-card-head .mesh-channel-pill-strip {" in css
    assert "flex: 0 1 auto;" in chat_channel_strip_section
    assert "width: auto;" in chat_channel_strip_section
    assert "min-height: 27px;" in chat_channel_strip_section
    assert "justify-content: flex-start;" in chat_channel_strip_section
    assert "flex-wrap: nowrap;" in css
    assert ".layout.view-chat .chat-card-head .mesh-channel-pill {" in css
    assert ".layout.view-chat .chat-card-head .mesh-channel-pill:hover," in css
    assert ".layout.view-chat .chat-compose-shell {" in css
    assert "margin-top: 0;" in css
    assert "border: 1px solid color-mix(in srgb, var(--line) 88%, var(--ink) 12%);" in css
    assert "border-radius: 10px;" in css
    assert "background: color-mix(in srgb, var(--panel) 78%, var(--bg) 22%);" in css
    assert "padding: 6px 8px;" in css
    assert "gap: 0;" in css
    assert ".chat-left-bottom-bar {" in css
    assert "margin: 0;" in css
    assert "border: 1px solid color-mix(in srgb, var(--line) 88%, var(--ink) 12%);" in css
    assert "background: color-mix(in srgb, var(--panel) 78%, var(--bg) 22%);" in css
    assert "position: relative;" in css
    assert "display: flex;" in css
    assert ".chat-user-search-wrap {" in css
    assert "flex: 1 1 auto;" in css
    assert ".chat-node-navigator-dock-btn {" in css
    assert ".chat-node-navigator-menu-docked {" in css
    assert "bottom: calc(100% + 6px);" in css
    assert ".chat-member-list {" in css
    assert "gap: 0;" in css
    assert ".chat-member-item {" in css
    assert "--chat-member-node-bg: color-mix(in srgb, var(--panel) 94%, var(--bg) 6%);" in css
    assert "--chat-member-node-sat-mult: 0;" in css
    assert "border-radius: 0;" in css
    assert "border-bottom: 1px solid var(--chat-member-node-border);" in css
    assert "[data-theme=\"dark\"] .chat-left-panel," in css


def test_light_mode_chat_channel_controls_keep_dark_text_on_light_shells() -> None:
    css = build_dashboard_css(theme_css="")

    compose_shell_section = css.rsplit("\n    .chat-compose-shell {", 1)[1].split("}", 1)[0]
    tinted_compose_shell_section = css.split(".chat-compose-shell.channel-tinted,\n    .layout.view-chat .chat-compose-shell.channel-tinted {", 1)[1].split("}", 1)[0]
    chat_input_section = css.rsplit("\n    #chat-input {", 1)[1].split("}", 1)[0]
    chat_input_hover_section = css.rsplit("\n    #chat-input:hover {", 1)[1].split("}", 1)[0]
    channel_wrap_section = css.split(".mesh-channel-wrap {", 1)[1].split("}", 1)[0]
    channel_pill_section = css.split(".mesh-channel-pill {", 1)[1].split("}", 1)[0]
    channel_badge_section = css.split(".mesh-channel-primary-badge {", 1)[1].split("}", 1)[0]
    channel_unread_section = css.split(".mesh-channel-pill-unread {", 1)[1].split("}", 1)[0]
    channel_menu_btn_section = css.split(".mesh-channel-menu-btn {", 1)[1].split("}", 1)[0]
    dark_channel_badge_section = css.rsplit("[data-theme=\"dark\"] .mesh-channel-primary-badge {", 1)[1].split("}", 1)[0]
    dark_channel_badge_active_section = css.split("[data-theme=\"dark\"] .mesh-channel-pill:hover .mesh-channel-primary-badge,\n    [data-theme=\"dark\"] .mesh-channel-pill.active .mesh-channel-primary-badge,\n    [data-theme=\"dark\"] .mesh-channel-menu-btn:hover .mesh-channel-primary-badge,\n    [data-theme=\"dark\"] .mesh-channel-menu-btn[aria-expanded=\"true\"] .mesh-channel-primary-badge {", 1)[1].split("}", 1)[0]
    dark_input_section = css.rsplit("[data-theme=\"dark\"] .list-search-input,\n    [data-theme=\"dark\"] #chat-input,\n    [data-theme=\"dark\"] .chat-send-channel-select {", 1)[1].split("}", 1)[0]
    dark_chat_input_section = css.rsplit("[data-theme=\"dark\"] #chat-input {", 1)[1].split("}", 1)[0]
    dark_chat_input_hover_section = css.rsplit("[data-theme=\"dark\"] #chat-input:hover {", 1)[1].split("}", 1)[0]
    dark_chat_input_focus_section = css.rsplit("[data-theme=\"dark\"] #chat-input:focus {", 1)[1].split("}", 1)[0]
    dark_bottom_bar_section = css.rsplit("[data-theme=\"dark\"] .chat-left-bottom-bar {", 1)[1].split("}", 1)[0]
    dark_send_btn_section = css.split("[data-theme=\"dark\"] #chat-emoji-btn,\n    [data-theme=\"dark\"] #chat-send-btn {", 1)[1].split("}", 1)[0]

    assert "border: 1px solid color-mix(in srgb, var(--line) 88%, var(--ink) 12%);" in compose_shell_section
    assert "background: color-mix(in srgb, var(--panel) 78%, var(--bg) 22%);" in compose_shell_section
    assert "box-shadow: none;" in compose_shell_section
    assert "border-radius: 10px;" in compose_shell_section
    assert "padding: 6px 8px;" in compose_shell_section
    assert "gap: 0;" in compose_shell_section
    assert "border-color: rgba(var(--chat-send-channel-rgb), 0.34);" in tinted_compose_shell_section
    assert "rgba(var(--chat-send-channel-rgb), 0.06)" in tinted_compose_shell_section
    assert "box-shadow: inset 0 0 0 1px rgba(var(--chat-send-channel-rgb), 0.06);" in tinted_compose_shell_section
    assert "color-mix(in srgb, var(--ink) 88%, var(--accent-2) 12%)" in channel_wrap_section
    assert "#f2fff7" not in channel_wrap_section
    assert "color-mix(in srgb, var(--ink) 88%, var(--accent-2) 12%)" in channel_pill_section
    assert "#f2fff7" not in channel_pill_section
    assert "color-mix(in srgb, var(--ink) 78%, var(--accent-2) 22%)" in channel_badge_section
    assert "rgba(242, 255, 247, 0.88)" not in channel_badge_section
    assert "color-mix(in srgb, var(--muted) 82%, var(--accent-2) 18%)" in channel_unread_section
    assert "rgba(242, 255, 247, 0.88)" not in channel_unread_section
    assert "color-mix(in srgb, var(--ink) 88%, var(--accent-2) 12%)" in channel_menu_btn_section
    assert "#f2fff7" not in channel_menu_btn_section
    assert "[data-theme=\"dark\"] .card.chat .body," in css
    assert "[data-theme=\"dark\"] .card.chat .chat-shell {" in css
    assert "[data-theme=\"dark\"] .chat-left-bottom-bar {" in css
    assert "var(--workspace-shell-border-muted)" in dark_channel_badge_section
    assert "var(--workspace-shell-active-bg)" in dark_channel_badge_section
    assert "var(--workspace-shell-text-soft)" in dark_channel_badge_section
    assert "var(--workspace-shell-active-text)" in dark_channel_badge_active_section
    assert "background: var(--ui-panel) !important;" in dark_bottom_bar_section
    assert "var(--ui-border)" in dark_bottom_bar_section
    assert "[data-theme=\"dark\"] #chat-emoji-btn," in css
    assert "[data-theme=\"dark\"] #chat-send-btn {" in css
    assert "background: var(--ui-panel);" in dark_input_section
    assert "border-color: var(--ui-border);" in dark_input_section
    assert "border-color: #c2d8c7;" in chat_input_section
    assert "background: #f9fdf9;" in chat_input_section
    assert "rgba(var(--chat-send-channel-rgb)" not in chat_input_section
    assert "border-color: #b7cfbe;" in chat_input_hover_section
    assert "background: #fbfefb;" in chat_input_hover_section
    assert "rgba(var(--chat-send-channel-rgb)" not in chat_input_hover_section
    assert "border-color: var(--ui-border);" in dark_chat_input_section
    assert "background: var(--ui-panel);" in dark_chat_input_section
    assert "rgba(var(--chat-send-channel-rgb)" not in dark_chat_input_section
    assert "color-mix(in srgb, var(--ui-border) 72%, var(--ui-text) 28%)" in dark_chat_input_hover_section
    assert "background: var(--ui-panel-alt);" in dark_chat_input_hover_section
    assert "color-mix(in srgb, var(--ui-accent) 34%, transparent)" in dark_chat_input_focus_section
    assert "border-color: var(--ui-accent);" in dark_chat_input_focus_section
    assert "background: var(--ui-panel-alt);" in dark_chat_input_focus_section
    assert "background: var(--ui-panel) !important;" in dark_send_btn_section
    assert "border-color: var(--ui-border) !important;" in dark_send_btn_section
    assert "color: var(--ui-text) !important;" in dark_send_btn_section
    assert "var(--workspace-shell-border)" not in dark_send_btn_section
    assert ".list-search-input,\n    #chat-input {" in css
    assert "#chat-input:hover {" in css
    assert "[data-theme=\"dark\"] #chat-input:hover {" in css
    assert "[data-theme=\"dark\"] #chat-input:focus {" in css


def test_chat_left_column_uses_distinct_head_and_roster_shells() -> None:
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

    assert 'class="chat-left-head-shell"' in html
    assert 'class="chat-left-section chat-users-section chat-left-roster-shell"' in html
    assert 'id="theme-toggle-inline-btn"' in html
    assert 'class="workspace-launcher-shell chat-users-head-launcher-shell"' in html
    assert 'id="chat-node-navigator-menu-btn"' in html
    assert 'class="chat-node-navigator-menu chat-node-navigator-menu-docked"' in html


def test_chat_compose_notices_float_above_composer_shell() -> None:
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

    assert '<div id="chat-compose-notices" class="chat-compose-notices" hidden>' in html
    assert 'id="chat-channel-mismatch-warning"' in html
    assert 'id="chat-send-status"' in html
    assert 'class="chat-notice-viewport"' in html
    assert 'class="chat-notice-track"' in html
    assert 'class="chat-notice-item chat-notice-item-primary"' in html
    assert 'class="chat-notice-item chat-notice-item-secondary"' in html
    assert ".chat-compose-shell {" in css
    assert ".chat-compose-notices {" in css
    assert "padding: 6px 10px 0 10px;" in css
    assert ".chat-notice-track {" in css
    assert "animation: chatNoticeTickerScroll" in css
    assert "@keyframes chatNoticeTickerScroll {" in css


def test_dark_chat_palette_matches_green_workspace_theme() -> None:
    css = build_dashboard_css(theme_css="")

    assert "[data-theme=\"dark\"] .card.chat .chat-card-head {" in css
    assert "background: #0d1711;" in css
    assert "[data-theme=\"dark\"] .layout.view-chat .card.chat {" in css
    assert "border-color: transparent;" in css
    assert "[data-theme=\"dark\"] .chat-left-panel {" in css
    assert "border-color: transparent !important;" in css
    assert "[data-theme=\"dark\"] .chat-left-head-shell {" in css
    assert "[data-theme=\"dark\"] .chat-left-roster-shell {" in css
    assert "[data-theme=\"dark\"] .card.chat .body {" in css
    assert "[data-theme=\"dark\"] .card.chat .chat-shell {" in css
    assert "background: #08120d;" in css
    assert "background: #08120d !important;" in css
    assert "[data-theme=\"dark\"] .layout.view-chat .card.chat .body," in css
    assert "[data-theme=\"dark\"] .layout.view-chat .card.chat .chat-shell {" in css
    assert "background: transparent !important;" in css
    assert "[data-theme=\"dark\"] .layout.view-chat .card.chat .chat-card-head.workspace-chrome-bar {" in css
    assert "background: var(--workspace-shell-bg-alt);" in css
    assert "box-shadow: none;" in css
    assert "[data-theme=\"dark\"] .layout.view-chat .chat-card-head .chat-card-head-actions::before," in css
    assert "[data-theme=\"dark\"] .layout.view-chat .chat-card-head .chat-mesh-channel-wrap {" in css
    assert "[data-theme=\"dark\"] .workspace-shell[data-layout-view=\"chat\"] .chat-users-head-launcher-shell .topbar-view-menu-btn:hover," in css
    assert "[data-theme=\"dark\"] .layout.view-chat .chat-card-head .mesh-channel-pill:hover," in css
    assert "[data-theme=\"dark\"] .layout.view-chat .card.chat .chat-log-scroll {" in css
    assert "background: var(--workspace-shell-bg);" in css
    assert "border-color: var(--workspace-shell-border);" in css
    dark_compose_shell_section = css.rsplit("[data-theme=\"dark\"] .layout.view-chat .card.chat .chat-compose-shell {", 1)[1].split("}", 1)[0]
    dark_tinted_compose_shell_section = css.split("[data-theme=\"dark\"] .chat-compose-shell.channel-tinted,\n    [data-theme=\"dark\"] .card.chat .chat-compose-shell.channel-tinted,\n    [data-theme=\"dark\"] .layout.view-chat .card.chat .chat-compose-shell.channel-tinted {", 1)[1].split("}", 1)[0]
    dark_bottom_bar_section = css.rsplit("[data-theme=\"dark\"] .chat-left-bottom-bar {", 1)[1].split("}", 1)[0]
    assert "[data-theme=\"dark\"] .layout.view-chat .card.chat .chat-compose-shell {" in css
    assert "background: var(--ui-panel);" in dark_compose_shell_section
    assert "background-image: none;" in dark_compose_shell_section
    assert "color-mix(in srgb, var(--ui-border) 62%, transparent)" in dark_compose_shell_section
    assert "rgba(var(--chat-send-channel-rgb), 0.1)" in dark_tinted_compose_shell_section
    assert "rgba(16, 26, 36, 0.99) 34%" in dark_tinted_compose_shell_section
    assert "border-color: rgba(var(--chat-send-channel-rgb), 0.38) !important;" in dark_tinted_compose_shell_section
    assert "box-shadow: inset 0 0 0 1px rgba(var(--chat-send-channel-rgb), 0.08);" in dark_tinted_compose_shell_section
    assert "var(--workspace-shell-border)" not in dark_tinted_compose_shell_section
    assert "[data-theme=\"dark\"] .chat-left-bottom-bar {" in css
    assert "background: var(--ui-panel) !important;" in dark_bottom_bar_section
    assert "var(--ui-border)" in dark_bottom_bar_section
    assert "[data-theme=\"dark\"] .chat-panel-splitter {" in css
    assert "[data-theme=\"dark\"] .chat-member-pane {" in css
    assert "[data-theme=\"dark\"] .card.chat .chat-feed-item {" in css
    assert "--chat-feed-node-hue: 148;" in css
    assert "--chat-feed-node-tint-end-hue: 170;" in css
    assert "--chat-feed-node-outline-hue: 154;" in css
    assert "--chat-feed-node-dark-sat-mult: 0;" in css
    assert "--chat-feed-node-gradient: linear-gradient(" in css
    assert "hsl(var(--chat-feed-node-tint-start-hue, 148) calc(34% * var(--chat-feed-node-dark-sat-mult, 1))" in css
    assert "[data-theme=\"dark\"] .chat-feed-item.kind-status {" in css
    assert "rgba(44, 82, 60, 0.58)" in css
    assert "[data-theme=\"dark\"] .card.chat .chat-reaction-chip," in css
    assert "background: #173126;" in css
    assert "[data-theme=\"dark\"] .chat-node-navigator-menu," in css
    assert "background: #0d1711;" in css
    assert "[data-theme=\"dark\"] .chat-member-item {" in css
    assert "--chat-member-node-dark-sat-mult: 0;" in css
    assert "--chat-member-node-outline-dark-sat-mult: 0;" in css
    assert "calc(44% * var(--chat-member-node-dark-sat-mult, 1))" in css
    assert "calc(18% * var(--chat-member-node-dark-sat-mult, 1))" in css
    assert "color: var(--ui-text);" in css
    assert "[data-theme=\"dark\"] .chat-member-item:hover {" in css
    assert "color-mix(in srgb, var(--chat-member-node-outline) 88%, var(--ui-accent) 12%)" in css
    assert "color-mix(in srgb, var(--workspace-shell-border-strong) 68%, var(--ui-accent) 32%)" in css
    assert "[data-theme=\"dark\"] .chat-member-item.selected-node {" in css
    assert "hsl(var(--chat-member-node-outline-hue, 154) calc(30% * var(--chat-member-node-outline-dark-sat-mult, 1.1))" in css
    assert "hsl(var(--chat-member-node-hue, 145) calc(44% * var(--chat-member-node-dark-sat-mult, 1))" in css


def test_chat_compose_controls_order_matches_current_layout() -> None:
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

    channel_idx = html.index('id="chat-send-channel-menu-btn"')
    input_idx = html.index('id="chat-input"')
    send_idx = html.index('id="chat-send-btn"')
    emoji_idx = html.index('id="chat-emoji-btn"')

    assert channel_idx < input_idx < send_idx < emoji_idx


def test_chat_ui_flags_nodes_with_malformed_text_payloads() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    css = build_dashboard_css(theme_css="")

    assert "function malformedTextPayloadRecord(packetEntry) {" in js
    assert "function mapMalformedTextPayloadByNode(recentPackets) {" in js
    assert "Malformed text payloads detected:" in js
    assert "Malformed Text Packets" in js
    assert ".chat-member-alert-chip {" in css
    assert "[data-theme=\"dark\"] .chat-member-alert-chip {" in css


def test_chat_send_channel_compact_dot_trigger_geometry() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    css = build_dashboard_css(theme_css="")

    assert ".chat-composer-input-row {" in css
    assert "gap: 6px;" in css
    assert ".chat-send-channel-wrap {" in css
    assert "flex: 0 0 27px;" in css
    assert "min-width: 27px;" in css
    assert "max-width: 27px;" in css
    assert "border-radius: 999px;" in css
    assert ".chat-send-channel-menu-btn {" in css
    assert "position: absolute;" in css
    assert "inset: 0;" in css
    assert ".chat-send-channel-dot {" in css
    assert "pointer-events: none;" in css
    assert 'const chatComposerTinted = !meshChannelIsPrimary(activeMeshSendChannelIndex);' in js
    assert 'composeShell.classList.toggle("channel-tinted", chatComposerTinted);' in js


def test_chat_send_status_reuses_input_placeholder_instead_of_notice_row() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "let chatInputPlaceholderStatusText = \"\";" in js
    assert "function clearChatInputPlaceholderStatus(expectedToken = \"\") {" in js
    assert "function setChatInputPlaceholderStatus(message, options = null) {" in js
    assert 'input.placeholder = chatInputPlaceholderStatusText;' in js
    assert 'input.title = chatInputPlaceholderStatusFullText || chatInputPlaceholderStatusText;' in js
    assert 'setChatNoticeTickerText("chat-send-status", "", false);' in js
    assert 'setChatInputPlaceholderStatus(message, {' in js
    assert "ttlMs: isError ? 9000 : 7000," in js
    assert "clearChatInputPlaceholderStatus(token);" in js


def test_chat_text_renderer_wraps_inline_emoji_for_subtle_feed_contrast() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    css = build_dashboard_css(theme_css="")

    assert "const chatEmojiSegmenter = (" in js
    assert "const chatInlineEmojiTokenRe =" in js
    assert "function chatIsEmojiOnlyText(textValue) {" in js
    assert "function chatEscapeTextWithBreaksAndEmoji(textValue) {" in js
    assert 'parts.push(`<span class="chat-inline-emoji">${escaped}</span>`);' in js
    assert "chat-feed-text-emoji-only" in js
    assert ".chat-inline-emoji {" in css
    assert ".chat-inline-emoji::before {" in css
    assert ".chat-feed-text-inline.chat-feed-text-emoji-only {" in css
    assert "font-size: 1.72em;" in css
    assert "drop-shadow(0 0 6px rgba(255, 214, 94, 0.38))" in css
    assert "[data-theme=\"dark\"] .chat-inline-emoji {" in css


def test_chat_feed_author_names_do_not_encode_status_color() -> None:
    feed_src = Path("meshdash/assets/dashboard.js.chat.render.feed_items.tmpl").read_text()
    css = build_dashboard_css(theme_css="")

    assert '<span class="chat-name">${{escAttr(fromMeta.label)}}</span>' in feed_src
    assert 'status-${{fromMeta.status}}' not in feed_src
    assert ".chat-feed-author .chat-name {" in css
    assert "color: #2f4b3a;" in css


def test_chat_node_search_syncs_to_live_navigator_row_bounds() -> None:
    js_src = Path("meshdash/assets/dashboard.js.chat.state.messaging.peers.tmpl").read_text()

    assert "function syncChatNodeNavigatorSearchBounds() {" in js_src
    assert 'document.querySelector(".chat-left-bottom-bar")' in js_src
    assert 'document.getElementById("chat-room-unread-list")' in js_src
    assert 'document.getElementById("chat-room-pinned-list")' in js_src
    assert 'unreadList.querySelector(".chat-member-item, .chat-member-empty")' in js_src
    assert 'pinnedList.querySelector(".chat-member-item, .chat-member-empty")' in js_src
    assert 'roomList.querySelector(".chat-member-item, .chat-member-empty")' in js_src
    assert 'bottomBar.style.setProperty("--chat-user-search-inline-start",' in js_src
    assert 'bottomBar.style.setProperty("--chat-user-search-inline-end",' in js_src
    assert 'window.addEventListener("resize", scheduleChatNodeNavigatorSearchBoundsSync);' in js_src


def test_chat_unread_node_click_routes_into_messages_tab(assert_tokens_present) -> None:
    peers_src = Path("meshdash/assets/dashboard.js.chat.state.messaging.peers.tmpl").read_text()

    assert_tokens_present(peers_src, [
        'const unreadDirectCount = Math.max(0, Math.trunc(Number(member.dataset.unreadDirectCount) || 0));',
        'const graphOpen = activeLayoutView === "network" && activeNetworkSubview === "graph";',
        'selectNode(nodeId, true, !graphOpen && unreadDirectCount <= 0);',
        'if (unreadDirectCount > 0 && typeof setChatNodeDetailsDrawerTab === "function") {',
        'setChatNodeDetailsDrawerTab("messages", {',
        'fetchHistory: false,',
        'data-unread-direct-count="${{escAttr(unreadDirectCount)}}"',
    ])


def test_chat_click_selection_keeps_same_node_selected(assert_tokens_present) -> None:
    bindings_src = Path("meshdash/assets/dashboard.js.chat.events.bindings.tmpl").read_text()
    peers_src = Path("meshdash/assets/dashboard.js.chat.state.messaging.peers.tmpl").read_text()
    selection_src = Path("meshdash/assets/dashboard.js.chat.events.map_selection.tmpl").read_text()

    assert 'selectNode(nodeId, true, false);' in bindings_src
    assert "function chatFeedSelectionKeyForItem(item) {" in bindings_src
    assert "const sameExactChat = (" in bindings_src
    assert "clearNodeSelection();" in bindings_src
    assert "chatFeedRepeatToggleMessageKey = messageSelectionKey;" in bindings_src
    assert_tokens_present(peers_src, [
        'if (!isSelectableNodeId(nodeId)) {{',
        'selectNode(nodeId, true, !graphOpen);',
        'return;',
        'selectNode(nodeId, true, !graphOpen && unreadDirectCount <= 0);',
        'if (unreadDirectCount > 0 && typeof setChatNodeDetailsDrawerTab === "function") {{',
        'setChatNodeDetailsDrawerTab("messages", {{',
        'fetchHistory: false,',
    ])
    assert 'if (!chatFeedSelectionSyncInProgress && typeof clearChatFeedRepeatToggleState === "function") {' in selection_src
    assert 'if (typeof clearChatFeedRepeatToggleState === "function") {' in selection_src


def test_chat_node_list_uses_same_tint_seed_family_as_feed() -> None:
    peers_src = Path("meshdash/assets/dashboard.js.chat.state.messaging.peers.tmpl").read_text()
    feed_src = Path("meshdash/assets/dashboard.js.chat.render.feed_items.tmpl").read_text()

    assert "const tintSeedNode = (" in peers_src
    assert 'nodesById.get(normalizeNodeId(nodeId))' in peers_src
    assert 'const autoNodeHue = (typeof nodeTintHue === "function") ? nodeTintHue(nodeId, 210) : 210;' in peers_src
    assert "fallbackHue: 210," in peers_src
    assert 'const autoNodeTintHue = (typeof nodeTintHue === "function")' in feed_src
    assert '? nodeTintHue(tintNodeId, 210)' in feed_src
    assert "fallbackHue: 210," in feed_src


def test_chat_reaction_anchor_reuses_same_button_for_more_and_less_states() -> None:
    emoji_src = Path("meshdash/assets/dashboard.js.chat.state.messaging.emoji_ui.tmpl").read_text()
    bindings_src = Path("meshdash/assets/dashboard.js.chat.events.bindings.tmpl").read_text()
    feed_src = Path("meshdash/assets/dashboard.js.chat.render.feed_items.tmpl").read_text()
    layout_src = Path("meshdash/assets/dashboard.js.chat.events.core.navigation.layout.tmpl").read_text()
    css = build_dashboard_css(theme_css="")

    assert "function syncChatReactionAnchorLabels() {{" in emoji_src
    assert 'function setChatReactionPickerExpanded(expanded, focusSearch = false) {{' in emoji_src
    assert "function isChatReactionAnchorToggleSource(anchor) {{" in emoji_src
    assert "function restoreChatReactionContextTooltip() {{" in emoji_src
    assert "function suppressChatReactionContextTooltip(anchor = null) {{" in emoji_src
    assert "function parseChatReactionSummaryGroups(anchor) {{" in emoji_src
    assert "function renderChatEmojiReactionSummaryRow(anchor = null) {{" in emoji_src
    assert "function animateChatEmojiPanelTransition(previousRect = null, options = null) {{" in emoji_src
    assert "function animateChatEmojiPanelClose(options = null) {{" in emoji_src
    assert "function finalizeChatEmojiPanelClose(panel = null) {{" in emoji_src
    assert '"Less reactions"' in emoji_src
    assert '"More reactions"' in emoji_src
    assert "const reactionExpandedFromAnchor = (" in emoji_src
    assert "reactToggleRow.hidden = true;" in emoji_src
    assert 'const reactionAnchorGap = reactionAnchorOwnsToggle ? 0 : 6;' in emoji_src
    assert 'const availableAbove = Math.max(220, Math.round(anchorRect.top - minTop + 2));' in emoji_src
    assert 'if (target.closest(".chat-reaction-summary") || target.closest(".chat-react-btn")) return;' in emoji_src
    assert 'const owner = anchor.closest(".chat-feed-item[title], .chatlabs-message-row[title], [data-message-id][title]");' in emoji_src
    assert 'owner.removeAttribute("title");' in emoji_src
    assert 'animateChatEmojiPanelTransition(previousRect, {{' in emoji_src
    assert 'animateChatEmojiPanelClose({{' in emoji_src
    assert 'const canManageOrder = !usePreferredChoices && chatEmojiMode !== "react";' in emoji_src
    assert 'id="chat-emoji-current-reactions-shell"' in emoji_src
    assert 'target.closest(".chat-emoji-current-reaction-chip")' in emoji_src
    assert '<div class="chat-emoji-top-label">Current reactions</div>' not in emoji_src
    assert "restoreChatReactionContextTooltip();" in emoji_src
    assert "suppressChatReactionContextTooltip(chatEmojiAnchorElement);" in emoji_src
    assert 'openReactionPickerFromAnchor(summary, {{ expand: true, toggleExpanded: true }});' in bindings_src
    assert 'openReactionPickerFromAnchor(anchor, {{ expand: false }});' in bindings_src
    assert 'aria-label="${{escAttr(summaryAria)}}">' in feed_src
    assert '"Add reaction"' in feed_src
    assert 'chat-reaction-summary-label">React<' in feed_src
    assert 'title="${{escAttr(summaryTitle)}}"' not in feed_src
    assert 'title="${{escAttr(`${{reactionSummaryTitle}} • React to this message`)}}"' not in layout_src
    assert 'title="Add reaction"' not in layout_src
    assert "node.dataset.defaultReactionTitle" not in emoji_src
    assert 'node.setAttribute("title", nextText);' not in emoji_src
    assert ".chat-reaction-summary.is-empty.is-reaction-preview," in css
    assert ".chat-emoji-panel.is-closing {" in css
    assert ".chat-emoji-current-reactions-shell {" in css
    assert "gap: 0;" in css
    assert ".chat-emoji-current-reaction-chip {" in css
    assert "@keyframes chatEmojiPanelContentIn {" in css
    assert "transition: background 140ms ease, border-color 140ms ease, color 140ms ease, box-shadow 180ms ease, transform 180ms ease;" in css
    assert "[data-theme=\"dark\"] .card.chat .chat-reaction-summary.is-empty.is-reaction-preview," in css


def test_chat_feed_cache_tracks_chat_tail_for_reaction_rebuilds() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "const rawMessagesLength = rawMessages.length;" in js
    assert "const rawMessagesTailKey = rawMessagesLength > 0" in js
    assert 'String(chatMessageKey(rawMessages[rawMessagesLength - 1]) || "")' in js
    assert "const rawPacketsLength = rawPackets.length;" in js
    assert 'const activeChatChannelKey = String(activeChatChannel || "all").trim() || "all";' in js
    assert "const chatMainDirectModeActive = !!chatMainDirectModeEnabled;" in js
    assert "chatDerivedCache.activeChatChannel === activeChatChannelKey" in js
    assert "chatDerivedCache.chatMainDirectModeEnabled === chatMainDirectModeActive" in js
    assert "chatDerivedCache.rawMessagesLength === rawMessagesLength" in js
    assert "chatDerivedCache.rawMessagesTailKey === rawMessagesTailKey" in js
    assert "chatDerivedCache.rawPacketsLength === rawPacketsLength" in js
    assert "rawMessagesTailKey," in js
    assert "activeChatChannel: activeChatChannelKey," in js
    assert "chatMainDirectModeEnabled: chatMainDirectModeActive," in js


def test_chat_reaction_notices_prefer_full_names_and_target_context(assert_tokens_present) -> None:
    unread_src = Path("meshdash/assets/dashboard.js.chat.events.core.notifications.unread.tmpl").read_text()
    preview_src = Path("meshdash/assets/dashboard.js.chat.events.core.notifications.notices.message_preview_history.tmpl").read_text()
    persist_src = Path("meshdash/assets/dashboard.js.chat.events.core.notifications.notices.persist_track.tmpl").read_text()

    assert "function chatResolvedNodeLabel(nodeIdRaw, nodesById, explicitName = \"\") {{" in unread_src
    assert "const preferred = node ? String(preferredNodeName(node) || \"\").trim() : \"\";" in unread_src
    assert "return preferred || explicit || cached || senderId || \"Unknown node\";" in unread_src
    assert "const messageInfoById = new Map();" in unread_src
    assert "senderLabel: chatSenderLabelFromMessage(msg, nodesById)," in unread_src
    assert "const reactionTargetLabel = reactionTargetInfo && typeof reactionTargetInfo === \"object\"" in unread_src
    assert "reaction_target_label: reactionTargetLabel," in unread_src
    assert_tokens_present(preview_src, [
        "const reactionTarget = compactChatChangePreview(",
        "msg && (msg.reaction_target_label ?? msg.reactionTargetLabel),",
        "const reactionTargetText = compactChatChangePreview(",
        "msg && (msg.reaction_target_text ?? msg.reactionTargetText),",
        'return `reacted ${{emoji}} to a message from ${{reactionTarget}}: "${{reactionTargetText}}"`;',
        "if (emoji && reactionTarget) return `reacted ${{emoji}} to a message from ${{reactionTarget}}`;",
        'return `reaction to a message from ${{reactionTarget}}: "${{reactionTargetText}}"`;',
        "if (reactionTarget) return `reaction to a message from ${{reactionTarget}}`;",
    ])
    assert "version: 3," in persist_src
    assert "Number(payload.version) === 3" in persist_src


def test_node_name_cache_rejects_generic_downgrades_and_accepts_history_caps() -> None:
    src = Path("meshdash/assets/dashboard.js.chat.events.core.identity.favorites_selection.topbar_map_title.tmpl").read_text()

    assert "function isGenericNodeCacheLabel(nameRaw, nodeIdRaw) {{" in src
    assert "function rememberNodeNameCacheCandidate(nodeIdRaw, candidateRaw) {{" in src
    assert "!isGenericNodeCacheLabel(current, nodeId)" in src
    assert "&& isGenericNodeCacheLabel(candidate, nodeId)" in src
    assert "function updateNodeNameCache(nodes, historyCaps = null) {{" in src
    assert "for (const [rawNodeId, caps] of Object.entries(historyCapsObj)) {{" in src
    assert "for (const name of [caps.last_long_name, caps.last_short_name]) {{" in src


def test_chat_node_list_can_collapse_into_compact_rail() -> None:
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

    assert 'id="chat-panel-collapse-btn"' in html
    assert 'id="chat-panel-collapse-glyph"' in html
    assert "--chat-panel-collapsed-width: 160px;" in css
    assert ".workspace-shell.chat-panel-open.chat-panel-collapsed {" in css
    assert ".workspace-shell.chat-panel-collapsed .chat-users-head-launcher-shell {" in css
    assert ".workspace-shell.chat-panel-collapsed .chat-users-head-launcher-shell .topbar-view-menu-btn {" in css
    assert ".workspace-shell.chat-panel-collapsed #chat-node-navigator-menu," in css
    assert ".workspace-shell.chat-panel-collapsed .chat-member-meta-row," in css
    assert ".workspace-shell.chat-panel-collapsed #chat-peer-add-toggle-btn," in css
    assert ".workspace-shell.chat-panel-collapsed .chat-left-bottom-bar {" in css
    assert "const chatPanelCollapsedStorageKey = \"meshDashboardChatPanelCollapsedV1\";" in js
    assert "let chatPanelCollapsed = false;" in js
    assert "function applyChatPanelCollapseState() {" in js
    assert "function setChatPanelCollapsed(nextCollapsed, options = null) {" in js
    assert "function loadChatPanelCollapseState() {" in js
    assert "let hasStoredPreference = false;" in js
    assert 'window.matchMedia("(max-width: 760px)").matches' in js
    assert "function persistChatPanelCollapseState() {" in js
    assert "function bindChatPanelCollapseToggle() {" in js
    assert 'window.localStorage.setItem(chatPanelCollapsedStorageKey, chatPanelCollapsed ? "1" : "0");' in js
    assert 'runBootStep("loadChatPanelCollapseState", () => loadChatPanelCollapseState());' in js
    assert 'runBootStep("bindChatPanelCollapseToggle", () => bindChatPanelCollapseToggle());' in js


def test_chat_mobile_layout_stacks_feed_meta_and_header_filters() -> None:
    css = build_dashboard_css(theme_css="")

    mobile_section = css.split("@media (max-width: 760px) {", 1)[1]

    assert ".layout.view-chat .chat-card-head .chat-card-head-actions {" in mobile_section
    assert "--chat-header-compose-trailing-space: 0px;" in mobile_section
    assert ".workspace-shell.chat-panel-open .workspace-main {" in mobile_section
    assert "grid-column: 1;" in mobile_section
    assert ".layout.view-chat .chat-card-head .mesh-channel-pill-strip {" in mobile_section
    assert "scroll-snap-type: x proximity;" in mobile_section
    assert ".chat-feed-line {" in mobile_section
    assert "flex-direction: column;" in mobile_section
    assert ".chat-feed-side {" in mobile_section
    assert "justify-content: flex-end;" in mobile_section
    assert ".chat-reply-inline {" in mobile_section
    assert "flex-wrap: wrap;" in mobile_section
    assert ".workspace-shell.chat-panel-collapsed .chat-left-head-shell {" in mobile_section
    assert "background: transparent;" in mobile_section


def test_chat_feed_self_authored_messages_render_as_bubbles_without_inline_time() -> None:
    css = build_dashboard_css(theme_css="")
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    item_section = css.rsplit("\n    .chat-feed-item {", 1)[1].split("}", 1)[0]
    self_item_section = css.split(".chat-feed-item.self-authored {", 1)[1].split("}", 1)[0]
    self_reaction_section = css.split(".chat-feed-item.self-authored .chat-reaction-row {", 1)[1].split("}", 1)[0]
    summary_section = css.rsplit("\n    .chat-feed-summary {", 1)[1].split("}", 1)[0]
    author_name_section = css.rsplit("\n    .chat-feed-author .chat-name {", 1)[1].split("}", 1)[0]
    text_section = css.rsplit("\n    .chat-feed-text {", 1)[1].split("}", 1)[0]
    dark_item_section = css.split('[data-theme="dark"] .card.chat .chat-feed-item {', 1)[1].split("}", 1)[0]
    monitor_item_section = css.split(".chat-feed.chat-feed-view-monitor .chat-feed-item {", 1)[1].split("}", 1)[0]
    mobile_section = css.split("@media (max-width: 760px) {", 1)[1]

    assert "width: fit-content;" in item_section
    assert "max-width: min(84%, 100%);" in item_section
    assert "border-radius: 16px 16px 16px 6px;" in item_section
    assert "margin-right: auto;" in item_section
    assert "padding: 9px 12px;" in item_section
    assert "display: flex;" in summary_section
    assert "align-items: flex-start;" in summary_section
    assert "flex-wrap: wrap;" in summary_section
    assert "gap: 4px 5px;" in summary_section
    assert "line-height: 1.45;" in summary_section
    assert "font-size: 14px;" in author_name_section
    assert "font-weight: 700;" in author_name_section
    assert "font-size: 14px;" in text_section
    assert "line-height: 1.45;" in text_section
    assert "margin-left: auto;" in self_item_section
    assert "margin-right: 0;" in self_item_section
    assert "border-radius: 16px 16px 6px 16px;" in self_item_section
    assert "justify-content: flex-end;" in self_reaction_section
    assert "--chat-feed-node-emoji-tail-space: 24px;" in css
    assert "--chat-feed-node-emoji-tail-inset: -6px;" in css
    assert ".chat-feed-item.has-node-emoji {" in css
    assert "--chat-feed-node-emoji-tail-space: clamp(52px, 4.9vw, 74px);" in css
    assert "--chat-feed-node-emoji-tail-inset: 8px;" in css
    assert "padding-right: var(--chat-feed-node-emoji-tail-space);" in css
    assert ".chat-feed-item.self-authored.has-node-emoji {" in css
    assert "padding-left: var(--chat-feed-node-emoji-tail-space);" in css
    assert ".chat-feed-item.has-node-emoji::after {" in css
    assert 'content: attr(data-node-emoji);' in css
    assert 'font-size: clamp(44px, 4.7vw, 70px);' in css
    assert "right: var(--chat-feed-node-emoji-tail-inset);" in css
    assert ".chat-feed-item.self-authored.has-node-emoji::after {" in css
    assert "left: var(--chat-feed-node-emoji-tail-inset);" in css
    assert '[data-theme="dark"] .card.chat .chat-feed-item.has-node-emoji::after {' in css
    assert ".chat-hop-watermark-inline {" in css
    assert "font-size: 10px;" in css
    assert "font-weight: 700;" in css
    assert "font-variant-numeric: tabular-nums;" in css
    assert "opacity: 0.58;" in css
    assert '[data-theme="dark"] .card.chat .chat-hop-watermark-inline {' in css
    assert "opacity: 0.52;" in css
    assert "border: 1px solid var(--chat-feed-node-outline);" in dark_item_section
    assert "border-radius: 16px 16px 16px 6px;" in dark_item_section
    assert "width: 100%;" in monitor_item_section
    assert "max-width: 100%;" in monitor_item_section
    assert "border-radius: 0;" in monitor_item_section
    assert "max-width: min(92%, 100%);" in mobile_section
    assert "const isSelfAuthored = isLocalEcho || (" in js
    assert 'const selfAuthoredClass = isSelfAuthored ? " self-authored" : "";' in js
    assert "const nodeVisualEmoji = (typeof nodeVisualEmojiForNode === \"function\")" in js
    assert 'const nodeEmojiClass = nodeVisualEmoji ? " has-node-emoji" : "";' in js
    assert 'data-node-emoji="${escAttr(nodeVisualEmoji)}"' in js
    assert "function formatLocalChatTime12Hour(" in js
    assert 'const meridiem = hour24 >= 12 ? "PM" : "AM";' in js
    assert 'const hasHopWatermarkTime = !!(hopWatermarkTimeText && hopWatermarkTimeText !== "n/a");' in js
    assert 'const hopWatermarkInline = (hasHop || hasHopWatermarkTime)' in js
    assert 'const hopWatermarkTimeText = formatLocalChatTime12Hour(msgTimeUnix, rawTimeText || "n/a", nowUnix);' in js
    assert 'const hopWatermarkText = hasHop' in js
    assert 'Time: ${hopWatermarkTimeText}' in js
    assert '${hopNum} hop' in js
    assert 'if (hopWatermarkInline) reactionRowParts.push(hopWatermarkInline);' in js
    assert 'const routingMetadataLabel = hasRoutingMetadata' in js
    assert 'messageTooltipParts.push(`Routing: ${routingMetadataLabel}`);' in js
    assert 'class="chat-hop-watermark-inline"' in js
    assert "<span class=\"chat-feed-time\"" not in js


def test_chat_feed_search_is_reapplied_after_feed_render() -> None:
    css = build_dashboard_css(theme_css="")
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert ".chat-feed-item.chat-feed-search-hidden {" in css
    assert "display: none !important;" in css
    assert "feed.__meshChatFeedSearchRows = [];" in js
    assert 'if (typeof applyChatFeedSearchFilter === "function") {' in js
    assert "applyChatFeedSearchFilter();" in js


def test_chat_macro_menu_removes_novelty_face_shortcuts_only() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "function renderChatMacroHelpPreview" in js
    assert "Macro Menu - click a command to insert" in js
    assert "Macro Help (${sourceLabel}) - click a command to insert" in js
    assert '"/shrug"' not in js
    assert '"/tableflip"' not in js
    assert '"/flip"' not in js
    assert '"/unflip"' not in js
    assert '"/give"' not in js
    assert '"/lenny"' not in js
    assert '"/cheer"' not in js
    assert '"/search <text>"' in js
    assert '"/1337 <text>"' in js
    assert '"/backwards <text>"' in js
    assert '"/scrambled <text>"' in js
    assert '"/upsidedown <text>"' in js
    assert '"/disemvowel <text>"' in js
    assert '"/special <text>"' not in js
    assert '"/glyph <text>"' in js


def test_launcher_menu_omits_header_block() -> None:
    js = Path("meshdash/assets/dashboard.js.chat.events.core.identity.node_self.tmpl").read_text()

    assert 'document.getElementById("layout-view-menu-head-mark")' not in js
    assert 'document.getElementById("layout-view-menu-head-brand")' not in js
    assert 'document.getElementById("layout-view-menu-head-version")' not in js
    assert 'document.getElementById("layout-view-menu-head-commit")' not in js
    assert "const setLauncherHead = " not in js
    assert 'const launcherAppMark = "MF";' not in js
    assert 'const launcherAppName = "Meshyface";' not in js


def test_workspace_shell_records_active_layout_view_for_chat_css_hooks() -> None:
    js = Path("meshdash/assets/dashboard.js.chat.events.core.navigation.layout.tmpl").read_text()

    assert "shell.dataset.layoutView = next;" in js
    assert "shell.classList.remove(`layout-view-${{name}}`);" in js
    assert "shell.classList.add(`layout-view-${{next}}`);" in js
