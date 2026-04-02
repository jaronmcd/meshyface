from meshdash.tracker_entries import (
    build_chat_entry_from_packet,
    build_packet_summary,
)


def test_build_packet_summary_includes_core_and_optional_fields():
    packet = {
        "from": 123,
        "to": 456,
        "rxTime": 100,
        "rxRssi": -101,
        "rxSnr": 4.5,
        "hopStart": 5,
        "hopLimit": 3,
        "wantAck": True,
        "priority": "BACKGROUND",
        "channel": 0,
    }
    decoded = {"portnum": "TEXT_MESSAGE_APP", "text": "hello"}
    summary = build_packet_summary(
        packet=packet,
        decoded=decoded,
        from_id="!a",
        to_id="!b",
        packet_id=999,
        rx_time=100,
        hops=2,
        reply_id=888,
        emoji_glyph="😀",
        emoji_codepoint=128512,
        is_reaction=True,
        packet_position={"lat": 44.95, "lon": -93.1},
        packet_battery=85,
        utc_now_fn=lambda: "now",
        format_epoch_fn=lambda value: f"ts:{value}",
        to_int_fn=int,
    )
    assert summary["captured_at"] == "now"
    assert summary["packet_id"] == 999
    assert summary["from"] == "!a"
    assert summary["to"] == "!b"
    assert summary["from_num"] == 123
    assert summary["to_num"] == 456
    assert summary["portnum"] == "TEXT_MESSAGE_APP"
    assert summary["rx_time"] == "ts:100"
    assert summary["hops"] == 2
    assert summary["reply_id"] == 888
    assert summary["emoji"] == "😀"
    assert summary["emoji_codepoint"] == 128512
    assert summary["is_reaction"] is True
    assert summary["position"] == {"lat": 44.95, "lon": -93.1}
    assert summary["battery_level"] == 85


def test_build_chat_entry_from_packet_returns_none_without_text_or_reaction():
    packet = {"rxTime": 100}
    entry = build_chat_entry_from_packet(
        packet=packet,
        decoded={"portnum": "TEXT_MESSAGE_APP"},
        from_id="!a",
        to_id="!b",
        packet_id=1,
        hops=1,
        reply_id=None,
        emoji_glyph=None,
        emoji_codepoint=None,
        is_reaction=False,
        utc_now_fn=lambda: "now",
        format_epoch_fn=lambda value: f"ts:{value}",
    )
    assert entry is None


def test_build_chat_entry_from_packet_builds_reaction_row():
    packet = {
        "rxTime": 100,
        "channel": 1,
        "hopStart": 5,
        "hopLimit": 3,
        "rxSnr": 11.0,
        "rxRssi": -25,
    }
    entry = build_chat_entry_from_packet(
        packet=packet,
        decoded={"portnum": "TEXT_MESSAGE_APP", "text": ""},
        from_id="!a",
        to_id="!b",
        packet_id=42,
        hops=2,
        reply_id=41,
        emoji_glyph="👍",
        emoji_codepoint=128077,
        is_reaction=True,
        utc_now_fn=lambda: "now",
        format_epoch_fn=lambda value: f"ts:{value}",
    )
    assert entry is not None
    assert entry["captured_at"] == "now"
    assert entry["message_id"] == 42
    assert entry["reply_id"] == 41
    assert entry["emoji"] == "👍"
    assert entry["emoji_codepoint"] == 128077
    assert entry["is_reaction"] is True
    assert entry["rx_snr"] == 11.0
    assert entry["rx_rssi"] == -25
