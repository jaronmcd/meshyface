from __future__ import annotations

import json
from dataclasses import dataclass

from .meshyface_profile import (
    normalize_meshyface_theme_recipe,
)
from .runtime_types import ToIntFn


@dataclass(frozen=True)
class MeshyfaceProfileThemeRequest:
    theme: dict[str, object]
    channel_index: int


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
    return MeshyfaceProfileThemeRequest(
        theme=theme,
        channel_index=int(channel_index),
    )
