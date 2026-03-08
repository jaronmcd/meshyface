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
    disabled_commands = _parse_disabled_commands(
        payload.get("disabled_commands", payload.get("disabledCommands"))
    )
    if enabled is not None:
        out["enabled"] = enabled
    if log_enabled is not None:
        out["log_enabled"] = log_enabled
    if game_enabled is not None:
        out["game_enabled"] = game_enabled
    if disabled_commands is not None:
        out["disabled_commands"] = disabled_commands
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

