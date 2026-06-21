from importlib import import_module
import json
from hmac import compare_digest

from .http_handler_contracts import DashboardHttpHandler
from .http_route_contracts import DashboardPostRouteDependencies
from .api_system_update import (
    run_update_from_github as _run_update_from_github_helper,
    sync_update_branches_from_github as _sync_update_branches_from_github_helper,
)


_TOKEN_PROTECTED_WRITE_PATHS = {
    "/api/chat/send",
    "/api/games/zork",
    "/api/tools/network",
    "/api/bots/zork",
    "/api/bots/ping",
    "/api/bbs/host",
    "/api/settings/radio",
    "/api/settings/channels",
    "/api/settings/theme",
    "/api/settings/bbs",
    "/api/settings/custom_telemetry",
    "/api/settings/raw_packets",
    "/api/system/update",
    "/api/system/update/sync",
    "/api/system/restart",
}
_PRIVATE_MODE_BLOCKED_POST_PATHS = {
    "/api/chat/send",
    "/api/games/zork",
    "/api/tools/network",
    "/api/bots/zork",
    "/api/bots/ping",
}


def _load_optional_handler(module_path: str, attr_name: str):
    try:
        module = import_module(module_path, package=__package__)
    except Exception:
        return None
    value = getattr(module, attr_name, None)
    if callable(value):
        return value
    return None


_handle_chat_send_post_helper = _load_optional_handler(".api_chat", "handle_chat_send_post")
_handle_theme_settings_post_helper = _load_optional_handler(
    ".api_theme",
    "handle_theme_settings_post",
)
_handle_bbs_settings_post_helper = _load_optional_handler(
    ".api_bbs",
    "handle_bbs_settings_post",
)
_handle_bbs_host_post_helper = _load_optional_handler(
    ".api_bbs",
    "handle_bbs_host_post",
)
_handle_custom_telemetry_settings_post_helper = _load_optional_handler(
    ".api_custom_telemetry",
    "handle_custom_telemetry_settings_post",
)
_handle_raw_packet_capture_settings_post_helper = _load_optional_handler(
    ".api_raw_packets",
    "handle_raw_packet_capture_settings_post",
)
_handle_radio_settings_post_helper = _load_optional_handler(".api_radio", "handle_radio_settings_post")
_handle_channel_settings_post_helper = _load_optional_handler(
    ".api_channels",
    "handle_channel_settings_post",
)
_handle_standalone_zork_post_helper = _load_optional_handler(
    ".api_zork",
    "handle_standalone_zork_post",
)
_handle_network_tool_post_helper = _load_optional_handler(
    ".api_network_tools",
    "handle_network_tool_post",
)
_handle_zork_bot_toggle_post_helper = _load_optional_handler(
    ".api_bots",
    "handle_zork_bot_toggle_post",
)


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


def _read_system_update_request(handler: DashboardHttpHandler) -> dict[str, object]:
    raw_length = _header_value(getattr(handler, "headers", None), "Content-Length").strip()
    if not raw_length:
        return {}
    try:
        length = int(raw_length)
    except ValueError as exc:
        raise ValueError("invalid Content-Length") from exc
    if length < 0 or length > 4096:
        raise ValueError("system update request body is too large")
    if length == 0:
        return {}
    raw_body = handler.rfile.read(length)
    if not raw_body:
        return {}
    try:
        parsed = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid JSON request body") from exc
    if not isinstance(parsed, dict):
        raise ValueError("system update request body must be an object")
    return parsed


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
        if not callable(_handle_chat_send_post_helper):
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={"ok": False, "error": "Chat send is not enabled on this dashboard instance"},
            )
            return
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
        if not callable(_handle_standalone_zork_post_helper):
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={"ok": False, "error": "Standalone Zork is not enabled on this dashboard instance"},
            )
            return
        _handle_standalone_zork_post_helper(
            handler,
            play_standalone_zork_fn=deps.play_standalone_zork_fn,
            to_int_fn=deps.to_int_fn,
            validate_content_length_fn=deps.validate_content_length_fn,
            parse_standalone_zork_request_fn=deps.parse_standalone_zork_request_fn,
            write_json_response_fn=deps.write_json_response_fn,
        )
        return

    if path == "/api/tools/network":
        parse_network_tool_request_fn = deps.parse_network_tool_request_fn
        if parse_network_tool_request_fn is None or not callable(_handle_network_tool_post_helper):
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={"ok": False, "error": "Network tools are not enabled on this dashboard instance"},
            )
            return
        _handle_network_tool_post_helper(
            handler,
            run_network_tool_fn=deps.run_network_tool_fn,
            to_int_fn=deps.to_int_fn,
            validate_content_length_fn=deps.validate_content_length_fn,
            parse_network_tool_request_fn=parse_network_tool_request_fn,
            write_json_response_fn=deps.write_json_response_fn,
        )
        return

    if path in {"/api/bots/zork", "/api/bots/ping"}:
        parse_zork_bot_toggle_request_fn = deps.parse_zork_bot_toggle_request_fn
        if parse_zork_bot_toggle_request_fn is None or not callable(_handle_zork_bot_toggle_post_helper):
            error_label = "Ping" if path == "/api/bots/ping" else "Zork"
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={"ok": False, "error": f"{error_label} bot runtime is not enabled on this dashboard instance"},
            )
            return
        _handle_zork_bot_toggle_post_helper(
            handler,
            set_zork_bot_enabled_fn=deps.set_zork_bot_enabled_fn,
            set_ping_bot_enabled_fn=deps.set_ping_bot_enabled_fn,
            set_ping_bot_message_only_fn=deps.set_ping_bot_message_only_fn,
            manage_zork_bot_fn=deps.manage_zork_bot_fn,
            default_command="ping" if path == "/api/bots/ping" else "zork",
            to_int_fn=deps.to_int_fn,
            validate_content_length_fn=deps.validate_content_length_fn,
            parse_zork_bot_toggle_request_fn=parse_zork_bot_toggle_request_fn,
            write_json_response_fn=deps.write_json_response_fn,
        )
        return

    if path == "/api/settings/radio":
        parse_radio_settings_request_fn = deps.parse_radio_settings_request_fn
        if parse_radio_settings_request_fn is None or not callable(_handle_radio_settings_post_helper):
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
        if parse_channel_settings_request_fn is None or not callable(_handle_channel_settings_post_helper):
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
        if parse_theme_settings_request_fn is None or not callable(_handle_theme_settings_post_helper):
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

    if path == "/api/settings/bbs":
        parse_bbs_settings_request_fn = deps.parse_bbs_settings_request_fn
        if parse_bbs_settings_request_fn is None or not callable(_handle_bbs_settings_post_helper):
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={"ok": False, "error": "BBS settings are not enabled on this dashboard instance"},
            )
            return
        _handle_bbs_settings_post_helper(
            handler,
            set_bbs_settings_fn=deps.set_bbs_settings_fn,
            to_int_fn=deps.to_int_fn,
            validate_content_length_fn=deps.validate_content_length_fn,
            parse_bbs_settings_request_fn=parse_bbs_settings_request_fn,
            write_json_response_fn=deps.write_json_response_fn,
        )
        return

    if path == "/api/bbs/host":
        parse_bbs_host_request_fn = deps.parse_bbs_host_request_fn
        if parse_bbs_host_request_fn is None or not callable(_handle_bbs_host_post_helper):
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={"ok": False, "error": "BBS host runtime is not enabled on this dashboard instance"},
            )
            return
        _handle_bbs_host_post_helper(
            handler,
            start_bbs_host_fn=deps.start_bbs_host_fn,
            stop_bbs_host_fn=deps.stop_bbs_host_fn,
            append_bbs_host_post_fn=deps.append_bbs_host_post_fn,
            to_int_fn=deps.to_int_fn,
            validate_content_length_fn=deps.validate_content_length_fn,
            parse_bbs_host_request_fn=parse_bbs_host_request_fn,
            write_json_response_fn=deps.write_json_response_fn,
        )
        return

    if path == "/api/settings/custom_telemetry":
        parse_custom_telemetry_settings_request_fn = deps.parse_custom_telemetry_settings_request_fn
        if (
            parse_custom_telemetry_settings_request_fn is None
            or not callable(_handle_custom_telemetry_settings_post_helper)
        ):
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={"ok": False, "error": "Custom telemetry settings are not enabled on this dashboard instance"},
            )
            return
        _handle_custom_telemetry_settings_post_helper(
            handler,
            set_custom_telemetry_settings_fn=deps.set_custom_telemetry_settings_fn,
            to_int_fn=deps.to_int_fn,
            validate_content_length_fn=deps.validate_content_length_fn,
            parse_custom_telemetry_settings_request_fn=parse_custom_telemetry_settings_request_fn,
            write_json_response_fn=deps.write_json_response_fn,
        )
        return

    if path == "/api/settings/raw_packets":
        parse_raw_packet_capture_settings_request_fn = deps.parse_raw_packet_capture_settings_request_fn
        if (
            parse_raw_packet_capture_settings_request_fn is None
            or not callable(_handle_raw_packet_capture_settings_post_helper)
        ):
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={"ok": False, "error": "Raw packet capture settings are not enabled on this dashboard instance"},
            )
            return
        _handle_raw_packet_capture_settings_post_helper(
            handler,
            set_raw_packet_capture_settings_fn=deps.set_raw_packet_capture_settings_fn,
            to_int_fn=deps.to_int_fn,
            validate_content_length_fn=deps.validate_content_length_fn,
            parse_raw_packet_capture_settings_request_fn=parse_raw_packet_capture_settings_request_fn,
            write_json_response_fn=deps.write_json_response_fn,
        )
        return

    if path == "/api/system/update":
        try:
            request_payload = _read_system_update_request(handler)
        except ValueError as exc:
            deps.write_json_response_fn(
                handler,
                status_code=400,
                payload_obj={"ok": False, "updated": False, "error": str(exc)},
                no_store=True,
            )
            return
        try:
            response_obj = _run_update_from_github_helper(
                target_branch=(
                    request_payload.get("branch")
                    or request_payload.get("target_branch")
                    or ""
                ),
            )
        except Exception as exc:
            response_obj = {
                "ok": False,
                "updated": False,
                "state": "error",
                "error": str(exc or "software update failed"),
                "message": "Software update failed.",
                "http_status": 500,
            }
        status_code = 200
        try:
            status_code = int(response_obj.get("http_status") or (200 if response_obj.get("ok") else 409))
        except Exception:
            status_code = 200 if response_obj.get("ok") else 409
        payload_obj = dict(response_obj)
        payload_obj.pop("http_status", None)
        deps.write_json_response_fn(
            handler,
            status_code=status_code,
            payload_obj=payload_obj,
            no_store=True,
        )
        return

    if path == "/api/system/update/sync":
        try:
            request_payload = _read_system_update_request(handler)
        except ValueError as exc:
            deps.write_json_response_fn(
                handler,
                status_code=400,
                payload_obj={"ok": False, "synced": False, "updated": False, "error": str(exc)},
                no_store=True,
            )
            return
        try:
            response_obj = _sync_update_branches_from_github_helper(
                target_branch=(
                    request_payload.get("branch")
                    or request_payload.get("target_branch")
                    or ""
                ),
            )
        except Exception as exc:
            response_obj = {
                "ok": False,
                "synced": False,
                "updated": False,
                "state": "error",
                "error": str(exc or "software branch sync failed"),
                "message": "Software branch sync failed.",
                "http_status": 500,
            }
        status_code = 200
        try:
            status_code = int(response_obj.get("http_status") or (200 if response_obj.get("ok") else 409))
        except Exception:
            status_code = 200 if response_obj.get("ok") else 409
        payload_obj = dict(response_obj)
        payload_obj.pop("http_status", None)
        deps.write_json_response_fn(
            handler,
            status_code=status_code,
            payload_obj=payload_obj,
            no_store=True,
        )
        return

    if path == "/api/system/restart":
        restart_fn = deps.schedule_backend_restart_fn
        if not callable(restart_fn):
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={
                    "ok": False,
                    "restart_scheduled": False,
                    "state": "unavailable",
                    "error": "Backend reload is not enabled on this dashboard instance.",
                    "message": "Backend reload is not enabled on this dashboard instance.",
                },
                no_store=True,
            )
            return
        try:
            response_obj = restart_fn()
        except Exception as exc:
            response_obj = {
                "ok": False,
                "restart_scheduled": False,
                "state": "error",
                "error": str(exc or "backend reload failed"),
                "message": "Backend reload failed.",
                "http_status": 500,
            }
        status_code = 202
        try:
            status_code = int(response_obj.get("http_status") or (202 if response_obj.get("ok") else 500))
        except Exception:
            status_code = 202 if response_obj.get("ok") else 500
        payload_obj = dict(response_obj)
        payload_obj.pop("http_status", None)
        deps.write_json_response_fn(
            handler,
            status_code=status_code,
            payload_obj=payload_obj,
            no_store=True,
        )
        return

    deps.write_json_response_fn(
        handler,
        status_code=404,
        payload_obj={"ok": False, "error": "Not Found"},
    )
