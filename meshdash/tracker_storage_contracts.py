from collections.abc import Iterable
from typing import Optional, Protocol


class RecentPacketBuffer(Protocol):
    def append(self, value: dict[str, object]) -> None:
        ...

    def extend(self, values: Iterable[dict[str, object]]) -> None:
        ...


class RecentChatBuffer(Protocol):
    def append(self, value: dict[str, object]) -> None:
        ...

    def extend(self, values: Iterable[dict[str, object]]) -> None:
        ...


class TrackerHistoryWriter(Protocol):
    def save_connection_event(
        self,
        *,
        from_id: str,
        to_id: str,
        rx_time: Optional[int],
        portnum: Optional[str],
        hops: Optional[int],
    ) -> None:
        ...

    def save_packet(self, entry: dict[str, object]) -> None:
        ...

    def save_chat(self, entry: dict[str, object]) -> None:
        ...
