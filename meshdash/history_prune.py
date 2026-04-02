from .sql_contracts import SqlConnection


def prune_history_tables(
    conn: SqlConnection,
    *,
    now_unix: int,
    retention_seconds: int,
    event_retention_seconds: int,
    rollup_retention_seconds: int,
    max_rows: int,
    event_max_rows: int,
) -> None:
    if retention_seconds > 0:
        cutoff = int(now_unix) - int(retention_seconds)
        conn.execute("DELETE FROM packets WHERE created_unix < ?", (cutoff,))
        conn.execute("DELETE FROM chat WHERE created_unix < ?", (cutoff,))
        conn.execute("DELETE FROM connections WHERE last_seen_unix < ?", (cutoff,))
    if event_retention_seconds > 0:
        event_cutoff = int(now_unix) - int(event_retention_seconds)
        conn.execute("DELETE FROM packet_events WHERE created_unix < ?", (event_cutoff,))
        conn.execute("DELETE FROM node_positions WHERE created_unix < ?", (event_cutoff,))
        conn.execute("DELETE FROM node_capabilities WHERE last_seen_unix < ?", (event_cutoff,))
    if rollup_retention_seconds > 0:
        rollup_cutoff = int(now_unix) - int(rollup_retention_seconds)
        conn.execute("DELETE FROM node_metrics_1m WHERE last_seen_unix < ?", (rollup_cutoff,))
        conn.execute("DELETE FROM link_metrics_1m WHERE last_seen_unix < ?", (rollup_cutoff,))
        conn.execute("DELETE FROM summary_metrics_1m WHERE last_seen_unix < ?", (rollup_cutoff,))
        conn.execute("DELETE FROM environment_metrics_1m WHERE last_seen_unix < ?", (rollup_cutoff,))
        # node_hour_seen is derived from node_metrics_1m; prune it with the
        # same retention window.
        hour_cutoff = int(rollup_cutoff) - (int(rollup_cutoff) % 3600)
        conn.execute("DELETE FROM node_hour_seen WHERE hour_bucket < ?", (hour_cutoff,))

    if max_rows > 0:
        conn.execute(
            """
            DELETE FROM packets
            WHERE id <= (SELECT COALESCE(MAX(id), 0) - ? FROM packets)
            """,
            (int(max_rows),),
        )
        conn.execute(
            """
            DELETE FROM chat
            WHERE id <= (SELECT COALESCE(MAX(id), 0) - ? FROM chat)
            """,
            (int(max_rows),),
        )
        conn.execute(
            """
            DELETE FROM connections
            WHERE id NOT IN (
              SELECT id FROM connections
              ORDER BY last_seen_unix DESC
              LIMIT ?
            )
            """,
            (int(max_rows),),
        )
    if event_max_rows > 0:
        conn.execute(
            """
            DELETE FROM packet_events
            WHERE id <= (SELECT COALESCE(MAX(id), 0) - ? FROM packet_events)
            """,
            (int(event_max_rows),),
        )
        conn.execute(
            """
            DELETE FROM node_positions
            WHERE id <= (SELECT COALESCE(MAX(id), 0) - ? FROM node_positions)
            """,
            (int(event_max_rows),),
        )
