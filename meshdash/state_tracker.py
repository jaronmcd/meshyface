from typing import Optional

from .state_node_contracts import NodeByIdMap
from .state_service_contracts import StateTracker
from .tracker_snapshot_contracts import (
    TrackerSnapshot,
    coerce_tracker_snapshot,
    empty_tracker_snapshot,
)


def load_tracker_snapshot_safe(
    tracker: StateTracker,
    nodes_by_id: NodeByIdMap,
) -> tuple[TrackerSnapshot, Optional[str]]:
    try:
        snapshot_typed_fn = getattr(tracker, "snapshot_typed", None)
        if callable(snapshot_typed_fn):
            return coerce_tracker_snapshot(snapshot_typed_fn(nodes_by_id)), None
        return coerce_tracker_snapshot(tracker.snapshot(nodes_by_id)), None
    except Exception as exc:
        return empty_tracker_snapshot(), str(exc)


def load_tracker_node_saved_counts_safe(
    tracker: StateTracker,
) -> tuple[dict[str, dict[str, object]], Optional[str]]:
    try:
        return tracker.load_node_saved_counts(), None
    except Exception as exc:
        return {}, str(exc)


def load_tracker_node_capabilities_safe(
    tracker: StateTracker,
) -> tuple[dict[str, dict[str, object]], Optional[str]]:
    try:
        return tracker.load_node_capabilities(), None
    except Exception as exc:
        return {}, str(exc)
