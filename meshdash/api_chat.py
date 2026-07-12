from .http_handler_contracts import DashboardHttpHandler
from .http_route_contracts import (
    ParseChatSendRequestFn,
    SendChatFn,
    ToIntFn,
    ValidateContentLengthFn,
    WriteJsonResponseFn,
)
from .file_transfer_protocol import FILE_TRANSFER_PROTOCOL_PREFIX


def handle_chat_send_post(
    handler: DashboardHttpHandler,
    *,
    send_chat_fn: SendChatFn | None,
    to_int_fn: ToIntFn,
    validate_content_length_fn: ValidateContentLengthFn,
    parse_chat_send_request_fn: ParseChatSendRequestFn,
    write_json_response_fn: WriteJsonResponseFn,
    file_transfer_only: bool = False,
) -> None:
    if send_chat_fn is None:
        write_json_response_fn(
            handler,
            status_code=503,
            payload_obj={"ok": False, "error": "Chat send is not enabled on this dashboard instance"},
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
    chat_request = parse_chat_send_request_fn(raw, to_int_fn=to_int_fn)
    request_text = str(chat_request.text or "").strip()
    is_file_transfer = request_text.startswith(FILE_TRANSFER_PROTOCOL_PREFIX)
    if file_transfer_only != is_file_transfer:
        error = (
            "A valid MF_FILE_V2 frame is required"
            if file_transfer_only
            else "MF_FILE_V2 frames must use /api/files/send"
        )
        write_json_response_fn(
            handler,
            status_code=400,
            payload_obj={"ok": False, "error": error},
        )
        return

    try:
        response_obj = send_chat_fn(
            text=chat_request.text,
            destination=chat_request.destination,
            channel_index=chat_request.channel_index,
            reply_id=chat_request.reply_id,
            retry_of=chat_request.retry_of,
            emoji=chat_request.emoji,
        )
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
            payload_obj={"ok": False, "error": f"Send failed: {exc}"},
        )
        return

    write_json_response_fn(handler, status_code=200, payload_obj=response_obj, no_store=True)
