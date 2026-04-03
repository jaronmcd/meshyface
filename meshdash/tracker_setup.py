from collections import Counter, deque
from dataclasses import dataclass

from .file_transfer_protocol import is_file_transfer_protocol_chat_entry
from .game_protocol import is_game_protocol_chat_entry
from .tracker_bootstrap import TrackerHistoryBootstrap
from .tracker_bootstrap_contracts import TrackerBootstrapHistoryStore
from .tracker_snapshot_build_contracts import EdgeKey, EdgeRow
from .tracker_storage_contracts import RecentChatBuffer, RecentPacketBuffer
from .tracker_runtime_init_contracts import BuildHistoricalEdgesFn, LoadTrackerHistoryBootstrapFn


@dataclass
class TrackerBuffers:
    edges: dict[EdgeKey, EdgeRow]
    historical_edges: dict[EdgeKey, EdgeRow]
    port_counts: Counter[str]
    recent_packets: deque[dict[str, object]]
    recent_chat: deque[dict[str, object]]


def initialize_tracker_buffers(packet_limit: int) -> TrackerBuffers:
    return TrackerBuffers(
        edges={},
        historical_edges={},
        port_counts=Counter(),
        recent_packets=deque(maxlen=packet_limit),
        recent_chat=deque(maxlen=packet_limit),
    )


def apply_tracker_history_bootstrap(
    *,
    history_store: TrackerBootstrapHistoryStore | None,
    packet_limit: int,
    recent_packets: RecentPacketBuffer,
    recent_chat: RecentChatBuffer,
    load_tracker_history_bootstrap_fn: LoadTrackerHistoryBootstrapFn,
    build_historical_edges_fn: BuildHistoricalEdgesFn,
) -> dict[EdgeKey, EdgeRow]:
    if history_store is None:
        return {}
    bootstrap: TrackerHistoryBootstrap = load_tracker_history_bootstrap_fn(
        history_store,
        packet_limit=packet_limit,
        build_historical_edges_fn=build_historical_edges_fn,
    )
    recent_packets.extend(bootstrap.recent_packets)
    recent_chat.extend(
        row
        for row in bootstrap.recent_chat
        if not is_file_transfer_protocol_chat_entry(row) and not is_game_protocol_chat_entry(row)
    )
    return bootstrap.historical_edges
