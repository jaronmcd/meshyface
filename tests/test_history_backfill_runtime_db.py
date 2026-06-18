import json
import sqlite3
from pathlib import Path

from meshdash.history.db import (
    open_and_initialize_history_connection_with_policy,
    open_history_read_connection,
    prune_history_connection_with_policy,
    reset_history_connection,
)
from meshdash.history_backfill import (
    backfill_environment_metric_rollups,
    backfill_node_capabilities,
    backfill_node_hour_seen,
    backfill_node_position_counts,
    backfill_node_saved_counts,
)
from meshdash.history_schema import initialize_history_schema
from meshdash.history_store_policy import HistoryStorePolicy
from meshdash.history_writes import (
    _canonical_node_id,
    _extract_node_label,
    save_environment_metric_rollups,
    save_packet_event_and_rollups,
)


def _json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"))


def _to_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except Exception:
        return None


def _metric_values(bucket: int, node_id: str, packets: int, last_seen: int) -> tuple[object, ...]:
    return (
        bucket,
        node_id,
        packets,
        4.0,
        2,
        1.0,
        3.0,
        -160.0,
        2,
        -90.0,
        -70.0,
        5,
        2,
        2,
        3,
        last_seen,
    )


def test_history_backfills_rebuild_counts_capabilities_names_and_environment_rollups() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    conn.execute(
        """
        INSERT INTO node_metrics_1m(
          bucket_unix, node_id, packet_count, snr_sum, snr_count, snr_min, snr_max,
          rssi_sum, rssi_count, rssi_min, rssi_max, hops_sum, hops_count, hops_min,
          hops_max, last_seen_unix
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        _metric_values(1_700_000_000, "!01020304", 4, 1_700_000_050),
    )
    conn.execute(
        "INSERT INTO node_positions(created_unix, node_id, lat, lon, altitude, sats_in_view) VALUES(?, ?, ?, ?, ?, ?)",
        (1_700_000_040, "!01020304", 30.0, -97.0, 100.0, 6),
    )
    conn.execute(
        "INSERT INTO packet_events(created_unix, from_id, to_id, portnum, hops) VALUES(?, ?, ?, ?, ?)",
        (1_700_000_060, "!01020304", "^all", "TEXT_MESSAGE_APP", 3),
    )
    conn.execute(
        "INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(?, ?, ?)",
        (
            1_700_000_070,
            _json({"from": "!01020304", "portnum": "NODEINFO_APP"}),
            _json({"decoded": {"user": {"id": "!01020304", "shortName": "mesh", "longName": "Mesh Relay"}}}),
        ),
    )
    conn.execute(
        "INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(?, ?, ?)",
        (
            1_700_000_080,
            _json({"from": "!01020304", "rx_time_unix": 1_700_000_080, "from_long_name": "Weather Node"}),
            _json({"decoded": {"telemetry": {"time": 1_700_000_080}, "environmentMetrics": {"temperature": 21.5}}}),
        ),
    )
    conn.execute("INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(?, ?, ?)", (1, "[]", "[]"))
    conn.execute("DELETE FROM node_saved_counts")
    conn.execute("DELETE FROM node_position_counts")
    conn.execute("DELETE FROM node_hour_seen")

    backfill_node_saved_counts(conn)
    backfill_node_position_counts(conn)
    backfill_node_hour_seen(conn)
    backfill_node_capabilities(conn, to_int_fn=_to_int)
    env_result = backfill_environment_metric_rollups(conn, reset_existing=True, commit_every=1)

    assert conn.execute("SELECT saved_packets, saved_points FROM node_saved_counts").fetchone() == (4, 1)
    assert conn.execute("SELECT position_points, position_last_seen_unix FROM node_position_counts").fetchone() == (
        1,
        1_700_000_040,
    )
    assert conn.execute("SELECT hour_bucket, node_id FROM node_hour_seen").fetchone() == (
        1_699_999_200,
        "!01020304",
    )
    caps = conn.execute(
        """
        SELECT first_seen_unix, last_seen_unix, has_position, last_position_unix,
               last_hops, last_short_name, last_long_name, names_updated_unix
        FROM node_capabilities
        WHERE node_id = '!01020304'
        """
    ).fetchone()
    assert caps == (
        1_700_000_040,
        1_700_000_070,
        1,
        1_700_000_040,
        3,
        "mesh",
        "Mesh Relay",
        1_700_000_070,
    )
    assert env_result == {
        "before_rows": 0,
        "after_rows": 1,
        "delta_rows": 1,
        "scanned_packets": 3,
        "usable_packets": 2,
        "bad_rows": 1,
    }
    assert conn.execute(
        "SELECT node_id, node_label, metric_key, sample_count, last_value FROM environment_metrics_1m"
    ).fetchone() == ("!01020304", "Weather Node", "temperature", 1, 21.5)

    # Existing derived rows should make these no-ops.
    backfill_node_saved_counts(conn)
    backfill_node_position_counts(conn)
    backfill_node_hour_seen(conn)
    assert conn.execute("SELECT COUNT(*) FROM node_saved_counts").fetchone()[0] == 1


def test_save_packet_event_and_rollups_updates_core_history_tables() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)

    save_packet_event_and_rollups(
        conn,
        {
            "rx_time_unix": 1_700_000_065,
            "from": "01020304",
            "to": "05060708",
            "portnum": "TEXT_MESSAGE_APP",
            "rx_snr": "1.5",
            "rx_rssi": "-82",
            "hops": "2",
            "hop_start": "5",
            "hop_limit": "3",
            "channel": 0,
            "want_ack": True,
            "priority": "DEFAULT",
            "position": {"latitude": 30.0, "longitude": -97.0, "altitude": 100, "satsInView": 6},
            "battery_level": "88",
            "from_long_name": "Relay",
        },
        packet={
            "decoded": {
                "telemetry": {"time": 1_700_000_065},
                "environmentMetrics": {"temperature": 20.0, "relativeHumidity": "55"},
            },
            "user": {"id": "!01020304", "shortName": "mesh", "longName": "Mesh Relay"},
        },
        now_unix_fn=lambda: 1_700_000_100,
    )

    assert conn.execute("SELECT from_id, to_id, portnum, hops FROM packet_events").fetchone() == (
        "01020304",
        "05060708",
        "TEXT_MESSAGE_APP",
        2,
    )
    assert conn.execute("SELECT node_id, packet_count, last_seen_unix FROM node_metrics_1m").fetchone() == (
        "01020304",
        1,
        1_700_000_065,
    )
    assert conn.execute("SELECT from_id, to_id, packet_count FROM link_metrics_1m").fetchone() == (
        "01020304",
        "05060708",
        1,
    )
    assert conn.execute("SELECT node_id, lat, lon, altitude, sats_in_view FROM node_positions").fetchone() == (
        "01020304",
        30.0,
        -97.0,
        100.0,
        6,
    )
    assert conn.execute(
        "SELECT has_position, last_hops, battery_level, last_short_name, last_long_name FROM node_capabilities"
    ).fetchone() == (1, 2, 88, "mesh", "Mesh Relay")
    assert conn.execute(
        "SELECT metric_key, metric_label, sample_count, last_value FROM environment_metrics_1m ORDER BY metric_key"
    ).fetchall() == [
        ("relative_humidity", "Relativehumidity", 1, 55.0),
        ("temperature", "Temperature", 1, 20.0),
    ]


def test_environment_rollup_helpers_cover_noops_canonical_ids_and_updates() -> None:
    assert _canonical_node_id("") == ""
    assert _canonical_node_id("broadcast") == "^all"
    assert _canonical_node_id("!ABCDEF12") == "!abcdef12"
    assert _canonical_node_id("ABCDEF12") == "!abcdef12"
    assert _canonical_node_id(255) == "!000000ff"
    assert _canonical_node_id("255") == "!000000ff"
    assert _canonical_node_id(True) == "True"
    assert _canonical_node_id("node") == "node"
    assert _extract_node_label({"from_long_name": " Long ", "from_short_name": "Short"}, "!node") == "Long"
    assert _extract_node_label({"from_short_name": "Short"}, "!node") == "Short"
    assert _extract_node_label({}, "!node") == "!node"

    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    save_environment_metric_rollups(conn, summary={}, packet=None, now_unix_fn=lambda: 1_700_000_100)
    save_environment_metric_rollups(conn, summary={}, packet={"decoded": "bad"}, now_unix_fn=lambda: 1_700_000_100)
    save_environment_metric_rollups(
        conn,
        summary={"from": "01020304"},
        packet={"decoded": {}},
        now_unix_fn=lambda: 1_700_000_100,
    )
    save_environment_metric_rollups(
        conn,
        summary={"from": "^all"},
        packet={"decoded": {"environmentMetrics": {"temperature": 20}}},
        now_unix_fn=lambda: 1_700_000_100,
    )
    save_environment_metric_rollups(
        conn,
        summary={"from": "01020304", "rx_time_unix": 1_700_000_020, "from_name": "Weather"},
        packet={"decoded": {"environmentMetrics": {"": 1, "temperature": "bad", "humidity": 50}}},
        now_unix_fn=lambda: 1_700_000_100,
    )
    save_environment_metric_rollups(
        conn,
        summary={"from": "01020304", "rx_time_unix": 1_700_000_010},
        packet={"decoded": {"telemetry": {"time": 1_700_000_010}, "environmentMetrics": {"humidity": 40}}},
        now_unix_fn=lambda: 1_700_000_100,
    )

    assert conn.execute(
        """
        SELECT node_id, node_label, metric_key, sample_count, value_sum, value_min,
               value_max, last_value, last_seen_unix
        FROM environment_metrics_1m
        """
    ).fetchone() == ("!01020304", "!01020304", "humidity", 2, 90.0, 40.0, 50.0, 50.0, 1_700_000_020)


def test_history_db_open_read_prune_and_reset_paths(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "history.sqlite3"
    policy = HistoryStorePolicy(
        max_rows=100,
        event_max_rows=1000,
        retention_seconds=7 * 86400,
        event_retention_seconds=30 * 86400,
        rollup_retention_seconds=365 * 86400,
    )

    conn = open_and_initialize_history_connection_with_policy(db_path=str(db_path), policy=policy)
    prune_history_connection_with_policy(conn, policy=policy)
    conn.execute("INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(?, ?, ?)", (100, "{}", "{}"))
    conn.execute("INSERT INTO chat(created_unix, message_json) VALUES(?, ?)", (101, "{}"))
    conn.commit()

    read_conn = open_history_read_connection(db_path=str(db_path))
    assert read_conn.execute("SELECT COUNT(*) FROM packets").fetchone()[0] == 1
    try:
        read_conn.execute("INSERT INTO chat(created_unix, message_json) VALUES(?, ?)", (102, "{}"))
    except sqlite3.OperationalError as exc:
        assert "readonly" in str(exc).lower() or "query" in str(exc).lower()
    else:
        raise AssertionError("read-only history connection accepted a write")
    read_conn.close()

    assert reset_history_connection(conn) == 2
    assert conn.execute("SELECT COUNT(*) FROM packets").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM chat").fetchone()[0] == 0
    assert reset_history_connection(conn) == 0
    conn.close()
