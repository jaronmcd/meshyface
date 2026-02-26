from .helpers import to_jsonable


def collect_local_state(iface: object) -> dict[str, object]:
    local = getattr(iface, "localNode", None)
    if local is None:
        local = iface.getNode("^local")

    state: dict[str, object] = {}
    state["local_config"] = to_jsonable(getattr(local, "localConfig", None))
    state["module_config"] = to_jsonable(getattr(local, "moduleConfig", None))
    channels = getattr(local, "channels", None)
    if channels is None:
        state["channels"] = []
    else:
        state["channels"] = [to_jsonable(channel) for channel in channels]
    return state
