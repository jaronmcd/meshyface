from .api_metrics import DashboardApiMetrics
from .http_api_get import build_get_route_dependencies, make_get_dispatch
from .http_api_post import build_post_route_dependencies, make_post_dispatch
from .http_handler import build_dashboard_handler_class
from .helpers import to_int
from .http_route_contracts import (
    GetThemeSettingsFn,
    NodeHistoryFn,
    OnlineActivityFn,
    SummaryMetricsHistoryFn,
    SendChatFn,
    SendMeshyfaceProfileFn,
    SetThemePresetFn,
    StateFn,
    ToIntFn,
)


def make_http_handler(
    html_text: str,
    state_fn: StateFn,
    node_history_fn: NodeHistoryFn | None = None,
    online_activity_fn: OnlineActivityFn | None = None,
    summary_metrics_fn: SummaryMetricsHistoryFn | None = None,
    send_chat_fn: SendChatFn | None = None,
    send_meshyface_profile_fn: SendMeshyfaceProfileFn | None = None,
    get_theme_settings_fn: GetThemeSettingsFn | None = None,
    set_theme_preset_fn: SetThemePresetFn | None = None,
    api_token: str | None = None,
    private_mode: bool = False,
    default_node_history_hours: int = 72,
    to_int_fn: ToIntFn = to_int,
):
    api_metrics = DashboardApiMetrics()
    apply_radio_settings_fn = getattr(state_fn, "apply_radio_settings_fn", None)
    apply_channel_settings_fn = getattr(state_fn, "apply_channel_settings_fn", None)
    state_meshyface_profile_fn = getattr(state_fn, "send_meshyface_profile_fn", None)
    get_bbs_settings_fn = getattr(state_fn, "get_bbs_settings_fn", None)
    get_bbs_host_runtime_fn = getattr(state_fn, "get_bbs_host_runtime_fn", None)
    set_bbs_settings_fn = getattr(state_fn, "set_bbs_settings_fn", None)
    set_zork_bot_enabled_fn = getattr(state_fn, "set_zork_bot_enabled_fn", None)
    set_ping_bot_enabled_fn = getattr(state_fn, "set_ping_bot_enabled_fn", None)
    set_ping_bot_message_only_fn = getattr(state_fn, "set_ping_bot_message_only_fn", None)
    manage_zork_bot_fn = getattr(state_fn, "manage_zork_bot_fn", None)
    start_bbs_host_fn = getattr(state_fn, "start_bbs_host_fn", None)
    stop_bbs_host_fn = getattr(state_fn, "stop_bbs_host_fn", None)
    append_bbs_host_post_fn = getattr(state_fn, "append_bbs_host_post_fn", None)
    get_custom_telemetry_settings_fn = getattr(state_fn, "get_custom_telemetry_settings_fn", None)
    set_custom_telemetry_settings_fn = getattr(state_fn, "set_custom_telemetry_settings_fn", None)
    set_raw_packet_capture_settings_fn = getattr(state_fn, "set_raw_packet_capture_settings_fn", None)
    play_standalone_zork_fn = getattr(state_fn, "play_standalone_zork_fn", None)
    run_network_tool_fn = getattr(state_fn, "run_network_tool_fn", None)
    schedule_backend_restart_fn = getattr(state_fn, "schedule_backend_restart_fn", None)
    clean_api_token = str(api_token or "").strip() or None
    get_deps = build_get_route_dependencies(
        html_text=html_text,
        state_fn=state_fn,
        node_history_fn=node_history_fn,
        online_activity_fn=online_activity_fn,
        summary_metrics_fn=summary_metrics_fn,
        get_theme_settings_fn=get_theme_settings_fn,
        get_bbs_settings_fn=get_bbs_settings_fn,
        get_bbs_host_runtime_fn=get_bbs_host_runtime_fn,
        get_custom_telemetry_settings_fn=get_custom_telemetry_settings_fn,
        private_mode=bool(private_mode),
        api_metrics=api_metrics,
        default_node_history_hours=default_node_history_hours,
        to_int_fn=to_int_fn,
    )
    post_deps = build_post_route_dependencies(
        send_chat_fn=send_chat_fn,
        send_meshyface_profile_fn=(
            send_meshyface_profile_fn
            if callable(send_meshyface_profile_fn)
            else (
                state_meshyface_profile_fn
                if callable(state_meshyface_profile_fn)
                else None
            )
        ),
        set_theme_preset_fn=set_theme_preset_fn,
        set_bbs_settings_fn=set_bbs_settings_fn,
        set_zork_bot_enabled_fn=set_zork_bot_enabled_fn,
        set_ping_bot_enabled_fn=set_ping_bot_enabled_fn,
        set_ping_bot_message_only_fn=set_ping_bot_message_only_fn,
        manage_zork_bot_fn=manage_zork_bot_fn,
        start_bbs_host_fn=start_bbs_host_fn,
        stop_bbs_host_fn=stop_bbs_host_fn,
        append_bbs_host_post_fn=append_bbs_host_post_fn,
        apply_radio_settings_fn=apply_radio_settings_fn,
        apply_channel_settings_fn=apply_channel_settings_fn,
        set_custom_telemetry_settings_fn=set_custom_telemetry_settings_fn,
        set_raw_packet_capture_settings_fn=set_raw_packet_capture_settings_fn,
        play_standalone_zork_fn=play_standalone_zork_fn,
        run_network_tool_fn=run_network_tool_fn,
        schedule_backend_restart_fn=(
            schedule_backend_restart_fn if callable(schedule_backend_restart_fn) else None
        ),
        api_token=clean_api_token,
        private_mode=bool(private_mode),
        api_metrics=api_metrics,
        to_int_fn=to_int_fn,
    )

    return build_dashboard_handler_class(
        dispatch_get_fn=make_get_dispatch(deps=get_deps),
        dispatch_post_fn=make_post_dispatch(deps=post_deps),
    )
