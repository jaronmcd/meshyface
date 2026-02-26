from collections.abc import Iterable
from typing import Protocol

from .runtime_types import FormatEpochFn
from .tracker_snapshot_contracts import TrackerSnapshot

EdgeKey = tuple[str, str]
EdgeRow = dict[str, object]
NodeRow = dict[str, object]
PortCountRow = dict[str, object]
PacketRow = dict[str, object]
ChatRow = dict[str, object]


class TrackerHistoryStore(Protocol):
    def load_node_saved_counts(self) -> dict[str, dict[str, object]]:
        ...

    def load_node_capabilities(self) -> dict[str, dict[str, object]]:
        ...


class PortCounter(Protocol):
    def most_common(self) -> list[tuple[str, int]]:
        ...


class ExpirePendingDeliveriesFn(Protocol):
    def __call__(self) -> None:
        ...


class BuildEdgeSnapshotRowsFn(Protocol):
    def __call__(
        self,
        *,
        session_edges: dict[EdgeKey, EdgeRow],
        historical_edges: dict[EdgeKey, EdgeRow],
        nodes_by_id: dict[str, NodeRow],
        min_real_link_count: int,
        format_epoch_fn: FormatEpochFn,
    ) -> tuple[list[EdgeRow], int]:
        ...


class BuildTrackerSnapshotPayloadTypedFn(Protocol):
    def __call__(
        self,
        *,
        session_edges: dict[EdgeKey, EdgeRow],
        historical_edges: dict[EdgeKey, EdgeRow],
        nodes_by_id: dict[str, NodeRow],
        port_counts: PortCounter,
        recent_packets: Iterable[PacketRow],
        recent_chat: Iterable[ChatRow],
        live_packet_count: int,
        min_real_link_count: int,
        format_epoch_fn: FormatEpochFn,
        build_edge_snapshot_rows_fn: BuildEdgeSnapshotRowsFn,
    ) -> TrackerSnapshot:
        ...


class BuildTrackerSnapshotPayloadFn(Protocol):
    def __call__(
        self,
        *,
        session_edges: dict[EdgeKey, EdgeRow],
        historical_edges: dict[EdgeKey, EdgeRow],
        nodes_by_id: dict[str, NodeRow],
        port_counts: PortCounter,
        recent_packets: Iterable[PacketRow],
        recent_chat: Iterable[ChatRow],
        live_packet_count: int,
        min_real_link_count: int,
        format_epoch_fn: FormatEpochFn,
        build_edge_snapshot_rows_fn: BuildEdgeSnapshotRowsFn,
    ) -> dict[str, object]:
        ...
