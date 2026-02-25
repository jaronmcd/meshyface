from typing import Any, Callable, Dict, Optional

from .helpers import (
    redact_secrets as _redact_secrets,
    to_jsonable as _to_jsonable,
)
from .nodes import (
    utc_now as _utc_now,
)
from .revision import RevisionInfo
from .runtime_types import ToJsonableFn, UtcNowFn
from .state_node_contracts import CollectedNodes, coerce_collected_nodes
from .state_nodes import (
    collect_local_state as _collect_local_state_helper,
    collect_nodes as _collect_nodes_helper,
)
from .state_summary import (
    apply_node_saved_counts as _apply_node_saved_counts_helper,
    build_summary_payload as _build_summary_payload_helper,
    collect_local_state_safe as _collect_local_state_safe_helper,
    modem_preset_from_local_state as _modem_preset_from_local_state_helper,
)


def build_dashboard_state(
    *,
    iface: Any,
    tracker: Any,
    started_at: float,
    target: str,
    show_secrets: bool,
    storage_probe_path: Optional[str],
    revision_info: RevisionInfo | Dict[str, str],
    sensitive_field_names: set[str],
    collect_nodes_fn: Callable[[Any], CollectedNodes | Dict[str, Any]] = _collect_nodes_helper,
    collect_local_state_fn: Callable[[Any], Dict[str, Any]] = _collect_local_state_helper,
    collect_local_state_safe_fn: Callable[..., tuple[Dict[str, Any], Optional[str]]] = _collect_local_state_safe_helper,
    modem_preset_from_local_state_fn: Callable[[Dict[str, Any]], Optional[str]] = _modem_preset_from_local_state_helper,
    apply_node_saved_counts_fn: Callable[[list[Dict[str, Any]], Dict[str, Dict[str, Any]]], None] = _apply_node_saved_counts_helper,
    build_summary_payload_fn: Callable[..., Dict[str, Any]] = _build_summary_payload_helper,
    to_jsonable_fn: ToJsonableFn = _to_jsonable,
    redact_secrets_fn: Callable[[Any, set[str]], Any] = _redact_secrets,
    utc_now_fn: UtcNowFn = _utc_now,
) -> Dict[str, Any]:
    nodes = coerce_collected_nodes(collect_nodes_fn(iface))
    tracker_data = tracker.snapshot(nodes.by_id)
    node_saved_counts = tracker.load_node_saved_counts()
    node_capabilities = tracker.load_node_capabilities()
    apply_node_saved_counts_fn(nodes.rows, node_saved_counts)

    my_info = to_jsonable_fn(getattr(iface, "myInfo", None))
    metadata = to_jsonable_fn(getattr(iface, "metadata", None))

    local_state, local_error = collect_local_state_safe_fn(
        iface,
        collect_local_state_fn=collect_local_state_fn,
    )
    modem_preset = modem_preset_from_local_state_fn(local_state)

    state = {
        "generated_at": utc_now_fn(),
        "summary": build_summary_payload_fn(
            target=target,
            started_at=started_at,
            node_rows=nodes.rows,
            nodes_with_position=nodes.with_position_count,
            tracker_data=tracker_data,
            storage_probe_path=storage_probe_path,
            revision_info=revision_info,
            modem_preset=modem_preset,
        ),
        "my_info": my_info,
        "metadata": metadata,
        "local_state": local_state,
        "local_state_error": local_error,
        "nodes": nodes.rows,
        "history_caps": node_capabilities,
        "nodes_full": nodes.full,
        "traffic": {
            "edges": tracker_data["edges"],
            "port_counts": tracker_data["port_counts"],
            "recent_packets": tracker_data["recent_packets"],
            "recent_chat": tracker_data["recent_chat"],
        },
    }

    if show_secrets:
        return state
    return redact_secrets_fn(state, sensitive_field_names)
