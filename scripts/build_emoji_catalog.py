#!/usr/bin/env python3
"""Build a compact emoji catalog payload from Unicode emoji-test.txt and CLDR annotations."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_EMOJI_VERSION = "17.0"
DEFAULT_INPUT_URL = "https://unicode.org/Public/emoji/latest/emoji-test.txt"
DEFAULT_INPUT_SHA256 = (
    "1d8a944f88d7952f7ef7c5167fef3c67995bcae24543949710231b03a201acda"
)
DEFAULT_CLDR_REF = "dc25cedd74edaea2c7f8dcd84eeee634f74e1867"
DEFAULT_ANNOTATIONS_URL = (
    "https://raw.githubusercontent.com/unicode-org/cldr/"
    f"{DEFAULT_CLDR_REF}/common/annotations/en.xml"
)
DEFAULT_ANNOTATIONS_SHA256 = (
    "091807d3ec993e2bde057c39f75ce3a051764c2a12a6a96204c475c8f3fea817"
)
DEFAULT_ANNOTATIONS_DERIVED_URL = (
    "https://raw.githubusercontent.com/unicode-org/cldr/"
    f"{DEFAULT_CLDR_REF}/common/annotationsDerived/en.xml"
)
DEFAULT_ANNOTATIONS_DERIVED_SHA256 = (
    "c3d08ed66d4f840ba8b1202a5c7f6c4336e3c65363c08144811dc3f587e92a80"
)
DEFAULT_OUTPUT_PATH = Path("meshdash/assets/chat_emoji_catalog.min.json")
DEFAULT_KEYWORD_CACHE_PATH = DEFAULT_OUTPUT_PATH

_GROUP_RE = re.compile(r"^#\s*group:\s*(.+?)\s*$")
_VERSION_RE = re.compile(r"^#\s*Version:\s*(.+?)\s*$")
_DATE_RE = re.compile(r"^#\s*Date:\s*(.+?)\s*$")
_EMOJI_RE = re.compile(
    r"^([0-9A-F ]+)\s*;\s*([a-z-]+)\s*#\s*(\S+)\s*(?:E[0-9.]+\s+)?(.+?)\s*$",
    re.IGNORECASE,
)

_ALLOWED_STATUSES = {"fully-qualified"}
# Codepoints that carry no searchable meaning of their own.
_PRESENTATION_SELECTORS = {0xFE0E, 0xFE0F}
_SKIN_TONE_MODIFIERS = set(range(0x1F3FB, 0x1F3FF + 1))
_MAX_KEYWORD_TOKENS = 24


def _slugify_group(label: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", label.strip().lower())
    token = re.sub(r"-+", "-", token).strip("-")
    return token or "group"


def _fold_search_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _keyword_tokens(text: str) -> list[str]:
    tokens = []
    for token in re.split(r"[^a-z0-9]+", _fold_search_text(text)):
        if not token:
            continue
        if len(token) < 2 and not token.isdigit():
            continue
        tokens.append(token)
    return tokens


def _merge_keyword_phrases(*phrases: str) -> str:
    seen: set[str] = set()
    merged: list[str] = []
    for phrase in phrases:
        for token in _keyword_tokens(phrase):
            if token in seen:
                continue
            seen.add(token)
            merged.append(token)
            if len(merged) >= _MAX_KEYWORD_TOKENS:
                return " ".join(merged)
    return " ".join(merged)


def _normalize_annotation_key(emoji: str) -> str:
    return "".join(ch for ch in emoji if ord(ch) not in _PRESENTATION_SELECTORS)


def _read_input_text(source: str) -> str:
    if source.startswith("http://") or source.startswith("https://"):
        with urllib.request.urlopen(source, timeout=30) as resp:
            return resp.read().decode("utf-8")
    return Path(source).read_text(encoding="utf-8")


def _read_checked_text(source: str, *, expected_sha256: str, label: str) -> str:
    text = _read_input_text(source)
    if expected_sha256:
        observed_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if observed_sha256.lower() != expected_sha256.lower():
            raise ValueError(
                f"{label} SHA-256 mismatch for {source}: "
                f"expected {expected_sha256}, got {observed_sha256}"
            )
    return text


def _string_keyword_map(value: object, *, label: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    out: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key or "").strip()
        keywords = str(raw_value or "").strip()
        if not key or not keywords:
            continue
        out[key] = keywords
    return out


def load_keyword_cache(source: str) -> tuple[dict[str, str], dict[str, str]]:
    """Read generated keyword maps from an existing catalog payload."""
    payload = json.loads(_read_input_text(source))
    if not isinstance(payload, dict):
        raise ValueError("keyword cache must be a JSON object")
    return (
        _string_keyword_map(
            payload.get("codepoint_keyword_map") or payload.get("codepointKeywordMap"),
            label="codepoint_keyword_map",
        ),
        _string_keyword_map(
            payload.get("emoji_keyword_map") or payload.get("emojiKeywordMap"),
            label="emoji_keyword_map",
        ),
    )


def parse_cldr_annotations(*xml_texts: str) -> dict[str, dict[str, str]]:
    """Map normalized emoji string -> {"keywords": ..., "tts": ...} from CLDR XML."""
    annotations: dict[str, dict[str, str]] = {}
    for xml_text in xml_texts:
        if not xml_text:
            continue
        root = ET.fromstring(xml_text)
        for node in root.iter("annotation"):
            cp = _normalize_annotation_key(node.get("cp") or "")
            if not cp:
                continue
            entry = annotations.setdefault(cp, {"keywords": "", "tts": ""})
            text = " ".join((node.text or "").replace("|", " ").split())
            if node.get("type") == "tts":
                entry["tts"] = text
            else:
                entry["keywords"] = text
    return annotations


def build_catalog(
    text: str,
    annotations: dict[str, dict[str, str]] | None = None,
    cached_codepoint_keyword_map: dict[str, str] | None = None,
    cached_emoji_keyword_map: dict[str, str] | None = None,
) -> dict[str, object]:
    version = "unknown"
    date_value = ""
    annotations = annotations or {}
    cached_codepoint_keyword_map = cached_codepoint_keyword_map or {}
    cached_emoji_keyword_map = cached_emoji_keyword_map or {}

    groups: list[dict[str, object]] = []
    group_index: dict[str, dict[str, object]] = {}
    codepoint_keyword_map: dict[str, str] = {}
    emoji_keyword_map: dict[str, str] = {}
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
        codepoints = [int(cp, 16) for cp in m_emoji.group(1).strip().split()]

        group = ensure_group(current_group_id, "Misc")
        emoji_list = group["emojis"]
        if isinstance(emoji_list, list) and emoji_value not in emoji_list:
            emoji_list.append(emoji_value)

        annotation = annotations.get(_normalize_annotation_key(emoji_value), {})
        keywords = _merge_keyword_phrases(
            name_value,
            annotation.get("tts", ""),
            annotation.get("keywords", ""),
        )
        if not keywords:
            continue

        meaningful = [cp for cp in codepoints if cp not in _PRESENTATION_SELECTORS]
        tone_free = [cp for cp in meaningful if cp not in _SKIN_TONE_MODIFIERS]
        if len(meaningful) == 1:
            key = f"{meaningful[0]:x}"
            codepoint_keyword_map.setdefault(
                key, cached_codepoint_keyword_map.get(key) or keywords
            )
        elif len(tone_free) == len(meaningful):
            # Sequences (flags, ZWJ, keycaps) need whole-emoji keywords; skin tone
            # variants are omitted because their base codepoint entry already
            # carries the searchable meaning.
            emoji_keyword_map.setdefault(
                emoji_value, cached_emoji_keyword_map.get(emoji_value) or keywords
            )
        elif len(tone_free) > 1:
            # Multi-person tone sequences sometimes have no tone-free
            # fully-qualified form (their base is a different codepoint, e.g.
            # people wrestling). Seed the tone-stripped key that the dashboard
            # falls back to, using only the base name before the tone suffix.
            base_keywords = _merge_keyword_phrases(name_value.split(":", 1)[0])
            if base_keywords:
                stripped_value = "".join(
                    chr(cp) for cp in codepoints if cp not in _SKIN_TONE_MODIFIERS
                )
                emoji_keyword_map.setdefault(
                    stripped_value,
                    cached_emoji_keyword_map.get(stripped_value) or base_keywords,
                )

    groups = [g for g in groups if isinstance(g.get("emojis"), list) and g["emojis"]]

    return {
        "ok": True,
        "version": version,
        "date": date_value,
        "groups": groups,
        "codepoint_keyword_map": codepoint_keyword_map,
        "emoji_keyword_map": emoji_keyword_map,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build chat_emoji_catalog.min.json from emoji-test.txt and CLDR annotations"
    )
    parser.add_argument(
        "--input", default=DEFAULT_INPUT_URL, help="Path or URL to emoji-test.txt"
    )
    parser.add_argument(
        "--input-sha256",
        default=DEFAULT_INPUT_SHA256,
        help="Expected SHA-256 of emoji-test.txt ('' to skip)",
    )
    parser.add_argument(
        "--expected-version",
        default=DEFAULT_EMOJI_VERSION,
        help="Expected # Version value from emoji-test.txt ('' to skip)",
    )
    parser.add_argument(
        "--annotations",
        default=DEFAULT_ANNOTATIONS_URL,
        help="Path or URL to CLDR common/annotations/en.xml ('' to skip)",
    )
    parser.add_argument(
        "--annotations-sha256",
        default=DEFAULT_ANNOTATIONS_SHA256,
        help="Expected SHA-256 of CLDR common/annotations/en.xml ('' to skip)",
    )
    parser.add_argument(
        "--annotations-derived",
        default=DEFAULT_ANNOTATIONS_DERIVED_URL,
        help="Path or URL to CLDR common/annotationsDerived/en.xml ('' to skip)",
    )
    parser.add_argument(
        "--annotations-derived-sha256",
        default=DEFAULT_ANNOTATIONS_DERIVED_SHA256,
        help="Expected SHA-256 of CLDR common/annotationsDerived/en.xml ('' to skip)",
    )
    parser.add_argument(
        "--keyword-cache",
        default=str(DEFAULT_KEYWORD_CACHE_PATH),
        help=(
            "Existing catalog JSON used to preserve expanded keywords if CLDR "
            "annotations are unavailable ('' to disable)"
        ),
    )
    parser.add_argument(
        "--allow-missing-annotations",
        action="store_true",
        help=(
            "Allow rebuilding with name-derived keywords if CLDR and keyword "
            "cache are unavailable"
        ),
    )
    parser.add_argument(
        "--output", default=str(DEFAULT_OUTPUT_PATH), help="Output JSON path"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_text = _read_checked_text(
        args.input, expected_sha256=args.input_sha256, label="emoji-test.txt"
    )
    annotation_error = ""
    annotations: dict[str, dict[str, str]] | None = None
    annotation_sources = (
        (args.annotations, args.annotations_sha256, "CLDR annotations"),
        (
            args.annotations_derived,
            args.annotations_derived_sha256,
            "CLDR derived annotations",
        ),
    )
    try:
        annotation_texts = [
            _read_checked_text(source, expected_sha256=expected_sha256, label=label)
            for source, expected_sha256, label in annotation_sources
            if source
        ]
        if annotation_texts:
            annotations = parse_cldr_annotations(*annotation_texts)
    except (OSError, UnicodeError, ValueError, ET.ParseError) as exc:
        annotation_error = str(exc)

    cached_codepoint_keyword_map: dict[str, str] = {}
    cached_emoji_keyword_map: dict[str, str] = {}
    if annotations is None:
        cache_error = ""
        if args.keyword_cache:
            try:
                (
                    cached_codepoint_keyword_map,
                    cached_emoji_keyword_map,
                ) = load_keyword_cache(args.keyword_cache)
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
                cache_error = str(exc)
        if not (
            cached_codepoint_keyword_map
            or cached_emoji_keyword_map
            or args.allow_missing_annotations
        ):
            reason = annotation_error or "CLDR annotations were skipped"
            if cache_error:
                reason = f"{reason}; keyword cache failed: {cache_error}"
            raise RuntimeError(
                f"{reason}. Provide valid CLDR sources, keep --keyword-cache, "
                "or pass --allow-missing-annotations."
            )
        if cached_codepoint_keyword_map or cached_emoji_keyword_map:
            reason = f": {annotation_error}" if annotation_error else ""
            print(f"using keyword cache from {args.keyword_cache}{reason}")

    payload = build_catalog(
        input_text,
        annotations,
        cached_codepoint_keyword_map=cached_codepoint_keyword_map,
        cached_emoji_keyword_map=cached_emoji_keyword_map,
    )
    expected_version = str(args.expected_version or "").strip()
    if expected_version and payload.get("version") != expected_version:
        raise RuntimeError(
            f"emoji-test.txt version mismatch: expected {expected_version}, "
            f"got {payload.get('version')}"
        )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"wrote {output_path}")
    print(f"version={payload.get('version')} date={payload.get('date')}")
    print(
        "codepoint_keywords="
        f"{len(payload.get('codepoint_keyword_map') or {})} "
        f"emoji_keywords={len(payload.get('emoji_keyword_map') or {})}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
