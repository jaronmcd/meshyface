from typing import Optional

from .revision import RevisionInfo
from .runtime_state_contracts import StateSnapshotRuntimeDependencies
from .state_service_contracts import StateTracker


def build_state_snapshot_runtime_dependencies_from_legacy_args(
    *,
    iface: object,
    tracker: StateTracker,
    started_at: float,
    target: str,
    show_secrets: bool,
    storage_probe_path: Optional[str],
    revision_info: RevisionInfo,
) -> StateSnapshotRuntimeDependencies:
    return StateSnapshotRuntimeDependencies(
        iface=iface,
        tracker=tracker,
        started_at=started_at,
        target=target,
        show_secrets=show_secrets,
        storage_probe_path=storage_probe_path,
        revision_info=revision_info,
    )
