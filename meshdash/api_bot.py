from .http_handler_contracts import DashboardHttpHandler
from .http_route_contracts import (
    ApplyBotSettingsFn,
    ParseBotSettingsRequestFn,
    ToIntFn,
    ValidateContentLengthFn,
    WriteJsonResponseFn,
)

_MAX_BOT_SETTINGS_POST_BYTES = 256 * 1024


def handle_bot_settings_post(
    handler: DashboardHttpHandler,
    *,
    apply_bot_settings_fn: ApplyBotSettingsFn | None,
    to_int_fn: ToIntFn,
    validate_content_length_fn: ValidateContentLengthFn,
    parse_bot_settings_request_fn: ParseBotSettingsRequestFn | None,
    write_json_response_fn: WriteJsonResponseFn,
) -> None:
    if apply_bot_settings_fn is None or parse_bot_settings_request_fn is None:
        write_json_response_fn(
            handler,
            status_code=503,
            payload_obj={"ok": False, "error": "Bot settings are not enabled on this dashboard instance"},
        )
        return

    try:
        content_length = validate_content_length_fn(
            handler.headers,
            to_int_fn=to_int_fn,
            max_bytes=_MAX_BOT_SETTINGS_POST_BYTES,
        )
    except ValueError:
        write_json_response_fn(
            handler,
            status_code=400,
            payload_obj={"ok": False, "error": "Invalid request size"},
        )
        return

    raw = handler.rfile.read(content_length)
    request = parse_bot_settings_request_fn(raw)
    if (
        request.enabled is None
        and request.log_enabled is None
        and request.game_enabled is None
        and request.game_public_start_enabled is None
        and request.command_settings is None
        and request.joke_triggers is None
        and request.joke_lines is None
        and request.joke_delay_punchline_enabled is None
    ):
        write_json_response_fn(
            handler,
            status_code=400,
            payload_obj={"ok": False, "error": "No bot settings provided"},
        )
        return

    try:
        response_obj = apply_bot_settings_fn(request)
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
            payload_obj={"ok": False, "error": f"Bot settings update failed: {exc}"},
        )
        return

    write_json_response_fn(handler, status_code=200, payload_obj=response_obj, no_store=True)
