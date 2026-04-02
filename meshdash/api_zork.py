from .http_handler_contracts import DashboardHttpHandler
from .http_route_contracts import (
    ParseStandaloneZorkRequestFn,
    PlayStandaloneZorkFn,
    ToIntFn,
    ValidateContentLengthFn,
    WriteJsonResponseFn,
)


def handle_standalone_zork_post(
    handler: DashboardHttpHandler,
    *,
    play_standalone_zork_fn: PlayStandaloneZorkFn | None,
    to_int_fn: ToIntFn,
    validate_content_length_fn: ValidateContentLengthFn,
    parse_standalone_zork_request_fn: ParseStandaloneZorkRequestFn | None,
    write_json_response_fn: WriteJsonResponseFn,
) -> None:
    if play_standalone_zork_fn is None or parse_standalone_zork_request_fn is None:
        write_json_response_fn(
            handler,
            status_code=503,
            payload_obj={"ok": False, "error": "Standalone Zork is not enabled on this dashboard instance"},
        )
        return

    try:
        content_length = validate_content_length_fn(
            handler.headers,
            to_int_fn=to_int_fn,
        )
    except ValueError:
        write_json_response_fn(
            handler,
            status_code=400,
            payload_obj={"ok": False, "error": "Invalid request size"},
        )
        return

    raw = handler.rfile.read(content_length)
    request = parse_standalone_zork_request_fn(raw)

    try:
        response_obj = play_standalone_zork_fn(
            text=request.text,
            session_id=request.session_id,
        )
    except ValueError as exc:
        write_json_response_fn(
            handler,
            status_code=400,
            payload_obj={"ok": False, "error": str(exc)},
        )
        return
    except Exception:
        write_json_response_fn(
            handler,
            status_code=500,
            payload_obj={"ok": False, "error": "Standalone Zork failed"},
        )
        return

    status_code = 200 if bool(response_obj.get("ok")) else 400
    write_json_response_fn(handler, status_code=status_code, payload_obj=response_obj, no_store=True)


__all__ = ["handle_standalone_zork_post"]
