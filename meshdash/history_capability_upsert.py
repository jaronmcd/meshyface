from typing import Optional

from .helpers import to_int as _to_int


def normalize_node_capability_inputs(
    *,
    last_hops: Optional[int],
    battery_level: Optional[int],
) -> tuple[Optional[int], Optional[int]]:
    clean_hops = last_hops if isinstance(last_hops, int) and last_hops >= 0 else None
    clean_battery = (
        battery_level
        if isinstance(battery_level, int) and 0 <= battery_level <= 100
        else None
    )
    return clean_hops, clean_battery


def build_node_capability_insert_values(
    *,
    node_id: str,
    event_unix: int,
    has_position: bool,
    clean_hops: Optional[int],
    clean_battery: Optional[int],
) -> tuple[object, ...]:
    return (
        node_id,
        event_unix,
        1 if has_position else 0,
        event_unix if has_position else None,
        clean_hops,
        clean_battery,
        event_unix if clean_battery is not None else None,
    )


def merge_node_capability_row(
    *,
    row: tuple[object, ...],
    event_unix: int,
    has_position: bool,
    clean_hops: Optional[int],
    clean_battery: Optional[int],
) -> dict[str, object]:
    (
        last_seen_unix,
        row_has_position,
        row_last_position_unix,
        row_last_hops,
        row_battery_level,
        row_battery_updated_unix,
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

    return {
        "last_seen_unix": merged_last_seen,
        "has_position": merged_has_position,
        "last_position_unix": merged_last_position_unix,
        "last_hops": merged_last_hops,
        "battery_level": merged_battery_level,
        "battery_updated_unix": merged_battery_updated_unix,
    }
