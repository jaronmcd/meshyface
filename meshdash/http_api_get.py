from typing import Callable, Protocol
from urllib.parse import urlparse

from .api_input_history import parse_node_history_request, parse_online_activity_request
from .helpers import to_int
from .http_handler_contracts import DashboardHttpHandler
from .http_responses import write_html_response, write_json_response, write_text_response
from .http_route_contracts import (
    ApiMetricsRecorder,
    DashboardGetRouteDependencies,
    GetCustomTelemetrySettingsFn,
    GetThemeSettingsFn,
    NodeHistoryFn,
    OnlineActivityFn,
    SummaryMetricsHistoryFn,
    StateFn,
    ToIntFn,
)
from .http_routes import handle_dashboard_get
from .services import empty_node_history, empty_online_activity, empty_summary_metrics


class ParsedUrl(Protocol):
    path: str
    query: str


def build_get_route_dependencies(
    *,
    html_text: str,
    state_fn: StateFn,
    node_history_fn: NodeHistoryFn | None,
    online_activity_fn: OnlineActivityFn | None,
    default_node_history_hours: int,
    summary_metrics_fn: SummaryMetricsHistoryFn | None = None,
    get_theme_settings_fn: GetThemeSettingsFn | None = None,
    get_custom_telemetry_settings_fn: GetCustomTelemetrySettingsFn | None = None,
    private_mode: bool = False,
    api_metrics: ApiMetricsRecorder | None = None,
    to_int_fn: ToIntFn = to_int,
) -> DashboardGetRouteDependencies:
    return DashboardGetRouteDependencies(
        html_text=html_text,
        state_fn=state_fn,
        node_history_fn=node_history_fn,
        online_activity_fn=online_activity_fn,
        summary_metrics_fn=summary_metrics_fn,
        default_node_history_hours=default_node_history_hours,
        to_int_fn=to_int_fn,
        parse_node_history_request_fn=parse_node_history_request,
        parse_online_activity_request_fn=parse_online_activity_request,
        empty_node_history_fn=empty_node_history,
        empty_online_activity_fn=empty_online_activity,
        empty_summary_metrics_fn=empty_summary_metrics,
        write_html_response_fn=write_html_response,
        write_json_response_fn=write_json_response,
        write_text_response_fn=write_text_response,
        get_theme_settings_fn=get_theme_settings_fn,
        get_custom_telemetry_settings_fn=get_custom_telemetry_settings_fn,
        private_mode=bool(private_mode),
        api_metrics=api_metrics,
    )


def dispatch_get_request(
    handler: DashboardHttpHandler,
    *,
    deps: DashboardGetRouteDependencies,
    parse_url_fn: Callable[[str], ParsedUrl] = urlparse,
    handle_get_fn=handle_dashboard_get,
) -> None:
    parsed = parse_url_fn(handler.path)
    handle_get_fn(
        handler,
        path=parsed.path,
        query=parsed.query,
        deps=deps,
    )


def make_get_dispatch(
    *,
    deps: DashboardGetRouteDependencies,
):
    def _dispatch_get(handler: DashboardHttpHandler) -> None:
        dispatch_get_request(handler, deps=deps)

    return _dispatch_get
