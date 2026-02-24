from meshdash.history_store_connection import (
    open_and_initialize_history_connection,
    prune_history_connection,
)


def test_open_and_initialize_history_connection_creates_expected_tables(tmp_path):
    db_path = tmp_path / "history.sqlite3"
    conn = open_and_initialize_history_connection(
        db_path=str(db_path),
        retention_seconds=7 * 86400,
        event_retention_seconds=30 * 86400,
        rollup_retention_seconds=365 * 86400,
        max_rows=5000,
        event_max_rows=200000,
    )
    try:
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "packets" in table_names
        assert "chat" in table_names
        assert "connections" in table_names
    finally:
        conn.close()


def test_prune_history_connection_is_idempotent(tmp_path):
    db_path = tmp_path / "history_prune.sqlite3"
    conn = open_and_initialize_history_connection(
        db_path=str(db_path),
        retention_seconds=0,
        event_retention_seconds=0,
        rollup_retention_seconds=0,
        max_rows=100,
        event_max_rows=1000,
    )
    try:
        # Should not raise for an empty DB.
        prune_history_connection(
            conn,
            retention_seconds=0,
            event_retention_seconds=0,
            rollup_retention_seconds=0,
            max_rows=100,
            event_max_rows=1000,
        )
    finally:
        conn.close()
