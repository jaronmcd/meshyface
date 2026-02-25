from typing import Any, Optional

from .helpers import to_int as _to_int
from .helpers import to_jsonable as _to_jsonable
from .runtime_types import ToIntFn, ToJsonableFn


def get_node_id_from_num(
    iface: Any,
    node_num: Any,
    *,
    broadcast_num: Optional[int],
    to_int_fn: ToIntFn = _to_int,
) -> Optional[str]:
    numeric = to_int_fn(node_num)
    if numeric is None:
        return None
    if broadcast_num is not None and numeric == broadcast_num:
        return "^all"

    nodes_by_num = getattr(iface, "nodesByNum", None) or {}
    info = nodes_by_num.get(numeric, {}) if isinstance(nodes_by_num, dict) else {}
    user = info.get("user", {}) if isinstance(info, dict) else {}
    node_id = user.get("id") if isinstance(user, dict) else None
    if node_id:
        return str(node_id)
    return f"!{numeric:08x}"


def get_local_node_num(
    iface: Any,
    *,
    to_jsonable_fn: ToJsonableFn = _to_jsonable,
    to_int_fn: ToIntFn = _to_int,
) -> Optional[int]:
    my_info = to_jsonable_fn(getattr(iface, "myInfo", None))
    if isinstance(my_info, dict):
        for key in ("my_node_num", "myNodeNum", "node_num", "nodeNum", "num"):
            value = to_int_fn(my_info.get(key))
            if value is not None:
                return value

    local = getattr(iface, "localNode", None)
    if local is not None:
        for key in ("nodeNum", "node_num", "num"):
            value = to_int_fn(getattr(local, key, None))
            if value is not None:
                return value
    return None


def get_local_node_id(
    iface: Any,
    *,
    broadcast_num: Optional[int],
    to_jsonable_fn: ToJsonableFn = _to_jsonable,
    to_int_fn: ToIntFn = _to_int,
) -> str:
    node_num = get_local_node_num(iface, to_jsonable_fn=to_jsonable_fn, to_int_fn=to_int_fn)
    if node_num is None:
        return "local"
    node_id = get_node_id_from_num(
        iface,
        node_num,
        broadcast_num=broadcast_num,
        to_int_fn=to_int_fn,
    )
    if node_id:
        return node_id
    return f"!{node_num:08x}"
