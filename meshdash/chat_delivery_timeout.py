import time
from collections.abc import Iterable
from typing import Callable, Optional

from .helpers import to_int
from .nodes import parse_utc_text_to_unix, utc_now


def expire_pending_deliveries(
    recent_chat: Iterable[object],
    timeout_seconds: int,
    *,
    to_int_fn: Callable[[object], Optional[int]] = to_int,
    parse_utc_text_to_unix_fn: Callable[[object], Optional[int]] = parse_utc_text_to_unix,
    now_unix_fn: Callable[[], int] = lambda: int(time.time()),
    now_text_fn: Callable[[], str] = utc_now,
) -> None:
    now_unix = now_unix_fn()
    timeout = max(1, int(timeout_seconds))
    for entry in recent_chat:
        if not isinstance(entry, dict):
            continue
        if entry.get("local_echo") is not True:
            continue
        if entry.get("ack_requested") is not True:
            continue
        if str(entry.get("delivery_state") or "") != "pending":
            continue

        pending_since = (
            to_int_fn(entry.get("delivery_updated_unix"))
            or parse_utc_text_to_unix_fn(entry.get("delivery_updated_at"))
            or parse_utc_text_to_unix_fn(entry.get("captured_at"))
            or parse_utc_text_to_unix_fn(entry.get("rx_time"))
        )
        if pending_since is None:
            pending_since = now_unix
            entry["delivery_updated_unix"] = pending_since
            entry["delivery_updated_at"] = now_text_fn()

        if now_unix - pending_since < timeout:
            continue

        entry["delivery_state"] = "timeout"
        entry["delivery_error"] = "No ACK received before timeout"
        entry["delivery_updated_unix"] = now_unix
        entry["delivery_updated_at"] = now_text_fn()
