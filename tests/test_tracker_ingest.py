from meshdash.tracker_ingest import parse_tracker_packet


def test_parse_tracker_packet_uses_explicit_ids_and_computes_reaction_fields():
    packet = {
        "id": "100",
        "from": 1,
        "to": 2,
        "fromId": "!from",
        "toId": "!to",
        "rxTime": "123",
        "hopStart": 5,
        "hopLimit": 3,
        "decoded": {
            "portnum": "TEXT_MESSAGE_APP",
            "replyId": 99,
            "emoji": 128077,
        },
    }

    parsed = parse_tracker_packet(
        packet,
        interface=object(),
        get_node_id_from_num_fn=lambda _iface, _num: None,
        to_int_fn=lambda v: int(v) if v is not None else None,
        calculate_hops_fn=lambda start, limit: int(start) - int(limit),
        extract_packet_position_fn=lambda _packet: {"lat": 44.95, "lon": -93.1},
        extract_packet_battery_level_fn=lambda _packet: 88,
        extract_reply_id_fn=lambda decoded: decoded.get("replyId"),
        extract_emoji_codepoint_fn=lambda decoded: decoded.get("emoji"),
        emoji_from_codepoint_fn=lambda value: chr(int(value)),
    )

    assert parsed["from_id"] == "!from"
    assert parsed["to_id"] == "!to"
    assert parsed["rx_time"] == 123
    assert parsed["hops"] == 2
    assert parsed["portnum"] == "TEXT_MESSAGE_APP"
    assert parsed["packet_id"] == 100
    assert parsed["packet_position"] == {"lat": 44.95, "lon": -93.1}
    assert parsed["packet_battery"] == 88
    assert parsed["reply_id"] == 99
    assert parsed["emoji_codepoint"] == 128077
    assert parsed["emoji_glyph"] == "👍"
    assert parsed["is_reaction"] is True


def test_parse_tracker_packet_falls_back_to_node_lookup_and_handles_non_dict_decoded():
    packet = {
        "id": None,
        "from": 42,
        "to": 43,
        "rxTime": None,
        "hopStart": None,
        "hopLimit": None,
        "decoded": "not-a-dict",
    }

    parsed = parse_tracker_packet(
        packet,
        interface=object(),
        get_node_id_from_num_fn=lambda _iface, num: f"!{num:08x}",
        to_int_fn=lambda v: int(v) if v is not None else None,
        calculate_hops_fn=lambda _start, _limit: None,
        extract_packet_position_fn=lambda _packet: None,
        extract_packet_battery_level_fn=lambda _packet: None,
        extract_reply_id_fn=lambda _decoded: None,
        extract_emoji_codepoint_fn=lambda _decoded: None,
        emoji_from_codepoint_fn=lambda _value: None,
    )

    assert parsed["from_id"] == "!0000002a"
    assert parsed["to_id"] == "!0000002b"
    assert parsed["decoded"] == "not-a-dict"
    assert parsed["portnum"] is None
    assert parsed["packet_id"] is None
    assert parsed["packet_position"] is None
    assert parsed["packet_battery"] is None
    assert parsed["reply_id"] is None
    assert parsed["emoji_codepoint"] is None
    assert parsed["emoji_glyph"] is None
    assert parsed["is_reaction"] is False


def test_parse_tracker_packet_normalizes_broadcast_alias_to_all():
    packet = {
        "id": "101",
        "fromId": "!ABCDEF12",
        "toId": "!FFFFFFFF",
        "rxTime": "123",
        "decoded": {
            "portnum": "TEXT_MESSAGE_APP",
            "text": "hello",
        },
    }

    parsed = parse_tracker_packet(
        packet,
        interface=object(),
        get_node_id_from_num_fn=lambda _iface, _num: None,
        to_int_fn=lambda v: int(v) if v is not None else None,
        calculate_hops_fn=lambda _start, _limit: None,
        extract_packet_position_fn=lambda _packet: None,
        extract_packet_battery_level_fn=lambda _packet: None,
        extract_reply_id_fn=lambda _decoded: None,
        extract_emoji_codepoint_fn=lambda _decoded: None,
        emoji_from_codepoint_fn=lambda _value: None,
    )

    assert parsed["from_id"] == "!abcdef12"
    assert parsed["to_id"] == "^all"


def test_parse_tracker_packet_normalizes_plain_hex_node_ids_without_bang():
    packet = {
        "id": "102",
        "fromId": "A1B2C3D4",
        "toId": "0F0E0D0C",
        "decoded": {"portnum": "TEXT_MESSAGE_APP"},
    }

    parsed = parse_tracker_packet(
        packet,
        interface=object(),
        get_node_id_from_num_fn=lambda _iface, _num: None,
        to_int_fn=lambda v: int(v) if v is not None else None,
        calculate_hops_fn=lambda _start, _limit: None,
        extract_packet_position_fn=lambda _packet: None,
        extract_packet_battery_level_fn=lambda _packet: None,
        extract_reply_id_fn=lambda _decoded: None,
        extract_emoji_codepoint_fn=lambda _decoded: None,
        emoji_from_codepoint_fn=lambda _value: None,
    )

    assert parsed["from_id"] == "!a1b2c3d4"
    assert parsed["to_id"] == "!0f0e0d0c"


def test_parse_tracker_packet_preserves_empty_lookup_node_id():
    packet = {
        "id": "103",
        "from": 1,
        "to": 2,
        "decoded": {"portnum": "TEXT_MESSAGE_APP"},
    }

    parsed = parse_tracker_packet(
        packet,
        interface=object(),
        get_node_id_from_num_fn=lambda _iface, _num: "",
        to_int_fn=lambda v: int(v) if v is not None else None,
        calculate_hops_fn=lambda _start, _limit: None,
        extract_packet_position_fn=lambda _packet: None,
        extract_packet_battery_level_fn=lambda _packet: None,
        extract_reply_id_fn=lambda _decoded: None,
        extract_emoji_codepoint_fn=lambda _decoded: None,
        emoji_from_codepoint_fn=lambda _value: None,
    )

    assert parsed["from_id"] == ""
    assert parsed["to_id"] == ""
