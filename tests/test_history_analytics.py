import meshdash.history_node_analytics as history_node_analytics_module
from meshdash.history_analytics import build_node_history_payload, build_online_activity_payload


def test_build_node_history_payload_handles_empty_node_id():
    payload = build_node_history_payload(
        node_id="",
        window_hours=72,
        metric_rows=[],
        position_rows=[],
        packet_rows=[],
    )
    assert payload == {
        "node_id": "",
        "window_hours": 72,
        "points": [],
        "positions": [],
        "name_history": [],
        "packet_timestamps": [],
        "summary": {},
    }


def test_build_node_history_payload_aggregates_rows_and_positions():
    metric_rows_desc = [
        (200, 2, 10.0, 2, 4.0, 6.0, -220.0, 2, -115.0, -105.0, 3, 2, 1, 2, 205),
        (100, 1, 5.0, 1, 5.0, 5.0, -110.0, 1, -110.0, -110.0, 1, 1, 1, 1, 110),
    ]
    position_rows_desc = [
        (210, 44.98, -93.26, 250.0, 8),
        (120, 44.97, -93.25, 245.0, 7),
        (130, 0.0, 0.0, 0.0, 0),
    ]
    packet_rows_desc = [
        (
            220,
            '{"from":"!abcd1234","rx_time_unix":220,"portnum":"NODEINFO_APP"}',
            '{"fromId":"!abcd1234","rxTime":220,"decoded":{"portnum":"NODEINFO_APP","user":{"id":"!abcd1234","shortName":"N1","longName":"Node One"}}}',
        ),
        (
            240,
            '{"from":"!abcd1234","rx_time_unix":240,"portnum":"NODEINFO_APP"}',
            '{"fromId":"!abcd1234","rxTime":240,"decoded":{"portnum":"NODEINFO_APP","user":{"id":"!abcd1234","shortName":"N2","longName":"Node Two"}}}',
        ),
    ]

    payload = build_node_history_payload(
        node_id="!abcd1234",
        window_hours=6,
        metric_rows=metric_rows_desc,
        position_rows=position_rows_desc,
        packet_rows=packet_rows_desc,
    )

    assert payload["node_id"] == "!abcd1234"
    assert payload["window_hours"] == 6
    assert payload["summary"]["total_packets"] == 3
    assert payload["summary"]["points"] == 2
    assert payload["summary"]["trail_points"] == 2
    assert payload["points"][0]["bucket_unix"] == 100
    assert payload["points"][1]["bucket_unix"] == 200
    assert payload["positions"][0]["time_unix"] == 120
    assert payload["positions"][1]["time_unix"] == 210
    assert len(payload["name_history"]) == 2
    assert payload["packet_timestamps"] == [220, 240]
    assert payload["name_history"][0]["short_name"] == "N1"
    assert payload["name_history"][1]["short_name"] == "N2"


def test_build_online_activity_payload_builds_hourly_profile_and_summary():
    rows = [
        (1710000000, 3),
        (1710003600, 5),
    ]
    payload = build_online_activity_payload(
        window_hours=12,
        hour_rows=rows,
        distinct_nodes=9,
        timezone_label="Test/TZ",
    )

    assert payload["window_hours"] == 12
    assert payload["timezone_label"] == "Test/TZ"
    assert payload["summary"]["sample_hours"] == 2
    assert payload["summary"]["distinct_nodes"] == 9
    assert payload["summary"]["max_online_nodes"] == 5
    assert payload["summary"]["avg_online_nodes"] == 4.0
    assert len(payload["hourly_profile"]) == 24
    assert payload["points"][0]["online_nodes"] == 3
    assert payload["points"][1]["online_nodes"] == 5
    for point in payload["points"]:
        assert point["hour_label"] == f"{point['hour_local']:02d}:00"


def test_build_node_history_payload_clamps_future_packet_timestamps(monkeypatch):
    monkeypatch.setattr(history_node_analytics_module.time, "time", lambda: 1000.0)
    payload = build_node_history_payload(
        node_id="!abcd1234",
        window_hours=6,
        metric_rows=[],
        position_rows=[],
        packet_rows=[
            (
                900,
                '{"from":"!abcd1234","rx_time_unix":5000,"portnum":"NODEINFO_APP"}',
                '{"fromId":"!abcd1234","rxTime":5000,"decoded":{"portnum":"NODEINFO_APP"}}',
            ),
        ],
    )
    assert payload["packet_timestamps"] == [900]
