from collections.abc import Iterable

from .helpers import format_epoch as _format_epoch, to_int as _to_int


SavedCountsRow = tuple[object, object, object, object]
CapabilityRow = tuple[object, object, object, object, object, object, object, object, object, object]


def decode_node_saved_counts_rows(rows: Iterable[SavedCountsRow]) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for node_id, saved_packets, saved_points, saved_last_seen_unix in rows:
        clean_node_id = str(node_id or "").strip()
        if not clean_node_id:
            continue
        out[clean_node_id] = {
            "saved_packets": int(saved_packets or 0),
            "saved_points": int(saved_points or 0),
            "saved_last_seen": _format_epoch(saved_last_seen_unix),
        }
    return out


def decode_node_capabilities_rows(rows: Iterable[CapabilityRow]) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for (
        node_id,
        last_seen_unix,
        has_position,
        last_position_unix,
        last_hops,
        battery_level,
        battery_updated_unix,
        last_short_name,
        last_long_name,
        names_updated_unix,
    ) in rows:
        clean_node_id = str(node_id or "").strip()
        if not clean_node_id:
            continue
        out[clean_node_id] = {
            "last_seen_unix": _to_int(last_seen_unix),
            "last_seen": _format_epoch(last_seen_unix),
            "has_position": bool(_to_int(has_position)),
            "last_position_unix": _to_int(last_position_unix),
            "last_position_time": _format_epoch(last_position_unix),
            "last_hops": _to_int(last_hops),
            "battery_level": _to_int(battery_level),
            "battery_updated_unix": _to_int(battery_updated_unix),
            "battery_updated_time": _format_epoch(battery_updated_unix),
            "last_short_name": str(last_short_name or "").strip() or None,
            "last_long_name": str(last_long_name or "").strip() or None,
            "names_updated_unix": _to_int(names_updated_unix),
        }
    return out
