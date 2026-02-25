import threading
from typing import Any, Callable

from .history_store_connection import (
    open_and_initialize_history_connection as _open_and_initialize_history_connection_helper,
)
from .history_store_policy import (
    build_history_store_policy as _build_history_store_policy_helper,
)


def initialize_history_store_runtime(
    store: Any,
    *,
    db_path: str,
    max_rows: int,
    retention_days: int,
    event_max_rows: int,
    event_retention_days: int,
    rollup_retention_days: int,
    lock_factory: Callable[[], Any] = threading.Lock,
    build_history_store_policy_fn: Callable[..., Any] = _build_history_store_policy_helper,
    open_and_initialize_history_connection_fn: Callable[..., Any] = _open_and_initialize_history_connection_helper,
) -> None:
    policy = build_history_store_policy_fn(
        max_rows=max_rows,
        retention_days=retention_days,
        event_max_rows=event_max_rows,
        event_retention_days=event_retention_days,
        rollup_retention_days=rollup_retention_days,
    )
    store.db_path = db_path
    store._policy = policy
    store.max_rows = policy.max_rows
    store.retention_seconds = policy.retention_seconds
    store.event_max_rows = policy.event_max_rows
    store.event_retention_seconds = policy.event_retention_seconds
    store.rollup_retention_seconds = policy.rollup_retention_seconds
    store._writes_since_prune = 0
    store._lock = lock_factory()
    store._conn = open_and_initialize_history_connection_fn(
        db_path=store.db_path,
        retention_seconds=policy.retention_seconds,
        event_retention_seconds=policy.event_retention_seconds,
        rollup_retention_seconds=policy.rollup_retention_seconds,
        max_rows=policy.max_rows,
        event_max_rows=policy.event_max_rows,
    )
