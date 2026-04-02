import inspect

from meshdash import app_meta
from meshdash import dashboard_runtime_loader_contracts
from meshdash import dashboard_setup_contracts
from meshdash import history_store_runtime_contracts
from meshdash import http_handler_contracts
from meshdash import http_route_contracts
from meshdash import runtime
from meshdash import runtime_lifecycle_contracts
from meshdash import runtime_types
from meshdash import send_chat_contracts
from meshdash import sql_contracts
from meshdash import state_service_contracts
from meshdash import tracker_bootstrap_contracts
from meshdash import tracker_local_chat_contracts
from meshdash import tracker_seed_contracts
from meshdash import tracker_snapshot_build_contracts
from meshdash import tracker_storage_contracts


_MODULES = [
    app_meta,
    dashboard_runtime_loader_contracts,
    dashboard_setup_contracts,
    history_store_runtime_contracts,
    http_handler_contracts,
    http_route_contracts,
    runtime,
    runtime_lifecycle_contracts,
    runtime_types,
    send_chat_contracts,
    sql_contracts,
    state_service_contracts,
    tracker_bootstrap_contracts,
    tracker_local_chat_contracts,
    tracker_seed_contracts,
    tracker_snapshot_build_contracts,
    tracker_storage_contracts,
]


def _dummy_value(name: str):
    key = name.lower()
    if key in {"self", "cls"}:
        return object()
    if key.endswith("_fn") or key.startswith("build_") or key.startswith("parse_") or key.startswith("set_"):
        return lambda *args, **kwargs: None
    if any(token in key for token in ("count", "size", "hours", "days", "seconds", "timeout", "code", "port")):
        return 1
    if any(token in key for token in ("show", "enabled", "include", "want", "history")):
        return False
    if any(token in key for token in ("path", "id", "name", "text", "title", "label", "host", "query", "version")):
        return "x"
    if any(token in key for token in ("rows", "items", "values", "packets", "chat", "edges")):
        return []
    if any(
        token in key
        for token in ("dict", "map", "payload", "entry", "packet", "decoded", "headers", "state", "nodes", "config")
    ):
        return {}
    return object()


def _invoke_protocol_method(fn):
    sig = inspect.signature(fn)
    args = []
    kwargs = {}
    first = True
    for param in sig.parameters.values():
        if first:
            first = False
            continue
        if param.default is not inspect._empty:
            continue
        value = _dummy_value(param.name)
        if param.kind in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD):
            args.append(value)
        elif param.kind == param.KEYWORD_ONLY:
            kwargs[param.name] = value
    return fn(object(), *args, **kwargs)


def test_protocol_contract_methods_can_be_invoked():
    invoked = 0
    allowed_dunders = {"__call__", "__enter__", "__exit__", "__setitem__"}

    for module in _MODULES:
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if getattr(cls, "__module__", "") != module.__name__:
                continue
            if not getattr(cls, "_is_protocol", False):
                continue
            for method_name, method in cls.__dict__.items():
                if not inspect.isfunction(method):
                    continue
                if method_name.startswith("__") and method_name not in allowed_dunders:
                    continue
                _invoke_protocol_method(method)
                invoked += 1

    # Guard so the test fails if we accidentally stop exercising protocol stubs.
    assert invoked >= 80
