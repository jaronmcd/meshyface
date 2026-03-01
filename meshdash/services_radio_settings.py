from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .api_input_radio import RadioSettingsRequest


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
) -> dict[str, object]:
    """Apply radio settings/actions to the connected local node."""

    lora_updates = dict(request.lora or {})
    local_updates = _normalize_section_updates(request.local)
    module_updates = _normalize_section_updates(request.module)
    actions = dict(request.actions or {})

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

    if (
        not lora_updates
        and not local_updates
        and not module_updates
        and not reset_nodedb
        and not reset_dashboard_db
        and not set_time
    ):
        return {"ok": False, "error": "No settings/actions provided"}

    node = _get_local_node(iface)
    applied: dict[str, object] = {}
    write_sections: list[str] = []
    applied_fields: list[str] = []
    ignored_fields: list[str] = []
    actions_applied: list[str] = []

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

            if set_time:
                set_time_fn = getattr(node, "setTime", None)
                if not callable(set_time_fn):
                    return {"ok": False, "error": "Meshtastic node does not support setTime()"}
                set_time_fn(0)

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

    response: dict[str, object] = {
        "ok": True,
        "applied": applied,
        "applied_fields": applied_fields,
        "ignored_fields": ignored_fields,
        "actions_applied": actions_applied,
        "write_sections": write_sections,
        "reboot_expected": bool(write_sections or reset_nodedb),
    }
    if deleted_history_rows is not None:
        response["deleted_history_rows"] = deleted_history_rows
    return response
