import os
import sqlite3
import time

from .helpers import to_int as _to_int
from .history_backfill import backfill_node_capabilities as _backfill_node_capabilities_helper
from .history_maintenance import (
    prune_history_tables_now as _prune_history_tables_now_helper,
)
from .history_prune import prune_history_tables as _prune_history_tables_helper
from .history_schema import initialize_history_schema as _initialize_history_schema_helper
from .history_store_policy import HistoryStorePolicy
from .sql_contracts import SqlConnection


def open_and_initialize_history_connection(
    *,
    db_path: str,
    retention_seconds: int,
    event_retention_seconds: int,
    rollup_retention_seconds: int,
    max_rows: int,
    event_max_rows: int,
) -> SqlConnection:
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")

    _initialize_history_schema_helper(conn)
    prune_history_connection(
        conn,
        retention_seconds=retention_seconds,
        event_retention_seconds=event_retention_seconds,
        rollup_retention_seconds=rollup_retention_seconds,
        max_rows=max_rows,
        event_max_rows=event_max_rows,
    )
    _backfill_node_capabilities_helper(conn, to_int_fn=_to_int)
    conn.commit()
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
