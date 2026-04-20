import re
from collections.abc import Mapping


_GENERIC_MESHTASTIC_RE = re.compile(r"^meshtastic(?:[\s_-]+([0-9a-f]{4,8}))?$", re.IGNORECASE)


def clean_node_name(value: object) -> str:
    return str(value or "").replace("\x00", "").strip()


def normalize_node_id_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in {
        "^all",
        "all",
        "broadcast",
        "!ffffffff",
        "ffffffff",
        "0xffffffff",
        "4294967295",
    }:
        return "^all"
    if text.startswith("!") and len(text) == 9 and all(ch in "0123456789abcdefABCDEF" for ch in text[1:]):
        return f"!{text[1:].lower()}"
    if len(text) == 8 and all(ch in "0123456789abcdefABCDEF" for ch in text):
        return f"!{text.lower()}"
    return text


def is_generic_node_name(value: object, node_id: object = "") -> bool:
    clean_value = clean_node_name(value)
    if not clean_value:
        return False
    lowered = clean_value.lower()
    normalized_node_id = normalize_node_id_text(node_id)
    raw_hex = normalized_node_id[1:] if normalized_node_id.startswith("!") else ""
    short_hex = raw_hex[-4:] if len(raw_hex) >= 4 else raw_hex
    if raw_hex and lowered in {raw_hex, short_hex}:
        return True
    match = _GENERIC_MESHTASTIC_RE.fullmatch(lowered)
    if not match:
        return False
    suffix = str(match.group(1) or "").strip().lower()
    if not suffix:
        return True
    return bool(raw_hex) and suffix in {raw_hex, short_hex}


def prefer_stable_node_name(
    current_value: object,
    historical_value: object,
    node_id: object = "",
) -> str:
    current_name = clean_node_name(current_value)
    historical_name = clean_node_name(historical_value)
    if current_name and not is_generic_node_name(current_name, node_id):
        return current_name
    if historical_name and not is_generic_node_name(historical_name, node_id):
        return historical_name
    return current_name or historical_name


def extract_user_names_from_packet(
    summary: Mapping[str, object] | None,
    packet: Mapping[str, object] | None,
) -> tuple[str, str]:
    safe_summary = summary if isinstance(summary, Mapping) else {}
    safe_packet = packet if isinstance(packet, Mapping) else {}
    decoded = safe_packet.get("decoded")
    safe_decoded = decoded if isinstance(decoded, Mapping) else {}
    sender_id = normalize_node_id_text(
        safe_summary.get("from")
        or safe_summary.get("from_id")
        or safe_summary.get("from_num")
        or safe_packet.get("fromId")
        or safe_packet.get("from_id")
        or safe_packet.get("from")
    )

    candidates: list[Mapping[str, object]] = []
    for value in (
        safe_packet.get("user"),
        safe_decoded.get("user"),
        safe_decoded.get("nodeinfo"),
        safe_decoded.get("nodeInfo"),
        safe_decoded.get("payload"),
        safe_decoded.get("admin"),
    ):
        if not isinstance(value, Mapping):
            continue
        nested_user = value.get("user")
        if isinstance(nested_user, Mapping):
            candidates.append(nested_user)
        candidates.append(value)

    short_name = ""
    long_name = ""
    for candidate in candidates:
        candidate_id = normalize_node_id_text(candidate.get("id") or candidate.get("node_id"))
        if candidate_id and sender_id and candidate_id != sender_id:
            continue
        if not short_name:
            short_name = clean_node_name(candidate.get("shortName") or candidate.get("short_name"))
        if not long_name:
            long_name = clean_node_name(candidate.get("longName") or candidate.get("long_name"))
        if short_name and long_name:
            break

    if not short_name:
        short_name = clean_node_name(safe_summary.get("from_short_name"))
    if not long_name:
        long_name = clean_node_name(safe_summary.get("from_long_name") or safe_summary.get("from_name"))
    return short_name, long_name
