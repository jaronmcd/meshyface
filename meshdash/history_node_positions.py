from collections.abc import Iterable
from typing import Optional

from .helpers import format_epoch as _format_epoch
from .helpers import to_float as _to_float
from .helpers import to_int as _to_int


def build_position_history_points(
    position_rows: Iterable[tuple[object, object, object, object, object]],
) -> dict[str, object]:
    positions: list[dict[str, object]] = []
    trail_start: Optional[int] = None
    trail_end: Optional[int] = None

    for created_unix, lat, lon, altitude, sats_in_view in reversed(list(position_rows)):
        point_unix = _to_int(created_unix)
        lat_f = _to_float(lat)
        lon_f = _to_float(lon)
        if point_unix is None or lat_f is None or lon_f is None:
            continue
        if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
            continue
        if lat_f == 0.0 and lon_f == 0.0:
            continue
        trail_start = point_unix if trail_start is None else min(trail_start, point_unix)
        trail_end = point_unix if trail_end is None else max(trail_end, point_unix)
        positions.append(
            {
                "time_unix": point_unix,
                "time": _format_epoch(point_unix),
                "lat": lat_f,
                "lon": lon_f,
                "altitude": _to_float(altitude),
                "sats_in_view": _to_int(sats_in_view),
            }
        )

    return {
        "positions": positions,
        "trail_start": trail_start,
        "trail_end": trail_end,
    }
