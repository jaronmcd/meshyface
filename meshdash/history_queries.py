from .sql_contracts import SqlConnection, SqlRows
from .history_summary_sampling import (
    summary_metrics_bucket_seconds as _summary_metrics_bucket_seconds,
    summary_metrics_bucket_unix as _summary_metrics_bucket_unix,
)

_PACKET_TYPE_CASE_SQL = """
CASE
  WHEN trim(COALESCE(portnum, '')) = '' THEN 'encrypted'
  WHEN upper(trim(portnum)) = 'TEXT_MESSAGE_APP' THEN 'chat'
  WHEN upper(trim(portnum)) = 'TELEMETRY_APP' THEN 'telemetry'
  WHEN upper(trim(portnum)) = 'POSITION_APP' THEN 'position'
  WHEN upper(trim(portnum)) = 'ROUTING_APP' THEN 'routing'
  WHEN upper(trim(portnum)) = 'STORE_FORWARD_APP' THEN 'storeforward'
  WHEN upper(trim(portnum)) = 'NODEINFO_APP' THEN 'nodeinfo'
  WHEN upper(trim(portnum)) = 'ADMIN_APP' THEN 'admin'
  ELSE 'other'
END
""".strip()


def fetch_recent_packet_rows(conn: SqlConnection, limit: int) -> SqlRows:
    return conn.execute(
        "SELECT summary_json, packet_json FROM packets ORDER BY id DESC LIMIT ?",
        (max(1, int(limit)),),
    ).fetchall()


def fetch_packet_search_rows(conn: SqlConnection, limit: int) -> SqlRows:
    clean_limit = int(limit)
    if clean_limit <= 0:
        return conn.execute(
            "SELECT id, created_unix, summary_json, packet_json FROM packets ORDER BY id ASC"
        ).fetchall()
    return conn.execute(
        """
        SELECT id, created_unix, summary_json, packet_json
        FROM (
          SELECT id, created_unix, summary_json, packet_json
          FROM packets
          ORDER BY id DESC
          LIMIT ?
        )
        ORDER BY id ASC
        """,
        (clean_limit,),
    ).fetchall()


def fetch_chat_search_rows(conn: SqlConnection, limit: int) -> SqlRows:
    clean_limit = int(limit)
    file_transfer_like = '%"text":"MF_FILE_V1|%'
    if clean_limit <= 0:
        return conn.execute(
            """
            SELECT id, created_unix, message_json
            FROM chat
            WHERE message_json NOT LIKE ?
            ORDER BY id ASC
            """,
            (file_transfer_like,),
        ).fetchall()
    return conn.execute(
        """
        SELECT id, created_unix, message_json
        FROM (
          SELECT id, created_unix, message_json
          FROM chat
          WHERE message_json NOT LIKE ?
          ORDER BY id DESC
          LIMIT ?
        )
        ORDER BY id ASC
        """,
        (file_transfer_like, clean_limit),
    ).fetchall()


def fetch_environment_metric_packet_rows(
    conn: SqlConnection,
    *,
    cutoff: int,
    limit: int,
) -> SqlRows:
    clean_limit = max(1, min(50000, int(limit)))
    clean_cutoff = max(0, int(cutoff))
    return conn.execute(
        """
        SELECT id, created_unix, summary_json, packet_json
        FROM (
          SELECT id, created_unix, summary_json, packet_json
          FROM packets
          WHERE created_unix >= ?
          ORDER BY id DESC
          LIMIT ?
        )
        ORDER BY id ASC
        """,
        (clean_cutoff, clean_limit),
    ).fetchall()


def fetch_environment_metric_rollup_rows(
    conn: SqlConnection,
    *,
    cutoff: int,
    limit: int,
    metric: str | None = None,
    node_id: str | None = None,
) -> SqlRows:
    clean_limit = max(1, min(300000, int(limit)))
    clean_cutoff = max(0, int(cutoff))
    where_clauses = ["last_seen_unix >= ?"]
    params: list[object] = [clean_cutoff]
    clean_metric = str(metric or "").strip()
    if clean_metric:
        where_clauses.append("metric_key = ?")
        params.append(clean_metric)
    clean_node_id = str(node_id or "").strip()
    if clean_node_id:
        where_clauses.append("node_id = ?")
        params.append(clean_node_id)
    params.append(clean_limit)
    sql = f"""
        SELECT bucket_unix, node_id, node_label, metric_key, metric_label,
               sample_count, value_sum, value_min, value_max, last_value, last_seen_unix
        FROM (
          SELECT bucket_unix, node_id, node_label, metric_key, metric_label,
                 sample_count, value_sum, value_min, value_max, last_value, last_seen_unix
          FROM environment_metrics_1m
          WHERE {' AND '.join(where_clauses)}
          ORDER BY bucket_unix DESC, last_seen_unix DESC
          LIMIT ?
        )
        ORDER BY bucket_unix ASC, node_id ASC, metric_key ASC
        """
    return conn.execute(sql, tuple(params)).fetchall()


def fetch_recent_chat_rows(conn: SqlConnection, limit: int) -> SqlRows:
    return conn.execute(
        """
        SELECT message_json
        FROM chat
        WHERE lower(COALESCE(json_extract(message_json, '$.text'), '')) NOT LIKE ?
          AND lower(COALESCE(json_extract(message_json, '$.text'), '')) NOT LIKE ?
          AND lower(COALESCE(json_extract(message_json, '$.text'), '')) NOT LIKE ?
          AND lower(COALESCE(json_extract(message_json, '$.text'), '')) NOT LIKE ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (
            'mf_file_v1|%',
            'rv1|%',
            'ck1|%',
            'ch1|%',
            max(1, int(limit)),
        ),
    ).fetchall()


def fetch_connection_rows(conn: SqlConnection) -> SqlRows:
    return conn.execute(
        """
        SELECT c.from_id,
               c.to_id,
               c.first_seen_unix,
               c.last_seen_unix,
               c.seen_count,
               c.portnums_json,
               c.last_hops,
               c.hops_sum,
               c.hops_count,
               metrics.snr_sum,
               metrics.snr_count,
               metrics.snr_min,
               metrics.snr_max,
               metrics.rssi_sum,
               metrics.rssi_count,
               metrics.rssi_min,
               metrics.rssi_max
        FROM connections AS c
        LEFT JOIN (
          SELECT from_id,
                 to_id,
                 COALESCE(SUM(snr_sum), 0.0) AS snr_sum,
                 COALESCE(SUM(snr_count), 0) AS snr_count,
                 MIN(snr_min) AS snr_min,
                 MAX(snr_max) AS snr_max,
                 COALESCE(SUM(rssi_sum), 0.0) AS rssi_sum,
                 COALESCE(SUM(rssi_count), 0) AS rssi_count,
                 MIN(rssi_min) AS rssi_min,
                 MAX(rssi_max) AS rssi_max
          FROM link_metrics_1m
          GROUP BY from_id, to_id
        ) AS metrics
          ON metrics.from_id = c.from_id AND metrics.to_id = c.to_id
        ORDER BY c.last_seen_unix DESC
        """
    ).fetchall()


def fetch_node_history_rows(
    conn: SqlConnection,
    *,
    node_id: str,
    cutoff: int,
    limit: int,
) -> tuple[SqlRows, SqlRows, SqlRows, SqlRows]:
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
    clean_node_id = str(node_id or "").strip()
    escaped_node_id = clean_node_id.replace("\\", "\\\\").replace('"', '\\"')
    from_pattern = f'%"from":"{escaped_node_id}"%'
    to_pattern = f'%"to":"{escaped_node_id}"%'
    packet_limit = max(250, min(20000, int(limit) * 4))
    packet_rows = conn.execute(
        """
        SELECT created_unix, summary_json, packet_json
        FROM packets
        WHERE created_unix >= ?
          AND (summary_json LIKE ? OR summary_json LIKE ?)
        ORDER BY id DESC
        LIMIT ?
        """,
        (cutoff, from_pattern, to_pattern, packet_limit),
    ).fetchall()
    packet_type_rows = conn.execute(
        f"""
        SELECT created_unix - (created_unix % 60) AS bucket_unix,
               {_PACKET_TYPE_CASE_SQL} AS packet_type,
               COUNT(*) AS packet_count
        FROM packet_events
        WHERE created_unix >= ?
          AND from_id = ?
        GROUP BY bucket_unix, packet_type
        ORDER BY bucket_unix ASC, packet_type ASC
        """,
        (cutoff, clean_node_id),
    ).fetchall()
    return metric_rows, position_rows, packet_rows, packet_type_rows


def fetch_local_signal_history_rows(
    conn: SqlConnection,
    *,
    cutoff: int,
    limit: int,
) -> SqlRows:
    return conn.execute(
        """
        SELECT bucket_unix,
               COUNT(*) AS packet_count,
               COALESCE(SUM(rx_snr), 0.0) AS snr_sum,
               SUM(CASE WHEN rx_snr IS NOT NULL THEN 1 ELSE 0 END) AS snr_count,
               MIN(rx_snr) AS snr_min,
               MAX(rx_snr) AS snr_max,
               COALESCE(SUM(rx_rssi), 0.0) AS rssi_sum,
               SUM(CASE WHEN rx_rssi IS NOT NULL THEN 1 ELSE 0 END) AS rssi_count,
               MIN(rx_rssi) AS rssi_min,
               MAX(rx_rssi) AS rssi_max,
               COALESCE(SUM(hops), 0.0) AS hops_sum,
               SUM(CASE WHEN hops IS NOT NULL THEN 1 ELSE 0 END) AS hops_count,
               MIN(hops) AS hops_min,
               MAX(hops) AS hops_max,
               MAX(created_unix) AS last_seen_unix
        FROM (
          SELECT (created_unix - (created_unix % 60)) AS bucket_unix,
                 rx_snr,
                 rx_rssi,
                 hops,
                 created_unix
          FROM packet_events
          WHERE created_unix >= ?
            AND (rx_snr IS NOT NULL OR rx_rssi IS NOT NULL)
        )
        GROUP BY bucket_unix
        ORDER BY bucket_unix DESC
        LIMIT ?
        """,
        (cutoff, limit),
    ).fetchall()


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
    cutoff_bucket = _summary_metrics_bucket_unix(int(cutoff))
    return conn.execute(
        """
        SELECT bucket_unix,
               node_count,
               saved_node_count,
               online_node_count,
               nodes_with_position,
               live_packet_count,
               edge_count,
               real_edge_count
        FROM summary_metrics_1m
        WHERE bucket_unix >= ?
        ORDER BY bucket_unix ASC
        LIMIT ?
        """,
        (cutoff_bucket, max(1, int(limit))),
    ).fetchall()


def fetch_summary_packet_type_rows(
    conn: SqlConnection,
    *,
    cutoff: int,
) -> SqlRows:
    cutoff_bucket = _summary_metrics_bucket_unix(int(cutoff))
    bucket_seconds = max(1, int(_summary_metrics_bucket_seconds()))
    return conn.execute(
        f"""
        SELECT created_unix - (created_unix % ?) AS bucket_unix,
               {_PACKET_TYPE_CASE_SQL} AS packet_type,
               COUNT(*) AS packet_count
        FROM packet_events
        WHERE created_unix >= ?
        GROUP BY bucket_unix, packet_type
        ORDER BY bucket_unix ASC, packet_type ASC
        """,
        (bucket_seconds, cutoff_bucket),
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
               last_hops, battery_level, battery_updated_unix,
               last_short_name, last_long_name, names_updated_unix
        FROM node_capabilities
        ORDER BY last_seen_unix DESC
        """
    ).fetchall()
