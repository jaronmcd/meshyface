import json
import time
from typing import Callable, Optional

from .helpers import safe_json_loads as _safe_json_loads, to_int as _to_int
from .history_time import clamp_future_unix as _clamp_future_unix


def normalize_connection_event_input(
    *,
    rx_time: Optional[int],
    portnum: Optional[str],
    hops: Optional[int],
    now_unix_fn: Callable[[], float] = time.time,
) -> tuple[int, Optional[str], Optional[int]]:
    now_unix = int(now_unix_fn())
    event_unix = _clamp_future_unix(rx_time, now_unix=now_unix)
    clean_port = str(portnum) if portnum is not None else None
    clean_hops = hops if isinstance(hops, int) and hops >= 0 else None
    return event_unix, clean_port, clean_hops


def build_connection_insert_values(
    *,
    from_id: str,
    to_id: str,
    event_unix: int,
    clean_port: Optional[str],
    clean_hops: Optional[int],
) -> tuple[object, ...]:
    ports: set[str] = set()
    if clean_port:
        ports.add(clean_port)
    return (
        from_id,
        to_id,
        event_unix,
        event_unix,
        1,
        json.dumps(sorted(ports), separators=(",", ":")),
        clean_hops,
        clean_hops if clean_hops is not None else 0,
        1 if clean_hops is not None else 0,
    )


def merge_connection_row(
    *,
    row: tuple[object, ...],
    event_unix: int,
    clean_port: Optional[str],
    clean_hops: Optional[int],
) -> dict[str, object]:
    first_seen_unix, last_seen_unix, seen_count, portnums_json, last_hops, hops_sum, hops_count = row
    ports = _safe_json_loads(portnums_json, [])
    if not isinstance(ports, list):
        ports = []
    port_set = {str(p) for p in ports if p is not None}
    if clean_port:
        port_set.add(clean_port)

    merged_first = min(_to_int(first_seen_unix) or event_unix, event_unix)
    merged_last = max(_to_int(last_seen_unix) or event_unix, event_unix)
    merged_count = (_to_int(seen_count) or 0) + 1

    merged_hops_sum = _to_int(hops_sum) or 0
    merged_hops_count = _to_int(hops_count) or 0
    merged_last_hops = _to_int(last_hops)
    if clean_hops is not None:
        merged_hops_sum += clean_hops
        merged_hops_count += 1
        merged_last_hops = clean_hops

    return {
        "first_seen_unix": merged_first,
        "last_seen_unix": merged_last,
        "seen_count": merged_count,
        "portnums_json": json.dumps(sorted(port_set), separators=(",", ":")),
        "last_hops": merged_last_hops,
        "hops_sum": merged_hops_sum,
        "hops_count": merged_hops_count,
    }
