from typing import Callable, Optional

from .sql_contracts import SqlConnection


def backfill_node_capabilities(
    conn: SqlConnection,
    *,
    to_int_fn: Callable[[object], Optional[int]],
) -> None:
    existing = conn.execute("SELECT COUNT(*) FROM node_capabilities").fetchone()
    if existing and int(existing[0] or 0) > 0:
        return

    merged: dict[str, dict[str, object]] = {}

    metric_rows = conn.execute(
        """
        SELECT node_id, MAX(last_seen_unix)
        FROM node_metrics_1m
        GROUP BY node_id
        """
    ).fetchall()
    for node_id, last_seen_unix in metric_rows:
        clean_node_id = str(node_id or "").strip()
        seen = to_int_fn(last_seen_unix)
        if not clean_node_id or seen is None:
            continue
        merged.setdefault(clean_node_id, {})
        merged[clean_node_id]["last_seen_unix"] = seen

    position_rows = conn.execute(
        """
        SELECT node_id, MAX(created_unix)
        FROM node_positions
        GROUP BY node_id
        """
    ).fetchall()
    for node_id, last_position_unix in position_rows:
        clean_node_id = str(node_id or "").strip()
        pos_unix = to_int_fn(last_position_unix)
        if not clean_node_id or pos_unix is None:
            continue
        node = merged.setdefault(clean_node_id, {})
        node["has_position"] = True
        node["last_position_unix"] = pos_unix
        node["last_seen_unix"] = max(to_int_fn(node.get("last_seen_unix")) or pos_unix, pos_unix)

    hop_rows = conn.execute(
        """
        SELECT events.from_id, events.hops, events.created_unix
        FROM packet_events AS events
        JOIN (
          SELECT from_id, MAX(id) AS max_id
          FROM packet_events
          WHERE from_id IS NOT NULL AND hops IS NOT NULL
          GROUP BY from_id
        ) AS latest
          ON latest.from_id = events.from_id AND latest.max_id = events.id
        """
    ).fetchall()
    for node_id, last_hops, hop_seen_unix in hop_rows:
        clean_node_id = str(node_id or "").strip()
        hops = to_int_fn(last_hops)
        seen = to_int_fn(hop_seen_unix)
        if not clean_node_id:
            continue
        node = merged.setdefault(clean_node_id, {})
        if hops is not None and hops >= 0:
            node["last_hops"] = hops
        if seen is not None:
            node["last_seen_unix"] = max(to_int_fn(node.get("last_seen_unix")) or seen, seen)

    for node_id, values in merged.items():
        seen = to_int_fn(values.get("last_seen_unix"))
        if seen is None or seen <= 0:
            continue
        has_position = 1 if values.get("has_position") else 0
        conn.execute(
            """
            INSERT OR REPLACE INTO node_capabilities(
              node_id, last_seen_unix, has_position, last_position_unix,
              last_hops, battery_level, battery_updated_unix
            ) VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node_id,
                seen,
                has_position,
                to_int_fn(values.get("last_position_unix")),
                to_int_fn(values.get("last_hops")),
                None,
                None,
            ),
        )
