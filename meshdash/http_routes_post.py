from collections.abc import Mapping
from importlib import import_module
import json
from hmac import compare_digest

from .http_handler_contracts import DashboardHttpHandler
from .http_plugin_admin import (
    PLUGIN_ADMIN_WRITE_PATHS,
    plugin_admin_authorization,
    plugin_browser_write_is_same_origin,
    request_has_json_content_type,
)
from .http_route_contracts import DashboardPostRouteDependencies
from .api_system_update import (
    cleanup_update_rollback_branches as _cleanup_update_rollback_branches_helper,
    repair_dirty_update_checkout as _repair_dirty_update_checkout_helper,
    rollback_update_to_commit as _rollback_update_to_commit_helper,
    run_update_from_github as _run_update_from_github_helper,
    sync_update_branches_from_github as _sync_update_branches_from_github_helper,
)
from .map_packs import (
    cancel_map_pack_build_job as _cancel_map_pack_build_job_helper,
    install_built_map_pack as _install_built_map_pack_helper,
    start_map_pack_build_job as _start_map_pack_build_job_helper,
)


_TOKEN_PROTECTED_WRITE_PATHS = {
    "/api/chat/send",
    "/api/files/send",
    "/api/meshyface/profile/settings",
    "/api/meshyface/profile/theme",
    "/api/games/zork",
    "/api/plugins/console",
    "/api/tools/network",
    "/api/settings/radio",
    "/api/settings/channels",
    "/api/settings/theme",
    "/api/settings/custom_telemetry",
    "/api/settings/raw_packets",
    "/api/maps/packs/build",
    "/api/maps/packs/build/cancel",
    "/api/maps/packs/install",
    "/api/settings/plugins",
    "/api/settings/plugins/config",
    "/api/settings/plugins/routes",
    "/api/settings/plugins/runtime",
    "/api/maps/packs/build",
    "/api/maps/packs/build/cancel",
    "/api/maps/packs/install",
    "/api/system/update",
    "/api/system/update/repair",
    "/api/system/update/rollback-cleanup",
    "/api/system/update/sync",
    "/api/system/restart",
}
_PRIVATE_MODE_BLOCKED_POST_PATHS = {
    "/api/chat/send",
    "/api/files/send",
    "/api/meshyface/profile/theme",
    "/api/games/zork",
    "/api/plugins/console",
    "/api/tools/network",
    "/api/maps/packs/build",
    "/api/maps/packs/build/cancel",
    "/api/maps/packs/install",
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
_handle_meshyface_profile_theme_post_helper = _load_optional_handler(
    ".api_meshyface_profile",
    "handle_meshyface_profile_theme_post",
)
_handle_meshyface_profile_settings_post_helper = _load_optional_handler(
    ".api_meshyface_profile",
    "handle_meshyface_profile_settings_post",
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


def _read_json_object_request(
    handler: DashboardHttpHandler,
    *,
    max_bytes: int,
    missing_ok: bool = False,
) -> dict[str, object]:
    raw_length = _header_value(getattr(handler, "headers", None), "Content-Length").strip()
    if not raw_length:
        if missing_ok:
            return {}
        raise ValueError("missing Content-Length")
    try:
        length = int(raw_length)
    except ValueError as exc:
        raise ValueError("invalid Content-Length") from exc
    if length < 0 or length > max_bytes:
        raise ValueError("invalid request size")
    if length == 0:
        return {}
    try:
        parsed = json.loads(handler.rfile.read(length).decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid JSON request body") from exc
    if not isinstance(parsed, dict):
        raise ValueError("request body must be an object")
    return parsed


def _read_plugin_settings_request(
    handler: DashboardHttpHandler,
) -> dict[str, object]:
    raw_length = _header_value(getattr(handler, "headers", None), "Content-Length").strip()
    try:
        length = int(raw_length)
    except ValueError as exc:
        raise ValueError("invalid Content-Length") from exc
    if length <= 0 or length > 2048:
        raise ValueError("invalid request size")
    try:
        parsed = json.loads(handler.rfile.read(length).decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid JSON request body") from exc
    if not isinstance(parsed, dict):
        raise ValueError("request body must be an object")
    if set(parsed) != {"plugin_id", "enabled", "package_digest"}:
        raise ValueError(
            "request body must contain only plugin_id, enabled, and package_digest"
        )
    plugin_id = parsed.get("plugin_id")
    if not isinstance(plugin_id, str) or not plugin_id.strip():
        raise ValueError("plugin_id must be a non-empty string")
    if not isinstance(parsed.get("enabled"), bool):
        raise ValueError("enabled must be a boolean")
    return {
        "plugin_id": plugin_id.strip().lower(),
        "enabled": parsed["enabled"],
        "package_digest": _plugin_package_digest(parsed.get("package_digest")),
    }


def _read_plugin_config_request(handler: DashboardHttpHandler) -> dict[str, object]:
    raw_length = _header_value(getattr(handler, "headers", None), "Content-Length").strip()
    try:
        length = int(raw_length)
    except ValueError as exc:
        raise ValueError("invalid Content-Length") from exc
    if length <= 0 or length > 65536:
        raise ValueError("invalid request size")
    try:
        parsed = json.loads(handler.rfile.read(length).decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid JSON request body") from exc
    if not isinstance(parsed, dict):
        raise ValueError("request body must be an object")
    if set(parsed) != {"plugin_id", "settings", "package_digest"}:
        raise ValueError(
            "request body must contain only plugin_id, settings, and package_digest"
        )
    plugin_id = parsed.get("plugin_id")
    if not isinstance(plugin_id, str) or not plugin_id.strip():
        raise ValueError("plugin_id must be a non-empty string")
    settings = parsed.get("settings")
    if not isinstance(settings, dict):
        raise ValueError("settings must be an object")
    return {
        "plugin_id": plugin_id.strip().lower(),
        "settings": settings,
        "package_digest": _plugin_package_digest(parsed.get("package_digest")),
    }


def _read_plugin_route_policy_request(
    handler: DashboardHttpHandler,
) -> dict[str, object]:
    raw_length = _header_value(getattr(handler, "headers", None), "Content-Length").strip()
    try:
        length = int(raw_length)
    except ValueError as exc:
        raise ValueError("invalid Content-Length") from exc
    if length <= 0 or length > 2048:
        raise ValueError("invalid request size")
    try:
        parsed = json.loads(handler.rfile.read(length).decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid JSON request body") from exc
    if not isinstance(parsed, dict):
        raise ValueError("request body must be an object")
    if set(parsed) != {
        "plugin_id",
        "mesh_enabled",
        "console_enabled",
        "ticker_enabled",
        "package_digest",
    }:
        raise ValueError(
            "request body must contain only plugin_id, mesh_enabled, "
            "console_enabled, ticker_enabled, and package_digest"
        )
    plugin_id = parsed.get("plugin_id")
    if not isinstance(plugin_id, str) or not plugin_id.strip():
        raise ValueError("plugin_id must be a non-empty string")
    if not isinstance(parsed.get("mesh_enabled"), bool):
        raise ValueError("mesh_enabled must be a boolean")
    if not isinstance(parsed.get("console_enabled"), bool):
        raise ValueError("console_enabled must be a boolean")
    if not isinstance(parsed.get("ticker_enabled"), bool):
        raise ValueError("ticker_enabled must be a boolean")
    return {
        "plugin_id": plugin_id.strip().lower(),
        "mesh_enabled": parsed["mesh_enabled"],
        "console_enabled": parsed["console_enabled"],
        "ticker_enabled": parsed["ticker_enabled"],
        "package_digest": _plugin_package_digest(parsed.get("package_digest")),
    }


def _read_plugin_runtime_settings_request(
    handler: DashboardHttpHandler,
) -> dict[str, object]:
    parsed = _read_json_object_request(handler, max_bytes=1024)
    if set(parsed) != {"enabled"}:
        raise ValueError("request body must contain only enabled")
    if not isinstance(parsed.get("enabled"), bool):
        raise ValueError("enabled must be a boolean")
    return {"enabled": parsed["enabled"]}


def _read_plugin_console_request(handler: DashboardHttpHandler) -> dict[str, object]:
    parsed = _read_json_object_request(handler, max_bytes=8192)
    allowed = {"command", "text", "session_id", "handler"}
    if not set(parsed).issubset(allowed):
        raise ValueError(
            "request body may contain only command, text, session_id, and handler"
        )
    command = parsed.get("command")
    if not isinstance(command, str) or not command.strip():
        raise ValueError("command must be a non-empty string")
    raw_handler = str(parsed.get("handler") or "auto").strip().lower() or "auto"
    if raw_handler not in {"auto", "command", "session", "message"}:
        raise ValueError("handler must be auto, command, session, or message")
    return {
        "command": command.strip().lower(),
        "text": parsed.get("text", ""),
        "session_id": parsed.get("session_id"),
        "handler": raw_handler,
    }


def _plugin_package_digest(value: object) -> str:
    digest = str(value or "").strip().lower()
    if (
        len(digest) != 71
        or not digest.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in digest[7:])
    ):
        raise ValueError("package_digest must be a SHA-256 plugin identity")
    return digest


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


def _map_pack_response_status(payload_obj: Mapping[str, object]) -> int:
    try:
        return int(payload_obj.get("http_status") or 200)
    except (TypeError, ValueError):
        return 200


def _plugin_console_response_status(payload_obj: Mapping[str, object]) -> int:
    if payload_obj.get("ok") is not False:
        return 200
    error = payload_obj.get("error")
    code = str(error.get("code") or "") if isinstance(error, Mapping) else ""
    if code in {"invalid_command", "invalid_handler", "empty_command", "invalid_request"}:
        return 400
    if code == "unknown_command":
        return 404
    if code == "plugin_console_disabled":
        return 403
    return 503


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

    if path in PLUGIN_ADMIN_WRITE_PATHS:
        authorized, auth_status, auth_error = plugin_admin_authorization(
            handler,
            required_token=deps.api_token,
        )
        if not authorized:
            _record_write_auth_denied(deps)
            extra_headers = (
                {"WWW-Authenticate": "Bearer"} if auth_status == 401 else None
            )
            deps.write_json_response_fn(
                handler,
                status_code=auth_status,
                payload_obj={"ok": False, "error": auth_error},
                no_store=True,
                extra_headers=extra_headers,
            )
            return
        if not request_has_json_content_type(handler):
            deps.write_json_response_fn(
                handler,
                status_code=415,
                payload_obj={
                    "ok": False,
                    "error": "Plugin administration requires application/json",
                },
                no_store=True,
            )
            return
        if not plugin_browser_write_is_same_origin(handler):
            _record_write_auth_denied(deps)
            deps.write_json_response_fn(
                handler,
                status_code=403,
                payload_obj={
                    "ok": False,
                    "error": "Cross-origin plugin administration is not allowed",
                },
                no_store=True,
            )
            return

    if (
        path in _TOKEN_PROTECTED_WRITE_PATHS
        and path not in PLUGIN_ADMIN_WRITE_PATHS
        and not _write_request_is_authorized(handler, deps=deps)
    ):
        _record_write_auth_denied(deps)
        deps.write_json_response_fn(
            handler,
            status_code=401,
            payload_obj={"ok": False, "error": "API token required for write endpoint"},
            no_store=True,
            extra_headers={"WWW-Authenticate": "Bearer"},
        )
        return

    if path == "/api/maps/packs/build":
        try:
            request_payload = _read_json_object_request(
                handler,
                max_bytes=4096,
                missing_ok=True,
            )
            response_obj = _start_map_pack_build_job_helper(request_payload)
        except ValueError as exc:
            response_obj = {
                "ok": False,
                "error": {"code": "invalid_request", "message": str(exc)},
                "http_status": 400,
            }
        status_code = _map_pack_response_status(response_obj)
        response_obj.pop("http_status", None)
        deps.write_json_response_fn(
            handler,
            status_code=status_code,
            payload_obj=response_obj,
            no_store=True,
        )
        return

    if path == "/api/maps/packs/build/cancel":
        response_obj = _cancel_map_pack_build_job_helper()
        deps.write_json_response_fn(
            handler,
            status_code=200,
            payload_obj=response_obj,
            no_store=True,
        )
        return

    if path == "/api/maps/packs/install":
        try:
            request_payload = _read_json_object_request(
                handler,
                max_bytes=2048,
                missing_ok=True,
            )
            response_obj = _install_built_map_pack_helper(request_payload)
        except ValueError as exc:
            response_obj = {
                "ok": False,
                "error": {"code": "invalid_request", "message": str(exc)},
                "http_status": 400,
            }
        status_code = _map_pack_response_status(response_obj)
        response_obj.pop("http_status", None)
        deps.write_json_response_fn(
            handler,
            status_code=status_code,
            payload_obj=response_obj,
            no_store=True,
        )
        return

    if path in {"/api/chat/send", "/api/files/send"}:
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
            file_transfer_only=(path == "/api/files/send"),
        )
        return

    if path == "/api/meshyface/profile/settings":
        if not callable(_handle_meshyface_profile_settings_post_helper):
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={
                    "ok": False,
                    "error": "Meshyface profile processing settings are not enabled on this dashboard instance",
                },
            )
            return
        _handle_meshyface_profile_settings_post_helper(
            handler,
            set_meshyface_profile_processing_enabled_fn=(
                deps.set_meshyface_profile_processing_enabled_fn
            ),
            to_int_fn=deps.to_int_fn,
            validate_content_length_fn=deps.validate_content_length_fn,
            write_json_response_fn=deps.write_json_response_fn,
        )
        return

    if path == "/api/meshyface/profile/theme":
        parse_profile_request_fn = deps.parse_meshyface_profile_theme_request_fn
        if parse_profile_request_fn is None or not callable(
            _handle_meshyface_profile_theme_post_helper
        ):
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={
                    "ok": False,
                    "error": "Meshyface profile sync is not enabled on this dashboard instance",
                },
            )
            return
        _handle_meshyface_profile_theme_post_helper(
            handler,
            send_meshyface_profile_fn=deps.send_meshyface_profile_fn,
            to_int_fn=deps.to_int_fn,
            validate_content_length_fn=deps.validate_content_length_fn,
            parse_meshyface_profile_theme_request_fn=parse_profile_request_fn,
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

    if path == "/api/plugins/console":
        runner = deps.run_plugin_console_command_fn
        if not callable(runner):
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={
                    "ok": False,
                    "error": {
                        "code": "plugin_runtime_unavailable",
                        "message": "Plugin console is unavailable",
                    },
                },
                no_store=True,
            )
            return
        try:
            request = _read_plugin_console_request(handler)
            response_obj = runner(
                command=request["command"],
                text=request.get("text", ""),
                session_id=request.get("session_id"),
                handler=request.get("handler", "auto"),
            )
        except ValueError as exc:
            deps.write_json_response_fn(
                handler,
                status_code=400,
                payload_obj={
                    "ok": False,
                    "error": {"code": "invalid_request", "message": str(exc)},
                },
                no_store=True,
            )
            return
        except Exception:
            deps.write_json_response_fn(
                handler,
                status_code=500,
                payload_obj={
                    "ok": False,
                    "error": {
                        "code": "plugin_console_failed",
                        "message": "Plugin console command failed",
                    },
                },
                no_store=True,
            )
            return
        if not isinstance(response_obj, Mapping):
            deps.write_json_response_fn(
                handler,
                status_code=500,
                payload_obj={
                    "ok": False,
                    "error": {
                        "code": "plugin_console_failed",
                        "message": "Plugin console command returned an invalid response",
                    },
                },
                no_store=True,
            )
            return
        deps.write_json_response_fn(
            handler,
            status_code=_plugin_console_response_status(response_obj),
            payload_obj=response_obj,
            no_store=True,
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

    if path == "/api/settings/plugins/runtime":
        setter = deps.set_plugin_runtime_enabled_fn
        if not callable(setter):
            response_obj = {
                "ok": False,
                "error": {
                    "code": "plugin_runtime_unavailable",
                    "message": "Plugin runtime management is unavailable",
                },
            }
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj=response_obj,
                no_store=True,
            )
            return
        try:
            request = _read_plugin_runtime_settings_request(handler)
            response_obj = setter(bool(request["enabled"]))
        except ValueError as exc:
            deps.write_json_response_fn(
                handler,
                status_code=400,
                payload_obj={
                    "ok": False,
                    "error": {"code": "invalid_request", "message": str(exc)},
                },
                no_store=True,
            )
            return
        except Exception as exc:
            deps.write_json_response_fn(
                handler,
                status_code=500,
                payload_obj={
                    "ok": False,
                    "error": {
                        "code": "plugin_runtime_update_failed",
                        "message": f"Plugin runtime update failed: {exc}",
                    },
                },
                no_store=True,
            )
            return
        if not isinstance(response_obj, Mapping):
            deps.write_json_response_fn(
                handler,
                status_code=500,
                payload_obj={
                    "ok": False,
                    "error": {
                        "code": "plugin_runtime_update_failed",
                        "message": (
                            "Plugin runtime update returned an invalid response"
                        ),
                    },
                },
                no_store=True,
            )
            return
        status_code = 200 if response_obj.get("ok") is not False else 503
        deps.write_json_response_fn(
            handler,
            status_code=status_code,
            payload_obj=response_obj,
            no_store=True,
        )
        return

    if path == "/api/settings/plugins":
        setter = deps.set_plugin_enabled_fn
        if not callable(setter):
            response_obj = {
                "ok": False,
                "error": {
                    "code": "plugin_runtime_unavailable",
                    "message": "Plugin runtime management is unavailable",
                },
            }
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj=response_obj,
                no_store=True,
            )
            return
        try:
            request = _read_plugin_settings_request(handler)
            response_obj = setter(
                request["plugin_id"],
                bool(request["enabled"]),
                expected_package_digest=request["package_digest"],
            )
        except ValueError as exc:
            deps.write_json_response_fn(
                handler,
                status_code=400,
                payload_obj={
                    "ok": False,
                    "error": {"code": "invalid_request", "message": str(exc)},
                },
                no_store=True,
            )
            return
        except Exception as exc:
            deps.write_json_response_fn(
                handler,
                status_code=500,
                payload_obj={
                    "ok": False,
                    "error": {
                        "code": "plugin_settings_update_failed",
                        "message": f"Plugin settings update failed: {exc}",
                    },
                },
                no_store=True,
            )
            return
        if not isinstance(response_obj, Mapping):
            deps.write_json_response_fn(
                handler,
                status_code=500,
                payload_obj={
                    "ok": False,
                    "error": {
                        "code": "plugin_settings_update_failed",
                        "message": "Plugin settings update returned an invalid response",
                    },
                },
                no_store=True,
            )
            return
        error = response_obj.get("error")
        error_code = str(error.get("code") or "") if isinstance(error, Mapping) else ""
        status_code = 200
        if response_obj.get("ok") is False:
            if error_code == "unknown_plugin":
                status_code = 404
            elif error_code == "plugin_identity_changed":
                status_code = 409
            else:
                status_code = 503
        deps.write_json_response_fn(
            handler,
            status_code=status_code,
            payload_obj=response_obj,
            no_store=True,
        )
        return

    if path == "/api/settings/plugins/routes":
        setter = deps.set_plugin_route_policy_fn
        if not callable(setter):
            response_obj = {
                "ok": False,
                "error": {
                    "code": "plugin_runtime_unavailable",
                    "message": "Plugin route management is unavailable",
                },
            }
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj=response_obj,
                no_store=True,
            )
            return
        try:
            request = _read_plugin_route_policy_request(handler)
            response_obj = setter(
                request["plugin_id"],
                mesh_enabled=bool(request["mesh_enabled"]),
                console_enabled=bool(request["console_enabled"]),
                ticker_enabled=bool(request["ticker_enabled"]),
                expected_package_digest=request["package_digest"],
            )
        except ValueError as exc:
            deps.write_json_response_fn(
                handler,
                status_code=400,
                payload_obj={
                    "ok": False,
                    "error": {"code": "invalid_request", "message": str(exc)},
                },
                no_store=True,
            )
            return
        except Exception as exc:
            deps.write_json_response_fn(
                handler,
                status_code=500,
                payload_obj={
                    "ok": False,
                    "error": {
                        "code": "plugin_route_policy_update_failed",
                        "message": f"Plugin route policy update failed: {exc}",
                    },
                },
                no_store=True,
            )
            return
        if not isinstance(response_obj, Mapping):
            deps.write_json_response_fn(
                handler,
                status_code=500,
                payload_obj={
                    "ok": False,
                    "error": {
                        "code": "plugin_route_policy_update_failed",
                        "message": (
                            "Plugin route policy update returned an invalid response"
                        ),
                    },
                },
                no_store=True,
            )
            return
        error = response_obj.get("error")
        error_code = str(error.get("code") or "") if isinstance(error, Mapping) else ""
        status_code = 200
        if response_obj.get("ok") is False:
            if error_code == "unknown_plugin":
                status_code = 404
            elif error_code == "plugin_identity_changed":
                status_code = 409
            else:
                status_code = 503
        deps.write_json_response_fn(
            handler,
            status_code=status_code,
            payload_obj=response_obj,
            no_store=True,
        )
        return

    if path == "/api/settings/plugins/config":
        setter = deps.set_plugin_settings_fn
        if not callable(setter):
            response_obj = {
                "ok": False,
                "error": {
                    "code": "plugin_runtime_unavailable",
                    "message": "Plugin configuration management is unavailable",
                },
            }
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj=response_obj,
                no_store=True,
            )
            return
        try:
            request = _read_plugin_config_request(handler)
            response_obj = setter(
                request["plugin_id"],
                request["settings"],
                expected_package_digest=request["package_digest"],
            )
        except ValueError as exc:
            deps.write_json_response_fn(
                handler,
                status_code=400,
                payload_obj={
                    "ok": False,
                    "error": {"code": "invalid_request", "message": str(exc)},
                },
                no_store=True,
            )
            return
        except Exception as exc:
            deps.write_json_response_fn(
                handler,
                status_code=500,
                payload_obj={
                    "ok": False,
                    "error": {
                        "code": "plugin_config_update_failed",
                        "message": f"Plugin configuration update failed: {exc}",
                    },
                },
                no_store=True,
            )
            return
        if not isinstance(response_obj, Mapping):
            deps.write_json_response_fn(
                handler,
                status_code=500,
                payload_obj={
                    "ok": False,
                    "error": {
                        "code": "plugin_config_update_failed",
                        "message": "Plugin configuration update returned an invalid response",
                    },
                },
                no_store=True,
            )
            return
        error = response_obj.get("error")
        error_code = str(error.get("code") or "") if isinstance(error, Mapping) else ""
        status_code = 200
        if response_obj.get("ok") is False:
            if error_code == "unknown_plugin":
                status_code = 404
            elif error_code == "plugin_identity_changed":
                status_code = 409
            else:
                status_code = 503
        deps.write_json_response_fn(
            handler,
            status_code=status_code,
            payload_obj=response_obj,
            no_store=True,
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
            target_branch = (
                request_payload.get("branch")
                or request_payload.get("target_branch")
                or ""
            )
            rollback_commit = (
                request_payload.get("rollback_commit")
                or request_payload.get("commit")
                or ""
            )
            if rollback_commit:
                response_obj = _rollback_update_to_commit_helper(
                    target_branch=target_branch,
                    target_commit=rollback_commit,
                )
            else:
                response_obj = _run_update_from_github_helper(
                    target_branch=target_branch,
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

    if path == "/api/system/update/repair":
        try:
            request_payload = _read_system_update_request(handler)
        except ValueError as exc:
            deps.write_json_response_fn(
                handler,
                status_code=400,
                payload_obj={"ok": False, "repaired": False, "updated": False, "error": str(exc)},
                no_store=True,
            )
            return
        try:
            response_obj = _repair_dirty_update_checkout_helper(
                target_branch=(
                    request_payload.get("branch")
                    or request_payload.get("target_branch")
                    or ""
                ),
            )
        except Exception as exc:
            response_obj = {
                "ok": False,
                "repaired": False,
                "updated": False,
                "state": "error",
                "error": str(exc or "software checkout repair failed"),
                "message": "Software checkout repair failed.",
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

    if path == "/api/system/update/rollback-cleanup":
        try:
            response_obj = _cleanup_update_rollback_branches_helper()
        except Exception as exc:
            response_obj = {
                "ok": False,
                "cleanup": False,
                "state": "error",
                "error": str(exc or "rollback cleanup failed"),
                "message": "Rollback cleanup failed.",
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
