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


def load_node_history(store: object, node_id: str, window_hours: int, max_points: int) -> dict[str, object]:
    with store._lock:
        return _load_node_history_data_helper(
            store._conn,
            node_id=node_id,
            window_hours=window_hours,
            max_points=max_points,
            fetch_node_history_rows_fn=_fetch_node_history_rows_helper,
            build_node_history_payload_fn=_build_node_history_payload_helper,
            now_unix_fn=time.time,
        )


def load_online_activity(store: object, window_hours: int) -> dict[str, object]:
    with store._lock:
        return _load_online_activity_data_helper(
            store._conn,
            window_hours=window_hours,
            fetch_online_activity_rows_fn=_fetch_online_activity_rows_helper,
            build_online_activity_payload_fn=_build_online_activity_payload_helper,
            now_unix_fn=time.time,
        )


def load_node_saved_counts(store: object) -> dict[str, dict[str, object]]:
    with store._lock:
        return _load_node_saved_counts_data_helper(
            store._conn,
            fetch_node_saved_count_rows_fn=_fetch_node_saved_count_rows_helper,
            decode_node_saved_counts_rows_fn=_decode_node_saved_counts_rows_helper,
        )


def load_node_capabilities(store: object) -> dict[str, dict[str, object]]:
    with store._lock:
        return _load_node_capabilities_data_helper(
            store._conn,
            fetch_node_capability_rows_fn=_fetch_node_capability_rows_helper,
            decode_node_capabilities_rows_fn=_decode_node_capabilities_rows_helper,
        )
