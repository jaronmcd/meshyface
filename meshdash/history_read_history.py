import time
from datetime import datetime

from .history_read_contracts import (
    BuildSummaryMetricsPayloadFn,
    BuildNodeHistoryPayloadFn,
    BuildOnlineActivityPayloadFn,
    FetchSummaryMetricsRowsFn,
    FetchNodeHistoryRowsFn,
    FetchOnlineActivityRowsFn,
    HistoryPayload,
    TimezoneLabelFn,
)
from .runtime_types import NowUnixFn
from .sql_contracts import SqlConnection


def load_node_history_data(
    conn: SqlConnection,
    *,
    node_id: str,
    window_hours: int,
    max_points: int,
    fetch_node_history_rows_fn: FetchNodeHistoryRowsFn,
    build_node_history_payload_fn: BuildNodeHistoryPayloadFn,
    now_unix_fn: NowUnixFn = time.time,
) -> HistoryPayload:
    clean_node_id = str(node_id or "").strip()
    hours = max(1, int(window_hours))
    if not clean_node_id:
        return build_node_history_payload_fn(
            node_id="",
            window_hours=hours,
            metric_rows=[],
            position_rows=[],
            packet_rows=[],
        )

    limit = max(20, min(10000, int(max_points)))
    cutoff = int(now_unix_fn()) - (hours * 3600)
    rows, position_rows, packet_rows = fetch_node_history_rows_fn(
        conn,
        node_id=clean_node_id,
        cutoff=cutoff,
        limit=limit,
    )
    return build_node_history_payload_fn(
        node_id=clean_node_id,
        window_hours=hours,
        metric_rows=rows,
        position_rows=position_rows,
        packet_rows=packet_rows,
    )


def load_online_activity_data(
    conn: SqlConnection,
    *,
    window_hours: int,
    fetch_online_activity_rows_fn: FetchOnlineActivityRowsFn,
    build_online_activity_payload_fn: BuildOnlineActivityPayloadFn,
    now_unix_fn: NowUnixFn = time.time,
    timezone_label_fn: TimezoneLabelFn = lambda: datetime.now().astimezone().tzname() or "local",
) -> HistoryPayload:
    hours = max(1, min(24 * 365, int(window_hours)))
    cutoff = int(now_unix_fn()) - (hours * 3600)
    rows, distinct_nodes = fetch_online_activity_rows_fn(
        conn,
        cutoff=cutoff,
    )
    return build_online_activity_payload_fn(
        window_hours=hours,
        hour_rows=rows,
        distinct_nodes=distinct_nodes,
        timezone_label=timezone_label_fn(),
    )


def load_summary_metrics_history_data(
    conn: SqlConnection,
    *,
    window_hours: int,
    fetch_summary_metrics_rows_fn: FetchSummaryMetricsRowsFn,
    build_summary_metrics_payload_fn: BuildSummaryMetricsPayloadFn,
    now_unix_fn: NowUnixFn = time.time,
) -> HistoryPayload:
    hours = max(1, min(24 * 365, int(window_hours)))
    cutoff = int(now_unix_fn()) - (hours * 3600)
    limit = max(60, min(24 * 365 * 60, (hours * 60) + 5))
    rows = fetch_summary_metrics_rows_fn(
        conn,
        cutoff=cutoff,
        limit=limit,
    )
    return build_summary_metrics_payload_fn(
        window_hours=hours,
        rows=rows,
    )
