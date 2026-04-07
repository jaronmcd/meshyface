import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_css import build_dashboard_css
from meshdash.html_sections import build_html_shell


def test_chat_layout_spacing_matches_tighter_network_style() -> None:
    css = build_dashboard_css(theme_css="")

    assert ".workspace-main > .layout.view-chat," in css
    assert ".workspace-main > .layout.view-console {" in css
    assert "grid-row: 1 / -1;" in css
    assert ".chat-shell {" in css
    assert "padding: 8px 10px;" in css
    assert ".chat-main-pane {" in css
    assert "row-gap: 0;" in css
    assert ".chat-log-scroll {" in css
    assert "padding: 0;" in css
    assert ".chat-compose-shell {" in css
    assert "margin-top: 6px;" in css
    assert "background: transparent;" in css
    assert "border: 0;" in css
    assert "border-radius: 0;" in css
    assert "padding: 0;" in css
    assert "gap: 0;" in css
    assert ".chat-left-bottom-bar {" in css
    assert "border: 0;" in css
    assert "[data-theme=\"dark\"] .chat-left-panel," in css
    assert "[data-theme=\"dark\"] .card.chat .body," in css
    assert "[data-theme=\"dark\"] .card.chat .chat-shell {" in css
    assert "[data-theme=\"dark\"] .chat-left-bottom-bar {" in css
    assert "background: #07140d !important;" in css
    assert "[data-theme=\"dark\"] #chat-emoji-btn," in css
    assert "[data-theme=\"dark\"] #chat-send-btn {" in css
    assert "border-color: #2b8a59 !important;" in css
    assert ".list-search-input,\n    #chat-input {" in css
    assert "#chat-input:hover {" not in css
    assert "[data-theme=\"dark\"] #chat-input:hover {" not in css
    assert "[data-theme=\"dark\"] #chat-input:focus {" not in css


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


def test_chat_send_channel_compact_dot_trigger_geometry() -> None:
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
