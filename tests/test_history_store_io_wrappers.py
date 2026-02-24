from meshdash.history_store import HistoryStore
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
