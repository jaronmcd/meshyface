from __future__ import annotations

import time
from collections.abc import Iterable, Mapping
from typing import Any, Callable

from .api_input_radio import RadioSettingsRequest
from .time_sync import (
    normalize_time_sync_timezone as _normalize_time_sync_timezone_helper,
    resolve_time_sync as _resolve_time_sync_helper,
)


def _is_scalar_json(value: object) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "y", "on"}:
            return True
        if v in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


def _coerce_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(float(value.strip()))
    return int(value)  # type: ignore[arg-type]


def _coerce_float(value: object) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value.strip())
    return float(value)  # type: ignore[arg-type]


def _normalize_fixed_position_payload(payload: Mapping[str, object] | None) -> dict[str, object]:
    if not payload:
        return {}
    out: dict[str, object] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        normalized = key.strip().lower()
        if normalized in {"lat", "latitude"}:
            out["lat"] = value
        elif normalized in {"lon", "lng", "longitude"}:
            out["lon"] = value
        elif normalized in {"alt", "altitude"}:
            out["alt"] = value
    return out


def _parse_fixed_position(payload: Mapping[str, object]) -> tuple[float, float, int]:
    if "lat" not in payload or "lon" not in payload:
        raise ValueError("Fixed position requires latitude and longitude")

    lat_raw = payload.get("lat")
    lon_raw = payload.get("lon")
    alt_raw = payload.get("alt", 0)
    if isinstance(lat_raw, bool) or isinstance(lon_raw, bool) or isinstance(alt_raw, bool):
        raise ValueError("Latitude/longitude/altitude must be numeric values")

    lat = _coerce_float(lat_raw)
    lon = _coerce_float(lon_raw)
    alt = _coerce_int(alt_raw if alt_raw is not None else 0)

    if lat < -90.0 or lat > 90.0:
        raise ValueError("Latitude must be between -90 and 90")
    if lon < -180.0 or lon > 180.0:
        raise ValueError("Longitude must be between -180 and 180")
    return lat, lon, alt


def _apply_field_update(msg: Any, field_name: str, value: object) -> None:
    """Best-effort apply a field update on a protobuf message.

    We rely on protobuf descriptors for safe enum conversion.
    """

    # Protobuf messages should have a DESCRIPTOR.
    desc = getattr(msg, "DESCRIPTOR", None)
    if desc is None or not hasattr(desc, "fields_by_name"):
        # Fall back to plain setattr; might work for some wrappers.
        setattr(msg, field_name, value)
        return

    field_desc = desc.fields_by_name.get(field_name)
    if field_desc is None:
        raise ValueError(f"Unknown field '{field_name}'")

    # Repeated fields
    if getattr(field_desc, "label", None) == field_desc.LABEL_REPEATED:  # type: ignore[attr-defined]
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError(f"Field '{field_name}' expects a list")
        if not all(_is_scalar_json(v) for v in value):
            raise ValueError(f"Field '{field_name}' list contains unsupported values")
        container = getattr(msg, field_name)
        try:
            # RepeatedScalarContainer supports clear/extend
            container.clear()
        except Exception:
            # Some containers don't have clear
            del container[:]
        try:
            container.extend(value)
        except Exception:
            for v in value:
                container.append(v)
        return

    # Message fields (nested)
    if getattr(field_desc, "type", None) == field_desc.TYPE_MESSAGE:  # type: ignore[attr-defined]
        if not isinstance(value, Mapping):
            raise ValueError(f"Field '{field_name}' expects an object")
        sub = getattr(msg, field_name)
        for k, v in value.items():
            if not isinstance(k, str):
                continue
            _apply_field_update(sub, k, v)
        return

    # Enum fields
    if getattr(field_desc, "type", None) == field_desc.TYPE_ENUM:  # type: ignore[attr-defined]
        if isinstance(value, str):
            enum_value = field_desc.enum_type.values_by_name.get(value)
            if enum_value is None:
                raise ValueError(f"Invalid enum value '{value}' for field '{field_name}'")
            setattr(msg, field_name, enum_value.number)
            return
        setattr(msg, field_name, _coerce_int(value))
        return

    # Scalar types
    ftype = getattr(field_desc, "type", None)
    if ftype in {field_desc.TYPE_BOOL}:  # type: ignore[attr-defined]
        setattr(msg, field_name, _coerce_bool(value))
        return
    if ftype in {
        field_desc.TYPE_INT32,
        field_desc.TYPE_SINT32,
        field_desc.TYPE_SFIXED32,
        field_desc.TYPE_INT64,
        field_desc.TYPE_SINT64,
        field_desc.TYPE_SFIXED64,
        field_desc.TYPE_UINT32,
        field_desc.TYPE_FIXED32,
        field_desc.TYPE_UINT64,
        field_desc.TYPE_FIXED64,
    }:  # type: ignore[attr-defined]
        setattr(msg, field_name, _coerce_int(value))
        return
    if ftype in {field_desc.TYPE_FLOAT, field_desc.TYPE_DOUBLE}:  # type: ignore[attr-defined]
        setattr(msg, field_name, _coerce_float(value))
        return
    if ftype in {field_desc.TYPE_STRING}:  # type: ignore[attr-defined]
        setattr(msg, field_name, str(value))
        return

    # Fallback
    setattr(msg, field_name, value)


def _apply_updates_to_message(msg: Any, updates: Mapping[str, object]) -> tuple[list[str], list[str]]:
    applied: list[str] = []
    ignored: list[str] = []
    for key, value in updates.items():
        if not isinstance(key, str):
            continue
        if value is None:
            ignored.append(key)
            continue
        try:
            _apply_field_update(msg, key, value)
            applied.append(key)
        except Exception:
            ignored.append(key)
    return applied, ignored


def _get_local_node(iface: object) -> Any:
    node = getattr(iface, "localNode", None)
    if node is not None:
        return node
    get_node = getattr(iface, "getNode", None)
    if callable(get_node):
        return get_node("^local")
    raise RuntimeError("Interface has no local node")


def _normalize_section_updates(
    section_updates: Mapping[str, object] | None,
) -> dict[str, dict[str, object]]:
    normalized: dict[str, dict[str, object]] = {}
    if not section_updates:
        return normalized
    for section, updates in section_updates.items():
        if not isinstance(section, str):
            continue
        if isinstance(updates, Mapping):
            normalized[section] = dict(updates)
    return normalized


def _clean_owner_name(value: object) -> str:
    return str(value or "").strip()


def _object_get(value: object, key: str) -> object | None:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def _owner_names_from_object(value: object) -> tuple[str, str]:
    if value is None:
        return "", ""

    nested_user = _object_get(value, "user")
    if nested_user is not None:
        nested_short, nested_long = _owner_names_from_object(nested_user)
        if nested_short or nested_long:
            return nested_short, nested_long

    short_name = _clean_owner_name(
        _object_get(value, "short_name")
        or _object_get(value, "shortName")
    )
    long_name = _clean_owner_name(
        _object_get(value, "long_name")
        or _object_get(value, "longName")
    )
    return short_name, long_name


def _current_owner_names(node: object, iface: object) -> tuple[str, str]:
    for candidate in (
        _object_get(node, "user"),
        node,
    ):
        short_name, long_name = _owner_names_from_object(candidate)
        if short_name or long_name:
            return short_name, long_name

    node_num = _object_get(node, "nodeNum")
    nodes_by_num = getattr(iface, "nodesByNum", None)
    if isinstance(nodes_by_num, Mapping):
        info = nodes_by_num.get(node_num)
        if info is None and node_num is not None:
            info = nodes_by_num.get(str(node_num))
        short_name, long_name = _owner_names_from_object(info)
        if short_name or long_name:
            return short_name, long_name

    return "", ""


def _normalize_owner_updates(owner_updates: Mapping[str, object] | None) -> dict[str, object]:
    if not owner_updates:
        return {}
    out: dict[str, object] = {}
    if "short_name" in owner_updates:
        out["short_name"] = _clean_owner_name(owner_updates.get("short_name"))
    if "long_name" in owner_updates:
        out["long_name"] = _clean_owner_name(owner_updates.get("long_name"))
    if "is_licensed" in owner_updates:
        out["is_licensed"] = _coerce_bool(owner_updates.get("is_licensed"))
    if "is_unmessagable" in owner_updates:
        out["is_unmessagable"] = _coerce_bool(owner_updates.get("is_unmessagable"))
    return out


def _normalize_time_sync_updates(time_sync_updates: Mapping[str, object] | None) -> dict[str, object]:
    if not time_sync_updates:
        return {}

    out: dict[str, object] = {}
    if "enabled" in time_sync_updates:
        out["enabled"] = _coerce_bool(time_sync_updates.get("enabled"))
    if "server" in time_sync_updates:
        clean_server = str(time_sync_updates.get("server") or "").strip()
        if clean_server:
            out["server"] = clean_server
    if "timezone" in time_sync_updates:
        out["timezone"] = _normalize_time_sync_timezone_helper(time_sync_updates.get("timezone"))
    if "timeout_ms" in time_sync_updates:
        out["timeout_ms"] = time_sync_updates.get("timeout_ms")
    return out


def _radio_ntp_server_from_node(node: object) -> str:
    local_config = _object_get(node, "localConfig")
    network = _object_get(local_config, "network")
    server = str(
        _object_get(network, "ntp_server")
        or _object_get(network, "ntpServer")
        or ""
    ).strip()
    return server


def _set_owner_with_fallback(node: object, owner_kwargs: Mapping[str, object]) -> None:
    set_owner = getattr(node, "setOwner", None)
    if not callable(set_owner):
        raise RuntimeError("Meshtastic node does not support setOwner()")

    kwargs = dict(owner_kwargs)
    try:
        set_owner(**kwargs)
        return
    except TypeError:
        pass

    fallback_kwargs = dict(kwargs)
    fallback_kwargs.pop("is_unmessagable", None)
    try:
        set_owner(**fallback_kwargs)
        return
    except TypeError:
        pass

    set_owner(
        fallback_kwargs.get("long_name"),
        fallback_kwargs.get("short_name"),
        bool(fallback_kwargs.get("is_licensed", False)),
    )


def _best_effort_set_object_value(target: object, key: str, value: object) -> None:
    if target is None:
        return
    if isinstance(target, dict):
        try:
            target[key] = value
        except Exception:
            pass
        return
    try:
        setattr(target, key, value)
    except Exception:
        pass


def _best_effort_sync_owner_cache_record(
    record: object,
    *,
    short_name: str,
    long_name: str,
    is_licensed: object | None = None,
    is_unmessagable: object | None = None,
) -> None:
    user_target = _object_get(record, "user")
    if user_target is None:
        user_target = record

    if short_name:
        _best_effort_set_object_value(user_target, "shortName", short_name)
        _best_effort_set_object_value(user_target, "short_name", short_name)
    if long_name:
        _best_effort_set_object_value(user_target, "longName", long_name)
        _best_effort_set_object_value(user_target, "long_name", long_name)
    if is_licensed is not None:
        licensed = _coerce_bool(is_licensed)
        _best_effort_set_object_value(user_target, "isLicensed", licensed)
        _best_effort_set_object_value(user_target, "is_licensed", licensed)
    if is_unmessagable is not None:
        unmessagable = _coerce_bool(is_unmessagable)
        _best_effort_set_object_value(user_target, "isUnmessagable", unmessagable)
        _best_effort_set_object_value(user_target, "is_unmessagable", unmessagable)


def _best_effort_refresh_owner_cache(iface: object, node: object, owner_applied: Mapping[str, object]) -> None:
    short_name = _clean_owner_name(owner_applied.get("short_name"))
    long_name = _clean_owner_name(owner_applied.get("long_name"))
    is_licensed = owner_applied.get("is_licensed") if "is_licensed" in owner_applied else None
    is_unmessagable = (
        owner_applied.get("is_unmessagable") if "is_unmessagable" in owner_applied else None
    )
    if not short_name and not long_name and is_licensed is None and is_unmessagable is None:
        return

    seen_ids: set[int] = set()

    def _patch(candidate: object) -> None:
        if candidate is None:
            return
        candidate_id = id(candidate)
        if candidate_id in seen_ids:
            return
        seen_ids.add(candidate_id)
        _best_effort_sync_owner_cache_record(
            candidate,
            short_name=short_name,
            long_name=long_name,
            is_licensed=is_licensed,
            is_unmessagable=is_unmessagable,
        )

    _patch(node)
    _patch(_object_get(node, "user"))

    node_num_raw = _object_get(node, "nodeNum")
    node_num: int | None = None
    try:
        node_num = int(node_num_raw)  # type: ignore[arg-type]
    except Exception:
        node_num = None

    nodes_by_num = getattr(iface, "nodesByNum", None)
    if isinstance(nodes_by_num, Mapping):
        lookup_keys: list[object] = [node_num_raw]
        if node_num is not None:
            lookup_keys.extend([node_num, str(node_num)])
        for key in lookup_keys:
            if key is None:
                continue
            try:
                _patch(nodes_by_num.get(key))
            except Exception:
                continue

    node_user = _object_get(node, "user")
    local_id = str(_object_get(node_user, "id") or "").strip()
    if not local_id and node_num is not None and node_num >= 0:
        local_id = f"!{node_num:08x}"

    nodes = getattr(iface, "nodes", None)
    if isinstance(nodes, Mapping):
        if local_id:
            try:
                _patch(nodes.get(local_id))
            except Exception:
                pass
        for candidate in nodes.values():
            candidate_user = _object_get(candidate, "user")
            candidate_id = str(_object_get(candidate_user, "id") or "").strip()
            candidate_num_raw = _object_get(candidate, "num")
            candidate_num: int | None = None
            try:
                candidate_num = int(candidate_num_raw)  # type: ignore[arg-type]
            except Exception:
                candidate_num = None
            if local_id and candidate_id == local_id:
                _patch(candidate)
                continue
            if node_num is not None and candidate_num == node_num:
                _patch(candidate)


def _mark_tracker_state_changed(tracker: object | None) -> None:
    if tracker is None:
        return
    try:
        setattr(tracker, "radio_link_changed_unix", int(time.time()))
    except Exception:
        pass


def _dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _scope_field_ref(scope: str, section: str, field: str) -> str:
    return f"{scope}.{section}.{field}"


def _apply_scope_updates(
    *,
    scope_name: str,
    config_obj: object | None,
    updates_by_section: Mapping[str, Mapping[str, object]],
) -> tuple[dict[str, dict[str, object]], list[str], list[str], list[str]]:
    """Apply updates for local/module config sections.

    Returns:
      applied_by_section, write_sections, ignored_fields, applied_field_refs
    """

    applied_by_section: dict[str, dict[str, object]] = {}
    write_sections: list[str] = []
    ignored_fields: list[str] = []
    applied_field_refs: list[str] = []

    for section, updates in updates_by_section.items():
        section_msg = getattr(config_obj, section, None) if config_obj is not None else None
        if section_msg is None:
            for field in updates.keys():
                if isinstance(field, str):
                    ignored_fields.append(_scope_field_ref(scope_name, section, field))
            continue

        applied, ignored = _apply_updates_to_message(section_msg, updates)
        if applied:
            applied_by_section[section] = {k: updates.get(k) for k in applied}
            write_sections.append(section)
            applied_field_refs.extend(_scope_field_ref(scope_name, section, field) for field in applied)
        ignored_fields.extend(_scope_field_ref(scope_name, section, field) for field in ignored)

    return applied_by_section, write_sections, ignored_fields, applied_field_refs


def _reset_history_store(history_store: object | None) -> int:
    if history_store is None:
        raise RuntimeError("Dashboard history is not enabled")

    reset_method = getattr(history_store, "reset", None)
    if callable(reset_method):
        deleted = reset_method()
        try:
            return int(deleted)
        except Exception:
            return 0

    raise RuntimeError("Dashboard history store does not support reset()")


def _reset_tracker_runtime_view(tracker: object | None) -> None:
    if tracker is None:
        return

    lock = getattr(tracker, "_lock", None)
    use_lock = hasattr(lock, "__enter__") and hasattr(lock, "__exit__")

    def _clear_tracker() -> None:
        for attr in ("edges", "_historical_edges", "port_counts", "recent_packets", "recent_chat"):
            value = getattr(tracker, attr, None)
            clear_fn = getattr(value, "clear", None)
            if callable(clear_fn):
                clear_fn()
        if hasattr(tracker, "live_packet_count"):
            try:
                tracker.live_packet_count = 0
            except Exception:
                pass

    if use_lock:
        with lock:
            _clear_tracker()
        return

    _clear_tracker()


def _clear_iface_node_cache(iface: object | None) -> None:
    if iface is None:
        return

    for attr in ("nodesByNum", "nodes", "_nodesByNum", "_nodes"):
        value = getattr(iface, attr, None)
        clear_fn = getattr(value, "clear", None)
        if callable(clear_fn):
            try:
                clear_fn()
            except Exception:
                pass


def apply_radio_settings(
    request: RadioSettingsRequest,
    *,
    iface: object,
    send_lock: object,
    history_store: object | None = None,
    tracker: object | None = None,
    resolve_time_sync_fn: Callable[..., dict[str, object]] | None = None,
) -> dict[str, object]:
    """Apply radio settings/actions to the connected local node."""

    lora_updates = dict(request.lora or {})
    local_updates = _normalize_section_updates(request.local)
    module_updates = _normalize_section_updates(request.module)
    owner_updates = _normalize_owner_updates(request.owner)
    fixed_position_updates = _normalize_fixed_position_payload(request.fixed_position)
    time_sync_updates = _normalize_time_sync_updates(request.time_sync)
    actions = dict(request.actions or {})

    if resolve_time_sync_fn is None:
        resolve_time_sync_fn = _resolve_time_sync_helper

    # Allow clients to submit LoRa updates either in top-level "lora" (legacy)
    # or in local.lora (generic editor). Top-level lora wins on conflicts.
    local_lora_updates = local_updates.pop("lora", None)
    if local_lora_updates:
        merged_lora = dict(local_lora_updates)
        merged_lora.update(lora_updates)
        lora_updates = merged_lora

    reset_nodedb = bool(actions.get("reset_nodedb"))
    reset_dashboard_db = bool(actions.get("reset_dashboard_db"))
    set_time = bool(actions.get("set_time"))
    regenerate_node_id = bool(actions.get("regenerate_node_id"))
    set_fixed_position = bool(actions.get("set_fixed_position")) or bool(fixed_position_updates)
    clear_fixed_position = bool(actions.get("clear_fixed_position"))

    if set_fixed_position and clear_fixed_position:
        return {"ok": False, "error": "Cannot set and clear fixed position in one request"}

    fixed_position_coords: tuple[float, float, int] | None = None
    if set_fixed_position:
        try:
            fixed_position_coords = _parse_fixed_position(fixed_position_updates)
        except Exception as exc:
            return {"ok": False, "error": f"Invalid fixed position: {exc}"}

    if (
        not lora_updates
        and not local_updates
        and not module_updates
        and not owner_updates
        and not reset_nodedb
        and not reset_dashboard_db
        and not set_time
        and not regenerate_node_id
        and not set_fixed_position
        and not clear_fixed_position
    ):
        return {"ok": False, "error": "No settings/actions provided"}

    node = _get_local_node(iface)
    owner_apply_kwargs: dict[str, object] = {}
    owner_applied: dict[str, object] = {}
    owner_applied_fields: list[str] = []
    if owner_updates:
        current_short_name, current_long_name = _current_owner_names(node, iface)
        short_name = _clean_owner_name(owner_updates.get("short_name")) or current_short_name
        long_name = _clean_owner_name(owner_updates.get("long_name")) or current_long_name
        if not long_name and short_name:
            long_name = short_name
        if not short_name and long_name:
            short_name = long_name[:4]
        if not short_name and not long_name:
            return {"ok": False, "error": "Owner update requires a short or long name"}

        owner_apply_kwargs["long_name"] = long_name
        owner_apply_kwargs["short_name"] = short_name
        owner_applied["long_name"] = long_name
        owner_applied["short_name"] = short_name
        owner_applied_fields.extend(["owner.long_name", "owner.short_name"])

        if "is_licensed" in owner_updates:
            owner_apply_kwargs["is_licensed"] = _coerce_bool(owner_updates.get("is_licensed"))
            owner_applied["is_licensed"] = owner_apply_kwargs["is_licensed"]
            owner_applied_fields.append("owner.is_licensed")
        if "is_unmessagable" in owner_updates:
            owner_apply_kwargs["is_unmessagable"] = _coerce_bool(owner_updates.get("is_unmessagable"))
            owner_applied["is_unmessagable"] = owner_apply_kwargs["is_unmessagable"]
            owner_applied_fields.append("owner.is_unmessagable")

    applied: dict[str, object] = {}
    write_sections: list[str] = []
    applied_fields: list[str] = []
    ignored_fields: list[str] = []
    actions_applied: list[str] = []
    time_sync_response: dict[str, object] | None = None

    if lora_updates:
        local_config = getattr(node, "localConfig", None)
        if local_config is None:
            return {"ok": False, "error": "Local config is not available"}

        lora_cfg = getattr(local_config, "lora", None)
        if lora_cfg is None:
            return {"ok": False, "error": "LoRa config is not available"}

        lora_applied, lora_ignored = _apply_updates_to_message(lora_cfg, lora_updates)
        if lora_applied:
            write_sections.append("lora")
            applied["lora"] = {k: lora_updates.get(k) for k in lora_applied}
            applied_fields.extend(lora_applied)
        ignored_fields.extend(lora_ignored)

    if local_updates:
        local_config = getattr(node, "localConfig", None)
        local_applied, local_write_sections, local_ignored, local_applied_refs = _apply_scope_updates(
            scope_name="local",
            config_obj=local_config,
            updates_by_section=local_updates,
        )
        if local_applied:
            applied["local"] = local_applied
        write_sections.extend(local_write_sections)
        ignored_fields.extend(local_ignored)
        applied_fields.extend(local_applied_refs)

    if module_updates:
        module_config = getattr(node, "moduleConfig", None)
        module_applied, module_write_sections, module_ignored, module_applied_refs = _apply_scope_updates(
            scope_name="module",
            config_obj=module_config,
            updates_by_section=module_updates,
        )
        if module_applied:
            applied["module"] = module_applied
        write_sections.extend(module_write_sections)
        ignored_fields.extend(module_ignored)
        applied_fields.extend(module_applied_refs)

    write_sections = _dedupe_preserve_order(write_sections)
    if reset_nodedb:
        actions_applied.append("reset_nodedb")
    if reset_dashboard_db:
        actions_applied.append("reset_dashboard_db")
    if set_time:
        actions_applied.append("set_time")
    if regenerate_node_id:
        actions_applied.append("regenerate_node_id")
    if set_fixed_position:
        actions_applied.append("set_fixed_position")
    if clear_fixed_position:
        actions_applied.append("clear_fixed_position")

    if owner_applied:
        applied["owner"] = owner_applied
        applied_fields.extend(owner_applied_fields)
        actions_applied.append("set_owner")

    if not write_sections and not actions_applied:
        return {
            "ok": False,
            "error": "No valid fields/actions to apply",
            "ignored_fields": ignored_fields,
        }

    # Apply on radio. Config changes and NodeDB reset can cause transient reconnects.
    try:
        lock = send_lock
        # Best-effort support for threading.Lock-like objects.
        acquire = getattr(lock, "acquire", None)
        release = getattr(lock, "release", None)
        if callable(acquire) and callable(release):
            acquire()
            locked = True
        else:
            locked = False

        try:
            write_cfg = getattr(node, "writeConfig", None)
            if write_sections and not callable(write_cfg):
                return {"ok": False, "error": "Meshtastic node does not support writeConfig()"}

            if write_sections:
                begin_tx = getattr(node, "beginSettingsTransaction", None)
                if callable(begin_tx):
                    try:
                        begin_tx()
                    except Exception:
                        pass

                for section in write_sections:
                    write_cfg(section)

                commit_tx = getattr(node, "commitSettingsTransaction", None)
                if callable(commit_tx):
                    try:
                        commit_tx()
                    except Exception:
                        pass

            if owner_apply_kwargs:
                _set_owner_with_fallback(node, owner_apply_kwargs)
                _best_effort_refresh_owner_cache(iface, node, owner_applied)

            if set_time:
                set_time_fn = getattr(node, "setTime", None)
                if not callable(set_time_fn):
                    return {"ok": False, "error": "Meshtastic node does not support setTime()"}
                use_time_server = bool(time_sync_updates.get("enabled"))
                timezone_name = str(time_sync_updates.get("timezone") or "local")
                time_server = str(time_sync_updates.get("server") or "").strip()
                if not time_server:
                    time_server = _radio_ntp_server_from_node(node) or "pool.ntp.org"

                time_sync_response = resolve_time_sync_fn(
                    use_time_server=use_time_server,
                    server=time_server,
                    timezone_name=timezone_name,
                    timeout_ms=time_sync_updates.get("timeout_ms"),
                )
                if not bool(time_sync_response.get("ok")):
                    error_text = str(time_sync_response.get("error") or "unknown time sync error")
                    return {
                        "ok": False,
                        "error": f"Time sync failed: {error_text}",
                        "actions_applied": actions_applied,
                        "time_sync": time_sync_response,
                    }

                if use_time_server:
                    applied_unix = _coerce_int(time_sync_response.get("applied_unix") or 0)
                    if applied_unix <= 0:
                        return {
                            "ok": False,
                            "error": "Time sync failed: invalid server time returned",
                            "actions_applied": actions_applied,
                            "time_sync": time_sync_response,
                        }
                    set_time_fn(applied_unix)
                else:
                    # Keep legacy behavior: Meshtastic maps 0 -> host clock now.
                    set_time_fn(0)

            if regenerate_node_id:
                factory_reset = getattr(node, "factoryReset", None)
                if not callable(factory_reset):
                    return {"ok": False, "error": "Meshtastic node does not support factoryReset()"}
                try:
                    factory_reset(full=True)
                except TypeError:
                    factory_reset(True)

            if set_fixed_position:
                set_fixed_position_fn = getattr(node, "setFixedPosition", None)
                if not callable(set_fixed_position_fn):
                    return {"ok": False, "error": "Meshtastic node does not support setFixedPosition()"}
                if fixed_position_coords is None:
                    return {"ok": False, "error": "Invalid fixed position payload"}
                lat, lon, alt = fixed_position_coords
                set_fixed_position_fn(lat, lon, alt)

            if clear_fixed_position:
                clear_fixed_position_fn = getattr(node, "removeFixedPosition", None)
                if not callable(clear_fixed_position_fn):
                    return {"ok": False, "error": "Meshtastic node does not support removeFixedPosition()"}
                clear_fixed_position_fn()

            if reset_nodedb:
                reset_db = getattr(node, "resetNodeDb", None)
                if not callable(reset_db):
                    return {"ok": False, "error": "Meshtastic node does not support resetNodeDb()"}
                reset_db()
        finally:
            if locked:
                release()
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Write failed: {exc}",
            "applied_fields": applied_fields,
            "actions_applied": actions_applied,
        }

    deleted_history_rows: int | None = None
    reset_nodedb_cleanup_error: Exception | None = None
    if reset_nodedb:
        try:
            _clear_iface_node_cache(iface)
            _reset_tracker_runtime_view(tracker)
        except Exception as exc:
            reset_nodedb_cleanup_error = exc
    if reset_dashboard_db:
        try:
            deleted_history_rows = _reset_history_store(history_store)
            _reset_tracker_runtime_view(tracker)
        except Exception as exc:
            return {
                "ok": False,
                "error": f"Dashboard history reset failed: {exc}",
                "actions_applied": actions_applied,
            }
    if reset_nodedb_cleanup_error is not None:
        return {
            "ok": False,
            "error": f"Post-reset cleanup failed: {reset_nodedb_cleanup_error}",
            "actions_applied": actions_applied,
        }
    _mark_tracker_state_changed(tracker)

    response: dict[str, object] = {
        "ok": True,
        "applied": applied,
        "applied_fields": applied_fields,
        "ignored_fields": ignored_fields,
        "actions_applied": actions_applied,
        "write_sections": write_sections,
        "reboot_expected": bool(write_sections or reset_nodedb or regenerate_node_id),
    }
    if time_sync_response is not None:
        response["time_sync"] = time_sync_response
    if deleted_history_rows is not None:
        response["deleted_history_rows"] = deleted_history_rows
    return response
