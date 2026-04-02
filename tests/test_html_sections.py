from meshdash.html_sections import build_html_shell


def test_build_html_shell_injects_style_js_and_header_tokens():
    html = build_html_shell(
        app_title="Meshyface",
        app_heading="Meshyface",
        style_css="/* style-css */",
        app_js="// app-js",
        revision_title="rev-title",
        revision_label="Rev: test",
        safety_label="Secrets redacted",
        packet_limit=250,
        history_label="History: on",
        refresh_ms=3000,
    )
    assert "<style>\n/* style-css */\n  </style>" in html
    assert "<script>\n// app-js\n  </script>" in html
    assert "<title>Meshyface</title>" in html
    assert '<h1 class="topbar-heading">' in html
    assert '<span class="topbar-heading-app">Meshyface</span>' in html
    assert 'id="self-radio-profile"' in html
    assert 'id="favorite-menu-toggle-btn"' in html
    assert ">n/a<" in html
    assert 'title="rev-title">Rev: test<' in html
    assert "Packet buffer: 250" in html
    assert "Refresh: 3000 ms" in html
    assert 'id="theme-preset-select"' in html
    assert 'id="m-target-radio-status"' in html
