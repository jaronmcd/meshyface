import json
from pathlib import Path
from typing import Callable, Optional

from .theme import build_palette_theme_preset


ThemeTokens = dict[str, str]
ThemePreset = dict[str, ThemeTokens]
ThemePresetMap = dict[str, ThemePreset]
ThemePresetCustomSettingsMap = dict[str, dict[str, object]]

_DEPRECATED_THEME_TOKENS = frozenset(
    "--" + name
    for name in (
        "bg",
        "panel",
        "line",
        "ink",
        "accent",
        "accent-2",
        "muted",
        "danger",
        "shadow",
    )
)

_DEFAULT_THEME_SETTINGS: dict[str, object] = {
    "base_color": "#003a73",
    "line_color": "#2f8cff",
    "line_contrast_color": "#d8ecff",
    "text_font": "system",
    "color_depth": 32,
    "foreground_transparency": 0,
    "foreground_blur": 0,
    "gradient_primary_start_color": "#003a73",
    "gradient_primary_end_color": "#060d1f",
    "gradient_primary_type": "linear",
    "gradient_primary_direction": "right",
    "background_type": "particles",
    "background_image_data": "",
    "background_image_layout": "cover",
    "background_image_darken": 0,
    "particles_enabled": False,
    "particles_color": "#d8ecff",
    "particles_link_color": "#d8ecff",
    "livemap_link_color": "#d8ecff",
    "particles_count": 72,
    "particles_speed": 2,
    "particles_size": 2,
    "particles_opacity": 42,
    "particles_links": False,
    "livemap_layers": {
        "roads": True,
        "railroads": True,
        "rivers": True,
        "lakes": True,
        "parks": True,
        "urban": True,
        "states": True,
        "borders": True,
        "coastline": True,
        "cities": True,
    },
}


def default_theme_presets() -> ThemePresetMap:
    return {
        "default": build_palette_theme_preset(
            _DEFAULT_THEME_SETTINGS["base_color"],
            line_color=_DEFAULT_THEME_SETTINGS["line_color"],
            line_contrast_color=_DEFAULT_THEME_SETTINGS["line_contrast_color"],
            text_font=_DEFAULT_THEME_SETTINGS["text_font"],
            color_depth=int(_DEFAULT_THEME_SETTINGS["color_depth"]),
            foreground_transparency=int(_DEFAULT_THEME_SETTINGS["foreground_transparency"]),
            foreground_blur=int(_DEFAULT_THEME_SETTINGS["foreground_blur"]),
            gradient_primary_start_color=_DEFAULT_THEME_SETTINGS["gradient_primary_start_color"],
            gradient_primary_end_color=_DEFAULT_THEME_SETTINGS["gradient_primary_end_color"],
            gradient_primary_type=_DEFAULT_THEME_SETTINGS["gradient_primary_type"],
            gradient_primary_direction=_DEFAULT_THEME_SETTINGS["gradient_primary_direction"],
        ),
    }


def default_theme_preset_custom_settings() -> ThemePresetCustomSettingsMap:
    return {
        "default": {
            key: dict(value) if isinstance(value, dict) else value
            for key, value in _DEFAULT_THEME_SETTINGS.items()
        }
    }


def _normalize_theme_tokens(
    raw_tokens: object,
    *,
    required_keys: set[str],
) -> Optional[ThemeTokens]:
    if not isinstance(raw_tokens, dict):
        return None
    normalized = {
        str(key): str(value)
        for key, value in raw_tokens.items()
        if str(key) not in _DEPRECATED_THEME_TOKENS
    }
    if not required_keys.issubset(set(normalized.keys())):
        return None
    return normalized


def _normalize_theme_preset(
    raw_preset: object,
    *,
    required_light_keys: set[str],
    required_dark_keys: set[str],
) -> Optional[ThemePreset]:
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
    json_loads_fn: Callable[[str], object] = json.loads,
    default_presets_fn: Callable[[], ThemePresetMap] = default_theme_presets,
) -> ThemePresetMap:
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
    presets: ThemePresetMap,
    preset_name: Optional[str],
    *,
    fallback_name: str = "default",
) -> ThemePreset:
    if preset_name:
        selected = presets.get(str(preset_name))
        if isinstance(selected, dict):
            return selected
    return presets[fallback_name]
