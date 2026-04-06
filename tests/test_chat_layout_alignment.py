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
    assert ".chat-compose-shell {" in css
    assert "border-radius: 10px;" in css
    assert "padding: 6px;" in css
    assert "gap: 0;" in css
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

    assert '<div class="chat-compose-notices">' in html
    assert 'id="chat-channel-mismatch-warning"' in html
    assert 'id="chat-send-status"' in html
    assert ".chat-compose-shell {" in css
    assert "position: relative;" in css
    assert ".chat-compose-notices {" in css
    assert "position: absolute;" in css
    assert "bottom: calc(100% + 2px);" in css
