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
    from_id = _normalize_packet_node_id(
        packet.get("fromId") or get_node_id_from_num_fn(interface, packet.get("from"))
    )
    to_id = _normalize_packet_node_id(
        packet.get("toId") or get_node_id_from_num_fn(interface, packet.get("to"))
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
    is_reaction = bool(reply_id is not None and reply_id > 0 and emoji_glyph)

    return {
        "from_id": from_id,
        "to_id": to_id,
        "rx_time": rx_time,
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
    }
