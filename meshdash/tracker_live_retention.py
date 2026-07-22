from collections.abc import Iterable, Iterator, Mapping, MutableMapping
from dataclasses import dataclass
from typing import Protocol

from .tracker_snapshot_build_contracts import EdgeKey, EdgeRow


DEFAULT_LIVE_STATE_RETENTION_SECONDS = 2 * 60 * 60
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


def _positive_unix(
    value: object,
    *,
    to_int_fn,
    parse_utc_text_to_unix_fn,
) -> int | None:
    if isinstance(value, bool):
        return None
    parsed = to_int_fn(value)
    if parsed is not None and parsed > 0:
        return int(parsed)
    parsed = parse_utc_text_to_unix_fn(value)
    if parsed is not None and parsed > 0:
        return int(parsed)
    return None


def _latest_unix_from_mapping(
    row: Mapping[str, object],
    keys: tuple[str, ...],
    *,
    to_int_fn,
    parse_utc_text_to_unix_fn,
) -> int | None:
    latest: int | None = None
    for key in keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        parsed = _positive_unix(
            value,
            to_int_fn=to_int_fn,
            parse_utc_text_to_unix_fn=parse_utc_text_to_unix_fn,
        )
        if parsed is not None and (latest is None or parsed > latest):
            latest = parsed
    return latest


def _latest_unix_from_sources(
    sources: Iterable[object],
    keys: tuple[str, ...],
    *,
    to_int_fn,
    parse_utc_text_to_unix_fn,
) -> int | None:
    latest: int | None = None
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        parsed = _latest_unix_from_mapping(
            source,
            keys,
            to_int_fn=to_int_fn,
            parse_utc_text_to_unix_fn=parse_utc_text_to_unix_fn,
        )
        if parsed is not None and (latest is None or parsed > latest):
            latest = parsed
    return latest


def _packet_observed_unix(
    entry: dict[str, object],
    *,
    to_int_fn,
    parse_utc_text_to_unix_fn,
) -> int | None:
    packet = entry.get("packet")
    decoded = packet.get("decoded") if isinstance(packet, Mapping) else None
    return _latest_unix_from_sources(
        (
            entry,
            entry.get("summary"),
            packet,
            decoded,
        ),
        (
            "rx_time_unix",
            "packet_rx_time_unix",
            "time_unix",
            "created_unix",
            "rxTime",
            "rx_time",
            "captured_at",
            "time",
        ),
        to_int_fn=to_int_fn,
        parse_utc_text_to_unix_fn=parse_utc_text_to_unix_fn,
    )


def _chat_observed_unix(
    entry: dict[str, object],
    *,
    to_int_fn,
    parse_utc_text_to_unix_fn,
) -> int | None:
    return _latest_unix_from_sources(
        (entry,),
        (
            "rx_time_unix",
            "time_unix",
            "delivery_updated_unix",
            "deliveryUpdatedUnix",
            "created_unix",
            "rxTime",
            "rx_time",
            "captured_at",
            "time",
        ),
        to_int_fn=to_int_fn,
        parse_utc_text_to_unix_fn=parse_utc_text_to_unix_fn,
    )


def _edge_observed_unix(
    edge: EdgeRow,
    *,
    to_int_fn,
    parse_utc_text_to_unix_fn,
) -> int | None:
    return _latest_unix_from_mapping(
        edge,
        (
            "last_rx_time",
            "lastRxTime",
            "rx_time",
            "rxTime",
            "updated_unix",
            "time_unix",
        ),
        to_int_fn=to_int_fn,
        parse_utc_text_to_unix_fn=parse_utc_text_to_unix_fn,
    )


def _purge_buffer(
    buffer: LiveRowBuffer,
    *,
    cutoff_unix: int,
    observed_unix_fn,
) -> int:
    retained: list[dict[str, object]] = []
    removed = 0
    for entry in buffer:
        observed_unix = observed_unix_fn(entry)
        if observed_unix is not None and observed_unix < cutoff_unix:
            removed += 1
            continue
        retained.append(entry)
    if removed <= 0:
        return 0
    buffer.clear()
    buffer.extend(retained)
    return removed


def _purge_edge_map(
    edges: MutableMapping[EdgeKey, EdgeRow],
    *,
    cutoff_unix: int,
    to_int_fn,
    parse_utc_text_to_unix_fn,
) -> int:
    expired_keys: list[EdgeKey] = []
    for key, edge in edges.items():
        if not isinstance(edge, Mapping):
            continue
        observed_unix = _edge_observed_unix(
            edge,
            to_int_fn=to_int_fn,
            parse_utc_text_to_unix_fn=parse_utc_text_to_unix_fn,
        )
        if observed_unix is not None and observed_unix < cutoff_unix:
            expired_keys.append(key)
    for key in expired_keys:
        edges.pop(key, None)
    return len(expired_keys)


def purge_live_state(
    *,
    recent_packets: LiveRowBuffer,
    recent_chat: LiveRowBuffer,
    edges: MutableMapping[EdgeKey, EdgeRow],
    historical_edges: MutableMapping[EdgeKey, EdgeRow],
    now_unix: int,
    retention_seconds: int = DEFAULT_LIVE_STATE_RETENTION_SECONDS,
    to_int_fn,
    parse_utc_text_to_unix_fn,
) -> LiveStatePurgeResult:
    if retention_seconds <= 0 or now_unix <= 0:
        return LiveStatePurgeResult()
    cutoff_unix = int(now_unix) - int(retention_seconds)
    return LiveStatePurgeResult(
        recent_packets=_purge_buffer(
            recent_packets,
            cutoff_unix=cutoff_unix,
            observed_unix_fn=lambda entry: _packet_observed_unix(
                entry,
                to_int_fn=to_int_fn,
                parse_utc_text_to_unix_fn=parse_utc_text_to_unix_fn,
            ),
        ),
        recent_chat=_purge_buffer(
            recent_chat,
            cutoff_unix=cutoff_unix,
            observed_unix_fn=lambda entry: _chat_observed_unix(
                entry,
                to_int_fn=to_int_fn,
                parse_utc_text_to_unix_fn=parse_utc_text_to_unix_fn,
            ),
        ),
        edges=_purge_edge_map(
            edges,
            cutoff_unix=cutoff_unix,
            to_int_fn=to_int_fn,
            parse_utc_text_to_unix_fn=parse_utc_text_to_unix_fn,
        ),
        historical_edges=_purge_edge_map(
            historical_edges,
            cutoff_unix=cutoff_unix,
            to_int_fn=to_int_fn,
            parse_utc_text_to_unix_fn=parse_utc_text_to_unix_fn,
        ),
    )
