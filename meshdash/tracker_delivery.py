from typing import Callable, Optional


def apply_routing_delivery_update(
    decoded: object,
    *,
    extract_update_fn: Callable[[object], Optional[dict[str, object]]],
    set_delivery_state_fn: Callable[[object, str, Optional[str]], bool],
) -> bool:
    delivery_update = extract_update_fn(decoded)
    if delivery_update is None:
        return False
    set_delivery_state_fn(
        delivery_update.get("request_id"),
        str(delivery_update.get("state") or "sent"),
        delivery_update.get("error"),
    )
    return True
