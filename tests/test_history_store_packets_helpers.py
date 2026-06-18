import json
import sqlite3
import threading
from types import SimpleNamespace

from meshdash.history_schema import initialize_history_schema
from meshdash.history_store_packets import (
    _build_environment_points,
    _build_environment_points_from_rollups,
    _canonical_node_id,
    _derive_environment_meta_from_points,
    _local_telemetry_sample_unix,
    _merge_environment_meta_maps,
    _search_excerpt,
    _should_skip_local_noise_packet,
    _should_skip_local_telemetry_duplicate,
    search_packets,
)


def test_packet_history_helpers_normalize_node_ids_and_excerpt_matches() -> None:
    assert _canonical_node_id(None) == ""
    assert _canonical_node_id("^all") == "^all"
    assert _canonical_node_id("FFFFFFFF") == "^all"
    assert _canonical_node_id("!ABCDEF12") == "!abcdef12"
    assert _canonical_node_id("abcdef12") == "!abcdef12"
    assert _canonical_node_id(0x1234) == "!00001234"
    assert _canonical_node_id("4660") == "!00001234"
    assert _canonical_node_id("node-name") == "node-name"

    assert _search_excerpt("", "needle") == ""
    assert _search_excerpt("Alpha beta gamma", "") == ""
    assert _search_excerpt("Alpha beta gamma", "missing") == ""
    excerpt = _search_excerpt("prefix " * 20 + "needle" + " suffix" * 20, "needle", max_chars=60)
    assert excerpt.startswith("...")
    assert "needle" in excerpt
    assert excerpt.endswith("...")
    assert len(excerpt) <= 60


def test_packet_history_helpers_filter_local_noise_and_telemetry_duplicates() -> None:
    admin_packet = {
        "summary": {
            "from": "!01020304",
            "portnum": "ADMIN_APP",
        }
    }
    remote_admin_packet = {
        "summary": {
            "from": "!05060708",
            "portnum": "ADMIN_APP",
        }
    }
    telemetry_packet = {
        "summary": {
            "from": "!01020304",
            "portnum": "TELEMETRY_APP",
            "rx_time_unix": 120,
        },
        "packet": {
            "decoded": {
                "telemetry": {
                    "time": 150,
                    "deviceMetrics": {
                        "batteryLevel": 87,
                    },
                }
            }
        },
    }

    assert _should_skip_local_noise_packet(admin_packet, local_node_id="!01020304") is True
    assert _should_skip_local_noise_packet(remote_admin_packet, local_node_id="!01020304") is False
    assert _should_skip_local_noise_packet({"summary": "bad"}, local_node_id="!01020304") is False
    assert _local_telemetry_sample_unix(telemetry_packet, local_node_id="!01020304") == 150
    assert _should_skip_local_telemetry_duplicate(
        telemetry_packet,
        local_node_id="!01020304",
        last_saved_sample_unix=151,
    ) == (True, 150)
    assert _should_skip_local_telemetry_duplicate(
        telemetry_packet,
        local_node_id="!01020304",
        last_saved_sample_unix=149,
    ) == (False, 150)


def test_build_environment_points_from_packet_rows_collects_metrics_and_filters() -> None:
    summary = {
        "from": "!ABCDEF12",
        "from_long_name": "Weather Node",
        "portnum": "TELEMETRY_APP",
        "rx_time_unix": 200,
    }
    packet = {
        "decoded": {
            "telemetry": {
                "time": 180,
                "environmentMetrics": {
                    "temperature": "22.5",
                    "relativeHumidity": 55,
                    "ignored": "not-number",
                },
            }
        }
    }
    rows = [(9, 190, json.dumps(summary), json.dumps(packet))]

    points, metric_meta, node_meta = _build_environment_points(
        rows,
        metric_filter="",
        node_filter="",
    )
    filtered_points, _filtered_metrics, _filtered_nodes = _build_environment_points(
        rows,
        metric_filter="temperature",
        node_filter="!abcdef12",
    )
    empty_points, _empty_metrics, _empty_nodes = _build_environment_points(
        rows,
        metric_filter="voltage",
        node_filter="!abcdef12",
    )

    assert [point["metric_key"] for point in points] == ["relative_humidity", "temperature"]
    assert points[0]["node_id"] == "!abcdef12"
    assert points[0]["node_label"] == "Weather Node"
    assert points[0]["unix"] == 200
    assert {point["value"] for point in points} == {22.5, 55.0}
    assert metric_meta["temperature"]["count"] == 1
    assert metric_meta["temperature"]["min"] == 22.5
    assert metric_meta["temperature"]["max"] == 22.5
    assert node_meta["!abcdef12"]["count"] == 2
    assert len(filtered_points) == 1
    assert filtered_points[0]["metric_key"] == "temperature"
    assert empty_points == []


def test_build_environment_points_from_rollups_and_merge_meta_maps() -> None:
    rollup_rows = [
        (300, "01020304", "", "voltage", "Voltage", 2, 25.0, 12.0, 13.0, 13.0, 320),
        (360, "!01020304", "Node A", "temperature", "Temperature", 1, None, None, None, 22.0, 360),
        (400, "!01020304", "Node A", "bad", "Bad", 1, None, None, None, None, 400),
        (420, "", "No Node", "voltage", "Voltage", 1, 1.0, 1.0, 1.0, 1.0, 420),
    ]

    points, metric_meta, node_meta = _build_environment_points_from_rollups(
        rollup_rows,
        metric_filter="",
        node_filter="",
    )

    assert [point["metric_key"] for point in points] == ["voltage", "temperature"]
    assert points[0]["value"] == 12.5
    assert points[0]["sample_count"] == 2
    assert metric_meta["voltage"]["count"] == 2
    assert metric_meta["temperature"]["count"] == 1
    assert node_meta["!01020304"]["count"] == 3
    assert node_meta["!01020304"]["label"] == "Node A"

    derived_metric_meta, derived_node_meta = _derive_environment_meta_from_points(points)
    merged_metric_meta, merged_node_meta = _merge_environment_meta_maps(
        metric_meta,
        node_meta,
        derived_metric_meta,
        derived_node_meta,
    )

    assert merged_metric_meta["voltage"]["count"] == 4
    assert merged_metric_meta["voltage"]["node_ids"] == {"!01020304"}
    assert merged_node_meta["!01020304"]["count"] == 6
    assert merged_node_meta["!01020304"]["metric_keys"] == {"voltage", "temperature"}


def test_search_packets_handles_empty_and_no_match_queries() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    store = SimpleNamespace(_conn=conn, _read_conn=None, _lock=threading.Lock())
    conn.execute(
        "INSERT INTO packets(created_unix, summary_json, packet_json) VALUES (?, ?, ?)",
        (
            100,
            json.dumps({"packet_id": 1, "text": "alpha"}),
            json.dumps({"decoded": {"text": "bravo"}}),
        ),
    )
    conn.execute(
        "INSERT INTO chat(created_unix, message_json) VALUES (?, ?)",
        (200, json.dumps({"text": "charlie"})),
    )
    conn.commit()

    empty = search_packets(store, "", scope="bogus", source="bogus", limit=999, before=99, after=99, scan_limit=999999)
    no_match = search_packets(store, "delta", scope="summary", source="packet", limit=2)

    assert empty["ok"] is True
    assert empty["scope"] == "both"
    assert empty["source"] == "both"
    assert empty["limit"] == 500
    assert empty["before"] == 30
    assert empty["after"] == 30
    assert empty["scan_limit"] == 50000
    assert empty["matches"] == 0
    assert empty["entries"] == []

    assert no_match["ok"] is True
    assert no_match["scope"] == "summary"
    assert no_match["source"] == "packet"
    assert no_match["scanned_packets"] == 1
    assert no_match["scanned_chat"] == 0
    assert no_match["matches"] == 0
    assert no_match["entries"] == []
