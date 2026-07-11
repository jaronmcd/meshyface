from __future__ import annotations

import time

from .helpers import to_int as _to_int
from .meshyface_profile import (
    MESHYFACE_PROFILE_PORTNUM,
    MESHYFACE_PROFILE_TYPE,
    build_meshyface_profile_payload,
    normalize_meshyface_profile_ghost,
    normalize_meshyface_profile_node_id,
    normalize_meshyface_theme_recipe,
)


def _sent_packet_id(sent_packet: object) -> int | None:
    if isinstance(sent_packet, dict):
        parsed = _to_int(
            sent_packet.get("id")
            or sent_packet.get("packet_id")
            or sent_packet.get("packetId")
        )
    else:
        parsed = _to_int(getattr(sent_packet, "id", None))
    return parsed if parsed is not None and parsed > 0 else None


def send_meshyface_profile_theme(
    *,
    theme: object,
    iface: object,
    send_lock: object,
    local_node_id_fn,
    channel_index: object = 0,
    ghost: object = None,
    ghost_text: object = None,
    ghost_blend: object = 24,
    ghost_effect: object = "soft",
    now_unix_fn=time.time,
) -> dict[str, object]:
    clean_theme = normalize_meshyface_theme_recipe(theme)
    if clean_theme is None:
        raise ValueError("theme must be a complete valid Meshyface theme recipe")
    clean_ghost = normalize_meshyface_profile_ghost(ghost)
    if clean_ghost is None and ghost_text is not None:
        clean_ghost = normalize_meshyface_profile_ghost(
            {
                "text": ghost_text,
                "blend": ghost_blend,
                "effect": ghost_effect,
            }
        )
    if clean_ghost is None and (ghost or ghost_text):
        raise ValueError("ghost must be 1-5 characters within the profile byte limit")
    try:
        local_node_id = local_node_id_fn()
    except Exception as exc:
        raise RuntimeError("local node id is unavailable") from exc
    clean_node_id = normalize_meshyface_profile_node_id(local_node_id)
    if not clean_node_id:
        raise ValueError("local node id is unavailable")
    if isinstance(channel_index, bool):
        raise ValueError("channel_index must be non-negative")
    clean_channel = _to_int(channel_index)
    if clean_channel is None or clean_channel < 0:
        raise ValueError("channel_index must be non-negative")
    try:
        updated_unix = int(now_unix_fn())
    except Exception:
        updated_unix = int(time.time())
    payload = build_meshyface_profile_payload(
        node_id=clean_node_id,
        updated_unix=updated_unix,
        theme=clean_theme,
        ghost=clean_ghost,
    )
    send_data = getattr(iface, "sendData", None)
    if not callable(send_data):
        raise RuntimeError("Connected interface does not support sendData()")

    with send_lock:
        sent_packet = send_data(
            payload,
            destinationId="^all",
            portNum=MESHYFACE_PROFILE_PORTNUM,
            wantAck=False,
            wantResponse=False,
            channelIndex=int(clean_channel),
        )

    response: dict[str, object] = {
        "ok": True,
        "sent": True,
        "type": MESHYFACE_PROFILE_TYPE,
        "node": clean_node_id,
        "updated": updated_unix,
        "theme": clean_theme,
        "destination": "^all",
        "channel_index": int(clean_channel),
        "portnum": MESHYFACE_PROFILE_PORTNUM,
    }
    if clean_ghost:
        response["ghost"] = clean_ghost
    packet_id = _sent_packet_id(sent_packet)
    if packet_id is not None:
        response["packet_id"] = packet_id
    return response
