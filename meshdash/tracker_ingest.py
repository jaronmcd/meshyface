from .runtime_types import (
    CalculateHopsFn,
    EmojiFromCodepointFn,
    ExtractEmojiCodepointFn,
    ExtractPacketBatteryLevelFn,
    ExtractPacketPositionFn,
    ExtractReplyIdFn,
    GetNodeIdFromNumFn,
    ToIntFn,
    TrackerPacket,
    TrackerParsedPacket,
)
from .helpers_node_names import extract_user_names_from_packet as _extract_user_names_from_packet
from .tracker_neighbor_info import extract_neighbor_info_edges as _extract_neighbor_info_edges_helper
from .helpers_packet_meta import extract_reaction_emoji as _extract_reaction_emoji


def _normalize_packet_node_id(value: object) -> object:
    text = str(value or "").strip()
    if not text:
        return value
    lowered = text.lower()
    if lowered in ("^all", "all", "broadcast", "!ffffffff", "ffffffff", "0xffffffff", "4294967295"):
        return "^all"
    if text.startswith("!") and len(text) == 9:
        raw = text[1:]
        if all(ch in "0123456789abcdefABCDEF" for ch in raw):
            return f"!{raw.lower()}"
    if len(text) == 8 and all(ch in "0123456789abcdefABCDEF" for ch in text):
        return f"!{text.lower()}"
    return text


def _canonical_outer_node_id(value: object) -> str:
    """Canonicalize the numeric packet header identity without consulting NodeDB."""
    if isinstance(value, bool):
        return ""
    if isinstance(value, float) and not value.is_integer():
        return ""
    try:
        numeric = int(value)
    except (TypeError, ValueError, OverflowError):
        return ""
    if numeric < 0 or numeric > 0xFFFFFFFF:
        return ""
    if numeric == 0xFFFFFFFF:
        return "^all"
    return f"!{numeric:08x}"


def _clean_node_name(value: object) -> str:
    return str(value or "").replace("\x00", "").strip()


def _extract_sender_names_from_node_entry(node: object, sender_id: object = "") -> tuple[str, str]:
    if not isinstance(node, dict):
        return "", ""
    clean_sender = str(_normalize_packet_node_id(sender_id) or "").strip()
    candidates: list[dict[str, object]] = []
    user = node.get("user")
    if isinstance(user, dict):
        candidates.append(user)
    candidates.append(node)

    short_name = ""
    long_name = ""
    for candidate in candidates:
        candidate_id = str(_normalize_packet_node_id(candidate.get("id") or candidate.get("node_id")) or "").strip()
        if candidate_id and clean_sender and candidate_id != clean_sender:
            continue
        if not short_name:
            short_name = _clean_node_name(candidate.get("shortName") or candidate.get("short_name"))
        if not long_name:
            long_name = _clean_node_name(candidate.get("longName") or candidate.get("long_name"))
        if short_name and long_name:
            break
    return short_name, long_name


def _extract_sender_names_from_interface(
    interface: object,
    *,
    sender_id: object,
    sender_num: object,
    to_int_fn: ToIntFn,
) -> tuple[str, str]:
    nodes_by_num = getattr(interface, "nodesByNum", None) or {}
    if not isinstance(nodes_by_num, dict):
        return "", ""

    node = None
    sender_num_int = to_int_fn(sender_num)
    if sender_num_int is not None:
        node = nodes_by_num.get(sender_num_int)

    clean_sender = str(_normalize_packet_node_id(sender_id) or "").strip()
    if not isinstance(node, dict) and clean_sender:
        for candidate in nodes_by_num.values():
            short_name, long_name = _extract_sender_names_from_node_entry(candidate, clean_sender)
            if short_name or long_name:
                return short_name, long_name
        return "", ""

    return _extract_sender_names_from_node_entry(node, clean_sender)


def parse_tracker_packet(
    packet: TrackerPacket,
    interface: object,
    *,
    get_node_id_from_num_fn: GetNodeIdFromNumFn,
    to_int_fn: ToIntFn,
    calculate_hops_fn: CalculateHopsFn,
    extract_packet_position_fn: ExtractPacketPositionFn,
    extract_packet_battery_level_fn: ExtractPacketBatteryLevelFn,
    extract_reply_id_fn: ExtractReplyIdFn,
    extract_emoji_codepoint_fn: ExtractEmojiCodepointFn,
    emoji_from_codepoint_fn: EmojiFromCodepointFn,
) -> TrackerParsedPacket:
    # Packet-header numbers are the transport identity. NodeDB names/ids are
    # untrusted display metadata and must not override them.
    raw_from = packet.get("from")
    raw_to = packet.get("to")
    from_id = _canonical_outer_node_id(raw_from)
    to_id = (
        _canonical_outer_node_id(raw_to)
        if raw_to is not None
        else _normalize_packet_node_id(packet.get("toId"))
    )
    rx_time = to_int_fn(packet.get("rxTime"))
    hops = calculate_hops_fn(packet.get("hopStart"), packet.get("hopLimit"))

    decoded = packet.get("decoded", {})
    portnum = decoded.get("portnum") if isinstance(decoded, dict) else None
    packet_id = to_int_fn(packet.get("id"))
    packet_position = extract_packet_position_fn(packet)
    packet_battery = extract_packet_battery_level_fn(packet)
    reply_id = extract_reply_id_fn(decoded)
    emoji_codepoint = extract_emoji_codepoint_fn(decoded)
    emoji_glyph = emoji_from_codepoint_fn(emoji_codepoint)
    if not emoji_glyph and reply_id is not None and reply_id > 0:
        fallback_emoji, fallback_codepoint = _extract_reaction_emoji(decoded)
        if fallback_emoji:
            emoji_glyph = fallback_emoji
            if emoji_codepoint is None and fallback_codepoint is not None and fallback_codepoint > 0:
                emoji_codepoint = fallback_codepoint
    is_reaction = bool(reply_id is not None and reply_id > 0 and emoji_glyph)
    neighbor_info_edges = _extract_neighbor_info_edges_helper(
        decoded,
        outer_source_id=from_id,
    )
    short_name, long_name = _extract_user_names_from_packet(
        {"from": from_id, "from_num": packet.get("from")},
        packet,
    )
    if not short_name and not long_name:
        short_name, long_name = _extract_sender_names_from_interface(
            interface,
            sender_id=from_id,
            sender_num=packet.get("from"),
            to_int_fn=to_int_fn,
        )

    return {
        "from_id": from_id,
        "to_id": to_id,
        "from_short_name": short_name,
        "from_long_name": long_name,
        "rx_time": rx_time,
        "rx_snr": packet.get("rxSnr"),
        "rx_rssi": packet.get("rxRssi"),
        "hops": hops,
        "decoded": decoded,
        "portnum": portnum,
        "packet_id": packet_id,
        "packet_position": packet_position,
        "packet_battery": packet_battery,
        "reply_id": reply_id,
        "emoji_codepoint": emoji_codepoint,
        "emoji_glyph": emoji_glyph,
        "is_reaction": is_reaction,
        "neighbor_info_edges": neighbor_info_edges,
    }
