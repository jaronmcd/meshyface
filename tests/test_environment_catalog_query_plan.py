import random
import sqlite3

from meshdash.history_queries import (
    fetch_environment_metric_catalog_metric_rows,
    fetch_environment_metric_catalog_node_rows,
)
from meshdash.history_schema import initialize_history_schema


class _CapturingConnection:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.sql = ""
        self.params: tuple = ()

    def execute(self, sql, params=()):
        self.sql, self.params = sql, tuple(params)
        return self.conn.execute(sql, params)


def _populated_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    rng = random.Random(3)
    rows = []
    for bucket in range(0, 4000 * 60, 60):
        for node in range(3):
            metric = rng.choice(["voltage", "temperature", "humidity"])
            value = rng.uniform(0, 30)
            rows.append((bucket, f"!{node:08x}", f"Node {node}", metric, metric.title(), 2, value * 2, value, value, value, bucket + 30))
    conn.executemany("INSERT OR REPLACE INTO environment_metrics_1m VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    return conn


def test_environment_catalog_queries_use_the_recent_window_index_and_keep_results() -> None:
    # Guard: grouping by the bare column made SQLite scan the whole rollup table through the
    # (metric_key|node_id, bucket_unix) index; the catalog cost then grew with rollup retention.
    conn = _populated_connection()
    cutoff = 3900 * 60

    for fetch, column in (
        (fetch_environment_metric_catalog_metric_rows, "metric_key"),
        (fetch_environment_metric_catalog_node_rows, "node_id"),
    ):
        capture = _CapturingConnection(conn)
        rows = fetch(capture, cutoff=cutoff)
        plan = " | ".join(row[3] for row in conn.execute("EXPLAIN QUERY PLAN " + capture.sql, capture.params))

        assert f"GROUP BY +{column}" in capture.sql
        assert "USING INDEX idx_environment_metrics_1m_last_seen_unix" in plan, plan
        assert "SCAN environment_metrics_1m" not in plan, plan
        bare = conn.execute(capture.sql.replace(f"GROUP BY +{column}", f"GROUP BY {column}"), capture.params).fetchall()
        assert rows == bare
        assert rows
