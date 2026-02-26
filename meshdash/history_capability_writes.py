from typing import Optional

from .history_capability_upsert import (
    build_node_capability_insert_values as _build_node_capability_insert_values,
    merge_node_capability_row as _merge_node_capability_row,
    normalize_node_capability_inputs as _normalize_node_capability_inputs,
)
from .sql_contracts import SqlConnection


def upsert_node_capability(
    conn: SqlConnection,
    *,
    node_id: str,
    event_unix: int,
    has_position: bool,
    last_hops: Optional[int],
    battery_level: Optional[int],
) -> None:
    clean_hops, clean_battery = _normalize_node_capability_inputs(
        last_hops=last_hops,
        battery_level=battery_level,
    )

    row = conn.execute(
        """
        SELECT last_seen_unix, has_position, last_position_unix,
               last_hops, battery_level, battery_updated_unix
        FROM node_capabilities
        WHERE node_id = ?
        """,
        (node_id,),
    ).fetchone()

    if row is None:
        conn.execute(
            """
            INSERT INTO node_capabilities(
              node_id, last_seen_unix, has_position, last_position_unix,
              last_hops, battery_level, battery_updated_unix
            ) VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            _build_node_capability_insert_values(
                node_id=node_id,
                event_unix=event_unix,
                has_position=has_position,
                clean_hops=clean_hops,
                clean_battery=clean_battery,
            ),
        )
        return

    merged = _merge_node_capability_row(
        row=row,
        event_unix=event_unix,
        has_position=has_position,
        clean_hops=clean_hops,
        clean_battery=clean_battery,
    )

    conn.execute(
        """
        UPDATE node_capabilities
        SET last_seen_unix = ?,
            has_position = ?,
            last_position_unix = ?,
            last_hops = ?,
            battery_level = ?,
            battery_updated_unix = ?
        WHERE node_id = ?
        """,
        (
            merged["last_seen_unix"],
            1 if merged["has_position"] else 0,
            merged["last_position_unix"],
            merged["last_hops"],
            merged["battery_level"],
            merged["battery_updated_unix"],
            node_id,
        ),
    )
