from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
from typing import Iterable

from .port_tools.extract_upstream_rooms import extract_rooms_from_file


ZORK_DIR = Path(__file__).resolve().parent
UPSTREAM_DUNG_PATH = ZORK_DIR / "upstream_1977" / "zork-master" / "zork" / "dung.56"
START_ROOM = "WHOUS"


@dataclass(frozen=True)
class RoomData:
    code: str
    short_name: str
    long_desc: str
    lit: bool
    exits: tuple[dict[str, object], ...]
    visible_object_codes: tuple[str, ...]
    handler_name: str = ""
    score_value: int = 0


@dataclass(frozen=True)
class ObjectData:
    code: str
    kind: str
    name: str
    short_desc: str
    detail_desc: str
    read_desc: str
    aliases: tuple[str, ...]
    adjectives: tuple[str, ...]
    flags: frozenset[str]
    contents: tuple[str, ...]
    parent: str | None
    function_name: str = ""

    @property
    def vocabulary(self) -> tuple[str, ...]:
        values: list[str] = []
        for raw in (
            self.code,
            self.name,
            self.short_desc,
            *self.aliases,
            *self.adjectives,
        ):
            values.extend(_clean_words(raw))
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not value or value in seen:
                continue
            seen.add(value)
            deduped.append(value)
        return tuple(deduped)


ROOM_DESC_OVERRIDES: dict[str, str] = {
    "CELLA": (
        "You are in a dark and damp cellar with a narrow passageway leading east, "
        "and a crawlway to the south. On the west is the bottom of a steep metal ramp."
    ),
    "MGRAT": "You are in a small room under a grating. Sunlight filters weakly from above.",
}


SPECIAL_VISIBLE_CODE_ALIASES = {
    "GATES": "DAM",
}


SPECIAL_OBJECT_NAME_OVERRIDES = {
    "DOOR": "trap door",
    "TDOOR": "trap door",
    "WDOOR": "wooden door",
    "FDOOR": "front door",
    "SDOOR": "stone door",
    "WIND1": "window",
    "WIND2": "window",
    "GRAT1": "grating",
    "GRAT2": "grating",
}


SPECIAL_OBJECT_READ_OVERRIDES = {
    "WDOOR": "The engravings translate to 'This space intentionally left blank'.",
}


def _clean_words(raw: str) -> list[str]:
    text = str(raw or "").replace("\\.", "")
    return [part for part in re.findall(r"[a-z0-9]+", text.lower()) if part]


def _read_string(text: str, start_index: int) -> tuple[str, int]:
    if start_index >= len(text) or text[start_index] != '"':
        raise ValueError(f"Expected string at offset {start_index}")
    out: list[str] = []
    index = start_index + 1
    escape = False
    while index < len(text):
        ch = text[index]
        if escape:
            out.append(ch)
            escape = False
            index += 1
            continue
        if ch == "\\":
            escape = True
            index += 1
            continue
        if ch == '"':
            return "".join(out), index + 1
        out.append(ch)
        index += 1
    raise ValueError(f"Unterminated string starting at {start_index}")


def _find_matching(text: str, start_index: int, open_ch: str, close_ch: str) -> int:
    depth = 0
    in_string = False
    escape = False
    for index in range(start_index, len(text)):
        ch = text[index]
        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == open_ch:
            depth += 1
            continue
        if ch == close_ch:
            depth -= 1
            if depth == 0:
                return index
    raise ValueError(f"Unterminated block starting at {start_index}")


def _read_balanced(text: str, start_index: int, open_ch: str, close_ch: str) -> tuple[str, int]:
    end_index = _find_matching(text, start_index, open_ch, close_ch)
    return text[start_index : end_index + 1], end_index + 1


def _tokenize_top_level(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    index = 0
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        ch = text[index]
        if ch == '"':
            value, index = _read_string(text, index)
            tokens.append(("string", value))
            continue
        if ch == "(":
            value, index = _read_balanced(text, index, "(", ")")
            tokens.append(("paren", value))
            continue
        if ch == "{":
            value, index = _read_balanced(text, index, "{", "}")
            tokens.append(("brace", value))
            continue
        if ch == "[":
            value, index = _read_balanced(text, index, "[", "]")
            tokens.append(("bracket", value))
            continue
        if ch == "<" or (ch == "%" and index + 1 < len(text) and text[index + 1] == "<"):
            prefix = ""
            if ch == "%":
                prefix = "%"
                index += 1
            value, index = _read_balanced(text, index, "<", ">")
            tokens.append(("angle", prefix + value))
            continue
        end_index = index
        while end_index < len(text) and not text[end_index].isspace() and text[end_index] not in '(){}[]<>"':
            end_index += 1
        tokens.append(("symbol", text[index:end_index]))
        index = end_index
    return tokens


def _extract_find_obj_codes(raw: str) -> tuple[str, ...]:
    return tuple(match.group(1) for match in re.finditer(r'FIND-OBJ\s*(?:\{\s*)?"([A-Z0-9]+)"', raw))


def _extract_flags(raw: str) -> frozenset[str]:
    return frozenset(match.group(1) for match in re.finditer(r",([A-Z][A-Z0-9-]*BIT)", raw))


def _extract_alias_groups(raw: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    groups = re.findall(r"\[(.*?)\]", raw, flags=re.S)
    first = tuple(re.findall(r'"([^"]*)"', groups[0])) if groups else tuple()
    second = tuple(re.findall(r'"([^"]*)"', groups[1])) if len(groups) > 1 else tuple()
    return first, second


def _extract_alias_groups_after(text: str, start_index: int) -> tuple[tuple[str, ...], tuple[str, ...]]:
    end_index = text.find(">", start_index)
    if end_index < 0:
        end_index = min(len(text), start_index + 160)
    raw = text[start_index:end_index]
    return _extract_alias_groups(raw)


def _normalize_symbol_name(raw: str) -> str:
    value = str(raw or "").strip()
    if value in {",DOORSTR", "DOORSTR"}:
        return "door"
    if value in {",BUTSTR", "BUTSTR"}:
        return "button"
    return value.lstrip(",").replace("-", " ").replace("_", " ").lower()


@lru_cache(maxsize=1)
def _parse_rooms_and_room_meta() -> tuple[dict[str, RoomData], dict[str, dict[str, object]]]:
    rooms_from_extractor = extract_rooms_from_file(UPSTREAM_DUNG_PATH)
    rooms_by_code = {
        str(room.get("code") or "").strip().upper(): room
        for room in rooms_from_extractor
        if str(room.get("code") or "").strip()
    }

    text = UPSTREAM_DUNG_PATH.read_text("latin1", errors="replace")
    meta_by_code: dict[str, dict[str, object]] = {}
    cursor = 0
    needle = '#ROOM {"'
    while True:
        start = text.find(needle, cursor)
        if start < 0:
            break
        brace_start = text.find("{", start)
        if brace_start < 0:
            break
        room_block, cursor = _read_balanced(text, brace_start, "{", "}")
        tokens = _tokenize_top_level(room_block[1:-1])
        if not tokens or tokens[0][0] != "string":
            continue
        code = str(tokens[0][1] or "").strip().upper()
        if not code:
            continue
        lit = False
        handler_name = ""
        score_value = 0
        for index, (kind, value) in enumerate(tokens):
            if kind == "symbol" and value == "#EXIT":
                lead_tokens = tokens[:index]
                lit = any(item_kind == "symbol" and item_value == "T" for item_kind, item_value in lead_tokens)
                tail_tokens = tokens[index + 2 :]
                for tail_kind, tail_value in tail_tokens:
                    if tail_kind != "symbol":
                        continue
                    if tail_value.isdigit() or tail_value.startswith("%,"):
                        if tail_value.isdigit() and score_value <= 0:
                            score_value = int(tail_value)
                        continue
                    if not handler_name:
                        handler_name = tail_value
                        continue
                break
        meta_by_code[code] = {
            "lit": lit,
            "handler_name": handler_name,
            "score_value": score_value,
        }

    final_rooms: dict[str, RoomData] = {}
    for code, base in rooms_by_code.items():
        meta = meta_by_code.get(code, {})
        long_desc = str(base.get("long_desc") or "").strip()
        if not long_desc:
            long_desc = ROOM_DESC_OVERRIDES.get(code, "")
        final_rooms[code] = RoomData(
            code=code,
            short_name=str(base.get("short_name") or "").strip(),
            long_desc=long_desc,
            lit=bool(meta.get("lit")),
            exits=tuple(dict(row) for row in (base.get("exits") or [])),
            visible_object_codes=tuple(str(row).strip().upper() for row in (base.get("visible_object_codes") or []) if str(row).strip()),
            handler_name=str(meta.get("handler_name") or "").strip(),
            score_value=int(meta.get("score_value") or 0),
        )
    return final_rooms, meta_by_code


@lru_cache(maxsize=1)
def _parse_objects() -> dict[str, ObjectData]:
    text = UPSTREAM_DUNG_PATH.read_text("latin1", errors="replace")
    read_desc_by_code: dict[str, str] = {}
    for match in re.finditer(r'<ADD-DESC\s*<FIND-OBJ\s*"([A-Z0-9]+)">\s*', text):
        code = str(match.group(1) or "").strip().upper()
        index = match.end()
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            continue
        if text[index] == '"':
            desc, _ = _read_string(text, index)
            read_desc_by_code[code] = desc
    objects: dict[str, ObjectData] = {}

    # Full #OBJECT blocks.
    cursor = 0
    needle = "#OBJECT {"
    while True:
        start = text.find(needle, cursor)
        if start < 0:
            break
        brace_start = text.find("{", start)
        if brace_start < 0:
            break
        object_block, cursor = _read_balanced(text, brace_start, "{", "}")
        block_text = object_block[1:-1]
        tokens = _tokenize_top_level(block_text)
        if len(tokens) < 3 or tokens[0][0] != "string":
            continue
        code = str(tokens[0][1] or "").strip().upper()
        if not code or code.startswith("#"):
            continue
        short_desc = str(tokens[1][1] or "") if len(tokens) > 1 and tokens[1][0] == "string" else ""
        name = str(tokens[2][1] or "") if len(tokens) > 2 and tokens[2][0] == "string" else ""
        detail_desc = str(tokens[3][1] or "") if len(tokens) > 3 and tokens[3][0] == "string" else ""
        function_name = ""
        contents: tuple[str, ...] = tuple()
        parent: str | None = None
        for index, (kind, value) in enumerate(tokens[4:], start=4):
            if (
                not function_name
                and kind == "symbol"
                and not value.startswith(",")
                and value != "#FIND-OBJ"
                and not value.isdigit()
                and not value.startswith("%")
            ):
                function_name = value
            if kind == "paren" and not contents:
                contents = tuple(code_value for code_value in _extract_find_obj_codes(value) if code_value)
                continue
            if parent is None:
                matches = _extract_find_obj_codes(value)
                if matches:
                    parent = matches[0]
                    continue
                if kind == "symbol" and value == "#FIND-OBJ":
                    next_index = index + 1
                    if next_index < len(tokens) and tokens[next_index][0] == "brace":
                        brace_matches = re.findall(r'"([A-Z0-9]+)"', tokens[next_index][1])
                        if brace_matches:
                            parent = brace_matches[0]
                            continue
        flag_source = object_block
        aliases, adjectives = _extract_alias_groups_after(text, cursor)
        objects[code] = ObjectData(
            code=code,
            kind="object",
            name=SPECIAL_OBJECT_NAME_OVERRIDES.get(code, name) or _normalize_symbol_name(name),
            short_desc=short_desc,
            detail_desc=detail_desc,
            read_desc=str(read_desc_by_code.get(code) or "").strip() or SPECIAL_OBJECT_READ_OVERRIDES.get(code, ""),
            aliases=aliases,
            adjectives=adjectives,
            flags=_extract_flags(flag_source),
            contents=contents,
            parent=parent,
            function_name=function_name,
        )

    # Abstract/simple objects declared with <AOBJECT ...> / <SOBJECT ...>.
    for kind_name in ("AOBJECT", "SOBJECT"):
        cursor = 0
        needle = f"<{kind_name} "
        while True:
            start = text.find(needle, cursor)
            if start < 0:
                break
            object_block, cursor = _read_balanced(text, start, "<", ">")
            tokens = _tokenize_top_level(object_block[1:-1])
            if len(tokens) < 3 or tokens[0][1] != kind_name or tokens[1][0] != "string":
                continue
            code = str(tokens[1][1] or "").strip().upper()
            if not code or code in objects:
                continue
            raw_name_token = tokens[2]
            if raw_name_token[0] == "string":
                name = str(raw_name_token[1] or "")
            else:
                name = _normalize_symbol_name(raw_name_token[1])
            function_name = ""
            for tail_kind, tail_value in tokens[3:]:
                if (
                    tail_kind == "symbol"
                    and not tail_value.startswith(",")
                    and not tail_value.isdigit()
                    and not tail_value.startswith("%")
                ):
                    function_name = tail_value
                    break
            aliases, adjectives = _extract_alias_groups_after(text, cursor)
            objects[code] = ObjectData(
                code=code,
                kind=kind_name.lower(),
                name=SPECIAL_OBJECT_NAME_OVERRIDES.get(code, name) or name,
                short_desc="",
                detail_desc="",
                read_desc=str(read_desc_by_code.get(code) or "").strip() or SPECIAL_OBJECT_READ_OVERRIDES.get(code, ""),
                aliases=aliases,
                adjectives=adjectives,
                flags=_extract_flags(object_block),
                contents=tuple(),
                parent=None,
                function_name=function_name,
            )

    # Some visible references use alias tokens instead of canonical object codes.
    for code, target in SPECIAL_VISIBLE_CODE_ALIASES.items():
        if code not in objects and target in objects:
            target_obj = objects[target]
            objects[code] = ObjectData(
                code=code,
                kind=target_obj.kind,
                name=target_obj.name,
                short_desc=target_obj.short_desc,
                detail_desc=target_obj.detail_desc,
                read_desc=target_obj.read_desc,
                aliases=target_obj.aliases,
                adjectives=target_obj.adjectives,
                flags=target_obj.flags,
                contents=target_obj.contents,
                parent=target_obj.parent,
                function_name=target_obj.function_name,
            )

    return objects


@lru_cache(maxsize=1)
def rooms() -> dict[str, RoomData]:
    room_map, _ = _parse_rooms_and_room_meta()
    return room_map


@lru_cache(maxsize=1)
def objects() -> dict[str, ObjectData]:
    return _parse_objects()


@lru_cache(maxsize=1)
def object_alias_index() -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for code, item in objects().items():
        for token in item.vocabulary:
            index.setdefault(token, set()).add(code)
        index.setdefault(code.lower(), set()).add(code)
    return index


@lru_cache(maxsize=1)
def initial_object_locations() -> dict[str, str]:
    room_map = rooms()
    object_map = objects()
    locations: dict[str, str] = {}
    # Room-anchored objects.
    for room_code, room in room_map.items():
        for visible_code in room.visible_object_codes:
            canonical_code = visible_code if visible_code in object_map else SPECIAL_VISIBLE_CODE_ALIASES.get(visible_code, visible_code)
            if canonical_code not in object_map:
                continue
            locations.setdefault(canonical_code, room_code)
    # Parent/contained objects.
    for code, item in object_map.items():
        if item.parent:
            locations[code] = item.parent
        elif code not in locations and item.kind == "object" and item.contents:
            # Container already placed elsewhere or later visible.
            continue
    return dict(locations)


ROOMS = rooms()
OBJECTS = objects()
OBJECT_ALIAS_INDEX = object_alias_index()
INITIAL_OBJECT_LOCATIONS = initial_object_locations()


def room_name(room_code: str) -> str:
    room = ROOMS.get(str(room_code or "").strip().upper())
    if room is None:
        return str(room_code or "").strip() or START_ROOM
    if room.short_name:
        return room.short_name
    return room.code.title()


def object_name(code: str) -> str:
    item = OBJECTS.get(str(code or "").strip().upper())
    if item is None:
        return str(code or "").strip().lower()
    cleaned = " ".join(_clean_words(item.name))
    if cleaned:
        return cleaned
    return item.code.lower()


__all__ = [
    "INITIAL_OBJECT_LOCATIONS",
    "OBJECTS",
    "OBJECT_ALIAS_INDEX",
    "ROOMS",
    "START_ROOM",
    "ObjectData",
    "RoomData",
    "object_name",
    "room_name",
]
