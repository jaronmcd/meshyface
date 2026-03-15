import re
from pathlib import Path


_ASSETS_DIR = Path(__file__).resolve().parents[1] / "meshdash" / "assets"
_TEMPLATE_FILES = (
    "dashboard.css.tmpl",
    "dashboard.css.base.tmpl",
    "dashboard.css.layout.tmpl",
    "dashboard.css.components.tmpl",
    "dashboard.html.tmpl",
    "dashboard.js.tmpl",
    "dashboard.js.bootstrap.tmpl",
    "dashboard.js.bootstrap.map.tmpl",
    "dashboard.js.bootstrap.tickers.tmpl",
    "dashboard.js.bootstrap.shared.tmpl",
    "dashboard.js.chat.tmpl",
    "dashboard.js.chat.state.tmpl",
    "dashboard.js.chat.state.core.tmpl",
    "dashboard.js.chat.state.channels.tmpl",
    "dashboard.js.chat.state.games.tmpl",
    "dashboard.js.chat.state.games.reversi_local.tmpl",
    "dashboard.js.chat.state.games.classic.tmpl",
    "dashboard.js.chat.state.games.network.tmpl",
    "dashboard.js.chat.state.games.ui.tmpl",
    "dashboard.js.chat.state.messaging.tmpl",
    "dashboard.js.chat.state.messaging.peers.tmpl",
    "dashboard.js.chat.state.messaging.emoji_search.tmpl",
    "dashboard.js.chat.state.messaging.send_flow.tmpl",
    "dashboard.js.chat.state.messaging.emoji_ui.tmpl",
    "dashboard.js.chat.state.files.tmpl",
    "dashboard.js.chat.events.tmpl",
    "dashboard.js.chat.events.core.tmpl",
    "dashboard.js.chat.events.core.identity.tmpl",
    "dashboard.js.chat.events.core.layout_tables.tmpl",
    "dashboard.js.chat.events.core.notifications.tmpl",
    "dashboard.js.chat.events.core.navigation.tmpl",
    "dashboard.js.chat.events.console.tmpl",
    "dashboard.js.chat.events.console.session.tmpl",
    "dashboard.js.chat.events.console.commands.tmpl",
    "dashboard.js.chat.events.console.formatting.tmpl",
    "dashboard.js.chat.events.console.ui.tmpl",
    "dashboard.js.chat.events.settings_map.tmpl",
    "dashboard.js.chat.events.settings.tmpl",
    "dashboard.js.chat.events.settings.state_normalize.tmpl",
    "dashboard.js.chat.events.settings.channels.tmpl",
    "dashboard.js.chat.events.settings.apply_actions.tmpl",
    "dashboard.js.chat.events.settings.bindings.tmpl",
    "dashboard.js.chat.events.map_selection.tmpl",
    "dashboard.js.chat.events.bindings.tmpl",
    "dashboard.js.chat.events.data_views.tmpl",
    "dashboard.js.chat.events.data_views.summary_map.tmpl",
    "dashboard.js.chat.events.data_views.nodes_saved.tmpl",
    "dashboard.js.chat.events.data_views.charts.tmpl",
    "dashboard.js.chat.events.data_views.history_fetch.tmpl",
    "dashboard.js.chat.render.tmpl",
    "dashboard.js.runtime.tmpl",
    "dashboard.js.runtime.views.tmpl",
    "dashboard.js.runtime.views.packet_channels.tmpl",
    "dashboard.js.runtime.views.encryption.tmpl",
    "dashboard.js.runtime.views.raw_data.tmpl",
    "dashboard.js.runtime.poll.tmpl",
    "dashboard.js.runtime.boot.tmpl",
)
_TRAILING_SPACE_RE = re.compile(r"[ \t]+$", re.MULTILINE)


def test_asset_templates_use_unix_newlines_and_no_tabs():
    for template_name in _TEMPLATE_FILES:
        raw = (_ASSETS_DIR / template_name).read_text(encoding="utf-8")
        assert "\r" not in raw
        assert "\t" not in raw


def test_asset_templates_have_no_trailing_whitespace():
    for template_name in _TEMPLATE_FILES:
        raw = (_ASSETS_DIR / template_name).read_text(encoding="utf-8")
        assert _TRAILING_SPACE_RE.search(raw) is None


def test_asset_templates_end_with_newline():
    for template_name in _TEMPLATE_FILES:
        raw = (_ASSETS_DIR / template_name).read_text(encoding="utf-8")
        assert raw.endswith("\n")
