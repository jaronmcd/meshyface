import sqlite3

from meshdash.history_backfill import (
    backfill_environment_metric_rollups,
    backfill_node_capabilities,
    backfill_node_hour_seen,
    backfill_node_saved_counts,
)
from meshdash.history.db import initialize_history_schema


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def test_backfill_node_capabilities_populates_from_history_tables():
    conn = sqlite3.connect(":memory:")
    try:
        initialize_history_schema(conn)
        conn.execute(
            """
            INSERT INTO node_metrics_1m(
              bucket_unix, node_id, packet_count,
              snr_sum, snr_count, snr_min, snr_max,
              rssi_sum, rssi_count, rssi_min, rssi_max,
              hops_sum, hops_count, hops_min, hops_max,
              last_seen_unix
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (60, "!n1", 1, 0.0, 0, None, None, 0.0, 0, None, None, 0, 0, None, None, 100),
        )
        conn.execute(
            """
            INSERT INTO node_positions(created_unix, node_id, lat, lon, altitude, sats_in_view)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (120, "!n1", 44.95, -93.10, None, None),
        )
        conn.execute(
            """
            INSERT INTO packet_events(
              created_unix, from_id, to_id, portnum,
              rx_snr, rx_rssi, hops, hop_start, hop_limit,
              channel, want_ack, priority, summary_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (130, "!n1", "^all", "TEXT_MESSAGE_APP", None, None, 3, None, None, None, None, None, "{}"),
        )

        backfill_node_capabilities(conn, to_int_fn=_to_int)

        row = conn.execute(
            """
            SELECT last_seen_unix, has_position, last_position_unix,
                   last_hops, battery_level, battery_updated_unix
            FROM node_capabilities
            WHERE node_id = ?
            """,
            ("!n1",),
        ).fetchone()

        assert row is not None
        assert row[0] == 130
        assert row[1] == 1
        assert row[2] == 120
        assert row[3] == 3
        assert row[4] is None
        assert row[5] is None
    finally:
        conn.close()


def test_backfill_node_capabilities_is_noop_when_capabilities_exist():
    conn = sqlite3.connect(":memory:")
    try:
        initialize_history_schema(conn)
        conn.execute(
            """
            INSERT INTO node_capabilities(
              node_id, last_seen_unix, has_position, last_position_unix,
              last_hops, battery_level, battery_updated_unix
            ) VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            ("!existing", 50, 0, None, None, None, None),
        )
        conn.execute(
            """
            INSERT INTO node_metrics_1m(
              bucket_unix, node_id, packet_count,
              snr_sum, snr_count, snr_min, snr_max,
              rssi_sum, rssi_count, rssi_min, rssi_max,
              hops_sum, hops_count, hops_min, hops_max,
              last_seen_unix
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (120, "!new", 1, 0.0, 0, None, None, 0.0, 0, None, None, 0, 0, None, None, 999),
        )

        backfill_node_capabilities(conn, to_int_fn=_to_int)

        rows = conn.execute(
            "SELECT node_id, last_seen_unix FROM node_capabilities ORDER BY node_id ASC"
        ).fetchall()
        assert rows == [("!existing", 50)]
    finally:
        conn.close()


def test_backfill_node_saved_counts_populates_and_skips_empty_node_ids():
    conn = sqlite3.connect(":memory:")
    try:
        initialize_history_schema(conn)
        conn.execute(
            """
            INSERT INTO node_metrics_1m(
              bucket_unix, node_id, packet_count,
              snr_sum, snr_count, snr_min, snr_max,
              rssi_sum, rssi_count, rssi_min, rssi_max,
              hops_sum, hops_count, hops_min, hops_max,
              last_seen_unix
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (60, "!n2", 3, 0.0, 0, None, None, 0.0, 0, None, None, 0, 0, None, None, 120),
        )
        conn.execute(
            """
            INSERT INTO node_metrics_1m(
              bucket_unix, node_id, packet_count,
              snr_sum, snr_count, snr_min, snr_max,
              rssi_sum, rssi_count, rssi_min, rssi_max,
              hops_sum, hops_count, hops_min, hops_max,
              last_seen_unix
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (120, "!n2", 2, 0.0, 0, None, None, 0.0, 0, None, None, 0, 0, None, None, 180),
        )
        conn.execute(
            """
            INSERT INTO node_metrics_1m(
              bucket_unix, node_id, packet_count,
              snr_sum, snr_count, snr_min, snr_max,
              rssi_sum, rssi_count, rssi_min, rssi_max,
              hops_sum, hops_count, hops_min, hops_max,
              last_seen_unix
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (180, "   ", 9, 0.0, 0, None, None, 0.0, 0, None, None, 0, 0, None, None, 200),
        )

        backfill_node_saved_counts(conn)

        row = conn.execute(
            "SELECT saved_packets, saved_points, saved_last_seen_unix FROM node_saved_counts WHERE node_id = ?",
            ("!n2",),
        ).fetchone()
        assert row == (5, 2, 180)
        assert conn.execute(
            "SELECT COUNT(*) FROM node_saved_counts WHERE node_id = ?",
            ("!n2",),
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_backfill_node_saved_counts_is_noop_when_table_already_has_rows():
    conn = sqlite3.connect(":memory:")
    try:
        initialize_history_schema(conn)
        conn.execute(
            "INSERT INTO node_saved_counts(node_id, saved_packets, saved_points, saved_last_seen_unix) VALUES(?, ?, ?, ?)",
            ("!existing", 1, 1, 1),
        )
        backfill_node_saved_counts(conn)
        rows = conn.execute("SELECT node_id FROM node_saved_counts ORDER BY node_id").fetchall()
        assert rows == [("!existing",)]
    finally:
        conn.close()


def test_backfill_node_saved_counts_handles_missing_table_gracefully():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE node_metrics_1m(node_id TEXT, packet_count INTEGER, last_seen_unix INTEGER, bucket_unix INTEGER)")
        backfill_node_saved_counts(conn)
    finally:
        conn.close()


def test_backfill_node_hour_seen_populates_and_handles_failures():
    conn = sqlite3.connect(":memory:")
    try:
        initialize_history_schema(conn)
        conn.execute(
            """
            INSERT INTO node_metrics_1m(
              bucket_unix, node_id, packet_count,
              snr_sum, snr_count, snr_min, snr_max,
              rssi_sum, rssi_count, rssi_min, rssi_max,
              hops_sum, hops_count, hops_min, hops_max,
              last_seen_unix
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (3661, "!n3", 1, 0.0, 0, None, None, 0.0, 0, None, None, 0, 0, None, None, 10),
        )
        conn.execute(
            """
            INSERT INTO node_metrics_1m(
              bucket_unix, node_id, packet_count,
              snr_sum, snr_count, snr_min, snr_max,
              rssi_sum, rssi_count, rssi_min, rssi_max,
              hops_sum, hops_count, hops_min, hops_max,
              last_seen_unix
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (7201, "", 1, 0.0, 0, None, None, 0.0, 0, None, None, 0, 0, None, None, 20),
        )

        backfill_node_hour_seen(conn)
        rows = conn.execute("SELECT hour_bucket, node_id FROM node_hour_seen ORDER BY node_id").fetchall()
        assert (3600, "!n3") in rows
    finally:
        conn.close()

    class _FailingConn:
        def __init__(self):
            self._calls = 0

        def execute(self, _sql, _params=None):
            self._calls += 1
            if self._calls == 1:
                raise RuntimeError("missing table")
            if self._calls == 2:
                raise RuntimeError("select failed")
            raise RuntimeError("insert failed")

    backfill_node_hour_seen(_FailingConn())

    class _Cursor:
        def __init__(self, *, one=None, many=None):
            self._one = one
            self._many = many or []

        def fetchone(self):
            return self._one

        def fetchall(self):
            return list(self._many)

    class _InsertFailConn:
        def __init__(self):
            self.calls = 0

        def execute(self, _sql, _params=None):
            self.calls += 1
            if self.calls == 1:
                return _Cursor(one=(0,))
            if self.calls == 2:
                return _Cursor(many=[(3600, "!n"), (7200, "")])
            raise RuntimeError("insert fail")

    backfill_node_hour_seen(_InsertFailConn())


def test_backfill_environment_metric_rollups_populates_from_saved_packets():
    conn = sqlite3.connect(":memory:")
    try:
        initialize_history_schema(conn)
        conn.execute(
            """
            INSERT INTO packets(created_unix, summary_json, packet_json)
            VALUES(
              120,
              '{"from":"!a1b2c3d4","from_short_name":"alpha","rx_time_unix":120,"portnum":"TELEMETRY_APP"}',
              '{"fromId":"!a1b2c3d4","rxTime":120,"decoded":{"portnum":"TELEMETRY_APP","telemetry":{"time":120,"environmentMetrics":{"temperature":21.5,"relativeHumidity":55.0}}}}'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO packets(created_unix, summary_json, packet_json)
            VALUES(
              130,
              '{"from":"!a1b2c3d4","from_short_name":"alpha","rx_time_unix":130,"portnum":"TELEMETRY_APP"}',
              '{"fromId":"!a1b2c3d4","rxTime":130,"decoded":{"portnum":"TELEMETRY_APP","telemetry":{"time":130,"environmentMetrics":{"temperature":22.5}}}}'
            )
            """
        )

        result = backfill_environment_metric_rollups(conn, reset_existing=False)

        assert result["scanned_packets"] == 2
        assert result["usable_packets"] == 2
        assert result["bad_rows"] == 0
        row = conn.execute(
            """
            SELECT sample_count, value_sum, value_min, value_max, last_value
            FROM environment_metrics_1m
            WHERE bucket_unix = 120 AND node_id = '!a1b2c3d4' AND metric_key = 'temperature'
            """
        ).fetchone()
        assert row == (2, 44.0, 21.5, 22.5, 22.5)
    finally:
        conn.close()


def test_backfill_environment_metric_rollups_reset_clears_existing_rows():
    conn = sqlite3.connect(":memory:")
    try:
        initialize_history_schema(conn)
        conn.execute(
            """
            INSERT INTO environment_metrics_1m(
              bucket_unix, node_id, node_label, metric_key, metric_label,
              sample_count, value_sum, value_min, value_max, last_value, last_seen_unix
            ) VALUES(0, '!a', 'alpha', 'temperature', 'Temperature',
                     1, 1.0, 1.0, 1.0, 1.0, 0)
            """
        )
        result = backfill_environment_metric_rollups(conn, reset_existing=True)
        assert result["before_rows"] == 0
        assert conn.execute("SELECT COUNT(*) FROM environment_metrics_1m").fetchone()[0] == 0
    finally:
        conn.close()
