import math
import time
from collections.abc import Iterable


MAX_NEIGHBOR_INFO_EDGES_PER_PACKET = 64
_BROADCAST_NODE_NUM = 0xFFFFFFFF


def _canonical_node_id(value: object) -> str:
    """Return a transport-derived Meshtastic node id, never a NodeDB alias."""
    if isinstance(value, bool):
        return ""
    if isinstance(value, str):
        text = value.strip()
        lowered = text.lower()
        if lowered in ("^all", "all", "broadcast", "!ffffffff", "ffffffff", "0xffffffff"):
            return "^all"
        if text.startswith("!") and len(text) == 9:
            raw = text[1:]
            if all(ch in "0123456789abcdefABCDEF" for ch in raw):
                return f"!{raw.lower()}"
        if len(text) == 8 and all(ch in "0123456789abcdefABCDEF" for ch in text):
            return f"!{text.lower()}"
        if not text.isdigit():
            return ""
        value = text
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            return ""
    try:
        numeric = int(value)
    except (TypeError, ValueError, OverflowError):
        return ""
    if numeric < 0 or numeric > _BROADCAST_NODE_NUM:
        return ""
    if numeric == _BROADCAST_NODE_NUM:
        return "^all"
    return f"!{numeric:08x}"


def _neighbor_payload(decoded: object) -> dict[str, object] | None:
    if not isinstance(decoded, dict):
        return None
    for key in ("neighborinfo", "neighbor_info", "neighborInfo"):
        value = decoded.get(key)
        if isinstance(value, dict):
            return value
    payload = decoded.get("payload")
    if isinstance(payload, dict):
        for key in ("neighborinfo", "neighbor_info", "neighborInfo"):
            value = payload.get(key)
            if isinstance(value, dict):
                return value
        return payload
    return None


def _first_present(mapping: dict[str, object], *keys: str) -> object | None:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def extract_neighbor_info_edges(
    decoded: object,
    *,
    outer_source_id: object,
) -> list[dict[str, object]]:
    """Extract bounded NeighborInfo edges bound to the packet header sender."""
    if not isinstance(decoded, dict):
        return []
    portnum = decoded.get("portnum")
    if portnum is not None and str(portnum) != "NEIGHBORINFO_APP":
        return []

    payload = _neighbor_payload(decoded)
    if not isinstance(payload, dict):
        return []

    source_id = _canonical_node_id(outer_source_id)
    if not source_id or source_id == "^all":
        return []

    claimed_source = _first_present(payload, "node_id", "nodeId")
    if claimed_source is not None:
        claimed_source_id = _canonical_node_id(claimed_source)
        if not claimed_source_id or claimed_source_id != source_id:
            return []

    neighbors = payload.get("neighbors")
    if not isinstance(neighbors, Iterable) or isinstance(neighbors, (str, bytes, dict)):
        return []

    rows: list[dict[str, object]] = []
    seen_neighbor_ids: set[str] = set()
    for index, entry in enumerate(neighbors):
        if index >= MAX_NEIGHBOR_INFO_EDGES_PER_PACKET:
            break
        if not isinstance(entry, dict):
            continue
        neighbor_id = _canonical_node_id(_first_present(entry, "node_id", "nodeId"))
        if (
            not neighbor_id
            or neighbor_id == "^all"
            or neighbor_id == source_id
            or neighbor_id in seen_neighbor_ids
        ):
            continue
        seen_neighbor_ids.add(neighbor_id)
        try:
            last_rx_time = int(_first_present(entry, "last_rx_time", "lastRxTime") or 0)
        except (TypeError, ValueError, OverflowError):
            last_rx_time = 0
        latest_plausible_time = int(time.time()) + 5 * 60
        if last_rx_time > latest_plausible_time:
            last_rx_time = latest_plausible_time
        try:
            snr = float(entry.get("snr"))
        except (TypeError, ValueError, OverflowError):
            snr = None
        if snr is not None and not math.isfinite(snr):
            snr = None
        rows.append(
            {
                "from_id": source_id,
                "to_id": neighbor_id,
                "rx_time": last_rx_time if last_rx_time > 0 else None,
                "rx_snr": snr,
            }
        )
    return rows
