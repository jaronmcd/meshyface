import sqlite3
import time
from collections.abc import Iterable

from ..helpers import to_int as _to_int
from ..history_backfill import (
    backfill_node_capabilities as _backfill_node_capabilities_helper,
    backfill_node_hour_seen as _backfill_node_hour_seen_helper,
    backfill_node_position_counts as _backfill_node_position_counts_helper,
    backfill_node_saved_counts as _backfill_node_saved_counts_helper,
)
from ..history_maintenance import (
    prune_history_tables_now as _prune_history_tables_now_helper,
)
from ..history_prune import prune_history_tables as _prune_history_tables_helper
from ..history_schema import initialize_history_schema
from ..history_store_policy import HistoryStorePolicy
from ..sqlite_permissions import (
    secure_sqlite_database_path,
    secure_sqlite_sidecar_paths,
)
from ..sql_contracts import SqlConnection


def open_and_initialize_history_connection(
    *,
    db_path: str,
    retention_seconds: int,
    event_retention_seconds: int,
    rollup_retention_seconds: int,
    max_rows: int,
    event_max_rows: int,
) -> SqlConnection:
    created_database = secure_sqlite_database_path(db_path)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    _configure_history_connection(conn)

    initialize_history_schema(conn)
    prune_history_connection(
        conn,
        retention_seconds=retention_seconds,
        event_retention_seconds=event_retention_seconds,
        rollup_retention_seconds=rollup_retention_seconds,
        max_rows=max_rows,
        event_max_rows=event_max_rows,
    )
    _backfill_node_saved_counts_helper(conn)
    _backfill_node_position_counts_helper(conn)
    _backfill_node_hour_seen_helper(conn)
    _backfill_node_capabilities_helper(conn, to_int_fn=_to_int)
    conn.commit()
    secure_sqlite_sidecar_paths(db_path, created_database=created_database)
    return conn


def _configure_history_connection(conn: SqlConnection, *, read_only: bool = False) -> None:
    """Apply SQLite pragmas tuned for a fast UI-polling workload."""
    # WAL allows concurrent readers + writers (critical for /api/state + background history writes).
    conn.execute("PRAGMA journal_mode=WAL")
    # NORMAL is a good balance: faster commits than FULL while still robust.
    conn.execute("PRAGMA synchronous=NORMAL")
    # Don't fail fast if a writer is mid-commit.
    conn.execute("PRAGMA busy_timeout=5000")

    # Keep temp structures in memory (helps GROUP BY / ORDER BY workloads).
    try:
        conn.execute("PRAGMA temp_store=MEMORY")
    except Exception:
        pass

    # Slightly larger page cache for snappier reads (negative = KiB).
    try:
        conn.execute("PRAGMA cache_size=-16000")
    except Exception:
        pass

    # Ensure FK constraints if schema ever adds them.
    try:
        conn.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass

    if read_only:
        # Best-effort guardrail; supported by modern SQLite.
        try:
            conn.execute("PRAGMA query_only=ON")
        except Exception:
            pass


def open_history_read_connection(*, db_path: str) -> SqlConnection:
    """Open a secondary read-only SQLite connection.

    Using a separate connection allows true concurrent reads while the writer
    connection is committing (especially effective under WAL).
    """
    created_database = secure_sqlite_database_path(db_path)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    _configure_history_connection(conn, read_only=True)
    secure_sqlite_sidecar_paths(db_path, created_database=created_database)
    return conn


def open_and_initialize_history_connection_with_policy(
    *,
    db_path: str,
    policy: HistoryStorePolicy,
) -> SqlConnection:
    return open_and_initialize_history_connection(
        db_path=db_path,
        retention_seconds=policy.retention_seconds,
        event_retention_seconds=policy.event_retention_seconds,
        rollup_retention_seconds=policy.rollup_retention_seconds,
        max_rows=policy.max_rows,
        event_max_rows=policy.event_max_rows,
    )


def prune_history_connection(
    conn: SqlConnection,
    *,
    retention_seconds: int,
    event_retention_seconds: int,
    rollup_retention_seconds: int,
    max_rows: int,
    event_max_rows: int,
) -> None:
    _prune_history_tables_now_helper(
        conn,
        retention_seconds=retention_seconds,
        event_retention_seconds=event_retention_seconds,
        rollup_retention_seconds=rollup_retention_seconds,
        max_rows=max_rows,
        event_max_rows=event_max_rows,
        prune_history_tables_fn=_prune_history_tables_helper,
        now_unix_fn=time.time,
    )


def prune_history_connection_with_policy(
    conn: SqlConnection,
    *,
    policy: HistoryStorePolicy,
) -> None:
    prune_history_connection(
        conn,
        retention_seconds=policy.retention_seconds,
        event_retention_seconds=policy.event_retention_seconds,
        rollup_retention_seconds=policy.rollup_retention_seconds,
        max_rows=policy.max_rows,
        event_max_rows=policy.event_max_rows,
    )


def _iter_history_table_names(conn: SqlConnection) -> Iterable[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    for row in rows:
        if not row:
            continue
        name = row[0]
        if isinstance(name, str) and name:
            yield name


def reset_history_connection(conn: SqlConnection) -> int:
    """Delete all rows from all non-system history tables.

    Returns the total number of rows deleted across all tables.
    """

    deleted_total = 0
    table_names = list(_iter_history_table_names(conn))
    for table_name in table_names:
        safe_name = table_name.replace('"', '""')
        try:
            before = conn.execute(f'SELECT COUNT(*) FROM "{safe_name}"').fetchone()
            if before and isinstance(before[0], int):
                deleted_total += int(before[0])
        except Exception:
            pass
        conn.execute(f'DELETE FROM "{safe_name}"')

    # Reset AUTOINCREMENT counters if present.
    try:
        conn.execute("DELETE FROM sqlite_sequence")
    except Exception:
        pass

    # Best-effort WAL cleanup after large deletes.
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:
        pass

    conn.commit()
    return int(deleted_total)

__all__ = [
    "initialize_history_schema",
    "open_and_initialize_history_connection",
    "open_and_initialize_history_connection_with_policy",
    "open_history_read_connection",
    "prune_history_connection",
    "prune_history_connection_with_policy",
    "reset_history_connection",
]
