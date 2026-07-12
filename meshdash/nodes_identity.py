from typing import Optional

from .helpers import to_int as _to_int
from .helpers import to_jsonable as _to_jsonable
from .runtime_types import ToIntFn, ToJsonableFn


def get_node_id_from_num(
    iface: object,
    node_num: object,
    *,
    broadcast_num: Optional[int],
    to_int_fn: ToIntFn = _to_int,
) -> Optional[str]:
    if isinstance(node_num, bool) or (
        isinstance(node_num, float) and not node_num.is_integer()
    ):
        return None
    numeric = to_int_fn(node_num)
    if numeric is None or numeric < 0 or numeric > 0xFFFFFFFF:
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
    iface: object,
    *,
    to_jsonable_fn: ToJsonableFn = _to_jsonable,
    to_int_fn: ToIntFn = _to_int,
) -> Optional[int]:
    my_info = to_jsonable_fn(getattr(iface, "myInfo", None))
    if isinstance(my_info, dict):
        for key in ("my_node_num", "myNodeNum", "node_num", "nodeNum", "num"):
            raw_value = my_info.get(key)
            value = (
                None
                if isinstance(raw_value, bool)
                or (isinstance(raw_value, float) and not raw_value.is_integer())
                else to_int_fn(raw_value)
            )
            if value is not None and 0 <= value <= 0xFFFFFFFF:
                return value

    local = getattr(iface, "localNode", None)
    if local is not None:
        for key in ("nodeNum", "node_num", "num"):
            raw_value = getattr(local, key, None)
            value = (
                None
                if isinstance(raw_value, bool)
                or (isinstance(raw_value, float) and not raw_value.is_integer())
                else to_int_fn(raw_value)
            )
            if value is not None and 0 <= value <= 0xFFFFFFFF:
                return value
    return None


def get_local_node_id(
    iface: object,
    *,
    broadcast_num: Optional[int],
    to_jsonable_fn: ToJsonableFn = _to_jsonable,
    to_int_fn: ToIntFn = _to_int,
) -> str:
    node_num = get_local_node_num(iface, to_jsonable_fn=to_jsonable_fn, to_int_fn=to_int_fn)
    if node_num is None:
        return "local"
    if broadcast_num is not None and node_num == broadcast_num:
        return "^all"
    # Local security identity comes from the numeric radio identity, not the
    # mutable NodeDB user record for that number.
    return f"!{node_num:08x}"
