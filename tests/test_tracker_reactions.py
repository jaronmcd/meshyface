import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.helpers_emoji import emoji_from_codepoint
from meshdash.helpers_packet_meta import extract_emoji_codepoint, extract_reply_id
from meshdash.tracker_entries import build_chat_entry_from_packet
from meshdash.tracker_ingest import parse_tracker_packet


def _node_id_from_num(_interface: object, node_num: object) -> str:
    mapping = {
        101: "!00000065",
        202: "!000000ca",
    }
    try:
        clean = int(node_num)
    except (TypeError, ValueError):
        return ""
    return mapping.get(clean, "")


def _parse_packet(packet: dict[str, object]) -> dict[str, object]:
    return parse_tracker_packet(
        packet,
        object(),
        get_node_id_from_num_fn=_node_id_from_num,
        to_int_fn=lambda value: int(value) if value is not None else None,
        calculate_hops_fn=lambda _start, _limit: None,
        extract_packet_position_fn=lambda _packet: None,
        extract_packet_battery_level_fn=lambda _packet: None,
        extract_reply_id_fn=extract_reply_id,
        extract_emoji_codepoint_fn=extract_emoji_codepoint,
        emoji_from_codepoint_fn=emoji_from_codepoint,
    )


def test_parse_tracker_packet_infers_reaction_from_emoji_only_reply_text() -> None:
    parsed = _parse_packet(
        {
            "id": 555,
            "from": 101,
            "to": 4294967295,
            "rxTime": 1234,
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "replyId": 444,
                "text": "😂",
            },
        }
    )

    assert parsed["reply_id"] == 444
    assert parsed["emoji_glyph"] == "😂"
    assert parsed["emoji_codepoint"] == ord("😂")
    assert parsed["is_reaction"] is True


def test_parse_tracker_packet_preserves_keycap_reaction_text_without_codepoint() -> None:
    packet = {
        "id": 556,
        "from": 101,
        "to": 4294967295,
        "rxTime": 1235,
        "decoded": {
            "portnum": "TEXT_MESSAGE_APP",
            "replyId": 445,
            "text": "4️⃣",
        },
    }
    parsed = _parse_packet(packet)

    assert parsed["reply_id"] == 445
    assert parsed["emoji_glyph"] == "4️⃣"
    assert parsed["emoji_codepoint"] is None
    assert parsed["is_reaction"] is True

    chat_entry = build_chat_entry_from_packet(
        packet=packet,
        decoded=packet["decoded"],
        from_id=parsed["from_id"],
        to_id=parsed["to_id"],
        packet_id=parsed["packet_id"],
        hops=parsed["hops"],
        reply_id=parsed["reply_id"],
        emoji_glyph=parsed["emoji_glyph"],
        emoji_codepoint=parsed["emoji_codepoint"],
        is_reaction=parsed["is_reaction"],
        utc_now_fn=lambda: "2026-04-19T21:00:00Z",
        format_epoch_fn=lambda value: str(value),
    )

    assert chat_entry is not None
    assert chat_entry["emoji"] == "4️⃣"
    assert "emoji_codepoint" not in chat_entry
    assert chat_entry["is_reaction"] is True


def test_parse_tracker_packet_keeps_short_ascii_reply_text_as_plain_message() -> None:
    parsed = _parse_packet(
        {
            "id": 557,
            "from": 101,
            "to": 4294967295,
            "rxTime": 1236,
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "replyId": 446,
                "text": "ok",
            },
        }
    )

    assert parsed["reply_id"] == 446
    assert parsed["emoji_glyph"] is None
    assert parsed["emoji_codepoint"] is None
    assert parsed["is_reaction"] is False


def test_build_chat_entry_from_alert_payload_bytes() -> None:
    packet = {
        "id": 558,
        "from": 101,
        "to": 202,
        "rxTime": 1237,
        "decoded": {
            "portnum": "ALERT_APP",
            "payload": b"test alert",
        },
    }
    parsed = _parse_packet(packet)
    chat_entry = build_chat_entry_from_packet(
        packet=packet,
        decoded=packet["decoded"],
        from_id=parsed["from_id"],
        to_id=parsed["to_id"],
        packet_id=parsed["packet_id"],
        hops=parsed["hops"],
        reply_id=parsed["reply_id"],
        emoji_glyph=parsed["emoji_glyph"],
        emoji_codepoint=parsed["emoji_codepoint"],
        is_reaction=parsed["is_reaction"],
        utc_now_fn=lambda: "2026-05-17T20:40:00Z",
        format_epoch_fn=lambda value: str(value),
    )

    assert chat_entry is not None
    assert chat_entry["text"] == "test alert"
    assert chat_entry["portnum"] == "ALERT_APP"
