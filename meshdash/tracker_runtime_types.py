from typing import Protocol

from .runtime_types import (
    ExtractDeliveryUpdateFn,
    SetDeliveryStateFn,
)
from .tracker_snapshot_build_contracts import EdgeKey, EdgeRow, PortCounter, TrackerHistoryStore
from .tracker_storage_contracts import RecentChatBuffer, RecentPacketBuffer, TrackerHistoryWriter


class TrackerRuntimeHistoryStore(TrackerHistoryStore, TrackerHistoryWriter, Protocol):
    pass


class TrackerReceiveRuntimeState(Protocol):
    edges: dict[EdgeKey, EdgeRow]
    _historical_edges: dict[EdgeKey, EdgeRow]
    port_counts: PortCounter
    recent_packets: RecentPacketBuffer
    recent_chat: RecentChatBuffer
    _history_store: TrackerRuntimeHistoryStore | None
    _extract_delivery_update_fn: ExtractDeliveryUpdateFn
    _set_delivery_state_fn: SetDeliveryStateFn

    def _expire_pending_deliveries_fn(self) -> None:
        ...


class TrackerSnapshotRuntimeState(TrackerReceiveRuntimeState, Protocol):
    live_packet_count: int
