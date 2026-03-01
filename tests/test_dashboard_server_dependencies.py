import argparse

from meshdash.dashboard_server_contracts import DashboardServerDependencies
from meshdash.dashboard_server_dependencies import (
    build_dashboard_server_dependencies_from_legacy_args,
)
from meshdash.revision import RevisionInfo


def test_build_dashboard_server_dependencies_from_legacy_args_maps_fields():
    args = argparse.Namespace(http_host="0.0.0.0", http_port=8877)
    revision = RevisionInfo(version="0.1.0", commit="abc", label="L", title="T")
    sentinel = {
        "history_enabled": True,
        "state_fn": object(),
        "node_history_fn": object(),
        "online_activity_fn": object(),
        "summary_metrics_fn": object(),
        "send_chat_fn": object(),
        "render_html_fn": object(),
        "make_http_handler_fn": object(),
        "threading_http_server_cls": object(),
    }

    deps = build_dashboard_server_dependencies_from_legacy_args(
        args=args,
        revision_info=revision,
        **sentinel,
    )

    assert isinstance(deps, DashboardServerDependencies)
    assert deps.args is args
    assert deps.revision_info is revision
    for key, value in sentinel.items():
        assert getattr(deps, key) is value
