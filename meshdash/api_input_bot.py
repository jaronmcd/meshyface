import json
from dataclasses import dataclass
from typing import Optional

from .bot_commands import normalize_bot_command_name


def _parse_optional_bool_token(value: object) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value == 1:
            return True
        if value == 0:
            return False
    text = str(value).strip().lower()
    if not text:
        return None
    if text in ("1", "true", "yes", "on", "enable", "enabled"):
        return True
    if text in ("0", "false", "no", "off", "disable", "disabled"):
        return False
    return None


def _parse_command_settings_payload(value: object) -> Optional[dict[str, bool]]:
    if not isinstance(value, dict):
        return None
    out: dict[str, bool] = {}
    for raw_name, raw_enabled in value.items():
        name = normalize_bot_command_name(raw_name)
        enabled = _parse_optional_bool_token(raw_enabled)
        if not name or enabled is None:
            continue
        out[name] = enabled
    return out or None


@dataclass(frozen=True)
class BotSettingsRequest:
    enabled: Optional[bool] = None
    log_enabled: Optional[bool] = None
    game_enabled: Optional[bool] = None
    command_settings: Optional[dict[str, bool]] = None


def parse_bot_settings_request(raw_body: bytes) -> BotSettingsRequest:
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except Exception:
        body = {}
    payload = body if isinstance(body, dict) else {}
    return BotSettingsRequest(
        enabled=_parse_optional_bool_token(payload.get("enabled")),
        log_enabled=_parse_optional_bool_token(
            payload.get("log_enabled", payload.get("logEnabled"))
        ),
        game_enabled=_parse_optional_bool_token(
            payload.get("game_enabled", payload.get("gameEnabled"))
        ),
        command_settings=_parse_command_settings_payload(
            payload.get("command_settings", payload.get("commandSettings"))
        ),
    )
