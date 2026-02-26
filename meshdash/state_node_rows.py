from .helpers import format_epoch, to_int, to_jsonable
from .nodes import extract_position, safe_nodes_items
from .state_node_contracts import CollectedNodes


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
            "hops_away": info.get("hopsAway"),
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
