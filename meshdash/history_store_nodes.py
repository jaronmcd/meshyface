import time

from .history_analytics import (
    build_node_history_payload as _build_node_history_payload_helper,
)
from .history_capabilities import (
    decode_node_capabilities_rows as _decode_node_capabilities_rows_helper,
    decode_node_position_counts_rows as _decode_node_position_counts_rows_helper,
    decode_node_saved_counts_rows as _decode_node_saved_counts_rows_helper,
)
from .history_queries import (
    fetch_local_signal_history_rows as _fetch_local_signal_history_rows_helper,
    fetch_node_capability_rows as _fetch_node_capability_rows_helper,
    fetch_node_history_rows as _fetch_node_history_rows_helper,
    fetch_node_position_count_rows as _fetch_node_position_count_rows_helper,
    fetch_node_saved_count_rows as _fetch_node_saved_count_rows_helper,
)
from .history_node_metrics import (
    build_metric_history_points as _build_metric_history_points_helper,
)
from .history_read_api import (
    load_node_capabilities_data as _load_node_capabilities_data_helper,
    load_node_position_counts_data as _load_node_position_counts_data_helper,
    load_node_saved_counts_data as _load_node_saved_counts_data_helper,
)
from .history_read_history import (
    load_node_history_data as _load_node_history_data_helper,
)
from .history_store_runtime_contracts import HistoryStoreReadState


def load_node_history(
    store: HistoryStoreReadState,
    node_id: str,
    window_hours: int,
    max_points: int,
) -> dict[str, object]:
    clean_node_id = str(node_id or "").strip().lower()
    local_node_id = str(getattr(store, "local_node_id", "") or "").strip().lower()
    hours = max(1, int(window_hours))
    points_limit = max(20, min(10000, int(max_points)))
    cutoff = int(time.time()) - (hours * 3600)
    read_conn = getattr(store, "_read_conn", None)
    if read_conn is None or read_conn is store._conn:
        read_conn = store._conn
        read_lock = store._lock
    else:
        read_lock = getattr(store, "_read_lock", None) or store._lock
    with read_lock:
        history_payload = _load_node_history_data_helper(
            read_conn,
            node_id=node_id,
            window_hours=hours,
            max_points=points_limit,
            fetch_node_history_rows_fn=_fetch_node_history_rows_helper,
            build_node_history_payload_fn=_build_node_history_payload_helper,
            now_unix_fn=time.time,
        )
        signal_points = list(history_payload.get("points") or [])
        signal_source = "node"
        if clean_node_id and local_node_id and clean_node_id == local_node_id:
            signal_metric_rows = _fetch_local_signal_history_rows_helper(
                read_conn,
                cutoff=cutoff,
                limit=points_limit,
            )
            signal_points = _build_metric_history_points_helper(signal_metric_rows)["points"]
            signal_source = "local-radio"
        history_payload["signal_points"] = signal_points
        history_payload["signal_source"] = signal_source
        return history_payload


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


def load_node_position_counts(store: HistoryStoreReadState) -> dict[str, dict[str, object]]:
    read_conn = getattr(store, "_read_conn", None)
    if read_conn is None or read_conn is store._conn:
        read_conn = store._conn
        read_lock = store._lock
    else:
        read_lock = getattr(store, "_read_lock", None) or store._lock
    with read_lock:
        return _load_node_position_counts_data_helper(
            read_conn,
            fetch_node_position_count_rows_fn=_fetch_node_position_count_rows_helper,
            decode_node_position_counts_rows_fn=_decode_node_position_counts_rows_helper,
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
