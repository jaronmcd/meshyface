from .history_maintenance import (
    next_prune_counter as _next_prune_counter_helper,
)
from .history.db import (
    prune_history_connection as _prune_history_connection_helper,
    prune_history_connection_with_policy as _prune_history_connection_with_policy_helper,
    reset_history_connection as _reset_history_connection_helper,
)
from .history_store_runtime_contracts import (
    HistoryStoreRuntimeState,
    NextPruneCounterFn,
    PruneUnlockedFn,
    PruneHistoryConnectionLegacyFn,
    PruneHistoryConnectionWithPolicyFn,
)
from .history_store_policy import (
    policy_from_store_fields as _policy_from_store_fields_helper,
)


def close_history_store(store: HistoryStoreRuntimeState) -> None:
    with store._lock:
        store._conn.close()
    raw_conn = getattr(store, "_raw_packet_conn", None)
    if raw_conn is not None:
        raw_lock = getattr(store, "_raw_packet_lock", None) or getattr(store, "_lock", None)
        if raw_lock is None:
            try:
                raw_conn.close()
            except Exception:
                pass
        else:
            with raw_lock:
                try:
                    raw_conn.close()
                except Exception:
                    pass
    read_conn = getattr(store, "_read_conn", None)
    if read_conn is None:
        return
    if read_conn is getattr(store, "_conn", None):
        return
    read_lock = getattr(store, "_read_lock", None) or getattr(store, "_lock", None)
    if read_lock is None:
        # Last resort.
        read_conn.close()
        return
    with read_lock:
        read_conn.close()


def prune_history_store_unlocked(
    store: HistoryStoreRuntimeState,
    *,
    prune_history_connection_with_policy_fn: PruneHistoryConnectionWithPolicyFn = _prune_history_connection_with_policy_helper,
    prune_history_connection_fn: PruneHistoryConnectionLegacyFn = _prune_history_connection_helper,
) -> None:
    policy = getattr(store, "_policy", None)
    if policy is None:
        policy = _policy_from_store_fields_helper(store)
    if (
        prune_history_connection_with_policy_fn is _prune_history_connection_with_policy_helper
        and prune_history_connection_fn is not _prune_history_connection_helper
    ):
        # Backward compatibility for callers/tests still injecting the scalar signature.
        prune_history_connection_fn(
            store._conn,
            retention_seconds=policy.retention_seconds,
            event_retention_seconds=policy.event_retention_seconds,
            rollup_retention_seconds=policy.rollup_retention_seconds,
            max_rows=policy.max_rows,
            event_max_rows=policy.event_max_rows,
        )
    else:
        prune_history_connection_with_policy_fn(
            store._conn,
            policy=policy,
        )


def maybe_prune_history_store_unlocked(
    store: HistoryStoreRuntimeState,
    *,
    next_prune_counter_fn: NextPruneCounterFn = _next_prune_counter_helper,
    prune_unlocked_fn: PruneUnlockedFn,
) -> None:
    store._writes_since_prune, should_prune = next_prune_counter_fn(store._writes_since_prune)
    if not should_prune:
        return
    prune_unlocked_fn()


def reset_history_store(store: HistoryStoreRuntimeState) -> int:
    with store._lock:
        deleted = _reset_history_connection_helper(store._conn)
        setattr(store, "_last_local_telemetry_sample_unix", 0)
        setattr(store, "_custom_telemetry_rules", [])
        setattr(store, "_custom_telemetry_updated_unix", 0)
        setattr(
            store,
            "_bot_runtime_settings",
            {
                "zork_enabled": False,
                "ping_enabled": False,
                "ping_message_only": False,
            },
        )
        setattr(store, "_bot_runtime_settings_updated_unix", 0)

    # Refresh read connection snapshots to avoid stale WAL readers.
    read_conn = getattr(store, "_read_conn", None)
    if read_conn is None or read_conn is getattr(store, "_conn", None):
        return int(deleted)

    read_lock = getattr(store, "_read_lock", None) or getattr(store, "_lock", None)
    if read_lock is None:
        return int(deleted)
    with read_lock:
        try:
            read_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            pass
    return int(deleted)
