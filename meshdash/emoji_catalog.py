from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any
import json


_ASSETS_DIR = Path(__file__).with_name("assets")
_CHAT_EMOJI_CATALOG_PATH = _ASSETS_DIR / "chat_emoji_catalog.min.json"


def _emoji_catalog_error_payload(message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": message,
        "version": "",
        "date": "",
        "groups": [],
        "codepoint_keyword_map": {},
    }


@lru_cache(maxsize=1)
def load_chat_emoji_catalog_payload() -> dict[str, Any]:
    try:
        text = _CHAT_EMOJI_CATALOG_PATH.read_text(encoding="utf-8")
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except Exception as exc:
        return _emoji_catalog_error_payload(
            f"emoji catalog unavailable: {exc}"
        )
    return _emoji_catalog_error_payload("emoji catalog payload invalid")
