import json

from meshdash.history_readers import (
    decode_connections_rows,
    decode_recent_chat_rows,
    decode_recent_packets_rows,
)


def test_decode_recent_packets_rows_filters_invalid_summary_and_reverses_order():
    rows = [
        (json.dumps({"id": 3}), json.dumps({"p": 3})),
        (json.dumps(["bad-summary"]), json.dumps({"p": 2})),
        (json.dumps({"id": 1}), json.dumps({"p": 1})),
    ]
    out = decode_recent_packets_rows(rows)
    assert out == [
        {"summary": {"id": 1}, "packet": {"p": 1}},
        {"summary": {"id": 3}, "packet": {"p": 3}},
    ]


def test_decode_recent_chat_rows_filters_invalid_entries_and_reverses_order():
    rows = [
        (json.dumps({"text": "latest"}),),
        (json.dumps({"text": "MF_FILE_V1|A|mtest123|0|4|AA=="}),),
        (json.dumps(["bad"]),),
        (json.dumps({"text": "oldest"}),),
    ]
    out = decode_recent_chat_rows(rows)
    assert out == [{"text": "oldest"}, {"text": "latest"}]


def test_decode_connections_rows_coerces_numeric_and_port_fields():
    rows = [
        (
            "!a",
            "!b",
            100,
            200,
            3,
            json.dumps(["TEXT_MESSAGE_APP", None, "POSITION_APP"]),
            2,
            7,
            3,
        )
    ]
    out = decode_connections_rows(rows)
    assert out == [
        {
            "from": "!a",
            "to": "!b",
            "count": 3,
            "first_rx_time": 100,
            "last_rx_time": 200,
            "portnums": ["TEXT_MESSAGE_APP", "POSITION_APP"],
            "last_hops": 2,
            "hops_sum": 7,
            "hops_count": 3,
        }
    ]
