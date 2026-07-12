import math
from typing import Optional

from .tracker_snapshot_build_contracts import EdgeKey, EdgeRow


MAX_TRACKED_EDGE_KEYS = 4096


def _to_metric_value(value: object) -> float | None:
    try:
        metric = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(metric):
        return None
    return metric


def _to_nonnegative_int(value: object, *, maximum: int | None = None) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed < 0 or (maximum is not None and parsed > maximum):
        return None
    return parsed


def _merge_signal_metric(edge: EdgeRow, prefix: str, value: object) -> None:
    metric = _to_metric_value(value)
    if metric is None:
        return
    sum_key = f"{prefix}_sum"
    count_key = f"{prefix}_count"
    min_key = f"{prefix}_min"
    max_key = f"{prefix}_max"
    current_sum = _to_metric_value(edge.get(sum_key))
    current_count = _to_nonnegative_int(edge.get(count_key)) or 0
    if current_sum is None:
        current_sum = 0.0
        current_count = 0
    merged_sum = current_sum + metric
    if not math.isfinite(merged_sum):
        return
    edge[sum_key] = merged_sum
    edge[count_key] = current_count + 1
    current_min = _to_metric_value(edge.get(min_key))
    current_max = _to_metric_value(edge.get(max_key))
    edge[min_key] = metric if current_min is None else min(current_min, metric)
    edge[max_key] = metric if current_max is None else max(current_max, metric)


def _new_edge(from_id: str, to_id: str) -> EdgeRow:
    return {
        "from": from_id,
        "to": to_id,
        "count": 0,
        "first_rx_time": None,
        "last_rx_time": None,
        "portnums": set(),
        "last_hops": None,
        "hops_sum": 0,
        "hops_count": 0,
        "snr_sum": 0.0,
        "snr_count": 0,
        "snr_min": None,
        "snr_max": None,
        "rssi_sum": 0.0,
        "rssi_count": 0,
        "rssi_min": None,
        "rssi_max": None,
    }


def is_direct_link(from_id: object, to_id: object) -> bool:
    from_text = str(from_id or "")
    to_text = str(to_id or "")
    return (
        bool(from_id)
        and bool(to_id)
        and len(from_text) <= 64
        and len(to_text) <= 64
        and from_id not in ("Unknown",)
        and to_id not in ("^all", "Unknown")
        and from_text != to_text
    )


def _edge_for_key(edges: dict[EdgeKey, EdgeRow], key: EdgeKey) -> EdgeRow | None:
    edge = edges.get(key)
    if edge is not None:
        # Keep insertion order as a cheap LRU so active legitimate links are
        # not permanently crowded out by an earlier burst of unique claims.
        edges[key] = edges.pop(key)
        return edge
    if len(edges) >= MAX_TRACKED_EDGE_KEYS:
        try:
            oldest_key = next(iter(edges))
        except StopIteration:
            oldest_key = None
        if oldest_key is not None:
            edges.pop(oldest_key, None)
    edge = _new_edge(*key)
    edges[key] = edge
    return edge


def _record_on_edge(
    edge: EdgeRow,
    *,
    rx_time: object,
    portnum: object,
    hops: object,
    rx_snr: object,
    rx_rssi: object,
) -> None:
    edge["count"] = (_to_nonnegative_int(edge.get("count")) or 0) + 1

    clean_rx_time = _to_nonnegative_int(rx_time)
    first_rx_time = _to_nonnegative_int(edge.get("first_rx_time"))
    last_rx_time = _to_nonnegative_int(edge.get("last_rx_time"))
    if clean_rx_time is not None and clean_rx_time > 0:
        if first_rx_time is None or clean_rx_time < first_rx_time:
            edge["first_rx_time"] = clean_rx_time
        if last_rx_time is None or clean_rx_time > last_rx_time:
            edge["last_rx_time"] = clean_rx_time

    if portnum is not None:
        clean_portnum = str(portnum)
        if len(clean_portnum) <= 64:
            portnums = edge.get("portnums")
            if not isinstance(portnums, set):
                portnums = set()
                edge["portnums"] = portnums
            if clean_portnum in portnums or len(portnums) < 64:
                portnums.add(clean_portnum)

    clean_hops = _to_nonnegative_int(hops, maximum=255)
    if clean_hops is not None:
        edge["last_hops"] = clean_hops
        edge["hops_sum"] = (_to_nonnegative_int(edge.get("hops_sum")) or 0) + clean_hops
        edge["hops_count"] = (_to_nonnegative_int(edge.get("hops_count")) or 0) + 1

    _merge_signal_metric(edge, "snr", rx_snr)
    _merge_signal_metric(edge, "rssi", rx_rssi)


def record_direct_edge_observation(
    *,
    session_edges: dict[EdgeKey, EdgeRow],
    historical_edges: dict[EdgeKey, EdgeRow],
    from_id: object,
    to_id: object,
    rx_time: Optional[int],
    portnum: Optional[object],
    hops: Optional[int],
    rx_snr: Optional[object],
    rx_rssi: Optional[object],
    include_live_count: bool,
) -> Optional[EdgeKey]:
    if not is_direct_link(from_id, to_id):
        return None

    clean_from = str(from_id)
    clean_to = str(to_id)
    key = (clean_from, clean_to)

    recorded = False
    edge = _edge_for_key(session_edges, key)
    if edge is not None:
        _record_on_edge(
            edge,
            rx_time=rx_time,
            portnum=portnum,
            hops=hops,
            rx_snr=rx_snr,
            rx_rssi=rx_rssi,
        )
        recorded = True

    if include_live_count:
        hist = _edge_for_key(historical_edges, key)
        if hist is not None:
            _record_on_edge(
                hist,
                rx_time=rx_time,
                portnum=portnum,
                hops=hops,
                rx_snr=rx_snr,
                rx_rssi=rx_rssi,
            )
            recorded = True

    return key if recorded else None
