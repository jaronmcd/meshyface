import json
import time
from typing import Callable

from .helpers import to_float as _to_float, to_int as _to_int
from .history_rollups import clean_node_id as _clean_node_id


def normalize_packet_event_summary(
    summary: dict[str, object],
    *,
    now_unix_fn: Callable[[], float] = time.time,
) -> dict[str, object]:
    event_unix = _to_int(summary.get("rx_time_unix"))
    if event_unix is None or event_unix <= 0:
        event_unix = int(now_unix_fn())

    portnum_raw = summary.get("portnum")
    channel_raw = summary.get("channel")
    priority_raw = summary.get("priority")

    return {
        "event_unix": event_unix,
        "from_id": _clean_node_id(summary.get("from")),
        "to_id": _clean_node_id(summary.get("to")),
        "portnum": str(portnum_raw) if portnum_raw is not None else None,
        "rx_snr": _to_float(summary.get("rx_snr")),
        "rx_rssi": _to_float(summary.get("rx_rssi")),
        "hops": _to_int(summary.get("hops")),
        "hop_start": _to_int(summary.get("hop_start")),
        "hop_limit": _to_int(summary.get("hop_limit")),
        "channel": str(channel_raw) if channel_raw is not None else None,
        "want_ack": 1 if summary.get("want_ack") else 0,
        "priority": str(priority_raw) if priority_raw is not None else None,
        "position_data": summary.get("position"),
        "battery_level": _to_int(summary.get("battery_level")),
        "summary_json": json.dumps(summary, separators=(",", ":")),
    }


def build_packet_event_insert_values(normalized: dict[str, object]) -> tuple[object, ...]:
    return (
        normalized["event_unix"],
        normalized["from_id"],
        normalized["to_id"],
        normalized["portnum"],
        normalized["rx_snr"],
        normalized["rx_rssi"],
        normalized["hops"],
        normalized["hop_start"],
        normalized["hop_limit"],
        normalized["channel"],
        normalized["want_ack"],
        normalized["priority"],
        normalized["summary_json"],
    )
