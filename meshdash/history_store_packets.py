import time

from .history_queries import (
    fetch_recent_packet_rows as _fetch_recent_packet_rows_helper,
)
from .history_raw_writes import (
    save_packet_record as _save_packet_record_helper,
)
from .history_read_api import (
    load_recent_packets_data as _load_recent_packets_data_helper,
)
from .history_readers import (
    decode_recent_packets_rows as _decode_recent_packets_rows_helper,
)
from .history_writes import (
    save_packet_event_and_rollups as _save_packet_event_and_rollups_helper,
)


def load_recent_packets(store: object, limit: int) -> list[dict[str, object]]:
    with store._lock:
        return _load_recent_packets_data_helper(
            store._conn,
            limit=limit,
            fetch_recent_packet_rows_fn=_fetch_recent_packet_rows_helper,
            decode_recent_packets_rows_fn=_decode_recent_packets_rows_helper,
        )


def save_packet(store: object, packet_entry: dict[str, object]) -> None:
    with store._lock:
        _save_packet_record_helper(
            store._conn,
            packet_entry,
            now_unix_fn=time.time,
            save_packet_event_and_rollups_fn=_save_packet_event_and_rollups_helper,
        )
        store._maybe_prune_unlocked()
        store._conn.commit()
