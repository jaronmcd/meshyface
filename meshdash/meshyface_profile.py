from __future__ import annotations

import json
import re
import time
from collections.abc import Mapping

from .helpers import to_int as _to_int


MESHYFACE_PROFILE_TYPE = "meshyface.profile"
MESHYFACE_PROFILE_VERSION = 1
MESHYFACE_PROFILE_PORTNUM = 256
DEFAULT_MESHYFACE_PROFILE_PORTNUM = MESHYFACE_PROFILE_PORTNUM
MESHYFACE_PROFILE_MAX_FUTURE_SECONDS = 24 * 60 * 60
MESHYFACE_PROFILE_CACHE_LIMIT = 2048

_PROFILE_COLOR_RE = re.compile(r"^#[0-9a-f]{6}$", re.IGNORECASE)
_PROFILE_NODE_ID_RE = re.compile(r"^!?[0-9a-f]{8}$", re.IGNORECASE)


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


def build_meshyface_profile_payload(
    *,
    node_id: object,
    color: object,
    updated_unix: object,
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
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


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
    return {
        "node_id": from_id,
        "color": color,
        "updated_unix": int(updated),
        "received_unix": max(0, received_unix),
        "source": "mesh",
    }
