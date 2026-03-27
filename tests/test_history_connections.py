import json

from meshdash.history_connections import (
    build_connection_insert_values,
    merge_connection_row,
    normalize_connection_event_input,
)


def test_normalize_connection_event_input_applies_defaults():
    event_unix, clean_port, clean_hops = normalize_connection_event_input(
        rx_time=None,
        portnum="TEXT_MESSAGE_APP",
        hops=3,
        now_unix_fn=lambda: 12345,
    )
    assert event_unix == 12345
    assert clean_port == "TEXT_MESSAGE_APP"
    assert clean_hops == 3


def test_normalize_connection_event_input_clamps_future_event_unix_to_now():
    event_unix, clean_port, clean_hops = normalize_connection_event_input(
        rx_time=9_999_999_999,
        portnum="NODEINFO_APP",
        hops=1,
        now_unix_fn=lambda: 400,
    )
    assert event_unix == 400
    assert clean_port == "NODEINFO_APP"
    assert clean_hops == 1


def test_build_connection_insert_values_builds_expected_row_values():
    values = build_connection_insert_values(
        from_id="!a",
        to_id="!b",
        event_unix=100,
        clean_port="TEXT_MESSAGE_APP",
        clean_hops=2,
    )
    assert values[0] == "!a"
    assert values[1] == "!b"
    assert values[2] == 100
    assert values[3] == 100
    assert values[4] == 1
    assert json.loads(values[5]) == ["TEXT_MESSAGE_APP"]
    assert values[6] == 2
    assert values[7] == 2
    assert values[8] == 1


def test_merge_connection_row_merges_ports_timestamps_counts_and_hops():
    row = (90, 95, 4, json.dumps(["NODEINFO_APP"]), 1, 5, 3)
    merged = merge_connection_row(
        row=row,
        event_unix=100,
        clean_port="TEXT_MESSAGE_APP",
        clean_hops=2,
    )

    assert merged["first_seen_unix"] == 90
    assert merged["last_seen_unix"] == 100
    assert merged["seen_count"] == 5
    assert json.loads(merged["portnums_json"]) == ["NODEINFO_APP", "TEXT_MESSAGE_APP"]
    assert merged["last_hops"] == 2
    assert merged["hops_sum"] == 7
    assert merged["hops_count"] == 4
