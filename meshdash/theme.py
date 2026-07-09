import colorsys
import math
import re
from typing import Dict, Optional

# Single source of truth for dashboard theme tokens.
# Keep palette changes here so CSS values stay centralized.
LIGHT_THEME_VARS: Dict[str, str] = {
    "--bg": "#d4e1f9",
    "--ink": "#1d2a46",
    "--panel": "#f4f8fe",
    "--line": "#4266d0",
    "--accent": "#5b8def",
    "--accent-2": "#4870bd",
    "--ui-bg": "#d4e1f9",
    "--ui-bg-elev": "#eef4fd",
    "--ui-panel": "#f4f8fe",
    "--ui-panel-alt": "#e9f0fc",
    "--ui-border": "#4266d0",
    "--ui-text": "#111827",
    "--ui-text-soft": "#636c7f",
    "--ui-accent": "#5b8def",
    "--ui-accent-soft": "#4870bd",
    "--theme-font-family": "\"IBM Plex Sans\", \"Segoe UI\", sans-serif",
    "--theme-text-color": "#111827",
    "--theme-text-color-strong": "#0e1421",
    "--theme-text-color-soft": "#404859",
    "--theme-text-color-muted": "#636c7f",
    "--theme-text-color-accent": "#25385d",
    "--theme-text-color-on-fill": "#0f172a",
    "--theme-text-color-code": "#1a263f",
    "--theme-base-color": "#5b8def",
    "--theme-background-gradient": "linear-gradient(to bottom, #eff2f7, #eff2f7)",
    "--theme-background-gradient-start": "#eff2f7",
    "--theme-background-gradient-end": "#eff2f7",
    "--theme-gradient-primary": "linear-gradient(to bottom, #eff2f7, #eff2f7)",
    "--theme-gradient-primary-start": "#eff2f7",
    "--theme-gradient-primary-end": "#eff2f7",
    "--theme-gradient-secondary": "linear-gradient(to bottom, #eff2f7, #eff2f7)",
    "--theme-gradient-secondary-start": "#eff2f7",
    "--theme-gradient-secondary-end": "#eff2f7",
    "--theme-foreground-transparency": "0",
    "--theme-foreground-blur": "none",
    "--ui-link": "#25385d",
    "--ui-shadow": "0 10px 24px rgba(24, 37, 62, 0.116)",
    "--workspace-shell-bg": "#f4f8fe",
    "--workspace-shell-bg-alt": "#e9f0fc",
    "--workspace-shell-border": "#4266d0",
    "--workspace-shell-border-muted": "#748fdd",
    "--workspace-shell-border-strong": "#456bc6",
    "--workspace-shell-text": "#111827",
    "--workspace-shell-text-soft": "#636c7f",
    "--workspace-shell-hover-bg": "#d7e3fa",
    "--workspace-shell-active-bg": "#cddcf9",
    "--workspace-shell-active-text": "#25385d",
    "--workspace-shell-divider-bg": "linear-gradient(to right, #dee8fb, #c0d2f3)",
    "--workspace-shell-divider-line": "#748fdd",
    "--workspace-shell-divider-line-active": "#4266d0",
    "--workspace-shell-shadow": "0 12px 28px rgba(24, 37, 62, 0.168)",
    "--danger": "#c53030",
    "--muted": "#5f7397",
    "--shadow": "0 10px 24px rgba(24, 37, 62, 0.116)",
    "--surface-tint-color": "#4270f0",
    "--surface-tint-bg-soft": "#ffffff",
    "--surface-tint-bg": "#ffffff",
    "--surface-tint-bg-alt": "#ffffff",
    "--surface-tint-bg-hover": "#ffffff",
    "--surface-tint-vignette": "radial-gradient(ellipse at center, transparent 58%, rgba(34, 57, 117, 0) 100%)",
    "--surface-tint-border": "#7797d2",
    "--surface-tint-border-strong": "#627cac",
    "--surface-tint-text": "#1d2a46",
    "--surface-tint-text-soft": "#5f7397",
    "--surface-tint-divider-bg": "linear-gradient(to right, #ffffff, #ffffff)",
    "--surface-tint-divider-line": "#627cac",
    "--surface-tint-start-hue": "224",
    "--surface-tint-end-hue": "252",
    "--surface-tint-outline-hue": "232",
}

DARK_THEME_VARS: Dict[str, str] = {
    "--ui-bg": "#182336",
    "--ui-bg-elev": "#1c2b47",
    "--ui-panel": "#223049",
    "--ui-panel-alt": "#273957",
    "--ui-border": "#4c62b3",
    "--ui-text": "#dae4f3",
    "--ui-text-soft": "#a9bbd5",
    "--ui-accent": "#83aaf3",
    "--ui-accent-soft": "#5b8def",
    "--theme-font-family": "\"IBM Plex Sans\", \"Segoe UI\", sans-serif",
    "--theme-text-color": "#e6edf3",
    "--theme-text-color-strong": "#eaf0f5",
    "--theme-text-color-soft": "#bfc9d6",
    "--theme-text-color-muted": "#a1adbf",
    "--theme-text-color-accent": "#c4d6f3",
    "--theme-text-color-on-fill": "#0f172a",
    "--theme-text-color-code": "#d4e1f3",
    "--theme-base-color": "#5b8def",
    "--theme-background-gradient": "linear-gradient(to bottom, #0e121b, #171d2c)",
    "--theme-background-gradient-start": "#0e121b",
    "--theme-background-gradient-end": "#171d2c",
    "--theme-gradient-primary": "linear-gradient(to bottom, #0e121b, #171d2c)",
    "--theme-gradient-primary-start": "#0e121b",
    "--theme-gradient-primary-end": "#171d2c",
    "--theme-gradient-secondary": "linear-gradient(to bottom, #0e121b, #171d2c)",
    "--theme-gradient-secondary-start": "#0e121b",
    "--theme-gradient-secondary-end": "#171d2c",
    "--theme-foreground-transparency": "0",
    "--theme-foreground-blur": "none",
    "--ui-link": "#a5cafa",
    "--ui-shadow": "0 10px 24px rgba(15, 23, 38, 0.408)",
    "--workspace-shell-bg": "#253a63",
    "--workspace-shell-bg-alt": "#263b65",
    "--workspace-shell-border": "#4d65be",
    "--workspace-shell-border-muted": "#41569d",
    "--workspace-shell-border-strong": "#5266bb",
    "--workspace-shell-text": "#d1def3",
    "--workspace-shell-text-soft": "#acbdd8",
    "--workspace-shell-hover-bg": "#29426f",
    "--workspace-shell-active-bg": "#375c9a",
    "--workspace-shell-active-text": "#bdd6fb",
    "--workspace-shell-divider-bg": "linear-gradient(to right, #2a4270, #314875)",
    "--workspace-shell-divider-line": "#41569d",
    "--workspace-shell-divider-line-active": "#4d65be",
    "--workspace-shell-shadow": "0 12px 28px rgba(11, 17, 29, 0.52)",
    "--surface-tint-color": "#4270f0",
    "--surface-tint-bg-soft": "#263b65",
    "--surface-tint-bg": "#253a63",
    "--surface-tint-bg-alt": "#263b65",
    "--surface-tint-bg-hover": "#29426f",
    "--surface-tint-vignette": "radial-gradient(ellipse at center, transparent 58%, rgba(18, 31, 67, 0) 100%)",
    "--surface-tint-border": "#41569d",
    "--surface-tint-border-strong": "#4d65be",
    "--surface-tint-text": "#d1def3",
    "--surface-tint-text-soft": "#acbdd8",
    "--surface-tint-divider-bg": "linear-gradient(to right, #263b65, #263b65)",
    "--surface-tint-divider-line": "#41569d",
    "--surface-tint-start-hue": "224",
    "--surface-tint-end-hue": "252",
    "--surface-tint-outline-hue": "232",
}

DEFAULT_THEME_BASE_COLOR = "#2563eb"
DEFAULT_THEME_LINE_COLOR = DEFAULT_THEME_BASE_COLOR
DEFAULT_THEME_LINE_CONTRAST_COLOR = "#ffffff"
DEFAULT_THEME_COLOR_DEPTH = 58
DEFAULT_THEME_GRADIENT_TYPE = "linear"
DEFAULT_THEME_GRADIENT_DIRECTION = "right"
DEFAULT_THEME_SECONDARY_GRADIENT_DIRECTION = "down-right"
DEFAULT_THEME_FOREGROUND_TRANSPARENCY = 0
DEFAULT_THEME_FOREGROUND_BLUR = 0
DEFAULT_THEME_TEXT_COLOR = DARK_THEME_VARS["--ui-text"]
DEFAULT_THEME_TEXT_FONT = "system"
DEFAULT_CUSTOM_THEME_BASE_COLOR = "#007bff"
DEFAULT_CUSTOM_THEME_LINE_COLOR = "#0da6ff"
DEFAULT_CUSTOM_THEME_LINE_CONTRAST_COLOR = "#4f55ff"
DEFAULT_CUSTOM_THEME_COLOR_DEPTH = 44
DEFAULT_CUSTOM_THEME_TEXT_FONT = DEFAULT_THEME_TEXT_FONT
DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_START_COLOR = "#00356e"
DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_END_COLOR = "#060d1f"
DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_TYPE = "linear"
DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_DIRECTION = "right"
DEFAULT_CUSTOM_THEME_FOREGROUND_TRANSPARENCY = 39
DEFAULT_CUSTOM_THEME_FOREGROUND_BLUR = 0
DEFAULT_THEME_BACKGROUND_TYPE = "particles"
DEFAULT_CUSTOM_THEME_BACKGROUND_TYPE = DEFAULT_THEME_BACKGROUND_TYPE
DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_DATA = ""
DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_LAYOUT = "cover"
DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_DARKEN = 0
DEFAULT_CUSTOM_THEME_PARTICLES_ENABLED = True
DEFAULT_CUSTOM_THEME_PARTICLES_COLOR = "#548dff"
DEFAULT_CUSTOM_THEME_PARTICLES_LINK_COLOR = DEFAULT_CUSTOM_THEME_LINE_CONTRAST_COLOR
DEFAULT_CUSTOM_THEME_LIVEMAP_LINK_COLOR = DEFAULT_CUSTOM_THEME_LINE_CONTRAST_COLOR
DEFAULT_CUSTOM_THEME_PARTICLES_COUNT = 50
DEFAULT_CUSTOM_THEME_PARTICLES_SPEED = 0.2
DEFAULT_CUSTOM_THEME_PARTICLES_SIZE = 2
DEFAULT_CUSTOM_THEME_PARTICLES_OPACITY = 88
DEFAULT_CUSTOM_THEME_PARTICLES_LINKS = True
DEFAULT_CUSTOM_THEME_LIVEMAP_LAYERS = {
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
}
MAX_THEME_BACKGROUND_IMAGE_DATA_LENGTH = 4_000_000
_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_BACKGROUND_IMAGE_DATA_RE = re.compile(
    r"^data:image/(?:png|jpeg|gif|webp|avif);base64,[A-Za-z0-9+/=]+$"
)
_THEME_TEXT_FONT_STACKS = {
    "system": "\"IBM Plex Sans\", \"Segoe UI\", sans-serif",
    "compact": "\"Bahnschrift\", \"Arial Narrow\", \"IBM Plex Sans\", \"Segoe UI\", sans-serif",
    "rounded": "\"Aptos\", \"Segoe UI Variable\", \"Nunito\", \"IBM Plex Sans\", sans-serif",
    "mono": "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \"Liberation Mono\", monospace",
    "serif": "Georgia, \"Times New Roman\", serif",
}
_THEME_BACKGROUND_TYPES = {"particles", "livemap", "image"}
_THEME_BACKGROUND_IMAGE_LAYOUTS = {"cover", "contain", "stretch", "center", "tile"}
_THEME_LIVEMAP_LAYER_KEYS = tuple(DEFAULT_CUSTOM_THEME_LIVEMAP_LAYERS.keys())
_THEME_GRADIENT_TYPES = {"linear", "radial"}
_THEME_GRADIENT_DIRECTIONS = {
    "right": {
        "linear": "to right",
        "radial": "circle at left center",
    },
    "left": {
        "linear": "to left",
        "radial": "circle at right center",
    },
    "down": {
        "linear": "to bottom",
        "radial": "circle at center top",
    },
    "up": {
        "linear": "to top",
        "radial": "circle at center bottom",
    },
    "down-right": {
        "linear": "135deg",
        "radial": "circle at top left",
    },
    "down-left": {
        "linear": "225deg",
        "radial": "circle at top right",
    },
    "up-right": {
        "linear": "45deg",
        "radial": "circle at bottom left",
    },
    "up-left": {
        "linear": "315deg",
        "radial": "circle at bottom right",
    },
    "center": {
        "linear": "to right",
        "radial": "circle at center",
    },
}


def normalize_theme_base_color(
    value: object,
    *,
    fallback: str = DEFAULT_THEME_BASE_COLOR,
) -> str:
    clean = str(value or "").strip()
    if not _HEX_COLOR_RE.fullmatch(clean):
        clean = str(fallback).strip()
    if len(clean) == 4:
        clean = "#" + "".join(ch * 2 for ch in clean[1:])
    return clean.lower()


def normalize_theme_line_color(
    value: object,
    *,
    fallback: str = DEFAULT_THEME_LINE_COLOR,
) -> str:
    return normalize_theme_base_color(value, fallback=fallback)


def normalize_theme_line_contrast_color(
    value: object,
    *,
    fallback: str = DEFAULT_THEME_LINE_CONTRAST_COLOR,
) -> str:
    return normalize_theme_base_color(value, fallback=fallback)


def normalize_theme_color_depth(
    value: object,
    *,
    fallback: int = DEFAULT_THEME_COLOR_DEPTH,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(fallback)
    return max(0, min(100, parsed))


def normalize_theme_text_font(
    value: object,
    *,
    fallback: str = DEFAULT_THEME_TEXT_FONT,
) -> str:
    clean = str(value or "").strip().lower()
    if clean in _THEME_TEXT_FONT_STACKS:
        return clean
    fallback_clean = str(fallback or "").strip().lower()
    if fallback_clean in _THEME_TEXT_FONT_STACKS:
        return fallback_clean
    return DEFAULT_THEME_TEXT_FONT


def theme_text_font_stack(value: object) -> str:
    return _THEME_TEXT_FONT_STACKS[normalize_theme_text_font(value)]


def normalize_theme_foreground_transparency(
    value: object,
    *,
    fallback: int = DEFAULT_THEME_FOREGROUND_TRANSPARENCY,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(fallback)
    return max(0, min(90, parsed))


def normalize_theme_foreground_blur(
    value: object,
    *,
    fallback: int = DEFAULT_THEME_FOREGROUND_BLUR,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(fallback)
    return max(0, min(40, parsed))


def theme_foreground_blur_css(value: object) -> str:
    clean = normalize_theme_foreground_blur(value)
    if clean <= 0:
        return "none"
    return f"blur({clean}px)"


def normalize_theme_background_type(
    value: object,
    *,
    fallback: str = DEFAULT_THEME_BACKGROUND_TYPE,
) -> str:
    clean = str(value or "").strip().lower()
    if clean in {"live-map", "live_map", "map"}:
        clean = "livemap"
    if clean in _THEME_BACKGROUND_TYPES:
        return clean
    fallback_clean = str(fallback or "").strip().lower()
    if fallback_clean in _THEME_BACKGROUND_TYPES:
        return fallback_clean
    return DEFAULT_THEME_BACKGROUND_TYPE


def normalize_theme_background_image_data(
    value: object,
    *,
    fallback: str = DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_DATA,
) -> str:
    clean = str(value or "").strip()
    fallback_clean = str(fallback or "").strip()
    if not clean:
        return fallback_clean if _BACKGROUND_IMAGE_DATA_RE.match(fallback_clean) else ""
    if len(clean) > MAX_THEME_BACKGROUND_IMAGE_DATA_LENGTH:
        return fallback_clean if _BACKGROUND_IMAGE_DATA_RE.match(fallback_clean) else ""
    if _BACKGROUND_IMAGE_DATA_RE.match(clean):
        return clean
    return fallback_clean if _BACKGROUND_IMAGE_DATA_RE.match(fallback_clean) else ""


def normalize_theme_background_image_layout(
    value: object,
    *,
    fallback: str = DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_LAYOUT,
) -> str:
    clean = str(value or "").strip().lower()
    aliases = {
        "fill": "cover",
        "fit": "contain",
        "fit-screen": "contain",
        "fit_screen": "contain",
        "full": "stretch",
        "stretched": "stretch",
        "repeat": "tile",
        "tiled": "tile",
        "centered": "center",
    }
    clean = aliases.get(clean, clean)
    if clean in _THEME_BACKGROUND_IMAGE_LAYOUTS:
        return clean
    fallback_clean = aliases.get(str(fallback or "").strip().lower(), str(fallback or "").strip().lower())
    if fallback_clean in _THEME_BACKGROUND_IMAGE_LAYOUTS:
        return fallback_clean
    return DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_LAYOUT


def normalize_theme_background_image_darken(
    value: object,
    *,
    fallback: int = DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_DARKEN,
) -> int:
    return _normalize_theme_particles_int(value, fallback=fallback, minimum=0, maximum=100)


def normalize_theme_particles_enabled(
    value: object,
    *,
    fallback: bool = DEFAULT_CUSTOM_THEME_PARTICLES_ENABLED,
) -> bool:
    if isinstance(value, bool):
        return value
    clean = str(value or "").strip().lower()
    if clean in {"1", "true", "yes", "on", "enabled"}:
        return True
    if clean in {"0", "false", "no", "off", "disabled"}:
        return False
    return bool(fallback)


def normalize_theme_livemap_layers(
    value: object,
    *,
    fallback: object = None,
) -> dict[str, bool]:
    base = (
        fallback
        if isinstance(fallback, dict)
        else DEFAULT_CUSTOM_THEME_LIVEMAP_LAYERS
    )
    normalized: dict[str, bool] = {}
    payload = value if isinstance(value, dict) else {}
    aliases = {
        "labels": "cities",
        "city_labels": "cities",
        "towns": "cities",
        "boundaries": "borders",
        "countries": "borders",
        "roads_major": "roads",
        "water": "lakes",
        "rails": "railroads",
    }
    for key in _THEME_LIVEMAP_LAYER_KEYS:
        normalized[key] = normalize_theme_particles_enabled(
            payload.get(key),
            fallback=bool(base.get(key, DEFAULT_CUSTOM_THEME_LIVEMAP_LAYERS[key])),
        )
    for raw_key, mapped_key in aliases.items():
        if raw_key in payload and mapped_key in normalized:
            normalized[mapped_key] = normalize_theme_particles_enabled(
                payload.get(raw_key),
                fallback=normalized[mapped_key],
            )
    return normalized


def normalize_theme_particles_color(
    value: object,
    *,
    fallback: str = DEFAULT_CUSTOM_THEME_PARTICLES_COLOR,
) -> str:
    return normalize_theme_base_color(value, fallback=fallback)


def _normalize_theme_particles_int(
    value: object,
    *,
    fallback: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(fallback)
    return max(minimum, min(maximum, parsed))


def _normalize_theme_particles_float(
    value: object,
    *,
    fallback: float,
    minimum: float,
    maximum: float,
) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(fallback)
    if not math.isfinite(parsed):
        parsed = float(fallback)
    clamped = max(minimum, min(maximum, parsed))
    return round(clamped, 1)


def normalize_theme_particles_count(
    value: object,
    *,
    fallback: int = DEFAULT_CUSTOM_THEME_PARTICLES_COUNT,
) -> int:
    return _normalize_theme_particles_int(value, fallback=fallback, minimum=0, maximum=240)


def normalize_theme_particles_speed(
    value: object,
    *,
    fallback: float = DEFAULT_CUSTOM_THEME_PARTICLES_SPEED,
) -> float:
    return _normalize_theme_particles_float(value, fallback=fallback, minimum=0, maximum=12)


def normalize_theme_particles_size(
    value: object,
    *,
    fallback: int = DEFAULT_CUSTOM_THEME_PARTICLES_SIZE,
) -> int:
    return _normalize_theme_particles_int(value, fallback=fallback, minimum=1, maximum=8)


def normalize_theme_particles_opacity(
    value: object,
    *,
    fallback: int = DEFAULT_CUSTOM_THEME_PARTICLES_OPACITY,
) -> int:
    return _normalize_theme_particles_int(value, fallback=fallback, minimum=0, maximum=100)


def normalize_theme_gradient_type(
    value: object,
    *,
    fallback: str = DEFAULT_THEME_GRADIENT_TYPE,
) -> str:
    clean = str(value or "").strip().lower()
    if clean in _THEME_GRADIENT_TYPES:
        return clean
    fallback_clean = str(fallback or "").strip().lower()
    if fallback_clean in _THEME_GRADIENT_TYPES:
        return fallback_clean
    return DEFAULT_THEME_GRADIENT_TYPE


def normalize_theme_gradient_direction(
    value: object,
    *,
    fallback: str = DEFAULT_THEME_GRADIENT_DIRECTION,
) -> str:
    clean = str(value or "").strip().lower()
    if clean in _THEME_GRADIENT_DIRECTIONS:
        return clean
    fallback_clean = str(fallback or "").strip().lower()
    if fallback_clean in _THEME_GRADIENT_DIRECTIONS:
        return fallback_clean
    return DEFAULT_THEME_GRADIENT_DIRECTION


def build_theme_gradient_css(
    start_color: object,
    end_color: object,
    *,
    gradient_type: object = DEFAULT_THEME_GRADIENT_TYPE,
    direction: object = DEFAULT_THEME_GRADIENT_DIRECTION,
) -> str:
    start_hex = normalize_theme_base_color(start_color)
    end_hex = normalize_theme_base_color(end_color, fallback=start_hex)
    clean_type = normalize_theme_gradient_type(gradient_type)
    clean_direction = normalize_theme_gradient_direction(direction)
    direction_css = _THEME_GRADIENT_DIRECTIONS[clean_direction][clean_type]
    return f"{clean_type}-gradient({direction_css}, {start_hex}, {end_hex})"


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    clean = normalize_theme_base_color(value)
    return (
        int(clean[1:3], 16),
        int(clean[3:5], 16),
        int(clean[5:7], 16),
    )


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, int(round(rgb[0])))),
        max(0, min(255, int(round(rgb[1])))),
        max(0, min(255, int(round(rgb[2])))),
    )


def _rgb_to_hls(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    return colorsys.rgb_to_hls(
        max(0.0, min(1.0, float(rgb[0]) / 255.0)),
        max(0.0, min(1.0, float(rgb[1]) / 255.0)),
        max(0.0, min(1.0, float(rgb[2]) / 255.0)),
    )


def _mix_rgb(
    start: tuple[int, int, int],
    end: tuple[int, int, int],
    ratio: float,
) -> tuple[int, int, int]:
    clamped = max(0.0, min(1.0, float(ratio)))
    return tuple(
        int(round((channel_start * (1.0 - clamped)) + (channel_end * clamped)))
        for channel_start, channel_end in zip(start, end)
    )


def _channel_luminance(channel: int) -> float:
    normalized = max(0.0, min(1.0, float(channel) / 255.0))
    if normalized <= 0.04045:
        return normalized / 12.92
    return ((normalized + 0.055) / 1.055) ** 2.4


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    red = _channel_luminance(rgb[0])
    green = _channel_luminance(rgb[1])
    blue = _channel_luminance(rgb[2])
    return (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)


def _contrast_ratio(
    foreground: tuple[int, int, int],
    background: tuple[int, int, int],
) -> float:
    fg_luminance = _relative_luminance(foreground)
    bg_luminance = _relative_luminance(background)
    lighter = max(fg_luminance, bg_luminance)
    darker = min(fg_luminance, bg_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def _ensure_contrast(
    foreground: tuple[int, int, int],
    background: tuple[int, int, int],
    minimum: float,
    *,
    mix_target: tuple[int, int, int],
) -> tuple[int, int, int]:
    out = foreground
    for _ in range(18):
        if _contrast_ratio(out, background) >= minimum:
            return out
        out = _mix_rgb(out, mix_target, 0.18)
    if _contrast_ratio(out, background) >= minimum:
        return out
    return mix_target


def _readable_on_fill(fill: tuple[int, int, int]) -> tuple[int, int, int]:
    light_text = (248, 251, 255)
    dark_text = (15, 23, 42)
    if _contrast_ratio(light_text, fill) >= _contrast_ratio(dark_text, fill):
        return light_text
    return dark_text


def _ensure_min_luminance(
    rgb: tuple[int, int, int],
    minimum: float,
    *,
    mix_target: tuple[int, int, int] = (255, 255, 255),
) -> tuple[int, int, int]:
    out = rgb
    for _ in range(8):
        if _relative_luminance(out) >= minimum:
            break
        out = _mix_rgb(out, mix_target, 0.2)
    return out


def _ensure_min_luminance_preserving_hue(
    rgb: tuple[int, int, int],
    minimum: float,
) -> tuple[int, int, int]:
    if _relative_luminance(rgb) >= minimum:
        return rgb
    hue, lightness, saturation = _rgb_to_hls(rgb)
    low = lightness
    high = 1.0
    out = rgb
    for _ in range(20):
        mid = (low + high) / 2.0
        candidate = tuple(
            int(round(channel * 255.0))
            for channel in colorsys.hls_to_rgb(hue, mid, saturation)
        )
        if _relative_luminance(candidate) >= minimum:
            out = candidate
            high = mid
        else:
            low = mid
    if _relative_luminance(out) < minimum:
        return _ensure_min_luminance(out, minimum)
    return out


def _ensure_max_luminance(
    rgb: tuple[int, int, int],
    maximum: float,
) -> tuple[int, int, int]:
    out = rgb
    for _ in range(8):
        if _relative_luminance(out) <= maximum:
            break
        out = _mix_rgb(out, (0, 0, 0), 0.18)
    return out


def _depth_mix(depth: int, low: float, high: float) -> float:
    ratio = normalize_theme_color_depth(depth) / 100.0
    return low + ((high - low) * ratio)


def _depth_curve_mix(depth: int, low: float, high: float) -> float:
    ratio = math.pow(normalize_theme_color_depth(depth) / 100.0, 0.72)
    return low + ((high - low) * ratio)


def _adjust_hls(
    rgb: tuple[int, int, int],
    *,
    hue_degrees: float = 0.0,
    saturation_scale: float = 1.0,
    lightness_shift: float = 0.0,
) -> tuple[int, int, int]:
    hue, lightness, saturation = _rgb_to_hls(rgb)
    hue = (hue + (float(hue_degrees) / 360.0)) % 1.0
    saturation = max(0.0, min(1.0, saturation * float(saturation_scale)))
    lightness = max(0.0, min(1.0, lightness + float(lightness_shift)))
    return tuple(
        int(round(channel * 255.0))
        for channel in colorsys.hls_to_rgb(hue, lightness, saturation)
    )


def _same_hue_surface_alt(
    rgb: tuple[int, int, int],
    depth: int,
    *,
    lightness_low: float = 0.006,
    lightness_high: float = 0.018,
) -> tuple[int, int, int]:
    return _adjust_hls(
        rgb,
        saturation_scale=_depth_curve_mix(depth, 1.0, 1.05),
        lightness_shift=_depth_curve_mix(depth, lightness_low, lightness_high),
    )


def _format_alpha(alpha: float) -> str:
    return f"{max(0.0, min(1.0, alpha)):.3f}".rstrip("0").rstrip(".")


def _rgba(rgb: tuple[int, int, int], alpha: float) -> str:
    return f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {_format_alpha(alpha)})"


def build_palette_theme_preset(
    base_color: object,
    *,
    line_color: object = None,
    line_contrast_color: object = None,
    tint_color: object = None,
    color_depth: int = DEFAULT_THEME_COLOR_DEPTH,
    tint_intensity: object = None,
    gradient_primary_start_color: object = None,
    gradient_primary_end_color: object = None,
    gradient_primary_type: object = DEFAULT_THEME_GRADIENT_TYPE,
    gradient_primary_direction: object = DEFAULT_THEME_GRADIENT_DIRECTION,
    foreground_transparency: int = DEFAULT_THEME_FOREGROUND_TRANSPARENCY,
    foreground_blur: int = DEFAULT_THEME_FOREGROUND_BLUR,
    text_color: object = None,
    text_font: object = DEFAULT_THEME_TEXT_FONT,
) -> dict[str, Dict[str, str]]:
    base_hex = normalize_theme_base_color(base_color)
    line_hex = normalize_theme_line_color(line_color, fallback=base_hex)
    line_contrast_hex = normalize_theme_line_contrast_color(line_contrast_color)
    text_font_clean = normalize_theme_text_font(text_font)
    text_font_stack = theme_text_font_stack(text_font_clean)
    # Accepted for compatibility with old custom-theme settings. Readable text
    # and shared surface tokens are generated from the active theme instead.
    _ = tint_color
    _ = tint_intensity
    _ = text_color
    gradient_primary_start_hex = normalize_theme_base_color(
        gradient_primary_start_color,
        fallback=base_hex,
    )
    gradient_primary_end_hex = normalize_theme_base_color(
        gradient_primary_end_color,
        fallback=DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_END_COLOR,
    )
    background_gradient_css = build_theme_gradient_css(
        gradient_primary_start_hex,
        gradient_primary_end_hex,
        gradient_type=gradient_primary_type,
        direction=gradient_primary_direction,
    )
    depth = normalize_theme_color_depth(color_depth)
    foreground_transparency_clean = normalize_theme_foreground_transparency(foreground_transparency)
    foreground_blur_css = theme_foreground_blur_css(foreground_blur)
    foreground_alpha = 1.0 - (foreground_transparency_clean / 100.0)
    base_rgb = _hex_to_rgb(base_hex)
    line_rgb = _hex_to_rgb(line_hex)
    line_contrast_rgb = _hex_to_rgb(line_contrast_hex)
    base_surface_rgb = _adjust_hls(
        base_rgb,
        hue_degrees=_depth_curve_mix(depth, 0.0, -14.0),
        saturation_scale=_depth_curve_mix(depth, 0.68, 1.34),
        lightness_shift=_depth_curve_mix(depth, 0.0, -0.055),
    )
    base_surface_alt_rgb = _adjust_hls(
        base_rgb,
        hue_degrees=_depth_curve_mix(depth, 0.0, 32.0),
        saturation_scale=_depth_curve_mix(depth, 0.66, 1.26),
        lightness_shift=_depth_curve_mix(depth, 0.0, -0.04),
    )
    line_surface_rgb = _adjust_hls(
        line_rgb,
        hue_degrees=_depth_curve_mix(depth, 0.0, -12.0),
        saturation_scale=_depth_curve_mix(depth, 0.76, 1.34),
        lightness_shift=_depth_curve_mix(depth, 0.0, 0.025),
    )
    line_surface_alt_rgb = _adjust_hls(
        line_rgb,
        hue_degrees=_depth_curve_mix(depth, 0.0, 18.0),
        saturation_scale=_depth_curve_mix(depth, 0.72, 1.22),
        lightness_shift=_depth_curve_mix(depth, 0.0, 0.045),
    )
    tint_rgb = _mix_rgb(line_surface_rgb, base_surface_alt_rgb, 0.35)
    tint_hex = _rgb_to_hex(tint_rgb)
    gradient_primary_start_rgb = _hex_to_rgb(gradient_primary_start_hex)
    gradient_primary_end_rgb = _hex_to_rgb(gradient_primary_end_hex)
    foreground_transparency_ratio = foreground_transparency_clean / 100.0
    deep_base_rgb = _mix_rgb(
        base_surface_rgb,
        (0, 0, 0),
        _depth_curve_mix(depth, 0.48, 0.3),
    )

    # Light mode gets its own airy version of the same gradient (same hue,
    # pushed light) instead of reusing the dark-tuned colors verbatim.
    light_gradient_primary_start_rgb = _ensure_min_luminance_preserving_hue(
        gradient_primary_start_rgb, 0.88
    )
    light_gradient_primary_end_rgb = _ensure_min_luminance_preserving_hue(
        gradient_primary_end_rgb, 0.88
    )
    light_gradient_primary_start_hex = _rgb_to_hex(light_gradient_primary_start_rgb)
    light_gradient_primary_end_hex = _rgb_to_hex(light_gradient_primary_end_rgb)
    light_background_gradient_css = build_theme_gradient_css(
        light_gradient_primary_start_hex,
        light_gradient_primary_end_hex,
        gradient_type=gradient_primary_type,
        direction=gradient_primary_direction,
    )
    # Used only to estimate readable text color against the light wallpaper,
    # so it must be the light-adapted gradient, not the dark-tuned one.
    light_wallpaper_rgb = _mix_rgb(
        light_gradient_primary_start_rgb, light_gradient_primary_end_rgb, 0.5
    )

    def _visible_light_surface(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
        if foreground_transparency_clean <= 0:
            return rgb
        return _mix_rgb(rgb, light_wallpaper_rgb, foreground_transparency_ratio)

    def _light_reading_target(background: tuple[int, int, int]) -> tuple[int, int, int]:
        if foreground_transparency_clean <= 0:
            return (0, 0, 0)
        readable = _readable_on_fill(background)
        return (255, 255, 255) if readable == (248, 251, 255) else (0, 0, 0)

    light_accent_rgb = _ensure_max_luminance(base_rgb, 0.34)
    light_accent_strong_rgb = _ensure_max_luminance(
        _mix_rgb(light_accent_rgb, (0, 0, 0), _depth_mix(depth, 0.16, 0.24)),
        0.22,
    )
    dark_accent_soft_rgb = _ensure_min_luminance_preserving_hue(base_rgb, 0.22)
    dark_accent_rgb = _ensure_min_luminance_preserving_hue(
        _mix_rgb(dark_accent_soft_rgb, (255, 255, 255), _depth_mix(depth, 0.12, 0.24)),
        0.4,
    )

    light_bg_rgb = _mix_rgb(_hex_to_rgb(LIGHT_THEME_VARS["--bg"]), base_surface_rgb, _depth_curve_mix(depth, 0.04, 0.2))
    light_panel_rgb = _mix_rgb(
        _hex_to_rgb(LIGHT_THEME_VARS["--panel"]),
        base_surface_alt_rgb,
        _depth_curve_mix(depth, 0.0, 0.08),
    )
    light_line_source_rgb = _mix_rgb(line_surface_rgb, _hex_to_rgb(LIGHT_THEME_VARS["--ink"]), 0.18)
    light_line_rgb = _ensure_max_luminance(
        _mix_rgb(
            _hex_to_rgb(LIGHT_THEME_VARS["--line"]),
            light_line_source_rgb,
            _depth_mix(depth, 0.62, 0.82),
        ),
        0.34,
    )
    light_ui_bg_rgb = light_bg_rgb
    light_ui_bg_elev_rgb = _mix_rgb(light_panel_rgb, light_bg_rgb, 0.18)
    light_ui_panel_rgb = light_panel_rgb
    light_ui_panel_alt_rgb = _mix_rgb(light_panel_rgb, light_bg_rgb, 0.34)
    light_ui_border_rgb = light_line_rgb
    light_reading_bg_rgb = _visible_light_surface(light_panel_rgb)
    light_reading_target_rgb = _light_reading_target(light_reading_bg_rgb)
    light_text_seed_rgb = _hex_to_rgb(
        DARK_THEME_VARS["--theme-text-color"]
        if light_reading_target_rgb == (255, 255, 255)
        else LIGHT_THEME_VARS["--theme-text-color"]
    )
    if light_reading_target_rgb == (255, 255, 255):
        light_ink_rgb = _ensure_contrast(
            _mix_rgb(light_text_seed_rgb, light_accent_rgb, _depth_mix(depth, 0.02, 0.06)),
            light_reading_bg_rgb,
            7.0,
            mix_target=light_reading_target_rgb,
        )
        light_muted_rgb = _ensure_contrast(
            _mix_rgb(light_ink_rgb, light_reading_bg_rgb, 0.34),
            light_reading_bg_rgb,
            4.5,
            mix_target=light_reading_target_rgb,
        )
    else:
        light_ink_rgb = _ensure_max_luminance(
            _mix_rgb(_hex_to_rgb(LIGHT_THEME_VARS["--ink"]), light_accent_strong_rgb, _depth_mix(depth, 0.08, 0.14)),
            0.06,
        )
        light_muted_rgb = _ensure_max_luminance(
            _mix_rgb(_hex_to_rgb(LIGHT_THEME_VARS["--muted"]), light_accent_strong_rgb, _depth_mix(depth, 0.08, 0.16)),
            0.2,
        )

    dark_ui_bg_rgb = _mix_rgb(_hex_to_rgb(DARK_THEME_VARS["--ui-bg"]), deep_base_rgb, _depth_curve_mix(depth, 0.02, 0.34))
    dark_ui_bg_elev_rgb = _same_hue_surface_alt(
        dark_ui_bg_rgb,
        depth,
        lightness_low=0.006,
        lightness_high=0.014,
    )
    dark_ui_panel_rgb = _mix_rgb(
        _hex_to_rgb(DARK_THEME_VARS["--ui-panel"]),
        deep_base_rgb,
        _depth_curve_mix(depth, 0.04, 0.44),
    )
    dark_ui_panel_alt_rgb = _same_hue_surface_alt(
        dark_ui_panel_rgb,
        depth,
        lightness_low=0.007,
        lightness_high=0.016,
    )
    dark_line_rgb = _ensure_min_luminance(line_surface_rgb, 0.16, mix_target=line_contrast_rgb)
    dark_ui_border_rgb = _mix_rgb(
        _hex_to_rgb(DARK_THEME_VARS["--ui-border"]),
        dark_line_rgb,
        _depth_curve_mix(depth, 0.46, 0.9),
    )
    dark_ui_text_rgb = _ensure_min_luminance(
        _mix_rgb(_hex_to_rgb(DARK_THEME_VARS["--ui-text"]), dark_accent_rgb, _depth_mix(depth, 0.04, 0.1)),
        0.76,
    )
    dark_ui_text_soft_rgb = _ensure_min_luminance(
        _mix_rgb(_hex_to_rgb(DARK_THEME_VARS["--ui-text-soft"]), dark_accent_soft_rgb, _depth_mix(depth, 0.06, 0.12)),
        0.4,
    )
    dark_ui_link_rgb = _ensure_min_luminance(
        _mix_rgb(_hex_to_rgb(DARK_THEME_VARS["--ui-link"]), dark_accent_rgb, _depth_mix(depth, 0.24, 0.46)),
        0.5,
    )

    workspace_bg_rgb = _mix_rgb(
        _hex_to_rgb(DARK_THEME_VARS["--workspace-shell-bg"]),
        deep_base_rgb,
        _depth_curve_mix(depth, 0.08, 0.66),
    )
    workspace_bg_alt_rgb = _same_hue_surface_alt(
        workspace_bg_rgb,
        depth,
        lightness_low=0.006,
        lightness_high=0.016,
    )
    workspace_border_rgb = _mix_rgb(
        _hex_to_rgb(DARK_THEME_VARS["--workspace-shell-border"]),
        dark_line_rgb,
        _depth_curve_mix(depth, 0.52, 0.94),
    )
    workspace_line_muted_source_rgb = _mix_rgb(dark_line_rgb, workspace_bg_rgb, 0.24)
    workspace_border_muted_rgb = _mix_rgb(
        _hex_to_rgb(DARK_THEME_VARS["--workspace-shell-border-muted"]),
        workspace_line_muted_source_rgb,
        _depth_curve_mix(depth, 0.46, 0.9),
    )
    workspace_line_strong_source_rgb = _mix_rgb(
        _mix_rgb(dark_line_rgb, line_contrast_rgb, 0.14),
        line_surface_alt_rgb,
        _depth_curve_mix(depth, 0.04, 0.22),
    )
    workspace_border_strong_rgb = _mix_rgb(
        _hex_to_rgb(DARK_THEME_VARS["--workspace-shell-border-strong"]),
        workspace_line_strong_source_rgb,
        _depth_curve_mix(depth, 0.5, 0.94),
    )
    workspace_text_rgb = _ensure_min_luminance(
        _mix_rgb(_hex_to_rgb(DARK_THEME_VARS["--workspace-shell-text"]), dark_accent_rgb, _depth_mix(depth, 0.08, 0.16)),
        0.72,
    )
    workspace_text_soft_rgb = _ensure_min_luminance(
        _mix_rgb(_hex_to_rgb(DARK_THEME_VARS["--workspace-shell-text-soft"]), dark_accent_soft_rgb, _depth_mix(depth, 0.08, 0.14)),
        0.5,
    )
    workspace_hover_bg_rgb = _mix_rgb(
        _hex_to_rgb(DARK_THEME_VARS["--workspace-shell-hover-bg"]),
        dark_accent_soft_rgb,
        _depth_mix(depth, 0.14, 0.24),
    )
    workspace_active_bg_rgb = _mix_rgb(
        _hex_to_rgb(DARK_THEME_VARS["--workspace-shell-active-bg"]),
        dark_accent_soft_rgb,
        _depth_mix(depth, 0.18, 0.3),
    )
    workspace_active_text_rgb = _ensure_min_luminance(
        _mix_rgb(_hex_to_rgb(DARK_THEME_VARS["--workspace-shell-active-text"]), dark_accent_rgb, _depth_mix(depth, 0.12, 0.24)),
        0.64,
    )
    divider_start_rgb = _mix_rgb(workspace_bg_rgb, dark_accent_soft_rgb, _depth_curve_mix(depth, 0.02, 0.18))
    divider_end_rgb = _mix_rgb(workspace_bg_alt_rgb, dark_accent_rgb, _depth_curve_mix(depth, 0.03, 0.22))
    workspace_divider_css = build_theme_gradient_css(
        _rgb_to_hex(divider_start_rgb),
        _rgb_to_hex(divider_end_rgb),
    )

    tint_hue, _, tint_saturation = _rgb_to_hls(tint_rgb)
    tint_hue_degrees = (tint_hue * 360.0) % 360.0
    tint_start_hue = int(round(tint_hue_degrees)) % 360
    tint_end_hue = int(round(tint_hue_degrees + _depth_curve_mix(depth, 16.0, 58.0))) % 360
    tint_outline_hue = int(
        round(tint_hue_degrees + (_depth_curve_mix(depth, 5.0, 18.0) if tint_saturation >= 0.06 else 0.0))
    ) % 360

    light_surface_soft_rgb = (255, 255, 255)
    light_surface_bg_rgb = (255, 255, 255)
    light_surface_bg_alt_rgb = (255, 255, 255)
    light_surface_hover_rgb = (255, 255, 255)
    light_surface_vignette_rgb = _mix_rgb(tint_rgb, (15, 23, 42), 0.62)
    light_surface_vignette_alpha = 0.0
    light_surface_border_rgb = _ensure_max_luminance(
        _hex_to_rgb(LIGHT_THEME_VARS["--line"]),
        0.34,
    )
    light_surface_border_strong_rgb = _ensure_max_luminance(
        light_surface_border_rgb,
        0.28,
    )
    light_surface_text_bg_rgb = _visible_light_surface(light_surface_bg_rgb)
    light_surface_text_target_rgb = _light_reading_target(light_surface_text_bg_rgb)
    if light_surface_text_target_rgb == (255, 255, 255):
        light_surface_text_rgb = _ensure_contrast(
            light_ink_rgb,
            light_surface_text_bg_rgb,
            7.0,
            mix_target=light_surface_text_target_rgb,
        )
        light_surface_text_soft_rgb = _ensure_contrast(
            _mix_rgb(light_surface_text_rgb, light_surface_text_bg_rgb, 0.34),
            light_surface_text_bg_rgb,
            4.5,
            mix_target=light_surface_text_target_rgb,
        )
    else:
        light_surface_text_rgb = _ensure_max_luminance(
            light_ink_rgb,
            0.08,
        )
        light_surface_text_soft_rgb = _ensure_max_luminance(
            light_muted_rgb,
            0.22,
        )
    light_surface_divider_start_rgb = light_surface_soft_rgb
    light_surface_divider_end_rgb = light_surface_bg_alt_rgb
    light_surface_divider_css = build_theme_gradient_css(
        _rgb_to_hex(light_surface_divider_start_rgb),
        _rgb_to_hex(light_surface_divider_end_rgb),
    )

    dark_surface_soft_rgb = workspace_bg_alt_rgb
    dark_surface_bg_rgb = workspace_bg_rgb
    dark_surface_bg_alt_rgb = workspace_bg_alt_rgb
    dark_surface_hover_rgb = workspace_hover_bg_rgb
    dark_surface_vignette_rgb = _mix_rgb(tint_rgb, (0, 0, 0), 0.72)
    dark_surface_vignette_alpha = 0.0
    dark_surface_border_rgb = workspace_border_muted_rgb
    dark_surface_border_strong_rgb = workspace_border_rgb
    dark_surface_text_rgb = _ensure_min_luminance(
        workspace_text_rgb,
        0.72,
    )
    dark_surface_text_soft_rgb = _ensure_min_luminance(
        workspace_text_soft_rgb,
        0.5,
    )
    dark_surface_divider_start_rgb = dark_surface_soft_rgb
    dark_surface_divider_end_rgb = dark_surface_bg_alt_rgb
    dark_surface_divider_css = build_theme_gradient_css(
        _rgb_to_hex(dark_surface_divider_start_rgb),
        _rgb_to_hex(dark_surface_divider_end_rgb),
    )

    if light_reading_target_rgb == (255, 255, 255):
        light_theme_text_rgb = _ensure_contrast(
            light_text_seed_rgb,
            light_reading_bg_rgb,
            7.0,
            mix_target=light_reading_target_rgb,
        )
        light_theme_text_strong_rgb = _ensure_contrast(
            _mix_rgb(light_theme_text_rgb, light_reading_target_rgb, 0.16),
            light_reading_bg_rgb,
            9.0,
            mix_target=light_reading_target_rgb,
        )
        light_theme_text_soft_rgb = _ensure_contrast(
            _mix_rgb(light_theme_text_rgb, light_reading_bg_rgb, 0.2),
            light_reading_bg_rgb,
            4.5,
            mix_target=light_reading_target_rgb,
        )
        light_theme_text_muted_rgb = _ensure_contrast(
            _mix_rgb(light_theme_text_rgb, light_reading_bg_rgb, 0.36),
            light_reading_bg_rgb,
            4.5,
            mix_target=light_reading_target_rgb,
        )
        light_theme_text_accent_rgb = _ensure_min_luminance(
            _mix_rgb(light_theme_text_rgb, light_accent_rgb, 0.34),
            0.58,
        )
    else:
        light_theme_text_rgb = _ensure_contrast(
            light_text_seed_rgb,
            light_panel_rgb,
            7.0,
            mix_target=(0, 0, 0),
        )
        light_theme_text_strong_rgb = _ensure_contrast(
            _mix_rgb(light_theme_text_rgb, (0, 0, 0), 0.16),
            light_panel_rgb,
            9.0,
            mix_target=(0, 0, 0),
        )
        light_theme_text_soft_rgb = _ensure_contrast(
            _mix_rgb(light_theme_text_rgb, light_bg_rgb, 0.24),
            light_panel_rgb,
            4.5,
            mix_target=(0, 0, 0),
        )
        light_theme_text_muted_rgb = _ensure_contrast(
            _mix_rgb(light_theme_text_rgb, light_bg_rgb, 0.42),
            light_panel_rgb,
            4.5,
            mix_target=(0, 0, 0),
        )
        light_theme_text_accent_rgb = _ensure_max_luminance(
            _mix_rgb(light_theme_text_rgb, light_accent_strong_rgb, 0.36),
            0.28,
        )
    light_theme_text_on_fill_rgb = _readable_on_fill(light_accent_rgb)
    light_theme_text_code_rgb = _ensure_contrast(
        _mix_rgb(light_theme_text_rgb, light_accent_strong_rgb, 0.16),
        light_reading_bg_rgb if light_reading_target_rgb == (255, 255, 255) else light_panel_rgb,
        4.5,
        mix_target=light_reading_target_rgb if light_reading_target_rgb == (255, 255, 255) else (0, 0, 0),
    )
    light_workspace_bg_rgb = light_panel_rgb
    light_workspace_bg_alt_rgb = _mix_rgb(light_panel_rgb, light_bg_rgb, 0.34)
    light_workspace_border_rgb = light_line_rgb
    light_workspace_border_muted_rgb = _mix_rgb(light_line_rgb, light_workspace_bg_rgb, 0.28)
    light_workspace_border_strong_rgb = _ensure_max_luminance(
        _mix_rgb(light_line_rgb, light_accent_strong_rgb, _depth_mix(depth, 0.42, 0.58)),
        0.28,
    )
    light_workspace_text_rgb = light_theme_text_rgb
    light_workspace_text_soft_rgb = light_theme_text_muted_rgb
    light_workspace_hover_bg_rgb = _mix_rgb(
        light_workspace_bg_alt_rgb,
        light_accent_rgb,
        _depth_mix(depth, 0.08, 0.16),
    )
    light_workspace_active_bg_rgb = _mix_rgb(
        light_workspace_bg_alt_rgb,
        light_accent_rgb,
        _depth_mix(depth, 0.14, 0.24),
    )
    light_workspace_active_text_rgb = _ensure_contrast(
        light_theme_text_accent_rgb,
        _visible_light_surface(light_workspace_active_bg_rgb),
        4.5,
        mix_target=light_reading_target_rgb,
    )
    light_workspace_divider_css = build_theme_gradient_css(
        _rgb_to_hex(_mix_rgb(light_workspace_bg_alt_rgb, light_accent_rgb, _depth_mix(depth, 0.04, 0.1))),
        _rgb_to_hex(_mix_rgb(light_workspace_active_bg_rgb, light_accent_strong_rgb, _depth_mix(depth, 0.06, 0.12))),
    )

    dark_text_seed_rgb = _hex_to_rgb(DARK_THEME_VARS["--theme-text-color"])
    dark_theme_text_rgb = _ensure_contrast(
        dark_text_seed_rgb,
        workspace_bg_rgb,
        7.0,
        mix_target=(255, 255, 255),
    )
    dark_theme_text_strong_rgb = _ensure_contrast(
        _mix_rgb(dark_theme_text_rgb, (255, 255, 255), 0.16),
        workspace_bg_rgb,
        9.0,
        mix_target=(255, 255, 255),
    )
    dark_theme_text_soft_rgb = _ensure_contrast(
        _mix_rgb(dark_theme_text_rgb, workspace_bg_rgb, 0.2),
        workspace_bg_rgb,
        4.5,
        mix_target=(255, 255, 255),
    )
    dark_theme_text_muted_rgb = _ensure_contrast(
        _mix_rgb(dark_theme_text_rgb, workspace_bg_rgb, 0.36),
        workspace_bg_rgb,
        4.5,
        mix_target=(255, 255, 255),
    )
    dark_theme_text_accent_rgb = _ensure_min_luminance(
        _mix_rgb(dark_theme_text_rgb, dark_accent_rgb, 0.34),
        0.58,
    )
    dark_theme_text_on_fill_rgb = _readable_on_fill(dark_accent_rgb)
    dark_theme_text_code_rgb = _ensure_contrast(
        _mix_rgb(dark_theme_text_rgb, dark_accent_rgb, 0.18),
        workspace_bg_rgb,
        4.5,
        mix_target=(255, 255, 255),
    )

    def _foreground_fill(rgb: tuple[int, int, int]) -> str:
        if foreground_transparency_clean <= 0:
            return _rgb_to_hex(rgb)
        return _rgba(rgb, foreground_alpha)

    light_tokens = {
        "--bg": _foreground_fill(light_bg_rgb),
        "--ink": _rgb_to_hex(light_ink_rgb),
        "--panel": _foreground_fill(light_panel_rgb),
        "--line": _rgb_to_hex(light_line_rgb),
        "--accent": _rgb_to_hex(light_accent_rgb),
        "--accent-2": _rgb_to_hex(light_accent_strong_rgb),
        "--ui-bg": _foreground_fill(light_ui_bg_rgb),
        "--ui-bg-elev": _foreground_fill(light_ui_bg_elev_rgb),
        "--ui-panel": _foreground_fill(light_ui_panel_rgb),
        "--ui-panel-alt": _foreground_fill(light_ui_panel_alt_rgb),
        "--ui-border": _rgb_to_hex(light_ui_border_rgb),
        "--ui-text": _rgb_to_hex(light_theme_text_rgb),
        "--ui-text-soft": _rgb_to_hex(light_theme_text_muted_rgb),
        "--ui-accent": _rgb_to_hex(light_accent_rgb),
        "--ui-accent-soft": _rgb_to_hex(light_accent_strong_rgb),
        "--theme-font-family": text_font_stack,
        "--theme-text-color": _rgb_to_hex(light_theme_text_rgb),
        "--theme-text-color-strong": _rgb_to_hex(light_theme_text_strong_rgb),
        "--theme-text-color-soft": _rgb_to_hex(light_theme_text_soft_rgb),
        "--theme-text-color-muted": _rgb_to_hex(light_theme_text_muted_rgb),
        "--theme-text-color-accent": _rgb_to_hex(light_theme_text_accent_rgb),
        "--theme-text-color-on-fill": _rgb_to_hex(light_theme_text_on_fill_rgb),
        "--theme-text-color-code": _rgb_to_hex(light_theme_text_code_rgb),
        "--theme-base-color": base_hex,
        "--theme-background-gradient": light_background_gradient_css,
        "--theme-background-gradient-start": light_gradient_primary_start_hex,
        "--theme-background-gradient-end": light_gradient_primary_end_hex,
        "--theme-gradient-primary": light_background_gradient_css,
        "--theme-gradient-primary-start": light_gradient_primary_start_hex,
        "--theme-gradient-primary-end": light_gradient_primary_end_hex,
        "--theme-gradient-secondary": light_background_gradient_css,
        "--theme-gradient-secondary-start": light_gradient_primary_start_hex,
        "--theme-gradient-secondary-end": light_gradient_primary_end_hex,
        "--theme-foreground-transparency": str(foreground_transparency_clean),
        "--theme-foreground-blur": foreground_blur_css,
        "--ui-link": _rgb_to_hex(light_theme_text_accent_rgb),
        "--ui-shadow": f"0 10px 24px {_rgba(_mix_rgb(base_rgb, (0, 0, 0), 0.74), _depth_mix(depth, 0.08, 0.14))}",
        "--workspace-shell-bg": _foreground_fill(light_workspace_bg_rgb),
        "--workspace-shell-bg-alt": _foreground_fill(light_workspace_bg_alt_rgb),
        "--workspace-shell-border": _rgb_to_hex(light_workspace_border_rgb),
        "--workspace-shell-border-muted": _rgb_to_hex(light_workspace_border_muted_rgb),
        "--workspace-shell-border-strong": _rgb_to_hex(light_workspace_border_strong_rgb),
        "--workspace-shell-text": _rgb_to_hex(light_workspace_text_rgb),
        "--workspace-shell-text-soft": _rgb_to_hex(light_workspace_text_soft_rgb),
        "--workspace-shell-hover-bg": _foreground_fill(light_workspace_hover_bg_rgb),
        "--workspace-shell-active-bg": _foreground_fill(light_workspace_active_bg_rgb),
        "--workspace-shell-active-text": _rgb_to_hex(light_workspace_active_text_rgb),
        "--workspace-shell-divider-bg": light_workspace_divider_css,
        "--workspace-shell-divider-line": _rgb_to_hex(light_workspace_border_muted_rgb),
        "--workspace-shell-divider-line-active": _rgb_to_hex(light_workspace_border_rgb),
        "--workspace-shell-shadow": f"0 12px 28px {_rgba(_mix_rgb(base_rgb, (0, 0, 0), 0.74), _depth_mix(depth, 0.12, 0.2))}",
        "--danger": LIGHT_THEME_VARS["--danger"],
        "--muted": _rgb_to_hex(light_muted_rgb),
        "--shadow": f"0 10px 24px {_rgba(_mix_rgb(base_rgb, (0, 0, 0), 0.74), _depth_mix(depth, 0.08, 0.14))}",
        "--surface-tint-color": tint_hex,
        "--surface-tint-bg-soft": _foreground_fill(light_surface_soft_rgb),
        "--surface-tint-bg": _foreground_fill(light_surface_bg_rgb),
        "--surface-tint-bg-alt": _foreground_fill(light_surface_bg_alt_rgb),
        "--surface-tint-bg-hover": _foreground_fill(light_surface_hover_rgb),
        "--surface-tint-vignette": (
            f"radial-gradient(ellipse at center, transparent 58%, "
            f"{_rgba(light_surface_vignette_rgb, light_surface_vignette_alpha)} 100%)"
        ),
        "--surface-tint-border": _rgb_to_hex(light_surface_border_rgb),
        "--surface-tint-border-strong": _rgb_to_hex(light_surface_border_strong_rgb),
        "--surface-tint-text": _rgb_to_hex(light_surface_text_rgb),
        "--surface-tint-text-soft": _rgb_to_hex(light_surface_text_soft_rgb),
        "--surface-tint-divider-bg": light_surface_divider_css,
        "--surface-tint-divider-line": _rgb_to_hex(light_surface_border_strong_rgb),
        "--surface-tint-start-hue": str(tint_start_hue),
        "--surface-tint-end-hue": str(tint_end_hue),
        "--surface-tint-outline-hue": str(tint_outline_hue),
    }
    dark_tokens = {
        "--ui-bg": _foreground_fill(dark_ui_bg_rgb),
        "--ui-bg-elev": _foreground_fill(dark_ui_bg_elev_rgb),
        "--ui-panel": _foreground_fill(dark_ui_panel_rgb),
        "--ui-panel-alt": _foreground_fill(dark_ui_panel_alt_rgb),
        "--ui-border": _rgb_to_hex(dark_ui_border_rgb),
        "--ui-text": _rgb_to_hex(dark_ui_text_rgb),
        "--ui-text-soft": _rgb_to_hex(dark_ui_text_soft_rgb),
        "--ui-accent": _rgb_to_hex(dark_accent_rgb),
        "--ui-accent-soft": _rgb_to_hex(dark_accent_soft_rgb),
        "--theme-font-family": text_font_stack,
        "--theme-text-color": _rgb_to_hex(dark_theme_text_rgb),
        "--theme-text-color-strong": _rgb_to_hex(dark_theme_text_strong_rgb),
        "--theme-text-color-soft": _rgb_to_hex(dark_theme_text_soft_rgb),
        "--theme-text-color-muted": _rgb_to_hex(dark_theme_text_muted_rgb),
        "--theme-text-color-accent": _rgb_to_hex(dark_theme_text_accent_rgb),
        "--theme-text-color-on-fill": _rgb_to_hex(dark_theme_text_on_fill_rgb),
        "--theme-text-color-code": _rgb_to_hex(dark_theme_text_code_rgb),
        "--theme-base-color": base_hex,
        "--theme-background-gradient": background_gradient_css,
        "--theme-background-gradient-start": gradient_primary_start_hex,
        "--theme-background-gradient-end": gradient_primary_end_hex,
        "--theme-gradient-primary": background_gradient_css,
        "--theme-gradient-primary-start": gradient_primary_start_hex,
        "--theme-gradient-primary-end": gradient_primary_end_hex,
        "--theme-gradient-secondary": background_gradient_css,
        "--theme-gradient-secondary-start": gradient_primary_start_hex,
        "--theme-gradient-secondary-end": gradient_primary_end_hex,
        "--theme-foreground-transparency": str(foreground_transparency_clean),
        "--theme-foreground-blur": foreground_blur_css,
        "--ui-link": _rgb_to_hex(dark_ui_link_rgb),
        "--ui-shadow": f"0 10px 24px {_rgba(_mix_rgb(base_rgb, (0, 0, 0), 0.84), _depth_mix(depth, 0.36, 0.44))}",
        "--workspace-shell-bg": _foreground_fill(workspace_bg_rgb),
        "--workspace-shell-bg-alt": _foreground_fill(workspace_bg_alt_rgb),
        "--workspace-shell-border": _rgb_to_hex(workspace_border_rgb),
        "--workspace-shell-border-muted": _rgb_to_hex(workspace_border_muted_rgb),
        "--workspace-shell-border-strong": _rgb_to_hex(workspace_border_strong_rgb),
        "--workspace-shell-text": _rgb_to_hex(workspace_text_rgb),
        "--workspace-shell-text-soft": _rgb_to_hex(workspace_text_soft_rgb),
        "--workspace-shell-hover-bg": _foreground_fill(workspace_hover_bg_rgb),
        "--workspace-shell-active-bg": _foreground_fill(workspace_active_bg_rgb),
        "--workspace-shell-active-text": _rgb_to_hex(workspace_active_text_rgb),
        "--workspace-shell-divider-bg": workspace_divider_css,
        "--workspace-shell-divider-line": _rgb_to_hex(workspace_border_muted_rgb),
        "--workspace-shell-divider-line-active": _rgb_to_hex(workspace_border_rgb),
        "--workspace-shell-shadow": f"0 12px 28px {_rgba(_mix_rgb(base_rgb, (0, 0, 0), 0.88), _depth_mix(depth, 0.46, 0.56))}",
        "--surface-tint-color": tint_hex,
        "--surface-tint-bg-soft": _foreground_fill(dark_surface_soft_rgb),
        "--surface-tint-bg": _foreground_fill(dark_surface_bg_rgb),
        "--surface-tint-bg-alt": _foreground_fill(dark_surface_bg_alt_rgb),
        "--surface-tint-bg-hover": _foreground_fill(dark_surface_hover_rgb),
        "--surface-tint-vignette": (
            f"radial-gradient(ellipse at center, transparent 58%, "
            f"{_rgba(dark_surface_vignette_rgb, dark_surface_vignette_alpha)} 100%)"
        ),
        "--surface-tint-border": _rgb_to_hex(dark_surface_border_rgb),
        "--surface-tint-border-strong": _rgb_to_hex(dark_surface_border_strong_rgb),
        "--surface-tint-text": _rgb_to_hex(dark_surface_text_rgb),
        "--surface-tint-text-soft": _rgb_to_hex(dark_surface_text_soft_rgb),
        "--surface-tint-divider-bg": dark_surface_divider_css,
        "--surface-tint-divider-line": _rgb_to_hex(dark_surface_border_rgb),
        "--surface-tint-start-hue": str(tint_start_hue),
        "--surface-tint-end-hue": str(tint_end_hue),
        "--surface-tint-outline-hue": str(tint_outline_hue),
    }
    return {
        "light": light_tokens,
        "dark": dark_tokens,
    }


def _render_vars(selector: str, vars_map: Dict[str, str], indent: str) -> str:
    lines = [f"{indent}{selector} {{"]
    for key, value in vars_map.items():
        lines.append(f"{indent}  {key}: {value};")
    lines.append(f"{indent}}}")
    return "\n".join(lines)


def build_theme_css(
    indent: str = "    ",
    *,
    light_vars: Optional[Dict[str, str]] = None,
    dark_vars: Optional[Dict[str, str]] = None,
) -> str:
    light_tokens = light_vars if isinstance(light_vars, dict) else LIGHT_THEME_VARS
    dark_tokens = dark_vars if isinstance(dark_vars, dict) else DARK_THEME_VARS
    parts = [
        _render_vars(":root", light_tokens, indent),
        f"{indent}/* Readability-first dark theme override */",
        _render_vars('[data-theme="dark"]', dark_tokens, indent),
    ]
    return "\n".join(parts)
