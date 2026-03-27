from meshdash.history_packet_events import (
    build_packet_event_insert_values,
    normalize_packet_event_summary,
)


def test_normalize_packet_event_summary_maps_expected_fields():
    summary = {
        "from": " !abc ",
        "to": "^all",
        "portnum": "TEXT_MESSAGE_APP",
        "rx_snr": "-7.5",
        "rx_rssi": "-121",
        "hops": "3",
        "hop_start": "5",
        "hop_limit": "2",
        "channel": 0,
        "want_ack": True,
        "priority": "BACKGROUND",
        "battery_level": "91",
        "position": {"latitude": 44.95, "longitude": -93.1},
    }
    normalized = normalize_packet_event_summary(summary, now_unix_fn=lambda: 500)

    assert normalized["event_unix"] == 500
    assert normalized["from_id"] == "!abc"
    assert normalized["to_id"] is None
    assert normalized["portnum"] == "TEXT_MESSAGE_APP"
    assert normalized["rx_snr"] == -7.5
    assert normalized["rx_rssi"] == -121.0
    assert normalized["hops"] == 3
    assert normalized["hop_start"] == 5
    assert normalized["hop_limit"] == 2
    assert normalized["channel"] == "0"
    assert normalized["want_ack"] == 1
    assert normalized["priority"] == "BACKGROUND"
    assert normalized["battery_level"] == 91
    assert normalized["position_data"] == {"latitude": 44.95, "longitude": -93.1}
    assert normalized["summary_json"] == (
        '{"from":" !abc ","to":"^all","portnum":"TEXT_MESSAGE_APP","rx_snr":"-7.5",'
        '"rx_rssi":"-121","hops":"3","hop_start":"5","hop_limit":"2","channel":0,'
        '"want_ack":true,"priority":"BACKGROUND","battery_level":"91",'
        '"position":{"latitude":44.95,"longitude":-93.1}}'
    )


def test_normalize_packet_event_summary_clamps_future_event_unix_to_now():
    normalized = normalize_packet_event_summary(
        {"from": "!abc", "rx_time_unix": 9_999_999_999},
        now_unix_fn=lambda: 500,
    )
    assert normalized["event_unix"] == 500


def test_build_packet_event_insert_values_matches_table_column_order():
    normalized = {
        "event_unix": 100,
        "from_id": "!a",
        "to_id": "^all",
        "portnum": "NODEINFO_APP",
        "rx_snr": -5.0,
        "rx_rssi": -100.0,
        "hops": 2,
        "hop_start": 4,
        "hop_limit": 2,
        "channel": "1",
        "want_ack": 0,
        "priority": "BACKGROUND",
        "summary_json": "{}",
    }
    assert build_packet_event_insert_values(normalized) == (
        100,
        "!a",
        "^all",
        "NODEINFO_APP",
        -5.0,
        -100.0,
        2,
        4,
        2,
        "1",
        0,
        "BACKGROUND",
        "{}",
    )
