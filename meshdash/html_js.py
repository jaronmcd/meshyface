from .html_assets import render_asset_template as _render_asset_template_helper

_DASHBOARD_JS_TEMPLATE_PARTS = (
    "dashboard.js.bootstrap.map.setup_emoji.tmpl",
    "dashboard.js.bootstrap.map.offline_basemap.tmpl",
    "dashboard.js.bootstrap.map.resize.tmpl",
    "dashboard.js.bootstrap.map.signal_heatmap.tmpl",
    "dashboard.js.bootstrap.map.wheel.tmpl",
    "dashboard.js.bootstrap.tickers.metrics.tmpl",
    "dashboard.js.bootstrap.tickers.preferences.tmpl",
    "dashboard.js.bootstrap.tickers.controls.tmpl",
    "dashboard.js.bootstrap.shared.tmpl",
    "dashboard.js.chat.state.core.chat.tmpl",
    "dashboard.js.chat.state.core.bot_history.tmpl",
    "dashboard.js.chat.state.core.bot_controls.tmpl",
    "dashboard.js.chat.state.channels.tmpl",
    "dashboard.js.chat.state.games.reversi_local.tmpl",
    "dashboard.js.chat.state.games.classic.checkers.tmpl",
    "dashboard.js.chat.state.games.classic.chess.tmpl",
    "dashboard.js.chat.state.games.classic.poker.tmpl",
    "dashboard.js.chat.state.games.network.board_links.tmpl",
    "dashboard.js.chat.state.games.network.reversi_link.tmpl",
    "dashboard.js.chat.state.games.ui.tmpl",
    "dashboard.js.chat.state.messaging.peers.tmpl",
    "dashboard.js.chat.state.messaging.emoji_search.tmpl",
    "dashboard.js.chat.state.messaging.send_flow.tmpl",
    "dashboard.js.chat.state.messaging.emoji_ui.tmpl",
    "dashboard.js.chat.state.files.protocol.tmpl",
    "dashboard.js.chat.state.files.frames.tmpl",
    "dashboard.js.chat.state.files.maintenance.tmpl",
    "dashboard.js.chat.state.files.view.tmpl",
    "dashboard.js.chat.events.core.identity.tmpl",
    "dashboard.js.chat.events.core.layout_tables.tmpl",
    "dashboard.js.chat.events.core.notifications.notices.tmpl",
    "dashboard.js.chat.events.core.notifications.menus.tmpl",
    "dashboard.js.chat.events.core.notifications.unread.tmpl",
    "dashboard.js.chat.events.core.navigation.tmpl",
    "dashboard.js.chat.events.console.session.tmpl",
    "dashboard.js.chat.events.console.commands.tmpl",
    "dashboard.js.chat.events.console.formatting.tmpl",
    "dashboard.js.chat.events.console.ui.tmpl",
    "dashboard.js.chat.events.settings.state_normalize.core.tmpl",
    "dashboard.js.chat.events.settings.state_normalize.position_map.tmpl",
    "dashboard.js.chat.events.settings.state_normalize.render_read.tmpl",
    "dashboard.js.chat.events.settings.channels.tmpl",
    "dashboard.js.chat.events.settings.apply_actions.tmpl",
    "dashboard.js.chat.events.settings.bindings.tmpl",
    "dashboard.js.chat.events.map_selection.tmpl",
    "dashboard.js.chat.events.bindings.tmpl",
    "dashboard.js.ui.shared_controls.tmpl",
    "dashboard.js.chat.events.data_views.summary_map.tmpl",
    "dashboard.js.chat.events.data_views.nodes_saved.tmpl",
    "dashboard.js.chat.events.data_views.charts.zoom_timeline.tmpl",
    "dashboard.js.chat.events.data_views.charts.signal_online.tmpl",
    "dashboard.js.chat.events.data_views.charts.weekly.tmpl",
    "dashboard.js.chat.events.data_views.history_fetch.tmpl",
    "dashboard.js.chat.render.tmpl",
    "dashboard.js.runtime.views.packet_channels.tmpl",
    "dashboard.js.runtime.views.encryption.tmpl",
    "dashboard.js.runtime.views.raw_data.tmpl",
    "dashboard.js.runtime.poll.tmpl",
    "dashboard.js.runtime.boot.tmpl",
)


def build_dashboard_js(
    *,
    refresh_ms: int,
    node_history_hours: int,
    node_history_max_points: int,
    reset_ticker_scale_on_restart: bool = True,
) -> str:
    values = {
        "refresh_ms": refresh_ms,
        "node_history_hours": node_history_hours,
        "node_history_max_points": node_history_max_points,
        "reset_ticker_scale_on_restart": (
            1 if bool(reset_ticker_scale_on_restart) else 0
        ),
    }
    return "".join(
        _render_asset_template_helper(template_name, **values)
        for template_name in _DASHBOARD_JS_TEMPLATE_PARTS
    )
