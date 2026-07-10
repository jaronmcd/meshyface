from dataclasses import dataclass, field
from typing import Mapping, Optional

StateRow = dict[str, object]
StateSummary = dict[str, object]
StateLocal = dict[str, object]
StateHistoryCaps = dict[str, dict[str, object]]


@dataclass(frozen=True)
class StateTrafficPayload:
    edges: list[dict[str, object]]
    port_counts: list[dict[str, object]]
    recent_packets: list[dict[str, object]]
    recent_chat: list[dict[str, object]]
    node_packet_trends: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "edges": self.edges,
            "port_counts": self.port_counts,
            "recent_packets": self.recent_packets,
            "recent_chat": self.recent_chat,
            "node_packet_trends": self.node_packet_trends,
        }


@dataclass(frozen=True)
class DashboardStatePayload:
    generated_at: str
    summary: StateSummary
    summary_error: Optional[str]
    my_info: object
    my_info_error: Optional[str]
    metadata: object
    metadata_error: Optional[str]
    local_state: StateLocal
    local_state_error: Optional[str]
    nodes_error: Optional[str]
    tracker_error: Optional[str]
    tracker_saved_counts_error: Optional[str]
    tracker_capabilities_error: Optional[str]
    nodes: list[StateRow]
    history_caps: StateHistoryCaps
    nodes_full: list[StateRow]
    traffic: StateTrafficPayload
    local_node_id: str = "local"
    meshyface_profiles: dict[str, dict[str, object]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "summary": self.summary,
            "summary_error": self.summary_error,
            "my_info": self.my_info,
            "my_info_error": self.my_info_error,
            "metadata": self.metadata,
            "metadata_error": self.metadata_error,
            "local_state": self.local_state,
            "local_state_error": self.local_state_error,
            "nodes_error": self.nodes_error,
            "tracker_error": self.tracker_error,
            "tracker_saved_counts_error": self.tracker_saved_counts_error,
            "tracker_capabilities_error": self.tracker_capabilities_error,
            "nodes": self.nodes,
            "history_caps": self.history_caps,
            "nodes_full": self.nodes_full,
            "traffic": self.traffic.as_dict(),
            "local_node_id": self.local_node_id,
            "meshyface_profiles": self.meshyface_profiles,
        }


def coerce_state_traffic_payload(
    value: StateTrafficPayload | Mapping[str, object],
) -> StateTrafficPayload:
    if isinstance(value, StateTrafficPayload):
        return value
    if not isinstance(value, Mapping):
        raise TypeError(f"Expected StateTrafficPayload or mapping, got {type(value)!r}")

    edges_raw = value.get("edges") or []
    port_counts_raw = value.get("port_counts") or []
    recent_packets_raw = value.get("recent_packets") or []
    recent_chat_raw = value.get("recent_chat") or []
    node_packet_trends_raw = value.get("node_packet_trends") or {}

    edges = edges_raw if isinstance(edges_raw, list) else []
    port_counts = port_counts_raw if isinstance(port_counts_raw, list) else []
    recent_packets = recent_packets_raw if isinstance(recent_packets_raw, list) else []
    recent_chat = recent_chat_raw if isinstance(recent_chat_raw, list) else []
    node_packet_trends = node_packet_trends_raw if isinstance(node_packet_trends_raw, dict) else {}

    return StateTrafficPayload(
        edges=edges,
        port_counts=port_counts,
        recent_packets=recent_packets,
        recent_chat=recent_chat,
        node_packet_trends=node_packet_trends,
    )


def coerce_dashboard_state_payload(
    value: DashboardStatePayload | Mapping[str, object],
) -> DashboardStatePayload:
    if isinstance(value, DashboardStatePayload):
        return value
    if not isinstance(value, Mapping):
        raise TypeError(f"Expected DashboardStatePayload or mapping, got {type(value)!r}")

    return DashboardStatePayload(
        generated_at=str(value.get("generated_at") or ""),
        summary=dict(value.get("summary") or {}),
        summary_error=(str(value.get("summary_error")) if value.get("summary_error") else None),
        my_info=value.get("my_info"),
        my_info_error=(str(value.get("my_info_error")) if value.get("my_info_error") else None),
        metadata=value.get("metadata"),
        metadata_error=(str(value.get("metadata_error")) if value.get("metadata_error") else None),
        local_state=dict(value.get("local_state") or {}),
        local_state_error=(str(value.get("local_state_error")) if value.get("local_state_error") else None),
        nodes_error=(str(value.get("nodes_error")) if value.get("nodes_error") else None),
        tracker_error=(str(value.get("tracker_error")) if value.get("tracker_error") else None),
        tracker_saved_counts_error=(
            str(value.get("tracker_saved_counts_error")) if value.get("tracker_saved_counts_error") else None
        ),
        tracker_capabilities_error=(
            str(value.get("tracker_capabilities_error")) if value.get("tracker_capabilities_error") else None
        ),
        nodes=(value.get("nodes") if isinstance(value.get("nodes"), list) else []),
        history_caps=(value.get("history_caps") if isinstance(value.get("history_caps"), dict) else {}),
        nodes_full=(value.get("nodes_full") if isinstance(value.get("nodes_full"), list) else []),
        traffic=coerce_state_traffic_payload(value.get("traffic") or {}),
        local_node_id=str(value.get("local_node_id") or "local"),
        meshyface_profiles=(
            value.get("meshyface_profiles")
            if isinstance(value.get("meshyface_profiles"), dict)
            else {}
        ),
    )


def normalize_state_payload_for_api(
    value: object,
) -> object:
    if isinstance(value, DashboardStatePayload):
        return value.as_dict()
    if isinstance(value, Mapping) and (
        "generated_at" in value or "summary" in value or "traffic" in value
    ):
        return coerce_dashboard_state_payload(value).as_dict()
    return value
