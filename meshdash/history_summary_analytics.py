from collections.abc import Iterable
from math import ceil
from typing import Optional

from .helpers import format_epoch as _format_epoch
from .helpers import to_int as _to_int

_PACKET_TYPE_ORDER = (
    "all",
    "chat",
    "telemetry",
    "position",
    "routing",
    "storeforward",
    "nodeinfo",
    "admin",
    "encrypted",
    "other",
)


def _empty_packet_series_payload() -> dict[str, object]:
    return {
        "available": True,
        "order": list(_PACKET_TYPE_ORDER),
        "series": {key: [] for key in _PACKET_TYPE_ORDER},
    }


# (bucket, node_count, saved_node_count, online_node_count, nodes_with_position,
#  live_packet_count, edge_count, real_edge_count)
_SummaryValues = tuple[int, int, int, int, int, int, int, int]


def _row_tuple(row: object) -> Optional[tuple[object, ...]]:
    if isinstance(row, tuple):
        return row
    if isinstance(row, list):
        return tuple(row)
    try:
        return tuple(row)
    except Exception:
        return None


def _parse_packet_type_counts(packet_type_rows: Iterable[tuple[object, ...]]) -> dict[int, dict[str, int]]:
    packet_counts_by_bucket: dict[int, dict[str, int]] = {}
    for raw_packet_row in packet_type_rows:
        raw_row = _row_tuple(raw_packet_row)
        if raw_row is None or len(raw_row) < 3:
            continue
        bucket = _to_int(raw_row[0])
        packet_type = str(raw_row[1] or "").strip().lower()
        packet_count = max(0, _to_int(raw_row[2]) or 0)
        if bucket is None or bucket <= 0 or packet_count <= 0:
            continue
        clean_type = packet_type if packet_type in _PACKET_TYPE_ORDER else "other"
        bucket_counts = packet_counts_by_bucket.setdefault(
            bucket,
            {key: 0 for key in _PACKET_TYPE_ORDER},
        )
        bucket_counts[clean_type] = int(bucket_counts.get(clean_type, 0)) + packet_count
        bucket_counts["all"] = int(bucket_counts.get("all", 0)) + packet_count
    return packet_counts_by_bucket


def _parse_summary_values(rows: Iterable[tuple[object, ...]]) -> list[_SummaryValues]:
    values: list[_SummaryValues] = []
    for row in rows:
        raw_row = _row_tuple(row)
        if raw_row is None:
            continue
        if len(raw_row) >= 8:
            (
                raw_bucket,
                raw_nodes,
                raw_saved_nodes,
                raw_online_nodes,
                raw_pos_nodes,
                raw_live_packets,
                raw_edge_count,
                raw_links,
            ) = raw_row[:8]
        elif len(raw_row) >= 7:
            (
                raw_bucket,
                raw_nodes,
                raw_saved_nodes,
                raw_online_nodes,
                raw_pos_nodes,
                raw_live_packets,
                raw_links,
            ) = raw_row[:7]
            raw_edge_count = raw_links
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
            raw_edge_count = raw_links
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
            raw_edge_count = raw_links
        else:
            continue
        bucket = _to_int(raw_bucket)
        if bucket is None:
            continue
        values.append(
            (
                bucket,
                max(0, _to_int(raw_nodes) or 0),
                max(0, _to_int(raw_saved_nodes) or 0),
                max(0, _to_int(raw_online_nodes) or 0),
                max(0, _to_int(raw_pos_nodes) or 0),
                max(0, _to_int(raw_live_packets) or 0),
                max(0, _to_int(raw_edge_count) or 0),
                max(0, _to_int(raw_links) or 0),
            )
        )
    return values


def _summary_point(values: _SummaryValues, bucket_unix: Optional[int] = None) -> dict[str, object]:
    bucket = values[0] if bucket_unix is None else bucket_unix
    return {
        "bucket_unix": bucket,
        "bucket_time": _format_epoch(bucket),
        "node_count": values[1],
        "saved_node_count": values[2],
        "online_node_count": values[3],
        "nodes_with_position": values[4],
        "live_packet_count": values[5],
        "edge_count": values[6],
        "real_edge_count": values[7],
    }


_SUMMARY_VALUE_KEYS = (
    "node_count",
    "saved_node_count",
    "online_node_count",
    "nodes_with_position",
    "live_packet_count",
    "edge_count",
    "real_edge_count",
)


def _summary_block(values: list[_SummaryValues]) -> dict[str, object]:
    if not values:
        return {
            "samples": 0,
            "window_start": None,
            "window_end": None,
            "latest": {},
            "delta": {},
        }
    first = values[0]
    latest = values[-1]
    return {
        "samples": len(values),
        "window_start": _format_epoch(first[0]),
        "window_end": _format_epoch(latest[0]),
        "latest": {key: latest[index + 1] for index, key in enumerate(_SUMMARY_VALUE_KEYS)},
        "delta": {key: latest[index + 1] - first[index + 1] for index, key in enumerate(_SUMMARY_VALUE_KEYS)},
    }


def _packet_series_payload(packet_counts_by_bucket: dict[int, dict[str, int]]) -> dict[str, object]:
    if not packet_counts_by_bucket:
        return _empty_packet_series_payload()
    return {
        "available": True,
        "order": list(_PACKET_TYPE_ORDER),
        "series": {
            key: [
                {
                    "bucket_unix": bucket,
                    "packet_count": int(bucket_counts.get(key, 0)),
                }
                for bucket, bucket_counts in sorted(packet_counts_by_bucket.items())
                if int(bucket_counts.get(key, 0)) > 0
            ]
            for key in _PACKET_TYPE_ORDER
        },
    }


def build_summary_metrics_payload(
    *,
    window_hours: int,
    rows: Iterable[tuple[object, ...]],
    packet_type_rows: Iterable[tuple[object, ...]],
    bucket_seconds: int,
) -> dict[str, object]:
    packet_counts_by_bucket = _parse_packet_type_counts(packet_type_rows)
    values = _parse_summary_values(rows)
    return {
        "window_hours": max(1, int(window_hours)),
        "bucket_seconds": max(1, int(bucket_seconds)),
        "points": [_summary_point(point_values) for point_values in values],
        "packet_series": _packet_series_payload(packet_counts_by_bucket),
        "summary": _summary_block(values),
    }


def aggregate_summary_bucket(bucket_unix: int, first_bucket_unix: int, bucket_seconds: int) -> int:
    clean_bucket_seconds = max(1, int(bucket_seconds))
    if bucket_unix <= first_bucket_unix:
        return int(first_bucket_unix)
    offset = int(bucket_unix) - int(first_bucket_unix)
    return int(first_bucket_unix) + ((offset // clean_bucket_seconds) * clean_bucket_seconds)


def summary_aggregate_bucket_seconds(
    *,
    point_bucket_count: int,
    packet_bucket_count: int,
    first_bucket_unix: int,
    last_bucket_unix: int,
    raw_bucket_seconds: int,
    max_points: int,
) -> Optional[int]:
    """Aggregate bucket width that keeps every series within ``max_points``, or None."""
    longest_series = max(point_bucket_count, packet_bucket_count)
    if longest_series <= max_points:
        return None
    bucket_span_count = ((last_bucket_unix - first_bucket_unix) // raw_bucket_seconds) + 1
    aggregate_multiple = max(
        1,
        ceil(longest_series / max_points),
        ceil(bucket_span_count / max_points),
    )
    aggregate_bucket_seconds = raw_bucket_seconds * aggregate_multiple
    if aggregate_bucket_seconds <= raw_bucket_seconds:
        return None
    return aggregate_bucket_seconds


def build_downsampled_summary_metrics_payload(
    *,
    window_hours: int,
    rows: Iterable[tuple[object, ...]],
    packet_type_rows: Iterable[tuple[object, ...]],
    bucket_seconds: int,
    max_points: int,
) -> dict[str, object]:
    """Same result as downsampling ``build_summary_metrics_payload`` output to ``max_points``.

    Long windows hold hundreds of thousands of 15-second samples. Building a dict per raw
    sample only to collapse them afterwards cost seconds on a small host, so aggregate the
    parsed rows first and materialize only the kept points.
    """
    packet_counts_by_bucket = _parse_packet_type_counts(packet_type_rows)
    values = _parse_summary_values(rows)
    raw_bucket_seconds = max(1, int(bucket_seconds))
    clean_max_points = max(1, int(max_points))
    point_buckets = [point_values[0] for point_values in values if point_values[0] > 0]
    all_buckets = point_buckets + list(packet_counts_by_bucket)
    aggregate_bucket_seconds = (
        summary_aggregate_bucket_seconds(
            point_bucket_count=len(point_buckets),
            packet_bucket_count=len(packet_counts_by_bucket),
            first_bucket_unix=min(all_buckets),
            last_bucket_unix=max(all_buckets),
            raw_bucket_seconds=raw_bucket_seconds,
            max_points=clean_max_points,
        )
        if all_buckets
        else None
    )
    if aggregate_bucket_seconds is None:
        return {
            "window_hours": max(1, int(window_hours)),
            "bucket_seconds": raw_bucket_seconds,
            "points": [_summary_point(point_values) for point_values in values],
            "packet_series": _packet_series_payload(packet_counts_by_bucket),
            "summary": _summary_block(values),
        }

    first_bucket = min(all_buckets)
    last_values_by_bucket: dict[int, _SummaryValues] = {}
    for point_values in values:
        if point_values[0] <= 0:
            continue
        aggregate_bucket = aggregate_summary_bucket(point_values[0], first_bucket, aggregate_bucket_seconds)
        last_values_by_bucket[aggregate_bucket] = point_values
    points = [
        _summary_point(last_values_by_bucket[aggregate_bucket], bucket_unix=aggregate_bucket)
        for aggregate_bucket in sorted(last_values_by_bucket)
    ]
    series: dict[str, list[dict[str, object]]] = {}
    for key in _PACKET_TYPE_ORDER:
        counts_by_bucket: dict[int, int] = {}
        for bucket, bucket_counts in sorted(packet_counts_by_bucket.items()):
            packet_count = int(bucket_counts.get(key, 0))
            if packet_count <= 0:
                continue
            aggregate_bucket = aggregate_summary_bucket(bucket, first_bucket, aggregate_bucket_seconds)
            counts_by_bucket[aggregate_bucket] = counts_by_bucket.get(aggregate_bucket, 0) + packet_count
        series[key] = [
            {"bucket_unix": bucket, "packet_count": count}
            for bucket, count in sorted(counts_by_bucket.items())
            if count > 0
        ]
    return {
        "window_hours": max(1, int(window_hours)),
        "bucket_seconds": aggregate_bucket_seconds,
        "points": points,
        "packet_series": {
            "available": True,
            "order": list(_PACKET_TYPE_ORDER),
            "series": series,
        },
        "summary": _summary_block(values),
        "resolution": {
            "downsampled": True,
            "max_points": clean_max_points,
            "raw_bucket_seconds": raw_bucket_seconds,
            "bucket_seconds": aggregate_bucket_seconds,
            "raw_points": len(point_buckets),
            "points": len(points),
        },
    }
