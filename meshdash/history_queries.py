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
    hour_rows = conn.execute(
        """
        SELECT bucket_unix - (bucket_unix % 3600) AS hour_bucket,
               COUNT(DISTINCT node_id) AS online_nodes
        FROM node_metrics_1m
        WHERE bucket_unix >= ?
        GROUP BY hour_bucket
        ORDER BY hour_bucket ASC
        """,
        (cutoff,),
    ).fetchall()
    distinct_row = conn.execute(
        "SELECT COUNT(DISTINCT node_id) FROM node_metrics_1m WHERE bucket_unix >= ?",
        (cutoff,),
    ).fetchone()
    distinct_nodes = int((distinct_row[0] if distinct_row else 0) or 0)
    return hour_rows, distinct_nodes


def fetch_node_saved_count_rows(conn: SqlConnection) -> SqlRows:
    return conn.execute(
        """
        SELECT node_id,
               SUM(packet_count) AS saved_packets,
               COUNT(*) AS saved_points,
               MAX(last_seen_unix) AS saved_last_seen_unix
        FROM node_metrics_1m
        GROUP BY node_id
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
