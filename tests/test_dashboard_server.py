import argparse

from meshdash.dashboard_server import (
    DashboardServerParts,
    build_dashboard_server,
    build_dashboard_server_with_dependencies,
)
from meshdash.dashboard_server_contracts import DashboardServerDependencies
from meshdash.revision import RevisionInfo


class _FakeServer:
    def __init__(self, addr, handler_cls):
        self.addr = addr
        self.handler_cls = handler_cls
        self.server_address = ("127.0.0.1", 8877)


def test_build_dashboard_server_renders_handler_and_binds_server():
    args = argparse.Namespace(
        refresh_ms=3000,
        packet_limit=250,
        show_secrets=False,
        history_max_rows=5000,
        history_retention_days=7,
        node_history_hours=72,
        node_history_max_points=1440,
        http_host="0.0.0.0",
        http_port=8877,
    )
    observed = {}

    def _render_html(**kwargs):
        observed["render"] = kwargs
        return "<html></html>"

    def _make_http_handler(html_text, state_fn, **kwargs):
        observed["handler"] = {
            "html_text": html_text,
            "state_fn": state_fn,
            **kwargs,
        }
        return object()

    parts = build_dashboard_server(
        args=args,
        revision_info=RevisionInfo(version="0.1.0", commit="abc", label="rev-label", title="rev-title"),
        history_enabled=True,
        state_fn=lambda: {"ok": True},
        node_history_fn=lambda *_a, **_k: {"history": True},
        online_activity_fn=lambda *_a, **_k: {"online": True},
        summary_metrics_fn=lambda *_a, **_k: {"summary": True},
        send_chat_fn=lambda **_k: {"send": True},
        render_html_fn=_render_html,
        make_http_handler_fn=_make_http_handler,
        threading_http_server_cls=_FakeServer,
    )

    assert isinstance(parts, DashboardServerParts)
    assert parts.html == "<html></html>"
    assert isinstance(parts.server, _FakeServer)
    assert parts.bound_host == "127.0.0.1"
    assert parts.bound_port == 8877
    assert observed["render"]["revision_label"] == "rev-label"
    assert observed["render"]["history_enabled"] is True
    assert observed["handler"]["html_text"] == "<html></html>"
    assert callable(observed["handler"]["state_fn"])


def test_build_dashboard_server_with_dependencies_renders_handler_and_binds_server():
    args = argparse.Namespace(
        refresh_ms=3000,
        packet_limit=250,
        show_secrets=False,
        history_max_rows=5000,
        history_retention_days=7,
        node_history_hours=72,
        node_history_max_points=1440,
        http_host="0.0.0.0",
        http_port=8877,
    )
    observed = {}

    def _render_html(**kwargs):
        observed["render"] = kwargs
        return "<html></html>"

    def _make_http_handler(html_text, state_fn, **kwargs):
        observed["handler"] = {
            "html_text": html_text,
            "state_fn": state_fn,
            **kwargs,
        }
        return object()

    dependencies = DashboardServerDependencies(
        args=args,
        revision_info=RevisionInfo(version="0.1.0", commit="abc", label="rev-label", title="rev-title"),
        history_enabled=True,
        state_fn=lambda: {"ok": True},
        node_history_fn=lambda *_a, **_k: {"history": True},
        online_activity_fn=lambda *_a, **_k: {"online": True},
        summary_metrics_fn=lambda *_a, **_k: {"summary": True},
        send_chat_fn=lambda **_k: {"send": True},
        render_html_fn=_render_html,
        make_http_handler_fn=_make_http_handler,
        threading_http_server_cls=_FakeServer,
    )

    parts = build_dashboard_server_with_dependencies(dependencies=dependencies)

    assert isinstance(parts, DashboardServerParts)
    assert parts.html == "<html></html>"
    assert isinstance(parts.server, _FakeServer)
    assert parts.bound_host == "127.0.0.1"
    assert parts.bound_port == 8877
    assert observed["render"]["revision_label"] == "rev-label"
    assert observed["render"]["history_enabled"] is True
    assert observed["handler"]["html_text"] == "<html></html>"
    assert callable(observed["handler"]["state_fn"])
