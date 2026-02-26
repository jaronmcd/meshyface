from typing import Optional

from .tracker_local_chat_contracts import LocalChatEntry, LocalChatHistoryWriter, RecentChatBuffer


def append_local_chat_entry(
    *,
    recent_chat: RecentChatBuffer,
    history_store: LocalChatHistoryWriter | None,
    entry: Optional[LocalChatEntry],
) -> bool:
    if entry is None:
        return False
    recent_chat.append(entry)
    if history_store is not None:
        history_store.save_chat(entry)
    return True
