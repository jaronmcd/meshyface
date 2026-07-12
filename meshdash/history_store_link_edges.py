import time
from collections.abc import Iterable

from .helpers import to_float as _to_float, to_int as _to_int
from .history_capabilities import (
    decode_node_capabilities_rows as _decode_node_capabilities_rows,
)
from .history_queries import (
    fetch_node_capability_rows as _fetch_node_capability_rows,
)
from .history_store_runtime_contracts import HistoryStoreReadState
from .sql_contracts import SqlConnection


_DEFAULT_LIMIT = 1200
_MAX_LIMIT = 3000
_MAX_LIMIT_MAX_WINDOW = 12000
_MIN_REAL_LINK_COUNT = 2
_WINDOW_SECONDS = {
    "6h": 6 * 60 * 60,
    "12h": 12 * 60 * 60,
    "24h": 24 * 60 * 60,
    "72h": 72 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
    "14d": 14 * 24 * 60 * 60,
    "30d": 30 * 24 * 60 * 60,
    "max": 0,
}


def _normalize_link_window(raw_window: object) -> str:
    clean = str(raw_window or "").strip().lower().replace(" ", "")
    aliases = {
        "": "7d",
        "history": "7d",
        "week": "7d",
        "1w": "7d",
        "all": "max",
        "full": "max",
        "forever": "max",
    }
    clean = aliases.get(clean, clean)
    return clean if clean in _WINDOW_SECONDS else "7d"


def _clean_limit(raw_limit: object, *, window: str) -> int:
    parsed = _to_int(raw_limit)
    if parsed is None:
        parsed = _DEFAULT_LIMIT
    max_limit = _MAX_LIMIT_MAX_WINDOW if window == "max" else _MAX_LIMIT
    return max(1, min(max_limit, int(parsed)))


def _fetch_link_metric_edge_rows(
    conn: SqlConnection,
    *,
    cutoff_unix: int,
    limit: int,
):
    return conn.execute(
        """
        SELECT from_id,
               to_id,
               MIN(bucket_unix) AS first_seen_unix,
               MAX(last_seen_unix) AS last_seen_unix,
               COALESCE(SUM(packet_count), 0) AS packet_count,
               COALESCE(SUM(snr_sum), 0.0) AS snr_sum,
               COALESCE(SUM(snr_count), 0) AS snr_count,
               MIN(CASE WHEN snr_count > 0 THEN snr_min END) AS snr_min,
               MAX(CASE WHEN snr_count > 0 THEN snr_max END) AS snr_max,
               COALESCE(SUM(rssi_sum), 0.0) AS rssi_sum,
               COALESCE(SUM(rssi_count), 0) AS rssi_count,
               MIN(CASE WHEN rssi_count > 0 THEN rssi_min END) AS rssi_min,
               MAX(CASE WHEN rssi_count > 0 THEN rssi_max END) AS rssi_max,
               COALESCE(SUM(hops_sum), 0) AS hops_sum,
               COALESCE(SUM(hops_count), 0) AS hops_count,
               MIN(CASE WHEN hops_count > 0 THEN hops_min END) AS hops_min,
               MAX(CASE WHEN hops_count > 0 THEN hops_max END) AS hops_max
        FROM link_metrics_1m
        WHERE (? <= 0 OR last_seen_unix >= ?)
          AND trim(COALESCE(from_id, '')) <> ''
          AND trim(COALESCE(to_id, '')) <> ''
          AND trim(COALESCE(from_id, '')) NOT IN ('Unknown', 'n/a', '^all')
          AND trim(COALESCE(to_id, '')) NOT IN ('Unknown', 'n/a', '^all')
          AND from_id <> to_id
        GROUP BY from_id, to_id
        HAVING SUM(packet_count) > 0
        ORDER BY packet_count DESC, last_seen_unix DESC, from_id ASC, to_id ASC
        LIMIT ?
        """,
        (int(cutoff_unix), int(cutoff_unix), max(1, int(limit))),
    ).fetchall()


def _decode_link_metric_edge_rows(rows: Iterable[tuple[object, ...]]) -> list[dict[str, object]]:
    edges: list[dict[str, object]] = []
    for row in rows:
        if len(row) < 17:
            continue
        (
            from_id,
            to_id,
            first_seen_unix,
            last_seen_unix,
            packet_count,
            snr_sum,
            snr_count,
            snr_min,
            snr_max,
            rssi_sum,
            rssi_count,
            rssi_min,
            rssi_max,
            hops_sum,
            hops_count,
            _hops_min,
            hops_max,
        ) = row[:17]
        count = max(0, _to_int(packet_count) or 0)
        if count <= 0:
            continue
        hops_total = _to_float(hops_sum)
        hops_samples = _to_int(hops_count) or 0
        if hops_total is None or hops_samples <= 0:
            hops_total = 0.0
            hops_samples = 0
        snr_total = _to_float(snr_sum)
        snr_samples = _to_int(snr_count) or 0
        if snr_total is None or snr_samples <= 0:
            snr_total = 0.0
            snr_samples = 0
        rssi_total = _to_float(rssi_sum)
        rssi_samples = _to_int(rssi_count) or 0
        if rssi_total is None or rssi_samples <= 0:
            rssi_total = 0.0
            rssi_samples = 0
        edge: dict[str, object] = {
            "from": str(from_id),
            "to": str(to_id),
            "count": count,
            "session_count": 0,
            "lifetime_count": count,
            "is_real": count >= _MIN_REAL_LINK_COUNT,
            "confidence": "confirmed" if count >= _MIN_REAL_LINK_COUNT else "observed",
            "first_rx_unix": _to_int(first_seen_unix),
            "last_rx_unix": _to_int(last_seen_unix),
            "hops_samples": hops_samples,
            "snr_samples": snr_samples,
            "rssi_samples": rssi_samples,
            "is_rollup": True,
        }
        if hops_samples > 0:
            edge["avg_hops"] = round(hops_total / hops_samples, 2)
            last_hops = _to_int(hops_max)
            edge["last_hops"] = last_hops if last_hops is not None and 0 <= last_hops <= 255 else None
        if snr_samples > 0:
            edge["avg_snr"] = round(snr_total / snr_samples, 2)
            edge["snr_min"] = _to_float(snr_min)
            edge["snr_max"] = _to_float(snr_max)
        if rssi_samples > 0:
            edge["avg_rssi"] = round(rssi_total / rssi_samples, 2)
            edge["rssi_min"] = _to_float(rssi_min)
            edge["rssi_max"] = _to_float(rssi_max)
        edges.append(edge)
    return edges


def load_link_edges(
    store: HistoryStoreReadState,
    *,
    window: object = "7d",
    limit: object = _DEFAULT_LIMIT,
) -> dict[str, object]:
    clean_window = _normalize_link_window(window)
    clean_limit = _clean_limit(limit, window=clean_window)
    window_seconds = int(_WINDOW_SECONDS[clean_window])
    cutoff_unix = 0
    if window_seconds > 0:
        cutoff_unix = max(0, int(time.time()) - window_seconds)

    read_conn = getattr(store, "_read_conn", None)
    if read_conn is None or read_conn is store._conn:
        read_conn = store._conn
        read_lock = store._lock
    else:
        read_lock = getattr(store, "_read_lock", None) or store._lock

    with read_lock:
        rows = _fetch_link_metric_edge_rows(
            read_conn,
            cutoff_unix=cutoff_unix,
            limit=clean_limit + 1,
        )
        capability_rows = _fetch_node_capability_rows(read_conn)

    truncated = len(rows) > clean_limit
    edges = _decode_link_metric_edge_rows(rows[:clean_limit])
    edge_node_ids = {
        str(value or "").strip()
        for edge in edges
        for value in (edge.get("from"), edge.get("to"))
    }
    capability_map = _decode_node_capabilities_rows(capability_rows)
    history_caps = {
        node_id: caps
        for node_id, caps in capability_map.items()
        if node_id in edge_node_ids
    }
    return {
        "ok": True,
        "window": clean_window,
        "window_seconds": window_seconds,
        "limit": clean_limit,
        "truncated": truncated,
        "edge_count": len(edges),
        "history_caps": history_caps,
        "edges": edges,
    }
