from meshdash.history_read_history import (
    load_node_history_data,
    load_online_activity_data,
    load_summary_metrics_history_data,
)


def test_load_node_history_data_returns_empty_payload_for_blank_node_id():
    payload = load_node_history_data(
        conn="conn",
        node_id="",
        window_hours=6,
        max_points=100,
        fetch_node_history_rows_fn=lambda *_args, **_kwargs: (["m"], ["p"]),
        build_node_history_payload_fn=lambda **kwargs: kwargs,
        now_unix_fn=lambda: 1000,
    )
    assert payload["node_id"] == ""
    assert payload["window_hours"] == 6
    assert payload["metric_rows"] == []
    assert payload["position_rows"] == []


def test_load_node_history_data_fetches_and_builds_payload():
    seen = {}
    payload = load_node_history_data(
        conn="conn",
        node_id=" !abc ",
        window_hours=6,
        max_points=50,
        fetch_node_history_rows_fn=lambda conn, **kwargs: (
            seen.update({"conn": conn, **kwargs}) or ([{"v": 1}], [{"p": 1}])
        ),
        build_node_history_payload_fn=lambda **kwargs: kwargs,
        now_unix_fn=lambda: 1000,
    )
    assert seen["conn"] == "conn"
    assert seen["node_id"] == "!abc"
    assert seen["cutoff"] == 1000 - (6 * 3600)
    assert seen["limit"] == 50
    assert payload["metric_rows"] == [{"v": 1}]
    assert payload["position_rows"] == [{"p": 1}]


def test_load_online_activity_data_fetches_and_builds_payload():
    seen = {}
    payload = load_online_activity_data(
        conn="conn",
        window_hours=12,
        fetch_online_activity_rows_fn=lambda conn, **kwargs: (
            seen.update({"conn": conn, **kwargs}) or ([{"hour": 1}], 7)
        ),
        build_online_activity_payload_fn=lambda **kwargs: kwargs,
        now_unix_fn=lambda: 1000,
        timezone_label_fn=lambda: "UTC",
    )
    assert seen["conn"] == "conn"
    assert seen["cutoff"] == 1000 - (12 * 3600)
    assert payload["window_hours"] == 12
    assert payload["hour_rows"] == [{"hour": 1}]
    assert payload["distinct_nodes"] == 7
    assert payload["timezone_label"] == "UTC"


def test_load_summary_metrics_history_data_fetches_and_builds_payload():
    seen = {}
    payload = load_summary_metrics_history_data(
        conn="conn",
        window_hours=12,
        fetch_summary_metrics_rows_fn=lambda conn, **kwargs: (
            seen.update({"conn": conn, **kwargs}) or [{"bucket_unix": 60}]
        ),
        build_summary_metrics_payload_fn=lambda **kwargs: kwargs,
        now_unix_fn=lambda: 1000,
    )
    assert seen["conn"] == "conn"
    assert seen["cutoff"] == 1000 - (12 * 3600)
    assert seen["limit"] == (12 * 60) + 5
    assert payload["window_hours"] == 12
    assert payload["rows"] == [{"bucket_unix": 60}]
