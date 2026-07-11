from __future__ import annotations

import json

from .http_handler_contracts import DashboardHttpHandler
from .http_route_contracts import (
    ParseMeshyfaceProfileThemeRequestFn,
    SendMeshyfaceProfileFn,
    SetMeshyfaceProfileProcessingEnabledFn,
    ToIntFn,
    ValidateContentLengthFn,
    WriteJsonResponseFn,
)


def handle_meshyface_profile_theme_post(
    handler: DashboardHttpHandler,
    *,
    send_meshyface_profile_fn: SendMeshyfaceProfileFn | None,
    to_int_fn: ToIntFn,
    validate_content_length_fn: ValidateContentLengthFn,
    parse_meshyface_profile_theme_request_fn: ParseMeshyfaceProfileThemeRequestFn | None,
    write_json_response_fn: WriteJsonResponseFn,
) -> None:
    if send_meshyface_profile_fn is None or parse_meshyface_profile_theme_request_fn is None:
        write_json_response_fn(
            handler,
            status_code=503,
            payload_obj={
                "ok": False,
                "error": "Meshyface profile sync is not enabled on this dashboard instance",
            },
        )
        return

    try:
        content_length = validate_content_length_fn(
            handler.headers,
            to_int_fn=to_int_fn,
            max_bytes=2048,
        )
    except ValueError:
        write_json_response_fn(
            handler,
            status_code=400,
            payload_obj={"ok": False, "error": "Invalid request size"},
        )
        return

    raw = handler.rfile.read(content_length)
    try:
        request = parse_meshyface_profile_theme_request_fn(raw, to_int_fn=to_int_fn)
    except ValueError as exc:
        write_json_response_fn(
            handler,
            status_code=400,
            payload_obj={"ok": False, "error": str(exc)},
        )
        return

    try:
        send_kwargs: dict[str, object] = {
            "theme": request.theme,
            "channel_index": request.channel_index,
        }
        if request.ghost is not None:
            send_kwargs["ghost"] = request.ghost
        response_obj = send_meshyface_profile_fn(**send_kwargs)
    except ValueError as exc:
        write_json_response_fn(
            handler,
            status_code=400,
            payload_obj={"ok": False, "error": str(exc)},
        )
        return
    except Exception as exc:
        write_json_response_fn(
            handler,
            status_code=500,
            payload_obj={"ok": False, "error": f"Meshyface profile sync failed: {exc}"},
        )
        return

    status_code = 200 if bool(response_obj.get("ok")) else 400
    write_json_response_fn(
        handler,
        status_code=status_code,
        payload_obj=response_obj,
        no_store=True,
    )


def _parse_processing_enabled_request(raw: bytes) -> bool:
    try:
        parsed = json.loads(raw.decode("utf-8") if raw else "{}")
    except Exception as exc:
        raise ValueError("invalid JSON request body") from exc
    if not isinstance(parsed, dict):
        raise ValueError("request body must be an object")
    if "enabled" not in parsed:
        raise ValueError("enabled is required")
    raw_enabled = parsed.get("enabled")
    if isinstance(raw_enabled, bool):
        return raw_enabled
    if isinstance(raw_enabled, int) and raw_enabled in (0, 1):
        return bool(raw_enabled)
    if isinstance(raw_enabled, str):
        clean = raw_enabled.strip().lower()
        if clean in {"1", "true", "yes", "on", "enabled"}:
            return True
        if clean in {"0", "false", "no", "off", "disabled"}:
            return False
    raise ValueError("enabled must be a boolean")


def handle_meshyface_profile_settings_post(
    handler: DashboardHttpHandler,
    *,
    set_meshyface_profile_processing_enabled_fn: (
        SetMeshyfaceProfileProcessingEnabledFn | None
    ),
    to_int_fn: ToIntFn,
    validate_content_length_fn: ValidateContentLengthFn,
    write_json_response_fn: WriteJsonResponseFn,
) -> None:
    if set_meshyface_profile_processing_enabled_fn is None:
        write_json_response_fn(
            handler,
            status_code=503,
            payload_obj={
                "ok": False,
                "error": "Meshyface profile processing settings are not enabled on this dashboard instance",
            },
        )
        return

    try:
        content_length = validate_content_length_fn(
            handler.headers,
            to_int_fn=to_int_fn,
            max_bytes=256,
        )
    except ValueError:
        write_json_response_fn(
            handler,
            status_code=400,
            payload_obj={"ok": False, "error": "Invalid request size"},
        )
        return

    raw = handler.rfile.read(content_length)
    try:
        enabled = _parse_processing_enabled_request(raw)
    except ValueError as exc:
        write_json_response_fn(
            handler,
            status_code=400,
            payload_obj={"ok": False, "error": str(exc)},
        )
        return

    try:
        response_obj = set_meshyface_profile_processing_enabled_fn(enabled)
    except Exception as exc:
        write_json_response_fn(
            handler,
            status_code=500,
            payload_obj={
                "ok": False,
                "error": f"Meshyface profile processing update failed: {exc}",
            },
        )
        return

    status_code = 200 if bool(response_obj.get("ok")) else 400
    write_json_response_fn(
        handler,
        status_code=status_code,
        payload_obj=response_obj,
        no_store=True,
    )
