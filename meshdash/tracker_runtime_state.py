from collections.abc import Iterable
from typing import Dict

from .helpers import (
    format_epoch as _format_epoch,
)
from .runtime_types import FormatEpochFn
from .tracker_snapshot_build_contracts import (
    ChatRow,
    BuildEdgeSnapshotRowsFn,
    EdgeKey,
    EdgeRow,
    NodeRow,
    PacketRow,
    PortCounter,
    BuildTrackerSnapshotPayloadFn,
    BuildTrackerSnapshotPayloadTypedFn,
    ExpirePendingDeliveriesFn,
    TrackerHistoryStore,
)
from .tracker_snapshot import (
    build_edge_snapshot_rows as _build_edge_snapshot_rows_helper,
    build_tracker_snapshot_payload_typed as _build_tracker_snapshot_payload_typed_helper,
    build_tracker_snapshot_payload as _build_tracker_snapshot_payload_helper,
)
from .tracker_snapshot_contracts import TrackerSnapshot, coerce_tracker_snapshot
from .tracker_runtime_types import TrackerSnapshotRuntimeState


def load_tracker_node_saved_counts(
    history_store: TrackerHistoryStore | None,
) -> Dict[str, Dict[str, object]]:
    if history_store is None:
        return {}
    return history_store.load_node_saved_counts()


def load_tracker_node_capabilities(
    history_store: TrackerHistoryStore | None,
) -> Dict[str, Dict[str, object]]:
    if history_store is None:
        return {}
    return history_store.load_node_capabilities()


def build_tracker_snapshot(
    *,
    nodes_by_id: Dict[str, NodeRow],
    expire_pending_deliveries_fn: ExpirePendingDeliveriesFn,
    session_edges: Dict[EdgeKey, EdgeRow],
    historical_edges: Dict[EdgeKey, EdgeRow],
    port_counts: PortCounter,
    recent_packets: Iterable[PacketRow],
    recent_chat: Iterable[ChatRow],
    live_packet_count: int,
    min_real_link_count: int,
    format_epoch_fn: FormatEpochFn,
    build_edge_snapshot_rows_fn: BuildEdgeSnapshotRowsFn,
    build_tracker_snapshot_payload_fn: BuildTrackerSnapshotPayloadFn,
) -> Dict[str, object]:
    expire_pending_deliveries_fn()
    return build_tracker_snapshot_payload_fn(
        session_edges=session_edges,
        historical_edges=historical_edges,
        nodes_by_id=nodes_by_id,
        port_counts=port_counts,
        recent_packets=recent_packets,
        recent_chat=recent_chat,
        live_packet_count=live_packet_count,
        min_real_link_count=min_real_link_count,
        format_epoch_fn=format_epoch_fn,
        build_edge_snapshot_rows_fn=build_edge_snapshot_rows_fn,
    )


def build_tracker_snapshot_typed(
    *,
    nodes_by_id: Dict[str, NodeRow],
    expire_pending_deliveries_fn: ExpirePendingDeliveriesFn,
    session_edges: Dict[EdgeKey, EdgeRow],
    historical_edges: Dict[EdgeKey, EdgeRow],
    port_counts: PortCounter,
    recent_packets: Iterable[PacketRow],
    recent_chat: Iterable[ChatRow],
    live_packet_count: int,
    min_real_link_count: int,
    format_epoch_fn: FormatEpochFn,
    build_edge_snapshot_rows_fn: BuildEdgeSnapshotRowsFn,
    build_tracker_snapshot_payload_typed_fn: BuildTrackerSnapshotPayloadTypedFn,
) -> TrackerSnapshot:
    expire_pending_deliveries_fn()
    return coerce_tracker_snapshot(
        build_tracker_snapshot_payload_typed_fn(
            session_edges=session_edges,
            historical_edges=historical_edges,
            nodes_by_id=nodes_by_id,
            port_counts=port_counts,
            recent_packets=recent_packets,
            recent_chat=recent_chat,
            live_packet_count=live_packet_count,
            min_real_link_count=min_real_link_count,
            format_epoch_fn=format_epoch_fn,
            build_edge_snapshot_rows_fn=build_edge_snapshot_rows_fn,
        )
    )


def load_tracker_node_saved_counts_for_tracker(
    tracker: TrackerSnapshotRuntimeState,
) -> Dict[str, Dict[str, object]]:
    return load_tracker_node_saved_counts(tracker._history_store)


def load_tracker_node_capabilities_for_tracker(
    tracker: TrackerSnapshotRuntimeState,
) -> Dict[str, Dict[str, object]]:
    return load_tracker_node_capabilities(tracker._history_store)


def build_tracker_snapshot_for_tracker(
    tracker: TrackerSnapshotRuntimeState,
    *,
    nodes_by_id: Dict[str, NodeRow],
    min_real_link_count: int,
    format_epoch_fn: FormatEpochFn = _format_epoch,
    build_edge_snapshot_rows_fn: BuildEdgeSnapshotRowsFn = _build_edge_snapshot_rows_helper,
    build_tracker_snapshot_payload_fn: BuildTrackerSnapshotPayloadFn = _build_tracker_snapshot_payload_helper,
) -> Dict[str, object]:
    return build_tracker_snapshot(
        nodes_by_id=nodes_by_id,
        expire_pending_deliveries_fn=tracker._expire_pending_deliveries_fn,
        session_edges=tracker.edges,
        historical_edges=tracker._historical_edges,
        port_counts=tracker.port_counts,
        recent_packets=tracker.recent_packets,
        recent_chat=tracker.recent_chat,
        live_packet_count=tracker.live_packet_count,
        min_real_link_count=min_real_link_count,
        format_epoch_fn=format_epoch_fn,
        build_edge_snapshot_rows_fn=build_edge_snapshot_rows_fn,
        build_tracker_snapshot_payload_fn=build_tracker_snapshot_payload_fn,
    )


def build_tracker_snapshot_for_tracker_typed(
    tracker: TrackerSnapshotRuntimeState,
    *,
    nodes_by_id: Dict[str, NodeRow],
    min_real_link_count: int,
    format_epoch_fn: FormatEpochFn = _format_epoch,
    build_edge_snapshot_rows_fn: BuildEdgeSnapshotRowsFn = _build_edge_snapshot_rows_helper,
    build_tracker_snapshot_payload_typed_fn: BuildTrackerSnapshotPayloadTypedFn = _build_tracker_snapshot_payload_typed_helper,
) -> TrackerSnapshot:
    return build_tracker_snapshot_typed(
        nodes_by_id=nodes_by_id,
        expire_pending_deliveries_fn=tracker._expire_pending_deliveries_fn,
        session_edges=tracker.edges,
        historical_edges=tracker._historical_edges,
        port_counts=tracker.port_counts,
        recent_packets=tracker.recent_packets,
        recent_chat=tracker.recent_chat,
        live_packet_count=tracker.live_packet_count,
        min_real_link_count=min_real_link_count,
        format_epoch_fn=format_epoch_fn,
        build_edge_snapshot_rows_fn=build_edge_snapshot_rows_fn,
        build_tracker_snapshot_payload_typed_fn=build_tracker_snapshot_payload_typed_fn,
    )
