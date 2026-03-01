from .sql_contracts import SqlConnection, SqlRows


def fetch_recent_packet_rows(conn: SqlConnection, limit: int) -> SqlRows:
    return conn.execute(
        "SELECT summary_json, packet_json FROM packets ORDER BY id DESC LIMIT ?",
        (max(1, int(limit)),),
    ).fetchall()


def fetch_recent_chat_rows(conn: SqlConnection, limit: int) -> SqlRows:
    return conn.execute(
        "SELECT message_json FROM chat ORDER BY id DESC LIMIT ?",
        (max(1, int(limit)),),
    ).fetchall()


def fetch_connection_rows(conn: SqlConnection) -> SqlRows:
    return conn.execute(
        """
        SELECT from_id, to_id, first_seen_unix, last_seen_unix, seen_count,
               portnums_json, last_hops, hops_sum, hops_count
        FROM connections
        ORDER BY last_seen_unix DESC
        """
    ).fetchall()


def fetch_node_history_rows(
    conn: SqlConnection,
    *,
    node_id: str,
    cutoff: int,
    limit: int,
) -> tuple[SqlRows, SqlRows]:
    metric_rows = conn.execute(
        """
        SELECT bucket_unix, packet_count,
               snr_sum, snr_count, snr_min, snr_max,
               rssi_sum, rssi_count, rssi_min, rssi_max,
               hops_sum, hops_count, hops_min, hops_max,
               last_seen_unix
        FROM node_metrics_1m
        WHERE node_id = ? AND bucket_unix >= ?
        ORDER BY bucket_unix DESC
        LIMIT ?
        """,
        (node_id, cutoff, limit),
    ).fetchall()
    position_rows = conn.execute(
        """
        SELECT created_unix, lat, lon, altitude, sats_in_view
        FROM node_positions
        WHERE node_id = ? AND created_unix >= ?
        ORDER BY created_unix DESC
        LIMIT ?
        """,
        (node_id, cutoff, limit),
    ).fetchall()
    return metric_rows, position_rows


def fetch_online_activity_rows(conn: SqlConnection, cutoff: int) -> tuple[SqlRows, int]:
    # node_hour_seen is a compact per-node-per-hour presence table maintained
    # via triggers on node_metrics_1m. It's dramatically smaller than the
    # 1-minute rollup, so these queries stay snappy even with large histories.
    cutoff_hour = int(cutoff) - (int(cutoff) % 3600)
    hour_rows = conn.execute(
        """
        SELECT hour_bucket,
               COUNT(*) AS online_nodes
        FROM node_hour_seen
        WHERE hour_bucket >= ?
        GROUP BY hour_bucket
        ORDER BY hour_bucket ASC
        """,
        (cutoff_hour,),
    ).fetchall()
    distinct_row = conn.execute(
        "SELECT COUNT(DISTINCT node_id) FROM node_hour_seen WHERE hour_bucket >= ?",
        (cutoff_hour,),
    ).fetchone()
    distinct_nodes = int((distinct_row[0] if distinct_row else 0) or 0)
    return hour_rows, distinct_nodes


def fetch_summary_metrics_rows(
    conn: SqlConnection,
    *,
    cutoff: int,
    limit: int,
) -> SqlRows:
    cutoff_bucket = int(cutoff) - (int(cutoff) % 60)
    return conn.execute(
        """
        SELECT bucket_unix,
               node_count,
               nodes_with_position,
               live_packet_count,
               real_edge_count
        FROM summary_metrics_1m
        WHERE bucket_unix >= ?
        ORDER BY bucket_unix ASC
        LIMIT ?
        """,
        (cutoff_bucket, max(1, int(limit))),
    ).fetchall()


def fetch_node_saved_count_rows(conn: SqlConnection) -> SqlRows:
    # NOTE: node_saved_counts is maintained by triggers on node_metrics_1m.
    # This avoids scanning/grouping the entire rollup table on every /api/state
    # refresh, which can become a major UI latency source.
    return conn.execute(
        """
        SELECT node_id,
               saved_packets,
               saved_points,
               saved_last_seen_unix
        FROM node_saved_counts
        """
    ).fetchall()


def fetch_node_capability_rows(conn: SqlConnection) -> SqlRows:
    return conn.execute(
        """
        SELECT node_id, last_seen_unix, has_position, last_position_unix,
               last_hops, battery_level, battery_updated_unix
        FROM node_capabilities
        ORDER BY last_seen_unix DESC
        """
    ).fetchall()
