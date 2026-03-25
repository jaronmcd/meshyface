import argparse

from meshdash.dashboard_setup import open_optional_history_store, seed_tracker_if_empty


def test_open_optional_history_store_returns_none_when_disabled():
    args = argparse.Namespace(no_history=True)
    store = open_optional_history_store(args, history_store_cls=lambda **_kwargs: object(), history_db_path="/tmp/x")
    assert store is None


def test_open_optional_history_store_builds_store_when_enabled():
    args = argparse.Namespace(
        no_history=False,
        history_max_rows=5000,
        history_retention_days=7,
        history_event_max_rows=200000,
        history_event_retention_days=30,
        history_rollup_retention_days=365,
    )
    captured = {}

    def _store_cls(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    store = open_optional_history_store(
        args,
        history_store_cls=_store_cls,
        history_db_path="/tmp/test.sqlite3",
    )
    assert store == {"ok": True}
    assert captured["db_path"] == "/tmp/test.sqlite3"
    assert captured["max_rows"] == 5000


def test_open_optional_history_store_handles_constructor_error():
    args = argparse.Namespace(
        no_history=False,
        history_max_rows=5000,
        history_retention_days=7,
        history_event_max_rows=200000,
        history_event_retention_days=30,
        history_rollup_retention_days=365,
    )
    lines = []

    def _raise_store_cls(**_kwargs):
        raise RuntimeError("db unavailable")

    store = open_optional_history_store(
        args,
        history_store_cls=_raise_store_cls,
        history_db_path="/tmp/test.sqlite3",
        print_fn=lines.append,
    )

    assert store is None
    assert len(lines) == 1
    assert "History disabled: cannot open /tmp/test.sqlite3: db unavailable" in lines[0]


def test_seed_tracker_if_empty_calls_seed_only_when_no_packets():
    calls = {"seed": 0}

    class _Tracker:
        def __init__(self, has_packets):
            self._has_packets = has_packets

        def has_recent_packets(self):
            return self._has_packets

    seed_tracker_if_empty(
        _Tracker(has_packets=True),
        iface="iface",
        seed_tracker_fn=lambda *_args, **_kwargs: calls.__setitem__("seed", calls["seed"] + 1),
    )
    seed_tracker_if_empty(
        _Tracker(has_packets=False),
        iface="iface",
        seed_tracker_fn=lambda *_args, **_kwargs: calls.__setitem__("seed", calls["seed"] + 1),
    )
    assert calls["seed"] == 1
