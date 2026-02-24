import time
from typing import Any, Dict

from .history_analytics import (
    build_node_history_payload as _build_node_history_payload_helper,
    build_online_activity_payload as _build_online_activity_payload_helper,
)
from .history_capabilities import (
    decode_node_capabilities_rows as _decode_node_capabilities_rows_helper,
    decode_node_saved_counts_rows as _decode_node_saved_counts_rows_helper,
)
from .history_queries import (
    fetch_connection_rows as _fetch_connection_rows_helper,
    fetch_node_capability_rows as _fetch_node_capability_rows_helper,
    fetch_node_history_rows as _fetch_node_history_rows_helper,
    fetch_node_saved_count_rows as _fetch_node_saved_count_rows_helper,
    fetch_online_activity_rows as _fetch_online_activity_rows_helper,
    fetch_recent_chat_rows as _fetch_recent_chat_rows_helper,
    fetch_recent_packet_rows as _fetch_recent_packet_rows_helper,
)
from .history_read_api import (
    load_connections_data as _load_connections_data_helper,
    load_node_capabilities_data as _load_node_capabilities_data_helper,
    load_node_saved_counts_data as _load_node_saved_counts_data_helper,
    load_recent_chat_data as _load_recent_chat_data_helper,
    load_recent_packets_data as _load_recent_packets_data_helper,
)
from .history_read_history import (
    load_node_history_data as _load_node_history_data_helper,
    load_online_activity_data as _load_online_activity_data_helper,
)
from .history_readers import (
    decode_connections_rows as _decode_connections_rows_helper,
    decode_recent_chat_rows as _decode_recent_chat_rows_helper,
    decode_recent_packets_rows as _decode_recent_packets_rows_helper,
)


def load_recent_packets(store: Any, limit: int) -> list[Dict[str, Any]]:
    with store._lock:
        return _load_recent_packets_data_helper(
            store._conn,
            limit=limit,
            fetch_recent_packet_rows_fn=_fetch_recent_packet_rows_helper,
            decode_recent_packets_rows_fn=_decode_recent_packets_rows_helper,
        )


def load_recent_chat(store: Any, limit: int) -> list[Dict[str, Any]]:
    with store._lock:
        return _load_recent_chat_data_helper(
            store._conn,
            limit=limit,
            fetch_recent_chat_rows_fn=_fetch_recent_chat_rows_helper,
            decode_recent_chat_rows_fn=_decode_recent_chat_rows_helper,
        )


def load_connections(store: Any) -> list[Dict[str, Any]]:
    with store._lock:
        return _load_connections_data_helper(
            store._conn,
            fetch_connection_rows_fn=_fetch_connection_rows_helper,
            decode_connections_rows_fn=_decode_connections_rows_helper,
        )


def load_node_history(store: Any, node_id: str, window_hours: int, max_points: int) -> Dict[str, Any]:
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


def load_online_activity(store: Any, window_hours: int) -> Dict[str, Any]:
    with store._lock:
        return _load_online_activity_data_helper(
            store._conn,
            window_hours=window_hours,
            fetch_online_activity_rows_fn=_fetch_online_activity_rows_helper,
            build_online_activity_payload_fn=_build_online_activity_payload_helper,
            now_unix_fn=time.time,
        )


def load_node_saved_counts(store: Any) -> Dict[str, Dict[str, Any]]:
    with store._lock:
        return _load_node_saved_counts_data_helper(
            store._conn,
            fetch_node_saved_count_rows_fn=_fetch_node_saved_count_rows_helper,
            decode_node_saved_counts_rows_fn=_decode_node_saved_counts_rows_helper,
        )


def load_node_capabilities(store: Any) -> Dict[str, Dict[str, Any]]:
    with store._lock:
        return _load_node_capabilities_data_helper(
            store._conn,
            fetch_node_capability_rows_fn=_fetch_node_capability_rows_helper,
            decode_node_capabilities_rows_fn=_decode_node_capabilities_rows_helper,
        )
