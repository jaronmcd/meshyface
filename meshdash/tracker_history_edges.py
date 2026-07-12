import math
from collections.abc import Iterable

from .tracker_edges import MAX_TRACKED_EDGE_KEYS
from .tracker_snapshot_build_contracts import EdgeKey, EdgeRow


def _to_float(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _to_nonnegative_int(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(0, parsed)


def _to_optional_nonnegative_int(value: object, *, maximum: int | None = None) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed < 0 or (maximum is not None and parsed > maximum):
        return None
    return parsed


def _portnum_set(value: object) -> set[str]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return set()
    out: set[str] = set()
    for portnum in value:
        clean = str(portnum)
        if len(clean) <= 64:
            out.add(clean)
        if len(out) >= 64:
            break
    return out


def _metric_rollup(edge: EdgeRow, prefix: str) -> tuple[float, int, float | None, float | None]:
    total = _to_float(edge.get(f"{prefix}_sum"))
    count = _to_nonnegative_int(edge.get(f"{prefix}_count"))
    if total is None or count <= 0:
        return 0.0, 0, None, None
    return (
        total,
        count,
        _to_float(edge.get(f"{prefix}_min")),
        _to_float(edge.get(f"{prefix}_max")),
    )


def build_historical_edges(
    connection_rows: Iterable[EdgeRow],
) -> dict[EdgeKey, EdgeRow]:
    out: dict[EdgeKey, EdgeRow] = {}
    for edge in connection_rows:
        from_id = str(edge["from"])
        to_id = str(edge["to"])
        key = (from_id, to_id)
        if key not in out and len(out) >= MAX_TRACKED_EDGE_KEYS:
            break
        snr_sum, snr_count, snr_min, snr_max = _metric_rollup(edge, "snr")
        rssi_sum, rssi_count, rssi_min, rssi_max = _metric_rollup(edge, "rssi")
        out[key] = {
            "from": from_id,
            "to": to_id,
            "count": _to_nonnegative_int(edge.get("count")),
            "first_rx_time": _to_optional_nonnegative_int(edge.get("first_rx_time")),
            "last_rx_time": _to_optional_nonnegative_int(edge.get("last_rx_time")),
            "portnums": _portnum_set(edge.get("portnums")),
            "last_hops": _to_optional_nonnegative_int(edge.get("last_hops"), maximum=255),
            "hops_sum": _to_nonnegative_int(edge.get("hops_sum")),
            "hops_count": _to_nonnegative_int(edge.get("hops_count")),
            "snr_sum": snr_sum,
            "snr_count": snr_count,
            "snr_min": snr_min,
            "snr_max": snr_max,
            "rssi_sum": rssi_sum,
            "rssi_count": rssi_count,
            "rssi_min": rssi_min,
            "rssi_max": rssi_max,
        }
    return out
