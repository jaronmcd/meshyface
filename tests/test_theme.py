from meshdash.theme import DARK_THEME_VARS, LIGHT_THEME_VARS, build_theme_css


def test_theme_css_includes_light_and_dark_selectors():
    css = build_theme_css()
    assert ":root {" in css
    assert '[data-theme="dark"] {' in css


def test_theme_css_contains_all_tokens():
    css = build_theme_css()
    for key, value in LIGHT_THEME_VARS.items():
        assert f"{key}: {value};" in css
    for key, value in DARK_THEME_VARS.items():
        assert f"{key}: {value};" in css


def test_theme_css_indent_override():
    css = build_theme_css(indent="  ")
    lines = css.splitlines()
    assert lines[0].startswith("  :root {")


def test_theme_css_accepts_override_token_maps():
    css = build_theme_css(
        light_vars={"--bg": "#ffffff"},
        dark_vars={"--ui-bg": "#000000"},
    )
    assert "--bg: #ffffff;" in css
    assert "--ui-bg: #000000;" in css
