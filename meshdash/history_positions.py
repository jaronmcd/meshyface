from .helpers import (
    extract_position_fields as _extract_position_fields,
    to_float as _to_float,
    to_int as _to_int,
)
from .sql_contracts import SqlConnection


def insert_node_position_if_changed(
    conn: SqlConnection,
    *,
    node_id: str,
    event_unix: int,
    position_data: object,
) -> None:
    coords = _extract_position_fields(position_data)
    if coords is None:
        return

    altitude = None
    sats = None
    if isinstance(position_data, dict):
        altitude = _to_float(position_data.get("altitude"))
        if altitude is None:
            altitude = _to_float(position_data.get("altitude_m"))
        if altitude is None:
            altitude = _to_float(position_data.get("altitudeM"))

        sats = _to_int(position_data.get("sats_in_view"))
        if sats is None:
            sats = _to_int(position_data.get("satsInView"))
        if sats is None:
            sats = _to_int(position_data.get("satellites"))

    latest = conn.execute(
        """
        SELECT created_unix, lat, lon
        FROM node_positions
        WHERE node_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (node_id,),
    ).fetchone()
    if latest is not None:
        latest_unix, latest_lat, latest_lon = latest
        latest_unix_i = _to_int(latest_unix)
        latest_lat_f = _to_float(latest_lat)
        latest_lon_f = _to_float(latest_lon)
        if (
            latest_unix_i is not None
            and latest_lat_f is not None
            and latest_lon_f is not None
            and abs(coords[0] - latest_lat_f) < 1e-7
            and abs(coords[1] - latest_lon_f) < 1e-7
            and abs(event_unix - latest_unix_i) < 30
        ):
            return

    conn.execute(
        """
        INSERT INTO node_positions(created_unix, node_id, lat, lon, altitude, sats_in_view)
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        (
            event_unix,
            node_id,
            coords[0],
            coords[1],
            altitude,
            sats if sats is not None and sats >= 0 else None,
        ),
    )
