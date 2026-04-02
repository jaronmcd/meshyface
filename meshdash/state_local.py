from collections.abc import Mapping

from .helpers import to_jsonable


def _mapping_get(obj: object, key: str) -> object | None:
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)


def _coerce_local_node_num(*candidates: object) -> int | None:
    for candidate in candidates:
        try:
            value = int(candidate)  # type: ignore[arg-type]
        except Exception:
            continue
        if value > 0:
            return value
    return None


def _resolve_local_node_info(iface: object, local_node_num: int | None) -> object | None:
    if local_node_num is None:
        return None

    nodes_by_num = getattr(iface, "nodesByNum", None)
    if isinstance(nodes_by_num, Mapping):
        direct = nodes_by_num.get(local_node_num)
        if direct is None:
            direct = nodes_by_num.get(str(local_node_num))
        if direct is not None:
            return direct

    # Fallback for interfaces that keep node records by ID.
    nodes = getattr(iface, "nodes", None)
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


def _channel_index_from_jsonable(channel: object, *, fallback_index: int) -> int | None:
    if not isinstance(channel, Mapping):
        return None
    raw_index = channel.get("index")
    try:
        index = int(raw_index)  # type: ignore[arg-type]
    except Exception:
        index = None
    if index is not None and index >= 0:
        return index

    role_raw = str(channel.get("role") or "").strip().upper()
    if role_raw in {"PRIMARY", "CHANNEL_ROLE_PRIMARY", "1"}:
        return 0
    if fallback_index == 0:
        return 0
    return None


def _is_empty_jsonable(value: object) -> bool:
    if value is None:
        return True
    if value == "":
        return True
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _merge_channel_jsonable(existing: object, incoming: object, *, channel_index: int | None) -> object:
    if not isinstance(existing, Mapping) or not isinstance(incoming, Mapping):
        return existing if not _is_empty_jsonable(existing) else incoming

    merged = dict(existing)
    for key, value in incoming.items():
        if key == "settings" and isinstance(value, Mapping):
            current = merged.get("settings")
            if isinstance(current, Mapping):
                merged_settings = dict(current)
                for settings_key, settings_value in value.items():
                    if _is_empty_jsonable(merged_settings.get(settings_key)):
                        merged_settings[settings_key] = settings_value
                merged["settings"] = merged_settings
                continue
        if _is_empty_jsonable(merged.get(key)):
            merged[key] = value

    if channel_index is not None and _is_empty_jsonable(merged.get("index")):
        merged["index"] = channel_index
    return merged


def _dedupe_channel_list(channels: object) -> list[object]:
    if not isinstance(channels, list):
        return []

    deduped: dict[object, object] = {}
    order: list[object] = []
    unknown_counter = 0
    for fallback_index, raw_channel in enumerate(channels):
        channel = to_jsonable(raw_channel)
        channel_index = _channel_index_from_jsonable(channel, fallback_index=fallback_index)
        if channel_index is None:
            key = f"unknown:{unknown_counter}"
            unknown_counter += 1
        else:
            key = channel_index
        if key not in deduped:
            deduped[key] = channel
            order.append(key)
            continue
        deduped[key] = _merge_channel_jsonable(
            deduped[key],
            channel,
            channel_index=channel_index,
        )

    return [deduped[key] for key in order]


def collect_local_state(iface: object) -> dict[str, object]:
    local = getattr(iface, "localNode", None)
    if local is None:
        local = iface.getNode("^local")

    state: dict[str, object] = {}
    state["local_config"] = to_jsonable(getattr(local, "localConfig", None))
    state["module_config"] = to_jsonable(getattr(local, "moduleConfig", None))
    channels = getattr(local, "channels", None)
    if channels is None:
        state["channels"] = []
    else:
        state["channels"] = _dedupe_channel_list(list(channels))

    my_info = getattr(iface, "myInfo", None)
    local_node_num = _coerce_local_node_num(
        _mapping_get(local, "nodeNum"),
        _mapping_get(my_info, "my_node_num"),
        _mapping_get(my_info, "myNodeNum"),
    )
    if local_node_num is not None:
        state["local_node_num"] = local_node_num

    local_node_info = _resolve_local_node_info(iface, local_node_num)
    if local_node_info is not None:
        state["local_node_info"] = to_jsonable(local_node_info)
    local_stats = _mapping_get(local, "localStats")
    if local_stats is None:
        local_stats = _mapping_get(local, "local_stats")
    if local_stats is None and isinstance(local_node_info, Mapping):
        local_stats = local_node_info.get("localStats")
        if local_stats is None:
            local_stats = local_node_info.get("local_stats")
    if local_stats is not None:
        state["local_stats"] = to_jsonable(local_stats)

    # Capture current local position when available so the settings map can
    # restore its marker after reloads even if fixed-position coords are absent
    # from local_config.position.
    local_position = None
    if isinstance(state.get("local_node_info"), Mapping):
        local_position = state["local_node_info"].get("position")
    if local_position is None:
        local_position = _mapping_get(local, "position")
    if local_position is not None:
        state["local_position"] = to_jsonable(local_position)
    return state
