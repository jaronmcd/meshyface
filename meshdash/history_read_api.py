from .history_read_contracts import (
    DecodeNodeCapabilityMapFn,
    DecodeRowsListFn,
    FetchRowsFn,
    FetchRowsWithLimitFn,
    HistoryListPayload,
    NodeCapabilityMap,
)
from .sql_contracts import SqlConnection

def load_recent_packets_data(
    conn: SqlConnection,
    *,
    limit: int,
    fetch_recent_packet_rows_fn: FetchRowsWithLimitFn,
    decode_recent_packets_rows_fn: DecodeRowsListFn,
) -> HistoryListPayload:
    rows = fetch_recent_packet_rows_fn(conn, limit=limit)
    return decode_recent_packets_rows_fn(rows)


def load_recent_chat_data(
    conn: SqlConnection,
    *,
    limit: int,
    fetch_recent_chat_rows_fn: FetchRowsWithLimitFn,
    decode_recent_chat_rows_fn: DecodeRowsListFn,
) -> HistoryListPayload:
    rows = fetch_recent_chat_rows_fn(conn, limit=limit)
    return decode_recent_chat_rows_fn(rows)


def load_connections_data(
    conn: SqlConnection,
    *,
    fetch_connection_rows_fn: FetchRowsFn,
    decode_connections_rows_fn: DecodeRowsListFn,
) -> HistoryListPayload:
    rows = fetch_connection_rows_fn(conn)
    return decode_connections_rows_fn(rows)


def load_node_saved_counts_data(
    conn: SqlConnection,
    *,
    fetch_node_saved_count_rows_fn: FetchRowsFn,
    decode_node_saved_counts_rows_fn: DecodeNodeCapabilityMapFn,
) -> NodeCapabilityMap:
    rows = fetch_node_saved_count_rows_fn(conn)
    return decode_node_saved_counts_rows_fn(rows)


def load_node_capabilities_data(
    conn: SqlConnection,
    *,
    fetch_node_capability_rows_fn: FetchRowsFn,
    decode_node_capabilities_rows_fn: DecodeNodeCapabilityMapFn,
) -> NodeCapabilityMap:
    rows = fetch_node_capability_rows_fn(conn)
    return decode_node_capabilities_rows_fn(rows)
