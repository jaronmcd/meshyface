from dataclasses import dataclass
from typing import Mapping

TrackerEdgeRow = dict[str, object]
TrackerPortCountRow = dict[str, object]
TrackerPacketRow = dict[str, object]
TrackerChatRow = dict[str, object]


@dataclass(frozen=True)
class TrackerSnapshot:
    live_packet_count: int
    real_edge_count: int
    edges: list[TrackerEdgeRow]
    port_counts: list[TrackerPortCountRow]
    recent_packets: list[TrackerPacketRow]
    recent_chat: list[TrackerChatRow]

    def as_dict(self) -> dict[str, object]:
        return {
            "live_packet_count": self.live_packet_count,
            "real_edge_count": self.real_edge_count,
            "edges": self.edges,
            "port_counts": self.port_counts,
            "recent_packets": self.recent_packets,
            "recent_chat": self.recent_chat,
        }


def empty_tracker_snapshot() -> TrackerSnapshot:
    return TrackerSnapshot(
        live_packet_count=0,
        real_edge_count=0,
        edges=[],
        port_counts=[],
        recent_packets=[],
        recent_chat=[],
    )


def coerce_tracker_snapshot(value: TrackerSnapshot | Mapping[str, object]) -> TrackerSnapshot:
    if isinstance(value, TrackerSnapshot):
        return value
    if not isinstance(value, Mapping):
        raise TypeError(f"Expected TrackerSnapshot or mapping, got {type(value)!r}")

    live_packet_count = int(value.get("live_packet_count") or 0)
    real_edge_count = int(value.get("real_edge_count") or 0)
    edges_raw = value.get("edges") or []
    port_counts_raw = value.get("port_counts") or []
    recent_packets_raw = value.get("recent_packets") or []
    recent_chat_raw = value.get("recent_chat") or []

    edges = edges_raw if isinstance(edges_raw, list) else []
    port_counts = port_counts_raw if isinstance(port_counts_raw, list) else []
    recent_packets = recent_packets_raw if isinstance(recent_packets_raw, list) else []
    recent_chat = recent_chat_raw if isinstance(recent_chat_raw, list) else []

    return TrackerSnapshot(
        live_packet_count=live_packet_count,
        real_edge_count=real_edge_count,
        edges=edges,
        port_counts=port_counts,
        recent_packets=recent_packets,
        recent_chat=recent_chat,
    )
