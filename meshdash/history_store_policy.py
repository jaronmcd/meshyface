from dataclasses import dataclass


@dataclass(frozen=True)
class HistoryStorePolicy:
    max_rows: int
    event_max_rows: int
    retention_seconds: int
    event_retention_seconds: int
    rollup_retention_seconds: int


def build_history_store_policy(
    *,
    max_rows: int,
    retention_days: int,
    event_max_rows: int,
    event_retention_days: int,
    rollup_retention_days: int,
) -> HistoryStorePolicy:
    return HistoryStorePolicy(
        max_rows=max(100, int(max_rows)),
        event_max_rows=max(1000, int(event_max_rows)),
        retention_seconds=max(0, int(retention_days)) * 86400,
        event_retention_seconds=max(0, int(event_retention_days)) * 86400,
        rollup_retention_seconds=max(0, int(rollup_retention_days)) * 86400,
    )


def policy_from_store_fields(store: object) -> HistoryStorePolicy:
    return HistoryStorePolicy(
        max_rows=int(getattr(store, "max_rows")),
        event_max_rows=int(getattr(store, "event_max_rows")),
        retention_seconds=int(getattr(store, "retention_seconds")),
        event_retention_seconds=int(getattr(store, "event_retention_seconds")),
        rollup_retention_seconds=int(getattr(store, "rollup_retention_seconds")),
    )
