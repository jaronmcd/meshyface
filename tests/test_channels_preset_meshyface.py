import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_js import build_dashboard_js
from meshdash.html_sections import build_html_shell


def test_channels_settings_do_not_expose_meshyface_quick_join_preset() -> None:
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

    assert 'id="settings-channels-join-meshyface-btn"' not in html
    assert "Join Meshyface" not in html
    assert "does not ship a bundled shared channel key" in html


def test_channel_settings_js_keeps_url_import_and_no_bundled_meshyface_psk() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    legacy_psk = "base64:" + "u2yfVqp2J8P+Uer6z9OnNGwORpCCSNF4GKbzYgya9jM="

    assert 'const meshyfaceBetaChannelPreset = Object.freeze({' not in js
    assert "handleJoinMeshyfaceBetaChannel" not in js
    assert 'document.getElementById("settings-channels-join-meshyface-btn")' not in js
    assert legacy_psk not in js
    assert 'action: "import_url"' in js
