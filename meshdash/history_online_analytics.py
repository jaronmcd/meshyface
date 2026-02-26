from datetime import datetime
from collections.abc import Iterable
from typing import Optional

from .helpers import format_epoch as _format_epoch
from .helpers import to_int as _to_int


def build_online_activity_payload(
    *,
    window_hours: int,
    hour_rows: Iterable[tuple[object, ...]],
    distinct_nodes: int,
    timezone_label: Optional[str] = None,
) -> dict[str, object]:
    hours = max(1, int(window_hours))
    tz_label = timezone_label or datetime.now().astimezone().tzname() or "local"

    points: list[dict[str, object]] = []
    by_hour: dict[int, list[int]] = {hour: [] for hour in range(24)}
    total_online = 0
    max_online = 0
    first_bucket: Optional[int] = None
    last_bucket: Optional[int] = None

    for raw_bucket, raw_online in hour_rows:
        bucket = _to_int(raw_bucket)
        if bucket is None:
            continue
        online_nodes = max(0, _to_int(raw_online) or 0)
        local_dt = datetime.fromtimestamp(bucket)
        hour_local = local_dt.hour
        by_hour.setdefault(hour_local, []).append(online_nodes)
        total_online += online_nodes
        max_online = max(max_online, online_nodes)
        first_bucket = bucket if first_bucket is None else min(first_bucket, bucket)
        last_bucket = bucket if last_bucket is None else max(last_bucket, bucket)
        points.append(
            {
                "bucket_unix": bucket,
                "bucket_time": _format_epoch(bucket),
                "bucket_local": local_dt.strftime("%Y-%m-%d %H:00"),
                "hour_local": hour_local,
                "hour_label": f"{hour_local:02d}:00",
                "online_nodes": online_nodes,
            }
        )

    best_hour: Optional[int] = None
    best_avg: Optional[float] = None
    hourly_profile: list[dict[str, object]] = []
    for hour in range(24):
        samples = by_hour.get(hour, [])
        sample_count = len(samples)
        avg_online = (sum(samples) / sample_count) if sample_count > 0 else None
        peak_online = max(samples) if sample_count > 0 else 0
        if avg_online is not None:
            if best_avg is None or avg_online > best_avg + 1e-9:
                best_hour = hour
                best_avg = avg_online
            elif best_hour is not None and abs(avg_online - best_avg) <= 1e-9 and hour < best_hour:
                best_hour = hour
        hourly_profile.append(
            {
                "hour": hour,
                "label": f"{hour:02d}:00",
                "avg_online_nodes": round(avg_online, 2) if avg_online is not None else None,
                "sample_hours": sample_count,
                "peak_online_nodes": peak_online,
            }
        )

    sample_hours = len(points)
    avg_online_nodes = (total_online / sample_hours) if sample_hours > 0 else None

    return {
        "window_hours": hours,
        "timezone": "local",
        "timezone_label": tz_label,
        "points": points,
        "hourly_profile": hourly_profile,
        "summary": {
            "sample_hours": sample_hours,
            "distinct_nodes": int(distinct_nodes or 0),
            "max_online_nodes": max_online,
            "avg_online_nodes": round(avg_online_nodes, 2) if avg_online_nodes is not None else None,
            "best_hour": best_hour,
            "best_hour_label": f"{best_hour:02d}:00" if best_hour is not None else None,
            "best_hour_avg_online_nodes": round(best_avg, 2) if best_avg is not None else None,
            "window_start": _format_epoch(first_bucket),
            "window_end": _format_epoch(last_bucket),
        },
    }
