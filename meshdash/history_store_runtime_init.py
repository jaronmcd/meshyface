import threading
from typing import Callable

from .helpers import safe_json_loads as _safe_json_loads
from .helpers import to_int as _to_int
from .history_env_metrics import (
    normalize_custom_telemetry_rules as _normalize_custom_telemetry_rules,
)
from .history.db import (
    open_and_initialize_history_connection as _open_and_initialize_history_connection_helper,
    open_and_initialize_history_connection_with_policy as _open_and_initialize_history_connection_with_policy_helper,
    open_history_read_connection as _open_history_read_connection_helper,
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
from .history_profile import (
    local_node_id_from_profiled_history_db_path as _local_node_id_from_profiled_history_db_path_helper,
)
from .history_raw_packets import (
    initialize_raw_packet_store_runtime as _initialize_raw_packet_store_runtime_helper,
)


def _load_custom_telemetry_settings_from_conn(conn: object) -> tuple[list[dict[str, object]], int]:
    try:
        row = conn.execute(
            """
            SELECT value_json, updated_unix
            FROM dashboard_settings
            WHERE key = ?
            """,
            ("custom_telemetry_rules_v1",),
        ).fetchone()
    except Exception:
        row = None
    if not row:
        return [], 0
    value_json = row[0] if len(row) > 0 else "[]"
    updated_unix = int(_to_int(row[1]) or 0) if len(row) > 1 else 0
    parsed = _safe_json_loads(value_json if isinstance(value_json, str) else "[]", [])
    rules = _normalize_custom_telemetry_rules(parsed)
    return rules, updated_unix


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
    initialize_raw_packet_store_runtime_fn: Callable[..., None] = _initialize_raw_packet_store_runtime_helper,
) -> None:
    policy = build_history_store_policy_fn(
        max_rows=max_rows,
        retention_days=retention_days,
        event_max_rows=event_max_rows,
        event_retention_days=event_retention_days,
        rollup_retention_days=rollup_retention_days,
    )
    store.db_path = db_path
    store.local_node_id = _local_node_id_from_profiled_history_db_path_helper(db_path)
    store._last_local_telemetry_sample_unix = 0
    store._policy = policy
    store.max_rows = policy.max_rows
    store.retention_seconds = policy.retention_seconds
    store.event_max_rows = policy.event_max_rows
    store.event_retention_seconds = policy.event_retention_seconds
    store.rollup_retention_seconds = policy.rollup_retention_seconds
    store._writes_since_prune = 0
    store._lock = lock_factory()
    # Read operations can happen frequently (UI polling) and should not be blocked
    # by writer commits. We'll optionally provision a dedicated read connection.
    store._read_lock = lock_factory()
    store._read_conn = None
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
    custom_rules, custom_rules_updated_unix = _load_custom_telemetry_settings_from_conn(
        store._conn
    )
    store._custom_telemetry_rules = custom_rules
    store._custom_telemetry_updated_unix = custom_rules_updated_unix
    store._bot_runtime_settings = {
        "zork_enabled": False,
        "ping_enabled": False,
        "ping_message_only": False,
    }
    store._bot_runtime_settings_updated_unix = 0
    store._meshyface_profile_processing_enabled = False
    store._meshyface_profile_processing_updated_unix = 0
    initialize_raw_packet_store_runtime_fn(
        store,
        history_db_path=store.db_path,
        lock_factory=lock_factory,
    )

    # Only create a separate read connection when we're using the default
    # connection opener *and* the DB path is file-backed. In-memory SQLite
    # databases can't be shared across multiple connections.
    if (
        store.db_path
        and str(store.db_path) not in (":memory:", "file::memory:")
        and open_and_initialize_history_connection_with_policy_fn
        is _open_and_initialize_history_connection_with_policy_helper
        and open_and_initialize_history_connection_fn
        is _open_and_initialize_history_connection_helper
    ):
        try:
            store._read_conn = _open_history_read_connection_helper(db_path=store.db_path)
        except Exception:
            store._read_conn = None
