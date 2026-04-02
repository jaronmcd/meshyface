from collections.abc import Mapping
from typing import Optional, Protocol

from .revision import RevisionInfo
from .state_node_contracts import CollectedNodes, NodeByIdMap
from .tracker_snapshot_contracts import TrackerSnapshot

RevisionPayload = RevisionInfo | dict[str, str]


class CollectNodesFn(Protocol):
    def __call__(self, iface: object) -> CollectedNodes:
        ...


class CollectLocalStateFn(Protocol):
    def __call__(self, iface: object) -> dict[str, object]:
        ...


class CollectLocalStateSafeFn(Protocol):
    def __call__(
        self,
        iface: object,
        *,
        collect_local_state_fn: CollectLocalStateFn,
    ) -> tuple[dict[str, object], Optional[str]]:
        ...


class ModemPresetFromLocalStateFn(Protocol):
    def __call__(self, local_state: dict[str, object]) -> Optional[str]:
        ...


class ApplyNodeSavedCountsFn(Protocol):
    def __call__(
        self,
        rows: list[dict[str, object]],
        node_saved_counts: dict[str, dict[str, object]],
    ) -> None:
        ...


class BuildSummaryPayloadFn(Protocol):
    def __call__(
        self,
        *,
        target: str,
        started_at: float,
        node_rows: list[dict[str, object]],
        nodes_with_position: int,
        tracker_data: TrackerSnapshot,
        storage_probe_path: Optional[str],
        revision_info: RevisionInfo,
        modem_preset: Optional[str],
    ) -> dict[str, object]:
        ...


class GetRadioConnectionStatusFn(Protocol):
    def __call__(self, iface: object) -> Mapping[str, object] | None:
        ...


class RedactSecretsFn(Protocol):
    def __call__(self, state: object, sensitive_field_names: set[str]) -> object:
        ...


class StateTracker(Protocol):
    def snapshot(self, by_id: dict[str, dict[str, object]]) -> TrackerSnapshot:
        ...

    def load_node_saved_counts(self) -> dict[str, dict[str, object]]:
        ...

    def load_node_capabilities(self) -> dict[str, dict[str, object]]:
        ...


class LoadTrackerSnapshotSafeFn(Protocol):
    def __call__(
        self,
        tracker: StateTracker,
        nodes_by_id: NodeByIdMap,
    ) -> tuple[TrackerSnapshot, Optional[str]]:
        ...


class LoadTrackerNodeSavedCountsSafeFn(Protocol):
    def __call__(
        self,
        tracker: StateTracker,
    ) -> tuple[dict[str, dict[str, object]], Optional[str]]:
        ...


class LoadTrackerNodeCapabilitiesSafeFn(Protocol):
    def __call__(
        self,
        tracker: StateTracker,
    ) -> tuple[dict[str, dict[str, object]], Optional[str]]:
        ...
