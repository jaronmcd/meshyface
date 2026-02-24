from meshdash.http_handler import build_dashboard_handler_class


def test_build_dashboard_handler_class_dispatches_get_and_post():
    observed = {"get": 0, "post": 0}

    def _dispatch_get(_handler):
        observed["get"] += 1

    def _dispatch_post(_handler):
        observed["post"] += 1

    handler_cls = build_dashboard_handler_class(
        dispatch_get_fn=_dispatch_get,
        dispatch_post_fn=_dispatch_post,
    )
    handler = handler_cls.__new__(handler_cls)

    handler.do_GET()
    handler.do_POST()

    assert observed["get"] == 1
    assert observed["post"] == 1


def test_build_dashboard_handler_class_swallows_broken_pipe_errors():
    handler_cls = build_dashboard_handler_class(
        dispatch_get_fn=lambda _handler: (_ for _ in ()).throw(BrokenPipeError()),
        dispatch_post_fn=lambda _handler: (_ for _ in ()).throw(ConnectionResetError()),
    )
    handler = handler_cls.__new__(handler_cls)

    # Should not raise.
    handler.do_GET()
    handler.do_POST()
