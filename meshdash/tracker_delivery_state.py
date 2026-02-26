import time
from collections.abc import Reversible
from typing import Callable, Optional

from .chat import (
    expire_pending_deliveries as _expire_pending_deliveries_helper,
    extract_routing_delivery_update as _extract_routing_delivery_update_helper,
    set_delivery_state as _set_delivery_state_helper,
)


def set_tracker_delivery_state(
    recent_chat: Reversible[object],
    *,
    message_id: object,
    state: str,
    error: Optional[str] = None,
    to_int_fn: Callable[[object], Optional[int]],
    utc_now_fn: Callable[[], str],
    now_unix_fn: Callable[[], float] = time.time,
) -> bool:
    return _set_delivery_state_helper(
        recent_chat,
        message_id=message_id,
        state=state,
        error=error,
        to_int_fn=to_int_fn,
        now_text_fn=utc_now_fn,
        now_unix_fn=lambda: int(now_unix_fn()),
    )


def extract_tracker_delivery_update(
    decoded: object,
    *,
    to_int_fn: Callable[[object], Optional[int]],
) -> Optional[dict[str, object]]:
    return _extract_routing_delivery_update_helper(decoded, to_int_fn=to_int_fn)


def expire_tracker_pending_deliveries(
    recent_chat: Reversible[object],
    *,
    timeout_seconds: int,
    to_int_fn: Callable[[object], Optional[int]],
    parse_utc_text_to_unix_fn: Callable[[object], Optional[float]],
    utc_now_fn: Callable[[], str],
    now_unix_fn: Callable[[], float] = time.time,
) -> None:
    _expire_pending_deliveries_helper(
        recent_chat,
        timeout_seconds=timeout_seconds,
        to_int_fn=to_int_fn,
        parse_utc_text_to_unix_fn=parse_utc_text_to_unix_fn,
        now_unix_fn=lambda: int(now_unix_fn()),
        now_text_fn=utc_now_fn,
    )
