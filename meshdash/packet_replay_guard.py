from collections import OrderedDict
from collections.abc import Mapping
import hashlib
import json
import time

from .helpers import to_int, to_jsonable


class PacketReplayGuard:
    """Bounded replay filter for packets that would mutate application state."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 10 * 60,
        max_entries: int = 8192,
    ) -> None:
        self._ttl_seconds = max(1.0, float(ttl_seconds))
        self._max_entries = max(1, int(max_entries))
        self._seen: OrderedDict[tuple[object, ...], float] = OrderedDict()

    @staticmethod
    def _bounded_integer(
        value: object,
        *,
        minimum: int,
        maximum: int,
    ) -> int | None:
        if isinstance(value, bool) or (
            isinstance(value, float) and not value.is_integer()
        ):
            return None
        parsed = to_int(value)
        if parsed is None or parsed < minimum or parsed > maximum:
            return None
        return int(parsed)

    @staticmethod
    def _key(packet: object) -> tuple[object, ...] | None:
        if not isinstance(packet, Mapping):
            return None
        sender_num = PacketReplayGuard._bounded_integer(
            packet.get("from"),
            minimum=0,
            maximum=0xFFFFFFFE,
        )
        packet_id = PacketReplayGuard._bounded_integer(
            packet.get("id"),
            minimum=1,
            maximum=0xFFFFFFFF,
        )
        if sender_num is None:
            return None
        channel = PacketReplayGuard._bounded_integer(
            packet.get("channel", 0),
            minimum=0,
            maximum=255,
        )
        if channel is None:
            return None
        decoded = packet.get("decoded")
        portnum = decoded.get("portnum") if isinstance(decoded, Mapping) else None
        clean_portnum = str(portnum or "")[:64]
        if packet_id is not None:
            return ("id", sender_num, packet_id, channel, clean_portnum)

        # Some adapters omit/zero packet IDs. Fingerprint a bounded canonical
        # packet view so binary, telemetry, position, and NeighborInfo updates
        # receive the same replay protection as text frames.
        canonical_view = {
            "to": packet.get("to"),
            "channel": packet.get("channel", 0),
            "decoded": decoded,
        }
        try:
            content = json.dumps(
                to_jsonable(canonical_view),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")[:4096]
        except Exception:
            content = repr(type(decoded)).encode("utf-8")[:4096]
        destination = PacketReplayGuard._bounded_integer(
            packet.get("to"),
            minimum=0,
            maximum=0xFFFFFFFF,
        )
        if destination is None:
            return None
        digest = hashlib.blake2s(content, digest_size=16).digest()
        return ("content", sender_num, destination, channel, clean_portnum, digest)

    def accept(self, packet: object, *, now_monotonic: float | None = None) -> bool:
        key = self._key(packet)
        if key is None:
            return False
        now_value = float(time.monotonic() if now_monotonic is None else now_monotonic)
        stale_before = now_value - self._ttl_seconds
        while self._seen:
            _, observed = next(iter(self._seen.items()))
            if observed >= stale_before:
                break
            self._seen.popitem(last=False)
        observed = self._seen.get(key)
        if observed is not None and observed >= stale_before:
            self._seen[key] = now_value
            self._seen.move_to_end(key)
            return False
        self._seen[key] = now_value
        self._seen.move_to_end(key)
        while len(self._seen) > self._max_entries:
            self._seen.popitem(last=False)
        return True

    def clear(self) -> None:
        self._seen.clear()

    def __len__(self) -> int:
        return len(self._seen)
