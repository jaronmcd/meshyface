from .html_assets import render_asset_template as _render_asset_template_helper

_DASHBOARD_JS_TEMPLATE_PARTS = (
    "dashboard.js.bootstrap.map.tmpl",
    "dashboard.js.bootstrap.tickers.tmpl",
    "dashboard.js.bootstrap.shared.tmpl",
    "dashboard.js.chat.state.core.tmpl",
    "dashboard.js.chat.state.channels.tmpl",
    "dashboard.js.chat.state.games.tmpl",
    "dashboard.js.chat.state.messaging.tmpl",
    "dashboard.js.chat.state.files.tmpl",
    "dashboard.js.chat.events.core.tmpl",
    "dashboard.js.chat.events.console.tmpl",
    "dashboard.js.chat.events.settings.tmpl",
    "dashboard.js.chat.events.map_selection.tmpl",
    "dashboard.js.chat.events.bindings.tmpl",
    "dashboard.js.chat.events.data_views.summary_map.tmpl",
    "dashboard.js.chat.events.data_views.nodes_saved.tmpl",
    "dashboard.js.chat.events.data_views.charts.tmpl",
    "dashboard.js.chat.events.data_views.history_fetch.tmpl",
    "dashboard.js.chat.render.tmpl",
    "dashboard.js.runtime.views.tmpl",
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
