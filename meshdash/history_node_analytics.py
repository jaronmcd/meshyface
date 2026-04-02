import time
from collections.abc import Iterable
from typing import Optional

from .helpers import format_epoch as _format_epoch
from .helpers import safe_json_loads as _safe_json_loads
from .helpers import to_int as _to_int
from .history_time import clamp_future_unix as _clamp_future_unix
from .history_node_metrics import (
    build_metric_history_points as _build_metric_history_points_helper,
)
from .history_node_names import (
    build_name_history_points as _build_name_history_points_helper,
)
from .history_node_positions import (
    build_position_history_points as _build_position_history_points_helper,
)


def _extract_packet_time_unix(
    created_unix: object,
    summary_json: object,
    packet_json: object,
    *,
    now_unix: int,
) -> int | None:
    summary = _safe_json_loads(summary_json, {})
    packet = _safe_json_loads(packet_json, {})
    decoded = packet.get("decoded") if isinstance(packet, dict) else {}
    if not isinstance(decoded, dict):
        decoded = {}
    for candidate in (
        summary.get("rx_time_unix") if isinstance(summary, dict) else None,
        summary.get("rxTime") if isinstance(summary, dict) else None,
        packet.get("rxTime") if isinstance(packet, dict) else None,
        packet.get("rx_time_unix") if isinstance(packet, dict) else None,
        decoded.get("rx_time_unix"),
        created_unix,
    ):
        ts = _to_int(candidate)
        if ts is not None and ts > 0:
            clamped = _clamp_future_unix(
                ts,
                now_unix=now_unix,
                fallback_unix=created_unix,
                default_to_now=False,
            )
            if clamped > 0:
                return int(clamped)
            continue
    return None


def _collect_packet_timestamps(
    packet_rows: Iterable[tuple[object, ...]],
) -> list[int]:
    timestamps: set[int] = set()
    now_unix = int(time.time())
    for row in packet_rows:
        created_unix = row[0] if len(row) > 0 else None
        summary_json = row[1] if len(row) > 1 else None
        packet_json = row[2] if len(row) > 2 else None
        packet_time = _extract_packet_time_unix(
            created_unix,
            summary_json,
            packet_json,
            now_unix=now_unix,
        )
        if packet_time is None or packet_time <= 0:
            continue
        timestamps.add(packet_time)
    return sorted(timestamps)


def build_node_history_payload(
    *,
    node_id: str,
    window_hours: int,
    metric_rows: Iterable[tuple[object, ...]],
    position_rows: Iterable[tuple[object, ...]],
    packet_rows: Iterable[tuple[object, ...]],
) -> dict[str, object]:
    clean_node_id = str(node_id or "").strip()
    hours = max(1, int(window_hours))
    if not clean_node_id:
        return {
            "node_id": "",
            "window_hours": hours,
            "points": [],
            "positions": [],
            "name_history": [],
            "packet_timestamps": [],
            "summary": {},
        }

    points: list[dict[str, object]] = []
    positions: list[dict[str, object]] = []
    total_packets = 0
    snr_min_all: Optional[float] = None
    snr_max_all: Optional[float] = None
    rssi_min_all: Optional[float] = None
    rssi_max_all: Optional[float] = None
    first_bucket: Optional[int] = None
    last_bucket: Optional[int] = None
    last_seen: Optional[int] = None
    trail_start: Optional[int] = None
    trail_end: Optional[int] = None

    metric_data = _build_metric_history_points_helper(metric_rows)
    points = metric_data["points"]
    total_packets = metric_data["total_packets"]
    first_bucket = metric_data["first_bucket"]
    last_bucket = metric_data["last_bucket"]
    last_seen = metric_data["last_seen"]
    snr_min_all = metric_data["snr_min"]
    snr_max_all = metric_data["snr_max"]
    rssi_min_all = metric_data["rssi_min"]
    rssi_max_all = metric_data["rssi_max"]

    position_data = _build_position_history_points_helper(position_rows)
    positions = position_data["positions"]
    trail_start = position_data["trail_start"]
    trail_end = position_data["trail_end"]
    packet_timestamps = _collect_packet_timestamps(packet_rows)
    name_history = _build_name_history_points_helper(
        node_id=clean_node_id,
        packet_rows=packet_rows,
    )

    return {
        "node_id": clean_node_id,
        "window_hours": hours,
        "points": points,
        "positions": positions,
        "name_history": name_history,
        "packet_timestamps": packet_timestamps,
        "summary": {
            "total_packets": total_packets,
            "points": len(points),
            "first_bucket": _format_epoch(first_bucket),
            "last_bucket": _format_epoch(last_bucket),
            "last_seen": _format_epoch(last_seen),
            "snr_min": snr_min_all,
            "snr_max": snr_max_all,
            "rssi_min": rssi_min_all,
            "rssi_max": rssi_max_all,
            "trail_points": len(positions),
            "trail_start": _format_epoch(trail_start),
            "trail_end": _format_epoch(trail_end),
        },
    }
