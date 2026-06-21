import sqlite3
from types import SimpleNamespace

import meshdash.history_store_runtime_impl as runtime_impl
from meshdash.history_schema import initialize_history_schema
from meshdash.history_store_policy import HistoryStorePolicy
from meshdash.history_store_runtime_init import (
    _load_custom_telemetry_settings_from_conn,
    initialize_history_store_runtime,
)
from meshdash.history_store_runtime_maintenance import (
    close_history_store,
    maybe_prune_history_store_unlocked,
    prune_history_store_unlocked,
    reset_history_store,
)


class _Lock:
    def __init__(self) -> None:
        self.enters = 0

    def __enter__(self):
        self.enters += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False


class _Conn:
    def __init__(self, row: tuple[object, ...] | None = None) -> None:
        self.row = row
        self.closed = False
        self.executed: list[str] = []

    def execute(self, sql: str, params: object = None):
        del params
        self.executed.append(sql)
        return self

    def fetchone(self):
        return self.row

    def close(self) -> None:
        self.closed = True


def test_initialize_history_store_runtime_uses_legacy_open_and_preloads_settings() -> None:
    policy = HistoryStorePolicy(
        max_rows=123,
        event_max_rows=456,
        retention_seconds=7,
        event_retention_seconds=8,
        rollup_retention_seconds=9,
    )
    opened: list[dict[str, object]] = []
    conn = _Conn(
        (
            '[{"metric_key":"temp-c","source":"decoded","path":"telemetry.environment.temperature","scale":"1"}]',
            "321",
        )
    )
    locks: list[_Lock] = []

    def lock_factory() -> _Lock:
        lock = _Lock()
        locks.append(lock)
        return lock

    def open_legacy(**kwargs):
        opened.append(kwargs)
        return conn

    store = SimpleNamespace()
    initialize_history_store_runtime(
        store,
        db_path="/tmp/history.radio-abcdef12.sqlite3",
        max_rows=1,
        retention_days=2,
        event_max_rows=3,
        event_retention_days=4,
        rollup_retention_days=5,
        lock_factory=lock_factory,
        build_history_store_policy_fn=lambda **kwargs: policy,
        open_and_initialize_history_connection_fn=open_legacy,
        initialize_raw_packet_store_runtime_fn=lambda *_args, **_kwargs: None,
    )

    assert store.db_path == "/tmp/history.radio-abcdef12.sqlite3"
    assert store.local_node_id == "!abcdef12"
    assert store.max_rows == 123
    assert store.event_max_rows == 456
    assert store._conn is conn
    assert store._read_conn is None
    assert len(locks) == 2
    assert opened == [
        {
            "db_path": store.db_path,
            "retention_seconds": 7,
            "event_retention_seconds": 8,
            "rollup_retention_seconds": 9,
            "max_rows": 123,
            "event_max_rows": 456,
        }
    ]
    assert store._custom_telemetry_updated_unix == 321
    assert store._custom_telemetry_rules == [
        {
            "metric_key": "temp_c",
            "source": "decoded",
            "path": "telemetry.environment.temperature",
            "portnum": "",
            "enabled": True,
            "scale": 1.0,
            "offset": 0.0,
        }
    ]
    assert store._bbs_host_settings["title"] == "Packet Exchange"
    assert store._bot_runtime_settings == {
        "zork_enabled": False,
        "ping_enabled": False,
        "ping_message_only": False,
    }


def test_initialize_history_store_runtime_uses_policy_open_when_injected() -> None:
    policy = HistoryStorePolicy(
        max_rows=200,
        event_max_rows=2000,
        retention_seconds=70,
        event_retention_seconds=80,
        rollup_retention_seconds=90,
    )
    calls: list[dict[str, object]] = []
    conn = _Conn(("bad-json", "bad-time"))

    initialize_history_store_runtime(
        SimpleNamespace(),
        db_path=":memory:",
        max_rows=1,
        retention_days=2,
        event_max_rows=3,
        event_retention_days=4,
        rollup_retention_days=5,
        build_history_store_policy_fn=lambda **kwargs: policy,
        open_and_initialize_history_connection_with_policy_fn=lambda **kwargs: calls.append(kwargs) or conn,
    )

    assert calls == [{"db_path": ":memory:", "policy": policy}]


def test_load_custom_telemetry_settings_handles_missing_and_invalid_rows() -> None:
    assert _load_custom_telemetry_settings_from_conn(_Conn(None)) == ([], 0)
    assert _load_custom_telemetry_settings_from_conn(_Conn(("{}", None))) == ([], 0)

    class BrokenConn:
        def execute(self, *_args, **_kwargs):
            raise sqlite3.OperationalError("missing table")

    assert _load_custom_telemetry_settings_from_conn(BrokenConn()) == ([], 0)


def test_history_store_maintenance_close_prune_maybe_and_reset_paths() -> None:
    conn = _Conn()
    lock = _Lock()
    store = SimpleNamespace(_conn=conn, _lock=lock, _read_conn=None)
    close_history_store(store)
    assert conn.closed is True
    assert lock.enters == 1

    read_conn = _Conn()
    read_lock = _Lock()
    store = SimpleNamespace(_conn=_Conn(), _lock=_Lock(), _read_conn=read_conn, _read_lock=read_lock)
    close_history_store(store)
    assert read_conn.closed is True
    assert read_lock.enters == 1

    policy = HistoryStorePolicy(
        max_rows=10,
        event_max_rows=20,
        retention_seconds=30,
        event_retention_seconds=40,
        rollup_retention_seconds=50,
    )
    policy_calls: list[object] = []
    prune_history_store_unlocked(
        SimpleNamespace(_conn="conn", _policy=policy),
        prune_history_connection_with_policy_fn=lambda conn, *, policy: policy_calls.append((conn, policy)),
    )
    assert policy_calls == [("conn", policy)]

    legacy_calls: list[dict[str, object]] = []
    legacy_store = SimpleNamespace(
        _conn="conn",
        max_rows=10,
        event_max_rows=20,
        retention_seconds=30,
        event_retention_seconds=40,
        rollup_retention_seconds=50,
    )
    prune_history_store_unlocked(
        legacy_store,
        prune_history_connection_fn=lambda conn, **kwargs: legacy_calls.append({"conn": conn, **kwargs}),
    )
    assert legacy_calls == [
        {
            "conn": "conn",
            "retention_seconds": 30,
            "event_retention_seconds": 40,
            "rollup_retention_seconds": 50,
            "max_rows": 10,
            "event_max_rows": 20,
        }
    ]

    pruned: list[str] = []
    maybe_store = SimpleNamespace(_writes_since_prune=4)
    maybe_prune_history_store_unlocked(
        maybe_store,
        next_prune_counter_fn=lambda value: (value + 1, False),
        prune_unlocked_fn=lambda: pruned.append("yes"),
    )
    assert maybe_store._writes_since_prune == 5
    assert pruned == []
    maybe_prune_history_store_unlocked(
        maybe_store,
        next_prune_counter_fn=lambda value: (0, True),
        prune_unlocked_fn=lambda: pruned.append("yes"),
    )
    assert maybe_store._writes_since_prune == 0
    assert pruned == ["yes"]

    sqlite_conn = sqlite3.connect(":memory:")
    initialize_history_schema(sqlite_conn)
    sqlite_conn.execute("INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(?, ?, ?)", (1, "{}", "{}"))
    read_conn = _Conn()
    reset_store = SimpleNamespace(
        _conn=sqlite_conn,
        _lock=_Lock(),
        _read_conn=read_conn,
        _read_lock=_Lock(),
        _last_local_telemetry_sample_unix=99,
        _bbs_host_settings={"title": "old"},
        _custom_telemetry_rules=[{"metric_key": "old"}],
        _bot_runtime_settings={"zork_enabled": True},
    )

    assert reset_history_store(reset_store) == 1
    assert reset_store._last_local_telemetry_sample_unix == 0
    assert reset_store._custom_telemetry_rules == []
    assert reset_store._bbs_host_settings["title"] == "Packet Exchange"
    assert reset_store._bot_runtime_settings == {
        "zork_enabled": False,
        "ping_enabled": False,
        "ping_message_only": False,
    }
    assert any("wal_checkpoint" in sql for sql in read_conn.executed)


def test_history_store_facade_methods_delegate_to_runtime_helpers(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    def _record(name: str, value: object = None):
        calls.append((name, value))
        return {"helper": name, "value": value}

    monkeypatch.setattr(
        runtime_impl,
        "_initialize_history_store_runtime_helper",
        lambda store, **kwargs: _record("init", kwargs),
    )
    monkeypatch.setattr(runtime_impl, "_close_history_store_helper", lambda store: _record("close"))
    monkeypatch.setattr(runtime_impl, "_prune_history_store_unlocked_helper", lambda store: _record("prune"))
    monkeypatch.setattr(
        runtime_impl,
        "_maybe_prune_history_store_unlocked_helper",
        lambda store, *, prune_unlocked_fn: _record("maybe_prune", callable(prune_unlocked_fn)),
    )
    monkeypatch.setattr(runtime_impl, "_reset_history_store_helper", lambda store: 7)
    monkeypatch.setattr(runtime_impl, "_load_recent_packets_helper", lambda store, limit: _record("packets", limit))
    monkeypatch.setattr(runtime_impl, "_search_packets_helper", lambda store, needle, **kwargs: _record("search", (needle, kwargs)))
    monkeypatch.setattr(runtime_impl, "_load_environment_metrics_history_helper", lambda store, **kwargs: _record("env", kwargs))
    monkeypatch.setattr(runtime_impl, "_load_malformed_text_history_helper", lambda store, **kwargs: _record("malformed", kwargs))
    monkeypatch.setattr(runtime_impl, "_load_recent_chat_helper", lambda store, limit: _record("recent_chat", limit))
    monkeypatch.setattr(runtime_impl, "_load_chat_page_helper", lambda store, **kwargs: _record("chat_page", kwargs))
    monkeypatch.setattr(runtime_impl, "_load_connections_helper", lambda store: _record("connections"))
    monkeypatch.setattr(runtime_impl, "_load_link_edges_helper", lambda store, **kwargs: _record("links", kwargs))
    monkeypatch.setattr(runtime_impl, "_load_node_history_helper", lambda store, node_id, hours, points: _record("node_history", (node_id, hours, points)))
    monkeypatch.setattr(runtime_impl, "_load_online_activity_helper", lambda store, hours: _record("online", hours))
    monkeypatch.setattr(runtime_impl, "_load_node_saved_counts_helper", lambda store: _record("saved_counts"))
    monkeypatch.setattr(runtime_impl, "_load_node_position_counts_helper", lambda store: _record("position_counts"))
    monkeypatch.setattr(runtime_impl, "_load_node_capabilities_helper", lambda store: _record("capabilities"))
    monkeypatch.setattr(runtime_impl, "_load_node_packet_trends_helper", lambda store, **kwargs: _record("trends", kwargs))
    monkeypatch.setattr(runtime_impl, "_load_summary_metrics_helper", lambda store, hours: _record("summary", hours))
    monkeypatch.setattr(runtime_impl, "_load_top_nodes_helper", lambda store, **kwargs: _record("top", kwargs))
    monkeypatch.setattr(runtime_impl, "_load_database_stats_helper", lambda store: _record("stats"))
    monkeypatch.setattr(runtime_impl, "_save_connection_event_wrapper_helper", lambda store, **kwargs: _record("save_conn", kwargs))
    monkeypatch.setattr(runtime_impl, "_save_packet_helper", lambda store, entry: _record("save_packet", entry))
    monkeypatch.setattr(runtime_impl, "_save_chat_helper", lambda store, entry: _record("save_chat", entry))
    monkeypatch.setattr(runtime_impl, "_update_chat_helper", lambda store, entry: True)
    monkeypatch.setattr(runtime_impl, "_save_summary_metrics_helper", lambda store, summary: _record("save_summary", summary))
    monkeypatch.setattr(runtime_impl, "_load_custom_telemetry_settings_helper", lambda store: _record("get_custom"))
    monkeypatch.setattr(runtime_impl, "_save_custom_telemetry_settings_helper", lambda store, *, rules: _record("set_custom", rules))
    monkeypatch.setattr(runtime_impl, "_load_bbs_settings_helper", lambda store: _record("get_bbs"))
    monkeypatch.setattr(runtime_impl, "_load_bot_runtime_settings_helper", lambda store: _record("get_bot"))
    monkeypatch.setattr(runtime_impl, "_load_bbs_posts_helper", lambda store: _record("get_posts"))
    monkeypatch.setattr(runtime_impl, "_save_bbs_settings_helper", lambda store, *, settings: _record("set_bbs", settings))
    monkeypatch.setattr(runtime_impl, "_save_bot_runtime_settings_helper", lambda store, *, settings: _record("set_bot", settings))
    monkeypatch.setattr(runtime_impl, "_append_bbs_post_helper", lambda store, *, post: _record("append_post", post))
    monkeypatch.setattr(runtime_impl, "_load_raw_packet_stats_helper", lambda store: _record("raw_stats"))
    monkeypatch.setattr(runtime_impl, "_save_raw_packet_settings_helper", lambda store, *, settings: _record("raw_settings", settings))
    monkeypatch.setattr(runtime_impl, "_save_raw_packet_capture_helper", lambda store, packet: _record("raw_packet", packet))
    monkeypatch.setattr(runtime_impl, "_build_raw_packet_database_download_helper", lambda store: _record("raw_download"))

    store = runtime_impl.HistoryStore(
        db_path=":memory:",
        max_rows=1,
        retention_days=2,
        event_max_rows=3,
        event_retention_days=4,
        rollup_retention_days=5,
    )

    store.close()
    store._prune_unlocked()
    store._maybe_prune_unlocked()
    assert store.reset() == 7
    assert store.load_recent_packets(5)["helper"] == "packets"
    assert store.search_packets("needle", limit=1, before=2, after=3, scope="chat", scan_limit=4, source="packets")[
        "helper"
    ] == "search"
    assert store.load_environment_metrics_history(window_hours=1, metric="temp", node_id="!node", limit=5)["helper"] == "env"
    assert store.load_malformed_text_history(window_hours=1, node_id="!node", limit=5)["helper"] == "malformed"
    assert store.load_recent_chat(2)["helper"] == "recent_chat"
    assert store.load_chat_page(limit=2, before_id=3, before_unix=4, scope="all", peer_id="!peer")["helper"] == "chat_page"
    assert store.load_connections()["helper"] == "connections"
    assert store.load_link_edges(window="1d", limit=10)["helper"] == "links"
    assert store.load_node_history("!node", 24, 100)["helper"] == "node_history"
    assert store.load_online_activity(24)["helper"] == "online"
    assert store.load_node_saved_counts()["helper"] == "saved_counts"
    assert store.load_node_position_counts()["helper"] == "position_counts"
    assert store.load_node_capabilities()["helper"] == "capabilities"
    assert store.load_node_packet_trends(
        local_node_id="!local",
        window_seconds=60,
        bucket_count=4,
        recent_window_seconds=30,
    )["helper"] == "trends"
    assert store.load_summary_metrics(24)["helper"] == "summary"
    assert store.load_top_nodes(category="heard", limit=3, exclude_node_ids=["!skip"])["helper"] == "top"
    assert store.database_stats()["helper"] == "stats"
    assert store.database_stats()["raw_packet_store"]["helper"] == "raw_stats"
    assert store.raw_packet_stats()["helper"] == "raw_stats"
    assert store.set_raw_packet_capture_settings({"capture_enabled": True})["helper"] == "raw_settings"
    assert store.save_raw_packet({"id": 1})["helper"] == "raw_packet"
    assert store.raw_packet_database_download()["helper"] == "raw_download"
    store.save_connection_event("!a", "!b", 1, "TEXT", 2)
    store.save_packet({"id": 1})
    store.save_chat({"text": "hi"})
    assert store.update_chat({"id": 1}) is True
    store.save_summary_metrics({"node_count": 1})
    assert store.get_custom_telemetry_settings()["helper"] == "get_custom"
    assert store.set_custom_telemetry_settings([{"metric_key": "temp"}])["helper"] == "set_custom"
    assert store.get_bbs_settings()["helper"] == "get_bbs"
    assert store.get_bot_runtime_settings()["helper"] == "get_bot"
    assert store.get_bbs_posts()["helper"] == "get_posts"
    assert store.set_bbs_settings({"title": "bbs"})["helper"] == "set_bbs"
    assert store.set_bot_runtime_settings({"ping_enabled": True})["helper"] == "set_bot"
    assert store.append_bbs_post({"title": "post"})["helper"] == "append_post"

    assert calls[0][0] == "init"
    assert ("maybe_prune", True) in calls
