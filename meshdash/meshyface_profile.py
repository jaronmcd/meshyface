from __future__ import annotations

import base64
import binascii
import json
import re
import time
from collections.abc import Mapping

from .helpers import to_int as _to_int
from .theme import build_palette_theme_preset as _build_palette_theme_preset


MESHYFACE_PROFILE_TYPE = "meshyface.profile"
MESHYFACE_PROFILE_VERSION = 2
MESHYFACE_PROFILE_PORTNUM = 256
DEFAULT_MESHYFACE_PROFILE_PORTNUM = MESHYFACE_PROFILE_PORTNUM
MESHYFACE_PROFILE_MAX_PAYLOAD_BYTES = 233
MESHYFACE_PROFILE_MAX_FUTURE_SECONDS = 24 * 60 * 60
MESHYFACE_PROFILE_CACHE_LIMIT = 2048
MESHYFACE_THEME_RECIPE_VERSION = 1
MESHYFACE_THEME_RECIPE_BYTES = 21
MESHYFACE_THEME_RECIPE_ENCODED_LENGTH = 28
MESHYFACE_PROFILE_GHOST_TEXT_MAX_CHARS = 5
MESHYFACE_PROFILE_GHOST_TEXT_MAX_BYTES = 32

_PROFILE_COLOR_RE = re.compile(r"^#[0-9a-f]{6}$", re.IGNORECASE)
_PROFILE_NODE_ID_RE = re.compile(r"^!?[0-9a-f]{8}$", re.IGNORECASE)
_THEME_RECIPE_WIRE_RE = re.compile(r"^[A-Za-z0-9_-]{28}$")
_PROFILE_GHOST_TEXT_DISALLOWED_RE = re.compile(r"[\x00-\x1f\x7f;{}<>\"'\\]")
_RGBA_COLOR_RE = re.compile(
    r"^rgba\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*"
    r"(0(?:\.\d+)?|1(?:\.0+)?)\s*\)$"
)
_PROFILE_WIRE_REQUIRED_KEYS = frozenset({"type", "v", "node", "updated", "theme"})
_PROFILE_WIRE_OPTIONAL_KEYS = frozenset({"ghost", "ghost_fx"})
_PROFILE_WIRE_KEYS = _PROFILE_WIRE_REQUIRED_KEYS | _PROFILE_WIRE_OPTIONAL_KEYS
_THEME_RECIPE_KEYS = frozenset(
    {
        "version",
        "base_color",
        "line_color",
        "line_contrast_color",
        "gradient_primary_start_color",
        "gradient_primary_end_color",
        "color_depth",
        "foreground_transparency",
        "foreground_blur",
        "text_font",
        "gradient_primary_type",
        "gradient_primary_direction",
        "mode",
    }
)
_THEME_FONTS = ("system", "compact", "rounded", "mono", "serif")
_THEME_GRADIENT_TYPES = ("linear", "radial")
_THEME_GRADIENT_DIRECTIONS = (
    "right",
    "left",
    "down",
    "up",
    "down-right",
    "down-left",
    "up-right",
    "up-left",
    "center",
)
_THEME_MODES = ("light", "dark")
_PROFILE_GHOST_EFFECTS = ("soft", "glow", "outline", "stamp")


def normalize_meshyface_profile_color(value: object) -> str | None:
    if not isinstance(value, str) or not _PROFILE_COLOR_RE.fullmatch(value):
        return None
    return value.lower()


def normalize_meshyface_profile_node_id(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        if value < 0 or value > 0xFFFFFFFF:
            return None
        return f"!{value:08x}"
    text = str(value or "").strip().lower()
    if not _PROFILE_NODE_ID_RE.fullmatch(text):
        return None
    return text if text.startswith("!") else f"!{text}"


def normalize_meshyface_profile_ghost_text(value: object) -> str | None:
    if value is None:
        return ""
    if not isinstance(value, str):
        return None
    text = _PROFILE_GHOST_TEXT_DISALLOWED_RE.sub("", value)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    clean_chars: list[str] = []
    encoded_len = 0
    for char in text:
        char_bytes = char.encode("utf-8", errors="ignore")
        if not char_bytes:
            continue
        if len(clean_chars) >= MESHYFACE_PROFILE_GHOST_TEXT_MAX_CHARS:
            break
        if encoded_len + len(char_bytes) > MESHYFACE_PROFILE_GHOST_TEXT_MAX_BYTES:
            break
        clean_chars.append(char)
        encoded_len += len(char_bytes)
    return "".join(clean_chars).strip()


def normalize_meshyface_profile_ghost_blend(
    value: object,
    *,
    fallback: int = 24,
) -> int | None:
    if value is None:
        return int(max(0, min(100, fallback)))
    if isinstance(value, bool):
        return None
    parsed = _to_int(value)
    if parsed is None or parsed < 0 or parsed > 100:
        return None
    return int(parsed)


def normalize_meshyface_profile_ghost_effect(
    value: object,
    *,
    fallback: str = "soft",
) -> str:
    clean = str(value or "").strip().lower()
    if clean in _PROFILE_GHOST_EFFECTS:
        return clean
    fallback_clean = str(fallback or "").strip().lower()
    return fallback_clean if fallback_clean in _PROFILE_GHOST_EFFECTS else "soft"


def encode_meshyface_profile_ghost_fx(
    *,
    blend: object = 24,
    effect: object = "soft",
) -> int | None:
    clean_blend = normalize_meshyface_profile_ghost_blend(blend)
    if clean_blend is None:
        return None
    clean_effect = normalize_meshyface_profile_ghost_effect(effect)
    blend_steps = max(0, min(31, round(clean_blend * 31 / 100)))
    effect_id = _PROFILE_GHOST_EFFECTS.index(clean_effect)
    return int(blend_steps | (effect_id << 5))


def decode_meshyface_profile_ghost_fx(value: object) -> dict[str, object] | None:
    if value is None:
        value = encode_meshyface_profile_ghost_fx()
    if isinstance(value, bool):
        return None
    parsed = _to_int(value)
    if parsed is None or parsed < 0 or parsed > 255:
        return None
    fx = int(parsed)
    blend_steps = fx & 0x1F
    effect_id = (fx >> 5) & 0x03
    return {
        "blend": int(round(blend_steps * 100 / 31)),
        "effect": _PROFILE_GHOST_EFFECTS[effect_id],
        "fx": fx,
    }


def normalize_meshyface_profile_ghost(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if isinstance(value, str):
        payload: Mapping[str, object] = {"text": value}
    elif isinstance(value, Mapping):
        payload = value
    else:
        return None

    text = normalize_meshyface_profile_ghost_text(
        _mapping_get(payload, "text", "ghost_text", "ghost")
    )
    if text is None:
        return None
    if not text:
        return None

    fx_raw = _mapping_get(payload, "fx", "ghost_fx")
    decoded_fx = decode_meshyface_profile_ghost_fx(fx_raw) if fx_raw is not None else None
    if fx_raw is not None and decoded_fx is None:
        return None
    blend_fallback = int(decoded_fx["blend"]) if decoded_fx else 24
    effect_fallback = str(decoded_fx["effect"]) if decoded_fx else "soft"
    blend = normalize_meshyface_profile_ghost_blend(
        _mapping_get(payload, "blend", "ghost_blend"),
        fallback=blend_fallback,
    )
    if blend is None:
        return None
    effect = normalize_meshyface_profile_ghost_effect(
        _mapping_get(payload, "effect", "ghost_effect"),
        fallback=effect_fallback,
    )
    fx = encode_meshyface_profile_ghost_fx(blend=blend, effect=effect)
    if fx is None:
        return None
    return {
        "text": text,
        "blend": int(blend),
        "effect": effect,
        "fx": int(fx),
    }


def _normalize_theme_integer(value: object, *, minimum: int, maximum: int) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if minimum <= value <= maximum else None


def _normalize_theme_enum(value: object, choices: tuple[str, ...]) -> str | None:
    if not isinstance(value, str):
        return None
    clean = value.strip().lower()
    return clean if clean in choices else None


def normalize_meshyface_theme_recipe(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping) or set(value.keys()) != _THEME_RECIPE_KEYS:
        return None
    version = _normalize_theme_integer(
        value.get("version"),
        minimum=MESHYFACE_THEME_RECIPE_VERSION,
        maximum=MESHYFACE_THEME_RECIPE_VERSION,
    )
    colors = {
        key: normalize_meshyface_profile_color(value.get(key))
        for key in (
            "base_color",
            "line_color",
            "line_contrast_color",
            "gradient_primary_start_color",
            "gradient_primary_end_color",
        )
    }
    color_depth = _normalize_theme_integer(
        value.get("color_depth"), minimum=0, maximum=100
    )
    foreground_transparency = _normalize_theme_integer(
        value.get("foreground_transparency"), minimum=0, maximum=90
    )
    foreground_blur = _normalize_theme_integer(
        value.get("foreground_blur"), minimum=0, maximum=40
    )
    text_font = _normalize_theme_enum(value.get("text_font"), _THEME_FONTS)
    gradient_type = _normalize_theme_enum(
        value.get("gradient_primary_type"), _THEME_GRADIENT_TYPES
    )
    gradient_direction = _normalize_theme_enum(
        value.get("gradient_primary_direction"), _THEME_GRADIENT_DIRECTIONS
    )
    mode = _normalize_theme_enum(value.get("mode"), _THEME_MODES)
    if (
        version is None
        or any(color is None for color in colors.values())
        or color_depth is None
        or foreground_transparency is None
        or foreground_blur is None
        or text_font is None
        or gradient_type is None
        or gradient_direction is None
        or mode is None
    ):
        return None
    return {
        "version": version,
        **{key: str(color) for key, color in colors.items()},
        "color_depth": color_depth,
        "foreground_transparency": foreground_transparency,
        "foreground_blur": foreground_blur,
        "text_font": text_font,
        "gradient_primary_type": gradient_type,
        "gradient_primary_direction": gradient_direction,
        "mode": mode,
    }


def _theme_surface_color_and_opacity(value: object) -> tuple[str, int] | None:
    color = normalize_meshyface_profile_color(value)
    if color is not None:
        return color, 100
    match = _RGBA_COLOR_RE.fullmatch(str(value or "").strip())
    if match is None:
        return None
    red, green, blue = (int(match.group(index)) for index in range(1, 4))
    if any(component < 0 or component > 255 for component in (red, green, blue)):
        return None
    try:
        alpha = float(match.group(4))
    except ValueError:
        return None
    if alpha < 0 or alpha > 1:
        return None
    return f"#{red:02x}{green:02x}{blue:02x}", int(round(alpha * 100))


def build_meshyface_theme_render(value: object) -> dict[str, object] | None:
    """Project a valid recipe into safe, sender-owned node-surface tokens.

    The theme recipe is intentionally compact for mesh transport.  This
    receiver-side projection reuses the canonical palette generator so a
    themed node gets the same workspace surface layered over the sender's
    background gradient, rather than treating its accent/base as a flat fill.
    """

    recipe = normalize_meshyface_theme_recipe(value)
    if recipe is None:
        return None
    try:
        palette = _build_palette_theme_preset(
            recipe["base_color"],
            line_color=recipe["line_color"],
            line_contrast_color=recipe["line_contrast_color"],
            color_depth=int(recipe["color_depth"]),
            gradient_primary_start_color=recipe["gradient_primary_start_color"],
            gradient_primary_end_color=recipe["gradient_primary_end_color"],
            gradient_primary_type=recipe["gradient_primary_type"],
            gradient_primary_direction=recipe["gradient_primary_direction"],
            foreground_transparency=int(recipe["foreground_transparency"]),
            foreground_blur=int(recipe["foreground_blur"]),
            text_font=recipe["text_font"],
        )
        tokens = palette[str(recipe["mode"])]
    except (KeyError, TypeError, ValueError):
        return None

    background_start = normalize_meshyface_profile_color(
        tokens.get("--theme-background-gradient-start")
    )
    background_end = normalize_meshyface_profile_color(
        tokens.get("--theme-background-gradient-end")
    )
    border = normalize_meshyface_profile_color(tokens.get("--workspace-shell-border"))
    border_muted = normalize_meshyface_profile_color(
        tokens.get("--workspace-shell-border-muted")
    )
    surface = _theme_surface_color_and_opacity(tokens.get("--workspace-shell-bg"))
    surface_hover = _theme_surface_color_and_opacity(
        tokens.get("--workspace-shell-hover-bg")
    )
    if not all((background_start, background_end, border, border_muted, surface, surface_hover)):
        return None
    surface_color, surface_opacity = surface
    hover_color, hover_opacity = surface_hover
    return {
        "background_start_color": background_start,
        "background_end_color": background_end,
        "surface_color": surface_color,
        "surface_opacity": surface_opacity,
        "surface_hover_color": hover_color,
        "surface_hover_opacity": hover_opacity,
        "border_color": border,
        "border_muted_color": border_muted,
    }


def encode_meshyface_theme_recipe(value: object) -> str:
    recipe = normalize_meshyface_theme_recipe(value)
    if recipe is None:
        raise ValueError("theme must be a complete valid Meshyface theme recipe")
    color_bytes = b"".join(
        bytes.fromhex(str(recipe[key])[1:])
        for key in (
            "base_color",
            "line_color",
            "line_contrast_color",
            "gradient_primary_start_color",
            "gradient_primary_end_color",
        )
    )
    font_id = _THEME_FONTS.index(str(recipe["text_font"]))
    gradient_type_id = _THEME_GRADIENT_TYPES.index(
        str(recipe["gradient_primary_type"])
    )
    direction_id = _THEME_GRADIENT_DIRECTIONS.index(
        str(recipe["gradient_primary_direction"])
    )
    mode_id = _THEME_MODES.index(str(recipe["mode"]))
    packed_enums = font_id | (gradient_type_id << 3) | (direction_id << 4)
    raw = bytes((MESHYFACE_THEME_RECIPE_VERSION,)) + color_bytes + bytes(
        (
            int(recipe["color_depth"]),
            int(recipe["foreground_transparency"]),
            int(recipe["foreground_blur"]),
            packed_enums,
            mode_id,
        )
    )
    if len(raw) != MESHYFACE_THEME_RECIPE_BYTES:
        raise ValueError("theme recipe encoded to an invalid size")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_meshyface_theme_recipe(value: object) -> dict[str, object] | None:
    if not isinstance(value, str) or not _THEME_RECIPE_WIRE_RE.fullmatch(value):
        return None
    try:
        raw = base64.b64decode(value, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError):
        return None
    if (
        len(raw) != MESHYFACE_THEME_RECIPE_BYTES
        or raw[0] != MESHYFACE_THEME_RECIPE_VERSION
        or base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != value
    ):
        return None
    color_depth = raw[16]
    foreground_transparency = raw[17]
    foreground_blur = raw[18]
    packed_enums = raw[19]
    font_id = packed_enums & 0b111
    gradient_type_id = (packed_enums >> 3) & 0b1
    direction_id = (packed_enums >> 4) & 0b1111
    mode_id = raw[20]
    if (
        color_depth > 100
        or foreground_transparency > 90
        or foreground_blur > 40
        or font_id >= len(_THEME_FONTS)
        or gradient_type_id >= len(_THEME_GRADIENT_TYPES)
        or direction_id >= len(_THEME_GRADIENT_DIRECTIONS)
        or mode_id >= len(_THEME_MODES)
    ):
        return None

    def _color(offset: int) -> str:
        return f"#{raw[offset:offset + 3].hex()}"

    return {
        "version": MESHYFACE_THEME_RECIPE_VERSION,
        "base_color": _color(1),
        "line_color": _color(4),
        "line_contrast_color": _color(7),
        "gradient_primary_start_color": _color(10),
        "gradient_primary_end_color": _color(13),
        "color_depth": color_depth,
        "foreground_transparency": foreground_transparency,
        "foreground_blur": foreground_blur,
        "text_font": _THEME_FONTS[font_id],
        "gradient_primary_type": _THEME_GRADIENT_TYPES[gradient_type_id],
        "gradient_primary_direction": _THEME_GRADIENT_DIRECTIONS[direction_id],
        "mode": _THEME_MODES[mode_id],
    }


def build_meshyface_profile_payload(
    *,
    node_id: object,
    updated_unix: object,
    theme: object,
    ghost: object = None,
    ghost_text: object = None,
    ghost_blend: object = 24,
    ghost_effect: object = "soft",
) -> bytes:
    clean_node_id = normalize_meshyface_profile_node_id(node_id)
    if not clean_node_id:
        raise ValueError("local node id is unavailable")
    clean_theme = normalize_meshyface_theme_recipe(theme)
    if clean_theme is None:
        raise ValueError("theme must be a complete valid Meshyface theme recipe")
    if isinstance(updated_unix, bool):
        raise ValueError("updated timestamp must be positive")
    updated = _to_int(updated_unix)
    if updated is None or updated <= 0:
        raise ValueError("updated timestamp must be positive")
    payload = {
        "type": MESHYFACE_PROFILE_TYPE,
        "v": MESHYFACE_PROFILE_VERSION,
        "node": clean_node_id,
        "updated": int(updated),
        "theme": encode_meshyface_theme_recipe(clean_theme),
    }
    clean_ghost = normalize_meshyface_profile_ghost(ghost)
    if clean_ghost is None and ghost_text is not None:
        clean_ghost = normalize_meshyface_profile_ghost(
            {
                "text": ghost_text,
                "blend": ghost_blend,
                "effect": ghost_effect,
            }
        )
    if clean_ghost:
        payload["ghost"] = clean_ghost["text"]
        payload["ghost_fx"] = clean_ghost["fx"]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > MESHYFACE_PROFILE_MAX_PAYLOAD_BYTES:
        raise ValueError(
            f"profile payload exceeds {MESHYFACE_PROFILE_MAX_PAYLOAD_BYTES}-byte Meshtastic limit"
        )
    return encoded


def _mapping_get(obj: object, *keys: str) -> object | None:
    if isinstance(obj, Mapping):
        for key in keys:
            if key in obj:
                return obj.get(key)
    for key in keys:
        if hasattr(obj, key):
            return getattr(obj, key)
    return None


def _is_meshyface_profile_portnum(value: object) -> bool:
    if not isinstance(value, bool):
        parsed = _to_int(value)
        if parsed is not None:
            return parsed == MESHYFACE_PROFILE_PORTNUM
    text = str(value or "").strip().upper()
    return text in {
        "PRIVATE_APP",
        "PORTNUM.PRIVATE_APP",
        "PORTNUMS_PB2.PORTNUM.PRIVATE_APP",
    }


def _decode_payload_object(payload: object) -> Mapping[str, object] | None:
    if isinstance(payload, Mapping):
        return payload
    if isinstance(payload, (bytes, bytearray, memoryview)):
        try:
            text = bytes(payload).decode("utf-8", errors="strict").strip("\x00 \t\r\n")
        except Exception:
            return None
    elif isinstance(payload, (list, tuple)):
        try:
            text = (
                bytes(int(part) & 0xFF for part in payload)
                .decode("utf-8", errors="strict")
                .strip("\x00 \t\r\n")
            )
        except Exception:
            return None
    else:
        return None
    if not text or not text.startswith("{"):
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        return None
    return parsed if isinstance(parsed, Mapping) else None


def parse_meshyface_profile_packet(
    packet: object,
    *,
    now_unix_fn=time.time,
) -> dict[str, object] | None:
    decoded = _mapping_get(packet, "decoded")
    if decoded is None:
        return None
    portnum = _mapping_get(decoded, "portnum", "portNum", "port_num")
    if not _is_meshyface_profile_portnum(portnum):
        return None
    body = _decode_payload_object(_mapping_get(decoded, "payload"))
    if body is None:
        return None
    body_keys = set(body.keys())
    if (
        not _PROFILE_WIRE_REQUIRED_KEYS.issubset(body_keys)
        or body_keys - _PROFILE_WIRE_KEYS
    ):
        return None
    if body.get("type") != MESHYFACE_PROFILE_TYPE:
        return None
    version = body.get("v")
    if isinstance(version, bool) or _to_int(version) != MESHYFACE_PROFILE_VERSION:
        return None

    # Meshtastic's decoded packet dictionary supplies fromId. Do not trust a
    # self-asserted node in the JSON body without that transport identity.
    from_id = normalize_meshyface_profile_node_id(_mapping_get(packet, "fromId"))
    body_node_id = normalize_meshyface_profile_node_id(body.get("node"))
    if not from_id or not body_node_id or from_id != body_node_id:
        return None

    theme = decode_meshyface_theme_recipe(body.get("theme"))
    if theme is None:
        return None
    ghost: dict[str, object] | None = None
    if "ghost" in body or "ghost_fx" in body:
        if "ghost" not in body:
            return None
        ghost = normalize_meshyface_profile_ghost(
            {
                "text": body.get("ghost"),
                "fx": body.get("ghost_fx"),
            }
        )
        if ghost is None:
            return None
    updated_raw = body.get("updated")
    if isinstance(updated_raw, bool):
        return None
    updated = _to_int(updated_raw)
    if updated is None or updated <= 0:
        return None
    try:
        received_unix = int(now_unix_fn())
    except Exception:
        received_unix = int(time.time())
    if updated > received_unix + MESHYFACE_PROFILE_MAX_FUTURE_SECONDS:
        return None
    profile = {
        "node_id": from_id,
        "updated_unix": int(updated),
        "received_unix": max(0, received_unix),
        "source": "mesh",
        "theme": theme,
    }
    if ghost:
        profile["ghost"] = ghost
    return profile
