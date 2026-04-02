from .http_handler_contracts import DashboardHttpHandler
from .http_route_contracts import (
    ApplyChannelSettingsFn,
    ParseChannelSettingsRequestFn,
    ToIntFn,
    ValidateContentLengthFn,
    WriteJsonResponseFn,
)


def handle_channel_settings_post(
    handler: DashboardHttpHandler,
    *,
    apply_channel_settings_fn: ApplyChannelSettingsFn | None,
    to_int_fn: ToIntFn,
    validate_content_length_fn: ValidateContentLengthFn,
    parse_channel_settings_request_fn: ParseChannelSettingsRequestFn | None,
    write_json_response_fn: WriteJsonResponseFn,
    max_bytes: int = 65536,
) -> None:
    if apply_channel_settings_fn is None or parse_channel_settings_request_fn is None:
        write_json_response_fn(
            handler,
            status_code=503,
            payload_obj={
                "ok": False,
                "error": "Channel settings are not enabled on this dashboard instance",
            },
        )
        return

    try:
        content_length = validate_content_length_fn(
            handler.headers,
            to_int_fn=to_int_fn,
            max_bytes=max_bytes,
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
        request = parse_channel_settings_request_fn(raw)
    except ValueError as exc:
        write_json_response_fn(
            handler,
            status_code=400,
            payload_obj={"ok": False, "error": str(exc)},
        )
        return

    try:
        response_obj = apply_channel_settings_fn(request)
    except Exception as exc:
        write_json_response_fn(
            handler,
            status_code=500,
            payload_obj={"ok": False, "error": f"Channel settings update failed: {exc}"},
        )
        return

    status_code = 200 if bool(response_obj.get("ok")) else 400
    write_json_response_fn(
        handler,
        status_code=status_code,
        payload_obj=response_obj,
        no_store=True,
    )
