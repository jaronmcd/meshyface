import json

_ENV_METRIC_ALIAS_MAP = {
    "relativehumidity": "relative_humidity",
    "barometricpressure": "barometric_pressure",
    "gasresistance": "gas_resistance",
    "iaq": "iaq",
    "channelutilization": "channel_utilization",
    "airutiltx": "air_util_tx",
}


def normalize_env_metric_key(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    cleaned = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in text)
    cleaned = "_".join(part for part in cleaned.split("_") if part).lower()
    if not cleaned:
        return ""
    squashed = cleaned.replace("_", "")
    return _ENV_METRIC_ALIAS_MAP.get(squashed, cleaned)


def format_env_metric_label(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "Metric"
    words = "".join(ch if (ch.isalnum() or ch in ("_", "-")) else " " for ch in text)
    words = words.replace("_", " ").replace("-", " ")
    return " ".join(part.capitalize() for part in words.split() if part) or "Metric"


def metric_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        out = float(value)
        return out if out == out and abs(out) != float("inf") else None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        out = float(text)
    except Exception:
        return None
    return out if out == out and abs(out) != float("inf") else None


def _parse_bool_token(value: object, default: bool) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if int(value) == 1:
            return True
        if int(value) == 0:
            return False
    text = str(value or "").strip().lower()
    if not text:
        return bool(default)
    if text in {"1", "true", "yes", "on", "enabled", "enable"}:
        return True
    if text in {"0", "false", "no", "off", "disabled", "disable"}:
        return False
    return bool(default)


def _coerce_metric_number(value: object, default: float) -> float:
    parsed = metric_float(value)
    if parsed is None:
        return float(default)
    return float(parsed)


def _looks_like_hex_text(value: str) -> bool:
    return bool(value) and len(value) % 2 == 0 and all(ch in "0123456789abcdefABCDEF" for ch in value)


def _parse_payload_json(decoded: object) -> object | None:
    if not isinstance(decoded, dict):
        return None
    payload = decoded.get("payload")
    if isinstance(payload, (dict, list)):
        return payload
    if payload is None:
        return None

    text = ""
    if isinstance(payload, (bytes, bytearray)):
        try:
            text = bytes(payload).decode("utf-8", errors="strict")
        except Exception:
            text = ""
    else:
        text = str(payload or "").strip()
        if text and _looks_like_hex_text(text):
            try:
                text = bytes.fromhex(text).decode("utf-8", errors="strict").strip()
            except Exception:
                pass
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def _resolve_rule_path(root: object, path: str) -> object:
    clean_path = str(path or "").strip()
    if not clean_path:
        return root
    current = root
    for raw_part in clean_path.split("."):
        part = str(raw_part or "").strip()
        if not part:
            continue
        if isinstance(current, dict):
            if part in current:
                current = current.get(part)
                continue
            lowered_lookup = part.lower()
            matched = None
            for key, value in current.items():
                if str(key or "").strip().lower() == lowered_lookup:
                    matched = value
                    break
            if matched is None:
                return None
            current = matched
            continue
        if isinstance(current, list):
            if part.isdigit():
                idx = int(part)
                if idx < 0 or idx >= len(current):
                    return None
                current = current[idx]
                continue
            return None
        return None
    return current


def normalize_custom_telemetry_rules(
    value: object,
    *,
    max_rules: int = 128,
) -> list[dict[str, object]]:
    payload = value
    if isinstance(payload, dict) and isinstance(payload.get("rules"), list):
        payload = payload.get("rules")
    if not isinstance(payload, list):
        return []

    out: list[dict[str, object]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for raw_rule in payload:
        if len(out) >= max_rules:
            break
        if not isinstance(raw_rule, dict):
            continue
        metric_key = normalize_env_metric_key(
            raw_rule.get("metric_key")
            or raw_rule.get("key")
            or raw_rule.get("metric")
            or raw_rule.get("name")
        )
        if not metric_key:
            continue
        source = str(raw_rule.get("source") or "payload_json").strip().lower()
        if source not in {"decoded", "payload_json"}:
            source = "payload_json"
        path = str(raw_rule.get("path") or raw_rule.get("json_path") or "").strip()
        portnum = str(raw_rule.get("portnum") or raw_rule.get("port") or "").strip().upper()
        enabled = _parse_bool_token(raw_rule.get("enabled"), True)
        scale = _coerce_metric_number(raw_rule.get("scale"), 1.0)
        offset = _coerce_metric_number(raw_rule.get("offset"), 0.0)
        dedupe_key = (metric_key, source, path, portnum)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        out.append(
            {
                "enabled": enabled,
                "metric_key": metric_key,
                "source": source,
                "path": path,
                "portnum": portnum,
                "scale": float(scale),
                "offset": float(offset),
            }
        )
    return out


def _collect_custom_metric_container(
    *,
    decoded: object,
    summary: object,
    custom_rules: object,
) -> dict[str, float]:
    rules = normalize_custom_telemetry_rules(custom_rules)
    if not rules or not isinstance(decoded, dict):
        return {}

    summary_map = summary if isinstance(summary, dict) else {}
    decoded_portnum = str(decoded.get("portnum") or "").strip().upper()
    summary_portnum = str(summary_map.get("portnum") or "").strip().upper()
    payload_cache = {"loaded": False, "value": None}
    out: dict[str, float] = {}

    for rule in rules:
        if not _parse_bool_token(rule.get("enabled"), True):
            continue
        metric_key = normalize_env_metric_key(rule.get("metric_key") or "")
        if not metric_key:
            continue
        port_filter = str(rule.get("portnum") or "").strip().upper()
        if port_filter:
            portnum = summary_portnum or decoded_portnum
            if portnum != port_filter:
                continue

        source_key = str(rule.get("source") or "payload_json").strip().lower()
        if source_key == "decoded":
            source_obj = decoded
        else:
            if not payload_cache["loaded"]:
                payload_cache["value"] = _parse_payload_json(decoded)
                payload_cache["loaded"] = True
            source_obj = payload_cache["value"]
        if source_obj is None:
            continue

        path = str(rule.get("path") or "").strip()
        raw_value = _resolve_rule_path(source_obj, path)
        numeric_value = metric_float(raw_value)
        if numeric_value is None:
            continue
        scale = _coerce_metric_number(rule.get("scale"), 1.0)
        offset = _coerce_metric_number(rule.get("offset"), 0.0)
        adjusted = (float(numeric_value) * float(scale)) + float(offset)
        if adjusted != adjusted or abs(adjusted) == float("inf"):
            continue
        out[metric_key] = adjusted
    return out


def collect_environment_metric_containers(
    source: object,
    *,
    summary: object = None,
    packet: object = None,
    custom_rules: object = None,
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    metric_container_keys = {"environmentmetrics", "devicemetrics"}
    stack = [source]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            current_id = id(current)
            if current_id in seen:
                continue
            seen.add(current_id)
            for raw_key, raw_value in current.items():
                key = "".join(ch for ch in str(raw_key or "") if ch.isalnum()).lower()
                if key in metric_container_keys and isinstance(raw_value, dict):
                    out.append(raw_value)
                if isinstance(raw_value, (dict, list)):
                    stack.append(raw_value)
        elif isinstance(current, list):
            current_id = id(current)
            if current_id in seen:
                continue
            seen.add(current_id)
            for item in current:
                if isinstance(item, (dict, list)):
                    stack.append(item)

    decoded = source if isinstance(source, dict) else {}
    summary_map = summary if isinstance(summary, dict) else {}
    packet_map = packet if isinstance(packet, dict) else {}
    if not summary_map and isinstance(packet_map.get("summary"), dict):
        summary_map = packet_map.get("summary")
    custom_metrics = _collect_custom_metric_container(
        decoded=decoded,
        summary=summary_map,
        custom_rules=custom_rules,
    )
    if custom_metrics:
        out.append(custom_metrics)
    return out
