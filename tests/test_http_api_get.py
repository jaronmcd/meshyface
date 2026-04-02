from meshdash.http_api_get import (
    build_get_route_dependencies,
    dispatch_get_request,
    make_get_dispatch,
)


class _Handler:
    def __init__(self, path: str):
        self.path = path


def test_build_get_route_dependencies_sets_expected_defaults():
    state_fn = lambda: {"ok": True}
    deps = build_get_route_dependencies(
        html_text="<html>ok</html>",
        state_fn=state_fn,
        node_history_fn=None,
        online_activity_fn=None,
        default_node_history_hours=72,
    )

    assert deps.html_text == "<html>ok</html>"
    assert deps.state_fn is state_fn
    assert deps.default_node_history_hours == 72
    assert deps.get_theme_settings_fn is None
    assert deps.get_custom_telemetry_settings_fn is None
    assert callable(deps.parse_node_history_request_fn)
    assert callable(deps.parse_online_activity_request_fn)
    assert callable(deps.write_html_response_fn)
    assert callable(deps.write_json_response_fn)
    assert callable(deps.write_text_response_fn)


def test_dispatch_get_request_parses_and_forwards_to_route_handler():
    deps = build_get_route_dependencies(
        html_text="<html>ok</html>",
        state_fn=lambda: {"ok": True},
        node_history_fn=None,
        online_activity_fn=None,
        default_node_history_hours=72,
    )
    calls = {}

    class _Parsed:
        path = "/api/state"
        query = "hours=6"

    dispatch_get_request(
        _Handler("/ignored"),
        deps=deps,
        parse_url_fn=lambda _raw: _Parsed(),
        handle_get_fn=lambda handler, *, path, query, deps: calls.update(
            {"handler": handler, "path": path, "query": query, "deps": deps}
        ),
    )

    assert calls["path"] == "/api/state"
    assert calls["query"] == "hours=6"
    assert calls["deps"] is deps


def test_make_get_dispatch_uses_dispatch_helper(monkeypatch):
    deps = build_get_route_dependencies(
        html_text="<html>ok</html>",
        state_fn=lambda: {"ok": True},
        node_history_fn=None,
        online_activity_fn=None,
        default_node_history_hours=72,
    )
    calls = {}

    def _fake_dispatch(handler, *, deps):
        calls["handler"] = handler
        calls["deps"] = deps

    monkeypatch.setattr("meshdash.http_api_get.dispatch_get_request", _fake_dispatch)
    dispatch_fn = make_get_dispatch(deps=deps)
    handler = _Handler("/api/state")
    dispatch_fn(handler)

    assert calls["handler"] is handler
    assert calls["deps"] is deps
