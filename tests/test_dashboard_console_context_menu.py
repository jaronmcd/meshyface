import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_js import build_dashboard_js
from meshdash.html_template import render_html


def test_dashboard_js_includes_console_context_menu_paste_guard() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "ev.defaultPrevented" in js
    assert "window.isSecureContext" in js
    assert "Use Ctrl+V" in js
    assert "console-context-menu-paste" in js
    assert "browser blocked menu paste here" not in js


def test_render_html_includes_console_context_menu_markup() -> None:
    html = render_html(
        refresh_ms=1000,
        packet_limit=200,
        show_secrets=False,
        history_enabled=True,
        history_max_rows=200,
        history_retention_days=7,
        node_history_hours=24,
        node_history_max_points=240,
        revision_label="test",
        revision_title="test",
    )

    assert 'id="console-context-menu"' in html
    assert 'id="console-autocomplete-menu"' in html
    assert 'class="console-autocomplete-menu"' in html
    assert 'id="console-context-menu-paste"' in html
    assert 'id="console-context-menu-copy"' in html
