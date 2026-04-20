import re
from typing import Optional

from .helpers_core import to_int as _to_int
from .helpers_emoji import emoji_codepoint_from_any as _emoji_codepoint_from_any
from .helpers_emoji import normalize_single_emoji as _normalize_single_emoji


_ASCII_REACTION_TEXT_RE = re.compile(r"^[0-9A-Za-z.,;:!?\'\"`~_\-]+$")
_KEYCAP_REACTION_RE = re.compile(r"^([0-9#*])(?:\uFE0F)?\u20E3$")


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


def extract_reaction_emoji(decoded: object) -> tuple[Optional[str], Optional[int]]:
    if not isinstance(decoded, dict):
        return None, None

    explicit_emoji, explicit_codepoint = _normalize_single_emoji(decoded.get("emoji"))
    if explicit_emoji:
        return explicit_emoji, explicit_codepoint

    text = str(decoded.get("text") or "").strip()
    if not text:
        return None, None
    if len(text) > 8 or any(ch.isspace() for ch in text):
        return None, None
    keycap_match = _KEYCAP_REACTION_RE.fullmatch(text)
    if keycap_match:
        return f"{keycap_match.group(1)}\uFE0F\u20E3", None
    if _ASCII_REACTION_TEXT_RE.fullmatch(text):
        return None, None
    text_emoji, text_codepoint = _normalize_single_emoji(text)
    if text_emoji:
        return text_emoji, text_codepoint
    return None, None


def calculate_hops(hop_start: object, hop_limit: object) -> Optional[int]:
    start = _to_int(hop_start)
    limit = _to_int(hop_limit)
    if start is None or limit is None:
        return None
    hops = start - limit
    if hops < 0:
        return None
    return hops
