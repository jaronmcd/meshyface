from meshdash.history_store_runtime_maintenance import (
    close_history_store,
    maybe_prune_history_store_unlocked,
    prune_history_store_unlocked,
)


class _FakeLock:
    def __init__(self):
        self.entered = 0
        self.exited = 0

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exc_type, exc, tb):
        self.exited += 1
        return False


def test_close_history_store_closes_connection_under_lock():
    observed = {"closed": 0}

    class _Conn:
        def close(self):
            observed["closed"] += 1

    store = type("_Store", (), {"_lock": _FakeLock(), "_conn": _Conn()})()

    close_history_store(store)

    assert observed["closed"] == 1
    assert store._lock.entered == 1
    assert store._lock.exited == 1


def test_prune_history_store_unlocked_forwards_runtime_fields():
    observed = {}

    def _prune_history_connection(
        conn,
        *,
        retention_seconds,
        event_retention_seconds,
        rollup_retention_seconds,
        max_rows,
        event_max_rows,
    ):
        observed["args"] = (conn,)
        observed["kwargs"] = {
            "retention_seconds": retention_seconds,
            "event_retention_seconds": event_retention_seconds,
            "rollup_retention_seconds": rollup_retention_seconds,
            "max_rows": max_rows,
            "event_max_rows": event_max_rows,
        }

    store = type(
        "_Store",
        (),
        {
            "_conn": "conn",
            "retention_seconds": 7 * 86400,
            "event_retention_seconds": 30 * 86400,
            "rollup_retention_seconds": 365 * 86400,
            "max_rows": 5000,
            "event_max_rows": 200000,
        },
    )()

    prune_history_store_unlocked(
        store,
        prune_history_connection_fn=_prune_history_connection,
    )

    assert observed["args"] == ("conn",)
    assert observed["kwargs"] == {
        "retention_seconds": 7 * 86400,
        "event_retention_seconds": 30 * 86400,
        "rollup_retention_seconds": 365 * 86400,
        "max_rows": 5000,
        "event_max_rows": 200000,
    }


def test_prune_history_store_unlocked_prefers_policy_when_present():
    observed = {}

    def _prune_history_connection(
        conn,
        *,
        retention_seconds,
        event_retention_seconds,
        rollup_retention_seconds,
        max_rows,
        event_max_rows,
    ):
        observed["kwargs"] = {
            "retention_seconds": retention_seconds,
            "event_retention_seconds": event_retention_seconds,
            "rollup_retention_seconds": rollup_retention_seconds,
            "max_rows": max_rows,
            "event_max_rows": event_max_rows,
        }

    policy = type(
        "_Policy",
        (),
        {
            "retention_seconds": 1,
            "event_retention_seconds": 2,
            "rollup_retention_seconds": 3,
            "max_rows": 4,
            "event_max_rows": 5,
        },
    )()
    store = type(
        "_Store",
        (),
        {
            "_conn": "conn",
            "_policy": policy,
            "retention_seconds": 7 * 86400,
            "event_retention_seconds": 30 * 86400,
            "rollup_retention_seconds": 365 * 86400,
            "max_rows": 5000,
            "event_max_rows": 200000,
        },
    )()

    prune_history_store_unlocked(
        store,
        prune_history_connection_fn=_prune_history_connection,
    )

    assert observed["kwargs"] == {
        "retention_seconds": 1,
        "event_retention_seconds": 2,
        "rollup_retention_seconds": 3,
        "max_rows": 4,
        "event_max_rows": 5,
    }


def test_maybe_prune_history_store_unlocked_only_prunes_on_threshold():
    observed = {"prunes": 0}

    class _Store:
        _writes_since_prune = 5

    store = _Store()

    maybe_prune_history_store_unlocked(
        store,
        next_prune_counter_fn=lambda current: (current + 1, False),
        prune_unlocked_fn=lambda: observed.__setitem__("prunes", observed["prunes"] + 1),
    )
    assert store._writes_since_prune == 6
    assert observed["prunes"] == 0

    maybe_prune_history_store_unlocked(
        store,
        next_prune_counter_fn=lambda current: (current + 1, True),
        prune_unlocked_fn=lambda: observed.__setitem__("prunes", observed["prunes"] + 1),
    )
    assert store._writes_since_prune == 7
    assert observed["prunes"] == 1
