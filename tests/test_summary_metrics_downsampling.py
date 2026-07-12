import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.api_history_summary import build_summary_metrics_response
from meshdash.api_input_history import parse_history_window_request
from meshdash.helpers import to_int
from meshdash.history_views import empty_summary_metrics


def _summary_payload(sample_count: int = 200) -> dict[str, object]:
    first_bucket = 1_700_000_000
    points = [
        {
            "bucket_unix": first_bucket + (idx * 15),
            "bucket_time": str(first_bucket + (idx * 15)),
            "node_count": idx,
            "saved_node_count": idx,
            "online_node_count": idx,
            "nodes_with_position": idx,
            "live_packet_count": idx,
            "edge_count": idx,
            "real_edge_count": idx,
        }
        for idx in range(sample_count)
    ]
    packet_rows = [
        {
            "bucket_unix": point["bucket_unix"],
            "packet_count": 1,
        }
        for point in points
    ]
    return {
        "window_hours": 1,
        "bucket_seconds": 15,
        "points": points,
        "packet_series": {
            "available": True,
            "order": ["all", "chat"],
            "series": {
                "all": packet_rows,
                "chat": packet_rows,
            },
        },
        "summary": {
            "samples": sample_count,
            "latest": {"node_count": sample_count - 1},
            "delta": {"node_count": sample_count - 1},
        },
    }


def _build_response(query: str, payload: dict[str, object]) -> dict:
    return build_summary_metrics_response(
        query=query,
        summary_metrics_fn=lambda _hours_override: payload,
        default_node_history_hours=24,
        to_int_fn=to_int,
        parse_history_window_request_fn=parse_history_window_request,
        empty_summary_metrics_fn=empty_summary_metrics,
    )


def test_summary_metrics_response_downsamples_points_and_packet_series() -> None:
    response = _build_response("hours=1&points=64", _summary_payload())

    assert response["bucket_seconds"] == 60
    assert len(response["points"]) == 50
    assert response["resolution"] == {
        "downsampled": True,
        "max_points": 64,
        "raw_bucket_seconds": 15,
        "bucket_seconds": 60,
        "raw_points": 200,
        "points": 50,
    }
    assert response["summary"]["latest"]["node_count"] == 199

    packet_rows = response["packet_series"]["series"]["all"]
    assert len(packet_rows) == 50
    assert packet_rows[0]["packet_count"] == 4
    assert packet_rows[-1]["packet_count"] == 4


def test_summary_metrics_response_points_all_keeps_raw_resolution() -> None:
    response = _build_response("hours=1&points=all", _summary_payload())

    assert response["bucket_seconds"] == 15
    assert len(response["points"]) == 200
    assert "resolution" not in response
    assert len(response["packet_series"]["series"]["all"]) == 200


def test_summary_metrics_response_sparse_history_respects_point_limit() -> None:
    payload = _summary_payload()
    for idx, point in enumerate(payload["points"]):
        point["bucket_unix"] = 1_700_000_000 + (idx * 30)
    for idx, row in enumerate(payload["packet_series"]["series"]["all"]):
        row["bucket_unix"] = 1_700_000_000 + (idx * 30)
    for idx, row in enumerate(payload["packet_series"]["series"]["chat"]):
        row["bucket_unix"] = 1_700_000_000 + (idx * 30)

    response = _build_response("hours=1&points=64", payload)

    assert len(response["points"]) <= 64
    assert len(response["packet_series"]["series"]["all"]) <= 64


def test_summary_metrics_response_can_skip_packet_series() -> None:
    calls: list[tuple[object, bool]] = []

    def summary_metrics_fn(hours_override, *, include_packet_series: bool = True):
        calls.append((hours_override, include_packet_series))
        return _summary_payload()

    response = build_summary_metrics_response(
        query="hours=1&packet_series=0",
        summary_metrics_fn=summary_metrics_fn,
        default_node_history_hours=24,
        to_int_fn=to_int,
        parse_history_window_request_fn=parse_history_window_request,
        empty_summary_metrics_fn=empty_summary_metrics,
    )

    assert calls == [(1, False)]
    assert response["packet_series"] == {
        "available": False,
        "order": [],
        "series": {},
    }
