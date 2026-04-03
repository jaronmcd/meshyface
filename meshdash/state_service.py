import time
from collections.abc import Mapping
from typing import Dict, Optional

from .revision import RevisionInfo, coerce_revision_info
from .helpers import (
    redact_secrets as _redact_secrets,
    to_int as _to_int,
    to_jsonable as _to_jsonable,
)
from .history_node_names import build_name_change_chat_entries as _build_name_change_chat_entries_helper
from .nodes_identity import get_local_node_id as _get_local_node_id_helper
from .nodes import (
    parse_utc_text_to_unix as _parse_utc_text_to_unix_helper,
    utc_now as _utc_now,
)
from .runtime_types import ToJsonableFn, UtcNowFn
from .radio_connection_status import get_radio_connection_status as _get_radio_connection_status_helper
from .file_transfer_protocol import is_file_transfer_protocol_chat_entry as _is_file_transfer_protocol_chat_entry
from .game_protocol import is_game_protocol_chat_entry as _is_game_protocol_chat_entry
from .state_node_contracts import CollectedNodes, coerce_collected_nodes
from .state_payload_contracts import DashboardStatePayload, StateTrafficPayload
from .state_service_contracts import (
    ApplyNodeSavedCountsFn,
    BuildSummaryPayloadFn,
    CollectLocalStateFn,
    CollectLocalStateSafeFn,
    CollectNodesFn,
    GetRadioConnectionStatusFn,
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
    collect_nodes_typed as _collect_nodes_helper,
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
from .tracker_snapshot_contracts import coerce_tracker_snapshot, empty_tracker_snapshot

_MODEM_PRESET_ENUM_BY_NUMBER: dict[int, str] = {
    0: "LONG_FAST",
    1: "LONG_SLOW",
    2: "VERY_LONG_SLOW",
    3: "MEDIUM_SLOW",
    4: "MEDIUM_FAST",
    5: "SHORT_SLOW",
    6: "SHORT_FAST",
    7: "LONG_MODERATE",
    8: "SHORT_TURBO",
    9: "LONG_TURBO",
}
_MODEM_PRESET_NORMALIZED_KEYS: dict[str, str] = {
    str(name).replace("_", "").upper(): name for name in _MODEM_PRESET_ENUM_BY_NUMBER.values()
}
_ONLINE_NODE_WINDOW_SECONDS = 10 * 60


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
    revision_info: RevisionInfo,
    modem_preset: Optional[str],
) -> dict[str, object]:
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
        "revision": revision_info.as_dict(),
    }


def _coerce_nested_mapping_rows(
    value: object,
    *,
    label: str,
) -> dict[str, dict[str, object]]:
    if not isinstance(value, Mapping):
        raise TypeError(f"Expected {label} mapping")

    out: dict[str, dict[str, object]] = {}
    for key, nested in value.items():
        if isinstance(nested, Mapping):
            out[str(key)] = dict(nested)
        else:
            out[str(key)] = {}
    return out


def _tracker_radio_link_error(tracker: object) -> Optional[str]:
    # Tracker implementations may expose radio link state when available.
    connected = getattr(tracker, "radio_link_connected", None)
    if connected is not False:
        return None
    changed_raw = getattr(tracker, "radio_link_changed_unix", None)
    try:
        changed_unix = int(changed_raw) if changed_raw is not None else None
    except Exception:
        changed_unix = None
    age_text = ""
    if changed_unix is not None and changed_unix > 0:
        try:
            age_seconds = max(0, int(time.time()) - changed_unix)
            age_text = f" ({age_seconds}s)"
        except Exception:
            age_text = ""
    reason_raw = getattr(tracker, "radio_link_error", None)
    reason = str(reason_raw).strip() if reason_raw else ""
    if reason:
        return f"radio link lost{age_text}: {reason}"
    return f"radio link lost{age_text}"


def _chat_entry_sort_unix(entry: object) -> Optional[int]:
    if not isinstance(entry, Mapping):
        return None
    for value in (
        entry.get("rx_time_unix"),
        entry.get("time_unix"),
    ):
        unix_value = _to_int(value)
        if unix_value is not None and unix_value > 0:
            return int(unix_value)
    for value in (
        entry.get("rx_time"),
        entry.get("captured_at"),
        entry.get("time"),
    ):
        unix_value = _parse_utc_text_to_unix_helper(value)
        if unix_value is not None and unix_value > 0:
            return int(unix_value)
    return None


def _count_online_nodes(
    node_rows: list[dict[str, object]],
    *,
    now_unix: int,
    freshness_window_seconds: int = _ONLINE_NODE_WINDOW_SECONDS,
) -> int:
    count = 0
    for row in node_rows:
        if not isinstance(row, Mapping):
            continue
        last_seen_unix = _to_int(row.get("last_heard_unix"))
        if last_seen_unix is None:
            last_seen_unix = _to_int(row.get("last_heard_epoch"))
        if last_seen_unix is None:
            last_seen_unix = _parse_utc_text_to_unix_helper(row.get("last_heard"))
        if last_seen_unix is None or last_seen_unix <= 0:
            continue
        age_seconds = max(0, int(now_unix) - int(last_seen_unix))
        if age_seconds <= max(30, int(freshness_window_seconds)):
            count += 1
    return count


def _merge_recent_chat_entries(
    *,
    recent_chat: list[dict[str, object]],
    recent_packets: list[dict[str, object]],
) -> list[dict[str, object]]:
    filtered_recent_chat = [
        entry
        for entry in recent_chat
        if not _is_file_transfer_protocol_chat_entry(entry) and not _is_game_protocol_chat_entry(entry)
    ]
    name_change_entries = _build_name_change_chat_entries_helper(recent_packets=recent_packets)
    if not name_change_entries:
        return list(filtered_recent_chat)

    decorated_entries: list[tuple[tuple[int, int, int], dict[str, object]]] = []
    for order, entry in enumerate(filtered_recent_chat):
        sort_unix = _chat_entry_sort_unix(entry)
        sort_key = (1 if sort_unix is None else 0, 0 if sort_unix is None else int(sort_unix), order)
        decorated_entries.append((sort_key, entry))

    base_order = len(decorated_entries)
    for offset, entry in enumerate(name_change_entries):
        sort_unix = _chat_entry_sort_unix(entry)
        sort_key = (1 if sort_unix is None else 0, 0 if sort_unix is None else int(sort_unix), base_order + offset)
        decorated_entries.append((sort_key, entry))

    decorated_entries.sort(key=lambda item: item[0])
    return [entry for _, entry in decorated_entries]


def _normalize_modem_preset(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            number = int(value)
        except Exception:
            number = None
        if number is not None:
            mapped = _MODEM_PRESET_ENUM_BY_NUMBER.get(number)
            if mapped:
                return mapped
            return str(number)

    text = str(value or "").strip()
    if not text:
        return None
    numeric_text = text
    if numeric_text.startswith("+"):
        numeric_text = numeric_text[1:]
    if numeric_text.isdigit():
        mapped = _MODEM_PRESET_ENUM_BY_NUMBER.get(int(numeric_text))
        if mapped:
            return mapped
        return numeric_text
    upper = text.upper()
    upper = upper.split(".")[-1]
    upper = upper.replace("MODEMPRESET_", "")
    upper = upper.replace("CONFIG_LORACONFIG_MODEMPRESET_", "")
    upper = upper.replace("-", "_").replace(" ", "_")
    if upper in _MODEM_PRESET_ENUM_BY_NUMBER.values():
        return upper
    collapsed = upper.replace("_", "")
    mapped = _MODEM_PRESET_NORMALIZED_KEYS.get(collapsed)
    if mapped:
        return mapped
    return text


def _modem_preset_from_local_config(local_config: object) -> Optional[str]:
    if not isinstance(local_config, Mapping):
        return None
    lora = local_config.get("lora")
    if isinstance(lora, Mapping):
        return _normalize_modem_preset(lora.get("modem_preset"))
    return None


def _modem_preset_quick_from_iface(iface: object) -> Optional[str]:
    """Best-effort lightweight modem preset lookup for lite polling."""
    local = getattr(iface, "localNode", None)
    if local is None:
        get_node = getattr(iface, "getNode", None)
        if callable(get_node):
            try:
                local = get_node("^local")
            except Exception:
                local = None
    if local is None:
        return None

    local_config = getattr(local, "localConfig", None)
    from_mapping = _modem_preset_from_local_config(local_config)
    if from_mapping:
        return from_mapping

    lora = getattr(local_config, "lora", None)
    if isinstance(lora, Mapping):
        preset = _normalize_modem_preset(lora.get("modem_preset"))
        if preset:
            return preset
    elif lora is not None:
        preset = _normalize_modem_preset(getattr(lora, "modem_preset", None))
        if preset:
            return preset

    if isinstance(local, Mapping):
        return _modem_preset_from_local_config(local.get("local_config"))
    return None


def build_dashboard_state_typed(
    *,
    iface: object,
    tracker: StateTracker,
    target: str,
    started_at: float,
    storage_probe_path: Optional[str],
    revision_info: RevisionInfo,
    collect_nodes_fn: CollectNodesFn = _collect_nodes_helper,
    collect_local_state_fn: CollectLocalStateFn = _collect_local_state_helper,
    collect_local_state_safe_fn: CollectLocalStateSafeFn = _collect_local_state_safe_helper,
    modem_preset_from_local_state_fn: ModemPresetFromLocalStateFn = _modem_preset_from_local_state_helper,
    apply_node_saved_counts_fn: ApplyNodeSavedCountsFn = _apply_node_saved_counts_helper,
    build_summary_payload_fn: BuildSummaryPayloadFn = _build_summary_payload_helper,
    get_radio_connection_status_fn: GetRadioConnectionStatusFn = _get_radio_connection_status_helper,
    load_tracker_snapshot_safe_fn: LoadTrackerSnapshotSafeFn = _load_tracker_snapshot_safe_helper,
    load_tracker_node_saved_counts_safe_fn: LoadTrackerNodeSavedCountsSafeFn = _load_tracker_node_saved_counts_safe_helper,
    load_tracker_node_capabilities_safe_fn: LoadTrackerNodeCapabilitiesSafeFn = _load_tracker_node_capabilities_safe_helper,
    to_jsonable_fn: ToJsonableFn = _to_jsonable,
    utc_now_fn: UtcNowFn = _utc_now,
    include_debug: bool = True,
    include_nodes_full: bool = True,
) -> DashboardStatePayload:
    local_node_id = "local"
    try:
        local_node_id = str(
            _get_local_node_id_helper(
                iface,
                broadcast_num=None,
                to_jsonable_fn=to_jsonable_fn,
            )
        )
    except Exception:
        local_node_id = "local"

    nodes_error: Optional[str] = None
    try:
        nodes = coerce_collected_nodes(collect_nodes_fn(iface))
    except Exception as exc:
        nodes = CollectedNodes(rows=[], full=[], by_id={}, with_position_count=0)
        nodes_error = str(exc)

    if not include_nodes_full and nodes.full:
        nodes = CollectedNodes(
            rows=nodes.rows,
            full=[],
            by_id=nodes.by_id,
            with_position_count=nodes.with_position_count,
        )
    tracker_data_raw, tracker_error = load_tracker_snapshot_safe_fn(tracker, nodes.by_id)
    try:
        tracker_data = coerce_tracker_snapshot(tracker_data_raw)
    except Exception as exc:
        tracker_data = empty_tracker_snapshot()
        if tracker_error is None:
            tracker_error = str(exc)
    radio_link_error = _tracker_radio_link_error(tracker)
    if radio_link_error:
        tracker_error = f"{tracker_error} | {radio_link_error}" if tracker_error else radio_link_error

    node_saved_counts_raw, node_saved_counts_error = load_tracker_node_saved_counts_safe_fn(tracker)
    try:
        node_saved_counts = _coerce_nested_mapping_rows(
            node_saved_counts_raw,
            label="node saved counts",
        )
    except Exception as exc:
        node_saved_counts = {}
        if node_saved_counts_error is None:
            node_saved_counts_error = str(exc)

    node_capabilities_raw, node_capabilities_error = load_tracker_node_capabilities_safe_fn(tracker)
    try:
        node_capabilities = _coerce_nested_mapping_rows(
            node_capabilities_raw,
            label="node capabilities",
        )
    except Exception as exc:
        node_capabilities = {}
        if node_capabilities_error is None:
            node_capabilities_error = str(exc)
    try:
        apply_node_saved_counts_fn(nodes.rows, node_saved_counts)
    except Exception as exc:
        if node_saved_counts_error is None:
            node_saved_counts_error = str(exc)

    if include_debug:
        my_info, my_info_error = _to_jsonable_safe(
            getattr(iface, "myInfo", None),
            to_jsonable_fn=to_jsonable_fn,
        )
        metadata, metadata_error = _to_jsonable_safe(
            getattr(iface, "metadata", None),
            to_jsonable_fn=to_jsonable_fn,
        )

        local_error: Optional[str]
        try:
            local_state, local_error = collect_local_state_safe_fn(
                iface,
                collect_local_state_fn=collect_local_state_fn,
            )
        except Exception as exc:
            local_state, local_error = {}, str(exc)

        if not isinstance(local_state, Mapping):
            local_state = {}
            if local_error is None:
                local_error = "Expected local_state mapping from collect_local_state_safe_fn"
        elif not isinstance(local_state, dict):
            local_state = dict(local_state)

        modem_preset: Optional[str]
        try:
            modem_preset = modem_preset_from_local_state_fn(local_state)
        except Exception as exc:
            modem_preset = None
            if local_error is None:
                local_error = str(exc)
    else:
        my_info, my_info_error = None, None
        metadata, metadata_error = None, None
        local_state, local_error = {}, None
        modem_preset = _modem_preset_quick_from_iface(iface)

    radio_connection_status: dict[str, object] | None = None
    try:
        radio_connection_status_raw = get_radio_connection_status_fn(iface)
        if isinstance(radio_connection_status_raw, Mapping):
            radio_connection_status = dict(radio_connection_status_raw)
    except Exception:
        radio_connection_status = None

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
        if not isinstance(summary, Mapping):
            raise TypeError("Expected summary payload mapping from build_summary_payload_fn")
        if not isinstance(summary, dict):
            summary = dict(summary)
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

    # Keep radio and DB-known node counts explicit in the summary payload.
    summary_saved_node_count = _to_int(summary.get("saved_node_count"))
    if summary_saved_node_count is None:
        summary_saved_node_count = len(node_saved_counts)
    summary["saved_node_count"] = max(0, int(summary_saved_node_count))
    summary_online_node_count = _to_int(summary.get("online_node_count"))
    if summary_online_node_count is None:
        summary_online_node_count = _count_online_nodes(
            nodes.rows,
            now_unix=int(time.time()),
        )
    summary["online_node_count"] = max(0, int(summary_online_node_count))
    if isinstance(radio_connection_status, Mapping) and radio_connection_status:
        summary["radio_connection"] = dict(radio_connection_status)

    merged_recent_chat = _merge_recent_chat_entries(
        recent_chat=tracker_data.recent_chat,
        recent_packets=tracker_data.recent_packets,
    )
    traffic_payload = StateTrafficPayload(
        edges=tracker_data.edges,
        port_counts=tracker_data.port_counts,
        recent_packets=tracker_data.recent_packets,
        recent_chat=merged_recent_chat,
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
        local_node_id=local_node_id,
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
    get_radio_connection_status_fn: GetRadioConnectionStatusFn = _get_radio_connection_status_helper,
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
        revision_info=coerce_revision_info(revision_info),
        collect_nodes_fn=collect_nodes_fn,
        collect_local_state_fn=collect_local_state_fn,
        collect_local_state_safe_fn=collect_local_state_safe_fn,
        modem_preset_from_local_state_fn=modem_preset_from_local_state_fn,
        apply_node_saved_counts_fn=apply_node_saved_counts_fn,
        build_summary_payload_fn=build_summary_payload_fn,
        get_radio_connection_status_fn=get_radio_connection_status_fn,
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


def build_dashboard_state_lite(
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
    get_radio_connection_status_fn: GetRadioConnectionStatusFn = _get_radio_connection_status_helper,
    load_tracker_snapshot_safe_fn: LoadTrackerSnapshotSafeFn = _load_tracker_snapshot_safe_helper,
    load_tracker_node_saved_counts_safe_fn: LoadTrackerNodeSavedCountsSafeFn = _load_tracker_node_saved_counts_safe_helper,
    load_tracker_node_capabilities_safe_fn: LoadTrackerNodeCapabilitiesSafeFn = _load_tracker_node_capabilities_safe_helper,
    to_jsonable_fn: ToJsonableFn = _to_jsonable,
    redact_secrets_fn: RedactSecretsFn = _redact_secrets,
    utc_now_fn: UtcNowFn = _utc_now,
) -> Dict[str, object]:
    """Build a slimmed-down state snapshot optimized for UI polling.

    This skips expensive raw/debug fields (myInfo/metadata/local_state) and can
    also be paired with a nodes collector that avoids building the full node
    payload list.
    """
    state_payload = build_dashboard_state_typed(
        iface=iface,
        tracker=tracker,
        target=target,
        started_at=started_at,
        storage_probe_path=storage_probe_path,
        revision_info=coerce_revision_info(revision_info),
        collect_nodes_fn=collect_nodes_fn,
        collect_local_state_fn=collect_local_state_fn,
        collect_local_state_safe_fn=collect_local_state_safe_fn,
        modem_preset_from_local_state_fn=modem_preset_from_local_state_fn,
        apply_node_saved_counts_fn=apply_node_saved_counts_fn,
        build_summary_payload_fn=build_summary_payload_fn,
        get_radio_connection_status_fn=get_radio_connection_status_fn,
        load_tracker_snapshot_safe_fn=load_tracker_snapshot_safe_fn,
        load_tracker_node_saved_counts_safe_fn=load_tracker_node_saved_counts_safe_fn,
        load_tracker_node_capabilities_safe_fn=load_tracker_node_capabilities_safe_fn,
        to_jsonable_fn=to_jsonable_fn,
        utc_now_fn=utc_now_fn,
        include_debug=False,
        include_nodes_full=False,
    )
    state = state_payload.as_dict()

    if show_secrets:
        return state
    return redact_secrets_fn(state, sensitive_field_names)
