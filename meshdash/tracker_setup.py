from collections import Counter, deque
from typing import Any, Dict, Tuple


def initialize_tracker_buffers(packet_limit: int) -> Dict[str, Any]:
    return {
        "edges": {},
        "historical_edges": {},
        "port_counts": Counter(),
        "recent_packets": deque(maxlen=packet_limit),
        "recent_chat": deque(maxlen=packet_limit),
    }


def apply_tracker_history_bootstrap(
    *,
    history_store: Any,
    packet_limit: int,
    recent_packets: Any,
    recent_chat: Any,
    load_tracker_history_bootstrap_fn: Any,
    build_historical_edges_fn: Any,
) -> Dict[Tuple[str, str], Dict[str, Any]]:
    if history_store is None:
        return {}
    bootstrap = load_tracker_history_bootstrap_fn(
        history_store,
        packet_limit=packet_limit,
        build_historical_edges_fn=build_historical_edges_fn,
    )
    recent_packets.extend(bootstrap["recent_packets"])
    recent_chat.extend(bootstrap["recent_chat"])
    return bootstrap["historical_edges"]
