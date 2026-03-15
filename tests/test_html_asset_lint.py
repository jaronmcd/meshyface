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
    "dashboard.js.bootstrap.map.setup_emoji.tmpl",
    "dashboard.js.bootstrap.map.offline_basemap.tmpl",
    "dashboard.js.bootstrap.map.resize.tmpl",
    "dashboard.js.bootstrap.map.signal_heatmap.tmpl",
    "dashboard.js.bootstrap.map.wheel.tmpl",
    "dashboard.js.bootstrap.map.tmpl",
    "dashboard.js.bootstrap.tickers.metrics.tmpl",
    "dashboard.js.bootstrap.tickers.preferences.tmpl",
    "dashboard.js.bootstrap.tickers.controls.tmpl",
    "dashboard.js.bootstrap.tickers.tmpl",
    "dashboard.js.bootstrap.shared.tmpl",
    "dashboard.js.ui.shared_controls.tmpl",
    "dashboard.js.chat.tmpl",
    "dashboard.js.chat.state.tmpl",
    "dashboard.js.chat.state.core.chat.delivery_reactions.tmpl",
    "dashboard.js.chat.state.core.chat.channels_notifications.tmpl",
    "dashboard.js.chat.state.core.chat.bot_quick_actions.tmpl",
    "dashboard.js.chat.state.core.chat.tmpl",
    "dashboard.js.chat.state.core.bot_history.tmpl",
    "dashboard.js.chat.state.core.bot_controls.tmpl",
    "dashboard.js.chat.state.core.tmpl",
    "dashboard.js.chat.state.channels.tmpl",
    "dashboard.js.chat.state.games.tmpl",
    "dashboard.js.chat.state.games.reversi_local.tmpl",
    "dashboard.js.chat.state.games.classic.checkers.tmpl",
    "dashboard.js.chat.state.games.classic.chess.tmpl",
    "dashboard.js.chat.state.games.classic.poker.setup.tmpl",
    "dashboard.js.chat.state.games.classic.poker.flow.tmpl",
    "dashboard.js.chat.state.games.classic.poker.render.tmpl",
    "dashboard.js.chat.state.games.classic.poker.tmpl",
    "dashboard.js.chat.state.games.classic.tmpl",
    "dashboard.js.chat.state.games.network.board_links.tmpl",
    "dashboard.js.chat.state.games.network.reversi_link.tmpl",
    "dashboard.js.chat.state.games.network.tmpl",
    "dashboard.js.chat.state.games.ui.tmpl",
    "dashboard.js.chat.state.messaging.tmpl",
    "dashboard.js.chat.state.messaging.peers.tmpl",
    "dashboard.js.chat.state.messaging.emoji_search.tmpl",
    "dashboard.js.chat.state.messaging.send_flow.tmpl",
    "dashboard.js.chat.state.messaging.emoji_ui.tmpl",
    "dashboard.js.chat.state.files.protocol.tmpl",
    "dashboard.js.chat.state.files.frames.tmpl",
    "dashboard.js.chat.state.files.maintenance.tmpl",
    "dashboard.js.chat.state.files.view.tmpl",
    "dashboard.js.chat.state.files.tmpl",
    "dashboard.js.chat.events.tmpl",
    "dashboard.js.chat.events.core.tmpl",
    "dashboard.js.chat.events.core.identity.node_self.tmpl",
    "dashboard.js.chat.events.core.identity.favorites_selection.tmpl",
    "dashboard.js.chat.events.core.identity.text_utils.tmpl",
    "dashboard.js.chat.events.core.identity.tmpl",
    "dashboard.js.chat.events.core.layout_tables.tmpl",
    "dashboard.js.chat.events.core.notifications.notices.tmpl",
    "dashboard.js.chat.events.core.notifications.menus.tmpl",
    "dashboard.js.chat.events.core.notifications.unread.tmpl",
    "dashboard.js.chat.events.core.notifications.tmpl",
    "dashboard.js.chat.events.core.navigation.layout.tmpl",
    "dashboard.js.chat.events.core.navigation.splitters.tmpl",
    "dashboard.js.chat.events.core.navigation.tablesort.tmpl",
    "dashboard.js.chat.events.core.navigation.tmpl",
    "dashboard.js.chat.events.console.tmpl",
    "dashboard.js.chat.events.console.session.tmpl",
    "dashboard.js.chat.events.console.commands.helpers.tmpl",
    "dashboard.js.chat.events.console.commands.registry.tmpl",
    "dashboard.js.chat.events.console.commands.tmpl",
    "dashboard.js.chat.events.console.formatting.tmpl",
    "dashboard.js.chat.events.console.ui.tmpl",
    "dashboard.js.chat.events.settings.state_normalize.core.tmpl",
    "dashboard.js.chat.events.settings.state_normalize.position_map.tmpl",
    "dashboard.js.chat.events.settings.state_normalize.render_read.tmpl",
    "dashboard.js.chat.events.settings_map.tmpl",
    "dashboard.js.chat.events.settings.tmpl",
    "dashboard.js.chat.events.settings.state_normalize.tmpl",
    "dashboard.js.chat.events.settings.channels.table.tmpl",
    "dashboard.js.chat.events.settings.channels.reading.tmpl",
    "dashboard.js.chat.events.settings.channels.parse.tmpl",
    "dashboard.js.chat.events.settings.channels.tmpl",
    "dashboard.js.chat.events.settings.apply_actions.config.tmpl",
    "dashboard.js.chat.events.settings.apply_actions.modules.tmpl",
    "dashboard.js.chat.events.settings.apply_actions.radio_ops.tmpl",
    "dashboard.js.chat.events.settings.apply_actions.tmpl",
    "dashboard.js.chat.events.settings.bindings.tmpl",
    "dashboard.js.chat.events.map_selection.tmpl",
    "dashboard.js.chat.events.bindings.tmpl",
    "dashboard.js.chat.events.data_views.tmpl",
    "dashboard.js.chat.events.data_views.summary_map.summary.tmpl",
    "dashboard.js.chat.events.data_views.summary_map.map_helpers.tmpl",
    "dashboard.js.chat.events.data_views.summary_map.map_render.tmpl",
    "dashboard.js.chat.events.data_views.summary_map.tmpl",
    "dashboard.js.chat.events.data_views.nodes_saved.tmpl",
    "dashboard.js.chat.events.data_views.charts.zoom_timeline.tmpl",
    "dashboard.js.chat.events.data_views.charts.signal_online.tmpl",
    "dashboard.js.chat.events.data_views.charts.weekly.tmpl",
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
