import time

from .history_queries import (
    fetch_recent_chat_rows as _fetch_recent_chat_rows_helper,
)
from .history_raw_writes import (
    save_chat_record as _save_chat_record_helper,
)
from .history_read_api import (
    load_recent_chat_data as _load_recent_chat_data_helper,
)
from .history_readers import (
    decode_recent_chat_rows as _decode_recent_chat_rows_helper,
)


def load_recent_chat(store: object, limit: int) -> list[dict[str, object]]:
    with store._lock:
        return _load_recent_chat_data_helper(
            store._conn,
            limit=limit,
            fetch_recent_chat_rows_fn=_fetch_recent_chat_rows_helper,
            decode_recent_chat_rows_fn=_decode_recent_chat_rows_helper,
        )


def save_chat(store: object, chat_entry: dict[str, object]) -> None:
    with store._lock:
        _save_chat_record_helper(store._conn, chat_entry, now_unix_fn=time.time)
        store._maybe_prune_unlocked()
        store._conn.commit()
