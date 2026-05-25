from collections.abc import Mapping

from .helpers import format_epoch, to_int, to_jsonable
from .helpers_json import message_to_dict
from .nodes import extract_position, safe_nodes_items
from .state_node_contracts import CollectedNodes


def _as_dict(value: object) -> dict[str, object]:
    """Best-effort conversion to a plain dict without deep-walking large objects."""
    if isinstance(value, dict):
        return value
    if isinstance(value, Mapping):
        return dict(value)
    try:
        converted = message_to_dict(value)
    except Exception:
        converted = None
    return converted if isinstance(converted, dict) else {}


def _optional_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        try:
            return bool(int(value))
        except Exception:
            return None
    if value is None:
        return None
    clean = str(value).strip().lower()
    if clean in {"1", "true", "yes", "y", "on"}:
        return True
    if clean in {"0", "false", "no", "n", "off"}:
        return False
    return None


def collect_nodes(iface: object) -> dict[str, object]:
    return collect_nodes_typed(iface).as_dict()


def collect_nodes_typed(iface: object) -> CollectedNodes:
    rows: list[dict[str, object]] = []
    full_nodes: list[dict[str, object]] = []
    nodes_by_id: dict[str, dict[str, object]] = {}

    for node_num, raw_info in safe_nodes_items(iface):
        if not isinstance(raw_info, dict):
            continue

        info = to_jsonable(raw_info)
        if not isinstance(info, dict):
            continue

        node_num_int = to_int(info.get("num", node_num))
        user = info.get("user", {}) if isinstance(info.get("user"), dict) else {}
        node_id = user.get("id")
        if not node_id and node_num_int is not None:
            node_id = f"!{node_num_int:08x}"

        if not node_id:
            continue

        metrics = info.get("deviceMetrics", {}) if isinstance(info.get("deviceMetrics"), dict) else {}
        position = extract_position(info)
        last_heard_epoch = to_int(info.get("lastHeard")) or 0

        row = {
            "id": str(node_id),
            "num": node_num_int,
            "short_name": user.get("shortName"),
            "long_name": user.get("longName"),
            "hardware_model": user.get("hwModel"),
            "role": user.get("role"),
            "is_licensed": user.get("isLicensed"),
            "last_heard": format_epoch(last_heard_epoch),
            "last_heard_epoch": last_heard_epoch,
            "last_heard_unix": last_heard_epoch,
            "snr": info.get("snr"),
            "rssi": info.get("rssi"),
            "hops_away": info.get("hopsAway"),
            "is_favorite": _optional_bool(
                info.get("isFavorite")
                if info.get("isFavorite") is not None
                else info.get("is_favorite")
            ),
            "battery_level": metrics.get("batteryLevel"),
            "voltage": metrics.get("voltage"),
            "channel_utilization": metrics.get("channelUtilization"),
            "air_util_tx": metrics.get("airUtilTx"),
            "lat": position[0] if position else None,
            "lon": position[1] if position else None,
        }
        rows.append(row)
        nodes_by_id[str(node_id)] = row
        full_nodes.append(
            {
                "id": str(node_id),
                "num": node_num_int,
                "info": info,
            }
        )

    rows.sort(key=lambda item: item.get("last_heard_epoch", 0), reverse=True)
    for row in rows:
        row.pop("last_heard_epoch", None)

    full_nodes.sort(key=lambda item: item.get("num") or 0)
    nodes_with_position = sum(
        1 for node in rows if node.get("lat") is not None and node.get("lon") is not None
    )

    return CollectedNodes(
        rows=rows,
        full=full_nodes,
        by_id=nodes_by_id,
        with_position_count=nodes_with_position,
    )


def collect_nodes_rows_typed(iface: object) -> CollectedNodes:
    """Collect node rows without building the full raw node payload list.

    The "full" nodes payload can be very large (deeply nested dicts), and even
    if the API later drops it for lite polling, building it still costs CPU.
    This collector focuses on the fields the main UI needs.
    """
    rows: list[dict[str, object]] = []
    nodes_by_id: dict[str, dict[str, object]] = {}

    for node_num, raw_info in safe_nodes_items(iface):
        info = _as_dict(raw_info)
        if not info:
            continue

        node_num_int = to_int(info.get("num", node_num))

        user_raw = info.get("user")
        user = _as_dict(user_raw) if user_raw is not None else {}

        node_id = user.get("id")
        if not node_id and node_num_int is not None:
            node_id = f"!{node_num_int:08x}"
        if not node_id:
            continue

        metrics_raw = info.get("deviceMetrics")
        metrics = _as_dict(metrics_raw) if metrics_raw is not None else {}

        # extract_position expects a dict (and internally reads info["position"]).
        # Our info dict may contain a protobuf message under "position"; coerce
        # just that leaf rather than deep-walking the whole node record.
        pos_raw = info.get("position")
        if pos_raw is not None and not isinstance(pos_raw, dict):
            pos_dict = _as_dict(pos_raw)
            if pos_dict:
                info = dict(info)
                info["position"] = pos_dict
        position = extract_position(info)

        last_heard_epoch = to_int(info.get("lastHeard")) or 0

        row = {
            "id": str(node_id),
            "num": node_num_int,
            "short_name": user.get("shortName"),
            "long_name": user.get("longName"),
            "hardware_model": user.get("hwModel"),
            "role": user.get("role"),
            "is_licensed": user.get("isLicensed"),
            "last_heard": format_epoch(last_heard_epoch),
            "last_heard_epoch": last_heard_epoch,
            "last_heard_unix": last_heard_epoch,
            "snr": to_jsonable(info.get("snr")),
            "rssi": to_jsonable(info.get("rssi")),
            "hops_away": to_jsonable(info.get("hopsAway")),
            "is_favorite": _optional_bool(
                to_jsonable(info.get("isFavorite"))
                if info.get("isFavorite") is not None
                else to_jsonable(info.get("is_favorite"))
            ),
            "battery_level": metrics.get("batteryLevel"),
            "voltage": metrics.get("voltage"),
            "channel_utilization": metrics.get("channelUtilization"),
            "air_util_tx": metrics.get("airUtilTx"),
            "lat": position[0] if position else None,
            "lon": position[1] if position else None,
        }
        rows.append(row)
        nodes_by_id[str(node_id)] = row

    rows.sort(key=lambda item: item.get("last_heard_epoch", 0), reverse=True)
    for row in rows:
        row.pop("last_heard_epoch", None)

    nodes_with_position = sum(
        1 for node in rows if node.get("lat") is not None and node.get("lon") is not None
    )
    return CollectedNodes(
        rows=rows,
        full=[],
        by_id=nodes_by_id,
        with_position_count=nodes_with_position,
    )
