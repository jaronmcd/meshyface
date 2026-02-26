import time
from typing import Optional

from .history_connection_writes import (
    save_connection_event as _save_connection_event_helper,
)
from .history_queries import (
    fetch_connection_rows as _fetch_connection_rows_helper,
)
from .history_read_api import (
    load_connections_data as _load_connections_data_helper,
)
from .history_readers import (
    decode_connections_rows as _decode_connections_rows_helper,
)


def load_connections(store: object) -> list[dict[str, object]]:
    with store._lock:
        return _load_connections_data_helper(
            store._conn,
            fetch_connection_rows_fn=_fetch_connection_rows_helper,
            decode_connections_rows_fn=_decode_connections_rows_helper,
        )


def save_connection_event(
    store: object,
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
