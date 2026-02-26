from typing import Optional

from .history_metric_rows import (
    build_metric_rollup_values as _build_metric_rollup_values,
    merge_metric_rollup_row as _merge_metric_rollup_row,
)
from .history_metric_upsert import (
    upsert_metric_rollup_row as _upsert_metric_rollup_row_helper,
)
from .sql_contracts import SqlConnection


def upsert_node_metric(
    conn: SqlConnection,
    *,
    bucket_unix: int,
    node_id: str,
    event_unix: int,
    rx_snr: Optional[float],
    rx_rssi: Optional[float],
    hops: Optional[int],
) -> None:
    _upsert_metric_rollup_row_helper(
        conn,
        table_name="node_metrics_1m",
        key_fields=("node_id",),
        key_values=(node_id,),
        bucket_unix=bucket_unix,
        event_unix=event_unix,
        rx_snr=rx_snr,
        rx_rssi=rx_rssi,
        hops=hops,
        build_metric_rollup_values_fn=_build_metric_rollup_values,
        merge_metric_rollup_row_fn=_merge_metric_rollup_row,
    )


def upsert_link_metric(
    conn: SqlConnection,
    *,
    bucket_unix: int,
    from_id: str,
    to_id: str,
    event_unix: int,
    rx_snr: Optional[float],
    rx_rssi: Optional[float],
    hops: Optional[int],
) -> None:
    _upsert_metric_rollup_row_helper(
        conn,
        table_name="link_metrics_1m",
        key_fields=("from_id", "to_id"),
        key_values=(from_id, to_id),
        bucket_unix=bucket_unix,
        event_unix=event_unix,
        rx_snr=rx_snr,
        rx_rssi=rx_rssi,
        hops=hops,
        build_metric_rollup_values_fn=_build_metric_rollup_values,
        merge_metric_rollup_row_fn=_merge_metric_rollup_row,
    )
