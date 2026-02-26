import time
from typing import Callable, Optional

from .helpers import extract_position_fields as _extract_position_fields


def extract_position(
    node_info: dict[str, object],
    *,
    extract_position_fields_fn: Callable[[object], Optional[tuple[float, float]]] = _extract_position_fields,
) -> Optional[tuple[float, float]]:
    return extract_position_fields_fn(node_info.get("position"))


def safe_nodes_items(
    iface: object,
    *,
    retries: int = 3,
    sleep_seconds: float = 0.01,
) -> list[tuple[object, object]]:
    for _ in range(max(1, int(retries))):
        try:
            return list((iface.nodesByNum or {}).items())
        except RuntimeError:
            time.sleep(sleep_seconds)
    return []
