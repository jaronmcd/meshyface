import threading
from typing import Callable

from .history_store_connection import (
    open_and_initialize_history_connection as _open_and_initialize_history_connection_helper,
    open_and_initialize_history_connection_with_policy as _open_and_initialize_history_connection_with_policy_helper,
)
from .history_store_runtime_contracts import (
    BuildHistoryStorePolicyFn,
    HistoryStoreLock,
    HistoryStoreRuntimeState,
    OpenHistoryConnectionLegacyFn,
    OpenHistoryConnectionWithPolicyFn,
)
from .history_store_policy import (
    build_history_store_policy as _build_history_store_policy_helper,
)


def initialize_history_store_runtime(
    store: HistoryStoreRuntimeState,
    *,
    db_path: str,
    max_rows: int,
    retention_days: int,
    event_max_rows: int,
    event_retention_days: int,
    rollup_retention_days: int,
    lock_factory: Callable[[], HistoryStoreLock] = threading.Lock,
    build_history_store_policy_fn: BuildHistoryStorePolicyFn = _build_history_store_policy_helper,
    open_and_initialize_history_connection_with_policy_fn: OpenHistoryConnectionWithPolicyFn = _open_and_initialize_history_connection_with_policy_helper,
    open_and_initialize_history_connection_fn: OpenHistoryConnectionLegacyFn = _open_and_initialize_history_connection_helper,
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
    if (
        open_and_initialize_history_connection_with_policy_fn
        is _open_and_initialize_history_connection_with_policy_helper
        and open_and_initialize_history_connection_fn
        is not _open_and_initialize_history_connection_helper
    ):
        # Backward compatibility for callers/tests still injecting the scalar signature.
        store._conn = open_and_initialize_history_connection_fn(
            db_path=store.db_path,
            retention_seconds=policy.retention_seconds,
            event_retention_seconds=policy.event_retention_seconds,
            rollup_retention_seconds=policy.rollup_retention_seconds,
            max_rows=policy.max_rows,
            event_max_rows=policy.event_max_rows,
        )
    else:
        store._conn = open_and_initialize_history_connection_with_policy_fn(
            db_path=store.db_path,
            policy=policy,
        )
