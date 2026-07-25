from __future__ import annotations

import json
import re
from pathlib import Path


PORT_TOOLS_DIR = Path(__file__).resolve().parent
ZORK_DIR = PORT_TOOLS_DIR.parent
UPSTREAM_DUNG_PATH = ZORK_DIR / "upstream_1977" / "zork-master" / "zork" / "dung.56"
OUTPUT_PATH = ZORK_DIR / "upstream_1977" / "extracted_rooms.json"


def _find_matching_brace(text: str, start_index: int) -> int:
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
        if ch == "{":
            depth += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError(f"Unterminated brace block starting at {start_index}")


def _find_room_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    cursor = 0
    needle = "#ROOM {"
    while True:
        start = text.find(needle, cursor)
        if start < 0:
            break
        brace_start = text.find("{", start)
        if brace_start < 0:
            break
        brace_end = _find_matching_brace(text, brace_start)
        blocks.append(text[start : brace_end + 1])
        cursor = brace_end + 1
    return blocks


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


def _skip_ws(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _read_hash_token(text: str, start_index: int) -> tuple[str, int]:
    index = start_index
    while index < len(text) and not text[index].isspace() and text[index] not in "{}":
        index += 1
    return text[start_index:index], index


def _extract_setg_string_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for match in re.finditer(r"<(?:PSETG|SETG)\s+([A-Z0-9-]+)\s+", text):
        symbol = str(match.group(1) or "").strip().upper()
        if not symbol:
            continue
        index = _skip_ws(text, match.end())
        if index >= len(text) or text[index] != '"':
            continue
        value, _ = _read_string(text, index)
        values[symbol] = value
    return values


def _extract_strings(text: str) -> list[str]:
    out: list[str] = []
    index = 0
    while index < len(text):
        if text[index] != '"':
            index += 1
            continue
        value, index = _read_string(text, index)
        out.append(value)
    return out


def _extract_exit_block(room_block: str) -> str:
    marker = "#EXIT {"
    index = room_block.find(marker)
    if index < 0:
        return ""
    brace_start = room_block.find("{", index)
    if brace_start < 0:
        return ""
    brace_end = _find_matching_brace(room_block, brace_start)
    return room_block[brace_start + 1 : brace_end]


def _parse_exit_entries(exit_block: str) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    index = 0
    while index < len(exit_block):
        index = _skip_ws(exit_block, index)
        if index >= len(exit_block):
            break
        if exit_block[index] != '"':
            index += 1
            continue
        direction, index = _read_string(exit_block, index)
        index = _skip_ws(exit_block, index)
        if index >= len(exit_block):
            entries.append({"direction": direction, "kind": "unknown"})
            break
        if exit_block[index] == '"':
            target, index = _read_string(exit_block, index)
            entries.append(
                {
                    "direction": direction,
                    "kind": "room",
                    "target": target,
                }
            )
            continue
        if exit_block[index] != "#":
            entries.append({"direction": direction, "kind": "unknown"})
            index += 1
            continue
        token, index = _read_hash_token(exit_block, index)
        index = _skip_ws(exit_block, index)
        if index < len(exit_block) and exit_block[index] == "{":
            brace_end = _find_matching_brace(exit_block, index)
            inner = exit_block[index + 1 : brace_end]
            strings = _extract_strings(inner)
            index = brace_end + 1
        elif index < len(exit_block) and exit_block[index] == '"':
            message, index = _read_string(exit_block, index)
            strings = [message]
        else:
            strings = []
        row: dict[str, object] = {
            "direction": direction,
            "kind": token.lstrip("#").lower(),
        }
        if token.upper() in ("#CEXIT", "#FEXIT"):
            if strings:
                row["condition"] = strings[0]
            if len(strings) > 1:
                row["target"] = strings[1]
            if len(strings) > 2:
                row["message"] = strings[2]
        elif token.upper() == "#NEXIT":
            if strings:
                row["message"] = strings[0]
        else:
            if strings:
                row["args"] = strings
        entries.append(row)
    return entries


def _read_room_text_field(text: str, start_index: int, string_values: dict[str, str]) -> tuple[str, int]:
    index = _skip_ws(text, start_index)
    if index >= len(text):
        return "", index
    if text[index] == '"':
        return _read_string(text, index)
    if text.startswith("%,", index):
        end_index = index + 2
        while end_index < len(text) and (text[end_index].isalnum() or text[end_index] in {"-", "_"}):
            end_index += 1
        symbol = text[index + 2 : end_index].strip().upper()
        if not symbol:
            return "", end_index
        return str(string_values.get(symbol) or ""), end_index
    if text.startswith("%<>", index):
        return "", index + 3
    return "", index


def _parse_room_block(room_block: str, string_values: dict[str, str]) -> dict[str, object]:
    code_index = room_block.find('"')
    if code_index < 0:
        raise ValueError("Room block missing room code string")
    room_code, index = _read_string(room_block, code_index)
    long_desc, index = _read_room_text_field(room_block, index, string_values)
    short_name, index = _read_room_text_field(room_block, index, string_values)
    exits = _parse_exit_entries(_extract_exit_block(room_block))
    visible_objects = sorted(
        {
            match.group(1)
            for match in re.finditer(r'#FIND-OBJ\s*\{\s*"([A-Z0-9]+)"\s*\}', room_block)
        }
    )
    return {
        "code": room_code,
        "short_name": short_name,
        "long_desc": long_desc,
        "exits": exits,
        "visible_object_codes": visible_objects,
    }


def extract_rooms(text: str) -> list[dict[str, object]]:
    string_values = _extract_setg_string_values(text)
    rooms = [_parse_room_block(block, string_values) for block in _find_room_blocks(text)]
    deduped: list[dict[str, object]] = []
    seen_codes: set[str] = set()
    for room in rooms:
        code = str(room.get("code") or "").strip().upper()
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        deduped.append(room)
    return deduped


def extract_rooms_from_file(path: Path) -> list[dict[str, object]]:
    text = path.read_text("latin1", errors="replace")
    return extract_rooms(text)


def write_extracted_rooms(source_path: Path = UPSTREAM_DUNG_PATH, output_path: Path = OUTPUT_PATH) -> Path:
    rooms = extract_rooms_from_file(source_path)
    payload = {
        "source": str(source_path),
        "room_count": len(rooms),
        "rooms": rooms,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return output_path


def main() -> int:
    output_path = write_extracted_rooms()
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
