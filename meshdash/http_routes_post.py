from hmac import compare_digest

from .api_chat import (
    handle_chat_send_post as _handle_chat_send_post_helper,
)
from .api_theme import (
    handle_theme_settings_post as _handle_theme_settings_post_helper,
)
from .api_radio import (
    handle_radio_settings_post as _handle_radio_settings_post_helper,
)
from .api_channels import (
    handle_channel_settings_post as _handle_channel_settings_post_helper,
)
from .api_bot import (
    handle_bot_settings_post as _handle_bot_settings_post_helper,
)
from .api_zork import (
    handle_standalone_zork_post as _handle_standalone_zork_post_helper,
)
from .http_handler_contracts import DashboardHttpHandler
from .http_route_contracts import DashboardPostRouteDependencies


_TOKEN_PROTECTED_WRITE_PATHS = {
    "/api/chat/send",
    "/api/games/zork",
    "/api/settings/radio",
    "/api/settings/channels",
    "/api/settings/theme",
    "/api/settings/bot",
}
_PRIVATE_MODE_BLOCKED_POST_PATHS = {
    "/api/chat/send",
    "/api/games/zork",
}


def _header_value(headers: object, name: str) -> str:
    if headers is None:
        return ""
    try:
        direct = headers.get(name)  # type: ignore[attr-defined]
    except Exception:
        direct = None
    if direct is not None:
        return str(direct)
    name_l = name.lower()
    for key, value in getattr(headers, "items", lambda: [])():
        try:
            if str(key).lower() == name_l:
                return str(value)
        except Exception:
            continue
    return ""


def _extract_request_api_token(handler: DashboardHttpHandler) -> str:
    auth_header = _header_value(getattr(handler, "headers", None), "Authorization").strip()
    if auth_header:
        parts = auth_header.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return str(parts[1]).strip()
    return _header_value(getattr(handler, "headers", None), "X-API-Token").strip()


def _record_write_auth_denied(deps: DashboardPostRouteDependencies) -> None:
    metrics = deps.api_metrics
    record_fn = getattr(metrics, "record_write_auth_denied", None)
    if callable(record_fn):
        record_fn()


def _record_private_mode_block(deps: DashboardPostRouteDependencies) -> None:
    metrics = deps.api_metrics
    record_fn = getattr(metrics, "record_private_mode_block", None)
    if callable(record_fn):
        record_fn()


def _write_request_is_authorized(
    handler: DashboardHttpHandler,
    *,
    deps: DashboardPostRouteDependencies,
) -> bool:
    required_token = str(deps.api_token or "").strip()
    if not required_token:
        return True
    supplied_token = _extract_request_api_token(handler)
    if not supplied_token:
        return False
    return compare_digest(supplied_token, required_token)


def handle_dashboard_post(
    handler: DashboardHttpHandler,
    *,
    path: str,
    deps: DashboardPostRouteDependencies,
) -> None:
    if deps.private_mode and path in _PRIVATE_MODE_BLOCKED_POST_PATHS:
        _record_private_mode_block(deps)
        deps.write_json_response_fn(
            handler,
            status_code=403,
            payload_obj={"ok": False, "error": "This endpoint is disabled in private mode"},
            no_store=True,
        )
        return

    if path in _TOKEN_PROTECTED_WRITE_PATHS and not _write_request_is_authorized(handler, deps=deps):
        _record_write_auth_denied(deps)
        deps.write_json_response_fn(
            handler,
            status_code=401,
            payload_obj={"ok": False, "error": "API token required for write endpoint"},
            no_store=True,
            extra_headers={"WWW-Authenticate": "Bearer"},
        )
        return

    if path == "/api/chat/send":
        _handle_chat_send_post_helper(
            handler,
            send_chat_fn=deps.send_chat_fn,
            to_int_fn=deps.to_int_fn,
            validate_content_length_fn=deps.validate_content_length_fn,
            parse_chat_send_request_fn=deps.parse_chat_send_request_fn,
            write_json_response_fn=deps.write_json_response_fn,
        )
        return

    if path == "/api/games/zork":
        _handle_standalone_zork_post_helper(
            handler,
            play_standalone_zork_fn=deps.play_standalone_zork_fn,
            to_int_fn=deps.to_int_fn,
            validate_content_length_fn=deps.validate_content_length_fn,
            parse_standalone_zork_request_fn=deps.parse_standalone_zork_request_fn,
            write_json_response_fn=deps.write_json_response_fn,
        )
        return

    if path == "/api/settings/radio":
        parse_radio_settings_request_fn = deps.parse_radio_settings_request_fn
        if parse_radio_settings_request_fn is None:
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={
                    "ok": False,
                    "error": "Radio settings are not enabled on this dashboard instance",
                },
            )
            return
        _handle_radio_settings_post_helper(
            handler,
            apply_radio_settings_fn=deps.apply_radio_settings_fn,
            to_int_fn=deps.to_int_fn,
            validate_content_length_fn=deps.validate_content_length_fn,
            parse_radio_settings_request_fn=parse_radio_settings_request_fn,
            write_json_response_fn=deps.write_json_response_fn,
        )
        return

    if path == "/api/settings/channels":
        parse_channel_settings_request_fn = deps.parse_channel_settings_request_fn
        if parse_channel_settings_request_fn is None:
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={
                    "ok": False,
                    "error": "Channel settings are not enabled on this dashboard instance",
                },
            )
            return
        _handle_channel_settings_post_helper(
            handler,
            apply_channel_settings_fn=deps.apply_channel_settings_fn,
            to_int_fn=deps.to_int_fn,
            validate_content_length_fn=deps.validate_content_length_fn,
            parse_channel_settings_request_fn=parse_channel_settings_request_fn,
            write_json_response_fn=deps.write_json_response_fn,
        )
        return

    if path == "/api/settings/theme":
        parse_theme_settings_request_fn = deps.parse_theme_settings_request_fn
        if parse_theme_settings_request_fn is None:
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={"ok": False, "error": "Theme settings are not enabled on this dashboard instance"},
            )
            return
        _handle_theme_settings_post_helper(
            handler,
            set_theme_preset_fn=deps.set_theme_preset_fn,
            to_int_fn=deps.to_int_fn,
            validate_content_length_fn=deps.validate_content_length_fn,
            parse_theme_settings_request_fn=parse_theme_settings_request_fn,
            write_json_response_fn=deps.write_json_response_fn,
        )
        return

    if path == "/api/settings/bot":
        parse_bot_settings_request_fn = deps.parse_bot_settings_request_fn
        if parse_bot_settings_request_fn is None:
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={"ok": False, "error": "Bot settings are not enabled on this dashboard instance"},
            )
            return
        _handle_bot_settings_post_helper(
            handler,
            apply_bot_settings_fn=deps.apply_bot_settings_fn,
            to_int_fn=deps.to_int_fn,
            validate_content_length_fn=deps.validate_content_length_fn,
            parse_bot_settings_request_fn=parse_bot_settings_request_fn,
            write_json_response_fn=deps.write_json_response_fn,
        )
        return

    deps.write_json_response_fn(
        handler,
        status_code=404,
        payload_obj={"ok": False, "error": "Not Found"},
    )
