import time

from .history_analytics import (
    build_node_history_payload as _build_node_history_payload_helper,
    build_online_activity_payload as _build_online_activity_payload_helper,
)
from .history_capabilities import (
    decode_node_capabilities_rows as _decode_node_capabilities_rows_helper,
    decode_node_saved_counts_rows as _decode_node_saved_counts_rows_helper,
)
from .history_queries import (
    fetch_node_capability_rows as _fetch_node_capability_rows_helper,
    fetch_node_history_rows as _fetch_node_history_rows_helper,
    fetch_node_saved_count_rows as _fetch_node_saved_count_rows_helper,
    fetch_online_activity_rows as _fetch_online_activity_rows_helper,
)
from .history_read_api import (
    load_node_capabilities_data as _load_node_capabilities_data_helper,
    load_node_saved_counts_data as _load_node_saved_counts_data_helper,
)
from .history_read_history import (
    load_node_history_data as _load_node_history_data_helper,
    load_online_activity_data as _load_online_activity_data_helper,
)
from .history_store_runtime_contracts import HistoryStoreReadState


def load_node_history(
    store: HistoryStoreReadState,
    node_id: str,
    window_hours: int,
    max_points: int,
) -> dict[str, object]:
    read_conn = getattr(store, "_read_conn", None)
    if read_conn is None or read_conn is store._conn:
        read_conn = store._conn
        read_lock = store._lock
    else:
        read_lock = getattr(store, "_read_lock", None) or store._lock
    with read_lock:
        return _load_node_history_data_helper(
            read_conn,
            node_id=node_id,
            window_hours=window_hours,
            max_points=max_points,
            fetch_node_history_rows_fn=_fetch_node_history_rows_helper,
            build_node_history_payload_fn=_build_node_history_payload_helper,
            now_unix_fn=time.time,
        )


def load_online_activity(store: HistoryStoreReadState, window_hours: int) -> dict[str, object]:
    read_conn = getattr(store, "_read_conn", None)
    if read_conn is None or read_conn is store._conn:
        read_conn = store._conn
        read_lock = store._lock
    else:
        read_lock = getattr(store, "_read_lock", None) or store._lock
    with read_lock:
        return _load_online_activity_data_helper(
            read_conn,
            window_hours=window_hours,
            fetch_online_activity_rows_fn=_fetch_online_activity_rows_helper,
            build_online_activity_payload_fn=_build_online_activity_payload_helper,
            now_unix_fn=time.time,
        )


def load_node_saved_counts(store: HistoryStoreReadState) -> dict[str, dict[str, object]]:
    read_conn = getattr(store, "_read_conn", None)
    if read_conn is None or read_conn is store._conn:
        read_conn = store._conn
        read_lock = store._lock
    else:
        read_lock = getattr(store, "_read_lock", None) or store._lock
    with read_lock:
        return _load_node_saved_counts_data_helper(
            read_conn,
            fetch_node_saved_count_rows_fn=_fetch_node_saved_count_rows_helper,
            decode_node_saved_counts_rows_fn=_decode_node_saved_counts_rows_helper,
        )


def load_node_capabilities(store: HistoryStoreReadState) -> dict[str, dict[str, object]]:
    read_conn = getattr(store, "_read_conn", None)
    if read_conn is None or read_conn is store._conn:
        read_conn = store._conn
        read_lock = store._lock
    else:
        read_lock = getattr(store, "_read_lock", None) or store._lock
    with read_lock:
        return _load_node_capabilities_data_helper(
            read_conn,
            fetch_node_capability_rows_fn=_fetch_node_capability_rows_helper,
            decode_node_capabilities_rows_fn=_decode_node_capabilities_rows_helper,
        )
