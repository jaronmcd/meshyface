import sqlite3
import threading
from types import SimpleNamespace

from meshdash.history_schema import initialize_history_schema
from meshdash.history_store_settings import (
    load_bot_runtime_settings,
    save_bot_runtime_settings,
)


def _make_store(conn: sqlite3.Connection) -> SimpleNamespace:
    return SimpleNamespace(
        _conn=conn,
        _read_conn=None,
        _read_lock=None,
        _lock=threading.Lock(),
        _maybe_prune_unlocked=lambda: None,
    )


def test_bot_runtime_settings_store_defaults_to_bots_disabled() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    store = _make_store(conn)

    loaded = load_bot_runtime_settings(store)

    assert loaded["ok"] is True
    assert loaded["settings"] == {
        "zork_enabled": False,
        "ping_enabled": False,
        "ping_message_only": False,
    }
    assert loaded["updated_unix"] == 0


def test_bot_runtime_settings_store_round_trips_and_normalizes_values() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    store = _make_store(conn)

    saved = save_bot_runtime_settings(
        store,
        settings={
            "zork_enabled": "yes",
            "ping_enabled": 1,
            "ping_message_only": "true",
        },
    )

    assert saved["ok"] is True
    assert saved["settings"] == {
        "zork_enabled": True,
        "ping_enabled": True,
        "ping_message_only": True,
    }
    assert int(saved["updated_unix"]) > 0

    loaded = load_bot_runtime_settings(store)

    assert loaded["ok"] is True
    assert loaded["settings"] == saved["settings"]
    assert int(loaded["updated_unix"]) > 0
