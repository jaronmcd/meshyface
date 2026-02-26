from typing import Optional

from .tracker_snapshot_build_contracts import EdgeKey, EdgeRow


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
    }


def is_direct_link(from_id: object, to_id: object) -> bool:
    return (
        bool(from_id)
        and bool(to_id)
        and from_id not in ("Unknown",)
        and to_id not in ("^all", "Unknown")
        and str(from_id) != str(to_id)
    )


def record_direct_edge_observation(
    *,
    session_edges: dict[EdgeKey, EdgeRow],
    historical_edges: dict[EdgeKey, EdgeRow],
    from_id: object,
    to_id: object,
    rx_time: Optional[int],
    portnum: Optional[object],
    hops: Optional[int],
    include_live_count: bool,
) -> Optional[EdgeKey]:
    if not is_direct_link(from_id, to_id):
        return None

    clean_from = str(from_id)
    clean_to = str(to_id)
    key = (clean_from, clean_to)

    edge = session_edges.setdefault(key, _new_edge(clean_from, clean_to))
    edge["count"] += 1
    if rx_time is not None and (edge["first_rx_time"] is None or rx_time < edge["first_rx_time"]):
        edge["first_rx_time"] = rx_time
    if rx_time is not None and (edge["last_rx_time"] is None or rx_time > edge["last_rx_time"]):
        edge["last_rx_time"] = rx_time
    if portnum is not None:
        edge["portnums"].add(str(portnum))
    if hops is not None:
        edge["last_hops"] = hops
        edge["hops_sum"] += hops
        edge["hops_count"] += 1

    if include_live_count:
        hist = historical_edges.setdefault(key, _new_edge(clean_from, clean_to))
        hist["count"] += 1
        if rx_time is not None and (hist["first_rx_time"] is None or rx_time < hist["first_rx_time"]):
            hist["first_rx_time"] = rx_time
        if rx_time is not None and (hist["last_rx_time"] is None or rx_time > hist["last_rx_time"]):
            hist["last_rx_time"] = rx_time
        if portnum is not None:
            hist["portnums"].add(str(portnum))
        if hops is not None:
            hist["last_hops"] = hops
            hist["hops_sum"] += hops
            hist["hops_count"] += 1

    return key
