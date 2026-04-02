from typing import Optional

from .helpers_core import to_int as _to_int
from .helpers_emoji import emoji_codepoint_from_any as _emoji_codepoint_from_any


def extract_reply_id(decoded: object) -> Optional[int]:
    if not isinstance(decoded, dict):
        return None
    for key in ("replyId", "reply_id"):
        value = _to_int(decoded.get(key))
        if value is not None and value > 0:
            return value
    return None


def extract_emoji_codepoint(decoded: object) -> Optional[int]:
    if not isinstance(decoded, dict):
        return None
    return _emoji_codepoint_from_any(decoded.get("emoji"))


def calculate_hops(hop_start: object, hop_limit: object) -> Optional[int]:
    start = _to_int(hop_start)
    limit = _to_int(hop_limit)
    if start is None or limit is None:
        return None
    hops = start - limit
    if hops < 0:
        return None
    return hops
