from meshdash.history_summary_analytics import build_summary_metrics_payload


class _FiveColumnRow:
    def __iter__(self):
        return iter([1120, -3, -5, -7, -9])


def test_build_summary_metrics_payload_handles_empty_rows_shape():
    payload = build_summary_metrics_payload(
        window_hours=0,
        rows=[object(), ("not-a-bucket", 1, 2, 3, 4)],
    )

    assert payload["window_hours"] == 1
    assert payload["points"] == []
    assert payload["summary"] == {
        "samples": 0,
        "window_start": None,
        "window_end": None,
        "latest": {},
        "delta": {},
    }


def test_build_summary_metrics_payload_supports_7_6_5_column_rows():
    payload = build_summary_metrics_payload(
        window_hours=4,
        rows=[
            (1000, 2, 1, 1, 1, 3, 4),
            [1060, 4, 2, 2, 5, 6],
            _FiveColumnRow(),
        ],
    )

    points = payload["points"]
    assert len(points) == 3

    assert points[0]["bucket_unix"] == 1000
    assert points[0]["node_count"] == 2
    assert points[0]["saved_node_count"] == 1
    assert points[0]["online_node_count"] == 1
    assert points[0]["nodes_with_position"] == 1
    assert points[0]["live_packet_count"] == 3
    assert points[0]["real_edge_count"] == 4

    assert points[1]["bucket_unix"] == 1060
    assert points[1]["node_count"] == 4
    assert points[1]["saved_node_count"] == 2
    assert points[1]["online_node_count"] == 0
    assert points[1]["nodes_with_position"] == 2
    assert points[1]["live_packet_count"] == 5
    assert points[1]["real_edge_count"] == 6

    assert points[2]["bucket_unix"] == 1120
    assert points[2]["node_count"] == 0
    assert points[2]["saved_node_count"] == 0
    assert points[2]["online_node_count"] == 0
    assert points[2]["nodes_with_position"] == 0
    assert points[2]["live_packet_count"] == 0
    assert points[2]["real_edge_count"] == 0

    summary = payload["summary"]
    assert summary["samples"] == 3
    assert summary["window_start"] == points[0]["bucket_time"]
    assert summary["window_end"] == points[2]["bucket_time"]
    assert summary["latest"] == {
        "node_count": 0,
        "saved_node_count": 0,
        "online_node_count": 0,
        "nodes_with_position": 0,
        "live_packet_count": 0,
        "real_edge_count": 0,
    }
    assert summary["delta"] == {
        "node_count": -2,
        "saved_node_count": -1,
        "online_node_count": -1,
        "nodes_with_position": -1,
        "live_packet_count": -3,
        "real_edge_count": -4,
    }
