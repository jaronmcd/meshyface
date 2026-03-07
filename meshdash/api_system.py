from .http_handler_contracts import DashboardHttpHandler
from .http_route_contracts import StateFn, WriteJsonResponseFn
from .state_payload_contracts import normalize_state_payload_for_api

from urllib.parse import parse_qs


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


def _lite_state_payload(payload: object) -> object:
    """Drop large/raw-only fields to speed up UI polling."""
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    # Raw/debug payloads are expensive to serialize + transmit, and the browser
    # doesn't need them for the primary UI views.
    out.pop("my_info", None)
    out.pop("metadata", None)
    out.pop("local_state", None)
    out.pop("nodes_full", None)
    return out


def _resolve_bot_request_history_fn(*, state_fn: object, selected_fn: object) -> object:
    history_fn = getattr(selected_fn, "bot_request_history_fn", None)
    if callable(history_fn):
        return history_fn
    history_fn = getattr(state_fn, "bot_request_history_fn", None)
    if callable(history_fn):
        return history_fn
    return None


def _resolve_bot_settings_fn(*, state_fn: object, selected_fn: object) -> object:
    settings_fn = getattr(selected_fn, "bot_settings_fn", None)
    if callable(settings_fn):
        return settings_fn
    settings_fn = getattr(state_fn, "bot_settings_fn", None)
    if callable(settings_fn):
        return settings_fn
    return None


def _read_bot_request_rows(*, history_fn: object) -> object:
    if not callable(history_fn):
        return None
    try:
        rows = history_fn()
    except Exception:
        return None
    if not isinstance(rows, list):
        return None
    return rows


def _read_bot_settings(*, settings_fn: object) -> object:
    if not callable(settings_fn):
        return None
    try:
        payload = settings_fn()
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _bot_request_etag_marker(rows: object) -> str:
    if not isinstance(rows, list):
        return "0"
    sample = []
    for row in rows[:20]:
        if not isinstance(row, dict):
            continue
        sample.append(
            (
                str(row.get("id") or ""),
                str(row.get("received_unix") or row.get("sent_unix") or ""),
                str(row.get("response_message_id") or ""),
                "1" if bool(row.get("responded")) else "0",
            )
        )
    marker_parts = [str(len(rows))]
    marker_parts.extend("|".join(part) for part in sample)
    return ";".join(marker_parts)


def _bot_settings_etag_marker(settings: object) -> str:
    if not isinstance(settings, dict):
        return "none"
    commands = settings.get("commands")
    command_marker_parts = []
    if isinstance(commands, list):
        for row in commands:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "").strip().lower()
            if not name:
                continue
            command_marker_parts.append(f"{name}:{'1' if bool(row.get('enabled')) else '0'}")
    return "|".join(
        [
            "1" if bool(settings.get("enabled")) else "0",
            "1" if bool(settings.get("log_enabled")) else "0",
            "1" if bool(settings.get("game_enabled")) else "0",
            str(settings.get("active_game_sessions") or 0),
            ",".join(command_marker_parts),
        ]
    )


def _inject_bot_requests(
    payload: object,
    *,
    state_fn: object,
    selected_fn: object,
    rows: object = None,
) -> object:
    if not isinstance(payload, dict):
        return payload
    if rows is None:
        history_fn = _resolve_bot_request_history_fn(state_fn=state_fn, selected_fn=selected_fn)
        rows = _read_bot_request_rows(history_fn=history_fn)
    if not isinstance(rows, list):
        return payload
    out = dict(payload)
    out["bot_requests"] = rows
    return out


def _inject_bot_settings(
    payload: object,
    *,
    state_fn: object,
    selected_fn: object,
    settings: object = None,
) -> object:
    if not isinstance(payload, dict):
        return payload
    if settings is None:
        settings_fn = _resolve_bot_settings_fn(state_fn=state_fn, selected_fn=selected_fn)
        settings = _read_bot_settings(settings_fn=settings_fn)
    if not isinstance(settings, dict):
        return payload
    out = dict(payload)
    out["bot_settings"] = settings
    return out


def handle_state_get(
    handler: DashboardHttpHandler,
    *,
    state_fn: StateFn,
    write_json_response_fn: WriteJsonResponseFn,
    query: str = "",
) -> None:
    lite = _truthy_query_flag(query, "lite")

    # Resolve the function that will be used to build the payload.
    selected_fn = state_fn
    if lite:
        state_lite_fn = getattr(state_fn, "lite", None)
        if callable(state_lite_fn):
            selected_fn = state_lite_fn

    # Conditional GET: if the client already has this version, return 304.
    etag_fn = getattr(selected_fn, "etag", None)
    etag = None
    if callable(etag_fn):
        try:
            etag = str(etag_fn())
        except Exception:
            etag = None
    history_fn = _resolve_bot_request_history_fn(state_fn=state_fn, selected_fn=selected_fn)
    bot_rows = _read_bot_request_rows(history_fn=history_fn)
    settings_fn = _resolve_bot_settings_fn(state_fn=state_fn, selected_fn=selected_fn)
    bot_settings = _read_bot_settings(settings_fn=settings_fn)
    if etag and isinstance(bot_rows, list):
        etag = f"{etag}|bot:{_bot_request_etag_marker(bot_rows)}"
    if etag and isinstance(bot_settings, dict):
        etag = f"{etag}|botcfg:{_bot_settings_etag_marker(bot_settings)}"

    if etag:
        # BaseHTTPRequestHandler's headers mapping is case-insensitive, but our
        # Protocol is only a Mapping, so be defensive.
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
            handler.send_header("Cache-Control", "no-store")
            handler.send_header("ETag", etag)
            handler.send_header("Content-Length", "0")
            handler.end_headers()
            return

    payload_raw = selected_fn()
    payload = normalize_state_payload_for_api(payload_raw)
    payload = _inject_bot_requests(
        payload,
        state_fn=state_fn,
        selected_fn=selected_fn,
        rows=bot_rows,
    )
    payload = _inject_bot_settings(
        payload,
        state_fn=state_fn,
        selected_fn=selected_fn,
        settings=bot_settings,
    )
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
