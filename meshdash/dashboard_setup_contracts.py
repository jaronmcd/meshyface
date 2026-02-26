from typing import Protocol


class HistoryStoreLike(Protocol):
    def close(self) -> None:
        ...


class HistoryStoreFactory(Protocol):
    def __call__(
        self,
        *,
        db_path: str,
        max_rows: int,
        retention_days: int,
        event_max_rows: int,
        event_retention_days: int,
        rollup_retention_days: int,
    ) -> HistoryStoreLike:
        ...


class DashboardTrackerLike(Protocol):
    def on_receive(self, packet: object, interface: object) -> object:
        ...

    def has_recent_packets(self) -> bool:
        ...


class DashboardTrackerFactory(Protocol):
    def __call__(
        self,
        *,
        packet_limit: int,
        history_store: HistoryStoreLike | None,
    ) -> DashboardTrackerLike:
        ...
