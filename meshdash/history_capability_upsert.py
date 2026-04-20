from typing import Optional

from .helpers import to_int as _to_int
from .helpers_node_names import clean_node_name as _clean_node_name


def normalize_node_capability_inputs(
    *,
    last_hops: Optional[int],
    battery_level: Optional[int],
    last_short_name: object = None,
    last_long_name: object = None,
) -> tuple[Optional[int], Optional[int], str, str]:
    clean_hops = last_hops if isinstance(last_hops, int) and last_hops >= 0 else None
    clean_battery = (
        battery_level
        if isinstance(battery_level, int) and 0 <= battery_level <= 100
        else None
    )
    clean_short_name = _clean_node_name(last_short_name)
    clean_long_name = _clean_node_name(last_long_name)
    return clean_hops, clean_battery, clean_short_name, clean_long_name


def build_node_capability_insert_values(
    *,
    node_id: str,
    event_unix: int,
    has_position: bool,
    clean_hops: Optional[int],
    clean_battery: Optional[int],
    clean_short_name: str,
    clean_long_name: str,
) -> tuple[object, ...]:
    return (
        node_id,
        event_unix,
        1 if has_position else 0,
        event_unix if has_position else None,
        clean_hops,
        clean_battery,
        event_unix if clean_battery is not None else None,
        clean_short_name or None,
        clean_long_name or None,
        event_unix if (clean_short_name or clean_long_name) else None,
    )


def merge_node_capability_row(
    *,
    row: tuple[object, ...],
    event_unix: int,
    has_position: bool,
    clean_hops: Optional[int],
    clean_battery: Optional[int],
    clean_short_name: str,
    clean_long_name: str,
) -> dict[str, object]:
    (
        last_seen_unix,
        row_has_position,
        row_last_position_unix,
        row_last_hops,
        row_battery_level,
        row_battery_updated_unix,
        row_last_short_name,
        row_last_long_name,
        row_names_updated_unix,
    ) = row
    merged_last_seen = max(_to_int(last_seen_unix) or event_unix, event_unix)
    merged_has_position = bool(_to_int(row_has_position)) or has_position

    merged_last_position_unix = _to_int(row_last_position_unix)
    if has_position:
        merged_last_position_unix = event_unix

    merged_last_hops = clean_hops if clean_hops is not None else _to_int(row_last_hops)

    merged_battery_level = _to_int(row_battery_level)
    merged_battery_updated_unix = _to_int(row_battery_updated_unix)
    if clean_battery is not None:
        merged_battery_level = clean_battery
        merged_battery_updated_unix = event_unix

    merged_short_name = _clean_node_name(row_last_short_name)
    merged_long_name = _clean_node_name(row_last_long_name)
    merged_names_updated_unix = _to_int(row_names_updated_unix)
    if clean_short_name or clean_long_name:
        if (merged_names_updated_unix or 0) <= int(event_unix) or not (merged_short_name or merged_long_name):
            merged_short_name = clean_short_name or merged_short_name
            merged_long_name = clean_long_name or merged_long_name
            merged_names_updated_unix = int(event_unix)

    return {
        "last_seen_unix": merged_last_seen,
        "has_position": merged_has_position,
        "last_position_unix": merged_last_position_unix,
        "last_hops": merged_last_hops,
        "battery_level": merged_battery_level,
        "battery_updated_unix": merged_battery_updated_unix,
        "last_short_name": merged_short_name or None,
        "last_long_name": merged_long_name or None,
        "names_updated_unix": merged_names_updated_unix,
    }
