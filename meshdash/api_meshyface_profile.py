from __future__ import annotations

from .http_handler_contracts import DashboardHttpHandler
from .http_route_contracts import (
    ParseMeshyfaceProfileThemeRequestFn,
    SendMeshyfaceProfileFn,
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
