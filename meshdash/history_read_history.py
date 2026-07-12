import time

from .history_read_contracts import (
    BuildSummaryMetricsPayloadFn,
    BuildNodeHistoryPayloadFn,
    FetchSummaryPacketTypeRowsFn,
    FetchSummaryMetricsRowsFn,
    FetchNodeHistoryRowsFn,
    HistoryPayload,
)
from .history_summary_sampling import (
    summary_metrics_bucket_seconds as _summary_metrics_bucket_seconds,
    summary_metrics_query_limit as _summary_metrics_query_limit,
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
            packet_type_rows=[],
        )

    limit = max(20, min(10000, int(max_points)))
    cutoff = int(now_unix_fn()) - (hours * 3600)
    rows, position_rows, packet_rows, packet_type_rows = fetch_node_history_rows_fn(
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
        packet_type_rows=packet_type_rows,
    )


def load_summary_metrics_history_data(
    conn: SqlConnection,
    *,
    window_hours: int,
    fetch_summary_metrics_rows_fn: FetchSummaryMetricsRowsFn,
    fetch_summary_packet_type_rows_fn: FetchSummaryPacketTypeRowsFn | None,
    build_summary_metrics_payload_fn: BuildSummaryMetricsPayloadFn,
    now_unix_fn: NowUnixFn = time.time,
    include_packet_series: bool = True,
) -> HistoryPayload:
    hours = max(1, min(24 * 365, int(window_hours)))
    cutoff = int(now_unix_fn()) - (hours * 3600)
    limit = _summary_metrics_query_limit(hours)
    rows = fetch_summary_metrics_rows_fn(
        conn,
        cutoff=cutoff,
        limit=limit,
    )
    packet_type_rows = []
    if include_packet_series and callable(fetch_summary_packet_type_rows_fn):
        packet_type_rows = fetch_summary_packet_type_rows_fn(
            conn,
            cutoff=cutoff,
        )
    return build_summary_metrics_payload_fn(
        window_hours=hours,
        rows=rows,
        packet_type_rows=packet_type_rows,
        bucket_seconds=_summary_metrics_bucket_seconds(),
    )
