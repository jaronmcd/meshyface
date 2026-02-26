from dataclasses import dataclass

from .dashboard_args_contracts import DashboardArgs
from .dashboard_server_contracts import DashboardServerDependencies
from .dashboard_server_dependencies import (
    build_dashboard_server_dependencies_from_legacy_args,
)
from .revision import RevisionInfo
from .runtime_types import (
    MakeHttpHandlerFn,
    NodeHistoryFn,
    OnlineActivityFn,
    RenderHtmlFn,
    SendChatFn,
    StateFn,
    ThreadingHttpServerCls,
)


@dataclass(frozen=True)
class DashboardServerParts:
    server: object
    html: str
    handler_cls: object
    bound_host: str
    bound_port: int


def build_dashboard_server(
    *,
    args: DashboardArgs,
    revision_info: RevisionInfo,
    history_enabled: bool,
    state_fn: StateFn,
    node_history_fn: NodeHistoryFn,
    online_activity_fn: OnlineActivityFn,
    send_chat_fn: SendChatFn,
    render_html_fn: RenderHtmlFn,
    make_http_handler_fn: MakeHttpHandlerFn,
    threading_http_server_cls: ThreadingHttpServerCls,
) -> DashboardServerParts:
    dependencies = build_dashboard_server_dependencies_from_legacy_args(
        args=args,
        revision_info=revision_info,
        history_enabled=history_enabled,
        state_fn=state_fn,
        node_history_fn=node_history_fn,
        online_activity_fn=online_activity_fn,
        send_chat_fn=send_chat_fn,
        render_html_fn=render_html_fn,
        make_http_handler_fn=make_http_handler_fn,
        threading_http_server_cls=threading_http_server_cls,
    )
    return build_dashboard_server_with_dependencies(dependencies=dependencies)


def build_dashboard_server_with_dependencies(
    *,
    dependencies: DashboardServerDependencies,
) -> DashboardServerParts:
    html = dependencies.render_html_fn(
        refresh_ms=dependencies.args.refresh_ms,
        packet_limit=dependencies.args.packet_limit,
        show_secrets=dependencies.args.show_secrets,
        history_enabled=dependencies.history_enabled,
        history_max_rows=dependencies.args.history_max_rows,
        history_retention_days=dependencies.args.history_retention_days,
        node_history_hours=dependencies.args.node_history_hours,
        node_history_max_points=dependencies.args.node_history_max_points,
        revision_label=dependencies.revision_info.label,
        revision_title=dependencies.revision_info.title,
    )
    handler_cls = dependencies.make_http_handler_fn(
        html,
        dependencies.state_fn,
        node_history_fn=dependencies.node_history_fn,
        online_activity_fn=dependencies.online_activity_fn,
        send_chat_fn=dependencies.send_chat_fn,
    )
    server = dependencies.threading_http_server_cls(
        (dependencies.args.http_host, dependencies.args.http_port),
        handler_cls,
    )
    bound_host, bound_port = server.server_address[:2]
    return DashboardServerParts(
        server=server,
        html=html,
        handler_cls=handler_cls,
        bound_host=str(bound_host),
        bound_port=int(bound_port),
    )
