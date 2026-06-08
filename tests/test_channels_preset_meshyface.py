import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_js import build_dashboard_js
from meshdash.html_sections import build_html_shell


def test_channels_settings_expose_meshyface_quick_join_preset() -> None:
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

    assert 'id="settings-channels-join-meshyface-btn"' in html
    assert "Join Meshyface" in html
    assert "This does not change LoRa region, modem preset, or frequency slot." in html
    assert "Channel numbers are local to each radio." in html


def test_meshyface_quick_join_uses_channel_upsert_flow() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'const meshyfaceBetaChannelPreset = Object.freeze({' in js
    assert 'name: "Meshyface"' in js
    assert 'psk: "base64:u2yfVqp2J8P+Uer6z9OnNGwORpCCSNF4GKbzYgya9jM="' in js
    assert 'async function handleJoinMeshyfaceBetaChannel() {' in js
    assert 'document.getElementById("settings-channels-join-meshyface-btn")' in js
    assert 'setMeshChannelAppSendMode("games", "fixed", true);' in js
    assert 'setMeshChannelAppSendIndex("games", idx, true);' in js

    join_section = js.split("async function handleJoinMeshyfaceBetaChannel() {", 1)[1]
    join_section = join_section.split("function looksLikeMeshtasticChannelUrl", 1)[0]
    assert "const targetSlot = existing;" in join_section
    assert 'action: "upsert"' in join_section
    assert 'role: "SECONDARY"' in join_section
    assert 'action: "import_url"' not in join_section
    assert 'await ensureChannelsViewLocalStateHydrated(false);' in join_section
