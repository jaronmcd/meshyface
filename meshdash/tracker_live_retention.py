from collections.abc import Iterable, Iterator, MutableMapping
from dataclasses import dataclass
from typing import Protocol

from .tracker_snapshot_build_contracts import EdgeKey, EdgeRow


DEFAULT_MAX_RETAINED_LIVE_PACKET_ROWS = 120
DEFAULT_MAX_RETAINED_LIVE_CHAT_ROWS = 180
DEFAULT_MAX_RETAINED_LIVE_EDGE_ROWS = 256
LIVE_STATE_PURGE_INTERVAL_SECONDS = 60


class LiveRowBuffer(Protocol):
    def __iter__(self) -> Iterator[dict[str, object]]:
        ...

    def __len__(self) -> int:
        ...

    def clear(self) -> None:
        ...

    def extend(self, values: Iterable[dict[str, object]]) -> None:
        ...


@dataclass(frozen=True)
class LiveStatePurgeResult:
    recent_packets: int = 0
    recent_chat: int = 0
    edges: int = 0
    historical_edges: int = 0

    @property
    def total_removed(self) -> int:
        return self.recent_packets + self.recent_chat + self.edges + self.historical_edges

    def as_dict(self) -> dict[str, int]:
        return {
            "recent_packets": self.recent_packets,
            "recent_chat": self.recent_chat,
            "edges": self.edges,
            "historical_edges": self.historical_edges,
            "total_removed": self.total_removed,
        }


def _clean_limit(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(0, parsed)


def _purge_buffer_fifo(buffer: LiveRowBuffer, *, max_rows: int) -> int:
    rows = list(buffer)
    removed = max(0, len(rows) - _clean_limit(max_rows))
    if removed <= 0:
        return 0
    buffer.clear()
    buffer.extend(rows[removed:])
    return removed


def _purge_mapping_fifo(
    rows_by_key: MutableMapping[EdgeKey, EdgeRow],
    *,
    max_rows: int,
) -> int:
    removed = max(0, len(rows_by_key) - _clean_limit(max_rows))
    if removed <= 0:
        return 0
    for key in list(rows_by_key.keys())[:removed]:
        rows_by_key.pop(key, None)
    return removed


def purge_live_state(
    *,
    recent_packets: LiveRowBuffer,
    recent_chat: LiveRowBuffer,
    edges: MutableMapping[EdgeKey, EdgeRow],
    historical_edges: MutableMapping[EdgeKey, EdgeRow],
    max_recent_packets: int = DEFAULT_MAX_RETAINED_LIVE_PACKET_ROWS,
    max_recent_chat: int = DEFAULT_MAX_RETAINED_LIVE_CHAT_ROWS,
    max_edges: int = DEFAULT_MAX_RETAINED_LIVE_EDGE_ROWS,
    max_historical_edges: int = DEFAULT_MAX_RETAINED_LIVE_EDGE_ROWS,
) -> LiveStatePurgeResult:
    return LiveStatePurgeResult(
        recent_packets=_purge_buffer_fifo(
            recent_packets,
            max_rows=max_recent_packets,
        ),
        recent_chat=_purge_buffer_fifo(
            recent_chat,
            max_rows=max_recent_chat,
        ),
        edges=_purge_mapping_fifo(
            edges,
            max_rows=max_edges,
        ),
        historical_edges=_purge_mapping_fifo(
            historical_edges,
            max_rows=max_historical_edges,
        ),
    )
