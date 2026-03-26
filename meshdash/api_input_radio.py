import json
from dataclasses import dataclass, field

from .config import SENSITIVE_FIELD_NAMES
from .helpers_security import is_sensitive_key


@dataclass(frozen=True)
class RadioSettingsRequest:
    """A request to apply radio settings to the connected node.

    Supports:
      - `lora`: legacy LoRa-only field updates.
      - `local`: local config section updates, keyed by section name.
      - `module`: module config section updates, keyed by section name.
      - `owner`: local node identity updates, e.g. {"short_name":"ABCD","long_name":"Alpha Bravo"}
      - `fixed_position`: fixed GPS position values, e.g. {"lat": 45.0, "lon": -93.0, "alt": 250}
      - `time_sync`: host/dashboard time sync controls for set_time action, e.g.
        {"enabled": true, "server": "pool.ntp.org", "timezone": "America/Chicago"}
      - `actions`: control actions, e.g.
        {
          "reset_nodedb": true,
          "reset_dashboard_db": true,
          "set_time": true,
          "regenerate_node_id": true,
          "set_fixed_position": true,
          "clear_fixed_position": true,
        }
    """

    lora: dict[str, object] = field(default_factory=dict)
    local: dict[str, dict[str, object]] = field(default_factory=dict)
    module: dict[str, dict[str, object]] = field(default_factory=dict)
    owner: dict[str, object] = field(default_factory=dict)
    fixed_position: dict[str, object] = field(default_factory=dict)
    time_sync: dict[str, object] = field(default_factory=dict)
    actions: dict[str, bool] = field(default_factory=dict)


def _is_redacted_secret_placeholder(key: str | None, value: object) -> bool:
    if not key or not isinstance(value, str):
        return False
    if value.strip().lower() != "<redacted>":
        return False
    return is_sensitive_key(key, SENSITIVE_FIELD_NAMES)


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


def _clean_update_value(value: object, *, parent_key: str | None = None) -> object | None:
    if _is_redacted_secret_placeholder(parent_key, value):
        return None
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
            clean_v = _clean_update_value(v, parent_key=k)
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
        clean_value = _clean_update_value(value, parent_key=key)
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
        if key in {
            "reset_nodedb",
            "reset_dashboard_db",
            "set_time",
            "regenerate_node_id",
            "set_fixed_position",
            "clear_fixed_position",
        }:
            actions[key] = _coerce_bool(value)
    return actions


def _clean_owner(payload: object) -> dict[str, object]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("Expected 'owner' to be an object")

    clean: dict[str, object] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        normalized = key.strip().lower()
        if normalized in {"short_name", "shortname", "short"}:
            if value is None:
                clean["short_name"] = None
            elif isinstance(value, (str, int, float, bool)):
                clean["short_name"] = str(value)
        elif normalized in {"long_name", "longname", "long"}:
            if value is None:
                clean["long_name"] = None
            elif isinstance(value, (str, int, float, bool)):
                clean["long_name"] = str(value)
        elif normalized in {"is_licensed", "islicensed"}:
            clean["is_licensed"] = _coerce_bool(value)
        elif normalized in {"is_unmessagable", "isunmessagable"}:
            clean["is_unmessagable"] = _coerce_bool(value)
    return clean


def _clean_fixed_position(payload: object) -> dict[str, object]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("Expected 'fixed_position' to be an object")

    clean: dict[str, object] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        clean_value = _clean_update_value(value)
        if clean_value is None and value is not None:
            continue

        normalized = key.strip().lower()
        if normalized in {"lat", "latitude"}:
            clean["lat"] = clean_value
        elif normalized in {"lon", "lng", "longitude"}:
            clean["lon"] = clean_value
        elif normalized in {"alt", "altitude"}:
            clean["alt"] = clean_value
    return clean


def _clean_time_sync(payload: object) -> dict[str, object]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("Expected 'time_sync' to be an object")

    clean: dict[str, object] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        normalized = key.strip().lower()
        if normalized in {"enabled", "enable", "use_time_server", "use_server", "ntp_enabled"}:
            clean["enabled"] = _coerce_bool(value)
            continue

        clean_value = _clean_update_value(value)
        if clean_value is None and value is not None:
            continue

        if normalized in {"server", "ntp_server", "time_server", "host"}:
            clean["server"] = clean_value
        elif normalized in {"timezone", "tz"}:
            clean["timezone"] = clean_value
        elif normalized in {"timeout", "timeout_ms", "request_timeout_ms"}:
            clean["timeout_ms"] = clean_value
    return clean


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
    clean_owner = _clean_owner(payload.get("owner"))
    clean_fixed_position = _clean_fixed_position(payload.get("fixed_position"))
    clean_time_sync = _clean_time_sync(payload.get("time_sync"))
    clean_actions = _clean_actions(payload.get("actions"))

    if "reset_nodedb" not in clean_actions and "reset_nodedb" in payload:
        clean_actions["reset_nodedb"] = _coerce_bool(payload.get("reset_nodedb"))
    if "reset_dashboard_db" not in clean_actions and "reset_dashboard_db" in payload:
        clean_actions["reset_dashboard_db"] = _coerce_bool(payload.get("reset_dashboard_db"))
    if "set_time" not in clean_actions and "set_time" in payload:
        clean_actions["set_time"] = _coerce_bool(payload.get("set_time"))
    if "regenerate_node_id" not in clean_actions and "regenerate_node_id" in payload:
        clean_actions["regenerate_node_id"] = _coerce_bool(payload.get("regenerate_node_id"))
    if "set_fixed_position" not in clean_actions and "set_fixed_position" in payload:
        clean_actions["set_fixed_position"] = _coerce_bool(payload.get("set_fixed_position"))
    if "clear_fixed_position" not in clean_actions and "clear_fixed_position" in payload:
        clean_actions["clear_fixed_position"] = _coerce_bool(payload.get("clear_fixed_position"))

    return RadioSettingsRequest(
        lora=clean_lora,
        local=clean_local,
        module=clean_module,
        owner=clean_owner,
        fixed_position=clean_fixed_position,
        time_sync=clean_time_sync,
        actions=clean_actions,
    )
