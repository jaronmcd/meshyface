from __future__ import annotations

import json
from dataclasses import dataclass

from .meshyface_profile import normalize_meshyface_profile_color
from .runtime_types import ToIntFn


@dataclass(frozen=True)
class MeshyfaceProfileColorRequest:
    color: str
    channel_index: int


def parse_meshyface_profile_color_request(
    raw_body: bytes,
    *,
    to_int_fn: ToIntFn,
) -> MeshyfaceProfileColorRequest:
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid JSON request body") from exc
    if not isinstance(body, dict):
        raise ValueError("request body must be an object")
    color = normalize_meshyface_profile_color(body.get("color"))
    if not color:
        raise ValueError("color must be #rrggbb")
    raw_channel_index = body.get("channel_index", 0)
    if isinstance(raw_channel_index, bool):
        raise ValueError("channel_index must be non-negative")
    channel_index = to_int_fn(raw_channel_index)
    if channel_index is None or channel_index < 0:
        raise ValueError("channel_index must be non-negative")
    return MeshyfaceProfileColorRequest(
        color=color,
        channel_index=int(channel_index),
    )
