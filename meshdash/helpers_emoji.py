from typing import Optional

from .helpers_types import to_int as _to_int


def emoji_from_codepoint(codepoint: Optional[int]) -> Optional[str]:
    value = _to_int(codepoint)
    if value is None or value <= 0:
        return None
    try:
        return chr(value)
    except (OverflowError, ValueError):
        return None


def normalize_single_emoji(value: object) -> tuple[Optional[str], Optional[int]]:
    if value is None:
        return None, None
    text = str(value).strip()
    if not text:
        return None, None

    as_int = _to_int(text)
    if as_int is not None and as_int > 0:
        emoji = emoji_from_codepoint(as_int)
        if emoji:
            return emoji, as_int
        return None, None

    codepoint = ord(text[0])
    emoji = emoji_from_codepoint(codepoint)
    if emoji:
        return emoji, codepoint
    return None, None
