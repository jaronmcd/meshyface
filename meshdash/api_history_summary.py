from .http_route_contracts import (
    EmptySummaryMetricsFn,
    ParseOnlineActivityRequestFn,
    SummaryMetricsHistoryFn,
    ToIntFn,
)


def build_summary_metrics_response(
    *,
    query: str,
    summary_metrics_fn: SummaryMetricsHistoryFn | None,
    default_node_history_hours: int,
    to_int_fn: ToIntFn,
    parse_online_activity_request_fn: ParseOnlineActivityRequestFn,
    empty_summary_metrics_fn: EmptySummaryMetricsFn,
) -> dict:
    query_obj = parse_online_activity_request_fn(
        query,
        to_int_fn=to_int_fn,
    )
    hours_override = query_obj.hours_override
    if summary_metrics_fn is None:
        clean_hours = (
            hours_override
            if isinstance(hours_override, int) and hours_override > 0
            else default_node_history_hours
        )
        return empty_summary_metrics_fn(clean_hours)
    return summary_metrics_fn(hours_override)
