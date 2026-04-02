import json
from pathlib import Path
from typing import Optional

from .bot_commands import normalize_bot_command_name

DEFAULT_BOT_SETTINGS_FILE = "mesh_dashboard_bot_settings.json"


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


def _parse_disabled_commands(value: object) -> Optional[list[str]]:
    if not isinstance(value, list):
        return None
    out: list[str] = []
    seen: set[str] = set()
    for raw in value:
        clean = normalize_bot_command_name(raw)
        if not clean or clean in seen:
            continue
        out.append(clean)
        seen.add(clean)
    return out


def _parse_string_list(
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


def _parse_text_value(
    value: object,
    *,
    max_chars: int,
) -> str:
    clean = str(value or "").strip()
    if len(clean) > max_chars:
        clean = clean[:max_chars].rstrip()
    return clean


def load_persisted_bot_settings(settings_path: Optional[str]) -> dict[str, object]:
    if not settings_path:
        return {}
    try:
        payload = json.loads(Path(settings_path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    out: dict[str, object] = {}
    enabled = _parse_optional_bool_token(payload.get("enabled"))
    log_enabled = _parse_optional_bool_token(payload.get("log_enabled", payload.get("logEnabled")))
    game_enabled = _parse_optional_bool_token(payload.get("game_enabled", payload.get("gameEnabled")))
    game_public_start_enabled = _parse_optional_bool_token(
        payload.get("game_public_start_enabled", payload.get("gamePublicStartEnabled"))
    )
    disabled_commands = _parse_disabled_commands(
        payload.get("disabled_commands", payload.get("disabledCommands"))
    )
    if enabled is not None:
        out["enabled"] = enabled
    if log_enabled is not None:
        out["log_enabled"] = log_enabled
    if game_enabled is not None:
        out["game_enabled"] = game_enabled
    if game_public_start_enabled is not None:
        out["game_public_start_enabled"] = game_public_start_enabled
    if disabled_commands is not None:
        out["disabled_commands"] = disabled_commands
    ping_triggers = _parse_string_list(
        payload.get("ping_triggers", payload.get("pingTriggers")),
        split_commas=True,
        max_items=64,
        max_item_chars=160,
    )
    if ping_triggers is not None:
        out["ping_triggers"] = ping_triggers
    if "ping_response_template" in payload or "pingResponseTemplate" in payload:
        out["ping_response_template"] = _parse_text_value(
            payload.get("ping_response_template", payload.get("pingResponseTemplate")),
            max_chars=240,
        )
    pull_reel_symbols = _parse_string_list(
        payload.get("pull_reel_symbols", payload.get("pullReelSymbols")),
        split_commas=True,
        max_items=24,
        max_item_chars=16,
    )
    if pull_reel_symbols is not None:
        out["pull_reel_symbols"] = pull_reel_symbols
    if "pull_response_template" in payload or "pullResponseTemplate" in payload:
        out["pull_response_template"] = _parse_text_value(
            payload.get("pull_response_template", payload.get("pullResponseTemplate")),
            max_chars=280,
        )
    joke_triggers = _parse_string_list(
        payload.get("joke_triggers", payload.get("jokeTriggers")),
        split_commas=True,
        max_items=64,
        max_item_chars=160,
    )
    if joke_triggers is not None:
        out["joke_triggers"] = joke_triggers
    zork_triggers = _parse_string_list(
        payload.get("zork_triggers", payload.get("zorkTriggers")),
        split_commas=True,
        max_items=64,
        max_item_chars=160,
    )
    if zork_triggers is not None:
        out["zork_triggers"] = zork_triggers
    hard_disabled_incoming_commands = _parse_string_list(
        payload.get(
            "hard_disabled_incoming_commands",
            payload.get("hardDisabledIncomingCommands"),
        ),
        split_commas=True,
        max_items=128,
        max_item_chars=64,
    )
    if hard_disabled_incoming_commands is not None:
        out["hard_disabled_incoming_commands"] = hard_disabled_incoming_commands
    joke_lines = _parse_string_list(
        payload.get("joke_lines", payload.get("jokeLines")),
        split_commas=False,
        max_items=600,
        max_item_chars=240,
    )
    if joke_lines is not None:
        out["joke_lines"] = joke_lines
    joke_near_guess_lines = _parse_string_list(
        payload.get("joke_near_guess_lines", payload.get("jokeNearGuessLines")),
        split_commas=False,
        max_items=300,
        max_item_chars=240,
    )
    if joke_near_guess_lines is not None:
        out["joke_near_guess_lines"] = joke_near_guess_lines
    joke_delay_punchline_enabled = _parse_optional_bool_token(
        payload.get(
            "joke_delay_punchline_enabled",
            payload.get("jokeDelayPunchlineEnabled"),
        )
    )
    if joke_delay_punchline_enabled is not None:
        out["joke_delay_punchline_enabled"] = joke_delay_punchline_enabled
    return out


def save_persisted_bot_settings(
    settings_path: Optional[str],
    settings: dict[str, object],
) -> Optional[str]:
    if not settings_path:
        return None
    path = Path(settings_path)
    payload = {
        "enabled": bool(settings.get("enabled")),
        "log_enabled": bool(settings.get("log_enabled")),
        "game_enabled": bool(settings.get("game_enabled")),
        "game_public_start_enabled": bool(settings.get("game_public_start_enabled")),
        "disabled_commands": sorted(
            {
                clean
                for clean in (
                    normalize_bot_command_name(value)
                    for value in (settings.get("disabled_commands") or [])
                )
                if clean
            }
        ),
        "ping_triggers": [
            item
            for item in (
                str(value or "").strip()
                for value in (settings.get("ping_triggers") or [])
            )
            if item
        ],
        "ping_response_template": _parse_text_value(
            settings.get("ping_response_template"),
            max_chars=240,
        ),
        "pull_reel_symbols": [
            item
            for item in (
                str(value or "").strip()
                for value in (settings.get("pull_reel_symbols") or [])
            )
            if item
        ],
        "pull_response_template": _parse_text_value(
            settings.get("pull_response_template"),
            max_chars=280,
        ),
        "joke_triggers": [
            item
            for item in (
                str(value or "").strip()
                for value in (settings.get("joke_triggers") or [])
            )
            if item
        ],
        "zork_triggers": [
            item
            for item in (
                str(value or "").strip()
                for value in (settings.get("zork_triggers") or [])
            )
            if item
        ],
        "hard_disabled_incoming_commands": [
            item
            for item in (
                str(value or "").strip()
                for value in (settings.get("hard_disabled_incoming_commands") or [])
            )
            if item
        ],
        "joke_lines": [
            item
            for item in (
                str(value or "").strip()
                for value in (settings.get("joke_lines") or [])
            )
            if item
        ],
        "joke_near_guess_lines": [
            item
            for item in (
                str(value or "").strip()
                for value in (settings.get("joke_near_guess_lines") or [])
            )
            if item
        ],
        "joke_delay_punchline_enabled": bool(
            settings.get("joke_delay_punchline_enabled")
        ),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(path)
    except Exception as exc:
        return str(exc)
    return None
