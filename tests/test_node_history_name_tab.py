import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_js import build_dashboard_js
from meshdash.html_template import render_html


def test_render_html_includes_node_history_names_tab() -> None:
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

    assert 'id="tab-btn-names"' in html
    assert 'data-tab="names"' in html
    assert 'id="tab-panel-names"' in html
    assert 'id="node-name-history-host"' in html


def test_dashboard_js_renders_name_history_under_history_tab() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'nextTab === "online" || nextTab === "packets" || nextTab === "names"' in js
    assert 'const namesPanel = document.getElementById("tab-panel-names");' in js
    assert 'renderNodeNameHistoryPanel(nameHistoryEntries);' in js
    assert 'renderNodeNameHistoryPanel([], {' in js
    assert 'const nameHistoryEntries = Array.isArray(history && history.name_history)' in js
