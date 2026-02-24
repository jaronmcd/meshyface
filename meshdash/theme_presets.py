import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .theme import DARK_THEME_VARS, LIGHT_THEME_VARS


def _copy_theme_tokens(tokens: Dict[str, str]) -> Dict[str, str]:
    return {str(key): str(value) for key, value in tokens.items()}


def default_theme_presets() -> Dict[str, Dict[str, Dict[str, str]]]:
    return {
        "default": {
            "light": _copy_theme_tokens(LIGHT_THEME_VARS),
            "dark": _copy_theme_tokens(DARK_THEME_VARS),
        }
    }


def _normalize_theme_tokens(
    raw_tokens: Any,
    *,
    required_keys: set[str],
) -> Optional[Dict[str, str]]:
    if not isinstance(raw_tokens, dict):
        return None
    normalized = {str(key): str(value) for key, value in raw_tokens.items()}
    if not required_keys.issubset(set(normalized.keys())):
        return None
    return normalized


def _normalize_theme_preset(
    raw_preset: Any,
    *,
    required_light_keys: set[str],
    required_dark_keys: set[str],
) -> Optional[Dict[str, Dict[str, str]]]:
    if not isinstance(raw_preset, dict):
        return None
    light_tokens = _normalize_theme_tokens(
        raw_preset.get("light"),
        required_keys=required_light_keys,
    )
    dark_tokens = _normalize_theme_tokens(
        raw_preset.get("dark"),
        required_keys=required_dark_keys,
    )
    if light_tokens is None or dark_tokens is None:
        return None
    return {
        "light": light_tokens,
        "dark": dark_tokens,
    }


def load_theme_presets(
    presets_path: Optional[str],
    *,
    read_text_fn: Optional[Callable[[str], str]] = None,
    json_loads_fn: Callable[[str], Any] = json.loads,
    default_presets_fn: Callable[[], Dict[str, Dict[str, Dict[str, str]]]] = default_theme_presets,
) -> Dict[str, Dict[str, Dict[str, str]]]:
    presets = default_presets_fn()
    if not presets_path:
        return presets

    try:
        if read_text_fn is not None:
            raw_text = read_text_fn(presets_path)
        else:
            raw_text = Path(presets_path).read_text(encoding="utf-8")
        raw_data = json_loads_fn(raw_text)
    except Exception:
        return presets

    if not isinstance(raw_data, dict):
        return presets

    required_light_keys = set(presets["default"]["light"].keys())
    required_dark_keys = set(presets["default"]["dark"].keys())
    for preset_name, preset_data in raw_data.items():
        normalized = _normalize_theme_preset(
            preset_data,
            required_light_keys=required_light_keys,
            required_dark_keys=required_dark_keys,
        )
        if normalized is None:
            continue
        presets[str(preset_name)] = normalized
    return presets


def select_theme_preset(
    presets: Dict[str, Dict[str, Dict[str, str]]],
    preset_name: Optional[str],
    *,
    fallback_name: str = "default",
) -> Dict[str, Dict[str, str]]:
    if preset_name:
        selected = presets.get(str(preset_name))
        if isinstance(selected, dict):
            return selected
    return presets[fallback_name]
