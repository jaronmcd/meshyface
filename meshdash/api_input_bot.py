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


def _parse_string_list_payload(
    value: object,
    *,
    split_commas: bool,
    max_items: int,
    max_item_chars: int,
) -> Optional[list[str]]:
    explicit_list = isinstance(value, list)
    raw_items: list[object]
    if explicit_list:
        raw_items = list(value)
    else:
        text = str(value or "").strip()
        if not text:
            return None
        normalized = text.replace(";", "\n")
        if split_commas:
            normalized = normalized.replace(",", "\n")
        raw_items = normalized.splitlines()
    out: list[str] = []
    seen: set[str] = set()
    for raw_item in raw_items:
        item = str(raw_item or "").strip()
        if not item:
            continue
        if len(item) > max_item_chars:
            item = item[:max_item_chars].rstrip()
        if not item:
            continue
        dedupe_key = item.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        out.append(item)
        if len(out) >= max_items:
            break
    if out:
        return out
    if explicit_list:
        return []
    return None


@dataclass(frozen=True)
class BotSettingsRequest:
    enabled: Optional[bool] = None
    log_enabled: Optional[bool] = None
    game_enabled: Optional[bool] = None
    game_public_start_enabled: Optional[bool] = None
    command_settings: Optional[dict[str, bool]] = None
    joke_triggers: Optional[list[str]] = None
    joke_lines: Optional[list[str]] = None
    joke_delay_punchline_enabled: Optional[bool] = None


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
        game_public_start_enabled=_parse_optional_bool_token(
            payload.get("game_public_start_enabled", payload.get("gamePublicStartEnabled"))
        ),
        command_settings=_parse_command_settings_payload(
            payload.get("command_settings", payload.get("commandSettings"))
        ),
        joke_triggers=_parse_string_list_payload(
            payload.get("joke_triggers", payload.get("jokeTriggers")),
            split_commas=True,
            max_items=64,
            max_item_chars=160,
        ),
        joke_lines=_parse_string_list_payload(
            payload.get("joke_lines", payload.get("jokeLines")),
            split_commas=False,
            max_items=600,
            max_item_chars=240,
        ),
        joke_delay_punchline_enabled=_parse_optional_bool_token(
            payload.get(
                "joke_delay_punchline_enabled",
                payload.get("jokeDelayPunchlineEnabled"),
            )
        ),
    )
