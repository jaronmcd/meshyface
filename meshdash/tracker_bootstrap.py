from dataclasses import dataclass

from .tracker_bootstrap_contracts import BuildHistoricalEdgesFn, TrackerBootstrapHistoryStore
from .tracker_snapshot_build_contracts import EdgeKey, EdgeRow

@dataclass(frozen=True)
class TrackerHistoryBootstrap:
    recent_packets: list[dict[str, object]]
    recent_chat: list[dict[str, object]]
    historical_edges: dict[EdgeKey, EdgeRow]


def load_tracker_history_bootstrap(
    history_store: TrackerBootstrapHistoryStore,
    *,
    packet_limit: int,
    build_historical_edges_fn: BuildHistoricalEdgesFn,
) -> TrackerHistoryBootstrap:
    recent_packets = list(history_store.load_recent_packets(packet_limit))
    recent_chat = list(history_store.load_recent_chat(packet_limit))
    historical_edges = build_historical_edges_fn(history_store.load_connections())
    return TrackerHistoryBootstrap(
        recent_packets=recent_packets,
        recent_chat=recent_chat,
        historical_edges=historical_edges,
    )
