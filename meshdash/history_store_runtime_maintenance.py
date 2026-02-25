from typing import Any, Callable

from .history_maintenance import (
    next_prune_counter as _next_prune_counter_helper,
)
from .history_store_connection import (
    prune_history_connection as _prune_history_connection_helper,
)
from .history_store_policy import (
    policy_from_store_fields as _policy_from_store_fields_helper,
)


def close_history_store(store: Any) -> None:
    with store._lock:
        store._conn.close()


def prune_history_store_unlocked(
    store: Any,
    *,
    prune_history_connection_fn: Callable[..., None] = _prune_history_connection_helper,
) -> None:
    policy = getattr(store, "_policy", None)
    if policy is None:
        policy = _policy_from_store_fields_helper(store)
    prune_history_connection_fn(
        store._conn,
        retention_seconds=policy.retention_seconds,
        event_retention_seconds=policy.event_retention_seconds,
        rollup_retention_seconds=policy.rollup_retention_seconds,
        max_rows=policy.max_rows,
        event_max_rows=policy.event_max_rows,
    )


def maybe_prune_history_store_unlocked(
    store: Any,
    *,
    next_prune_counter_fn: Callable[[int], tuple[int, bool]] = _next_prune_counter_helper,
    prune_unlocked_fn: Callable[[], None],
) -> None:
    store._writes_since_prune, should_prune = next_prune_counter_fn(store._writes_since_prune)
    if not should_prune:
        return
    prune_unlocked_fn()
