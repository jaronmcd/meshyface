from typing import Optional

from .state_node_contracts import CollectedNodes
from .state_service_contracts import RevisionPayload, StateTracker

from .state_nodes import (
    collect_local_state as _collect_local_state_helper,
    collect_nodes as _collect_nodes_helper,
    collect_nodes_typed as _collect_nodes_typed_helper,
)
from .state_service import (
    build_dashboard_state as _build_dashboard_state_helper,
)


def collect_nodes(iface: object) -> dict[str, object]:
    return _collect_nodes_helper(iface)


def collect_nodes_typed(iface: object) -> CollectedNodes:
    return _collect_nodes_typed_helper(iface)


def collect_local_state(iface: object) -> dict[str, object]:
    return _collect_local_state_helper(iface)


def build_state(
    iface: object,
    tracker: StateTracker,
    started_at: float,
    target: str,
    show_secrets: bool,
    storage_probe_path: Optional[str],
    revision_info: RevisionPayload,
    sensitive_field_names: set[str],
) -> dict[str, object]:
    return _build_dashboard_state_helper(
        iface=iface,
        tracker=tracker,
        started_at=started_at,
        target=target,
        show_secrets=show_secrets,
        storage_probe_path=storage_probe_path,
        revision_info=revision_info,
        sensitive_field_names=sensitive_field_names,
        collect_nodes_fn=collect_nodes_typed,
        collect_local_state_fn=collect_local_state,
    )
