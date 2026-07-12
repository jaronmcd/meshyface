from typing import Optional, Protocol

from .runtime_types import EmojiFromCodepointFn, NowUnixFn, ToIntFn, UtcNowFn

LocalChatEntry = dict[str, object]


class LocalChatHistoryWriter(Protocol):
    def save_chat(self, entry: LocalChatEntry) -> None:
        ...


class RecentChatBuffer(Protocol):
    def append(self, value: LocalChatEntry) -> None:
        ...


class BuildLocalChatEntryFn(Protocol):
    def __call__(
        self,
        text: object,
        *,
        from_id: object,
        to_id: object,
        channel_index: object,
        message_id: object,
        reply_id: object,
        emoji: object,
        emoji_codepoint: object,
        is_reaction: bool,
        ack_requested: bool,
        retry_of: object,
        now_text: str,
        now_unix: int,
        to_int_fn: ToIntFn,
        emoji_from_codepoint_fn: EmojiFromCodepointFn,
    ) -> Optional[LocalChatEntry]:
        ...


class BuildTrackerLocalEntryFn(Protocol):
    def __call__(
        self,
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
        now_unix_fn: NowUnixFn,
        to_int_fn: ToIntFn,
        emoji_from_codepoint_fn: EmojiFromCodepointFn,
    ) -> Optional[LocalChatEntry]:
        ...


class AppendLocalChatEntryFn(Protocol):
    def __call__(
        self,
        *,
        recent_chat: RecentChatBuffer,
        history_store: LocalChatHistoryWriter | None,
        entry: Optional[LocalChatEntry],
    ) -> bool:
        ...


class TrackerLocalChatRuntimeState(Protocol):
    recent_chat: RecentChatBuffer
    _history_store: LocalChatHistoryWriter | None
