import time
from typing import Callable

from .sql_contracts import SqlConnection


def prune_history_tables_now(
    conn: SqlConnection,
    *,
    retention_seconds: int,
    event_retention_seconds: int,
    rollup_retention_seconds: int,
    max_rows: int,
    event_max_rows: int,
    prune_history_tables_fn: Callable[..., None],
    now_unix_fn: Callable[[], float] = time.time,
) -> None:
    prune_history_tables_fn(
        conn,
        now_unix=int(now_unix_fn()),
        retention_seconds=retention_seconds,
        event_retention_seconds=event_retention_seconds,
        rollup_retention_seconds=rollup_retention_seconds,
        max_rows=max_rows,
        event_max_rows=event_max_rows,
    )


def next_prune_counter(
    writes_since_prune: int,
    *,
    prune_every: int = 50,
) -> tuple[int, bool]:
    next_count = int(writes_since_prune) + 1
    if next_count < int(prune_every):
        return next_count, False
    return 0, True
