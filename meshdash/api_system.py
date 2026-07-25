import re
from collections.abc import Mapping
from urllib.parse import parse_qs

from .http_handler_contracts import DashboardHttpHandler
from .http_route_contracts import StateFn, WriteJsonResponseFn
from .http_responses import _send_no_store_headers
from .state_payload_contracts import normalize_state_payload_for_api

_PUBLIC_PLUGIN_COMMAND_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")


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


def _public_plugin_tickers(runtime: Mapping[str, object]) -> list[dict[str, object]]:
    tickers = runtime.get("tickers")
    if not isinstance(tickers, list):
        return []
    safe_tickers: list[dict[str, object]] = []
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
        safe_tickers.append(
            {
                str(key): value
                for key, value in ticker.items()
                if str(key) in public_fields
            }
        )
    return safe_tickers


def _public_plugin_console_commands(plugins: Mapping[str, object]) -> list[dict[str, object]]:
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


def _public_plugin_status(plugins: Mapping[str, object]) -> dict[str, object]:
    enabled = plugins.get("enabled") is True
    runtime_raw = plugins.get("runtime")
    runtime = runtime_raw if isinstance(runtime_raw, Mapping) else {}
    runtime_status = str(runtime.get("status") or "").strip().lower()
    worker_alive = runtime.get("worker_alive") is True
    has_error = bool(plugins.get("error") or runtime.get("last_error"))
    if not enabled:
        health = "disabled"
    elif has_error or runtime_status in {"error", "failed", "crashed"}:
        health = "error"
    elif worker_alive:
        health = "running"
    else:
        health = "enabled"
    enabled_plugins = plugins.get("enabled_plugins")
    public_runtime: dict[str, object] = {
        "tickers": _public_plugin_tickers(runtime),
    }
    if runtime_status:
        public_runtime["status"] = runtime_status
    if "worker_alive" in runtime:
        public_runtime["worker_alive"] = worker_alive
    public_status: dict[str, object] = {
        "enabled": enabled,
        "health": health,
        "active_count": (
            len(enabled_plugins) if isinstance(enabled_plugins, list) else 0
        ),
        "console_commands": _public_plugin_console_commands(plugins),
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
    summary["plugins"] = _public_plugin_status(plugins_raw)
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
