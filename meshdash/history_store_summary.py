import time
from collections.abc import Mapping

from .helpers import to_int as _to_int
from .history_analytics import (
    build_summary_metrics_payload as _build_summary_metrics_payload_helper,
)
from .history_summary_analytics import (
    build_downsampled_summary_metrics_payload as _build_downsampled_summary_metrics_payload_helper,
)
from .history_queries import (
    fetch_summary_packet_type_rows as _fetch_summary_packet_type_rows_helper,
    fetch_summary_metrics_rows as _fetch_summary_metrics_rows_helper,
)
from .history_read_history import (
    fetch_summary_metrics_history_rows as _fetch_summary_metrics_history_rows_helper,
)
from .history_summary_sampling import (
    summary_metrics_bucket_seconds as _summary_metrics_bucket_seconds,
    summary_metrics_bucket_unix as _summary_metrics_bucket_unix,
)
from .history_store_runtime_contracts import (
    HistoryStoreReadState,
    HistoryStoreWriteState,
)


def _summary_int(summary: Mapping[str, object], key: str) -> int:
    return max(0, _to_int(summary.get(key)) or 0)


def save_summary_metrics(
    store: HistoryStoreWriteState,
    summary: Mapping[str, object] | dict[str, object],
) -> None:
    if not isinstance(summary, Mapping):
        return
    now_unix = int(time.time())
    bucket_unix = _summary_metrics_bucket_unix(now_unix)
    node_count = _summary_int(summary, "node_count")
    saved_node_count = _summary_int(summary, "saved_node_count")
    online_node_count = _summary_int(summary, "online_node_count")
    nodes_with_position = _summary_int(summary, "nodes_with_position")
    live_packet_count = _summary_int(summary, "live_packet_count")
    edge_count = _summary_int(summary, "edge_count")
    real_edge_count = _summary_int(summary, "real_edge_count")
    if real_edge_count <= 0:
        real_edge_count = _summary_int(summary, "edge_count")
    if edge_count <= 0:
        edge_count = real_edge_count

    with store._lock:
        store._conn.execute(
            """
            INSERT INTO summary_metrics_1m(
              bucket_unix,
              node_count,
              saved_node_count,
              online_node_count,
              nodes_with_position,
              live_packet_count,
              edge_count,
              real_edge_count,
              last_seen_unix
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(bucket_unix) DO UPDATE SET
              node_count = excluded.node_count,
              saved_node_count = excluded.saved_node_count,
              online_node_count = excluded.online_node_count,
              nodes_with_position = excluded.nodes_with_position,
              live_packet_count = excluded.live_packet_count,
              edge_count = excluded.edge_count,
              real_edge_count = excluded.real_edge_count,
              last_seen_unix = excluded.last_seen_unix
            """,
            (
                bucket_unix,
                node_count,
                saved_node_count,
                online_node_count,
                nodes_with_position,
                live_packet_count,
                edge_count,
                real_edge_count,
                now_unix,
            ),
        )
        store._maybe_prune_unlocked()
        store._conn.commit()


def load_summary_metrics(
    store: HistoryStoreReadState,
    window_hours: int,
    *,
    include_packet_series: bool = True,
    max_points: int | None = None,
) -> dict[str, object]:
    read_conn = getattr(store, "_read_conn", None)
    if read_conn is None or read_conn is store._conn:
        read_conn = store._conn
        read_lock = store._lock
    else:
        read_lock = getattr(store, "_read_lock", None) or store._lock
    with read_lock:
        hours, rows, packet_type_rows = _fetch_summary_metrics_history_rows_helper(
            read_conn,
            window_hours=window_hours,
            fetch_summary_metrics_rows_fn=_fetch_summary_metrics_rows_helper,
            fetch_summary_packet_type_rows_fn=_fetch_summary_packet_type_rows_helper,
            now_unix_fn=time.time,
            include_packet_series=include_packet_series,
        )
    # Build points outside the shared read lock: long windows are CPU work that state polls,
    # which need the same connection, must not wait behind.
    if max_points is not None:
        return _build_downsampled_summary_metrics_payload_helper(
            window_hours=hours,
            rows=rows,
            packet_type_rows=packet_type_rows,
            bucket_seconds=_summary_metrics_bucket_seconds(),
            max_points=max_points,
        )
    return _build_summary_metrics_payload_helper(
        window_hours=hours,
        rows=rows,
        packet_type_rows=packet_type_rows,
        bucket_seconds=_summary_metrics_bucket_seconds(),
    )
