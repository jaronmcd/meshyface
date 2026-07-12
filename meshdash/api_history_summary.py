from collections.abc import Iterable
from inspect import Parameter, signature
from math import ceil
from urllib.parse import parse_qs

from .helpers import format_epoch
from .http_route_contracts import (
    EmptySummaryMetricsFn,
    ParseHistoryWindowRequestFn,
    SummaryMetricsHistoryFn,
    ToIntFn,
)

_DEFAULT_SUMMARY_MAX_POINTS = 1440
_MIN_SUMMARY_MAX_POINTS = 64
_MAX_SUMMARY_MAX_POINTS = 10000
_FALSE_QUERY_VALUES = {"0", "false", "no", "off", "skip"}


def _clean_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        clean = int(value)
    except (TypeError, ValueError):
        return None
    if clean <= 0:
        return None
    return clean


def _packet_series_bucket_values(packet_series: object) -> Iterable[int]:
    if not isinstance(packet_series, dict):
        return []
    raw_series = packet_series.get("series")
    if not isinstance(raw_series, dict):
        return []
    buckets: list[int] = []
    for raw_rows in raw_series.values():
        if not isinstance(raw_rows, list):
            continue
        for row in raw_rows:
            if not isinstance(row, dict):
                continue
            bucket = _clean_positive_int(row.get("bucket_unix"))
            if bucket is not None:
                buckets.append(bucket)
    return buckets


def _summary_points_limit(query: str, to_int_fn: ToIntFn) -> int | None:
    query_obj = parse_qs(query or "")
    raw_points = str(query_obj.get("points", [""])[0] or "").strip().lower()
    if raw_points in {"all", "full", "raw"}:
        return None
    parsed_points = to_int_fn(raw_points)
    if isinstance(parsed_points, int) and parsed_points > 0:
        return max(_MIN_SUMMARY_MAX_POINTS, min(_MAX_SUMMARY_MAX_POINTS, parsed_points))
    return _DEFAULT_SUMMARY_MAX_POINTS


def _summary_packet_series_enabled(query: str) -> bool:
    query_obj = parse_qs(query or "")
    raw_values = query_obj.get("packet_series")
    if not raw_values:
        return True
    raw_value = str(raw_values[0] or "").strip().lower()
    return raw_value not in _FALSE_QUERY_VALUES


def _unavailable_packet_series_payload() -> dict[str, object]:
    return {
        "available": False,
        "order": [],
        "series": {},
    }


def _without_packet_series(payload: dict[str, object]) -> dict[str, object]:
    next_payload = dict(payload)
    next_payload["packet_series"] = _unavailable_packet_series_payload()
    return next_payload


def _summary_metrics_fn_supports_packet_series(summary_metrics_fn: SummaryMetricsHistoryFn) -> bool:
    try:
        params = signature(summary_metrics_fn).parameters
    except (TypeError, ValueError):
        return True
    return any(
        name == "include_packet_series" or param.kind == Parameter.VAR_KEYWORD
        for name, param in params.items()
    )


def _load_summary_metrics_payload(
    *,
    summary_metrics_fn: SummaryMetricsHistoryFn,
    hours_override: int | None,
    include_packet_series: bool,
) -> dict[str, object]:
    if include_packet_series:
        return summary_metrics_fn(hours_override)
    if _summary_metrics_fn_supports_packet_series(summary_metrics_fn):
        return _without_packet_series(
            summary_metrics_fn(hours_override, include_packet_series=False)
        )
    return _without_packet_series(summary_metrics_fn(hours_override))


def _aggregate_bucket(bucket_unix: int, first_bucket_unix: int, bucket_seconds: int) -> int:
    clean_bucket_seconds = max(1, int(bucket_seconds))
    if bucket_unix <= first_bucket_unix:
        return int(first_bucket_unix)
    offset = int(bucket_unix) - int(first_bucket_unix)
    return int(first_bucket_unix) + ((offset // clean_bucket_seconds) * clean_bucket_seconds)


def _downsample_summary_points(
    points: list[object],
    *,
    aggregate_bucket_seconds: int,
    first_bucket_unix: int,
) -> list[dict[str, object]]:
    by_bucket: dict[int, dict[str, object]] = {}
    for point in points:
        if not isinstance(point, dict):
            continue
        bucket = _clean_positive_int(point.get("bucket_unix"))
        if bucket is None:
            continue
        aggregate_bucket = _aggregate_bucket(
            bucket,
            first_bucket_unix,
            aggregate_bucket_seconds,
        )
        next_point = dict(point)
        next_point["bucket_unix"] = aggregate_bucket
        next_point["bucket_time"] = format_epoch(aggregate_bucket)
        by_bucket[aggregate_bucket] = next_point
    return [by_bucket[bucket] for bucket in sorted(by_bucket)]


def _downsample_packet_series(
    packet_series: object,
    *,
    aggregate_bucket_seconds: int,
    first_bucket_unix: int,
) -> object:
    if not isinstance(packet_series, dict):
        return packet_series
    raw_series = packet_series.get("series")
    if not isinstance(raw_series, dict):
        return dict(packet_series)
    raw_order = packet_series.get("order")
    order = [str(key) for key in raw_order] if isinstance(raw_order, list) else []
    for key in raw_series:
        clean_key = str(key)
        if clean_key not in order:
            order.append(clean_key)
    next_series: dict[str, list[dict[str, object]]] = {}
    for key in order:
        rows = raw_series.get(key, [])
        counts_by_bucket: dict[int, int] = {}
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                bucket = _clean_positive_int(row.get("bucket_unix"))
                packet_count = _clean_positive_int(row.get("packet_count"))
                if bucket is None or packet_count is None:
                    continue
                aggregate_bucket = _aggregate_bucket(
                    bucket,
                    first_bucket_unix,
                    aggregate_bucket_seconds,
                )
                counts_by_bucket[aggregate_bucket] = (
                    counts_by_bucket.get(aggregate_bucket, 0) + packet_count
                )
        next_series[key] = [
            {
                "bucket_unix": bucket,
                "packet_count": count,
            }
            for bucket, count in sorted(counts_by_bucket.items())
            if count > 0
        ]
    next_packet_series = dict(packet_series)
    next_packet_series["order"] = order
    next_packet_series["series"] = next_series
    return next_packet_series


def _downsample_summary_metrics_payload(
    payload: dict,
    *,
    max_points: int | None,
) -> dict:
    if max_points is None:
        return payload
    clean_max_points = max(
        _MIN_SUMMARY_MAX_POINTS,
        min(_MAX_SUMMARY_MAX_POINTS, int(max_points)),
    )
    raw_bucket_seconds = max(1, _clean_positive_int(payload.get("bucket_seconds")) or 1)
    raw_points = payload.get("points")
    points = raw_points if isinstance(raw_points, list) else []
    point_buckets = [
        bucket
        for bucket in (
            _clean_positive_int(point.get("bucket_unix"))
            for point in points
            if isinstance(point, dict)
        )
        if bucket is not None
    ]
    packet_buckets = list(_packet_series_bucket_values(payload.get("packet_series")))
    all_buckets = point_buckets + packet_buckets
    if not all_buckets:
        return payload
    longest_series = max(
        len(point_buckets),
        len(set(packet_buckets)),
    )
    if longest_series <= clean_max_points:
        return payload

    first_bucket = min(all_buckets)
    last_bucket = max(all_buckets)
    bucket_span_count = ((last_bucket - first_bucket) // raw_bucket_seconds) + 1
    aggregate_multiple = max(
        1,
        ceil(longest_series / clean_max_points),
        ceil(bucket_span_count / clean_max_points),
    )
    aggregate_bucket_seconds = raw_bucket_seconds * aggregate_multiple
    if aggregate_bucket_seconds <= raw_bucket_seconds:
        return payload

    next_payload = dict(payload)
    next_payload["bucket_seconds"] = aggregate_bucket_seconds
    next_payload["points"] = _downsample_summary_points(
        points,
        aggregate_bucket_seconds=aggregate_bucket_seconds,
        first_bucket_unix=first_bucket,
    )
    next_payload["packet_series"] = _downsample_packet_series(
        payload.get("packet_series"),
        aggregate_bucket_seconds=aggregate_bucket_seconds,
        first_bucket_unix=first_bucket,
    )
    next_payload["resolution"] = {
        "downsampled": True,
        "max_points": clean_max_points,
        "raw_bucket_seconds": raw_bucket_seconds,
        "bucket_seconds": aggregate_bucket_seconds,
        "raw_points": len(point_buckets),
        "points": len(next_payload["points"]),
    }
    return next_payload


def build_summary_metrics_response(
    *,
    query: str,
    summary_metrics_fn: SummaryMetricsHistoryFn | None,
    default_node_history_hours: int,
    to_int_fn: ToIntFn,
    parse_history_window_request_fn: ParseHistoryWindowRequestFn,
    empty_summary_metrics_fn: EmptySummaryMetricsFn,
) -> dict:
    query_obj = parse_history_window_request_fn(
        query,
        to_int_fn=to_int_fn,
    )
    hours_override = query_obj.hours_override
    include_packet_series = _summary_packet_series_enabled(query)
    if summary_metrics_fn is None:
        clean_hours = (
            hours_override
            if isinstance(hours_override, int) and hours_override > 0
            else default_node_history_hours
        )
        payload = empty_summary_metrics_fn(clean_hours)
    else:
        payload = _load_summary_metrics_payload(
            summary_metrics_fn=summary_metrics_fn,
            hours_override=hours_override,
            include_packet_series=include_packet_series,
        )
    return _downsample_summary_metrics_payload(
        payload,
        max_points=_summary_points_limit(query, to_int_fn),
    )
