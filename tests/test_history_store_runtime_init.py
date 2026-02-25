from meshdash.history_store_runtime_init import initialize_history_store_runtime


def test_initialize_history_store_runtime_sets_fields_and_opens_connection():
    observed = {}
    sentinel_lock = object()
    sentinel_conn = object()

    class _Store:
        pass

    def _open_and_initialize_history_connection(**kwargs):
        observed["open_kwargs"] = kwargs
        return sentinel_conn

    store = _Store()
    initialize_history_store_runtime(
        store,
        db_path="/tmp/history.sqlite3",
        max_rows=50,
        retention_days=7,
        event_max_rows=200,
        event_retention_days=30,
        rollup_retention_days=365,
        lock_factory=lambda: sentinel_lock,
        open_and_initialize_history_connection_fn=_open_and_initialize_history_connection,
    )

    assert store.db_path == "/tmp/history.sqlite3"
    assert store.max_rows == 100
    assert store.retention_seconds == 7 * 86400
    assert store.event_max_rows == 1000
    assert store.event_retention_seconds == 30 * 86400
    assert store.rollup_retention_seconds == 365 * 86400
    assert store._policy.max_rows == 100
    assert store._policy.event_max_rows == 1000
    assert store._policy.retention_seconds == 7 * 86400
    assert store._policy.event_retention_seconds == 30 * 86400
    assert store._policy.rollup_retention_seconds == 365 * 86400
    assert store._writes_since_prune == 0
    assert store._lock is sentinel_lock
    assert store._conn is sentinel_conn
    assert observed["open_kwargs"] == {
        "db_path": "/tmp/history.sqlite3",
        "retention_seconds": 7 * 86400,
        "event_retention_seconds": 30 * 86400,
        "rollup_retention_seconds": 365 * 86400,
        "max_rows": 100,
        "event_max_rows": 1000,
    }
