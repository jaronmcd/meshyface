import time
from typing import Callable, Optional

from .helpers import safe_json_loads as _safe_json_loads
from .helpers import to_int as _to_int
from .helpers_node_names import extract_user_names_from_packet as _extract_user_names_from_packet
from .helpers_node_names import normalize_node_id_text as _normalize_node_id_text
from .history_capability_writes import upsert_node_capability as _upsert_node_capability_helper
from .history_writes import (
    save_environment_metric_rollups as _save_environment_metric_rollups_helper,
)
from .sql_contracts import SqlConnection


def backfill_node_capabilities(
    conn: SqlConnection,
    *,
    to_int_fn: Callable[[object], Optional[int]],
) -> None:
    existing = conn.execute("SELECT COUNT(*) FROM node_capabilities").fetchone()
    table_has_rows = bool(existing and int(existing[0] or 0) > 0)

    merged: dict[str, dict[str, object]] = {}

    if not table_has_rows:
        metric_rows = conn.execute(
            """
            SELECT node_id, MIN(last_seen_unix), MAX(last_seen_unix)
            FROM node_metrics_1m
            GROUP BY node_id
            """
        ).fetchall()
        for node_id, first_seen_unix, last_seen_unix in metric_rows:
            clean_node_id = str(node_id or "").strip()
            first_seen = to_int_fn(first_seen_unix)
            seen = to_int_fn(last_seen_unix)
            if not clean_node_id or seen is None:
                continue
            merged.setdefault(clean_node_id, {})
            if first_seen is not None and first_seen > 0:
                merged[clean_node_id]["first_seen_unix"] = first_seen
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
            node["first_seen_unix"] = min(to_int_fn(node.get("first_seen_unix")) or pos_unix, pos_unix)
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
                node["first_seen_unix"] = min(to_int_fn(node.get("first_seen_unix")) or seen, seen)
                node["last_seen_unix"] = max(to_int_fn(node.get("last_seen_unix")) or seen, seen)

        for node_id, values in merged.items():
            seen = to_int_fn(values.get("last_seen_unix"))
            if seen is None or seen <= 0:
                continue
            has_position = 1 if values.get("has_position") else 0
            conn.execute(
                """
                INSERT OR REPLACE INTO node_capabilities(
                  node_id, first_seen_unix, last_seen_unix, has_position, last_position_unix,
                  last_hops, battery_level, battery_updated_unix,
                  last_short_name, last_long_name, names_updated_unix
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node_id,
                    to_int_fn(values.get("first_seen_unix")) or seen,
                    seen,
                    has_position,
                    to_int_fn(values.get("last_position_unix")),
                    to_int_fn(values.get("last_hops")),
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            )

    latest_names_by_node: dict[str, dict[str, object]] = {}
    name_rows = conn.execute(
        """
        SELECT created_unix, summary_json, packet_json
        FROM packets
        WHERE summary_json LIKE '%"portnum":"NODEINFO_APP"%'
        ORDER BY id ASC
        """
    ).fetchall()
    for created_unix, summary_json, packet_json in name_rows:
        summary = _safe_json_loads(summary_json, {})
        packet = _safe_json_loads(packet_json, {})
        if not isinstance(summary, dict) or not isinstance(packet, dict):
            continue
        short_name, long_name = _extract_user_names_from_packet(summary, packet)
        if not short_name and not long_name:
            continue
        node_id = _normalize_node_id_text(
            summary.get("from")
            or packet.get("fromId")
            or packet.get("from_id")
            or packet.get("from")
        )
        if not node_id:
            decoded = packet.get("decoded")
            if isinstance(decoded, dict):
                user = decoded.get("user")
                if isinstance(user, dict):
                    node_id = _normalize_node_id_text(user.get("id") or user.get("node_id"))
        if not node_id:
            continue
        event_unix = to_int_fn(created_unix) or 0
        previous = latest_names_by_node.get(node_id)
        if previous and int(previous.get("event_unix") or 0) > event_unix:
            continue
        latest_names_by_node[node_id] = {
            "event_unix": event_unix,
            "last_short_name": short_name,
            "last_long_name": long_name,
        }

    for node_id, values in latest_names_by_node.items():
        event_unix = to_int_fn(values.get("event_unix")) or 0
        if event_unix <= 0:
            continue
        _upsert_node_capability_helper(
            conn,
            node_id=node_id,
            event_unix=event_unix,
            has_position=False,
            last_hops=None,
            battery_level=None,
            last_short_name=values.get("last_short_name"),
            last_long_name=values.get("last_long_name"),
        )


def backfill_node_saved_counts(conn: SqlConnection) -> None:
    """Populate node_saved_counts from node_metrics_1m if it's empty.

    The node_saved_counts table is maintained incrementally via triggers going
    forward, but existing databases need an initial fill so /api/state does not
    fall back to expensive GROUP BY scans.
    """
    try:
        existing = conn.execute("SELECT COUNT(*) FROM node_saved_counts").fetchone()
    except Exception:
        # Old schema without node_saved_counts (should be created by
        # initialize_history_schema, but be defensive).
        existing = None

    if existing and int(existing[0] or 0) > 0:
        return

    rows = conn.execute(
        """
        SELECT node_id,
               SUM(packet_count) AS saved_packets,
               COUNT(*) AS saved_points,
               MAX(last_seen_unix) AS saved_last_seen_unix
        FROM node_metrics_1m
        GROUP BY node_id
        """
    ).fetchall()
    for node_id, saved_packets, saved_points, saved_last_seen_unix in rows:
        clean_node_id = str(node_id or "").strip()
        if not clean_node_id:
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO node_saved_counts(
              node_id, saved_packets, saved_points, saved_last_seen_unix
            ) VALUES(?, ?, ?, ?)
            """,
            (
                clean_node_id,
                int(saved_packets or 0),
                int(saved_points or 0),
                int(saved_last_seen_unix or 0),
            ),
        )


def backfill_node_position_counts(conn: SqlConnection) -> None:
    """Populate node_position_counts from node_positions if it's empty."""
    try:
        existing = conn.execute("SELECT COUNT(*) FROM node_position_counts").fetchone()
    except Exception:
        existing = None

    if existing and int(existing[0] or 0) > 0:
        return

    rows = conn.execute(
        """
        SELECT node_id,
               COUNT(*) AS position_points,
               MAX(created_unix) AS position_last_seen_unix
        FROM node_positions
        GROUP BY node_id
        """
    ).fetchall()
    for node_id, position_points, position_last_seen_unix in rows:
        clean_node_id = str(node_id or "").strip()
        if not clean_node_id:
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO node_position_counts(
              node_id, position_points, position_last_seen_unix
            ) VALUES(?, ?, ?)
            """,
            (
                clean_node_id,
                int(position_points or 0),
                int(position_last_seen_unix or 0),
            ),
        )


def backfill_node_hour_seen(conn: SqlConnection) -> None:
    """Populate node_hour_seen from node_metrics_1m if it's empty.

    node_hour_seen is maintained incrementally via triggers going forward, but
    existing databases need an initial fill so Top 10 presence queries can run
    quickly without scanning the 1-minute rollup.
    """
    try:
        existing = conn.execute("SELECT COUNT(*) FROM node_hour_seen").fetchone()
    except Exception:
        existing = None

    if existing and int(existing[0] or 0) > 0:
        return

    try:
        rows = conn.execute(
            """
            SELECT DISTINCT (bucket_unix - (bucket_unix % 3600)) AS hour_bucket,
                            node_id
            FROM node_metrics_1m
            """
        ).fetchall()
    except Exception:
        rows = []

    for hour_bucket, node_id in rows:
        clean_node_id = str(node_id or "").strip()
        if not clean_node_id:
            continue
        try:
            conn.execute(
                "INSERT OR IGNORE INTO node_hour_seen(hour_bucket, node_id) VALUES(?, ?)",
                (int(hour_bucket or 0), clean_node_id),
            )
        except Exception:
            continue


def backfill_environment_metric_rollups(
    conn: SqlConnection,
    *,
    reset_existing: bool = False,
    commit_every: int = 1000,
    now_unix_fn: Callable[[], float] = time.time,
) -> dict[str, int]:
    if bool(reset_existing):
        conn.execute("DELETE FROM environment_metrics_1m")

    before_row = conn.execute("SELECT COUNT(*) FROM environment_metrics_1m").fetchone()
    before_rows = int((before_row[0] if before_row else 0) or 0)

    scanned_packets = 0
    usable_packets = 0
    bad_rows = 0
    rows = conn.execute(
        "SELECT created_unix, summary_json, packet_json FROM packets ORDER BY id ASC"
    ).fetchall()
    clean_commit_every = max(0, int(commit_every))
    for index, row in enumerate(rows, start=1):
        scanned_packets += 1
        created_unix = row[0] if len(row) > 0 else None
        summary_json = row[1] if len(row) > 1 else None
        packet_json = row[2] if len(row) > 2 else None

        summary = _safe_json_loads(summary_json, {})
        packet = _safe_json_loads(packet_json, {})
        if not isinstance(summary, dict) or not isinstance(packet, dict):
            bad_rows += 1
            continue
        usable_packets += 1

        fallback_unix = int(_to_int(created_unix) or 0)
        fallback_now_fn = (
            (lambda fallback=fallback_unix: float(fallback))
            if fallback_unix > 0
            else now_unix_fn
        )
        _save_environment_metric_rollups_helper(
            conn,
            summary=summary,
            packet=packet,
            now_unix_fn=fallback_now_fn,
        )
        if clean_commit_every > 0 and (index % clean_commit_every) == 0:
            conn.commit()

    after_row = conn.execute("SELECT COUNT(*) FROM environment_metrics_1m").fetchone()
    after_rows = int((after_row[0] if after_row else 0) or 0)
    return {
        "before_rows": before_rows,
        "after_rows": after_rows,
        "delta_rows": max(0, after_rows - before_rows),
        "scanned_packets": scanned_packets,
        "usable_packets": usable_packets,
        "bad_rows": bad_rows,
    }
