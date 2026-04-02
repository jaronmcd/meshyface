from meshdash.helpers import (
    calculate_hops,
    disk_space_info,
    emoji_from_codepoint,
    extract_packet_battery_level,
    extract_packet_position,
    extract_emoji_codepoint,
    extract_position_fields,
    extract_reply_id,
    format_epoch,
    is_sensitive_key,
    message_to_dict,
    normalize_single_emoji,
    redact_secrets,
    to_jsonable,
    to_int,
)


def test_to_int_handles_valid_and_invalid_values():
    assert to_int("42") == 42
    assert to_int(7.0) == 7
    assert to_int(None) is None
    assert to_int("not-a-number") is None


def test_format_epoch_returns_utc_string():
    assert format_epoch(1) == "1970-01-01 00:00:01Z"
    assert format_epoch(0) is None
    assert format_epoch("bad") is None


def test_calculate_hops_only_when_non_negative():
    assert calculate_hops(4, 2) == 2
    assert calculate_hops(2, 4) is None
    assert calculate_hops(None, 1) is None


def test_extract_reply_id_accepts_both_key_styles():
    assert extract_reply_id({"replyId": 123}) == 123
    assert extract_reply_id({"reply_id": "456"}) == 456
    assert extract_reply_id({"replyId": 0}) is None
    assert extract_reply_id({"other": 99}) is None


def test_extract_emoji_codepoint_accepts_int_string_and_glyph():
    assert extract_emoji_codepoint({"emoji": 128077}) == 128077
    assert extract_emoji_codepoint({"emoji": "128077"}) == 128077
    assert extract_emoji_codepoint({"emoji": "U+1F44D"}) == 0x1F44D
    assert extract_emoji_codepoint({"emoji": "1F44D"}) == 0x1F44D
    assert extract_emoji_codepoint({"emoji": "👍"}) == ord("👍")
    assert extract_emoji_codepoint({"emoji": ""}) is None
    assert extract_emoji_codepoint({"emoji": 0}) is None


def test_extract_emoji_codepoint_rejects_ascii_text_codepoints():
    assert extract_emoji_codepoint({"emoji": "j"}) is None
    assert extract_emoji_codepoint({"emoji": 106}) is None
    assert extract_emoji_codepoint({"emoji": "106"}) is None


def test_emoji_helpers_round_trip_simple_emoji():
    glyph, codepoint = normalize_single_emoji("👍")
    assert glyph == "👍"
    assert codepoint == ord("👍")
    assert emoji_from_codepoint(codepoint) == "👍"


def test_normalize_single_emoji_accepts_codepoint_string():
    glyph, codepoint = normalize_single_emoji(str(ord("😀")))
    assert glyph == "😀"
    assert codepoint == ord("😀")


def test_normalize_single_emoji_accepts_hex_and_variation_selector():
    glyph, codepoint = normalize_single_emoji("U+1F955")
    assert glyph == "🥕"
    assert codepoint == 0x1F955

    glyph, codepoint = normalize_single_emoji("🥕\ufe0f")
    assert glyph == "🥕"
    assert codepoint == 0x1F955


def test_normalize_single_emoji_rejects_ascii_text():
    glyph, codepoint = normalize_single_emoji("j")
    assert glyph is None
    assert codepoint is None


def test_disk_space_info_has_expected_shape_for_current_dir():
    info = disk_space_info(".")
    assert isinstance(info, dict)
    assert "path" in info
    assert any(key in info for key in ("free_bytes", "error"))


def test_extract_position_fields_accepts_scaled_int_coordinates():
    coords = extract_position_fields({"latitudeI": 449000000, "longitudeI": -930000000})
    assert coords == (44.9, -93.0)
    assert extract_position_fields({"latitude": 0, "longitude": 0}) is None


def test_extract_packet_position_prefers_decoded_position_payload():
    packet = {
        "decoded": {
            "position": {
                "latitude": 44.95,
                "longitude": -93.26,
                "altitude_m": 240,
                "satsInView": 9,
            }
        }
    }
    assert extract_packet_position(packet) == {
        "lat": 44.95,
        "lon": -93.26,
        "altitude": 240.0,
        "sats_in_view": 9,
    }


def test_extract_packet_battery_level_supports_telemetry_metrics():
    packet = {
        "decoded": {
            "telemetry": {
                "deviceMetrics": {
                    "batteryLevel": 87.4,
                }
            }
        }
    }
    assert extract_packet_battery_level(packet) == 87
    assert extract_packet_battery_level({"decoded": {"batteryLevel": 105}}) is None


def test_message_to_dict_returns_none_for_non_protobuf_values():
    assert message_to_dict({"a": 1}) is None
    assert message_to_dict("plain text") is None


def test_to_jsonable_converts_bytes_and_non_jsonable_types():
    payload = {
        "binary": b"\x01\x02",
        "set_data": {1, 2},
        "nested": {"value": 9},
    }
    out = to_jsonable(payload)
    assert out["binary"] == "0102"
    assert sorted(out["set_data"]) == [1, 2]
    assert out["nested"]["value"] == 9


def test_to_jsonable_stops_at_max_depth():
    value = current = {}
    for _ in range(14):
        nxt = {}
        current["next"] = nxt
        current = nxt
    out = to_jsonable(value)
    cursor = out
    for _ in range(13):
        cursor = cursor["next"]
    assert cursor == "<max-depth>"


def test_is_sensitive_key_and_redact_secrets_mask_expected_fields():
    names = {"password", "private_key", "psk"}
    assert is_sensitive_key("password", names) is True
    assert is_sensitive_key("admin_password", names) is True
    assert is_sensitive_key("radio_private_key", names) is True
    assert is_sensitive_key("username", names) is False

    source = {
        "username": "alice",
        "password": "secret",
        "nested": [{"wifi_psk": "topsecret"}, {"ok": True}],
    }
    redacted = redact_secrets(source, names | {"wifi_psk"})
    assert redacted["username"] == "alice"
    assert redacted["password"] == "<redacted>"
    assert redacted["nested"][0]["wifi_psk"] == "<redacted>"
