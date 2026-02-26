from collections.abc import Iterable
from typing import Protocol

from .tracker_snapshot_build_contracts import EdgeKey, EdgeRow


class TrackerBootstrapHistoryStore(Protocol):
    def load_recent_packets(self, limit: int) -> Iterable[dict[str, object]]:
        ...

    def load_recent_chat(self, limit: int) -> Iterable[dict[str, object]]:
        ...

    def load_connections(self) -> Iterable[EdgeRow]:
        ...


class BuildHistoricalEdgesFn(Protocol):
    def __call__(self, connection_rows: Iterable[EdgeRow]) -> dict[EdgeKey, EdgeRow]:
        ...
