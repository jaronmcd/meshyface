from .html_assets import render_asset_template as _render_asset_template_helper
from .config import DEFAULT_UI_PROFILE as _DEFAULT_UI_PROFILE

_DASHBOARD_JS_TEMPLATE_PARTS = (
    "dashboard.js.bootstrap.map.setup_emoji.base.tmpl",
    "dashboard.js.bootstrap.map.setup_emoji.catalog.tmpl",
    "dashboard.js.bootstrap.map.setup_emoji.state.constants_core.tmpl",
    "dashboard.js.bootstrap.map.setup_emoji.state.runtime_primary.tmpl",
    "dashboard.js.bootstrap.map.setup_emoji.state.runtime_games_chat.tmpl",
    "dashboard.js.bootstrap.map.setup_emoji.state.runtime_map_history.tmpl",
    "dashboard.js.bootstrap.map.offline_basemap.atlas_prep.tmpl",
    "dashboard.js.bootstrap.map.offline_basemap.atlas_layers.tmpl",
    "dashboard.js.bootstrap.map.offline_basemap.mode_connectivity.tmpl",
    "dashboard.js.bootstrap.map.resize.tmpl",
    "dashboard.js.bootstrap.map.signal_heatmap.primitives_knobs.tmpl",
    "dashboard.js.bootstrap.map.signal_heatmap.scoring.tmpl",
    "dashboard.js.bootstrap.map.signal_heatmap.render_sync.tmpl",
    "dashboard.js.bootstrap.map.wheel.tmpl",
    "dashboard.js.bootstrap.tickers.metrics.core.tmpl",
    "dashboard.js.bootstrap.tickers.metrics.runtime_time.tmpl",
    "dashboard.js.bootstrap.tickers.metrics.theme.tmpl",
    "dashboard.js.bootstrap.tickers.preferences.tmpl",
    "dashboard.js.bootstrap.tickers.controls.settings_ui.tmpl",
    "dashboard.js.bootstrap.tickers.controls.bindings_metric.tmpl",
    "dashboard.js.bootstrap.tickers.controls.preferences_map_lines.tmpl",
    "dashboard.js.bootstrap.tickers.controls.signal_heatmap_controls.tmpl",
    "dashboard.js.bootstrap.shared.chat_time_utils.tmpl",
    "dashboard.js.bootstrap.shared.telemetry_local.tmpl",
    "dashboard.js.bootstrap.shared.ticker_signal_gps.tmpl",
    "dashboard.js.bootstrap.shared.ticker_node_system.tmpl",
    "dashboard.js.bootstrap.shared.radio_status_freshness.tmpl",
    "dashboard.js.chat.state.core.chat.delivery_reactions.telemetry_geo.tmpl",
    "dashboard.js.chat.state.core.chat.delivery_reactions.ack_delivery.tmpl",
    "dashboard.js.chat.state.core.chat.delivery_reactions.reaction_popover.tmpl",
    "dashboard.js.chat.state.core.chat.channels_notifications.tmpl",
    "dashboard.js.chat.state.core.chat.bot_quick_actions.tmpl",
    "dashboard.js.chat.state.core.bot_history.sniffer_ingest.tmpl",
    "dashboard.js.chat.state.core.bot_history.history_store.tmpl",
    "dashboard.js.chat.state.core.bot_history.history_response_sync.tmpl",
    "dashboard.js.chat.state.core.bot_history.settings_tabs_ui.tmpl",
    "dashboard.js.chat.state.core.bot_history.sniffer_tab.tmpl",
    "dashboard.js.chat.state.core.bot_history.tmpl",
    "dashboard.js.chat.state.core.bot_controls.tmpl",
    "dashboard.js.chat.state.channels.labels_menu.tmpl",
    "dashboard.js.chat.state.channels.options_controls.tmpl",
    "dashboard.js.chat.state.channels.bindings_modes.tmpl",
    "dashboard.js.chat.state.games.reversi_local.protocol_invites.tmpl",
    "dashboard.js.chat.state.games.reversi_local.board_state.tmpl",
    "dashboard.js.chat.state.games.reversi_local.persistence_refresh.tmpl",
    "dashboard.js.chat.state.games.classic.checkers.helpers_moves.tmpl",
    "dashboard.js.chat.state.games.classic.checkers.state_refresh.tmpl",
    "dashboard.js.chat.state.games.classic.checkers.move_handlers.tmpl",
    "dashboard.js.chat.state.games.classic.checkers.render_status.tmpl",
    "dashboard.js.chat.state.games.classic.checkers.tmpl",
    "dashboard.js.chat.state.games.classic.chess.tmpl",
    "dashboard.js.chat.state.games.classic.poker.setup.tmpl",
    "dashboard.js.chat.state.games.classic.poker.flow.round_setup.tmpl",
    "dashboard.js.chat.state.games.classic.poker.flow.hand_eval_showdown.tmpl",
    "dashboard.js.chat.state.games.classic.poker.flow.actions_draw.tmpl",
    "dashboard.js.chat.state.games.classic.poker.flow.lifecycle_controls.tmpl",
    "dashboard.js.chat.state.games.classic.poker.flow.tmpl",
    "dashboard.js.chat.state.games.classic.poker.render.tmpl",
    "dashboard.js.chat.state.games.network.board_links.core.tmpl",
    "dashboard.js.chat.state.games.network.board_links.sync_ui.tmpl",
    "dashboard.js.chat.state.games.network.board_links.actions.tmpl",
    "dashboard.js.chat.state.games.network.reversi_link.protocol_sync.tmpl",
    "dashboard.js.chat.state.games.network.reversi_link.move_runtime.tmpl",
    "dashboard.js.chat.state.games.network.reversi_link.render_controls.tmpl",
    "dashboard.js.chat.state.games.network.reversi_link.session_actions.tmpl",
    "dashboard.js.chat.state.games.network.reversi_link.tmpl",
    "dashboard.js.chat.state.games.ui.tmpl",
    "dashboard.js.chat.state.messaging.peers.tmpl",
    "dashboard.js.chat.state.messaging.emoji_search.tmpl",
    "dashboard.js.chat.state.messaging.send_flow.tmpl",
    "dashboard.js.chat.state.messaging.emoji_ui.tmpl",
    "dashboard.js.chat.state.files.protocol.codec_flow.tmpl",
    "dashboard.js.chat.state.files.protocol.ui_send.tmpl",
    "dashboard.js.chat.state.files.protocol.session_state.tmpl",
    "dashboard.js.chat.state.files.frames.collect_state.tmpl",
    "dashboard.js.chat.state.files.frames.rows_build.tmpl",
    "dashboard.js.chat.state.files.frames.ack_match_helpers.tmpl",
    "dashboard.js.chat.state.files.maintenance.ack_frames.tmpl",
    "dashboard.js.chat.state.files.maintenance.outgoing_sessions.tmpl",
    "dashboard.js.chat.state.files.maintenance.runner.tmpl",
    "dashboard.js.chat.state.files.view.tmpl",
    "dashboard.js.chat.events.core.identity.node_self.tmpl",
    "dashboard.js.chat.events.core.identity.favorites_selection.search_dropdowns.tmpl",
    "dashboard.js.chat.events.core.identity.favorites_selection.favorites_state_ui.tmpl",
    "dashboard.js.chat.events.core.identity.favorites_selection.selection_cache.tmpl",
    "dashboard.js.chat.events.core.identity.favorites_selection.topbar_map_title.tmpl",
    "dashboard.js.chat.events.core.identity.favorites_selection.tmpl",
    "dashboard.js.chat.events.core.identity.text_utils.tmpl",
    "dashboard.js.chat.events.core.layout_tables.split_state_loaders.tmpl",
    "dashboard.js.chat.events.core.layout_tables.resizable_columns.tmpl",
    "dashboard.js.chat.events.core.layout_tables.split_state_persist.tmpl",
    "dashboard.js.chat.events.core.layout_tables.tmpl",
    "dashboard.js.chat.events.core.notifications.notices.message_preview_history.tmpl",
    "dashboard.js.chat.events.core.notifications.notices.persist_track.tmpl",
    "dashboard.js.chat.events.core.notifications.notices.notification_counts.tmpl",
    "dashboard.js.chat.events.core.notifications.notices.autodismiss_filters.tmpl",
    "dashboard.js.chat.events.core.notifications.notices.tmpl",
    "dashboard.js.chat.events.core.notifications.menus.tmpl",
    "dashboard.js.chat.events.core.notifications.unread.tmpl",
    "dashboard.js.chat.events.core.navigation.layout.tmpl",
    "dashboard.js.chat.events.core.navigation.splitters.tmpl",
    "dashboard.js.chat.events.core.navigation.tablesort.tmpl",
    "dashboard.js.chat.events.console.session.core.tmpl",
    "dashboard.js.chat.events.console.session.state.tmpl",
    "dashboard.js.chat.events.console.session.interaction.tmpl",
    "dashboard.js.chat.events.console.commands.helpers.tmpl",
    "dashboard.js.chat.events.console.commands.registry.tmpl",
    "dashboard.js.chat.events.console.formatting.tmpl",
    "dashboard.js.chat.events.console.ui.tmpl",
    "dashboard.js.chat.events.settings.state_normalize.cache_identity.tmpl",
    "dashboard.js.chat.events.settings.state_normalize.accessors_extractors.tmpl",
    "dashboard.js.chat.events.settings.state_normalize.normalize_helpers.tmpl",
    "dashboard.js.chat.events.settings.state_normalize.editors_tabs_geo.tmpl",
    "dashboard.js.chat.events.settings.state_normalize.position_map.source_cache_parsing.tmpl",
    "dashboard.js.chat.events.settings.state_normalize.position_map.state_resolution.tmpl",
    "dashboard.js.chat.events.settings.state_normalize.position_map.ui_bootstrap_tiles.tmpl",
    "dashboard.js.chat.events.settings.state_normalize.position_map.input_sync_render.tmpl",
    "dashboard.js.chat.events.settings.state_normalize.render_read.tmpl",
    "dashboard.js.chat.events.settings.channels.table.tmpl",
    "dashboard.js.chat.events.settings.channels.reading.tmpl",
    "dashboard.js.chat.events.settings.channels.parse.tmpl",
    "dashboard.js.chat.events.settings.apply_actions.config.tmpl",
    "dashboard.js.chat.events.settings.apply_actions.modules.tmpl",
    "dashboard.js.chat.events.settings.apply_actions.radio_ops.tmpl",
    "dashboard.js.chat.events.settings.bindings.tmpl",
    "dashboard.js.chat.events.map_selection.tmpl",
    "dashboard.js.chat.events.bindings.tmpl",
    "dashboard.js.ui.shared_controls.tmpl",
    "dashboard.js.chat.events.data_views.summary_map.summary.tmpl",
    "dashboard.js.chat.events.data_views.summary_map.map_helpers.tmpl",
    "dashboard.js.chat.events.data_views.summary_map.map_render.tmpl",
    "dashboard.js.chat.events.data_views.nodes_saved.nodes_table.tmpl",
    "dashboard.js.chat.events.data_views.nodes_saved.saved_helpers.tmpl",
    "dashboard.js.chat.events.data_views.nodes_saved.saved_views.tmpl",
    "dashboard.js.chat.events.data_views.charts.zoom_timeline.signal_zoom.tmpl",
    "dashboard.js.chat.events.data_views.charts.zoom_timeline.history_trend_zoom.tmpl",
    "dashboard.js.chat.events.data_views.charts.zoom_timeline.timeline_render.tmpl",
    "dashboard.js.chat.events.data_views.charts.zoom_timeline.signal_timeline.tmpl",
    "dashboard.js.chat.events.data_views.charts.zoom_timeline.tmpl",
    "dashboard.js.chat.events.data_views.charts.signal_online.tmpl",
    "dashboard.js.chat.events.data_views.charts.weekly.states.tmpl",
    "dashboard.js.chat.events.data_views.charts.weekly.chart_render.tmpl",
    "dashboard.js.chat.events.data_views.charts.weekly.summary.tmpl",
    "dashboard.js.chat.events.data_views.charts.weekly.tmpl",
    "dashboard.js.chat.events.data_views.history_fetch.chat_notifications.tmpl",
    "dashboard.js.chat.events.data_views.history_fetch.node_history_pipeline.tmpl",
    "dashboard.js.chat.events.data_views.history_fetch.summary_hydration.tmpl",
    "dashboard.js.chat.events.data_views.history_fetch.render_traffic_tables.tmpl",
    "dashboard.js.chat.events.data_views.history_fetch.tmpl",
    "dashboard.js.chat.render.identity_reactions.tmpl",
    "dashboard.js.chat.render.feed_prep.tmpl",
    "dashboard.js.chat.render.feed_items.tmpl",
    "dashboard.js.chat.render.roster_finalize.tmpl",
    "dashboard.js.chat.render.tmpl",
    "dashboard.js.runtime.views.packet_channels.channels_view.tmpl",
    "dashboard.js.runtime.views.packet_channels.encryption_rows.tmpl",
    "dashboard.js.runtime.views.packet_channels.encryption_trend.tmpl",
    "dashboard.js.runtime.views.encryption.tmpl",
    "dashboard.js.runtime.views.raw_data.tmpl",
    "dashboard.js.runtime.views.remote.tmpl",
    "dashboard.js.runtime.poll.tmpl",
    "dashboard.js.runtime.boot.tmpl",
)


_CORE_UI_EXCLUDED_TEMPLATE_PREFIXES = (
    "dashboard.js.chat.state.files.",
    "dashboard.js.chat.state.games.classic.poker.",
    "dashboard.js.chat.state.core.bot_history.",
)
_CORE_UI_EXCLUDED_TEMPLATE_NAMES = {
    "dashboard.js.chat.state.core.bot_controls.tmpl",
}
_CORE_UI_STUB_TEMPLATE = "dashboard.js.profile.core_ui.noop_feature_hooks.tmpl"
_RUNTIME_BOOT_TEMPLATE = "dashboard.js.runtime.boot.tmpl"


def _normalize_ui_profile(raw_profile: object = None) -> str:
    token = str(raw_profile or "").strip().lower().replace("_", "-")
    if not token:
        token = str(_DEFAULT_UI_PROFILE or "").strip().lower().replace("_", "-")
    if token in {"core", "coreui", "core-ui"}:
        return "core-ui"
    return "full"


def _core_ui_part_excluded(template_name: str) -> bool:
    if template_name in _CORE_UI_EXCLUDED_TEMPLATE_NAMES:
        return True
    return any(
        template_name.startswith(prefix)
        for prefix in _CORE_UI_EXCLUDED_TEMPLATE_PREFIXES
    )


def _template_parts_for_profile(raw_profile: object = None) -> tuple[str, ...]:
    profile = _normalize_ui_profile(raw_profile)
    if profile == "full":
        return _DASHBOARD_JS_TEMPLATE_PARTS

    selected = [
        template_name
        for template_name in _DASHBOARD_JS_TEMPLATE_PARTS
        if not _core_ui_part_excluded(template_name)
    ]
    if _CORE_UI_STUB_TEMPLATE not in selected:
        try:
            runtime_boot_idx = selected.index(_RUNTIME_BOOT_TEMPLATE)
        except ValueError:
            runtime_boot_idx = len(selected)
        selected.insert(runtime_boot_idx, _CORE_UI_STUB_TEMPLATE)
    return tuple(selected)


def build_dashboard_js(
    *,
    refresh_ms: int,
    node_history_hours: int,
    node_history_max_points: int,
    reset_ticker_scale_on_restart: bool = True,
    ui_profile: str | None = None,
) -> str:
    selected_parts = _template_parts_for_profile(ui_profile)
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
        for template_name in selected_parts
    )
