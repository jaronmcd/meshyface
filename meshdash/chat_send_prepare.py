from typing import Callable, Optional

NormalizeSingleEmojiFn = Callable[[object], tuple[Optional[str], Optional[int]]]
ToIntFn = Callable[[object], Optional[int]]
PreparedChatInput = dict[str, object]


def prepare_chat_send_input(
    *,
    text: object,
    destination: object,
    channel_index: Optional[int],
    reply_id: Optional[int],
    retry_of: Optional[int],
    emoji: object,
    chat_max_bytes: int,
    normalize_single_emoji_fn: NormalizeSingleEmojiFn,
    to_int_fn: ToIntFn,
) -> PreparedChatInput:
    raw_text = str(text or "")
    clean_text = raw_text
    raw_emoji = str(emoji or "").strip()
    clean_reply_id = to_int_fn(reply_id)
    clean_retry_of = to_int_fn(retry_of)
    clean_emoji, clean_emoji_codepoint = normalize_single_emoji_fn(emoji)

    if clean_reply_id is not None and clean_reply_id > 0 and raw_emoji and not clean_emoji:
        raise ValueError("Emoji reactions must use a single-codepoint emoji")

    has_reaction = bool(
        clean_reply_id is not None and clean_reply_id > 0 and clean_emoji and clean_emoji_codepoint
    )
    if clean_emoji and not has_reaction:
        raise ValueError("Emoji reactions require a valid reply_id")
    if clean_reply_id is not None and clean_reply_id <= 0:
        raise ValueError("reply_id must be a positive packet id")
    if has_reaction and clean_text.strip():
        raise ValueError("Emoji reactions must not include text")
    if not clean_text.strip() and not has_reaction:
        raise ValueError("Message cannot be empty")

    if clean_text:
        payload_bytes = clean_text.encode("utf-8")
        if len(payload_bytes) > int(chat_max_bytes):
            raise ValueError(
                f"Message is too long ({len(payload_bytes)} bytes). Limit is {chat_max_bytes} bytes."
            )

    clean_destination = str(destination or "^all").strip() or "^all"
    if clean_destination.lower() in ("all", "broadcast"):
        clean_destination = "^all"
    if not (clean_destination == "^all" or clean_destination.startswith("!")):
        raise ValueError("Destination must be '^all' or a node id like !abcdef12")

    clean_channel = channel_index if isinstance(channel_index, int) and channel_index >= 0 else 0
    should_request_ack = bool(clean_destination != "^all" and not has_reaction)

    return {
        "text": clean_text,
        "reply_id": clean_reply_id,
        "retry_of": clean_retry_of,
        "emoji": clean_emoji,
        "emoji_codepoint": clean_emoji_codepoint,
        "is_reaction": has_reaction,
        "destination": clean_destination,
        "channel_index": clean_channel,
        "ack_requested": should_request_ack,
    }
