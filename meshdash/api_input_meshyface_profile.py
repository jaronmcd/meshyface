from __future__ import annotations

import json
from dataclasses import dataclass

from .meshyface_profile import (
    normalize_meshyface_profile_ghost,
    normalize_meshyface_theme_recipe,
)
from .runtime_types import ToIntFn


@dataclass(frozen=True)
class MeshyfaceProfileThemeRequest:
    theme: dict[str, object]
    channel_index: int
    ghost: dict[str, object] | None = None


def parse_meshyface_profile_theme_request(
    raw_body: bytes,
    *,
    to_int_fn: ToIntFn,
) -> MeshyfaceProfileThemeRequest:
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid JSON request body") from exc
    if not isinstance(body, dict):
        raise ValueError("request body must be an object")
    if "color" in body:
        raise ValueError(
            "color is no longer supported; provide a complete Meshyface theme"
        )
    raw_channel_index = body.get("channel_index", 0)
    if isinstance(raw_channel_index, bool):
        raise ValueError("channel_index must be non-negative")
    channel_index = to_int_fn(raw_channel_index)
    if channel_index is None or channel_index < 0:
        raise ValueError("channel_index must be non-negative")
    theme = normalize_meshyface_theme_recipe(body.get("theme"))
    if theme is None:
        raise ValueError("theme must be a complete valid Meshyface theme recipe")
    ghost = None
    ghost_keys = {
        "ghost",
        "ghost_text",
        "ghost_blend",
        "ghost_effect",
        "ghost_tilt",
        "ghost_justify",
        "ghost_fx",
    }
    if any(key in body for key in ghost_keys):
        raw_ghost = body.get("ghost")
        if raw_ghost is not None:
            if isinstance(raw_ghost, dict):
                ghost_payload = dict(raw_ghost)
            else:
                ghost_payload = {
                    "text": raw_ghost,
                    "blend": body.get("ghost_blend"),
                    "effect": body.get("ghost_effect"),
                    "tilt": body.get("ghost_tilt"),
                    "justify": body.get("ghost_justify"),
                    "fx": body.get("ghost_fx"),
                }
            if "ghost_tilt" in body and "tilt" not in ghost_payload:
                ghost_payload["tilt"] = body.get("ghost_tilt")
            if "ghost_justify" in body and "justify" not in ghost_payload:
                ghost_payload["justify"] = body.get("ghost_justify")
            ghost = normalize_meshyface_profile_ghost(ghost_payload)
        else:
            ghost = normalize_meshyface_profile_ghost(
                {
                    "text": body.get("ghost_text"),
                    "blend": body.get("ghost_blend"),
                    "effect": body.get("ghost_effect"),
                    "tilt": body.get("ghost_tilt"),
                    "justify": body.get("ghost_justify"),
                    "fx": body.get("ghost_fx"),
                }
            )
        if ghost is None and (body.get("ghost") or body.get("ghost_text")):
            raise ValueError("ghost must be 1-5 characters within the profile byte limit")
    return MeshyfaceProfileThemeRequest(
        theme=theme,
        channel_index=int(channel_index),
        ghost=ghost,
    )
