import time
from collections.abc import Reversible
from typing import Callable, Optional

from .helpers import to_int
from .nodes import utc_now


def _is_hex_text(value: str) -> bool:
    return bool(value) and all(ch in "0123456789abcdefABCDEF" for ch in value)


def _canonical_node_id(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in {"^all", "all", "broadcast", "!ffffffff", "ffffffff", "0xffffffff", "4294967295"}:
        return "^all"
    if text.startswith("!") and len(text) == 9 and _is_hex_text(text[1:]):
        return f"!{text[1:].lower()}"
    if len(text) == 8 and _is_hex_text(text):
        return f"!{text.lower()}"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        parsed = int(value)
        if 0 <= parsed <= 0xFFFFFFFF:
            return f"!{parsed:08x}"
    if text.isdigit():
        try:
            parsed = int(text, 10)
        except Exception:
            parsed = -1
        if 0 <= parsed <= 0xFFFFFFFF:
            return f"!{parsed:08x}"
    return text


def _should_accept_delivery_update(
    target: dict[str, object],
    *,
    ack_from_id: object = None,
    ack_to_id: object = None,
) -> bool:
    ack_from = _canonical_node_id(ack_from_id)
    expected_from = _canonical_node_id(target.get("to") or target.get("to_id") or target.get("destination"))
    if expected_from:
        if not ack_from:
            return False
        if expected_from != "^all" and ack_from != expected_from:
            return False
    ack_to = _canonical_node_id(ack_to_id)
    expected_to = _canonical_node_id(target.get("from") or target.get("from_id"))
    if expected_to:
        if not ack_to or ack_to != expected_to:
            return False
    return True


def chat_message_id(
    entry: object,
    *,
    to_int_fn: Callable[[object], Optional[int]] = to_int,
) -> Optional[int]:
    if not isinstance(entry, dict):
        return None
    return to_int_fn(
        entry.get("message_id")
        or entry.get("messageId")
        or entry.get("packet_id")
        or entry.get("packetId")
    )


def set_delivery_state(
    recent_chat: Reversible[object],
    message_id: object,
    state: str,
    error: Optional[str] = None,
    *,
    ack_from_id: object = None,
    ack_to_id: object = None,
    to_int_fn: Callable[[object], Optional[int]] = to_int,
    now_text_fn: Callable[[], str] = utc_now,
    now_unix_fn: Callable[[], int] = lambda: int(time.time()),
    on_update_fn: Optional[Callable[[dict[str, object]], None]] = None,
) -> bool:
    clean_message_id = to_int_fn(message_id)
    if clean_message_id is None or clean_message_id <= 0:
        return False

    target: Optional[dict[str, object]] = None
    for entry in reversed(recent_chat):
        if not isinstance(entry, dict):
            continue
        if entry.get("local_echo") is not True:
            continue
        if chat_message_id(entry, to_int_fn=to_int_fn) != clean_message_id:
            continue
        target = entry
        break

    if target is None:
        return False

    if not _should_accept_delivery_update(
        target,
        ack_from_id=ack_from_id,
        ack_to_id=ack_to_id,
    ):
        return False

    target["delivery_state"] = str(state or "sent")
    target["delivery_updated_at"] = now_text_fn()
    target["delivery_updated_unix"] = now_unix_fn()
    if ack_from_id is not None:
        target["delivery_ack_from"] = _canonical_node_id(ack_from_id) or str(ack_from_id or "")
    if ack_to_id is not None:
        target["delivery_ack_to"] = _canonical_node_id(ack_to_id) or str(ack_to_id or "")
    if error:
        target["delivery_error"] = str(error)
    else:
        target.pop("delivery_error", None)
    if callable(on_update_fn):
        on_update_fn(target)
    return True
