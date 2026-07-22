from collections.abc import Iterable

from .helpers import format_epoch as _format_epoch
from .helpers import to_int as _to_int
from .history_queries import PACKET_TYPE_CASE_SQL
from .history_store_runtime_contracts import HistoryStoreReadState
from .sql_contracts import SqlConnection, SqlRows


_DEFAULT_LIMIT = 10
_MAX_LIMIT = 50
_ALL_CATEGORY_ID = "all"
_ALL_CATEGORY_META = {
    "id": _ALL_CATEGORY_ID,
    "label": "All Categories",
    "unit": "",
    "source": "history",
}
_DEVICE_UPTIME_METRIC_KEYS = ("uptimeseconds", "uptime_seconds", "uptime", "device_uptime")

TOP_NODE_CATEGORIES: tuple[dict[str, str], ...] = (
    {
        "id": "saved_packets",
        "label": "Saved Packets",
        "unit": "packets",
        "source": "node_saved_counts",
    },
    {
        "id": "device_uptime",
        "label": "Device Uptime",
        "unit": "seconds",
        "source": "environment_metrics_1m",
    },
    {
        "id": "active_hours",
        "label": "Seen Hours",
        "unit": "hours",
        "source": "node_hour_seen",
    },
    {
        "id": "chat_packets",
        "label": "Chats",
        "unit": "chats",
        "source": "packet_events",
    },
    {
        "id": "gps_positions",
        "label": "GPS Positions",
        "unit": "positions",
        "source": "node_positions",
    },
    {
        "id": "environment_metrics",
        "label": "Metrics",
        "unit": "samples",
        "source": "environment_metrics_1m",
    },
    {
        "id": "links",
        "label": "Links",
        "unit": "links",
        "source": "connections",
    },
    {
        "id": "link_packets",
        "label": "Link Packets",
        "unit": "packets",
        "source": "connections",
    },
    {
        "id": "telemetry_packets",
        "label": "Telemetry",
        "unit": "packets",
        "source": "packet_events",
    },
    {
        "id": "position_packets",
        "label": "Position Packets",
        "unit": "packets",
        "source": "packet_events",
    },
    {
        "id": "routing_packets",
        "label": "Routing",
        "unit": "packets",
        "source": "packet_events",
    },
    {
        "id": "nodeinfo_packets",
        "label": "Node Info",
        "unit": "packets",
        "source": "packet_events",
    },
    {
        "id": "direct_packets",
        "label": "Direct Sends",
        "unit": "packets",
        "source": "packet_events",
    },
    {
        "id": "storeforward_packets",
        "label": "Store/Fwd",
        "unit": "packets",
        "source": "packet_events",
    },
    {
        "id": "admin_packets",
        "label": "Admin",
        "unit": "packets",
        "source": "packet_events",
    },
    {
        "id": "encrypted_packets",
        "label": "Encrypted",
        "unit": "packets",
        "source": "packet_events",
    },
    {
        "id": "other_packets",
        "label": "Other Packets",
        "unit": "packets",
        "source": "packet_events",
    },
)

_CATEGORY_BY_ID = {entry["id"]: entry for entry in TOP_NODE_CATEGORIES}

_PORT_CATEGORY_TO_PORTNUM = {
    "chat_packets": "TEXT_MESSAGE_APP",
    "telemetry_packets": "TELEMETRY_APP",
    "position_packets": "POSITION_APP",
    "routing_packets": "ROUTING_APP",
    "nodeinfo_packets": "NODEINFO_APP",
    "storeforward_packets": "STORE_FORWARD_APP",
    "admin_packets": "ADMIN_APP",
}


def normalize_top_node_category(raw_category: object) -> str:
    clean = str(raw_category or "").strip().lower().replace("-", "_")
    aliases = {
        "everything": _ALL_CATEGORY_ID,
        "all_categories": _ALL_CATEGORY_ID,
        "all_lists": _ALL_CATEGORY_ID,
        "packets": "saved_packets",
        "stored_packets": "saved_packets",
        "saved": "saved_packets",
        "uptime": "device_uptime",
        "uptime_seconds": "device_uptime",
        "uptimeseconds": "device_uptime",
        "device_uptime_seconds": "device_uptime",
        "active": "active_hours",
        "seen": "active_hours",
        "seen_hours": "active_hours",
        "presence": "active_hours",
        "presence_hours": "active_hours",
        "chats": "chat_packets",
        "chat": "chat_packets",
        "gps": "gps_positions",
        "positions": "gps_positions",
        "position": "position_packets",
        "metrics": "environment_metrics",
        "metric": "environment_metrics",
        "telemetry": "telemetry_packets",
        "link": "links",
        "link_count": "links",
        "link_packets": "link_packets",
        "routing": "routing_packets",
        "nodeinfo": "nodeinfo_packets",
        "node_info": "nodeinfo_packets",
        "direct": "direct_packets",
        "store_forward": "storeforward_packets",
        "storefwd": "storeforward_packets",
        "encrypted": "encrypted_packets",
        "other": "other_packets",
    }
    clean = aliases.get(clean, clean)
    if clean == _ALL_CATEGORY_ID:
        return _ALL_CATEGORY_ID
    return clean if clean in _CATEGORY_BY_ID else "saved_packets"


def _clean_limit(limit: object) -> int:
    parsed = _to_int(limit)
    if parsed is None:
        parsed = _DEFAULT_LIMIT
    return max(1, min(_MAX_LIMIT, int(parsed)))


def _clean_node_id(node_id: object) -> str:
    return str(node_id or "").strip()


def _clean_excluded_node_ids(excluded_node_ids: object = None) -> set[str]:
    if excluded_node_ids is None:
        return set()
    if isinstance(excluded_node_ids, str):
        candidates: Iterable[object] = [excluded_node_ids]
    else:
        try:
            candidates = list(excluded_node_ids)  # type: ignore[arg-type]
        except Exception:
            candidates = [excluded_node_ids]
    return {
        clean.lower()
        for clean in (_clean_node_id(candidate) for candidate in candidates)
        if clean
    }


def _valid_node_clause(column_name: str = "node_id") -> str:
    return (
        f"trim(COALESCE({column_name}, '')) <> '' "
        f"AND trim(COALESCE({column_name}, '')) NOT IN ('Unknown', 'n/a', '^all')"
    )


def _fetch_saved_packet_rows(conn: SqlConnection, limit: int) -> SqlRows:
    return conn.execute(
        f"""
        SELECT node_id,
               saved_packets AS value,
               saved_points AS secondary_value,
               saved_last_seen_unix AS last_seen_unix
        FROM node_saved_counts
        WHERE {_valid_node_clause("node_id")}
          AND COALESCE(saved_packets, 0) > 0
        ORDER BY saved_packets DESC, saved_last_seen_unix DESC, node_id ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def _fetch_active_hour_rows(conn: SqlConnection, limit: int) -> SqlRows:
    return conn.execute(
        f"""
        SELECT node_id,
               COUNT(*) AS value,
               NULL AS secondary_value,
               MAX(hour_bucket) AS last_seen_unix
        FROM node_hour_seen
        WHERE {_valid_node_clause("node_id")}
        GROUP BY node_id
        HAVING value > 0
        ORDER BY value DESC, last_seen_unix DESC, node_id ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def _fetch_device_uptime_rows(conn: SqlConnection, limit: int) -> SqlRows:
    placeholders = ", ".join("?" for _ in _DEVICE_UPTIME_METRIC_KEYS)
    return conn.execute(
        f"""
        WITH uptime_rows AS (
          SELECT node_id,
                 sample_count,
                 last_value,
                 last_seen_unix
          FROM environment_metrics_1m
          WHERE {_valid_node_clause("node_id")}
            AND lower(trim(COALESCE(metric_key, ''))) IN ({placeholders})
            AND COALESCE(last_value, 0) > 0
        ),
        latest_rows AS (
          SELECT node_id,
                 MAX(last_seen_unix) AS last_seen_unix
          FROM uptime_rows
          GROUP BY node_id
        ),
        sample_counts AS (
          SELECT node_id,
                 SUM(sample_count) AS sample_count
          FROM uptime_rows
          GROUP BY node_id
        )
        SELECT latest.node_id,
               CAST(MAX(latest.last_value) AS INTEGER) AS value,
               counts.sample_count AS secondary_value,
               latest_seen.last_seen_unix AS last_seen_unix
        FROM uptime_rows latest
        JOIN latest_rows latest_seen
          ON latest_seen.node_id = latest.node_id
         AND latest_seen.last_seen_unix = latest.last_seen_unix
        JOIN sample_counts counts
          ON counts.node_id = latest.node_id
        GROUP BY latest.node_id
        HAVING value > 0
        ORDER BY value DESC, last_seen_unix DESC, latest.node_id ASC
        LIMIT ?
        """,
        (*_DEVICE_UPTIME_METRIC_KEYS, limit),
    ).fetchall()


def _fetch_gps_position_rows(conn: SqlConnection, limit: int) -> SqlRows:
    return conn.execute(
        f"""
        SELECT node_id,
               COUNT(*) AS value,
               NULL AS secondary_value,
               MAX(created_unix) AS last_seen_unix
        FROM node_positions
        WHERE {_valid_node_clause("node_id")}
        GROUP BY node_id
        HAVING value > 0
        ORDER BY value DESC, last_seen_unix DESC, node_id ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def _fetch_environment_metric_rows(conn: SqlConnection, limit: int) -> SqlRows:
    return conn.execute(
        f"""
        SELECT node_id,
               SUM(sample_count) AS value,
               COUNT(DISTINCT metric_key) AS secondary_value,
               MAX(last_seen_unix) AS last_seen_unix
        FROM environment_metrics_1m
        WHERE {_valid_node_clause("node_id")}
        GROUP BY node_id
        HAVING value > 0
        ORDER BY value DESC, last_seen_unix DESC, node_id ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def _fetch_link_rows(conn: SqlConnection, *, limit: int, by_packets: bool) -> SqlRows:
    value_expr = "SUM(seen_count)" if by_packets else "COUNT(DISTINCT peer_id)"
    secondary_expr = "COUNT(DISTINCT peer_id)" if by_packets else "SUM(seen_count)"
    return conn.execute(
        f"""
        SELECT node_id,
               {value_expr} AS value,
               {secondary_expr} AS secondary_value,
               MAX(last_seen_unix) AS last_seen_unix
        FROM (
          SELECT from_id AS node_id, to_id AS peer_id, seen_count, last_seen_unix
          FROM connections
          WHERE {_valid_node_clause("from_id")}
            AND {_valid_node_clause("to_id")}
          UNION ALL
          SELECT to_id AS node_id, from_id AS peer_id, seen_count, last_seen_unix
          FROM connections
          WHERE {_valid_node_clause("to_id")}
            AND {_valid_node_clause("from_id")}
        )
        GROUP BY node_id
        HAVING value > 0
        ORDER BY value DESC, last_seen_unix DESC, node_id ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def _fetch_direct_packet_rows(conn: SqlConnection, limit: int) -> SqlRows:
    return conn.execute(
        f"""
        SELECT from_id AS node_id,
               COUNT(*) AS value,
               COUNT(DISTINCT to_id) AS secondary_value,
               MAX(created_unix) AS last_seen_unix
        FROM packet_events
        WHERE {_valid_node_clause("from_id")}
          AND {_valid_node_clause("to_id")}
          AND from_id <> to_id
        GROUP BY from_id
        HAVING value > 0
        ORDER BY value DESC, last_seen_unix DESC, node_id ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def _fetch_packet_category_rows(conn: SqlConnection, *, category: str, limit: int) -> SqlRows:
    portnum = _PORT_CATEGORY_TO_PORTNUM.get(category)
    if portnum:
        return conn.execute(
            f"""
            SELECT from_id AS node_id,
                   COUNT(*) AS value,
                   COUNT(DISTINCT to_id) AS secondary_value,
                   MAX(created_unix) AS last_seen_unix
            FROM packet_events
            WHERE {_valid_node_clause("from_id")}
              AND upper(trim(COALESCE(portnum, ''))) = ?
            GROUP BY from_id
            HAVING value > 0
            ORDER BY value DESC, last_seen_unix DESC, node_id ASC
            LIMIT ?
            """,
            (portnum, limit),
        ).fetchall()

    if category == "encrypted_packets":
        return conn.execute(
            f"""
            SELECT from_id AS node_id,
                   COUNT(*) AS value,
                   COUNT(DISTINCT to_id) AS secondary_value,
                   MAX(created_unix) AS last_seen_unix
            FROM packet_events
            WHERE {_valid_node_clause("from_id")}
              AND trim(COALESCE(portnum, '')) = ''
            GROUP BY from_id
            HAVING value > 0
            ORDER BY value DESC, last_seen_unix DESC, node_id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    if category == "other_packets":
        return conn.execute(
            f"""
            SELECT from_id AS node_id,
                   COUNT(*) AS value,
                   COUNT(DISTINCT to_id) AS secondary_value,
                   MAX(created_unix) AS last_seen_unix
            FROM packet_events
            WHERE {_valid_node_clause("from_id")}
              AND ({PACKET_TYPE_CASE_SQL}) = 'other'
            GROUP BY from_id
            HAVING value > 0
            ORDER BY value DESC, last_seen_unix DESC, node_id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return conn.execute(
        f"""
        SELECT from_id AS node_id,
               COUNT(*) AS value,
               COUNT(DISTINCT to_id) AS secondary_value,
               MAX(created_unix) AS last_seen_unix
        FROM packet_events
        WHERE {_valid_node_clause("from_id")}
        GROUP BY from_id
        HAVING value > 0
        ORDER BY value DESC, last_seen_unix DESC, node_id ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def _fetch_category_rows(conn: SqlConnection, category: str, limit: int) -> SqlRows:
    if category == "saved_packets":
        return _fetch_saved_packet_rows(conn, limit)
    if category == "device_uptime":
        return _fetch_device_uptime_rows(conn, limit)
    if category == "active_hours":
        return _fetch_active_hour_rows(conn, limit)
    if category == "gps_positions":
        return _fetch_gps_position_rows(conn, limit)
    if category == "environment_metrics":
        return _fetch_environment_metric_rows(conn, limit)
    if category == "links":
        return _fetch_link_rows(conn, limit=limit, by_packets=False)
    if category == "link_packets":
        return _fetch_link_rows(conn, limit=limit, by_packets=True)
    if category == "direct_packets":
        return _fetch_direct_packet_rows(conn, limit)
    return _fetch_packet_category_rows(conn, category=category, limit=limit)


def _item_from_row(row: object, rank: int) -> dict[str, object] | None:
    if isinstance(row, tuple):
        raw = row
    elif isinstance(row, list):
        raw = tuple(row)
    else:
        try:
            raw = tuple(row)  # type: ignore[arg-type]
        except Exception:
            return None
    if len(raw) < 2:
        return None

    node_id = str(raw[0] or "").strip()
    if not node_id:
        return None
    value = _to_int(raw[1])
    if value is None or value <= 0:
        return None
    secondary = _to_int(raw[2]) if len(raw) > 2 else None
    last_seen_unix = _to_int(raw[3]) if len(raw) > 3 else None

    item: dict[str, object] = {
        "rank": rank,
        "node_id": node_id,
        "value": int(value),
    }
    if secondary is not None:
        item["secondary_value"] = int(secondary)
    if last_seen_unix is not None and last_seen_unix > 0:
        item["last_seen_unix"] = int(last_seen_unix)
        item["last_seen"] = _format_epoch(last_seen_unix)
    return item


def build_top_nodes_payload(
    *,
    category: object,
    rows: Iterable[object],
    limit: object = _DEFAULT_LIMIT,
    exclude_node_ids: object = None,
) -> dict[str, object]:
    clean_category = normalize_top_node_category(category)
    clean_limit = _clean_limit(limit)
    excluded = _clean_excluded_node_ids(exclude_node_ids)
    category_meta = dict(_CATEGORY_BY_ID.get(clean_category, _ALL_CATEGORY_META))
    items: list[dict[str, object]] = []
    for row in rows:
        item = _item_from_row(row, len(items) + 1)
        if item is None:
            continue
        if _clean_node_id(item.get("node_id")).lower() in excluded:
            continue
        item["rank"] = len(items) + 1
        items.append(item)
        if len(items) >= clean_limit:
            break
    return {
        "ok": True,
        "category": clean_category,
        "category_label": category_meta.get("label") or clean_category,
        "unit": category_meta.get("unit") or "",
        "source": category_meta.get("source") or "history",
        "limit": clean_limit,
        "categories": [dict(_ALL_CATEGORY_META), *[dict(entry) for entry in TOP_NODE_CATEGORIES]],
        "items": items,
    }


def build_top_nodes_groups_payload(
    *,
    groups: Iterable[dict[str, object]],
    limit: object = _DEFAULT_LIMIT,
) -> dict[str, object]:
    clean_limit = _clean_limit(limit)
    clean_groups: list[dict[str, object]] = []
    item_count = 0
    for group in groups:
        if not isinstance(group, dict):
            continue
        clean_group = dict(group)
        clean_group.pop("categories", None)
        items = clean_group.get("items")
        if isinstance(items, list):
            item_count += len(items)
        clean_groups.append(clean_group)
    return {
        "ok": True,
        "category": _ALL_CATEGORY_ID,
        "category_label": _ALL_CATEGORY_META["label"],
        "unit": "",
        "source": "history",
        "limit": clean_limit,
        "categories": [dict(_ALL_CATEGORY_META), *[dict(entry) for entry in TOP_NODE_CATEGORIES]],
        "groups": clean_groups,
        "item_count": item_count,
        "items": [],
    }


def load_top_nodes(
    store: HistoryStoreReadState,
    *,
    category: object = "saved_packets",
    limit: object = _DEFAULT_LIMIT,
    exclude_node_ids: object = None,
) -> dict[str, object]:
    clean_category = normalize_top_node_category(category)
    clean_limit = _clean_limit(limit)
    excluded = _clean_excluded_node_ids(exclude_node_ids)
    fetch_limit = clean_limit + len(excluded)
    read_conn = getattr(store, "_read_conn", None)
    if read_conn is None or read_conn is store._conn:
        read_conn = store._conn
        read_lock = store._lock
    else:
        read_lock = getattr(store, "_read_lock", None) or store._lock
    if clean_category == _ALL_CATEGORY_ID:
        groups: list[dict[str, object]] = []
        with read_lock:
            for entry in TOP_NODE_CATEGORIES:
                entry_id = entry["id"]
                rows = _fetch_category_rows(read_conn, entry_id, fetch_limit)
                groups.append(
                    build_top_nodes_payload(
                        category=entry_id,
                        rows=rows,
                        limit=clean_limit,
                        exclude_node_ids=excluded,
                    )
                )
        return build_top_nodes_groups_payload(
            groups=groups,
            limit=clean_limit,
        )
    with read_lock:
        rows = _fetch_category_rows(read_conn, clean_category, fetch_limit)
    return build_top_nodes_payload(
        category=clean_category,
        rows=rows,
        limit=clean_limit,
        exclude_node_ids=excluded,
    )
