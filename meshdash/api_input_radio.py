import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RadioSettingsRequest:
    """A request to apply radio settings to the connected node.

    Supports:
      - `lora`: legacy LoRa-only field updates.
      - `local`: local config section updates, keyed by section name.
      - `module`: module config section updates, keyed by section name.
      - `actions`: control actions, e.g.
        {"reset_nodedb": true, "reset_dashboard_db": true, "set_time": true}
    """

    lora: dict[str, object] = field(default_factory=dict)
    local: dict[str, dict[str, object]] = field(default_factory=dict)
    module: dict[str, dict[str, object]] = field(default_factory=dict)
    actions: dict[str, bool] = field(default_factory=dict)


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


def _clean_update_value(value: object) -> object | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        if all(item is None or isinstance(item, (str, int, float, bool)) for item in value):
            return list(value)
        return None
    if isinstance(value, dict):
        clean_obj: dict[str, object] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                continue
            clean_v = _clean_update_value(v)
            if clean_v is not None:
                clean_obj[k] = clean_v
            elif v is None:
                clean_obj[k] = None
        return clean_obj
    return None


def _clean_update_object(payload: object, *, field_name: str) -> dict[str, object]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError(f"Expected '{field_name}' to be an object")
    clean_obj: dict[str, object] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        clean_value = _clean_update_value(value)
        if clean_value is not None:
            clean_obj[key] = clean_value
        elif value is None:
            clean_obj[key] = None
    return clean_obj


def _clean_section_map(payload: object, *, field_name: str) -> dict[str, dict[str, object]]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError(f"Expected '{field_name}' to be an object")

    clean_sections: dict[str, dict[str, object]] = {}
    for section, updates in payload.items():
        if not isinstance(section, str):
            continue
        if not isinstance(updates, dict):
            continue
        clean_sections[section] = _clean_update_object(updates, field_name=f"{field_name}.{section}")
    return clean_sections


def _clean_actions(payload: object) -> dict[str, bool]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("Expected 'actions' to be an object")

    actions: dict[str, bool] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        if key in {"reset_nodedb", "reset_dashboard_db", "set_time"}:
            actions[key] = _coerce_bool(value)
    return actions


def parse_radio_settings_request(raw_body: bytes) -> RadioSettingsRequest:
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Invalid JSON: {exc}")

    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object")

    clean_lora = _clean_update_object(payload.get("lora"), field_name="lora")
    clean_local = _clean_section_map(payload.get("local"), field_name="local")
    clean_module = _clean_section_map(payload.get("module"), field_name="module")
    clean_actions = _clean_actions(payload.get("actions"))

    if "reset_nodedb" not in clean_actions and "reset_nodedb" in payload:
        clean_actions["reset_nodedb"] = _coerce_bool(payload.get("reset_nodedb"))
    if "reset_dashboard_db" not in clean_actions and "reset_dashboard_db" in payload:
        clean_actions["reset_dashboard_db"] = _coerce_bool(payload.get("reset_dashboard_db"))
    if "set_time" not in clean_actions and "set_time" in payload:
        clean_actions["set_time"] = _coerce_bool(payload.get("set_time"))

    return RadioSettingsRequest(
        lora=clean_lora,
        local=clean_local,
        module=clean_module,
        actions=clean_actions,
    )
