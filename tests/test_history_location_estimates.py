import math
import sqlite3
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.history_location_estimates import build_location_estimates, load_location_estimates
from meshdash.history_schema import initialize_history_schema


def _make_store(conn: sqlite3.Connection) -> SimpleNamespace:
    return SimpleNamespace(
        _conn=conn,
        _read_conn=None,
        _read_lock=None,
        _lock=threading.Lock(),
    )


def _rssi_for_distance_meters(distance_meters: float) -> float:
    return -97.0 - (10.0 * 2.4 * math.log10(max(1.0, distance_meters) / 1000.0))


def _project(lat: float, lon: float, ref_lat: float, ref_lon: float) -> tuple[float, float]:
    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = max(1.0, math.cos(math.radians(ref_lat)) * meters_per_deg_lat)
    return ((lon - ref_lon) * meters_per_deg_lon, (lat - ref_lat) * meters_per_deg_lat)


def test_build_location_estimates_trilaterates_unknown_node_and_adds_city() -> None:
    target_lat = 45.0
    target_lon = -93.26
    anchors = [
        ("!aaaa0001", 44.98, -93.28),
        ("!aaaa0002", 44.98, -93.24),
        ("!aaaa0003", 45.02, -93.26),
        ("!aaaa0004", 45.01, -93.29),
    ]
    ref_lat = sum(lat for _node_id, lat, _lon in anchors) / len(anchors)
    ref_lon = sum(lon for _node_id, _lat, lon in anchors) / len(anchors)
    target_x, target_y = _project(target_lat, target_lon, ref_lat, ref_lon)
    position_rows = [
        (node_id, 1_700_000_000, lat, lon)
        for node_id, lat, lon in anchors
    ]
    edge_rows = []
    for index, (node_id, lat, lon) in enumerate(anchors, start=1):
        anchor_x, anchor_y = _project(lat, lon, ref_lat, ref_lon)
        distance = math.hypot(target_x - anchor_x, target_y - anchor_y)
        rssi = _rssi_for_distance_meters(distance)
        samples = 12
        edge_rows.append(
            (
                "!bbbb0001",
                node_id,
                1_700_000_000 + index,
                1_700_000_100 + index,
                samples,
                0.0,
                0,
                rssi * samples,
                samples,
                samples,
                samples,
                1,
            )
        )

    with patch(
        "meshdash.history_location_estimates._nearest_city",
        return_value={
            "name": "Minneapolis",
            "state": "Minnesota",
            "country": "United States",
            "distance_km": 3.2,
            "population": 425000,
            "rank": 4,
        },
    ):
        payload = build_location_estimates(
            edge_rows=edge_rows,
            position_rows=position_rows,
            window="72h",
            limit=10,
            now_unix=1_700_000_200,
        )

    assert payload["ok"] is True
    assert payload["estimate_count"] == 1
    estimate = payload["estimates"][0]  # type: ignore[index]
    assert estimate["node_id"] == "!bbbb0001"
    assert estimate["source"] == "rssi_trilateration"
    assert estimate["anchor_count"] >= 3
    assert estimate["signal_samples"] == 48
    assert estimate["confidence"] > 0.6
    assert abs(float(estimate["lat"]) - target_lat) < 0.02
    assert abs(float(estimate["lon"]) - target_lon) < 0.02
    assert estimate["city"] == "Minneapolis, Minnesota"
    assert estimate["city_distance_km"] == 3.2


def test_load_location_estimates_reads_rollups_from_history_store() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    store = _make_store(conn)
    conn.executemany(
        """
        INSERT INTO node_positions(created_unix, node_id, lat, lon)
        VALUES (?, ?, ?, ?)
        """,
        [
            (1_700_000_000, "!aaaa0001", 44.98, -93.28),
            (1_700_000_000, "!aaaa0002", 44.98, -93.24),
            (1_700_000_000, "!aaaa0003", 45.02, -93.26),
        ],
    )
    conn.executemany(
        """
        INSERT INTO link_metrics_1m(
          bucket_unix, from_id, to_id, packet_count,
          snr_sum, snr_count, snr_min, snr_max,
          rssi_sum, rssi_count, rssi_min, rssi_max,
          hops_sum, hops_count, hops_min, hops_max, last_seen_unix
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (1_700_000_100, "!bbbb0001", "!aaaa0001", 8, 0.0, 0, None, None, -720.0, 8, -90.0, -90.0, 8, 8, 1, 1, 1_700_000_120),
            (1_700_000_100, "!bbbb0001", "!aaaa0002", 8, 0.0, 0, None, None, -720.0, 8, -90.0, -90.0, 8, 8, 1, 1, 1_700_000_120),
            (1_700_000_100, "!bbbb0001", "!aaaa0003", 8, 0.0, 0, None, None, -720.0, 8, -90.0, -90.0, 8, 8, 1, 1, 1_700_000_120),
        ],
    )
    conn.commit()

    with patch("meshdash.history_location_estimates.time.time", return_value=1_700_000_200):
        payload = load_location_estimates(store, window="24h", limit=5)

    assert payload["ok"] is True
    assert payload["window"] == "24h"
    assert payload["window_seconds"] == 24 * 60 * 60
    assert payload["limit"] == 5
    assert payload["estimate_count"] >= 0

    with (
        patch("meshdash.history_location_estimates.time.time", return_value=1_700_000_205),
        patch(
            "meshdash.history_location_estimates._fetch_link_metric_rows",
            side_effect=AssertionError("cache miss"),
        ),
    ):
        cached_payload = load_location_estimates(store, window="24h", limit=5)

    assert cached_payload is payload
