from importlib import import_module
from typing import Callable, Protocol
from urllib.parse import urlparse

from .helpers import to_int
from .http_handler_contracts import DashboardHttpHandler
from .http_responses import write_json_response
from .http_route_contracts import (
    ApiMetricsRecorder,
    ApplyRadioSettingsFn,
    ApplyChannelSettingsFn,
    DashboardPostRouteDependencies,
    PlayStandaloneZorkFn,
    AppendBbsHostPostFn,
    ManageZorkBotFn,
    StartBbsHostFn,
    StopBbsHostFn,
    RunNetworkToolFn,
    ScheduleBackendRestartFn,
    SendChatFn,
    SetBbsSettingsFn,
    SetPingBotEnabledFn,
    SetPingBotMessageOnlyFn,
    SetCustomTelemetrySettingsFn,
    SetThemePresetFn,
    SetZorkBotEnabledFn,
    ToIntFn,
)
from .http_routes import handle_dashboard_post


class ParsedUrl(Protocol):
    path: str


def _load_optional_callable(module_path: str, attr_name: str):
    try:
        module = import_module(module_path, package=__package__)
    except Exception:
        return None
    value = getattr(module, attr_name, None)
    if callable(value):
        return value
    return None


def _validate_content_length_unavailable(*_args, **_kwargs) -> int:
    raise ValueError("Chat send is not enabled on this dashboard instance")


def _parse_chat_send_request_unavailable(*_args, **_kwargs):
    raise ValueError("Chat send is not enabled on this dashboard instance")


validate_content_length = _load_optional_callable(".api_input_chat", "validate_content_length")
parse_chat_send_request = _load_optional_callable(".api_input_chat", "parse_chat_send_request")
parse_radio_settings_request = _load_optional_callable(".api_input_radio", "parse_radio_settings_request")
parse_channel_settings_request = _load_optional_callable(".api_input_channels", "parse_channel_settings_request")
parse_theme_settings_request = _load_optional_callable(".api_input_theme", "parse_theme_settings_request")
parse_bbs_settings_request = _load_optional_callable(".api_input_bbs", "parse_bbs_settings_request")
parse_bbs_host_request = _load_optional_callable(".api_input_bbs", "parse_bbs_host_request")
parse_zork_bot_toggle_request = _load_optional_callable(
    ".api_input_bots",
    "parse_zork_bot_toggle_request",
)
parse_custom_telemetry_settings_request = _load_optional_callable(
    ".api_input_custom_telemetry",
    "parse_custom_telemetry_settings_request",
)
parse_standalone_zork_request = _load_optional_callable(".api_input_zork", "parse_standalone_zork_request")
parse_network_tool_request = _load_optional_callable(
    ".api_input_network_tools",
    "parse_network_tool_request",
)


def build_post_route_dependencies(
    *,
    send_chat_fn: SendChatFn | None,
    set_theme_preset_fn: SetThemePresetFn | None = None,
    set_bbs_settings_fn: SetBbsSettingsFn | None = None,
    set_zork_bot_enabled_fn: SetZorkBotEnabledFn | None = None,
    set_ping_bot_enabled_fn: SetPingBotEnabledFn | None = None,
    set_ping_bot_message_only_fn: SetPingBotMessageOnlyFn | None = None,
    manage_zork_bot_fn: ManageZorkBotFn | None = None,
    start_bbs_host_fn: StartBbsHostFn | None = None,
    stop_bbs_host_fn: StopBbsHostFn | None = None,
    append_bbs_host_post_fn: AppendBbsHostPostFn | None = None,
    apply_radio_settings_fn: ApplyRadioSettingsFn | None = None,
    apply_channel_settings_fn: ApplyChannelSettingsFn | None = None,
    set_custom_telemetry_settings_fn: SetCustomTelemetrySettingsFn | None = None,
    play_standalone_zork_fn: PlayStandaloneZorkFn | None = None,
    run_network_tool_fn: RunNetworkToolFn | None = None,
    schedule_backend_restart_fn: ScheduleBackendRestartFn | None = None,
    api_token: str | None = None,
    private_mode: bool = False,
    api_metrics: ApiMetricsRecorder | None = None,
    to_int_fn: ToIntFn = to_int,
) -> DashboardPostRouteDependencies:
    clean_api_token = str(api_token or "").strip() or None
    return DashboardPostRouteDependencies(
        send_chat_fn=send_chat_fn,
        to_int_fn=to_int_fn,
        validate_content_length_fn=(
            validate_content_length or _validate_content_length_unavailable
        ),
        parse_chat_send_request_fn=(
            parse_chat_send_request or _parse_chat_send_request_unavailable
        ),
        write_json_response_fn=write_json_response,
        set_theme_preset_fn=set_theme_preset_fn,
        parse_theme_settings_request_fn=parse_theme_settings_request,
        set_bbs_settings_fn=set_bbs_settings_fn,
        parse_bbs_settings_request_fn=parse_bbs_settings_request,
        set_zork_bot_enabled_fn=set_zork_bot_enabled_fn,
        set_ping_bot_enabled_fn=set_ping_bot_enabled_fn,
        set_ping_bot_message_only_fn=set_ping_bot_message_only_fn,
        manage_zork_bot_fn=manage_zork_bot_fn,
        parse_zork_bot_toggle_request_fn=parse_zork_bot_toggle_request,
        start_bbs_host_fn=start_bbs_host_fn,
        stop_bbs_host_fn=stop_bbs_host_fn,
        append_bbs_host_post_fn=append_bbs_host_post_fn,
        parse_bbs_host_request_fn=parse_bbs_host_request,
        set_custom_telemetry_settings_fn=set_custom_telemetry_settings_fn,
        parse_custom_telemetry_settings_request_fn=parse_custom_telemetry_settings_request,
        apply_radio_settings_fn=apply_radio_settings_fn,
        parse_radio_settings_request_fn=parse_radio_settings_request,
        apply_channel_settings_fn=apply_channel_settings_fn,
        parse_channel_settings_request_fn=parse_channel_settings_request,
        play_standalone_zork_fn=play_standalone_zork_fn,
        parse_standalone_zork_request_fn=parse_standalone_zork_request,
        run_network_tool_fn=run_network_tool_fn,
        parse_network_tool_request_fn=parse_network_tool_request,
        schedule_backend_restart_fn=schedule_backend_restart_fn,
        api_token=clean_api_token,
        private_mode=bool(private_mode),
        api_metrics=api_metrics,
    )


def dispatch_post_request(
    handler: DashboardHttpHandler,
    *,
    deps: DashboardPostRouteDependencies,
    parse_url_fn: Callable[[str], ParsedUrl] = urlparse,
    handle_post_fn=handle_dashboard_post,
) -> None:
    parsed = parse_url_fn(handler.path)
    handle_post_fn(
        handler,
        path=parsed.path,
        deps=deps,
    )


def make_post_dispatch(
    *,
    deps: DashboardPostRouteDependencies,
):
    def _dispatch_post(handler: DashboardHttpHandler) -> None:
        dispatch_post_request(handler, deps=deps)

    return _dispatch_post
