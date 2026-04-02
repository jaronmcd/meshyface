from typing import Callable, Optional

from .chat_scope import chat_scope_for_destination
from .helpers import emoji_from_codepoint, to_int
from .runtime_types import EmojiFromCodepointFn, ToIntFn


def build_local_chat_entry(
    text: object,
    *,
    from_id: object = "local",
    to_id: object = "^all",
    channel_index: object = 0,
    message_id: object = None,
    reply_id: object = None,
    emoji: object = None,
    emoji_codepoint: object = None,
    is_reaction: bool = False,
    ack_requested: bool = False,
    retry_of: object = None,
    now_text: str,
    now_unix: int,
    to_int_fn: ToIntFn = to_int,
    emoji_from_codepoint_fn: EmojiFromCodepointFn = emoji_from_codepoint,
) -> Optional[dict[str, object]]:
    clean_text = str(text or "")
    clean_message_id = to_int_fn(message_id)
    clean_reply_id = to_int_fn(reply_id)
    clean_emoji_codepoint = to_int_fn(emoji_codepoint)
    clean_emoji = str(emoji or "").strip() or emoji_from_codepoint_fn(clean_emoji_codepoint)
    if clean_emoji and clean_emoji_codepoint is None:
        clean_emoji_codepoint = ord(clean_emoji[0])
    has_reaction = bool(
        is_reaction or (clean_reply_id is not None and clean_reply_id > 0 and clean_emoji)
    )
    if not clean_text.strip() and not has_reaction:
        return None

    should_track_delivery = bool(ack_requested and not has_reaction and str(to_id or "^all") != "^all")
    delivery_state = "sent"
    delivery_error: Optional[str] = None
    if should_track_delivery:
        if clean_message_id is not None and clean_message_id > 0:
            delivery_state = "pending"
        else:
            delivery_state = "error"
            delivery_error = "Delivery tracking unavailable (missing packet id)"

    entry: dict[str, object] = {
        "captured_at": now_text,
        "from": str(from_id or "local"),
        "to": str(to_id or "^all"),
        "scope": chat_scope_for_destination(to_id),
        "portnum": "TEXT_MESSAGE_APP",
        "channel": int(channel_index) if isinstance(channel_index, int) else 0,
        "rx_time": now_text,
        "text": clean_text,
        "local_echo": True,
        "delivery_state": delivery_state,
        "delivery_updated_at": now_text,
        "delivery_updated_unix": now_unix,
    }
    if clean_message_id is not None and clean_message_id > 0:
        entry["message_id"] = clean_message_id
    if clean_reply_id is not None and clean_reply_id > 0:
        entry["reply_id"] = clean_reply_id
    if clean_emoji:
        entry["emoji"] = clean_emoji
    if clean_emoji_codepoint is not None and clean_emoji_codepoint > 0:
        entry["emoji_codepoint"] = clean_emoji_codepoint
    if has_reaction:
        entry["is_reaction"] = True
    if should_track_delivery:
        entry["ack_requested"] = True
    if delivery_error:
        entry["delivery_error"] = delivery_error

    clean_retry_of = to_int_fn(retry_of)
    if clean_retry_of is not None and clean_retry_of > 0:
        entry["retry_of"] = clean_retry_of
    return entry
