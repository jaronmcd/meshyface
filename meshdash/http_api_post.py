from typing import Callable, Protocol
from urllib.parse import urlparse

from .api_input_chat import parse_chat_send_request, validate_content_length
from .api_input_radio import parse_radio_settings_request
from .api_input_channels import parse_channel_settings_request
from .api_input_bot import parse_bot_settings_request
from .api_input_theme import parse_theme_settings_request
from .api_input_custom_telemetry import parse_custom_telemetry_settings_request
from .api_input_zork import parse_standalone_zork_request
from .helpers import to_int
from .http_handler_contracts import DashboardHttpHandler
from .http_responses import write_json_response
from .http_route_contracts import (
    ApiMetricsRecorder,
    ApplyRadioSettingsFn,
    ApplyChannelSettingsFn,
    ApplyBotSettingsFn,
    DashboardPostRouteDependencies,
    PlayStandaloneZorkFn,
    SendChatFn,
    SetCustomTelemetrySettingsFn,
    SetThemePresetFn,
    ToIntFn,
)
from .http_routes import handle_dashboard_post


class ParsedUrl(Protocol):
    path: str


def build_post_route_dependencies(
    *,
    send_chat_fn: SendChatFn | None,
    set_theme_preset_fn: SetThemePresetFn | None = None,
    apply_radio_settings_fn: ApplyRadioSettingsFn | None = None,
    apply_channel_settings_fn: ApplyChannelSettingsFn | None = None,
    apply_bot_settings_fn: ApplyBotSettingsFn | None = None,
    set_custom_telemetry_settings_fn: SetCustomTelemetrySettingsFn | None = None,
    play_standalone_zork_fn: PlayStandaloneZorkFn | None = None,
    api_token: str | None = None,
    private_mode: bool = False,
    api_metrics: ApiMetricsRecorder | None = None,
    to_int_fn: ToIntFn = to_int,
) -> DashboardPostRouteDependencies:
    clean_api_token = str(api_token or "").strip() or None
    return DashboardPostRouteDependencies(
        send_chat_fn=send_chat_fn,
        to_int_fn=to_int_fn,
        validate_content_length_fn=validate_content_length,
        parse_chat_send_request_fn=parse_chat_send_request,
        write_json_response_fn=write_json_response,
        set_theme_preset_fn=set_theme_preset_fn,
        parse_theme_settings_request_fn=parse_theme_settings_request,
        set_custom_telemetry_settings_fn=set_custom_telemetry_settings_fn,
        parse_custom_telemetry_settings_request_fn=parse_custom_telemetry_settings_request,
        apply_radio_settings_fn=apply_radio_settings_fn,
        parse_radio_settings_request_fn=parse_radio_settings_request,
        apply_channel_settings_fn=apply_channel_settings_fn,
        parse_channel_settings_request_fn=parse_channel_settings_request,
        apply_bot_settings_fn=apply_bot_settings_fn,
        parse_bot_settings_request_fn=parse_bot_settings_request,
        play_standalone_zork_fn=play_standalone_zork_fn,
        parse_standalone_zork_request_fn=parse_standalone_zork_request,
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
