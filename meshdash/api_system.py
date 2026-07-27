import re
from collections.abc import Mapping
from urllib.parse import parse_qs

from .http_handler_contracts import DashboardHttpHandler
from .http_route_contracts import StateFn, WriteJsonResponseFn
from .http_responses import _send_no_store_headers
from .offline_atlas import nearest_city as _nearest_city
from .state_payload_contracts import normalize_state_payload_for_api

_PUBLIC_PLUGIN_COMMAND_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
_PUBLIC_PLUGIN_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
_PUBLIC_PLUGIN_VIEW_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
_PUBLIC_PLUGIN_VIEW_ICON_RE = re.compile(r"[A-Z0-9]{1,4}\Z")
_PUBLIC_PLUGIN_NODE_FIELD_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
_PUBLIC_NODE_ID_RE = re.compile(r"![0-9a-f]{8}\Z")
_NODE_LIST_MIRROR_FIELD_ORDER = (
    "id",
    "snr",
    "hardware",
    "battery",
    "hops",
    "last_heard",
    "links",
    "saved",
    "pos",
    "location_points",
    "city",
)
_NODE_LIST_MIRROR_FIELD_IDS = frozenset(_NODE_LIST_MIRROR_FIELD_ORDER)


def _first_present(row: Mapping[str, object], *keys: str) -> object | None:
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    return None


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _float_or_none(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value) if value is not None else None
    except (TypeError, ValueError, OverflowError):
        return None
    if number is None or number != number:
        return None
    if number in (float("inf"), float("-inf")):
        return None
    return number


def _timestamp_or_none(value: object) -> int | None:
    number = _int_or_none(value)
    if number is None or number <= 0:
        return None
    return number


def _node_location(row: Mapping[str, object]) -> tuple[float, float] | None:
    position = row.get("position")
    if isinstance(position, Mapping):
        lat = _float_or_none(_first_present(position, "latitude", "lat"))
        lon = _float_or_none(_first_present(position, "longitude", "lon"))
    else:
        lat = _float_or_none(_first_present(row, "latitude", "lat"))
        lon = _float_or_none(_first_present(row, "longitude", "lon"))
    if lat is None or lon is None:
        return None
    if lat < -90.0 or lat > 90.0 or lon < -180.0 or lon > 180.0:
        return None
    if abs(lat) < 1e-9 and abs(lon) < 1e-9:
        return None
    return lat, lon


def _node_list_city_value(
    location: tuple[float, float] | None,
    city_cache: dict[tuple[float, float], dict[str, object] | None],
) -> tuple[object, object | None, str]:
    if location is None:
        return "n/a", None, "City: n/a"
    cache_key = (round(location[0], 5), round(location[1], 5))
    if cache_key not in city_cache:
        city_cache[cache_key] = _nearest_city(location[0], location[1])
    city = city_cache.get(cache_key)
    if not isinstance(city, Mapping):
        return "n/a", None, "City: n/a"
    name = str(city.get("name") or "").strip()
    if not name:
        return "n/a", None, "City: n/a"
    admin = str(city.get("state") or city.get("admin1") or city.get("adm1name") or "").strip()
    country = str(city.get("country") or city.get("adm0name") or "").strip()
    value = f"{name}, {admin}" if admin else (f"{name}, {country}" if country else name)
    return value, value.casefold(), value


def _node_list_mirror_field_value(
    row: Mapping[str, object],
    field_id: str,
    *,
    runtime_status: str,
    city_cache: dict[tuple[float, float], dict[str, object] | None],
) -> dict[str, object] | None:
    node_id = str(row.get("id") or "").strip().lower()
    if _PUBLIC_NODE_ID_RE.fullmatch(node_id) is None:
        return None

    value: object
    sort: object | None
    title: str
    if field_id == "id":
        value, sort, title = node_id, node_id, f"Node ID: {node_id}"
    elif field_id == "snr":
        number = _float_or_none(_first_present(row, "snr", "rx_snr", "avg_snr"))
        value = number if number is not None else "n/a"
        sort = number
        title = f"SNR: {value}{' dB' if number is not None else ''}"
    elif field_id == "hardware":
        text = str(_first_present(row, "hardware_model", "hardware") or "").strip() or "n/a"
        value, sort, title = text, text.casefold(), f"Hardware: {text}"
    elif field_id == "battery":
        number = _int_or_none(_first_present(row, "battery_level", "battery"))
        value = number if number is not None else "n/a"
        sort = number
        title = f"Battery: {value}{'%' if number is not None else ''}"
    elif field_id == "hops":
        number = _int_or_none(_first_present(row, "hops_away", "hops", "last_hops"))
        value = number if number is not None else "n/a"
        sort = number
        title = f"Hops: {value}"
    elif field_id == "last_heard":
        number = _timestamp_or_none(
            _first_present(row, "last_heard_unix", "last_heard_epoch", "last_heard")
        )
        value = number if number is not None else "n/a"
        sort = number
        title = "Last heard"
    elif field_id == "links":
        number = _int_or_none(_first_present(row, "link_count", "links"))
        packet_count = _int_or_none(_first_present(row, "link_packet_count", "link_packets"))
        value = number if number is not None else "n/a"
        sort = number
        if number is None:
            title = "Links: n/a"
        elif packet_count is not None and packet_count > 0:
            title = (
                f"{number} linked node{'s' if number != 1 else ''}; "
                f"{packet_count} link packet{'s' if packet_count != 1 else ''}"
            )
        else:
            title = f"{number} linked node{'s' if number != 1 else ''}"
    elif field_id == "saved":
        number = _int_or_none(_first_present(row, "saved_packets", "total_packets"))
        value = number if number is not None else "n/a"
        sort = number
        title = f"Total packets: {value}"
    elif field_id == "pos":
        location = _node_location(row)
        if location is None:
            value, sort, title = "n/a", None, "Position: n/a"
        else:
            value = f"{location[0]:.5f}, {location[1]:.5f}"
            sort = location[0]
            title = f"Position: {value}"
    elif field_id == "location_points":
        number = _int_or_none(_first_present(row, "position_points", "location_points"))
        value = number if number is not None else "n/a"
        sort = number
        title = f"Location points: {value}"
    elif field_id == "city":
        value, sort, title = _node_list_city_value(_node_location(row), city_cache)
    else:
        return None

    return {
        "id": f"plugin:node_list:{field_id}",
        "plugin_id": "node_list",
        "field_id": field_id,
        "node_id": node_id,
        "value": value,
        "sort": sort,
        "title": title,
        "runtime_status": runtime_status or "running",
    }


def _truthy_query_flag(query: str, key: str) -> bool:
    """Return True when a query parameter is present and not an explicit false."""
    try:
        params = parse_qs(query or "", keep_blank_values=True)
    except Exception:
        return False
    if key not in params:
        return False
    raw = params.get(key) or [""]
    value = str(raw[0] if raw else "").strip().lower()
    return value not in ("", "0", "false", "no", "off")


def _query_value(query: str, key: str, default: str = "") -> str:
    try:
        params = parse_qs(query or "", keep_blank_values=True)
    except Exception:
        return default
    raw = params.get(key) or []
    value = str(raw[0] if raw else "").strip()
    return value or default


def _lite_state_payload(payload: object) -> object:
    """Drop large/raw-only fields to speed up UI polling."""
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    out.pop("my_info", None)
    out.pop("metadata", None)
    out.pop("local_state", None)
    out.pop("nodes_full", None)
    return out


def _private_mode_state_payload(payload: object) -> object:
    """Remove public chat/message slices for sensitive deployments."""
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    out.pop("faults", None)
    traffic_raw = out.get("traffic")
    if isinstance(traffic_raw, dict):
        traffic = dict(traffic_raw)
        traffic["recent_chat"] = []
        out["traffic"] = traffic
    return out


def _plugin_ticker_enabled_map(plugins: Mapping[str, object]) -> dict[str, bool]:
    scripts = plugins.get("scripts")
    if not isinstance(scripts, list):
        return {}
    enabled_by_plugin: dict[str, bool] = {}
    for script in scripts:
        if not isinstance(script, Mapping):
            continue
        plugin_id = str(script.get("id") or "").strip().lower()
        if plugin_id:
            enabled_by_plugin[plugin_id] = script.get("ticker_enabled") is not False
    return enabled_by_plugin


def _public_plugin_tickers(
    runtime: Mapping[str, object],
    *,
    ticker_enabled_by_plugin: Mapping[str, bool] | None = None,
) -> list[dict[str, object]]:
    tickers = runtime.get("tickers")
    if not isinstance(tickers, list):
        return []
    safe_tickers: list[dict[str, object]] = []
    ticker_policy = ticker_enabled_by_plugin or {}
    public_fields = {
        "id",
        "plugin_id",
        "ticker_id",
        "label",
        "metric",
        "default_enabled",
        "value",
        "rows",
        "state",
        "detail",
        "metric_value",
        "updated_at",
        "runtime_status",
    }
    for ticker in tickers:
        if not isinstance(ticker, Mapping):
            continue
        plugin_id = str(ticker.get("plugin_id") or "").strip().lower()
        if ticker_policy.get(plugin_id) is False:
            continue
        safe_tickers.append(
            {
                str(key): value
                for key, value in ticker.items()
                if str(key) in public_fields
            }
        )
    return safe_tickers


def _public_plugin_node_fields(
    runtime: Mapping[str, object],
) -> tuple[list[dict[str, object]], set[tuple[str, str]]]:
    rows = runtime.get("node_fields")
    if not isinstance(rows, list):
        return [], set()
    safe_fields: list[dict[str, object]] = []
    declared: set[tuple[str, str]] = set()
    public_fields = {
        "id",
        "plugin_id",
        "field_id",
        "label",
        "group",
        "value_type",
        "render_kinds",
        "default_render_kind",
        "default_visible",
        "sortable",
        "roster_line",
        "runtime_status",
    }
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        plugin_id = str(row.get("plugin_id") or "").strip().lower()
        field_id = str(row.get("field_id") or "").strip().lower()
        namespaced_id = str(row.get("id") or "").strip().lower()
        if (
            _PUBLIC_PLUGIN_ID_RE.fullmatch(plugin_id) is None
            or _PUBLIC_PLUGIN_NODE_FIELD_RE.fullmatch(field_id) is None
            or namespaced_id != f"plugin:{plugin_id}:{field_id}"
        ):
            continue
        declared.add((plugin_id, field_id))
        safe_fields.append(
            {
                str(key): value
                for key, value in row.items()
                if str(key) in public_fields
            }
        )
    return safe_fields, declared


def _public_plugin_node_field_values(
    runtime: Mapping[str, object],
    declared_node_fields: set[tuple[str, str]],
    *,
    node_rows: object = None,
    node_field_statuses: Mapping[tuple[str, str], str] | None = None,
) -> list[dict[str, object]]:
    rows = runtime.get("node_field_values")
    if not isinstance(rows, list):
        rows = []
    safe_values: list[dict[str, object]] = []
    public_fields = {
        "id",
        "plugin_id",
        "field_id",
        "node_id",
        "value",
        "sort",
        "title",
        "updated_at",
        "runtime_status",
    }
    node_list_mirror_fields = {
        field_id
        for plugin_id, field_id in declared_node_fields
        if plugin_id == "node_list" and field_id in _NODE_LIST_MIRROR_FIELD_IDS
    }
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        plugin_id = str(row.get("plugin_id") or "").strip().lower()
        field_id = str(row.get("field_id") or "").strip().lower()
        node_id = str(row.get("node_id") or "").strip().lower()
        namespaced_id = str(row.get("id") or "").strip().lower()
        if plugin_id == "node_list" and field_id in node_list_mirror_fields:
            continue
        if (
            (plugin_id, field_id) not in declared_node_fields
            or _PUBLIC_NODE_ID_RE.fullmatch(node_id) is None
            or namespaced_id != f"plugin:{plugin_id}:{field_id}"
        ):
            continue
        safe_values.append(
            {
                str(key): value
                for key, value in row.items()
                if str(key) in public_fields
            }
        )
    if node_list_mirror_fields and isinstance(node_rows, list):
        statuses = node_field_statuses or {}
        runtime_status = statuses.get(("node_list", "id"), "running")
        city_cache: dict[tuple[float, float], dict[str, object] | None] = {}
        for node_row in node_rows:
            if not isinstance(node_row, Mapping):
                continue
            for field_id in _NODE_LIST_MIRROR_FIELD_ORDER:
                if field_id not in node_list_mirror_fields:
                    continue
                runtime_status = statuses.get(("node_list", field_id), runtime_status)
                value = _node_list_mirror_field_value(
                    node_row,
                    field_id,
                    runtime_status=runtime_status,
                    city_cache=city_cache,
                )
                if value is not None:
                    safe_values.append(value)
    return safe_values


def _public_plugin_console_commands(plugins: Mapping[str, object]) -> list[dict[str, object]]:
    if plugins.get("runtime_enabled") is False:
        return []
    scripts = plugins.get("scripts")
    if not isinstance(scripts, list):
        return []
    commands: list[dict[str, object]] = []
    seen: set[str] = set()
    for script in scripts:
        if not isinstance(script, Mapping):
            continue
        if script.get("enabled") is not True or script.get("active") is not True:
            continue
        if script.get("console_enabled") is False:
            continue
        runtime_status = str(script.get("runtime_status") or "").strip().lower()
        if runtime_status in {"disabled", "error", "restart_pending"}:
            continue
        plugin_id = str(script.get("id") or "").strip().lower()
        plugin_name = str(script.get("name") or plugin_id).strip() or plugin_id
        raw_commands = script.get("commands")
        if not plugin_id or not isinstance(raw_commands, list):
            continue
        for raw_command in raw_commands:
            command = str(raw_command or "").strip().lower()
            if _PUBLIC_PLUGIN_COMMAND_RE.fullmatch(command) is None or command in seen:
                continue
            seen.add(command)
            commands.append(
                {
                    "name": command,
                    "plugin_id": plugin_id,
                    "plugin_name": plugin_name,
                    "runtime_status": runtime_status or "starting",
                }
            )
    return commands


def _public_plugin_views(plugins: Mapping[str, object]) -> list[dict[str, object]]:
    if plugins.get("runtime_enabled") is False:
        return []
    scripts = plugins.get("scripts")
    if not isinstance(scripts, list):
        return []
    views: list[dict[str, object]] = []
    for script in scripts:
        if not isinstance(script, Mapping):
            continue
        plugin_id = str(script.get("id") or "").strip().lower()
        plugin_name = str(script.get("name") or plugin_id).strip() or plugin_id
        if _PUBLIC_PLUGIN_ID_RE.fullmatch(plugin_id) is None:
            continue
        if script.get("enabled") is not True:
            continue
        if script.get("view_enabled") is False:
            continue
        raw_views = script.get("views")
        if not isinstance(raw_views, list):
            continue
        runtime_status = str(script.get("runtime_status") or "").strip().lower()
        for raw_view in raw_views:
            if not isinstance(raw_view, Mapping):
                continue
            view_id = str(raw_view.get("id") or "").strip().lower()
            label = str(raw_view.get("label") or "").strip()
            icon = str(raw_view.get("icon") or "").strip().upper()
            description = str(raw_view.get("description") or "").strip()
            content = str(raw_view.get("content") or "")
            if _PUBLIC_PLUGIN_VIEW_RE.fullmatch(view_id) is None:
                continue
            if not label or len(label) > 32:
                continue
            if _PUBLIC_PLUGIN_VIEW_ICON_RE.fullmatch(icon) is None:
                icon = label[:2].upper()
            if len(description) > 120:
                description = description[:120].rstrip()
            if len(content) > 16 * 1024:
                content = content[: 16 * 1024]
            views.append(
                {
                    "id": f"plugin:{plugin_id}:{view_id}",
                    "plugin_id": plugin_id,
                    "plugin_name": plugin_name,
                    "view_id": view_id,
                    "label": label,
                    "icon": icon,
                    "description": description,
                    "content": content,
                    "enabled": True,
                    "active": script.get("active") is True,
                    "runtime_status": runtime_status or "starting",
                }
            )
    return views


def _public_plugin_status(
    plugins: Mapping[str, object],
    *,
    node_rows: object = None,
) -> dict[str, object]:
    enabled = plugins.get("enabled") is True
    runtime_enabled = enabled and plugins.get("runtime_enabled") is not False
    runtime_raw = plugins.get("runtime")
    runtime = runtime_raw if isinstance(runtime_raw, Mapping) else {}
    ticker_enabled_by_plugin = _plugin_ticker_enabled_map(plugins)
    runtime_status = str(runtime.get("status") or "").strip().lower()
    worker_alive = runtime.get("worker_alive") is True
    has_error = bool(plugins.get("error") or runtime.get("last_error"))
    if not enabled or not runtime_enabled:
        health = "disabled"
    elif has_error or runtime_status in {"error", "failed", "crashed"}:
        health = "error"
    elif worker_alive:
        health = "running"
    else:
        health = "enabled"
    enabled_plugins = plugins.get("enabled_plugins")
    node_fields, declared_node_fields = _public_plugin_node_fields(runtime)
    node_field_statuses = {
        (
            str(row.get("plugin_id") or "").strip().lower(),
            str(row.get("field_id") or "").strip().lower(),
        ): str(row.get("runtime_status") or runtime_status or "running").strip().lower()
        for row in node_fields
    }
    public_runtime: dict[str, object] = {
        "tickers": _public_plugin_tickers(
            runtime,
            ticker_enabled_by_plugin=ticker_enabled_by_plugin,
        ),
        "node_fields": node_fields,
        "node_field_values": _public_plugin_node_field_values(
            runtime,
            declared_node_fields,
            node_rows=node_rows,
            node_field_statuses=node_field_statuses,
        ),
    }
    if runtime_status:
        public_runtime["status"] = runtime_status
    if "worker_alive" in runtime:
        public_runtime["worker_alive"] = worker_alive
    public_status: dict[str, object] = {
        "enabled": enabled,
        "runtime_enabled": runtime_enabled,
        "health": health,
        "active_count": (
            len(enabled_plugins) if isinstance(enabled_plugins, list) else 0
        ),
        "console_commands": _public_plugin_console_commands(plugins),
        "views": _public_plugin_views(plugins),
        "runtime": public_runtime,
    }
    for key in ("available", "discovered"):
        value = plugins.get(key)
        if isinstance(value, (bool, int)) and not isinstance(value, str):
            public_status[key] = value
    return public_status


def _public_plugin_state_payload(payload: object) -> object:
    if not isinstance(payload, dict):
        return payload
    summary_raw = payload.get("summary")
    if not isinstance(summary_raw, dict):
        return payload
    plugins_raw = summary_raw.get("plugins")
    if not isinstance(plugins_raw, Mapping):
        return payload
    out = dict(payload)
    summary = dict(summary_raw)
    summary["plugins"] = _public_plugin_status(
        plugins_raw,
        node_rows=payload.get("nodes"),
    )
    out["summary"] = summary
    return out


def _resolve_fault_history_fn(*, state_fn: object, selected_fn: object) -> object:
    history_fn = getattr(selected_fn, "fault_history_fn", None)
    if callable(history_fn):
        return history_fn
    history_fn = getattr(state_fn, "fault_history_fn", None)
    if callable(history_fn):
        return history_fn
    return None


def _read_fault_rows(*, history_fn: object) -> object:
    if not callable(history_fn):
        return None
    try:
        rows = history_fn()
    except Exception:
        return None
    if not isinstance(rows, list):
        return None
    return rows


def _fault_etag_marker(rows: object) -> str:
    if not isinstance(rows, list):
        return "0"
    sample = []
    for row in rows[:20]:
        if not isinstance(row, dict):
            continue
        sample.append(
            (
                str(row.get("id") or ""),
                str(row.get("created_unix") or ""),
                str(row.get("source") or ""),
                str(row.get("code") or ""),
            )
        )
    marker_parts = [str(len(rows))]
    marker_parts.extend("|".join(part) for part in sample)
    return ";".join(marker_parts)


def _inject_faults(
    payload: object,
    *,
    state_fn: object,
    selected_fn: object,
    rows: object = None,
) -> object:
    if not isinstance(payload, dict):
        return payload
    if rows is None:
        history_fn = _resolve_fault_history_fn(state_fn=state_fn, selected_fn=selected_fn)
        rows = _read_fault_rows(history_fn=history_fn)
    if not isinstance(rows, list) or len(rows) <= 0:
        return payload
    out = dict(payload)
    out["faults"] = rows
    return out


def handle_state_get(
    handler: DashboardHttpHandler,
    *,
    state_fn: StateFn,
    write_json_response_fn: WriteJsonResponseFn,
    query: str = "",
    private_mode: bool = False,
) -> None:
    lite = _truthy_query_flag(query, "lite")
    profile = _query_value(query, "profile", "").lower()

    selected_fn = state_fn
    if lite:
        if profile == "chat":
            state_lite_chat_fn = getattr(state_fn, "lite_chat", None)
            if callable(state_lite_chat_fn):
                selected_fn = state_lite_chat_fn
            else:
                state_lite_fn = getattr(state_fn, "lite", None)
                if callable(state_lite_fn):
                    selected_fn = state_lite_fn
        elif profile == "network":
            state_lite_network_fn = getattr(state_fn, "lite_network", None)
            if callable(state_lite_network_fn):
                selected_fn = state_lite_network_fn
            else:
                state_lite_fn = getattr(state_fn, "lite", None)
                if callable(state_lite_fn):
                    selected_fn = state_lite_fn
        elif profile in {"network-graph", "network_graph"}:
            state_lite_network_graph_fn = getattr(state_fn, "lite_network_graph", None)
            if callable(state_lite_network_graph_fn):
                selected_fn = state_lite_network_graph_fn
            else:
                state_lite_network_fn = getattr(state_fn, "lite_network", None)
                if callable(state_lite_network_fn):
                    selected_fn = state_lite_network_fn
                else:
                    state_lite_fn = getattr(state_fn, "lite", None)
                    if callable(state_lite_fn):
                        selected_fn = state_lite_fn
        elif profile in {"network-map", "network_map"}:
            state_lite_network_map_fn = getattr(state_fn, "lite_network_map", None)
            if callable(state_lite_network_map_fn):
                selected_fn = state_lite_network_map_fn
            else:
                state_lite_network_fn = getattr(state_fn, "lite_network", None)
                if callable(state_lite_network_fn):
                    selected_fn = state_lite_network_fn
                else:
                    state_lite_fn = getattr(state_fn, "lite", None)
                    if callable(state_lite_fn):
                        selected_fn = state_lite_fn
        elif profile == "status":
            state_lite_status_fn = getattr(state_fn, "lite_status", None)
            if callable(state_lite_status_fn):
                selected_fn = state_lite_status_fn
            else:
                state_lite_fn = getattr(state_fn, "lite", None)
                if callable(state_lite_fn):
                    selected_fn = state_lite_fn
        elif profile == "console":
            state_lite_console_fn = getattr(state_fn, "lite_console", None)
            if callable(state_lite_console_fn):
                selected_fn = state_lite_console_fn
            else:
                state_lite_fn = getattr(state_fn, "lite", None)
                if callable(state_lite_fn):
                    selected_fn = state_lite_fn
        else:
            state_lite_fn = getattr(state_fn, "lite", None)
            if callable(state_lite_fn):
                selected_fn = state_lite_fn

    etag_fn = getattr(selected_fn, "etag", None)
    etag = None
    if callable(etag_fn):
        try:
            etag = str(etag_fn())
        except Exception:
            etag = None

    fault_history_fn = _resolve_fault_history_fn(state_fn=state_fn, selected_fn=selected_fn)
    fault_rows = _read_fault_rows(history_fn=fault_history_fn)
    if etag and isinstance(fault_rows, list) and len(fault_rows) > 0:
        etag = f"{etag}|fault:{_fault_etag_marker(fault_rows)}"

    if etag:
        if_none_match = None
        try:
            if_none_match = handler.headers.get("If-None-Match")  # type: ignore[attr-defined]
        except Exception:
            if_none_match = None
        if if_none_match is None:
            for key, value in getattr(handler, "headers", {}).items():
                try:
                    if str(key).lower() == "if-none-match":
                        if_none_match = value
                        break
                except Exception:
                    continue
        if if_none_match is not None and str(if_none_match).strip() == etag:
            handler.send_response(304)
            _send_no_store_headers(handler)
            handler.send_header("ETag", etag)
            handler.send_header("Content-Length", "0")
            handler.end_headers()
            return

    payload_raw = selected_fn()
    payload = normalize_state_payload_for_api(payload_raw)
    payload = _inject_faults(
        payload,
        state_fn=state_fn,
        selected_fn=selected_fn,
        rows=fault_rows,
    )
    payload = _public_plugin_state_payload(payload)
    if private_mode:
        payload = _private_mode_state_payload(payload)
    if lite:
        payload = _lite_state_payload(payload)
    kwargs = {
        "status_code": 200,
        "payload_obj": payload,
        "no_store": True,
    }
    if etag:
        kwargs["extra_headers"] = {"ETag": etag}
    write_json_response_fn(handler, **kwargs)
