from collections.abc import Iterable
from typing import Callable, Protocol

from .sql_contracts import SqlConnection, SqlRow, SqlRows

HistoryPayload = dict[str, object]
HistoryListPayload = list[HistoryPayload]
NodeCapabilityMap = dict[str, HistoryPayload]
HistoryRow = SqlRow
HistoryRows = SqlRows


class FetchRowsWithLimitFn(Protocol):
    def __call__(self, conn: SqlConnection, *, limit: int) -> HistoryRows: ...


class FetchRowsFn(Protocol):
    def __call__(self, conn: SqlConnection) -> HistoryRows: ...


class DecodeRowsListFn(Protocol):
    def __call__(self, rows: Iterable[HistoryRow]) -> HistoryListPayload: ...


class DecodeNodeCapabilityMapFn(Protocol):
    def __call__(self, rows: Iterable[HistoryRow]) -> NodeCapabilityMap: ...


class FetchNodeHistoryRowsFn(Protocol):
    def __call__(
        self,
        conn: SqlConnection,
        *,
        node_id: str,
        cutoff: int,
        limit: int,
    ) -> tuple[HistoryRows, HistoryRows]: ...


class BuildNodeHistoryPayloadFn(Protocol):
    def __call__(
        self,
        *,
        node_id: str,
        window_hours: int,
        metric_rows: Iterable[HistoryRow],
        position_rows: Iterable[HistoryRow],
    ) -> HistoryPayload: ...


class FetchOnlineActivityRowsFn(Protocol):
    def __call__(
        self,
        conn: SqlConnection,
        *,
        cutoff: int,
    ) -> tuple[HistoryRows, int]: ...


class BuildOnlineActivityPayloadFn(Protocol):
    def __call__(
        self,
        *,
        window_hours: int,
        hour_rows: Iterable[HistoryRow],
        distinct_nodes: int,
        timezone_label: str,
    ) -> HistoryPayload: ...


TimezoneLabelFn = Callable[[], str]
