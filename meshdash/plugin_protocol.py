"""Strict JSON framing for the trusted plugin worker protocol.

The multiprocessing ``Connection`` is transport infrastructure only.  All
application messages crossing it are UTF-8 JSON bytes with explicit versioning;
plugin events, state, and actions are never pickled.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import TypeAlias


PROTOCOL_VERSION = 1
MAX_PROTOCOL_FRAME_BYTES = 1024 * 1024

JSONScalar: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


class PluginProtocolError(ValueError):
    """Raised for malformed, oversized, or unsupported worker messages."""


def _validate_json_value(value: object, *, depth: int = 0) -> None:
    if depth > 32:
        raise PluginProtocolError("JSON nesting exceeds 32 levels")
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PluginProtocolError("JSON numbers must be finite")
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item, depth=depth + 1)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise PluginProtocolError("JSON object keys must be strings")
            _validate_json_value(item, depth=depth + 1)
        return
    raise PluginProtocolError(f"unsupported JSON value: {type(value).__name__}")


def encode_message(message: Mapping[str, object]) -> bytes:
    envelope = dict(message)
    envelope.setdefault("protocol_version", PROTOCOL_VERSION)
    if envelope.get("protocol_version") != PROTOCOL_VERSION:
        raise PluginProtocolError("unsupported plugin protocol version")
    message_type = envelope.get("type")
    if not isinstance(message_type, str) or not message_type.strip():
        raise PluginProtocolError("plugin protocol message requires a type")
    _validate_json_value(envelope)
    try:
        payload = json.dumps(
            envelope,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PluginProtocolError(str(exc)) from exc
    if len(payload) > MAX_PROTOCOL_FRAME_BYTES:
        raise PluginProtocolError("plugin protocol frame is too large")
    return payload


def decode_message(payload: bytes) -> dict[str, JSONValue]:
    if not isinstance(payload, bytes):
        raise PluginProtocolError("plugin protocol payload must be bytes")
    if len(payload) > MAX_PROTOCOL_FRAME_BYTES:
        raise PluginProtocolError("plugin protocol frame is too large")
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PluginProtocolError("invalid plugin protocol JSON") from exc
    if not isinstance(decoded, dict):
        raise PluginProtocolError("plugin protocol envelope must be an object")
    _validate_json_value(decoded)
    if decoded.get("protocol_version") != PROTOCOL_VERSION:
        raise PluginProtocolError("unsupported plugin protocol version")
    message_type = decoded.get("type")
    if not isinstance(message_type, str) or not message_type.strip():
        raise PluginProtocolError("plugin protocol message requires a type")
    return decoded


__all__ = [
    "JSONValue",
    "MAX_PROTOCOL_FRAME_BYTES",
    "PROTOCOL_VERSION",
    "PluginProtocolError",
    "decode_message",
    "encode_message",
]
