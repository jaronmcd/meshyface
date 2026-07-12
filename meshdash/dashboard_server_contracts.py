from dataclasses import dataclass
from typing import Protocol

from .dashboard_args_contracts import DashboardArgs
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


class DashboardHttpServer(Protocol):
    server_address: tuple[object, object]


@dataclass(frozen=True)
class DashboardServerDependencies:
    args: DashboardArgs
    revision_info: RevisionInfo
    history_enabled: bool
    state_fn: StateFn
    node_history_fn: NodeHistoryFn
    summary_metrics_fn: SummaryMetricsHistoryFn
    send_chat_fn: SendChatFn
    render_html_fn: RenderHtmlFn
    make_http_handler_fn: MakeHttpHandlerFn
    threading_http_server_cls: ThreadingHttpServerCls
