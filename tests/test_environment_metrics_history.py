import sqlite3
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.history_schema import initialize_history_schema
from meshdash.history_store_packets import load_environment_metrics_history
from meshdash.html_js import build_dashboard_js


def test_environment_history_applies_metric_filter_before_rollup_limit() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    now = int(time.time() // 60 * 60)

    recent_voltage_rows = [
        (
            now - (idx * 60),
            "!11111111",
            "Voltage Node",
            "voltage",
            "Voltage",
            1,
            12.4,
            12.4,
            12.4,
            12.4,
            now - (idx * 60),
        )
        for idx in range(260)
    ]
    older_baro_rows = [
        (
            now - ((13 * 24 * 3600) - (idx * 3600)),
            "!22222222",
            "Weather Node",
            "barometric_pressure",
            "Barometric Pressure",
            1,
            995.0 + idx,
            995.0 + idx,
            995.0 + idx,
            995.0 + idx,
            now - ((13 * 24 * 3600) - (idx * 3600)),
        )
        for idx in range(5)
    ]
    conn.executemany(
        """
        INSERT INTO environment_metrics_1m(
          bucket_unix, node_id, node_label, metric_key, metric_label,
          sample_count, value_sum, value_min, value_max, last_value, last_seen_unix
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        recent_voltage_rows + older_baro_rows,
    )
    conn.commit()

    store = SimpleNamespace(
        _conn=conn,
        _read_conn=None,
        _lock=threading.Lock(),
        _custom_telemetry_rules=None,
    )

    unfiltered = load_environment_metrics_history(
        store,
        window_hours=14 * 24,
        limit=200,
    )
    filtered = load_environment_metrics_history(
        store,
        window_hours=14 * 24,
        metric="barometric_pressure",
        limit=200,
    )

    assert unfiltered["total_points"] == 200
    assert all(point["metric_key"] == "voltage" for point in unfiltered["points"])

    assert filtered["source"] == "rollup_1m"
    assert filtered["total_points"] == 5
    assert [point["metric_key"] for point in filtered["points"]] == ["barometric_pressure"] * 5
    assert filtered["points"][0]["unix"] < (now - (10 * 24 * 3600))
    assert filtered["metrics"] == [
        {
            "key": "barometric_pressure",
            "label": "Barometric Pressure",
            "count": 5,
            "nodes": 1,
            "min": 995.0,
            "max": 999.0,
        }
    ]


def test_dashboard_js_fetches_filtered_sensor_series_from_server() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "const envMetricsCatalogCache = new Map();" in js
    assert "const envMetricsSeriesCache = new Map();" in js
    assert 'params.set("metric", cleanMetric);' in js
    assert 'params.set("node_id", cleanNodeId);' in js
    assert 'metricSelect.addEventListener("change", () => {' in js
    assert 'nodeSelect.addEventListener("change", () => {' in js
    assert "void renderEnvironmentMetricsView(false);" in js
