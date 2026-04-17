import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_js import build_dashboard_js
from meshdash.html_template import render_html


def test_dashboard_js_includes_wall_chess_game_hooks() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'if (token === "wallchess") return "wallchess";' in js
    assert 'function startNewWallChessGame() {' in js
    assert 'function renderWallChessBoard() {' in js
    assert 'function renderWallChessStatus() {' in js
    assert 'function handleWallChessWallClick(orientationRaw, rowRaw, colRaw) {' in js
    assert 'if (normalizedGameId === "wallchess") return 10.36;' in js
    assert 'syncBoardGameNetworkState("wallchess", _state);' in js
    assert 'function sendWallChessActionToPeer(actionType, payload = {}) {' in js


def test_render_html_includes_wall_chess_panels() -> None:
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

    assert '<option value="wallchess">Wall Chess</option>' in html
    assert 'id="games-side-wallchess"' in html
    assert 'id="games-main-wallchess"' in html
    assert 'id="wallchess-board"' in html
    assert 'id="games-status-wallchess"' in html
    assert 'id="wallchess-host-btn"' in html
    assert 'id="wallchess-invite-list"' in html
    assert ".wall-chess-board {" in html
