import re
from pathlib import Path


_ASSETS_DIR = Path(__file__).resolve().parents[1] / "meshdash" / "assets"


def _asset_text(name: str) -> str:
    return (_ASSETS_DIR / name).read_text(encoding="utf-8")


def test_board_links_sync_defers_dedupe_until_move_is_applied():
    text = _asset_text("dashboard.js.chat.state.games.network.board_links.sync_ui.tmpl")

    # Regression guard: do not mark messages as seen at loop entry.
    assert "if (refs.getSeenKeys().has(dedupeKey)) continue;" in text
    assert "if (!rememberBoardGameNetworkMessage(gameId, dedupeKey)) continue;" not in text

    # Invalid move payloads are consumed so they do not loop forever.
    assert re.search(
        r"if \(!sessionId \|\| seq <= 0\) \{\{\s*rememberBoardGameNetworkMessage\(gameId, dedupeKey\);\s*continue;\s*\}\}",
        text,
    )

    # Valid move payloads must only be marked seen after successful apply.
    move_start = text.index('if (parsed.type === "move") {{')
    move_block = text[move_start:]
    applied_guard_idx = move_block.index("if (!applied) continue;")
    remember_after_apply_idx = move_block.index(
        "rememberBoardGameNetworkMessage(gameId, dedupeKey);",
        applied_guard_idx,
    )
    assert remember_after_apply_idx > applied_guard_idx


def test_reversi_sync_defers_dedupe_until_move_is_applied():
    text = _asset_text("dashboard.js.chat.state.games.network.reversi_link.protocol_sync.tmpl")

    # Regression guard: do not mark messages as seen at loop entry.
    assert "if (reversiSeenNetworkMessageKeys.has(dedupeKey)) continue;" in text
    assert "if (!rememberReversiNetworkMessage(dedupeKey)) continue;" not in text

    # Invalid move payloads are consumed so they do not loop forever.
    assert re.search(
        r"if \(!sessionId \|\| !inReversiBounds\(row, col\) \|\| seq <= 0\) \{\{\s*rememberReversiNetworkMessage\(dedupeKey\);\s*continue;\s*\}\}",
        text,
    )

    # Valid move payloads must only be marked seen after successful apply.
    move_start = text.index('if (parsed.type === "move") {{')
    move_block = text[move_start:]
    applied_guard_idx = move_block.index("if (!applied) continue;")
    remember_after_apply_idx = move_block.index(
        "rememberReversiNetworkMessage(dedupeKey);",
        applied_guard_idx,
    )
    assert remember_after_apply_idx > applied_guard_idx
