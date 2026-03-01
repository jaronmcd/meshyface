import time
from collections.abc import Mapping

from .helpers import to_int as _to_int
from .history_analytics import (
    build_summary_metrics_payload as _build_summary_metrics_payload_helper,
)
from .history_queries import (
    fetch_summary_metrics_rows as _fetch_summary_metrics_rows_helper,
)
from .history_read_history import (
    load_summary_metrics_history_data as _load_summary_metrics_history_data_helper,
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
    bucket_unix = now_unix - (now_unix % 60)
    node_count = _summary_int(summary, "node_count")
    nodes_with_position = _summary_int(summary, "nodes_with_position")
    live_packet_count = _summary_int(summary, "live_packet_count")
    real_edge_count = _summary_int(summary, "real_edge_count")
    if real_edge_count <= 0:
        real_edge_count = _summary_int(summary, "edge_count")

    with store._lock:
        store._conn.execute(
            """
            INSERT INTO summary_metrics_1m(
              bucket_unix,
              node_count,
              nodes_with_position,
              live_packet_count,
              real_edge_count,
              last_seen_unix
            ) VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(bucket_unix) DO UPDATE SET
              node_count = excluded.node_count,
              nodes_with_position = excluded.nodes_with_position,
              live_packet_count = excluded.live_packet_count,
              real_edge_count = excluded.real_edge_count,
              last_seen_unix = excluded.last_seen_unix
            """,
            (
                bucket_unix,
                node_count,
                nodes_with_position,
                live_packet_count,
                real_edge_count,
                now_unix,
            ),
        )
        store._maybe_prune_unlocked()
        store._conn.commit()


def load_summary_metrics(store: HistoryStoreReadState, window_hours: int) -> dict[str, object]:
    read_conn = getattr(store, "_read_conn", None)
    if read_conn is None or read_conn is store._conn:
        read_conn = store._conn
        read_lock = store._lock
    else:
        read_lock = getattr(store, "_read_lock", None) or store._lock
    with read_lock:
        return _load_summary_metrics_history_data_helper(
            read_conn,
            window_hours=window_hours,
            fetch_summary_metrics_rows_fn=_fetch_summary_metrics_rows_helper,
            build_summary_metrics_payload_fn=_build_summary_metrics_payload_helper,
            now_unix_fn=time.time,
        )
