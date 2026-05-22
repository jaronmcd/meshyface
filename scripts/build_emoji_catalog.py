#!/usr/bin/env python3
"""Build a compact emoji catalog payload from Unicode emoji-test.txt."""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

DEFAULT_INPUT_URL = "https://unicode.org/Public/emoji/latest/emoji-test.txt"
DEFAULT_OUTPUT_PATH = Path("meshdash/assets/chat_emoji_catalog.min.json")

_GROUP_RE = re.compile(r"^#\s*group:\s*(.+?)\s*$")
_VERSION_RE = re.compile(r"^#\s*Version:\s*(.+?)\s*$")
_DATE_RE = re.compile(r"^#\s*Date:\s*(.+?)\s*$")
_EMOJI_RE = re.compile(
    r"^([0-9A-F ]+)\s*;\s*([a-z-]+)\s*#\s*(\S+)\s*(?:E[0-9.]+\s+)?(.+?)\s*$",
    re.IGNORECASE,
)

_ALLOWED_STATUSES = {"fully-qualified"}
_STOPWORDS = {
    "and",
    "cap",
    "character",
    "component",
    "digit",
    "face",
    "for",
    "heart",
    "key",
    "of",
    "symbol",
    "tone",
    "with",
}


def _slugify_group(label: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", label.strip().lower())
    token = re.sub(r"-+", "-", token).strip("-")
    return token or "group"


def _keyword_from_name(name: str) -> str:
    for token in re.split(r"[^a-z0-9]+", name.lower()):
        if len(token) < 2:
            continue
        if token in _STOPWORDS:
            continue
        return token
    return "emoji"


def _read_input_text(source: str) -> str:
    if source.startswith("http://") or source.startswith("https://"):
        with urllib.request.urlopen(source, timeout=30) as resp:
            return resp.read().decode("utf-8")
    return Path(source).read_text(encoding="utf-8")


def build_catalog(text: str) -> dict[str, object]:
    version = "unknown"
    date_value = ""

    groups: list[dict[str, object]] = []
    group_index: dict[str, dict[str, object]] = {}
    codepoint_keyword_map: dict[str, str] = {}
    current_group_id = "misc"

    def ensure_group(group_id: str, label: str) -> dict[str, object]:
        existing = group_index.get(group_id)
        if existing is not None:
            return existing
        created: dict[str, object] = {"id": group_id, "label": label, "emojis": []}
        group_index[group_id] = created
        groups.append(created)
        return created

    ensure_group(current_group_id, "Misc")

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        if not line:
            continue

        m_version = _VERSION_RE.match(line)
        if m_version:
            version = m_version.group(1).strip()
            continue

        m_date = _DATE_RE.match(line)
        if m_date:
            date_value = m_date.group(1).strip()
            continue

        m_group = _GROUP_RE.match(line)
        if m_group:
            label = m_group.group(1).strip()
            current_group_id = _slugify_group(label)
            ensure_group(current_group_id, label)
            continue

        m_emoji = _EMOJI_RE.match(line)
        if not m_emoji:
            continue
        status = m_emoji.group(2).strip().lower()
        if status not in _ALLOWED_STATUSES:
            continue

        emoji_value = m_emoji.group(3).strip()
        name_value = m_emoji.group(4).strip()
        codepoints_raw = m_emoji.group(1).strip().split()

        group = ensure_group(current_group_id, "Misc")
        emoji_list = group["emojis"]
        if isinstance(emoji_list, list) and emoji_value not in emoji_list:
            emoji_list.append(emoji_value)

        keyword = _keyword_from_name(name_value)
        for cp in codepoints_raw:
            key = f"{int(cp, 16):x}"
            codepoint_keyword_map.setdefault(key, keyword)

    groups = [g for g in groups if isinstance(g.get("emojis"), list) and g["emojis"]]

    return {
        "ok": True,
        "version": version,
        "date": date_value,
        "groups": groups,
        "codepoint_keyword_map": codepoint_keyword_map,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build chat_emoji_catalog.min.json from emoji-test.txt")
    parser.add_argument("--input", default=DEFAULT_INPUT_URL, help="Path or URL to emoji-test.txt")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Output JSON path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_catalog(_read_input_text(args.input))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {output_path}")
    print(f"version={payload.get('version')} date={payload.get('date')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
