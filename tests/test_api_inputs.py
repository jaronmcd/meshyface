import pytest

from meshdash.api_inputs import (
    parse_chat_send_body,
    parse_node_history_query,
    parse_online_activity_query,
    validate_content_length,
)


def _to_int(value):
    if value in (None, ""):
        return None
    return int(value)


def test_parse_node_history_query_extracts_overrides():
    node_id, hours, points = parse_node_history_query(
        "node_id=%20!abc123%20&hours=6&points=1440",
        to_int_fn=_to_int,
    )
    assert node_id == "!abc123"
    assert hours == 6
    assert points == 1440


def test_parse_online_activity_query_extracts_hours():
    assert parse_online_activity_query("hours=24", to_int_fn=_to_int) == 24
    assert parse_online_activity_query("", to_int_fn=_to_int) is None


def test_validate_content_length_accepts_valid_and_rejects_invalid():
    assert validate_content_length({"Content-Length": "10"}, to_int_fn=_to_int) == 10

    with pytest.raises(ValueError, match="Invalid request size"):
        validate_content_length({"Content-Length": "0"}, to_int_fn=_to_int)

    with pytest.raises(ValueError, match="Invalid request size"):
        validate_content_length({"Content-Length": "9000"}, to_int_fn=_to_int)


def test_parse_chat_send_body_normalizes_payload():
    payload = parse_chat_send_body(
        b'{"text":"hello","destination":"!abc","channel_index":"2","reply_id":"99","retry_of":"5","emoji":"\\ud83d\\ude00"}',
        to_int_fn=_to_int,
    )
    assert payload["text"] == "hello"
    assert payload["destination"] == "!abc"
    assert payload["channel_index"] == 2
    assert payload["reply_id"] == 99
    assert payload["retry_of"] == 5
    assert payload["emoji"] == "😀"


def test_parse_chat_send_body_handles_invalid_or_non_dict_json():
    invalid = parse_chat_send_body(b"{not-json}", to_int_fn=_to_int)
    assert invalid == {
        "text": None,
        "destination": None,
        "channel_index": None,
        "reply_id": None,
        "retry_of": None,
        "emoji": None,
    }

    array_payload = parse_chat_send_body(b'["not","a","dict"]', to_int_fn=_to_int)
    assert array_payload["text"] is None
    assert array_payload["channel_index"] is None
