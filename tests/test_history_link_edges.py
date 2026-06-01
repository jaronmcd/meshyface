import sqlite3
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.history_schema import initialize_history_schema
from meshdash.history_store_link_edges import load_link_edges
from meshdash.http_routes_get import handle_dashboard_get


def _make_store(conn: sqlite3.Connection) -> SimpleNamespace:
    return SimpleNamespace(
        _conn=conn,
        _read_conn=None,
        _read_lock=None,
        _lock=threading.Lock(),
    )


def test_link_edges_returns_rollup_only_edges_for_selected_window() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    store = _make_store(conn)

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
            (29000, "!11111111", "!22222222", 2, 6.0, 2, 2.0, 4.0, -180.0, 2, -95.0, -85.0, 6, 2, 2, 4, 29010),
            (29100, "!11111111", "!22222222", 3, 12.0, 3, 3.0, 5.0, -270.0, 3, -96.0, -84.0, 9, 3, 2, 4, 29110),
            (200, "!33333333", "!44444444", 8, 0.0, 0, None, None, 0.0, 0, None, None, 0, 0, None, None, 210),
        ],
    )
    conn.executemany(
        """
        INSERT INTO node_capabilities(
          node_id, last_seen_unix, has_position, last_short_name, last_long_name
        ) VALUES (?, ?, ?, ?, ?)
        """,
        [
            ("!11111111", 29120, 0, "one", "Node One"),
            ("!22222222", 29130, 0, "two", "Node Two"),
        ],
    )
    conn.commit()

    with patch("meshdash.history_store_link_edges.time.time", return_value=30000):
        payload = load_link_edges(store, window="6h", limit=10)

    assert payload["ok"] is True
    assert payload["window"] == "6h"
    assert payload["edge_count"] == 1
    assert payload["history_caps"]["!11111111"]["last_short_name"] == "one"
    assert payload["history_caps"]["!22222222"]["last_long_name"] == "Node Two"
    assert payload["edges"] == [
        {
            "from": "!11111111",
            "to": "!22222222",
            "count": 5,
            "session_count": 0,
            "lifetime_count": 5,
            "is_real": True,
            "confidence": "confirmed",
            "first_rx_unix": 29000,
            "last_rx_unix": 29110,
            "hops_samples": 5,
            "snr_samples": 5,
            "rssi_samples": 5,
            "is_rollup": True,
            "avg_hops": 3.0,
            "last_hops": 4,
            "avg_snr": 3.6,
            "snr_min": 2.0,
            "snr_max": 5.0,
            "avg_rssi": -90.0,
            "rssi_min": -96.0,
            "rssi_max": -84.0,
        }
    ]


def test_link_edges_max_uses_retained_rollup_range_and_reports_truncation() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    store = _make_store(conn)

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
            (100, "!11111111", "!22222222", 5, 0.0, 0, None, None, 0.0, 0, None, None, 0, 0, None, None, 101),
            (200, "!33333333", "!44444444", 4, 0.0, 0, None, None, 0.0, 0, None, None, 0, 0, None, None, 201),
        ],
    )
    conn.commit()

    payload = load_link_edges(store, window="max", limit=1)

    assert payload["window"] == "max"
    assert payload["truncated"] is True
    assert payload["edge_count"] == 1
    assert payload["edges"][0]["from"] == "!11111111"


def test_link_edges_history_route_calls_state_loader_attribute() -> None:
    calls: list[tuple[object, object]] = []

    def state_fn():
        return {}

    def link_edges_fn(*, window: object, limit: object) -> dict[str, object]:
        calls.append((window, limit))
        return {"ok": True, "window": window, "limit": limit, "edges": []}

    setattr(state_fn, "link_edges_fn", link_edges_fn)
    written: list[tuple[int, dict[str, object], bool]] = []
    deps = SimpleNamespace(
        state_fn=state_fn,
        to_int_fn=lambda raw: int(raw) if str(raw or "").strip() else None,
        write_json_response_fn=lambda _handler, *, status_code, payload_obj, no_store=False, **_kwargs: written.append(
            (status_code, payload_obj, no_store)
        ),
    )

    handle_dashboard_get(
        object(),
        path="/api/history/links",
        query="window=30d&limit=42",
        deps=deps,
    )

    assert calls == [("30d", 42)]
    assert written == [(200, {"ok": True, "window": "30d", "limit": 42, "edges": []}, True)]


def test_link_edges_limit_cap_is_higher_for_max_window() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    store = _make_store(conn)

    max_payload = load_link_edges(store, window="max", limit=10000)
    weekly_payload = load_link_edges(store, window="7d", limit=10000)

    assert max_payload["window"] == "max"
    assert max_payload["limit"] == 10000
    assert weekly_payload["window"] == "7d"
    assert weekly_payload["limit"] == 3000
