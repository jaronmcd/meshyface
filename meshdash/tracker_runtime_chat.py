import time
from typing import Optional

from .chat import (
    build_local_chat_entry as _build_local_chat_entry,
)
from .helpers import (
    emoji_from_codepoint as _emoji_from_codepoint,
    to_int as _to_int,
)
from .nodes import (
    utc_now as _utc_now,
)
from .tracker_local_chat import (
    append_local_chat_entry as _append_local_chat_entry_helper,
)
from .tracker_local_entry import (
    build_tracker_local_entry as _build_tracker_local_entry_helper,
)
from .runtime_types import EmojiFromCodepointFn, NowUnixFn, ToIntFn, UtcNowFn
from .tracker_local_chat_contracts import (
    AppendLocalChatEntryFn,
    BuildLocalChatEntryFn,
    BuildTrackerLocalEntryFn,
    LocalChatHistoryWriter,
    RecentChatBuffer,
    TrackerLocalChatRuntimeState,
)


def record_tracker_local_chat(
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
    recent_chat: RecentChatBuffer,
    history_store: LocalChatHistoryWriter | None,
    build_tracker_local_entry_fn: BuildTrackerLocalEntryFn,
    append_local_chat_entry_fn: AppendLocalChatEntryFn,
    build_local_chat_entry_fn: BuildLocalChatEntryFn,
    utc_now_fn: UtcNowFn,
    now_unix_fn: NowUnixFn,
    to_int_fn: ToIntFn,
    emoji_from_codepoint_fn: EmojiFromCodepointFn,
) -> bool:
    entry = build_tracker_local_entry_fn(
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
        build_local_chat_entry_fn=build_local_chat_entry_fn,
        utc_now_fn=utc_now_fn,
        now_unix_fn=now_unix_fn,
        to_int_fn=to_int_fn,
        emoji_from_codepoint_fn=emoji_from_codepoint_fn,
    )
    if entry is None:
        return False
    return append_local_chat_entry_fn(
        recent_chat=recent_chat,
        history_store=history_store,
        entry=entry,
    )


def record_tracker_local_chat_for_tracker(
    tracker: TrackerLocalChatRuntimeState,
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
    now_unix_fn: NowUnixFn = time.time,
) -> bool:
    return record_tracker_local_chat(
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
        recent_chat=tracker.recent_chat,
        history_store=tracker._history_store,
        build_tracker_local_entry_fn=_build_tracker_local_entry_helper,
        append_local_chat_entry_fn=_append_local_chat_entry_helper,
        build_local_chat_entry_fn=_build_local_chat_entry,
        utc_now_fn=_utc_now,
        now_unix_fn=now_unix_fn,
        to_int_fn=_to_int,
        emoji_from_codepoint_fn=_emoji_from_codepoint,
    )
