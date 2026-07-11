from typing import Protocol

from .history_store_policy import HistoryStorePolicy
from .sql_contracts import SqlConnection


class HistoryStoreLock(Protocol):
    def __enter__(self) -> object:
        ...

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        ...


class HistoryStoreReadState(Protocol):
    _lock: HistoryStoreLock
    _conn: SqlConnection


class HistoryStoreWriteState(HistoryStoreReadState, Protocol):
    def _maybe_prune_unlocked(self) -> None:
        ...


class HistoryStoreRuntimeState(HistoryStoreWriteState, Protocol):
    db_path: str
    _policy: HistoryStorePolicy | None
    max_rows: int
    retention_seconds: int
    event_max_rows: int
    event_retention_seconds: int
    rollup_retention_seconds: int
    _writes_since_prune: int
    _bbs_host_settings: dict[str, object]
    _bbs_host_settings_updated_unix: int
    _bbs_host_posts: list[dict[str, object]]
    _bbs_host_posts_updated_unix: int
    _bot_runtime_settings: dict[str, object]
    _bot_runtime_settings_updated_unix: int
    _custom_telemetry_rules: list[dict[str, object]]
    _custom_telemetry_updated_unix: int
    _meshyface_profile_processing_enabled: bool
    _meshyface_profile_processing_updated_unix: int


class BuildHistoryStorePolicyFn(Protocol):
    def __call__(
        self,
        *,
        max_rows: int,
        retention_days: int,
        event_max_rows: int,
        event_retention_days: int,
        rollup_retention_days: int,
    ) -> HistoryStorePolicy:
        ...


class OpenHistoryConnectionWithPolicyFn(Protocol):
    def __call__(
        self,
        *,
        db_path: str,
        policy: HistoryStorePolicy,
    ) -> SqlConnection:
        ...


class OpenHistoryConnectionLegacyFn(Protocol):
    def __call__(
        self,
        *,
        db_path: str,
        retention_seconds: int,
        event_retention_seconds: int,
        rollup_retention_seconds: int,
        max_rows: int,
        event_max_rows: int,
    ) -> SqlConnection:
        ...


class PruneHistoryConnectionWithPolicyFn(Protocol):
    def __call__(
        self,
        conn: SqlConnection,
        *,
        policy: HistoryStorePolicy,
    ) -> None:
        ...


class PruneHistoryConnectionLegacyFn(Protocol):
    def __call__(
        self,
        conn: SqlConnection,
        *,
        retention_seconds: int,
        event_retention_seconds: int,
        rollup_retention_seconds: int,
        max_rows: int,
        event_max_rows: int,
    ) -> None:
        ...


class NextPruneCounterFn(Protocol):
    def __call__(self, current: int) -> tuple[int, bool]:
        ...


class PruneUnlockedFn(Protocol):
    def __call__(self) -> None:
        ...
