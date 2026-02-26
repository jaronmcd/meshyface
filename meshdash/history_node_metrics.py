from collections.abc import Iterable
from typing import Optional

from .helpers import format_epoch as _format_epoch
from .helpers import to_float as _to_float
from .helpers import to_int as _to_int


def build_metric_history_points(
    metric_rows: Iterable[
        tuple[
            object,
            object,
            object,
            object,
            object,
            object,
            object,
            object,
            object,
            object,
            object,
            object,
            object,
            object,
            object,
        ]
    ],
) -> dict[str, object]:
    points: list[dict[str, object]] = []
    total_packets = 0
    snr_min_all: Optional[float] = None
    snr_max_all: Optional[float] = None
    rssi_min_all: Optional[float] = None
    rssi_max_all: Optional[float] = None
    first_bucket: Optional[int] = None
    last_bucket: Optional[int] = None
    last_seen: Optional[int] = None

    for row in reversed(list(metric_rows)):
        (
            bucket_unix,
            packet_count,
            snr_sum,
            snr_count,
            snr_min,
            snr_max,
            rssi_sum,
            rssi_count,
            rssi_min,
            rssi_max,
            hops_sum,
            hops_count,
            hops_min,
            hops_max,
            last_seen_unix,
        ) = row

        bucket = _to_int(bucket_unix)
        if bucket is None:
            continue

        packets = _to_int(packet_count) or 0
        total_packets += packets
        first_bucket = bucket if first_bucket is None else min(first_bucket, bucket)
        last_bucket = bucket if last_bucket is None else max(last_bucket, bucket)
        seen_val = _to_int(last_seen_unix)
        if seen_val is not None:
            last_seen = seen_val if last_seen is None else max(last_seen, seen_val)

        snr_count_i = _to_int(snr_count) or 0
        rssi_count_i = _to_int(rssi_count) or 0
        hops_count_i = _to_int(hops_count) or 0
        snr_avg = (_to_float(snr_sum) or 0.0) / snr_count_i if snr_count_i > 0 else None
        rssi_avg = (_to_float(rssi_sum) or 0.0) / rssi_count_i if rssi_count_i > 0 else None
        hops_avg = (_to_float(hops_sum) or 0.0) / hops_count_i if hops_count_i > 0 else None

        snr_min_v = _to_float(snr_min)
        snr_max_v = _to_float(snr_max)
        rssi_min_v = _to_float(rssi_min)
        rssi_max_v = _to_float(rssi_max)

        if snr_min_v is not None:
            snr_min_all = snr_min_v if snr_min_all is None else min(snr_min_all, snr_min_v)
        if snr_max_v is not None:
            snr_max_all = snr_max_v if snr_max_all is None else max(snr_max_all, snr_max_v)
        if rssi_min_v is not None:
            rssi_min_all = rssi_min_v if rssi_min_all is None else min(rssi_min_all, rssi_min_v)
        if rssi_max_v is not None:
            rssi_max_all = rssi_max_v if rssi_max_all is None else max(rssi_max_all, rssi_max_v)

        points.append(
            {
                "bucket_unix": bucket,
                "bucket_time": _format_epoch(bucket),
                "packet_count": packets,
                "avg_snr": round(snr_avg, 2) if snr_avg is not None else None,
                "min_snr": snr_min_v,
                "max_snr": snr_max_v,
                "avg_rssi": round(rssi_avg, 2) if rssi_avg is not None else None,
                "min_rssi": rssi_min_v,
                "max_rssi": rssi_max_v,
                "avg_hops": round(hops_avg, 2) if hops_avg is not None else None,
                "min_hops": _to_int(hops_min),
                "max_hops": _to_int(hops_max),
                "hops_samples": hops_count_i,
                "last_seen": _format_epoch(last_seen_unix),
            }
        )

    return {
        "points": points,
        "total_packets": total_packets,
        "first_bucket": first_bucket,
        "last_bucket": last_bucket,
        "last_seen": last_seen,
        "snr_min": snr_min_all,
        "snr_max": snr_max_all,
        "rssi_min": rssi_min_all,
        "rssi_max": rssi_max_all,
    }
