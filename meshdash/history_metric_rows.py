from typing import Optional

from .helpers import to_float as _to_float, to_int as _to_int
from .history_rollups import merge_metric as _merge_metric


def build_metric_rollup_values(
    *,
    event_unix: int,
    rx_snr: Optional[float],
    rx_rssi: Optional[float],
    hops: Optional[int],
) -> dict[str, object]:
    snr_sum, snr_count, snr_min, snr_max = _merge_metric(0.0, 0, None, None, rx_snr)
    rssi_sum, rssi_count, rssi_min, rssi_max = _merge_metric(0.0, 0, None, None, rx_rssi)
    hops_sum, hops_count, hops_min, hops_max = _merge_metric(
        0.0,
        0,
        None,
        None,
        _to_float(hops),
    )
    return {
        "packet_count": 1,
        "snr_sum": snr_sum,
        "snr_count": snr_count,
        "snr_min": snr_min,
        "snr_max": snr_max,
        "rssi_sum": rssi_sum,
        "rssi_count": rssi_count,
        "rssi_min": rssi_min,
        "rssi_max": rssi_max,
        "hops_sum": int(hops_sum),
        "hops_count": hops_count,
        "hops_min": int(hops_min) if hops_min is not None else None,
        "hops_max": int(hops_max) if hops_max is not None else None,
        "last_seen_unix": event_unix,
    }


def merge_metric_rollup_row(
    *,
    row: tuple[object, ...],
    event_unix: int,
    rx_snr: Optional[float],
    rx_rssi: Optional[float],
    hops: Optional[int],
) -> dict[str, object]:
    (
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

    merged_snr_sum, merged_snr_count, merged_snr_min, merged_snr_max = _merge_metric(
        snr_sum,
        snr_count,
        snr_min,
        snr_max,
        rx_snr,
    )
    merged_rssi_sum, merged_rssi_count, merged_rssi_min, merged_rssi_max = _merge_metric(
        rssi_sum,
        rssi_count,
        rssi_min,
        rssi_max,
        rx_rssi,
    )
    merged_hops_sum, merged_hops_count, merged_hops_min, merged_hops_max = _merge_metric(
        hops_sum,
        hops_count,
        hops_min,
        hops_max,
        _to_float(hops),
    )
    return {
        "packet_count": int(packet_count or 0) + 1,
        "snr_sum": merged_snr_sum,
        "snr_count": merged_snr_count,
        "snr_min": merged_snr_min,
        "snr_max": merged_snr_max,
        "rssi_sum": merged_rssi_sum,
        "rssi_count": merged_rssi_count,
        "rssi_min": merged_rssi_min,
        "rssi_max": merged_rssi_max,
        "hops_sum": int(merged_hops_sum),
        "hops_count": merged_hops_count,
        "hops_min": int(merged_hops_min) if merged_hops_min is not None else None,
        "hops_max": int(merged_hops_max) if merged_hops_max is not None else None,
        "last_seen_unix": max(_to_int(last_seen_unix) or event_unix, event_unix),
    }
