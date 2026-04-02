from collections.abc import Iterable
from typing import Optional

from .helpers import format_epoch as _format_epoch
from .helpers import to_int as _to_int


def build_summary_metrics_payload(
    *,
    window_hours: int,
    rows: Iterable[tuple[object, ...]],
) -> dict[str, object]:
    hours = max(1, int(window_hours))
    points: list[dict[str, object]] = []
    first: Optional[dict[str, object]] = None
    latest: Optional[dict[str, object]] = None

    for row in rows:
        if isinstance(row, tuple):
            raw_row = row
        elif isinstance(row, list):
            raw_row = tuple(row)
        else:
            try:
                raw_row = tuple(row)
            except Exception:
                continue
        if len(raw_row) >= 7:
            (
                raw_bucket,
                raw_nodes,
                raw_saved_nodes,
                raw_online_nodes,
                raw_pos_nodes,
                raw_live_packets,
                raw_links,
            ) = raw_row[:7]
        elif len(raw_row) >= 6:
            (
                raw_bucket,
                raw_nodes,
                raw_saved_nodes,
                raw_pos_nodes,
                raw_live_packets,
                raw_links,
            ) = raw_row[:6]
            raw_online_nodes = None
        elif len(raw_row) >= 5:
            (
                raw_bucket,
                raw_nodes,
                raw_pos_nodes,
                raw_live_packets,
                raw_links,
            ) = raw_row[:5]
            raw_saved_nodes = None
            raw_online_nodes = None
        else:
            continue
        bucket = _to_int(raw_bucket)
        if bucket is None:
            continue
        point = {
            "bucket_unix": bucket,
            "bucket_time": _format_epoch(bucket),
            "node_count": max(0, _to_int(raw_nodes) or 0),
            "saved_node_count": max(0, _to_int(raw_saved_nodes) or 0),
            "online_node_count": max(0, _to_int(raw_online_nodes) or 0),
            "nodes_with_position": max(0, _to_int(raw_pos_nodes) or 0),
            "live_packet_count": max(0, _to_int(raw_live_packets) or 0),
            "real_edge_count": max(0, _to_int(raw_links) or 0),
        }
        points.append(point)
        if first is None:
            first = point
        latest = point

    if first is None or latest is None:
        summary: dict[str, object] = {
            "samples": 0,
            "window_start": None,
            "window_end": None,
            "latest": {},
            "delta": {},
        }
    else:
        summary = {
            "samples": len(points),
            "window_start": first.get("bucket_time"),
            "window_end": latest.get("bucket_time"),
            "latest": {
                "node_count": latest.get("node_count"),
                "saved_node_count": latest.get("saved_node_count"),
                "online_node_count": latest.get("online_node_count"),
                "nodes_with_position": latest.get("nodes_with_position"),
                "live_packet_count": latest.get("live_packet_count"),
                "real_edge_count": latest.get("real_edge_count"),
            },
            "delta": {
                "node_count": int(latest.get("node_count") or 0) - int(first.get("node_count") or 0),
                "saved_node_count": int(latest.get("saved_node_count") or 0) - int(first.get("saved_node_count") or 0),
                "online_node_count": int(latest.get("online_node_count") or 0) - int(first.get("online_node_count") or 0),
                "nodes_with_position": int(latest.get("nodes_with_position") or 0) - int(first.get("nodes_with_position") or 0),
                "live_packet_count": int(latest.get("live_packet_count") or 0) - int(first.get("live_packet_count") or 0),
                "real_edge_count": int(latest.get("real_edge_count") or 0) - int(first.get("real_edge_count") or 0),
            },
        }

    return {
        "window_hours": hours,
        "points": points,
        "summary": summary,
    }
