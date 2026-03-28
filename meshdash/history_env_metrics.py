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


def collect_environment_metric_containers(source: object) -> list[dict[str, object]]:
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
    return out
