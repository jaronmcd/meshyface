import time
from typing import Callable, Dict, Optional

from .revision import RevisionInfo
from .tracker_snapshot_contracts import TrackerSnapshot, coerce_tracker_snapshot

from .helpers import disk_space_info


def apply_node_saved_counts(
    rows: list[Dict[str, object]],
    node_saved_counts: Dict[str, Dict[str, object]],
) -> None:
    for row in rows:
        stats = node_saved_counts.get(str(row.get("id") or ""), {})
        row["saved_packets"] = int(stats.get("saved_packets") or 0)
        row["saved_points"] = int(stats.get("saved_points") or 0)
        row["saved_last_seen"] = stats.get("saved_last_seen")


def collect_local_state_safe(
    iface: object,
    *,
    collect_local_state_fn: Callable[[object], Dict[str, object]],
) -> tuple[Dict[str, object], Optional[str]]:
    try:
        return collect_local_state_fn(iface), None
    except Exception as exc:
        return {}, str(exc)


def modem_preset_from_local_state(local_state: Dict[str, object]) -> Optional[str]:
    try:
        return (local_state.get("local_config") or {}).get("lora", {}).get("modem_preset")
    except Exception:
        return None


def build_summary_payload(
    *,
    target: str,
    started_at: float,
    node_rows: list[Dict[str, object]],
    nodes_with_position: int,
    tracker_data: TrackerSnapshot | Dict[str, object],
    storage_probe_path: Optional[str],
    revision_info: RevisionInfo | Dict[str, str],
    modem_preset: Optional[str],
    now_ts_fn: Callable[[], float] = time.time,
    disk_space_info_fn: Callable[[Optional[str]], Dict[str, object]] = disk_space_info,
) -> Dict[str, object]:
    tracker_snapshot = coerce_tracker_snapshot(tracker_data)
    if isinstance(revision_info, RevisionInfo):
        revision_payload = revision_info.as_dict()
    else:
        revision_payload = dict(revision_info)
    return {
        "target": target,
        "uptime_seconds": int(max(0, now_ts_fn() - started_at)),
        "node_count": len(node_rows),
        "nodes_with_position": nodes_with_position,
        "live_packet_count": tracker_snapshot.live_packet_count,
        "edge_count": len(tracker_snapshot.edges),
        "real_edge_count": tracker_snapshot.real_edge_count,
        "recent_packet_buffer": len(tracker_snapshot.recent_packets),
        "modem_preset": modem_preset,
        "disk": disk_space_info_fn(storage_probe_path),
        "revision": revision_payload,
    }
