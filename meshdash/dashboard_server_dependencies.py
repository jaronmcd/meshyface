from .dashboard_args_contracts import DashboardArgs
from .dashboard_server_contracts import DashboardServerDependencies
from .revision import RevisionInfo
from .runtime_types import (
    MakeHttpHandlerFn,
    NodeHistoryFn,
    SummaryMetricsHistoryFn,
    RenderHtmlFn,
    SendChatFn,
    StateFn,
    ThreadingHttpServerCls,
)


def build_dashboard_server_dependencies_from_legacy_args(
    *,
    args: DashboardArgs,
    revision_info: RevisionInfo,
    history_enabled: bool,
    state_fn: StateFn,
    node_history_fn: NodeHistoryFn,
    summary_metrics_fn: SummaryMetricsHistoryFn,
    send_chat_fn: SendChatFn,
    render_html_fn: RenderHtmlFn,
    make_http_handler_fn: MakeHttpHandlerFn,
    threading_http_server_cls: ThreadingHttpServerCls,
) -> DashboardServerDependencies:
    return DashboardServerDependencies(
        args=args,
        revision_info=revision_info,
        history_enabled=history_enabled,
        state_fn=state_fn,
        node_history_fn=node_history_fn,
        summary_metrics_fn=summary_metrics_fn,
        send_chat_fn=send_chat_fn,
        render_html_fn=render_html_fn,
        make_http_handler_fn=make_http_handler_fn,
        threading_http_server_cls=threading_http_server_cls,
    )
