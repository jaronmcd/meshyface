from __future__ import annotations

import base64
import binascii
import json
import re
import time
from collections.abc import Mapping

from .helpers import to_int as _to_int


MESHYFACE_PROFILE_TYPE = "meshyface.profile"
MESHYFACE_PROFILE_VERSION = 1
MESHYFACE_PROFILE_PORTNUM = 256
DEFAULT_MESHYFACE_PROFILE_PORTNUM = MESHYFACE_PROFILE_PORTNUM
MESHYFACE_PROFILE_MAX_PAYLOAD_BYTES = 233
MESHYFACE_PROFILE_MAX_FUTURE_SECONDS = 24 * 60 * 60
MESHYFACE_PROFILE_CACHE_LIMIT = 2048
MESHYFACE_THEME_RECIPE_VERSION = 1
MESHYFACE_THEME_RECIPE_BYTES = 21
MESHYFACE_THEME_RECIPE_ENCODED_LENGTH = 28

_PROFILE_COLOR_RE = re.compile(r"^#[0-9a-f]{6}$", re.IGNORECASE)
_PROFILE_NODE_ID_RE = re.compile(r"^!?[0-9a-f]{8}$", re.IGNORECASE)
_THEME_RECIPE_WIRE_RE = re.compile(r"^[A-Za-z0-9_-]{28}$")
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
    color: object,
    updated_unix: object,
    theme: object = None,
) -> bytes:
    clean_node_id = normalize_meshyface_profile_node_id(node_id)
    if not clean_node_id:
        raise ValueError("local node id is unavailable")
    clean_color = normalize_meshyface_profile_color(color)
    if not clean_color:
        raise ValueError("color must be #rrggbb")
    if isinstance(updated_unix, bool):
        raise ValueError("updated timestamp must be positive")
    updated = _to_int(updated_unix)
    if updated is None or updated <= 0:
        raise ValueError("updated timestamp must be positive")
    payload = {
        "type": MESHYFACE_PROFILE_TYPE,
        "v": MESHYFACE_PROFILE_VERSION,
        "node": clean_node_id,
        "color": clean_color,
        "updated": int(updated),
    }
    if theme is not None:
        payload["theme"] = encode_meshyface_theme_recipe(theme)
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
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

    color = normalize_meshyface_profile_color(body.get("color"))
    if not color:
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
        "color": color,
        "updated_unix": int(updated),
        "received_unix": max(0, received_unix),
        "source": "mesh",
    }
    theme = decode_meshyface_theme_recipe(body.get("theme"))
    if theme is not None:
        profile["theme"] = theme
    return profile
