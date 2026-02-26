from typing import Dict, Optional

from .revision import RevisionInfo
from .helpers import (
    redact_secrets as _redact_secrets,
    to_jsonable as _to_jsonable,
)
from .nodes import (
    utc_now as _utc_now,
)
from .runtime_types import ToJsonableFn, UtcNowFn
from .state_node_contracts import CollectedNodes, coerce_collected_nodes
from .state_payload_contracts import DashboardStatePayload, StateTrafficPayload
from .state_service_contracts import (
    ApplyNodeSavedCountsFn,
    BuildSummaryPayloadFn,
    CollectLocalStateFn,
    CollectLocalStateSafeFn,
    CollectNodesFn,
    LoadTrackerNodeCapabilitiesSafeFn,
    LoadTrackerNodeSavedCountsSafeFn,
    LoadTrackerSnapshotSafeFn,
    ModemPresetFromLocalStateFn,
    RedactSecretsFn,
    RevisionPayload,
    StateTracker,
)
from .state_nodes import (
    collect_local_state as _collect_local_state_helper,
    collect_nodes as _collect_nodes_helper,
)
from .state_tracker import (
    load_tracker_node_capabilities_safe as _load_tracker_node_capabilities_safe_helper,
    load_tracker_node_saved_counts_safe as _load_tracker_node_saved_counts_safe_helper,
    load_tracker_snapshot_safe as _load_tracker_snapshot_safe_helper,
)
from .state_summary import (
    apply_node_saved_counts as _apply_node_saved_counts_helper,
    build_summary_payload as _build_summary_payload_helper,
    collect_local_state_safe as _collect_local_state_safe_helper,
    modem_preset_from_local_state as _modem_preset_from_local_state_helper,
)


def _to_jsonable_safe(
    value: object,
    *,
    to_jsonable_fn: ToJsonableFn,
) -> tuple[object, Optional[str]]:
    try:
        return to_jsonable_fn(value), None
    except Exception as exc:
        return None, str(exc)


def _build_summary_payload_fallback(
    *,
    target: str,
    node_rows: list[dict[str, object]],
    nodes_with_position: int,
    tracker_data: object,
    revision_info: RevisionPayload,
    modem_preset: Optional[str],
) -> dict[str, object]:
    if isinstance(revision_info, RevisionInfo):
        revision_payload = revision_info.as_dict()
    else:
        revision_payload = dict(revision_info)

    return {
        "target": target,
        "uptime_seconds": 0,
        "node_count": len(node_rows),
        "nodes_with_position": nodes_with_position,
        "live_packet_count": int(tracker_data.live_packet_count),
        "edge_count": len(tracker_data.edges),
        "real_edge_count": int(tracker_data.real_edge_count),
        "recent_packet_buffer": len(tracker_data.recent_packets),
        "modem_preset": modem_preset,
        "disk": {"free_percent": "n/a"},
        "revision": revision_payload,
    }


def build_dashboard_state_typed(
    *,
    iface: object,
    tracker: StateTracker,
    target: str,
    started_at: float,
    storage_probe_path: Optional[str],
    revision_info: RevisionPayload,
    collect_nodes_fn: CollectNodesFn = _collect_nodes_helper,
    collect_local_state_fn: CollectLocalStateFn = _collect_local_state_helper,
    collect_local_state_safe_fn: CollectLocalStateSafeFn = _collect_local_state_safe_helper,
    modem_preset_from_local_state_fn: ModemPresetFromLocalStateFn = _modem_preset_from_local_state_helper,
    apply_node_saved_counts_fn: ApplyNodeSavedCountsFn = _apply_node_saved_counts_helper,
    build_summary_payload_fn: BuildSummaryPayloadFn = _build_summary_payload_helper,
    load_tracker_snapshot_safe_fn: LoadTrackerSnapshotSafeFn = _load_tracker_snapshot_safe_helper,
    load_tracker_node_saved_counts_safe_fn: LoadTrackerNodeSavedCountsSafeFn = _load_tracker_node_saved_counts_safe_helper,
    load_tracker_node_capabilities_safe_fn: LoadTrackerNodeCapabilitiesSafeFn = _load_tracker_node_capabilities_safe_helper,
    to_jsonable_fn: ToJsonableFn = _to_jsonable,
    utc_now_fn: UtcNowFn = _utc_now,
) -> DashboardStatePayload:
    nodes_error: Optional[str] = None
    try:
        nodes = coerce_collected_nodes(collect_nodes_fn(iface))
    except Exception as exc:
        nodes = CollectedNodes(rows=[], full=[], by_id={}, with_position_count=0)
        nodes_error = str(exc)
    tracker_data, tracker_error = load_tracker_snapshot_safe_fn(tracker, nodes.by_id)
    node_saved_counts, node_saved_counts_error = load_tracker_node_saved_counts_safe_fn(tracker)
    node_capabilities, node_capabilities_error = load_tracker_node_capabilities_safe_fn(tracker)
    apply_node_saved_counts_fn(nodes.rows, node_saved_counts)

    my_info, my_info_error = _to_jsonable_safe(
        getattr(iface, "myInfo", None),
        to_jsonable_fn=to_jsonable_fn,
    )
    metadata, metadata_error = _to_jsonable_safe(
        getattr(iface, "metadata", None),
        to_jsonable_fn=to_jsonable_fn,
    )

    local_state, local_error = collect_local_state_safe_fn(
        iface,
        collect_local_state_fn=collect_local_state_fn,
    )
    modem_preset = modem_preset_from_local_state_fn(local_state)
    summary_error: Optional[str] = None
    try:
        summary = build_summary_payload_fn(
            target=target,
            started_at=started_at,
            node_rows=nodes.rows,
            nodes_with_position=nodes.with_position_count,
            tracker_data=tracker_data,
            storage_probe_path=storage_probe_path,
            revision_info=revision_info,
            modem_preset=modem_preset,
        )
    except Exception as exc:
        summary_error = str(exc)
        summary = _build_summary_payload_fallback(
            target=target,
            node_rows=nodes.rows,
            nodes_with_position=nodes.with_position_count,
            tracker_data=tracker_data,
            revision_info=revision_info,
            modem_preset=modem_preset,
        )

    traffic_payload = StateTrafficPayload(
        edges=tracker_data.edges,
        port_counts=tracker_data.port_counts,
        recent_packets=tracker_data.recent_packets,
        recent_chat=tracker_data.recent_chat,
    )
    state_payload = DashboardStatePayload(
        generated_at=utc_now_fn(),
        summary=summary,
        summary_error=summary_error,
        my_info=my_info,
        my_info_error=my_info_error,
        metadata=metadata,
        metadata_error=metadata_error,
        local_state=local_state,
        local_state_error=local_error,
        nodes_error=nodes_error,
        tracker_error=tracker_error,
        tracker_saved_counts_error=node_saved_counts_error,
        tracker_capabilities_error=node_capabilities_error,
        nodes=nodes.rows,
        history_caps=node_capabilities,
        nodes_full=nodes.full,
        traffic=traffic_payload,
    )
    return state_payload


def build_dashboard_state(
    *,
    iface: object,
    tracker: StateTracker,
    started_at: float,
    target: str,
    show_secrets: bool,
    storage_probe_path: Optional[str],
    revision_info: RevisionPayload,
    sensitive_field_names: set[str],
    collect_nodes_fn: CollectNodesFn = _collect_nodes_helper,
    collect_local_state_fn: CollectLocalStateFn = _collect_local_state_helper,
    collect_local_state_safe_fn: CollectLocalStateSafeFn = _collect_local_state_safe_helper,
    modem_preset_from_local_state_fn: ModemPresetFromLocalStateFn = _modem_preset_from_local_state_helper,
    apply_node_saved_counts_fn: ApplyNodeSavedCountsFn = _apply_node_saved_counts_helper,
    build_summary_payload_fn: BuildSummaryPayloadFn = _build_summary_payload_helper,
    load_tracker_snapshot_safe_fn: LoadTrackerSnapshotSafeFn = _load_tracker_snapshot_safe_helper,
    load_tracker_node_saved_counts_safe_fn: LoadTrackerNodeSavedCountsSafeFn = _load_tracker_node_saved_counts_safe_helper,
    load_tracker_node_capabilities_safe_fn: LoadTrackerNodeCapabilitiesSafeFn = _load_tracker_node_capabilities_safe_helper,
    to_jsonable_fn: ToJsonableFn = _to_jsonable,
    redact_secrets_fn: RedactSecretsFn = _redact_secrets,
    utc_now_fn: UtcNowFn = _utc_now,
) -> Dict[str, object]:
    state_payload = build_dashboard_state_typed(
        iface=iface,
        tracker=tracker,
        target=target,
        started_at=started_at,
        storage_probe_path=storage_probe_path,
        revision_info=revision_info,
        collect_nodes_fn=collect_nodes_fn,
        collect_local_state_fn=collect_local_state_fn,
        collect_local_state_safe_fn=collect_local_state_safe_fn,
        modem_preset_from_local_state_fn=modem_preset_from_local_state_fn,
        apply_node_saved_counts_fn=apply_node_saved_counts_fn,
        build_summary_payload_fn=build_summary_payload_fn,
        load_tracker_snapshot_safe_fn=load_tracker_snapshot_safe_fn,
        load_tracker_node_saved_counts_safe_fn=load_tracker_node_saved_counts_safe_fn,
        load_tracker_node_capabilities_safe_fn=load_tracker_node_capabilities_safe_fn,
        to_jsonable_fn=to_jsonable_fn,
        utc_now_fn=utc_now_fn,
    )
    state = state_payload.as_dict()

    if show_secrets:
        return state
    return redact_secrets_fn(state, sensitive_field_names)
