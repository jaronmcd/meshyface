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


def _private_mode_state_payload(payload: object) -> object:
    """Remove public chat/message slices for sensitive deployments."""
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    out.pop("faults", None)
    out.pop("bot_requests", None)
    out.pop("bot_faults", None)
    traffic_raw = out.get("traffic")
    if isinstance(traffic_raw, dict):
        traffic = dict(traffic_raw)
        traffic["recent_chat"] = []
        out["traffic"] = traffic
    return out


def _resolve_bot_request_history_fn(*, state_fn: object, selected_fn: object) -> object:
    history_fn = getattr(selected_fn, "bot_request_history_fn", None)
    if callable(history_fn):
        return history_fn
    history_fn = getattr(state_fn, "bot_request_history_fn", None)
    if callable(history_fn):
        return history_fn
    return None


def _resolve_fault_history_fn(*, state_fn: object, selected_fn: object) -> object:
    history_fn = getattr(selected_fn, "fault_history_fn", None)
    if callable(history_fn):
        return history_fn
    history_fn = getattr(state_fn, "fault_history_fn", None)
    if callable(history_fn):
        return history_fn
    return None


def _resolve_bot_fault_history_fn(*, state_fn: object, selected_fn: object) -> object:
    history_fn = getattr(selected_fn, "bot_fault_history_fn", None)
    if callable(history_fn):
        return history_fn
    history_fn = getattr(state_fn, "bot_fault_history_fn", None)
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


def _read_bot_fault_rows(*, history_fn: object) -> object:
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


def _bot_fault_etag_marker(rows: object) -> str:
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
                str(row.get("code") or ""),
            )
        )
    marker_parts = [str(len(rows))]
    marker_parts.extend("|".join(part) for part in sample)
    return ";".join(marker_parts)


def _filter_bot_fault_rows(rows: object) -> list[dict[str, object]]:
    if not isinstance(rows, list):
        return []
    out: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source") or "").strip().lower()
        if source != "bot":
            continue
        out.append(row)
    return out


def _bot_settings_etag_marker(settings: object) -> str:
    if not isinstance(settings, dict):
        return "none"
    commands = settings.get("commands")
    ping_triggers = settings.get("ping_triggers")
    pull_reel_symbols = settings.get("pull_reel_symbols")
    joke_triggers = settings.get("joke_triggers")
    zork_triggers = settings.get("zork_triggers")
    hard_disabled_incoming_commands = settings.get("hard_disabled_incoming_commands")
    joke_lines = settings.get("joke_lines")
    joke_near_guess_lines = settings.get("joke_near_guess_lines")
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
            "1" if bool(settings.get("game_public_start_enabled")) else "0",
            "1" if bool(settings.get("joke_delay_punchline_enabled")) else "0",
            str(settings.get("active_game_sessions") or 0),
            str(len(ping_triggers) if isinstance(ping_triggers, list) else 0),
            str(len(pull_reel_symbols) if isinstance(pull_reel_symbols, list) else 0),
            str(len(str(settings.get("pull_response_template") or ""))),
            str(len(joke_triggers) if isinstance(joke_triggers, list) else 0),
            str(len(zork_triggers) if isinstance(zork_triggers, list) else 0),
            str(
                len(hard_disabled_incoming_commands)
                if isinstance(hard_disabled_incoming_commands, list)
                else 0
            ),
            str(len(joke_lines) if isinstance(joke_lines, list) else 0),
            str(len(joke_near_guess_lines) if isinstance(joke_near_guess_lines, list) else 0),
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


def _inject_bot_faults(
    payload: object,
    *,
    state_fn: object,
    selected_fn: object,
    rows: object = None,
    fallback_rows: object = None,
) -> object:
    if not isinstance(payload, dict):
        return payload
    if rows is None:
        history_fn = _resolve_bot_fault_history_fn(state_fn=state_fn, selected_fn=selected_fn)
        rows = _read_bot_fault_rows(history_fn=history_fn)
    if not isinstance(rows, list):
        rows = _filter_bot_fault_rows(fallback_rows)
    if not isinstance(rows, list) or len(rows) <= 0:
        return payload
    out = dict(payload)
    out["bot_faults"] = rows
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
    private_mode: bool = False,
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
    fault_history_fn = _resolve_fault_history_fn(state_fn=state_fn, selected_fn=selected_fn)
    fault_rows = _read_fault_rows(history_fn=fault_history_fn)
    history_fn = _resolve_bot_request_history_fn(state_fn=state_fn, selected_fn=selected_fn)
    bot_rows = _read_bot_request_rows(history_fn=history_fn)
    bot_fault_history_fn = _resolve_bot_fault_history_fn(state_fn=state_fn, selected_fn=selected_fn)
    bot_fault_rows = _read_bot_fault_rows(history_fn=bot_fault_history_fn)
    if not isinstance(bot_fault_rows, list) and isinstance(fault_rows, list) and len(fault_rows) > 0:
        filtered_bot_fault_rows = _filter_bot_fault_rows(fault_rows)
        if len(filtered_bot_fault_rows) > 0:
            bot_fault_rows = filtered_bot_fault_rows
    settings_fn = _resolve_bot_settings_fn(state_fn=state_fn, selected_fn=selected_fn)
    bot_settings = _read_bot_settings(settings_fn=settings_fn)
    if etag and isinstance(fault_rows, list) and len(fault_rows) > 0:
        etag = f"{etag}|fault:{_fault_etag_marker(fault_rows)}"
    if etag and isinstance(bot_rows, list):
        etag = f"{etag}|bot:{_bot_request_etag_marker(bot_rows)}"
    if etag and isinstance(bot_fault_rows, list) and len(bot_fault_rows) > 0:
        etag = f"{etag}|botfault:{_bot_fault_etag_marker(bot_fault_rows)}"
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
    payload = _inject_faults(
        payload,
        state_fn=state_fn,
        selected_fn=selected_fn,
        rows=fault_rows,
    )
    payload = _inject_bot_requests(
        payload,
        state_fn=state_fn,
        selected_fn=selected_fn,
        rows=bot_rows,
    )
    payload = _inject_bot_faults(
        payload,
        state_fn=state_fn,
        selected_fn=selected_fn,
        rows=bot_fault_rows,
        fallback_rows=fault_rows,
    )
    payload = _inject_bot_settings(
        payload,
        state_fn=state_fn,
        selected_fn=selected_fn,
        settings=bot_settings,
    )
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
