import json
from typing import Any, Callable, Mapping, Optional
from urllib.parse import parse_qs


def parse_node_history_query(
    raw_query: str,
    *,
    to_int_fn: Callable[[Any], Optional[int]],
) -> tuple[str, Optional[int], Optional[int]]:
    query = parse_qs(raw_query)
    node_id = (query.get("node_id", [""])[0] or "").strip()
    hours_override = to_int_fn(query.get("hours", [""])[0])
    points_override = to_int_fn(query.get("points", [""])[0])
    return node_id, hours_override, points_override


def parse_online_activity_query(
    raw_query: str,
    *,
    to_int_fn: Callable[[Any], Optional[int]],
) -> Optional[int]:
    query = parse_qs(raw_query)
    return to_int_fn(query.get("hours", [""])[0])


def validate_content_length(
    headers: Mapping[str, Any],
    *,
    to_int_fn: Callable[[Any], Optional[int]],
    max_bytes: int = 8192,
) -> int:
    content_length = to_int_fn(headers.get("Content-Length")) or 0
    if content_length <= 0 or content_length > max_bytes:
        raise ValueError("Invalid request size")
    return content_length


def parse_chat_send_body(
    raw_body: bytes,
    *,
    to_int_fn: Callable[[Any], Optional[int]],
) -> dict:
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except Exception:
        body = {}
    payload = body if isinstance(body, dict) else {}
    return {
        "text": payload.get("text"),
        "destination": payload.get("destination"),
        "channel_index": to_int_fn(payload.get("channel_index")),
        "reply_id": to_int_fn(payload.get("reply_id")),
        "retry_of": to_int_fn(payload.get("retry_of")),
        "emoji": payload.get("emoji"),
    }
