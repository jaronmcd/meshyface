import json
import sqlite3
from types import SimpleNamespace

from meshdash.history_connection_writes import save_connection_event
from meshdash.history_connections import (
    build_connection_insert_values,
    merge_connection_row,
    normalize_connection_event_input,
)
from meshdash.history_metric_rows import build_metric_rollup_values, merge_metric_rollup_row
from meshdash.history_metric_upsert_queries import METRIC_FIELDS, select_existing_row, where_clause
from meshdash.history_metric_upsert_writes import insert_metric_row, update_metric_row
from meshdash.history_read_api import (
    load_connections_data,
    load_node_capabilities_data,
    load_node_position_counts_data,
    load_node_saved_counts_data,
    load_recent_chat_data,
    load_recent_packets_data,
)
from meshdash.history_views import (
    build_node_history_loader,
    build_online_activity_loader,
    build_summary_metrics_loader,
    empty_node_history,
    empty_online_activity,
    empty_summary_metrics,
)


def test_history_read_api_delegates_fetch_and_decode_functions() -> None:
    conn = object()
    calls: list[tuple[str, object]] = []

    def _fetch_limited(label: str):
        def _fetch(fetch_conn: object, *, limit: int):
            calls.append((label, fetch_conn))
            return [(label, limit)]

        return _fetch

    def _fetch(label: str):
        def _fetch_rows(fetch_conn: object):
            calls.append((label, fetch_conn))
            return [(label, 1)]

        return _fetch_rows

    def decode_list(rows):
        return [{"decoded": list(rows)}]

    def decode_map(rows):
        return {str(key): value for key, value in rows}

    assert load_recent_packets_data(
        conn,
        limit=5,
        fetch_recent_packet_rows_fn=_fetch_limited("packets"),
        decode_recent_packets_rows_fn=decode_list,
    ) == [{"decoded": [("packets", 5)]}]
    assert load_recent_chat_data(
        conn,
        limit=2,
        fetch_recent_chat_rows_fn=_fetch_limited("chat"),
        decode_recent_chat_rows_fn=decode_list,
    ) == [{"decoded": [("chat", 2)]}]
    assert load_connections_data(
        conn,
        fetch_connection_rows_fn=_fetch("connections"),
        decode_connections_rows_fn=decode_list,
    ) == [{"decoded": [("connections", 1)]}]
    assert load_node_saved_counts_data(
        conn,
        fetch_node_saved_count_rows_fn=_fetch("saved"),
        decode_node_saved_counts_rows_fn=decode_map,
    ) == {"saved": 1}
    assert load_node_position_counts_data(
        conn,
        fetch_node_position_count_rows_fn=_fetch("positions"),
        decode_node_position_counts_rows_fn=decode_map,
    ) == {"positions": 1}
    assert load_node_capabilities_data(
        conn,
        fetch_node_capability_rows_fn=_fetch("capabilities"),
        decode_node_capabilities_rows_fn=decode_map,
    ) == {"capabilities": 1}
    assert [label for label, fetch_conn in calls if fetch_conn is conn] == [
        "packets",
        "chat",
        "connections",
        "saved",
        "positions",
        "capabilities",
    ]


def test_history_view_loaders_return_empty_payloads_on_missing_store_and_errors() -> None:
    node_empty = empty_node_history(" !node ")
    online_empty = empty_online_activity(-1)
    summary_empty = empty_summary_metrics(0)

    assert node_empty["node_id"] == " !node "
    assert online_empty["window_hours"] == 72
    assert len(online_empty["hourly_profile"]) == 24
    assert summary_empty["window_hours"] == 72
    assert summary_empty["packet_series"]["available"] is False  # type: ignore[index]

    assert build_node_history_loader(None, default_hours=12, default_points=50)(" !node ", None, None)["node_id"] == "!node"
    assert build_online_activity_loader(None, default_hours=12)(None)["window_hours"] == 12
    assert build_summary_metrics_loader(None, default_hours=12)(None)["window_hours"] == 12

    broken = SimpleNamespace(
        load_node_history=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("node failed")),
        load_online_activity=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("online failed")),
        load_summary_metrics=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("summary failed")),
    )
    assert build_node_history_loader(broken, default_hours=6, default_points=10)("!node", 1, 2)["points"] == []
    assert build_online_activity_loader(broken, default_hours=6)(1)["points"] == []
    assert build_summary_metrics_loader(broken, default_hours=6)(1)["points"] == []
    assert build_summary_metrics_loader(object(), default_hours=6)(1)["points"] == []


def test_history_view_loaders_pass_clean_overrides_to_store() -> None:
    calls: list[dict[str, object]] = []

    class Store:
        def load_node_history(self, **kwargs):
            calls.append({"node": kwargs})
            return {"ok": True, "kind": "node", **kwargs}

        def load_online_activity(self, **kwargs):
            calls.append({"online": kwargs})
            return {"ok": True, "kind": "online", **kwargs}

        def load_summary_metrics(self, **kwargs):
            calls.append({"summary": kwargs})
            return {"ok": True, "kind": "summary", **kwargs}

    store = Store()

    node = build_node_history_loader(store, default_hours=6, default_points=10)(" !node ", 24, 100)
    online = build_online_activity_loader(store, default_hours=6)(24)
    summary = build_summary_metrics_loader(store, default_hours=6)(24)

    assert node["node_id"] == "!node"
    assert node["window_hours"] == 24
    assert node["max_points"] == 100
    assert online["window_hours"] == 24
    assert summary["window_hours"] == 24
    assert len(calls) == 3


def test_metric_rollup_values_merge_existing_rows_and_write_sqlite_rows() -> None:
    rolled = build_metric_rollup_values(event_unix=100, rx_snr=1.5, rx_rssi=-80.0, hops=2)
    empty = build_metric_rollup_values(event_unix=101, rx_snr=None, rx_rssi=None, hops=None)
    merged = merge_metric_rollup_row(
        row=tuple(rolled[field] for field in METRIC_FIELDS),
        event_unix=120,
        rx_snr=3.0,
        rx_rssi=-70.0,
        hops=4,
    )

    assert rolled["packet_count"] == 1
    assert rolled["snr_count"] == 1
    assert rolled["hops_sum"] == 2
    assert empty["snr_count"] == 0
    assert empty["hops_min"] is None
    assert merged["packet_count"] == 2
    assert merged["snr_sum"] == 4.5
    assert merged["rssi_max"] == -70.0
    assert merged["hops_max"] == 4
    assert merged["last_seen_unix"] == 120

    conn = sqlite3.connect(":memory:")
    metric_columns = ", ".join(f"{field} REAL" for field in METRIC_FIELDS)
    conn.execute(f"CREATE TABLE node_metrics(bucket_unix INTEGER, node_id TEXT, {metric_columns})")

    insert_metric_row(
        conn,
        table_name="node_metrics",
        key_fields=("node_id",),
        bucket_unix=60,
        key_values=("!node",),
        rolled=rolled,
    )
    assert where_clause(key_fields=("node_id",)) == "bucket_unix = ? AND node_id = ?"
    assert select_existing_row(
        conn,
        table_name="node_metrics",
        key_fields=("node_id",),
        bucket_unix=60,
        key_values=("!node",),
    ) is not None

    update_metric_row(
        conn,
        table_name="node_metrics",
        key_fields=("node_id",),
        bucket_unix=60,
        key_values=("!node",),
        merged=merged,
    )
    packet_count, snr_sum, *_rest = conn.execute(
        "SELECT packet_count, snr_sum FROM node_metrics WHERE bucket_unix = 60 AND node_id = '!node'"
    ).fetchone()
    assert packet_count == 2
    assert snr_sum == 4.5


def test_connection_helpers_normalize_merge_and_persist_connection_rows() -> None:
    assert normalize_connection_event_input(
        rx_time=None,
        portnum=None,
        hops=-1,
        now_unix_fn=lambda: 100,
    ) == (100, None, None)
    assert normalize_connection_event_input(
        rx_time=1000,
        portnum=123,
        hops=3,
        now_unix_fn=lambda: 100,
    ) == (100, "123", 3)
    assert build_connection_insert_values(
        from_id="!a",
        to_id="!b",
        event_unix=10,
        clean_port="TEXT",
        clean_hops=2,
    ) == ("!a", "!b", 10, 10, 1, '["TEXT"]', 2, 2, 1)

    merged = merge_connection_row(
        row=(20, 30, 2, '"not-list"', None, None, None),
        event_unix=10,
        clean_port="ROUTING",
        clean_hops=None,
    )
    assert merged == {
        "first_seen_unix": 10,
        "last_seen_unix": 30,
        "seen_count": 3,
        "portnums_json": '["ROUTING"]',
        "last_hops": None,
        "hops_sum": 0,
        "hops_count": 0,
    }

    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE connections(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          from_id TEXT NOT NULL,
          to_id TEXT NOT NULL,
          first_seen_unix INTEGER NOT NULL,
          last_seen_unix INTEGER NOT NULL,
          seen_count INTEGER NOT NULL,
          portnums_json TEXT NOT NULL,
          last_hops INTEGER,
          hops_sum INTEGER NOT NULL DEFAULT 0,
          hops_count INTEGER NOT NULL DEFAULT 0,
          UNIQUE(from_id, to_id)
        )
        """
    )

    save_connection_event(
        conn,
        from_id="!a",
        to_id="!b",
        rx_time=90,
        portnum="TEXT",
        hops=2,
        now_unix_fn=lambda: 100,
    )
    save_connection_event(
        conn,
        from_id="!a",
        to_id="!b",
        rx_time=1000,
        portnum="ROUTING",
        hops=4,
        now_unix_fn=lambda: 100,
    )

    row = conn.execute(
        "SELECT first_seen_unix, last_seen_unix, seen_count, portnums_json, last_hops, hops_sum, hops_count "
        "FROM connections WHERE from_id = '!a' AND to_id = '!b'"
    ).fetchone()
    assert row[:3] == (90, 100, 2)
    assert json.loads(row[3]) == ["ROUTING", "TEXT"]
    assert row[4:] == (4, 6, 2)
