import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_js import build_dashboard_js


def test_dashboard_js_supports_live_console_filtering() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'let consoleLiveFilterText = "";' in js
    assert "let consoleLiveFilterSpec = null;" in js
    assert (
        'usage: "live [-v|-vv|-vvv|-vvvv] [grep|rg [-i] [-v <text>] '
        '<text> [from!=%self]|filter=<text>] '
        '[-l1] [-l2] [-l3] [--layer=1,2,3]"'
    ) in js
    assert 'name: "rg"' in js
    assert 'usage: "rg <text> [-A<n>|-B<n>|-C<n>]' in js
    assert "function formatConsoleLiveFilterLabel(filterSpecOrText)" in js
    assert "function consoleLiveLineListMatchesFilter(lineList, filterSpecOrText)" in js
    assert "function consoleLivePacketFieldValue(entry, rawField)" in js
    assert "function consoleLiveEntryMatchesFilter(entry, lineList, filterSpecOrText)" in js
    assert "function consoleLiveFilterSignature(filterSpecOrText)" in js
    assert 'const liveFilterOptionKeys = new Set(["filter", "grep", "rg", "search", "match", "q", "query"]);' in js
    assert 'const liveFilterArgKeys = new Set(["filter", "grep", "rg", "search", "match"]);' in js
    assert 'const liveFilterFieldKeys = new Set(["from", "to", "port", "portnum", "text", "channel", "ch", "id", "packet"]);' in js
    assert 'if (isConsoleSelfTargetMacro(display))' in js
    assert "addExcludeTerm(clean);" in js
    assert "addFieldCondition(match[1], match[2], match[3])" in js
    assert 'if (key === "exclude" || key === "invert-match")' in js
    assert 'const fieldOptionMatch = key.match(/^([a-zA-Z_][a-zA-Z0-9_-]*)(!)?$/);' in js
    assert "consoleLiveFilterText = String(layerSelection.filterText || \"\").trim();" in js
    assert "consoleLiveFilterSpec = layerSelection.filterSpec || null;" in js
    assert 'return \'[live] missing filter text. Example: live grep -i "TEXT_MESSAGE_APP" from!=%self\';' in js
    assert "return layerSelection.unresolvedMacros.map((line) => `[live] ${line}`);" in js
    assert "const filterLabel = formatConsoleLiveFilterLabel(consoleLiveFilterSpec || consoleLiveFilterText);" in js
    assert "const filterSpec = consoleLiveFilterSpec || filterText;" in js
    assert "const filterSignature = consoleLiveFilterSignature(filterSpec);" in js
    assert "if (!consoleLiveEntryMatchesFilter(entry, lineList, filterSpec))" in js
    assert "consoleLiveFilterSpec = null;" in js


def test_dashboard_js_preserves_grep_invert_flag_after_live_filter_keyword() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'const stopAtLiveFilter = cleanCommandName === "live";' in js
    assert 'if (stopAtLiveFilter && /^(grep|rg|filter|search|match)$/i.test(text))' in js
    assert "if (match && !insideLiveFilter)" in js


def test_dashboard_js_help_documents_console_autocomplete_and_search_modes() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "autocomplete: type a command or node target to open suggestions" in js
    assert "node suggestions: node targets show name, ID, emoji, tag, status" in js
    assert "live grep [-i] [-v <text>] <text> [from!=%self] - stream matching live packet groups" in js
    assert "grep <text> or rg <text> - search retained packet/chat history with context windows" in js
    assert "/search <text> - filter visible console output live from the prompt" in js
