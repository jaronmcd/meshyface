import time
from typing import Optional

from .runtime_types import EmojiFromCodepointFn, NowUnixFn, ToIntFn, UtcNowFn
from .tracker_local_chat_contracts import BuildLocalChatEntryFn, LocalChatEntry


def build_tracker_local_entry(
    *,
    text: str,
    from_id: str,
    to_id: str,
    channel_index: int,
    message_id: Optional[int],
    reply_id: Optional[int],
    emoji: Optional[str],
    emoji_codepoint: Optional[int],
    is_reaction: bool,
    ack_requested: bool,
    retry_of: Optional[int],
    build_local_chat_entry_fn: BuildLocalChatEntryFn,
    utc_now_fn: UtcNowFn,
    to_int_fn: ToIntFn,
    emoji_from_codepoint_fn: EmojiFromCodepointFn,
    now_unix_fn: NowUnixFn = time.time,
) -> Optional[LocalChatEntry]:
    now_text = utc_now_fn()
    now_unix = int(now_unix_fn())
    return build_local_chat_entry_fn(
        text=text,
        from_id=from_id,
        to_id=to_id,
        channel_index=channel_index,
        message_id=message_id,
        reply_id=reply_id,
        emoji=emoji,
        emoji_codepoint=emoji_codepoint,
        is_reaction=is_reaction,
        ack_requested=ack_requested,
        retry_of=retry_of,
        now_text=now_text,
        now_unix=now_unix,
        to_int_fn=to_int_fn,
        emoji_from_codepoint_fn=emoji_from_codepoint_fn,
    )
