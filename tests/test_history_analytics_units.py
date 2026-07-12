import sqlite3

from meshdash.history_node_positions import build_position_history_points
from meshdash.history_positions import insert_node_position_if_changed
from meshdash.history_summary_analytics import build_summary_metrics_payload


def test_build_position_history_points_filters_invalid_rows_and_tracks_trail() -> None:
    payload = build_position_history_points(
        [
            (400, 0, 0, None, None),
            (300, 91, 0, None, None),
            (200, "2.5", "-3.5", "100", "7"),
            (100, 1, 2, None, None),
            ("bad", 9, 9, None, None),
        ]
    )

    assert payload["trail_start"] == 100
    assert payload["trail_end"] == 200
    assert payload["positions"] == [
        {
            "time_unix": 100,
            "time": payload["positions"][0]["time"],  # type: ignore[index]
            "lat": 1.0,
            "lon": 2.0,
            "altitude": None,
            "sats_in_view": None,
        },
        {
            "time_unix": 200,
            "time": payload["positions"][1]["time"],  # type: ignore[index]
            "lat": 2.5,
            "lon": -3.5,
            "altitude": 100.0,
            "sats_in_view": 7,
        },
    ]


def test_insert_node_position_if_changed_dedupes_recent_identical_points() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE node_positions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_unix INTEGER NOT NULL,
          node_id TEXT NOT NULL,
          lat REAL NOT NULL,
          lon REAL NOT NULL,
          altitude REAL,
          sats_in_view INTEGER
        )
        """
    )

    insert_node_position_if_changed(conn, node_id="!node", event_unix=90, position_data={"lat": 0, "lon": 0})
    insert_node_position_if_changed(
        conn,
        node_id="!node",
        event_unix=100,
        position_data={"latitude": "1", "longitude": "2", "altitude": "10.5", "satsInView": "6"},
    )
    insert_node_position_if_changed(
        conn,
        node_id="!node",
        event_unix=110,
        position_data={"latitude": "1.000000001", "longitude": "2.000000001", "altitude_m": "11", "satellites": "7"},
    )
    insert_node_position_if_changed(
        conn,
        node_id="!node",
        event_unix=140,
        position_data={"latitude": "1", "longitude": "2", "altitudeM": "12", "sats_in_view": "-1"},
    )

    rows = conn.execute(
        "SELECT created_unix, node_id, lat, lon, altitude, sats_in_view FROM node_positions ORDER BY id"
    ).fetchall()
    assert rows == [
        (100, "!node", 1.0, 2.0, 10.5, 6),
        (140, "!node", 1.0, 2.0, 12.0, None),
    ]


def test_build_summary_metrics_payload_handles_row_shapes_and_packet_series() -> None:
    payload = build_summary_metrics_payload(
        window_hours=0,
        bucket_seconds=0,
        packet_type_rows=[
            (100, "chat", 2),
            [100, "unknown", 3],
            (200, "position", "4"),
            (300, "chat", 0),
            (None, "chat", 1),
            ("bad",),
            object(),
        ],
        rows=[
            (100, 10, 8, 5, 2, 3, 4, 1),
            [200, 11, 9, 6, 3, 4, 2],
            (300, 12, 8, 4, 2, 1),
            (400, 13, 5, 1, 2),
            (500, 1, 1, 1),
            (None, 1, 1, 1, 1),
            object(),
        ],
    )

    assert payload["window_hours"] == 1
    assert payload["bucket_seconds"] == 1
    assert len(payload["points"]) == 4
    assert payload["summary"]["samples"] == 4  # type: ignore[index]
    assert payload["summary"]["latest"]["node_count"] == 13  # type: ignore[index]
    assert payload["summary"]["delta"]["node_count"] == 3  # type: ignore[index]
    assert payload["packet_series"]["series"]["all"] == [  # type: ignore[index]
        {"bucket_unix": 100, "packet_count": 5},
        {"bucket_unix": 200, "packet_count": 4},
    ]
    assert payload["packet_series"]["series"]["other"] == [{"bucket_unix": 100, "packet_count": 3}]  # type: ignore[index]


def test_build_summary_metrics_payload_handles_empty_metrics() -> None:
    payload = build_summary_metrics_payload(
        window_hours=24,
        rows=[],
        packet_type_rows=[],
        bucket_seconds=60,
    )

    assert payload["summary"] == {
        "samples": 0,
        "window_start": None,
        "window_end": None,
        "latest": {},
        "delta": {},
    }
    assert payload["packet_series"]["available"] is True  # type: ignore[index]
    assert payload["packet_series"]["series"]["all"] == []  # type: ignore[index]
