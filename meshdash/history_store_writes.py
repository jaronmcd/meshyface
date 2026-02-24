import time
from typing import Any, Dict, Optional

from .history_connection_writes import (
    save_connection_event as _save_connection_event_helper,
)
from .history_raw_writes import (
    save_chat_record as _save_chat_record_helper,
    save_packet_record as _save_packet_record_helper,
)
from .history_writes import (
    save_packet_event_and_rollups as _save_packet_event_and_rollups_helper,
)


def save_connection_event(
    store: Any,
    *,
    from_id: str,
    to_id: str,
    rx_time: Optional[int],
    portnum: Optional[str],
    hops: Optional[int],
) -> None:
    with store._lock:
        _save_connection_event_helper(
            store._conn,
            from_id=from_id,
            to_id=to_id,
            rx_time=rx_time,
            portnum=portnum,
            hops=hops,
            now_unix_fn=time.time,
        )

        store._maybe_prune_unlocked()
        store._conn.commit()


def save_packet(store: Any, packet_entry: Dict[str, Any]) -> None:
    with store._lock:
        _save_packet_record_helper(
            store._conn,
            packet_entry,
            now_unix_fn=time.time,
            save_packet_event_and_rollups_fn=_save_packet_event_and_rollups_helper,
        )
        store._maybe_prune_unlocked()
        store._conn.commit()


def save_chat(store: Any, chat_entry: Dict[str, Any]) -> None:
    with store._lock:
        _save_chat_record_helper(store._conn, chat_entry, now_unix_fn=time.time)
        store._maybe_prune_unlocked()
        store._conn.commit()
