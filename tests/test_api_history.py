from meshdash.api_inputs import NodeHistoryQuery, OnlineActivityQuery
from meshdash.api_history import (
    build_node_history_response,
    build_online_activity_response,
    build_summary_metrics_response,
)


def test_build_node_history_response_uses_loader_when_available():
    response = build_node_history_response(
        query="node_id=!abcd1234&hours=24&points=120",
        node_history_fn=lambda node_id, hours, points: {
            "node_id": node_id,
            "window_hours": hours,
            "max_points": points,
        },
        to_int_fn=lambda value: int(value) if value else None,
        parse_node_history_request_fn=lambda query, **kwargs: NodeHistoryQuery(
            node_id="!abcd1234",
            hours_override=24,
            points_override=120,
        ),
        empty_node_history_fn=lambda node_id: {"node_id": node_id, "points": []},
    )

    assert response == {
        "node_id": "!abcd1234",
        "window_hours": 24,
        "max_points": 120,
    }


def test_build_node_history_response_falls_back_to_empty_shape():
    response = build_node_history_response(
        query="node_id=!abcd1234",
        node_history_fn=None,
        to_int_fn=lambda value: int(value) if value else None,
        parse_node_history_request_fn=lambda query, **kwargs: NodeHistoryQuery(
            node_id="!abcd1234",
            hours_override=None,
            points_override=None,
        ),
        empty_node_history_fn=lambda node_id: {"node_id": node_id, "points": []},
    )

    assert response == {"node_id": "!abcd1234", "points": []}


def test_build_online_activity_response_uses_loader_when_available():
    response = build_online_activity_response(
        query="hours=48",
        online_activity_fn=lambda hours: {"window_hours": hours, "hourly_profile": []},
        default_node_history_hours=72,
        to_int_fn=lambda value: int(value) if value else None,
        parse_online_activity_request_fn=lambda query, **kwargs: OnlineActivityQuery(hours_override=48),
        empty_online_activity_fn=lambda hours: {"window_hours": hours, "hourly_profile": []},
    )

    assert response == {"window_hours": 48, "hourly_profile": []}


def test_build_online_activity_response_falls_back_to_default_window():
    response = build_online_activity_response(
        query="hours=0",
        online_activity_fn=None,
        default_node_history_hours=72,
        to_int_fn=lambda value: int(value) if value else None,
        parse_online_activity_request_fn=lambda query, **kwargs: OnlineActivityQuery(hours_override=0),
        empty_online_activity_fn=lambda hours: {"window_hours": hours, "hourly_profile": []},
    )

    assert response == {"window_hours": 72, "hourly_profile": []}


def test_build_summary_metrics_response_uses_loader_when_available():
    response = build_summary_metrics_response(
        query="hours=24",
        summary_metrics_fn=lambda hours: {"window_hours": hours, "points": [1]},
        default_node_history_hours=72,
        to_int_fn=lambda value: int(value) if value else None,
        parse_online_activity_request_fn=lambda query, **kwargs: OnlineActivityQuery(hours_override=24),
        empty_summary_metrics_fn=lambda hours: {"window_hours": hours, "points": []},
    )
    assert response == {"window_hours": 24, "points": [1]}


def test_build_summary_metrics_response_falls_back_to_default_window():
    response = build_summary_metrics_response(
        query="hours=0",
        summary_metrics_fn=None,
        default_node_history_hours=72,
        to_int_fn=lambda value: int(value) if value else None,
        parse_online_activity_request_fn=lambda query, **kwargs: OnlineActivityQuery(hours_override=0),
        empty_summary_metrics_fn=lambda hours: {"window_hours": hours, "points": []},
    )
    assert response == {"window_hours": 72, "points": []}
