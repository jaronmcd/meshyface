from typing import Iterable, Protocol


class TrackerSeedTarget(Protocol):
    def seed_packet(self, packet: dict[str, object], iface: object) -> None:
        ...


class SafeNodesItemsFn(Protocol):
    def __call__(
        self,
        iface: object,
        *,
        retries: int,
        sleep_seconds: float,
    ) -> Iterable[tuple[object, object]]:
        ...
