import threading

import meshdash.history_store_nodes as history_store_nodes_module
import meshdash.history_store_packets as history_store_packets_module
from meshdash.history_store import HistoryStore
from meshdash.history_store_chat import (
    load_recent_chat as load_recent_chat_domain,
    save_chat as save_chat_domain,
)
from meshdash.history_store_connections import (
    load_connections as load_connections_domain,
    save_connection_event as save_connection_event_domain,
)
from meshdash.history_store_nodes import (
    load_node_capabilities as load_node_capabilities_domain,
    load_node_history as load_node_history_domain,
    load_online_activity as load_online_activity_domain,
    load_node_saved_counts as load_node_saved_counts_domain,
)
from meshdash.history_store_packets import (
    load_recent_packets as load_recent_packets_domain,
    search_packets as search_packets_domain,
    save_packet as save_packet_domain,
)
from meshdash.history_store_summary import (
    load_summary_metrics as load_summary_metrics_domain,
    save_summary_metrics as save_summary_metrics_domain,
)
from meshdash.history_store_reads import (
    load_connections,
    load_recent_chat,
)
from meshdash.history_store_writes import (
    save_chat,
    save_connection_event,
)


def _make_store(tmp_path):
    db_path = tmp_path / "history_wrappers.sqlite3"
    return HistoryStore(
        db_path=str(db_path),
        max_rows=5000,
        retention_days=7,
        event_max_rows=200000,
        event_retention_days=30,
        rollup_retention_days=365,
    )


def test_history_store_write_and_read_wrappers_round_trip_chat(tmp_path):
    store = _make_store(tmp_path)
    try:
        save_chat(
            store,
            {
                "from": "!a",
                "to": "!b",
                "text": "hello",
                "rx_time": "2026-02-24 00:00:00Z",
            },
        )
        recent_chat = load_recent_chat(store, 10)
        assert recent_chat
        assert recent_chat[-1]["text"] == "hello"
    finally:
        store.close()


def test_history_store_write_and_read_wrappers_round_trip_connections(tmp_path):
    store = _make_store(tmp_path)
    try:
        save_connection_event(
            store,
            from_id="!a",
            to_id="!b",
            rx_time=1_700_000_000,
            portnum="TEXT_MESSAGE_APP",
            hops=2,
        )
        rows = load_connections(store)
        assert rows
        assert rows[0]["from"] == "!a"
        assert rows[0]["to"] == "!b"
        assert rows[0]["count"] >= 1
    finally:
        store.close()


def test_history_store_domain_modules_round_trip_packet_chat_and_connection(tmp_path):
    store = _make_store(tmp_path)
    try:
        save_packet_domain(
            store,
            {
                "summary": {
                    "from": "!p1",
                    "to": "!p2",
                    "rx_time_unix": 1_700_000_100,
                    "rx_snr": 1.5,
                    "rx_rssi": -110.0,
                    "hops": 1,
                    "portnum": "TEXT_MESSAGE_APP",
                    "text": "packet text",
                },
                "packet": {
                    "id": 1_700_000_100,
                    "fromId": "!p1",
                    "toId": "!p2",
                    "rxTime": 1_700_000_100,
                },
            },
        )
        packets = load_recent_packets_domain(store, 10)
        assert packets
        assert packets[-1]["summary"]["from"] == "!p1"

        save_chat_domain(
            store,
            {
                "from": "!c1",
                "to": "!c2",
                "text": "chat text",
                "rx_time": "2026-02-24 00:00:00Z",
            },
        )
        chat_rows = load_recent_chat_domain(store, 10)
        assert chat_rows
        assert chat_rows[-1]["text"] == "chat text"

        save_connection_event_domain(
            store,
            from_id="!n1",
            to_id="!n2",
            rx_time=1_700_000_123,
            portnum="NODEINFO_APP",
            hops=3,
        )
        connection_rows = load_connections_domain(store)
        assert connection_rows
        assert connection_rows[0]["from"] == "!n1"
        assert connection_rows[0]["to"] == "!n2"
    finally:
        store.close()


def test_history_store_domain_node_modules_return_mapping_shapes(tmp_path):
    store = _make_store(tmp_path)
    try:
        capabilities = load_node_capabilities_domain(store)
        saved_counts = load_node_saved_counts_domain(store)
        assert isinstance(capabilities, dict)
        assert isinstance(saved_counts, dict)
    finally:
        store.close()


def test_history_store_domain_summary_metrics_round_trip(tmp_path):
    store = _make_store(tmp_path)
    try:
        save_summary_metrics_domain(
            store,
            {
                "node_count": 12,
                "saved_node_count": 7,
                "online_node_count": 4,
                "nodes_with_position": 9,
                "live_packet_count": 77,
                "real_edge_count": 5,
            },
        )
        payload = load_summary_metrics_domain(store, 24)
        assert payload["window_hours"] == 24
        assert payload["points"]
        latest = payload["points"][-1]
        assert latest["node_count"] == 12
        assert latest["saved_node_count"] == 7
        assert latest["online_node_count"] == 4
        assert latest["nodes_with_position"] == 9
        assert latest["live_packet_count"] == 77
        assert latest["real_edge_count"] == 5
    finally:
        store.close()


def test_history_store_domain_packet_search_supports_scope_and_context(tmp_path):
    store = _make_store(tmp_path)
    try:
        save_packet_domain(
            store,
            {
                "summary": {"from": "!a", "to": "^all", "text": "alpha"},
                "packet": {"id": 1},
            },
        )
        save_packet_domain(
            store,
            {
                "summary": {"from": "!b", "to": "^all", "text": "needle-hit"},
                "packet": {"id": 2},
            },
        )
        save_packet_domain(
            store,
            {
                "summary": {"from": "!c", "to": "^all", "text": "omega"},
                "packet": {"id": 3},
            },
        )

        payload = search_packets_domain(
            store,
            "needle-hit",
            limit=5,
            before=1,
            after=1,
            scope="summary",
        )

        assert payload["matches"] == 1
        assert payload["returned_matches"] == 1
        assert payload["scope"] == "summary"
        entries = payload["entries"]
        assert len(entries) == 3
        assert entries[0]["match"] is False
        assert entries[1]["match"] is True
        assert entries[2]["match"] is False
        assert entries[1]["summary"]["text"] == "needle-hit"
    finally:
        store.close()


def test_history_store_domain_node_history_and_online_wrappers_delegate(monkeypatch):
    calls = {"node_history": None, "online_activity": None}

    def _fake_load_node_history_data(
        conn,
        *,
        node_id,
        window_hours,
        max_points,
        fetch_node_history_rows_fn,
        build_node_history_payload_fn,
        now_unix_fn,
    ):
        calls["node_history"] = {
            "conn": conn,
            "node_id": node_id,
            "window_hours": window_hours,
            "max_points": max_points,
            "fetch_fn": fetch_node_history_rows_fn,
            "build_fn": build_node_history_payload_fn,
            "now_unix": now_unix_fn(),
        }
        return {"ok": True, "kind": "node"}

    def _fake_load_online_activity_data(
        conn,
        *,
        window_hours,
        fetch_online_activity_rows_fn,
        build_online_activity_payload_fn,
        now_unix_fn,
    ):
        calls["online_activity"] = {
            "conn": conn,
            "window_hours": window_hours,
            "fetch_fn": fetch_online_activity_rows_fn,
            "build_fn": build_online_activity_payload_fn,
            "now_unix": now_unix_fn(),
        }
        return {"ok": True, "kind": "online"}

    monkeypatch.setattr(
        history_store_nodes_module,
        "_load_node_history_data_helper",
        _fake_load_node_history_data,
    )
    monkeypatch.setattr(
        history_store_nodes_module,
        "_load_online_activity_data_helper",
        _fake_load_online_activity_data,
    )

    class _Store:
        def __init__(self):
            self._conn = object()
            self._lock = threading.Lock()

    store = _Store()
    node_payload = load_node_history_domain(store, "!abc123", 24, 200)
    online_payload = load_online_activity_domain(store, 48)

    assert node_payload == {"ok": True, "kind": "node"}
    assert online_payload == {"ok": True, "kind": "online"}

    assert calls["node_history"]["conn"] is store._conn
    assert calls["node_history"]["node_id"] == "!abc123"
    assert calls["node_history"]["window_hours"] == 24
    assert calls["node_history"]["max_points"] == 200
    assert callable(calls["node_history"]["fetch_fn"])
    assert callable(calls["node_history"]["build_fn"])
    assert isinstance(calls["node_history"]["now_unix"], float)

    assert calls["online_activity"]["conn"] is store._conn
    assert calls["online_activity"]["window_hours"] == 48
    assert callable(calls["online_activity"]["fetch_fn"])
    assert callable(calls["online_activity"]["build_fn"])
    assert isinstance(calls["online_activity"]["now_unix"], float)


def test_history_store_domain_saved_count_and_capability_wrappers_delegate(monkeypatch):
    calls = {"saved_counts": None, "capabilities": None}

    def _fake_load_node_saved_counts_data(
        conn,
        *,
        fetch_node_saved_count_rows_fn,
        decode_node_saved_counts_rows_fn,
    ):
        calls["saved_counts"] = {
            "conn": conn,
            "fetch_fn": fetch_node_saved_count_rows_fn,
            "decode_fn": decode_node_saved_counts_rows_fn,
        }
        return {"!a": {"saved_packets": 7}}

    def _fake_load_node_capabilities_data(
        conn,
        *,
        fetch_node_capability_rows_fn,
        decode_node_capabilities_rows_fn,
    ):
        calls["capabilities"] = {
            "conn": conn,
            "fetch_fn": fetch_node_capability_rows_fn,
            "decode_fn": decode_node_capabilities_rows_fn,
        }
        return {"!a": {"gps_capable": True}}

    monkeypatch.setattr(
        history_store_nodes_module,
        "_load_node_saved_counts_data_helper",
        _fake_load_node_saved_counts_data,
    )
    monkeypatch.setattr(
        history_store_nodes_module,
        "_load_node_capabilities_data_helper",
        _fake_load_node_capabilities_data,
    )

    class _Store:
        def __init__(self):
            self._conn = object()
            self._lock = threading.Lock()

    store = _Store()
    saved_counts = load_node_saved_counts_domain(store)
    capabilities = load_node_capabilities_domain(store)

    assert saved_counts == {"!a": {"saved_packets": 7}}
    assert capabilities == {"!a": {"gps_capable": True}}

    assert calls["saved_counts"]["conn"] is store._conn
    assert (
        calls["saved_counts"]["fetch_fn"]
        is history_store_nodes_module._fetch_node_saved_count_rows_helper
    )
    assert (
        calls["saved_counts"]["decode_fn"]
        is history_store_nodes_module._decode_node_saved_counts_rows_helper
    )

    assert calls["capabilities"]["conn"] is store._conn
    assert (
        calls["capabilities"]["fetch_fn"]
        is history_store_nodes_module._fetch_node_capability_rows_helper
    )
    assert (
        calls["capabilities"]["decode_fn"]
        is history_store_nodes_module._decode_node_capabilities_rows_helper
    )


class _CountingLock:
    def __init__(self):
        self.enter_count = 0

    def __enter__(self):
        self.enter_count += 1
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FailLock:
    def __enter__(self):
        raise AssertionError("unexpected lock use")

    def __exit__(self, exc_type, exc, tb):
        return False


def test_load_recent_packets_uses_primary_lock_when_read_connection_missing(monkeypatch):
    calls = {}

    def _fake_load_recent_packets_data(
        conn,
        *,
        limit,
        fetch_recent_packet_rows_fn,
        decode_recent_packets_rows_fn,
    ):
        calls["conn"] = conn
        calls["limit"] = limit
        return [{"ok": True}]

    monkeypatch.setattr(
        history_store_packets_module,
        "_load_recent_packets_data_helper",
        _fake_load_recent_packets_data,
    )

    class _Store:
        def __init__(self):
            self._conn = object()
            self._lock = _CountingLock()
            # If selected while _read_conn is missing, this test should fail.
            self._read_lock = _FailLock()
            self._read_conn = None

    store = _Store()
    rows = load_recent_packets_domain(store, 5)

    assert rows == [{"ok": True}]
    assert calls["conn"] is store._conn
    assert calls["limit"] == 5
    assert store._lock.enter_count == 1


def test_load_recent_packets_uses_read_lock_when_read_connection_present(monkeypatch):
    calls = {}

    def _fake_load_recent_packets_data(
        conn,
        *,
        limit,
        fetch_recent_packet_rows_fn,
        decode_recent_packets_rows_fn,
    ):
        calls["conn"] = conn
        calls["limit"] = limit
        return [{"ok": True}]

    monkeypatch.setattr(
        history_store_packets_module,
        "_load_recent_packets_data_helper",
        _fake_load_recent_packets_data,
    )

    class _Store:
        def __init__(self):
            self._conn = object()
            # If selected when _read_conn exists, this test should fail.
            self._lock = _FailLock()
            self._read_lock = _CountingLock()
            self._read_conn = object()

    store = _Store()
    rows = load_recent_packets_domain(store, 6)

    assert rows == [{"ok": True}]
    assert calls["conn"] is store._read_conn
    assert calls["limit"] == 6
    assert store._read_lock.enter_count == 1


def test_search_packets_uses_primary_lock_when_read_connection_missing(monkeypatch):
    calls = {}

    def _fake_fetch_packet_search_rows(conn, limit):
        calls["conn"] = conn
        calls["limit"] = limit
        return [
            (
                10,
                1_700_000_000,
                '{"text":"hello needle"}',
                '{"decoded":{"text":"hello needle"}}',
            ),
        ]

    monkeypatch.setattr(
        history_store_packets_module,
        "_fetch_packet_search_rows_helper",
        _fake_fetch_packet_search_rows,
    )

    class _Store:
        def __init__(self):
            self._conn = object()
            self._lock = _CountingLock()
            self._read_lock = _FailLock()
            self._read_conn = None

    store = _Store()
    payload = search_packets_domain(store, "needle", limit=10, before=0, after=0, scan_limit=100)

    assert payload["matches"] == 1
    assert payload["returned_matches"] == 1
    assert len(payload["entries"]) == 1
    assert calls["conn"] is store._conn
    assert calls["limit"] == 100
    assert store._lock.enter_count == 1


def test_search_packets_uses_read_lock_when_read_connection_present(monkeypatch):
    calls = {}

    def _fake_fetch_packet_search_rows(conn, limit):
        calls["conn"] = conn
        calls["limit"] = limit
        return [
            (
                11,
                1_700_000_010,
                '{"text":"needle in summary"}',
                '{"decoded":{"text":"needle"}}',
            ),
        ]

    monkeypatch.setattr(
        history_store_packets_module,
        "_fetch_packet_search_rows_helper",
        _fake_fetch_packet_search_rows,
    )

    class _Store:
        def __init__(self):
            self._conn = object()
            self._lock = _FailLock()
            self._read_lock = _CountingLock()
            self._read_conn = object()

    store = _Store()
    payload = search_packets_domain(store, "needle", limit=10, before=0, after=0, scan_limit=90)

    assert payload["matches"] == 1
    assert payload["returned_matches"] == 1
    assert len(payload["entries"]) == 1
    assert calls["conn"] is store._read_conn
    assert calls["limit"] == 90
    assert store._read_lock.enter_count == 1
