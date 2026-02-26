from typing import Optional

from .revision import RevisionInfo
from .runtime_state_contracts import StateSnapshotRuntimeDependencies
from .runtime_state_dependencies import (
    build_state_snapshot_runtime_dependencies_from_legacy_args,
)
from .runtime_types import BuildStateFn, StateFn
from .state_service_contracts import StateTracker


def build_state_snapshot_loader(
    *,
    iface: object,
    tracker: StateTracker,
    started_at: float,
    target: str,
    show_secrets: bool,
    storage_probe_path: Optional[str],
    revision_info: RevisionInfo,
    build_state_fn: BuildStateFn,
) -> StateFn:
    dependencies = build_state_snapshot_runtime_dependencies_from_legacy_args(
        iface=iface,
        tracker=tracker,
        started_at=started_at,
        target=target,
        show_secrets=show_secrets,
        storage_probe_path=storage_probe_path,
        revision_info=revision_info,
    )
    return build_state_snapshot_loader_with_dependencies(
        dependencies=dependencies,
        build_state_fn=build_state_fn,
    )


def build_state_snapshot_loader_with_dependencies(
    *,
    dependencies: StateSnapshotRuntimeDependencies,
    build_state_fn: BuildStateFn,
) -> StateFn:
    def state_fn() -> dict:
        return build_state_fn(
            iface=dependencies.iface,
            tracker=dependencies.tracker,
            started_at=dependencies.started_at,
            target=dependencies.target,
            show_secrets=dependencies.show_secrets,
            storage_probe_path=dependencies.storage_probe_path,
            revision_info=dependencies.revision_info,
        )

    return state_fn
