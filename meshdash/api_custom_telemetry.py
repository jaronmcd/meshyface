from .http_handler_contracts import DashboardHttpHandler
from .http_route_contracts import (
    GetCustomTelemetrySettingsFn,
    ParseCustomTelemetrySettingsRequestFn,
    SetCustomTelemetrySettingsFn,
    ToIntFn,
    ValidateContentLengthFn,
    WriteJsonResponseFn,
)

_MAX_CUSTOM_TELEMETRY_SETTINGS_POST_BYTES = 256 * 1024


def handle_custom_telemetry_settings_get(
    handler: DashboardHttpHandler,
    *,
    get_custom_telemetry_settings_fn: GetCustomTelemetrySettingsFn | None,
    write_json_response_fn: WriteJsonResponseFn,
) -> None:
    if get_custom_telemetry_settings_fn is None:
        write_json_response_fn(
            handler,
            status_code=503,
            payload_obj={"ok": False, "error": "Custom telemetry settings are not enabled on this dashboard instance"},
        )
        return

    try:
        payload_obj = get_custom_telemetry_settings_fn()
    except Exception as exc:
        write_json_response_fn(
            handler,
            status_code=500,
            payload_obj={"ok": False, "error": f"Custom telemetry settings failed: {exc}"},
        )
        return

    write_json_response_fn(
        handler,
        status_code=200,
        payload_obj=payload_obj,
        no_store=True,
    )


def handle_custom_telemetry_settings_post(
    handler: DashboardHttpHandler,
    *,
    set_custom_telemetry_settings_fn: SetCustomTelemetrySettingsFn | None,
    to_int_fn: ToIntFn,
    validate_content_length_fn: ValidateContentLengthFn,
    parse_custom_telemetry_settings_request_fn: ParseCustomTelemetrySettingsRequestFn | None,
    write_json_response_fn: WriteJsonResponseFn,
) -> None:
    if set_custom_telemetry_settings_fn is None or parse_custom_telemetry_settings_request_fn is None:
        write_json_response_fn(
            handler,
            status_code=503,
            payload_obj={"ok": False, "error": "Custom telemetry settings are not enabled on this dashboard instance"},
        )
        return

    try:
        content_length = validate_content_length_fn(
            handler.headers,
            to_int_fn=to_int_fn,
            max_bytes=_MAX_CUSTOM_TELEMETRY_SETTINGS_POST_BYTES,
        )
    except ValueError:
        write_json_response_fn(
            handler,
            status_code=400,
            payload_obj={"ok": False, "error": "Invalid request size"},
        )
        return

    raw = handler.rfile.read(content_length)
    request = parse_custom_telemetry_settings_request_fn(raw)
    if request.rules is None:
        write_json_response_fn(
            handler,
            status_code=400,
            payload_obj={"ok": False, "error": "No custom telemetry rules provided"},
        )
        return

    try:
        response_obj = set_custom_telemetry_settings_fn(request.rules)
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
            payload_obj={"ok": False, "error": f"Custom telemetry settings update failed: {exc}"},
        )
        return

    status_code = 200 if bool(response_obj.get("ok")) else 400
    write_json_response_fn(handler, status_code=status_code, payload_obj=response_obj, no_store=True)
