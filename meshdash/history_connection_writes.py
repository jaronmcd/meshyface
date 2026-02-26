import time
from typing import Callable, Optional

from .history_connections import (
    build_connection_insert_values as _build_connection_insert_values,
    merge_connection_row as _merge_connection_row,
    normalize_connection_event_input as _normalize_connection_event_input,
)
from .sql_contracts import SqlConnection


def save_connection_event(
    conn: SqlConnection,
    *,
    from_id: str,
    to_id: str,
    rx_time: Optional[int],
    portnum: Optional[str],
    hops: Optional[int],
    now_unix_fn: Callable[[], float] = time.time,
) -> None:
    event_unix, clean_port, clean_hops = _normalize_connection_event_input(
        rx_time=rx_time,
        portnum=portnum,
        hops=hops,
        now_unix_fn=now_unix_fn,
    )

    row = conn.execute(
        """
        SELECT first_seen_unix, last_seen_unix, seen_count, portnums_json, last_hops, hops_sum, hops_count
        FROM connections
        WHERE from_id = ? AND to_id = ?
        """,
        (from_id, to_id),
    ).fetchone()

    if row is None:
        conn.execute(
            """
            INSERT INTO connections(
              from_id, to_id, first_seen_unix, last_seen_unix, seen_count,
              portnums_json, last_hops, hops_sum, hops_count
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _build_connection_insert_values(
                from_id=from_id,
                to_id=to_id,
                event_unix=event_unix,
                clean_port=clean_port,
                clean_hops=clean_hops,
            ),
        )
        return

    merged = _merge_connection_row(
        row=row,
        event_unix=event_unix,
        clean_port=clean_port,
        clean_hops=clean_hops,
    )
    conn.execute(
        """
        UPDATE connections
        SET first_seen_unix = ?, last_seen_unix = ?, seen_count = ?,
            portnums_json = ?, last_hops = ?, hops_sum = ?, hops_count = ?
        WHERE from_id = ? AND to_id = ?
        """,
        (
            merged["first_seen_unix"],
            merged["last_seen_unix"],
            merged["seen_count"],
            merged["portnums_json"],
            merged["last_hops"],
            merged["hops_sum"],
            merged["hops_count"],
            from_id,
            to_id,
        ),
    )
