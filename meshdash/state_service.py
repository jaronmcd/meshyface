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
from .meshyface_profile import (
    build_meshyface_theme_render as _build_meshyface_theme_render,
    normalize_meshyface_profile_node_id as _normalize_meshyface_profile_node_id,
    normalize_meshyface_theme_recipe as _normalize_meshyface_theme_recipe,
)
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
    load_tracker_node_position_counts_safe as _load_tracker_node_position_counts_safe_helper,
    load_tracker_node_saved_counts_safe as _load_tracker_node_saved_counts_safe_helper,
    load_tracker_snapshot_safe as _load_tracker_snapshot_safe_helper,
)
from .state_summary import (
    apply_node_link_counts as _apply_node_link_counts_helper,
    apply_node_historical_names as _apply_node_historical_names_helper,
    apply_node_position_counts as _apply_node_position_counts_helper,
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
# Meshtastic's LocalStats.num_online_nodes counts nodes heard in the past 2 hours.
_ONLINE_NODE_WINDOW_SECONDS = 2 * 60 * 60


def _mapping_or_attr_get(obj: object, key: str) -> object | None:
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)


def _first_positive_int(*values: object) -> Optional[int]:
    for value in values:
        int_value = _to_int(value)
        if int_value is not None and int_value > 0:
            return int(int_value)
    return None


def _coerce_optional_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "up", "connected", "online", "ok"}:
        return True
    if text in {"0", "false", "no", "off", "down", "disconnected", "offline", "lost"}:
        return False
    return None


def _coerce_positive_unix(value: object) -> int | None:
    try:
        unix_value = int(value) if value is not None else None
    except Exception:
        return None
    if unix_value is None or unix_value <= 0:
        return None
    return unix_value


def _build_radio_link_summary(*, tracker: object, target: str) -> dict[str, object]:
    connected = _coerce_optional_bool(getattr(tracker, "radio_link_connected", None))
    changed_unix = _coerce_positive_unix(getattr(tracker, "radio_link_changed_unix", None))
    reason_raw = getattr(tracker, "radio_link_error", None)
    reason = str(reason_raw).strip() if reason_raw else ""
    if connected is True:
        state = "connected"
        reason = ""
    elif connected is False:
        state = "disconnected"
    else:
        state = "unknown"

    return {
        "state": state,
        "connected": connected,
        "changed_unix": changed_unix,
        "reason": reason or None,
        "target": target,
        "source": "tracker.radio_link_connected",
    }


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


def _load_tracker_node_packet_trends_safe(
    tracker: object,
    *,
    local_node_id: str,
) -> dict[str, object]:
    load_fn = getattr(tracker, "load_node_packet_trends", None)
    if not callable(load_fn):
        return {}
    try:
        payload = load_fn(
            local_node_id=local_node_id,
            window_seconds=3600,
            bucket_count=24,
            recent_window_seconds=300,
        )
    except Exception:
        return {}
    if not isinstance(payload, Mapping):
        return {}
    return dict(payload)


def _load_meshyface_profiles_safe(tracker: object) -> dict[str, dict[str, object]]:
    load_fn = getattr(tracker, "meshyface_profiles_snapshot", None)
    try:
        raw = (
            load_fn()
            if callable(load_fn)
            else getattr(tracker, "meshyface_profiles_by_node_id", {})
        )
    except Exception:
        return {}
    if not isinstance(raw, Mapping):
        return {}

    profiles: dict[str, dict[str, object]] = {}
    for raw_node_id, raw_profile in raw.items():
        node_id = _normalize_meshyface_profile_node_id(raw_node_id)
        if not node_id or not isinstance(raw_profile, Mapping):
            continue
        updated_unix = _to_int(raw_profile.get("updated_unix"))
        if updated_unix is None or updated_unix <= 0:
            continue
        received_unix = _to_int(raw_profile.get("received_unix"))
        theme = _normalize_meshyface_theme_recipe(raw_profile.get("theme"))
        if theme is None:
            continue
        render = _build_meshyface_theme_render(theme)
        if render is None:
            continue
        profile = {
            "node_id": node_id,
            "updated_unix": int(updated_unix),
            "received_unix": max(0, int(received_unix or 0)),
            "source": "mesh",
            "theme": theme,
            "render": render,
        }
        profiles[node_id] = profile
    return profiles


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


def _online_node_count_from_stats(stats: object) -> Optional[int]:
    if stats is None:
        return None
    for key in (
        "num_online_nodes",
        "numOnlineNodes",
        "online_node_count",
        "onlineNodeCount",
    ):
        count = _to_int(_mapping_or_attr_get(stats, key))
        if count is not None:
            return max(0, int(count))
    return None


def _online_node_count_from_local_stats(local_state: object) -> Optional[int]:
    if not isinstance(local_state, Mapping):
        return None

    candidates: list[object] = [
        local_state.get("local_stats"),
        local_state.get("localStats"),
    ]
    local_node_info = local_state.get("local_node_info")
    if local_node_info is None:
        local_node_info = local_state.get("localNodeInfo")
    if isinstance(local_node_info, Mapping):
        candidates.extend(
            (
                local_node_info.get("localStats"),
                local_node_info.get("local_stats"),
            )
        )

    for stats in candidates:
        count = _online_node_count_from_stats(stats)
        if count is not None:
            return count
    return None


def _local_node_info_from_iface(iface: object) -> object | None:
    local = _mapping_or_attr_get(iface, "localNode")
    my_info = _mapping_or_attr_get(iface, "myInfo")
    local_node_num = _first_positive_int(
        _mapping_or_attr_get(local, "nodeNum"),
        _mapping_or_attr_get(my_info, "my_node_num"),
        _mapping_or_attr_get(my_info, "myNodeNum"),
    )
    if local_node_num is None:
        return None

    nodes_by_num = _mapping_or_attr_get(iface, "nodesByNum")
    if isinstance(nodes_by_num, Mapping):
        direct = nodes_by_num.get(local_node_num)
        if direct is None:
            direct = nodes_by_num.get(str(local_node_num))
        if direct is not None:
            return direct

    nodes = _mapping_or_attr_get(iface, "nodes")
    if isinstance(nodes, Mapping):
        local_id = f"!{local_node_num:08x}"
        direct = nodes.get(local_id)
        if direct is not None:
            return direct
        for value in nodes.values():
            if not isinstance(value, Mapping):
                continue
            user = value.get("user")
            if not isinstance(user, Mapping):
                continue
            if str(user.get("id") or "") == local_id:
                return value
    return None


def _online_node_count_from_iface_local_stats(iface: object) -> Optional[int]:
    local = _mapping_or_attr_get(iface, "localNode")
    my_info = _mapping_or_attr_get(iface, "myInfo")
    local_node_info = _local_node_info_from_iface(iface)
    candidates: list[object] = [
        _mapping_or_attr_get(local, "localStats"),
        _mapping_or_attr_get(local, "local_stats"),
        _mapping_or_attr_get(my_info, "localStats"),
        _mapping_or_attr_get(my_info, "local_stats"),
        _mapping_or_attr_get(local_node_info, "localStats"),
        _mapping_or_attr_get(local_node_info, "local_stats"),
    ]
    for stats in candidates:
        count = _online_node_count_from_stats(stats)
        if count is not None:
            return count
    return None


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


def _normalize_node_id_text(value: object) -> str:
    text = str(value or "").strip()
    return text if text else ""


def _slim_history_caps(
    history_caps: dict[str, dict[str, object]],
    *,
    nodes: list[dict[str, object]],
    recent_chat: list[dict[str, object]],
    recent_packets: list[dict[str, object]],
    edges: list[dict[str, object]],
    local_node_id: str,
    include_text_times: bool = True,
) -> dict[str, dict[str, object]]:
    relevant_ids: set[str] = set()

    def add_node_id(value: object) -> None:
        node_id = _normalize_node_id_text(value)
        if not node_id or node_id.startswith("^"):
            return
        relevant_ids.add(node_id)

    for row in nodes:
        if not isinstance(row, Mapping):
            continue
        add_node_id(row.get("id"))

    for entry in recent_chat:
        if not isinstance(entry, Mapping):
            continue
        add_node_id(entry.get("from"))
        add_node_id(entry.get("from_id"))
        add_node_id(entry.get("fromId"))
        add_node_id(entry.get("source"))
        add_node_id(entry.get("source_id"))
        add_node_id(entry.get("sourceId"))
        add_node_id(entry.get("to"))
        add_node_id(entry.get("to_id"))
        add_node_id(entry.get("toId"))
        add_node_id(entry.get("destination"))
        add_node_id(entry.get("dest"))
        add_node_id(entry.get("dest_id"))
        add_node_id(entry.get("destId"))

    for entry in recent_packets:
        if not isinstance(entry, Mapping):
            continue
        summary = entry.get("summary")
        packet = entry.get("packet")
        if isinstance(summary, Mapping):
            add_node_id(summary.get("from"))
            add_node_id(summary.get("from_id"))
            add_node_id(summary.get("fromId"))
            add_node_id(summary.get("to"))
            add_node_id(summary.get("to_id"))
            add_node_id(summary.get("toId"))
        if isinstance(packet, Mapping):
            add_node_id(packet.get("fromId"))
            add_node_id(packet.get("toId"))
            add_node_id(packet.get("destination"))

    for edge in edges:
        if not isinstance(edge, Mapping):
            continue
        add_node_id(edge.get("from"))
        add_node_id(edge.get("to"))

    add_node_id(local_node_id)

    slim: dict[str, dict[str, object]] = {}
    for raw_node_id, caps in history_caps.items():
        node_id = _normalize_node_id_text(raw_node_id)
        if not node_id or node_id not in relevant_ids or not isinstance(caps, Mapping):
            continue
        slim_caps: dict[str, object] = {}
        for key in (
            "first_seen_unix",
            "last_seen_unix",
            "has_position",
            "last_position_unix",
            "last_hops",
            "battery_level",
            "last_short_name",
            "last_long_name",
        ):
            value = caps.get(key)
            if value is not None:
                slim_caps[key] = value
        if include_text_times:
            for key in ("first_seen", "last_seen", "last_position_time"):
                value = caps.get(key)
                if value is not None:
                    slim_caps[key] = value
        if slim_caps:
            slim[node_id] = slim_caps
    return slim


def _slim_nodes_for_chat(nodes: list[dict[str, object]]) -> list[dict[str, object]]:
    kept_keys = (
        "air_util_tx",
        "battery_level",
        "channel_utilization",
        "hardware_model",
        "hops_away",
        "id",
        "is_favorite",
        "first_seen_unix",
        "last_heard_unix",
        "lat",
        "link_count",
        "link_packet_count",
        "lon",
        "long_name",
        "num",
        "position_last_seen_unix",
        "position_points",
        "role",
        "rssi",
        "saved_packets",
        "saved_points",
        "short_name",
        "snr",
        "voltage",
    )
    slimmed: list[dict[str, object]] = []
    for row in nodes:
        if not isinstance(row, Mapping):
            continue
        slim_row = {
            key: row.get(key)
            for key in kept_keys
            if row.get(key) is not None
        }
        if slim_row:
            slimmed.append(slim_row)
    return slimmed


def _slim_edges_for_network(edges: list[dict[str, object]]) -> list[dict[str, object]]:
    slimmed: list[dict[str, object]] = []
    for row in edges:
        if not isinstance(row, Mapping):
            continue
        slim_row: dict[str, object] = {}
        for key in (
            "from",
            "to",
            "session_count",
            "lifetime_count",
            "is_real",
            "last_hops",
            "avg_hops",
            "portnums",
            "avg_snr",
            "snr_min",
            "snr_max",
            "avg_rssi",
            "rssi_min",
            "rssi_max",
            "src_lat",
            "src_lon",
            "dst_lat",
            "dst_lon",
        ):
            value = row.get(key)
            if value is not None:
                slim_row[key] = value
        first_rx_time = row.get("first_rx_time")
        first_rx_unix = _parse_utc_text_to_unix_helper(first_rx_time)
        if first_rx_unix is not None and first_rx_unix > 0:
            slim_row["first_rx_unix"] = int(first_rx_unix)
        last_rx_time = row.get("last_rx_time")
        last_rx_unix = _parse_utc_text_to_unix_helper(last_rx_time)
        if last_rx_unix is not None and last_rx_unix > 0:
            slim_row["last_rx_unix"] = int(last_rx_unix)
        if slim_row:
            slimmed.append(slim_row)
    return slimmed


def _slim_packet_decoded(decoded: object) -> dict[str, object]:
    if not isinstance(decoded, Mapping):
        return {}
    slim: dict[str, object] = {}
    for key in (
        "portnum",
        "requestId",
        "request_id",
        "channel",
        "channelIndex",
        "channel_index",
        "text",
        "payload",
    ):
        value = decoded.get(key)
        if value is not None:
            slim[key] = value
    routing = decoded.get("routing")
    if isinstance(routing, Mapping):
        slim_routing: dict[str, object] = {}
        for key in ("requestId", "request_id"):
            value = routing.get(key)
            if value is not None:
                slim_routing[key] = value
        if slim_routing:
            slim["routing"] = slim_routing
    return slim


def _slim_packet_summary(summary: object) -> dict[str, object]:
    if not isinstance(summary, Mapping):
        return {}
    slim: dict[str, object] = {}
    for key in (
        "captured_at",
        "live",
        "packet_id",
        "message_id",
        "from",
        "to",
        "portnum",
        "rx_time",
        "rx_time_unix",
        "rx_rssi",
        "rx_snr",
        "hop_start",
        "hop_limit",
        "hops",
        "channel",
        "decoded_text",
        "reply_id",
        "emoji",
        "is_reaction",
    ):
        value = summary.get(key)
        if value is not None:
            slim[key] = value
    return slim


def _slim_recent_packets(
    recent_packets: list[dict[str, object]],
    *,
    max_packets: int = 120,
) -> list[dict[str, object]]:
    try:
        max_packets = max(0, int(max_packets))
    except Exception:
        max_packets = 120
    if max_packets <= 0:
        return []
    slimmed: list[dict[str, object]] = []
    # The tracker buffer is chronological; lite state needs the newest packet
    # frames so protocol side channels such as file-transfer/BBS snapshots can
    # complete from the current poll window.
    for entry in recent_packets[-max_packets:]:
        if not isinstance(entry, Mapping):
            continue
        slim_entry: dict[str, object] = {}
        summary = entry.get("summary")
        slim_summary = _slim_packet_summary(summary)
        if slim_summary:
            slim_entry["summary"] = slim_summary
        packet = entry.get("packet")
        if isinstance(packet, Mapping):
            slim_packet: dict[str, object] = {}
            for key in (
                "from",
                "to",
                "fromId",
                "toId",
                "destination",
                "channel",
                "channelIndex",
                "channel_index",
                "encrypted",
                "id",
                "packet_id",
                "message_id",
                "rxTime",
                "rxSnr",
                "rxRssi",
                "hopLimit",
                "hopStart",
                "relayNode",
                "transportMechanism",
                "portnum",
                "payload",
                "payload_text",
                "raw_payload",
                "rawPayload",
                "text",
            ):
                value = packet.get(key)
                if value is not None:
                    slim_packet[key] = value
            decoded = _slim_packet_decoded(packet.get("decoded"))
            if decoded:
                slim_packet["decoded"] = decoded
            if slim_packet:
                slim_entry["packet"] = slim_packet
        for key in ("captured_at", "rx_time", "time"):
            value = entry.get(key)
            if value is not None:
                slim_entry[key] = value
        if slim_entry:
            slimmed.append(slim_entry)
    return slimmed


def _slim_recent_packets_for_activity(
    recent_packets: list[dict[str, object]],
    *,
    max_packets: int = 120,
) -> list[dict[str, object]]:
    """Keep only fields needed for map activity flashes and signal-scaled pulses."""
    try:
        max_packets = max(0, int(max_packets))
    except Exception:
        max_packets = 120
    if max_packets <= 0:
        return []
    slimmed: list[dict[str, object]] = []
    for entry in recent_packets[-max_packets:]:
        if not isinstance(entry, Mapping):
            continue
        slim_entry: dict[str, object] = {}
        slim_summary = _slim_packet_summary(entry.get("summary"))
        if slim_summary:
            slim_entry["summary"] = slim_summary
        for key in ("captured_at", "rx_time", "time"):
            value = entry.get(key)
            if value is not None:
                slim_entry[key] = value
        if slim_entry:
            slimmed.append(slim_entry)
    return slimmed


def _packet_value_from_sources(entry: Mapping[str, object], keys: tuple[str, ...]) -> object:
    sources: list[object] = [
        entry,
        entry.get("summary"),
        entry.get("packet"),
    ]
    packet = entry.get("packet")
    if isinstance(packet, Mapping):
        sources.append(packet.get("decoded"))
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        for key in keys:
            value = source.get(key)
            if value is not None and value != "":
                return value
    return None


def _slim_recent_packets_for_network_graph(
    recent_packets: list[dict[str, object]],
    *,
    max_packets: int = 120,
) -> list[dict[str, object]]:
    """Keep the packet routing fields the graph uses for signal metadata."""
    try:
        max_packets = max(0, int(max_packets))
    except Exception:
        max_packets = 120
    if max_packets <= 0:
        return []
    slimmed: list[dict[str, object]] = []
    for entry in recent_packets[-max_packets:]:
        if not isinstance(entry, Mapping):
            continue
        slim_entry: dict[str, object] = {}
        for target_key, source_keys in (
            ("from", ("from", "from_id", "fromId", "source_id", "sourceId", "source", "from_num", "fromNum")),
            ("to", ("to", "to_id", "toId", "dest_id", "destId", "destination", "dest", "to_num", "toNum")),
            ("portnum", ("portnum", "portNum")),
            ("packet_id", ("packet_id", "packetId", "id", "message_id", "messageId")),
            ("rx_time_unix", ("rx_time_unix", "time_unix", "rxTime")),
        ):
            value = _packet_value_from_sources(entry, source_keys)
            if value is not None:
                slim_entry[target_key] = value
        for key in ("captured_at", "rx_time", "time"):
            value = entry.get(key)
            if value is not None:
                slim_entry[key] = value
        if slim_entry:
            slimmed.append(slim_entry)
    return slimmed


def _slim_recent_chat_for_map_activity(
    recent_chat: list[dict[str, object]],
    *,
    max_messages: int = 80,
) -> list[dict[str, object]]:
    """Keep only local send echoes needed for map self-send activity."""
    try:
        max_messages = max(0, int(max_messages))
    except Exception:
        max_messages = 80
    if max_messages <= 0:
        return []
    slimmed: list[dict[str, object]] = []
    for entry in recent_chat[-max_messages:]:
        if not isinstance(entry, Mapping):
            continue
        if entry.get("local_echo") is not True:
            continue
        slim_entry: dict[str, object] = {"local_echo": True}
        for key in (
            "from",
            "from_id",
            "fromId",
            "to",
            "to_id",
            "toId",
            "destination",
            "dest",
            "dest_id",
            "destId",
            "message_id",
            "messageId",
            "portnum",
            "channel",
            "rx_time",
            "captured_at",
            "delivery_updated_at",
            "delivery_updated_unix",
            "retry_of",
            "bot_command",
        ):
            value = entry.get(key)
            if value is not None:
                slim_entry[key] = value
        slimmed.append(slim_entry)
    return slimmed


def _slim_recent_chat_for_notifications(
    recent_chat: list[dict[str, object]],
    *,
    max_messages: int = 80,
) -> list[dict[str, object]]:
    """Keep only chat fields needed for unread/background notification tracking."""
    try:
        max_messages = max(0, int(max_messages))
    except Exception:
        max_messages = 80
    if max_messages <= 0:
        return []
    keep_keys = (
        "from",
        "from_id",
        "fromId",
        "from_name",
        "fromName",
        "source",
        "source_id",
        "sourceId",
        "to",
        "to_id",
        "toId",
        "destination",
        "dest",
        "dest_id",
        "destId",
        "message_id",
        "messageId",
        "packet_id",
        "packetId",
        "reply_id",
        "replyId",
        "portnum",
        "scope",
        "channel",
        "channel_index",
        "channelIndex",
        "rx_time",
        "captured_at",
        "time",
        "rx_time_unix",
        "time_unix",
        "delivery_updated_at",
        "delivery_updated_unix",
        "text",
        "decoded_text",
        "payload_text",
        "local_echo",
        "localEcho",
        "is_reaction",
        "isReaction",
        "emoji",
        "emoji_codepoint",
        "emojiCodepoint",
        "kind",
    )
    slimmed: list[dict[str, object]] = []
    for entry in recent_chat[-max_messages:]:
        if not isinstance(entry, Mapping):
            continue
        slim_entry: dict[str, object] = {}
        for key in keep_keys:
            value = entry.get(key)
            if value is not None:
                slim_entry[key] = value
        if slim_entry:
            slimmed.append(slim_entry)
    return slimmed


def _chat_entry_slim_merge_key(entry: object) -> str:
    if not isinstance(entry, Mapping):
        return ""
    for key in ("message_id", "messageId", "packet_id", "packetId"):
        value = _to_int(entry.get(key))
        if value is not None and value > 0:
            return f"id:{int(value)}"
    from_id = _normalize_node_id_text(
        entry.get("from")
        or entry.get("from_id")
        or entry.get("fromId")
        or entry.get("source")
        or entry.get("source_id")
        or entry.get("sourceId")
    )
    to_id = _normalize_node_id_text(
        entry.get("to")
        or entry.get("to_id")
        or entry.get("toId")
        or entry.get("destination")
        or entry.get("dest")
        or entry.get("dest_id")
        or entry.get("destId")
    )
    rx_time = str(
        entry.get("rx_time")
        or entry.get("captured_at")
        or entry.get("time")
        or entry.get("rx_time_unix")
        or entry.get("time_unix")
        or ""
    ).strip()
    text = str(
        entry.get("text")
        or entry.get("decoded_text")
        or entry.get("payload_text")
        or ""
    ).strip()
    channel = str(entry.get("channel") or entry.get("channel_index") or entry.get("channelIndex") or "").strip()
    if not from_id and not to_id and not rx_time and not text:
        return ""
    return f"sig:{from_id}|{to_id}|{rx_time}|{channel}|{text}"


def _merge_slim_recent_chat_rows(
    *row_groups: list[dict[str, object]],
) -> list[dict[str, object]]:
    merged: list[dict[str, object]] = []
    seen_keys: set[str] = set()
    for rows in row_groups:
        for entry in rows:
            if not isinstance(entry, Mapping):
                continue
            key = _chat_entry_slim_merge_key(entry)
            if key and key in seen_keys:
                continue
            if key:
                seen_keys.add(key)
            merged.append(dict(entry))
    return merged


def _slim_recent_chat_for_chat_profile(
    recent_chat: list[dict[str, object]],
) -> list[dict[str, object]]:
    def destination_implies_scope(destination: object, scope: object) -> bool:
        scope_text = str(scope or "").strip().lower()
        if not scope_text:
            return False
        destination_text = str(destination or "").strip().lower()
        if not destination_text or destination_text in {"^all", "all", "broadcast"}:
            return scope_text in {"all", "public", "broadcast", "channel"}
        return scope_text in {"direct", "dm", "private"}

    slimmed: list[dict[str, object]] = []
    for entry in recent_chat:
        if not isinstance(entry, Mapping):
            continue
        slim_entry = dict(entry)
        if slim_entry.get("delivery_updated_unix") not in (None, ""):
            slim_entry.pop("delivery_updated_at", None)
        destination = (
            slim_entry.get("to")
            or slim_entry.get("to_id")
            or slim_entry.get("toId")
            or slim_entry.get("destination")
            or slim_entry.get("dest")
            or slim_entry.get("dest_id")
            or slim_entry.get("destId")
        )
        if destination_implies_scope(destination, slim_entry.get("scope")):
            slim_entry.pop("scope", None)
        if str(slim_entry.get("portnum") or "").strip().upper() == "TEXT_MESSAGE_APP":
            slim_entry.pop("portnum", None)
        slimmed.append(slim_entry)
    return slimmed


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
    node_position_counts_raw, node_position_counts_error = _load_tracker_node_position_counts_safe_helper(tracker)
    try:
        node_position_counts = _coerce_nested_mapping_rows(
            node_position_counts_raw,
            label="node position counts",
        )
    except Exception as exc:
        node_position_counts = {}
        if node_position_counts_error is None:
            node_position_counts_error = str(exc)
    try:
        apply_node_saved_counts_fn(nodes.rows, node_saved_counts)
    except Exception as exc:
        if node_saved_counts_error is None:
            node_saved_counts_error = str(exc)
    try:
        _apply_node_position_counts_helper(nodes.rows, node_position_counts)
    except Exception as exc:
        if node_position_counts_error is None:
            node_position_counts_error = str(exc)
    try:
        _apply_node_historical_names_helper(nodes.rows, node_capabilities)
    except Exception as exc:
        if node_capabilities_error is None:
            node_capabilities_error = str(exc)
    try:
        _apply_node_link_counts_helper(nodes.rows, tracker_data.edges)
    except Exception as exc:
        if tracker_error is None:
            tracker_error = str(exc)

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
    summary_online_node_count = _online_node_count_from_local_stats(local_state)
    summary_online_node_count_source = "local_stats"
    if summary_online_node_count is None:
        summary_online_node_count = _online_node_count_from_iface_local_stats(iface)
    if summary_online_node_count is None:
        summary_online_node_count_source = "last_heard_2h"
        summary_online_node_count = _count_online_nodes(
            nodes.rows,
            now_unix=int(time.time()),
        )
    summary["online_node_count"] = max(0, int(summary_online_node_count))
    summary["online_node_count_source"] = summary_online_node_count_source
    summary["online_node_window_seconds"] = _ONLINE_NODE_WINDOW_SECONDS
    summary["radio_link"] = _build_radio_link_summary(tracker=tracker, target=target)
    if isinstance(radio_connection_status, Mapping) and radio_connection_status:
        summary["radio_connection"] = dict(radio_connection_status)
    get_zork_bot_runtime_fn = getattr(tracker, "get_zork_bot_runtime", None)
    if callable(get_zork_bot_runtime_fn):
        try:
            bots_runtime = get_zork_bot_runtime_fn()
            if isinstance(bots_runtime, Mapping):
                summary["bots"] = dict(bots_runtime)
        except Exception:
            pass
    get_file_transfer_runtime_fn = getattr(tracker, "get_file_transfer_runtime", None)
    if callable(get_file_transfer_runtime_fn):
        try:
            file_transfer_runtime = get_file_transfer_runtime_fn()
            if isinstance(file_transfer_runtime, Mapping):
                summary["file_transfer"] = dict(file_transfer_runtime)
        except Exception:
            pass

    merged_recent_chat = _merge_recent_chat_entries(
        recent_chat=tracker_data.recent_chat,
        recent_packets=tracker_data.recent_packets,
    )
    node_packet_trends = _load_tracker_node_packet_trends_safe(
        tracker,
        local_node_id=local_node_id,
    )
    meshyface_profiles = _load_meshyface_profiles_safe(tracker)
    traffic_payload = StateTrafficPayload(
        edges=tracker_data.edges,
        port_counts=tracker_data.port_counts,
        recent_packets=tracker_data.recent_packets,
        recent_chat=merged_recent_chat,
        node_packet_trends=node_packet_trends,
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
        meshyface_profiles=meshyface_profiles,
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
    profile: str = "default",
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
    profile_name = str(profile or "").strip().lower()
    if profile_name == "status":
        slim_recent_packets = []
    elif profile_name in {"network-graph", "network_graph"}:
        slim_recent_packets = _slim_recent_packets_for_network_graph(
            state_payload.traffic.recent_packets,
            max_packets=120,
        )
    elif profile_name in {"network-map", "network_map"}:
        slim_recent_packets = _slim_recent_packets_for_activity(
            state_payload.traffic.recent_packets,
            max_packets=120,
        )
    else:
        slim_recent_packets = _slim_recent_packets(
            state_payload.traffic.recent_packets,
            max_packets=120,
        )
    slim_recent_chat = list(state_payload.traffic.recent_chat)
    notification_recent_chat = _slim_recent_chat_for_notifications(slim_recent_chat)
    slim_edges = list(state_payload.traffic.edges)
    slim_port_counts = list(state_payload.traffic.port_counts)
    slim_node_packet_trends = state_payload.traffic.node_packet_trends
    slim_nodes = state_payload.nodes
    if profile_name == "chat":
        slim_nodes = _slim_nodes_for_chat(state_payload.nodes)
        slim_edges = []
        slim_recent_chat = _slim_recent_chat_for_chat_profile(slim_recent_chat)
    elif profile_name == "network":
        slim_nodes = _slim_nodes_for_chat(state_payload.nodes)
        slim_edges = _slim_edges_for_network(state_payload.traffic.edges)
        slim_recent_chat = notification_recent_chat
    elif profile_name in {"network-graph", "network_graph"}:
        slim_nodes = _slim_nodes_for_chat(state_payload.nodes)
        slim_edges = _slim_edges_for_network(state_payload.traffic.edges)
        slim_recent_chat = notification_recent_chat
        slim_port_counts = []
        slim_node_packet_trends = {}
    elif profile_name in {"network-map", "network_map"}:
        slim_nodes = _slim_nodes_for_chat(state_payload.nodes)
        slim_edges = _slim_edges_for_network(state_payload.traffic.edges)
        slim_recent_chat = _merge_slim_recent_chat_rows(
            notification_recent_chat,
            _slim_recent_chat_for_map_activity(slim_recent_chat),
        )
        slim_port_counts = []
        slim_node_packet_trends = {}
    elif profile_name in {"status", "console"}:
        slim_nodes = _slim_nodes_for_chat(state_payload.nodes)
        slim_edges = []
        slim_recent_chat = notification_recent_chat
        slim_port_counts = []
        slim_node_packet_trends = {}
    slim_history_caps = _slim_history_caps(
        state_payload.history_caps,
        nodes=slim_nodes,
        recent_chat=slim_recent_chat,
        recent_packets=slim_recent_packets,
        edges=slim_edges,
        local_node_id=state_payload.local_node_id,
        include_text_times=profile_name
        not in {
            "chat",
            "network",
            "network-graph",
            "network_graph",
            "network-map",
            "network_map",
            "status",
            "console",
        },
    )
    slim_traffic = StateTrafficPayload(
        edges=slim_edges,
        port_counts=slim_port_counts,
        recent_packets=slim_recent_packets,
        recent_chat=slim_recent_chat,
        node_packet_trends=slim_node_packet_trends,
    )
    state = DashboardStatePayload(
        generated_at=state_payload.generated_at,
        summary=state_payload.summary,
        summary_error=state_payload.summary_error,
        my_info=state_payload.my_info,
        my_info_error=state_payload.my_info_error,
        metadata=state_payload.metadata,
        metadata_error=state_payload.metadata_error,
        local_state=state_payload.local_state,
        local_state_error=state_payload.local_state_error,
        nodes_error=state_payload.nodes_error,
        tracker_error=state_payload.tracker_error,
        tracker_saved_counts_error=state_payload.tracker_saved_counts_error,
        tracker_capabilities_error=state_payload.tracker_capabilities_error,
        nodes=slim_nodes,
        history_caps=slim_history_caps,
        nodes_full=state_payload.nodes_full,
        traffic=slim_traffic,
        local_node_id=state_payload.local_node_id,
        meshyface_profiles=state_payload.meshyface_profiles,
    ).as_dict()

    if show_secrets:
        return state
    return redact_secrets_fn(state, sensitive_field_names)
