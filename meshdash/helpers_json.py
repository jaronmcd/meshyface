import json
import math
from typing import TypeAlias, TypeVar

try:
    from google.protobuf.json_format import MessageToDict as _protobuf_message_to_dict
    from google.protobuf.message import Message as _protobuf_message_type
except Exception:
    _protobuf_message_type = None
    _protobuf_message_to_dict = None


JsonScalar: TypeAlias = None | str | int | float | bool
JsonValue: TypeAlias = JsonScalar | dict[str, "JsonValue"] | list["JsonValue"]
DefaultT = TypeVar("DefaultT")


def safe_json_loads(value: str, default: DefaultT) -> JsonValue | DefaultT:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def message_to_dict(value: object) -> object | None:
    if (
        _protobuf_message_type is not None
        and _protobuf_message_to_dict is not None
        and isinstance(value, _protobuf_message_type)
    ):
        return _protobuf_message_to_dict(value, preserving_proto_field_name=True)
    return None


def to_jsonable(value: object, depth: int = 0) -> JsonValue:
    if depth > 12:
        return "<max-depth>"
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, bytes):
        return value.hex()
    as_message = message_to_dict(value)
    if as_message is not None:
        return to_jsonable(as_message, depth + 1)
    if isinstance(value, dict):
        out: dict[str, JsonValue] = {}
        for key, val in value.items():
            out[str(key)] = to_jsonable(val, depth + 1)
        return out
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item, depth + 1) for item in value]
    return str(value)
