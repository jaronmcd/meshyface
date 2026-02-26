from typing import Callable, Optional

from .helpers import to_int


def extract_routing_delivery_update(
    decoded: object,
    *,
    to_int_fn: Callable[[object], Optional[int]] = to_int,
) -> Optional[dict[str, object]]:
    if not isinstance(decoded, dict):
        return None
    portnum = str(decoded.get("portnum") or "")
    if portnum != "ROUTING_APP":
        return None
    routing = decoded.get("routing")
    if not isinstance(routing, dict):
        return None

    request_id = (
        to_int_fn(routing.get("requestId"))
        or to_int_fn(routing.get("request_id"))
        or to_int_fn(decoded.get("requestId"))
        or to_int_fn(decoded.get("request_id"))
    )
    if request_id is None or request_id <= 0:
        return None

    error_reason = str(
        routing.get("errorReason")
        or routing.get("error_reason")
        or ""
    ).strip()
    if not error_reason or error_reason.upper() == "NONE":
        return {"request_id": request_id, "state": "acked", "error": None}
    return {"request_id": request_id, "state": "nak", "error": error_reason}
