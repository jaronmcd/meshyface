from meshdash.http_api_post import (
    build_post_route_dependencies,
    dispatch_post_request,
    make_post_dispatch,
)


class _Handler:
    def __init__(self, path: str):
        self.path = path


def test_build_post_route_dependencies_sets_expected_defaults():
    send_chat_fn = lambda **_kwargs: {"ok": True}
    set_theme_preset_fn = lambda _preset_name: {"ok": True}
    play_standalone_zork_fn = lambda **_kwargs: {"ok": True}
    deps = build_post_route_dependencies(
        send_chat_fn=send_chat_fn,
        set_theme_preset_fn=set_theme_preset_fn,
        play_standalone_zork_fn=play_standalone_zork_fn,
    )

    assert deps.send_chat_fn is send_chat_fn
    assert deps.set_theme_preset_fn is set_theme_preset_fn
    assert deps.play_standalone_zork_fn is play_standalone_zork_fn
    assert callable(deps.validate_content_length_fn)
    assert callable(deps.parse_chat_send_request_fn)
    assert callable(deps.parse_theme_settings_request_fn)
    assert callable(deps.parse_custom_telemetry_settings_request_fn)
    assert callable(deps.parse_bot_settings_request_fn)
    assert callable(deps.parse_standalone_zork_request_fn)
    assert callable(deps.write_json_response_fn)


def test_dispatch_post_request_parses_and_forwards_to_route_handler():
    deps = build_post_route_dependencies(send_chat_fn=None)
    calls = {}

    class _Parsed:
        path = "/api/chat/send"

    dispatch_post_request(
        _Handler("/ignored"),
        deps=deps,
        parse_url_fn=lambda _raw: _Parsed(),
        handle_post_fn=lambda handler, *, path, deps: calls.update(
            {"handler": handler, "path": path, "deps": deps}
        ),
    )

    assert calls["path"] == "/api/chat/send"
    assert calls["deps"] is deps


def test_make_post_dispatch_uses_dispatch_helper(monkeypatch):
    deps = build_post_route_dependencies(send_chat_fn=None)
    calls = {}

    def _fake_dispatch(handler, *, deps):
        calls["handler"] = handler
        calls["deps"] = deps

    monkeypatch.setattr("meshdash.http_api_post.dispatch_post_request", _fake_dispatch)
    dispatch_fn = make_post_dispatch(deps=deps)
    handler = _Handler("/api/chat/send")
    dispatch_fn(handler)

    assert calls["handler"] is handler
    assert calls["deps"] is deps
