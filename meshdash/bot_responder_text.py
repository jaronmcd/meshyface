import re
import time
from typing import Optional

from .helpers import to_int as _to_int

_CHAT_TOO_LONG_RE = re.compile(r"Message is too long \((\d+) bytes\)\. Limit is (\d+) bytes\.")
_ZORK_START_HELP_HINT = "type help for list of commands."


def _safe_strftime(unix_seconds: object) -> str:
    value = _to_int(unix_seconds)
    if value is None or value <= 0:
        return "n/a"
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(value))
    except Exception:
        return "n/a"


def _chat_limit_bytes_from_error(exc: Exception) -> Optional[int]:
    match = _CHAT_TOO_LONG_RE.search(str(exc or ""))
    if not match:
        return None
    return _to_int(match.group(2))


def _truncate_text_to_bytes(text: object, max_bytes: int, *, suffix: str = "") -> str:
    raw = str(text or "")
    limit = max(0, int(max_bytes))
    if limit <= 0:
        return ""
    raw_bytes = raw.encode("utf-8")
    if len(raw_bytes) <= limit and not suffix:
        return raw
    suffix_text = str(suffix or "")
    suffix_bytes = suffix_text.encode("utf-8")
    if len(suffix_bytes) >= limit:
        suffix_text = ""
        suffix_bytes = b""
    budget = max(0, limit - len(suffix_bytes))
    out: list[str] = []
    used = 0
    for ch in raw:
        chunk = ch.encode("utf-8")
        if used + len(chunk) > budget:
            break
        out.append(ch)
        used += len(chunk)
    trimmed = "".join(out).rstrip()
    return f"{trimmed}{suffix_text}" if suffix_text else trimmed


def _repair_truncated_ellipsis(text: object, max_bytes: int) -> Optional[str]:
    raw = str(text or "").strip()
    if not raw.endswith("…"):
        return None
    repaired = _truncate_text_to_bytes(raw[:-1].rstrip(), max_bytes, suffix="...")
    if not repaired:
        return None
    if len(repaired.encode("utf-8")) > int(max_bytes):
        return None
    return repaired


def _take_prefix_by_bytes(text: str, max_bytes: int) -> str:
    if max_bytes <= 0:
        return ""
    out: list[str] = []
    used = 0
    for ch in text:
        chunk = ch.encode("utf-8")
        if used + len(chunk) > max_bytes:
            break
        out.append(ch)
        used += len(chunk)
    return "".join(out)


def _split_text_by_bytes(text: object, max_bytes: int) -> list[str]:
    raw = str(text or "").strip()
    limit = max(1, int(max_bytes))
    if not raw:
        return []
    if len(raw.encode("utf-8")) <= limit:
        return [raw]
    parts: list[str] = []
    remaining = raw
    while remaining:
        if len(remaining.encode("utf-8")) <= limit:
            parts.append(remaining)
            break
        prefix = _take_prefix_by_bytes(remaining, limit)
        if not prefix:
            break
        split_at = -1
        for index in range(len(prefix) - 1, -1, -1):
            if prefix[index].isspace():
                split_at = index
                break
        if split_at > len(prefix) // 2:
            chunk = prefix[:split_at].rstrip()
            remaining = remaining[split_at + 1 :].lstrip()
        else:
            chunk = prefix.rstrip()
            remaining = remaining[len(prefix) :].lstrip()
        if not chunk:
            chunk = prefix
            remaining = remaining[len(prefix) :].lstrip()
        parts.append(chunk)
    return [part for part in parts if part]


def _segment_reply_text(text: object, max_bytes: int) -> list[str]:
    raw = str(text or "").strip()
    limit = max(1, int(max_bytes))
    if not raw:
        return []
    if len(raw.encode("utf-8")) <= limit:
        return [raw]
    repaired = _repair_truncated_ellipsis(raw, limit)
    if repaired is not None:
        return [repaired]
    digits = 1
    while True:
        prefix_reserve = len(f"{'9' * digits}/{'9' * digits} ".encode("utf-8"))
        chunk_limit = max(1, limit - prefix_reserve)
        chunks = _split_text_by_bytes(raw, chunk_limit)
        total = len(chunks)
        if total <= 1:
            break
        next_digits = len(str(total))
        if next_digits == digits:
            return [f"{index}/{total} {chunk}" for index, chunk in enumerate(chunks, start=1)]
        digits = next_digits
    return [_truncate_text_to_bytes(raw, limit)]


def _tag_zork_start_reply(reply_text: object, *, app_name: str) -> Optional[str]:
    if str(app_name or "").strip().lower() != "zork":
        if isinstance(reply_text, str):
            return reply_text
        return str(reply_text).strip() if reply_text is not None else None
    if not isinstance(reply_text, str):
        return str(reply_text).strip() if reply_text is not None else None
    text = reply_text.strip()
    if not text:
        return ""
    lowered = text.lower()
    marker = "zork: session started."
    marker_index = lowered.find(marker)
    if marker_index < 0:
        return text
    if _ZORK_START_HELP_HINT in lowered:
        return text
    marker_end = marker_index + len(marker)
    head = text[:marker_end].rstrip()
    tail = text[marker_end:].lstrip()
    tip = f"Tip: {_ZORK_START_HELP_HINT}"
    if tail:
        return f"{head} {tail} {tip}"
    return f"{head} {tip}"
