import meshdash.helpers_json as helpers_json
from meshdash.chat_delivery_extract import extract_routing_delivery_update
from meshdash.chat_delivery_timeout import expire_pending_deliveries
from meshdash.chat_send_response import build_chat_send_response, delivery_state_for_send
from meshdash.helpers_json import message_to_dict, safe_json_loads, to_jsonable
from meshdash.helpers_packet_battery import extract_packet_battery_level
from meshdash.helpers_packet_position import extract_packet_position, extract_position_fields


def test_extract_routing_delivery_update_filters_and_normalizes_states() -> None:
    assert extract_routing_delivery_update(None) is None
    assert extract_routing_delivery_update({"portnum": "TEXT_MESSAGE_APP"}) is None
    assert extract_routing_delivery_update({"portnum": "ROUTING_APP", "routing": "bad"}) is None
    assert extract_routing_delivery_update({"portnum": "ROUTING_APP", "routing": {}}) is None
    assert extract_routing_delivery_update(
        {"portnum": "ROUTING_APP", "routing": {"requestId": "42", "errorReason": "NONE"}}
    ) == {"request_id": 42, "state": "acked", "error": None}
    assert extract_routing_delivery_update(
        {"portnum": "ROUTING_APP", "routing": {"error_reason": "NO_ROUTE"}, "request_id": "43"}
    ) == {"request_id": 43, "state": "nak", "error": "NO_ROUTE"}


def test_expire_pending_deliveries_skips_irrelevant_rows_and_marks_timeouts() -> None:
    entries: list[object] = [
        "not a row",
        {"local_echo": False, "ack_requested": True, "delivery_state": "pending"},
        {"local_echo": True, "ack_requested": False, "delivery_state": "pending"},
        {"local_echo": True, "ack_requested": True, "delivery_state": "sent"},
        {"local_echo": True, "ack_requested": True, "delivery_state": "pending", "delivery_updated_unix": 99},
        {"local_echo": True, "ack_requested": True, "delivery_state": "pending"},
        {"local_echo": True, "ack_requested": True, "delivery_state": "pending", "captured_at": "old"},
    ]
    expired: list[dict[str, object]] = []

    expire_pending_deliveries(
        entries,
        5,
        parse_utc_text_to_unix_fn=lambda value: 80 if value == "old" else None,
        now_unix_fn=lambda: 100,
        now_text_fn=lambda: "NOW",
        format_epoch_fn=lambda value: f"T{value}",
        on_expire_fn=expired.append,
    )

    recent = entries[4]
    missing_since = entries[5]
    old = entries[6]
    assert isinstance(recent, dict)
    assert isinstance(missing_since, dict)
    assert isinstance(old, dict)
    assert recent["delivery_state"] == "pending"
    assert missing_since["delivery_state"] == "pending"
    assert missing_since["delivery_updated_unix"] == 100
    assert missing_since["delivery_updated_at"] == "NOW"
    assert old["delivery_state"] == "timeout"
    assert old["delivery_updated_unix"] == 85
    assert old["delivery_updated_at"] == "T85"
    assert expired == [old]


def test_expire_pending_deliveries_uses_now_text_when_formatting_fails() -> None:
    row = {"local_echo": True, "ack_requested": True, "delivery_state": "pending", "rx_time": "old"}

    expire_pending_deliveries(
        [row],
        0,
        parse_utc_text_to_unix_fn=lambda value: 10 if value == "old" else None,
        now_unix_fn=lambda: 20,
        now_text_fn=lambda: "NOW",
        format_epoch_fn=lambda value: None,
    )

    assert row["delivery_state"] == "timeout"
    assert row["delivery_updated_unix"] == 11
    assert row["delivery_updated_at"] == "NOW"


def test_chat_send_response_builds_delivery_and_reaction_payloads() -> None:
    assert delivery_state_for_send(ack_requested=False, sent_packet_id=None) == "sent"
    assert delivery_state_for_send(ack_requested=True, sent_packet_id=7) == "pending"
    assert delivery_state_for_send(ack_requested=True, sent_packet_id=0) == "error"

    response = build_chat_send_response(
        now_text_fn=lambda: "now",
        local_node_id="!local",
        destination="!dest",
        channel_index=2,
        message_id=10,
        reply_id=9,
        retry_of=8,
        ack_requested=True,
        delivery_state="pending",
        text="hello",
        is_reaction=False,
        emoji=None,
        emoji_codepoint=None,
    )
    reaction = build_chat_send_response(
        now_text_fn=lambda: "now",
        local_node_id="!local",
        destination="!dest",
        channel_index=2,
        message_id=11,
        reply_id=None,
        retry_of=None,
        ack_requested=False,
        delivery_state="sent",
        text="ignored",
        is_reaction=True,
        emoji="thumbs-up",
        emoji_codepoint=42,
    )

    assert response["retry_of"] == 8
    assert response["text"] == "hello"
    assert reaction["text"] == ""
    assert reaction["reaction"] == "thumbs-up"
    assert reaction["reaction_codepoint"] == 42


def test_json_helpers_load_convert_and_delegate_protobuf_like_messages(monkeypatch) -> None:
    class FakeMessage:
        pass

    monkeypatch.setattr(helpers_json, "_protobuf_message_type", FakeMessage)
    monkeypatch.setattr(
        helpers_json,
        "_protobuf_message_to_dict",
        lambda value, *, preserving_proto_field_name: {"payload": b"\x0f", "preserve": preserving_proto_field_name},
    )

    assert safe_json_loads('{"ok": true}', {}) == {"ok": True}
    assert safe_json_loads("{bad", {"fallback": True}) == {"fallback": True}
    assert safe_json_loads(None, []) == []  # type: ignore[arg-type]
    assert message_to_dict(FakeMessage()) == {"payload": b"\x0f", "preserve": True}
    assert to_jsonable(FakeMessage()) == {"payload": "0f", "preserve": True}
    assert to_jsonable({1: (b"\x01", {"items": {2, 3}})})["1"][0] == "01"  # type: ignore[index]
    assert to_jsonable("x", depth=13) == "<max-depth>"
    assert to_jsonable(object()).startswith("<object object at ")


def test_packet_battery_extraction_uses_nested_candidates_and_valid_ranges() -> None:
    assert extract_packet_battery_level("not a packet") is None  # type: ignore[arg-type]
    assert extract_packet_battery_level({"decoded": {"telemetry": {"deviceMetrics": {"batteryLevel": "55.4"}}}}) == 55
    assert extract_packet_battery_level({"decoded": {"metrics": {"battery_percent": "101"}, "battery": "33"}}) == 33
    assert extract_packet_battery_level({"telemetry": {"device_metrics": {"batteryPercent": 12.2}}}) == 12
    assert extract_packet_battery_level({"device_metrics": {"battery_level": "bad"}, "battery": -1}) is None


def test_packet_position_extraction_validates_coordinates_and_metadata() -> None:
    assert extract_position_fields("bad") is None
    assert extract_position_fields({"latitude": 1, "longitude": 2}) == (1.0, 2.0)
    assert extract_position_fields({"lat": "3.5", "lon": "-4.5"}) == (3.5, -4.5)
    assert extract_position_fields({"latitudeI": 123456789, "longitudeI": -987654321}) == (12.3456789, -98.7654321)
    assert extract_position_fields({"latitude_i": 10000000, "longitude_i": 20000000}) == (1.0, 2.0)
    assert extract_position_fields({"lat": 0, "lon": 0}) is None
    assert extract_position_fields({"lat": 91, "lon": 0}) is None
    assert extract_position_fields({"lat": 1}) is None
    assert extract_packet_position({"decoded": {"position": {"lat": 0, "lon": 0}}}) is None

    decoded_position = extract_packet_position(
        {"decoded": {"position": {"lat": 3, "lon": 4, "altitude": "100.5", "satsInView": "7"}}}
    )
    root_position = extract_packet_position(
        {"gps": {"latitude_i": 50000000, "longitude_i": 60000000, "altitude_m": "20", "satellites": "4"}}
    )
    decoded_location = extract_packet_position(
        {"decoded": {"location": {"lat": 7, "lon": 8, "altitudeM": "30", "sats_in_view": "-1"}}}
    )

    assert extract_packet_position("bad") is None  # type: ignore[arg-type]
    assert decoded_position == {"lat": 3.0, "lon": 4.0, "altitude": 100.5, "sats_in_view": 7}
    assert root_position == {"lat": 5.0, "lon": 6.0, "altitude": 20.0, "sats_in_view": 4}
    assert decoded_location == {"lat": 7.0, "lon": 8.0, "altitude": 30.0}
