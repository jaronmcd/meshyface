from meshdash.html_css import build_dashboard_css
from meshdash.html_js import build_dashboard_js


def test_build_dashboard_css_includes_theme_tokens_and_core_selectors():
    css = build_dashboard_css(theme_css=":root { --test-color: #123456; }")
    assert ":root { --test-color: #123456; }" in css
    assert ".topbar" in css
    assert ".workspace-shell" in css
    assert "* { box-sizing: border-box; }" in css
    assert "{{" not in css
    assert "}}" not in css


def test_build_dashboard_js_injects_runtime_values():
    js = build_dashboard_js(
        refresh_ms=3000,
        node_history_hours=72,
        node_history_max_points=1440,
    )
    assert "const refreshMs = 3000;" in js
    assert "const nodeHistoryHours = 72;" in js
    assert "const nodeHistoryMaxPoints = 1440;" in js
    assert "setInterval(poll, refreshMs);" in js
    assert "/^[0-9a-f]{8}$/i.test(hex)" in js
    assert "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" in js
    assert "{{" not in js
    assert "}}" not in js
