from typing import Optional

from .runtime_types import (
    BuildChatEntryFromPacketFn,
    BuildPacketSummaryFn,
    FormatEpochFn,
    ToIntFn,
    ToJsonableFn,
    TrackerPacket,
    TrackerParsedPacket,
    UtcNowFn,
)


def _copy_sender_names(target: dict[str, object], parsed: TrackerParsedPacket) -> None:
    short_name = str(parsed.get("from_short_name") or "").strip()
    long_name = str(parsed.get("from_long_name") or "").strip()
    if short_name:
        target["from_short_name"] = short_name
    if long_name:
        target["from_long_name"] = long_name
    display_name = long_name or short_name
    if display_name:
        target["from_name"] = display_name


def build_tracker_packet_artifacts(
    *,
    packet: TrackerPacket,
    parsed: TrackerParsedPacket,
    include_live_count: bool,
    build_packet_summary_fn: BuildPacketSummaryFn,
    build_chat_entry_from_packet_fn: BuildChatEntryFromPacketFn,
    utc_now_fn: UtcNowFn,
    format_epoch_fn: FormatEpochFn,
    to_int_fn: ToIntFn,
    to_jsonable_fn: ToJsonableFn,
) -> tuple[dict[str, object], Optional[dict[str, object]]]:
    packet_summary = build_packet_summary_fn(
        packet=packet,
        decoded=parsed["decoded"],
        from_id=parsed["from_id"],
        to_id=parsed["to_id"],
        packet_id=parsed["packet_id"],
        rx_time=parsed["rx_time"],
        hops=parsed["hops"],
        reply_id=parsed["reply_id"],
        emoji_glyph=parsed["emoji_glyph"],
        emoji_codepoint=parsed["emoji_codepoint"],
        is_reaction=parsed["is_reaction"],
        packet_position=parsed["packet_position"],
        packet_battery=parsed["packet_battery"],
        utc_now_fn=utc_now_fn,
        format_epoch_fn=format_epoch_fn,
        to_int_fn=to_int_fn,
    )
    _copy_sender_names(packet_summary, parsed)
    packet_summary["live"] = include_live_count

    packet_entry = {
        "summary": packet_summary,
        "packet": to_jsonable_fn(packet),
    }

    chat_entry = build_chat_entry_from_packet_fn(
        packet=packet,
        decoded=parsed["decoded"],
        from_id=parsed["from_id"],
        to_id=parsed["to_id"],
        packet_id=parsed["packet_id"],
        hops=parsed["hops"],
        reply_id=parsed["reply_id"],
        emoji_glyph=parsed["emoji_glyph"],
        emoji_codepoint=parsed["emoji_codepoint"],
        is_reaction=parsed["is_reaction"],
        utc_now_fn=utc_now_fn,
        format_epoch_fn=format_epoch_fn,
    )
    if chat_entry is not None:
        _copy_sender_names(chat_entry, parsed)
    return packet_entry, chat_entry
