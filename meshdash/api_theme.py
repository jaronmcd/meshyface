from .http_handler_contracts import DashboardHttpHandler
from .http_route_contracts import (
    GetThemeSettingsFn,
    ParseThemeSettingsRequestFn,
    SetThemePresetFn,
    ToIntFn,
    ValidateContentLengthFn,
    WriteJsonResponseFn,
)
from .theme import MAX_THEME_BACKGROUND_IMAGE_DATA_LENGTH


_MAX_THEME_SETTINGS_POST_BYTES = MAX_THEME_BACKGROUND_IMAGE_DATA_LENGTH + (256 * 1024)


def handle_theme_settings_get(
    handler: DashboardHttpHandler,
    *,
    get_theme_settings_fn: GetThemeSettingsFn | None,
    write_json_response_fn: WriteJsonResponseFn,
) -> None:
    if get_theme_settings_fn is None:
        write_json_response_fn(
            handler,
            status_code=503,
            payload_obj={"ok": False, "error": "Theme settings are not enabled on this dashboard instance"},
        )
        return

    try:
        payload_obj = get_theme_settings_fn()
    except Exception as exc:
        write_json_response_fn(
            handler,
            status_code=500,
            payload_obj={"ok": False, "error": f"Theme settings failed: {exc}"},
        )
        return

    write_json_response_fn(
        handler,
        status_code=200,
        payload_obj=payload_obj,
        no_store=True,
    )


def handle_theme_settings_post(
    handler: DashboardHttpHandler,
    *,
    set_theme_preset_fn: SetThemePresetFn | None,
    to_int_fn: ToIntFn,
    validate_content_length_fn: ValidateContentLengthFn,
    parse_theme_settings_request_fn: ParseThemeSettingsRequestFn,
    write_json_response_fn: WriteJsonResponseFn,
) -> None:
    if set_theme_preset_fn is None:
        write_json_response_fn(
            handler,
            status_code=503,
            payload_obj={"ok": False, "error": "Theme settings are not enabled on this dashboard instance"},
        )
        return

    try:
        content_length = validate_content_length_fn(
            handler.headers,
            to_int_fn=to_int_fn,
            max_bytes=_MAX_THEME_SETTINGS_POST_BYTES,
        )
    except ValueError:
        write_json_response_fn(
            handler,
            status_code=400,
            payload_obj={"ok": False, "error": "Invalid request size"},
        )
        return

    raw = handler.rfile.read(content_length)
    request = parse_theme_settings_request_fn(raw)

    try:
        response_obj = set_theme_preset_fn(request)
    except Exception as exc:
        write_json_response_fn(
            handler,
            status_code=500,
            payload_obj={"ok": False, "error": f"Theme settings update failed: {exc}"},
        )
        return

    status_code = 200 if bool(response_obj.get("ok")) else 400
    write_json_response_fn(
        handler,
        status_code=status_code,
        payload_obj=response_obj,
        no_store=True,
    )
