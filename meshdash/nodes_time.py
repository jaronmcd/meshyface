from datetime import datetime, timezone
from typing import Optional


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def parse_utc_text_to_unix(value: object) -> Optional[int]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%SZ")
    except Exception:
        return None
    return int(parsed.replace(tzinfo=timezone.utc).timestamp())
