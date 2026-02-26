from typing import Optional

from .helpers_core import to_int as _to_int


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
    raw = decoded.get("emoji")
    if raw is None:
        return None

    if isinstance(raw, str):
        clean = raw.strip()
        if not clean:
            return None
        as_int = _to_int(clean)
        if as_int is not None:
            return as_int if as_int > 0 else None
        return ord(clean[0])

    as_int = _to_int(raw)
    if as_int is None or as_int <= 0:
        return None
    return as_int


def calculate_hops(hop_start: object, hop_limit: object) -> Optional[int]:
    start = _to_int(hop_start)
    limit = _to_int(hop_limit)
    if start is None or limit is None:
        return None
    hops = start - limit
    if hops < 0:
        return None
    return hops
