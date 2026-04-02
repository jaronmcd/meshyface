import re
from typing import Optional

from .helpers_types import to_int as _to_int

_HEX_CODEPOINT_RE = re.compile(r"^(?:U\+)?([0-9A-Fa-f]{4,8})$")
_SKIP_LEADING_CODEPOINTS = {0xFE0E, 0xFE0F}


def _is_reaction_codepoint_candidate(codepoint: object) -> bool:
    value = _to_int(codepoint)
    if value is None or value <= 0:
        return False
    # Reject plain ASCII chars so reply text like "joy joy" cannot become "j".
    if value <= 0x7F:
        return False
    return True


def emoji_from_codepoint(codepoint: Optional[int]) -> Optional[str]:
    value = _to_int(codepoint)
    if not _is_reaction_codepoint_candidate(value):
        return None
    try:
        return chr(value)
    except (OverflowError, ValueError):
        return None


def emoji_codepoint_from_any(value: object) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, str):
        clean = value.strip()
        if not clean:
            return None
        as_int = _to_int(clean)
        if as_int is not None:
            return as_int if _is_reaction_codepoint_candidate(as_int) else None
        match = _HEX_CODEPOINT_RE.fullmatch(clean)
        if match:
            try:
                parsed = int(match.group(1), 16)
            except ValueError:
                parsed = None
            return parsed if _is_reaction_codepoint_candidate(parsed) else None
        parsed_codepoint: Optional[int] = None
        for ch in clean:
            codepoint = ord(ch)
            if codepoint in _SKIP_LEADING_CODEPOINTS:
                continue
            # Reactions support a single base codepoint only.
            if parsed_codepoint is not None:
                return None
            parsed_codepoint = codepoint
        return parsed_codepoint if _is_reaction_codepoint_candidate(parsed_codepoint) else None
    as_int = _to_int(value)
    if not _is_reaction_codepoint_candidate(as_int):
        return None
    return as_int


def normalize_single_emoji(value: object) -> tuple[Optional[str], Optional[int]]:
    codepoint = emoji_codepoint_from_any(value)
    if codepoint is None:
        return None, None
    emoji = emoji_from_codepoint(codepoint)
    if emoji:
        return emoji, codepoint
    return None, None
