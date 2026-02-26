import json
from dataclasses import dataclass
from typing import Mapping, Optional

from .runtime_types import ToIntFn


def validate_content_length(
    headers: Mapping[str, object],
    *,
    to_int_fn: ToIntFn,
    max_bytes: int = 8192,
) -> int:
    content_length = to_int_fn(headers.get("Content-Length")) or 0
    if content_length <= 0 or content_length > max_bytes:
        raise ValueError("Invalid request size")
    return content_length


@dataclass(frozen=True)
class ChatSendRequest:
    text: object
    destination: object
    channel_index: Optional[int]
    reply_id: Optional[int]
    retry_of: Optional[int]
    emoji: object


def parse_chat_send_request(
    raw_body: bytes,
    *,
    to_int_fn: ToIntFn,
) -> ChatSendRequest:
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except Exception:
        body = {}
    payload = body if isinstance(body, dict) else {}
    return ChatSendRequest(
        text=payload.get("text"),
        destination=payload.get("destination"),
        channel_index=to_int_fn(payload.get("channel_index")),
        reply_id=to_int_fn(payload.get("reply_id")),
        retry_of=to_int_fn(payload.get("retry_of")),
        emoji=payload.get("emoji"),
    )


def parse_chat_send_body(
    raw_body: bytes,
    *,
    to_int_fn: ToIntFn,
) -> dict[str, object]:
    request = parse_chat_send_request(raw_body, to_int_fn=to_int_fn)
    return {
        "text": request.text,
        "destination": request.destination,
        "channel_index": request.channel_index,
        "reply_id": request.reply_id,
        "retry_of": request.retry_of,
        "emoji": request.emoji,
    }
