from typing import Callable, Optional, Sequence

from .history_metric_upsert_queries import (
    select_existing_row as _select_existing_row_helper,
)
from .history_metric_upsert_writes import (
    insert_metric_row as _insert_metric_row_helper,
)
from .history_metric_upsert_writes import (
    update_metric_row as _update_metric_row_helper,
)
from .sql_contracts import SqlConnection


def upsert_metric_rollup_row(
    conn: SqlConnection,
    *,
    table_name: str,
    key_fields: Sequence[str],
    key_values: Sequence[object],
    bucket_unix: int,
    event_unix: int,
    rx_snr: Optional[float],
    rx_rssi: Optional[float],
    hops: Optional[int],
    build_metric_rollup_values_fn: Callable[..., dict[str, object]],
    merge_metric_rollup_row_fn: Callable[..., dict[str, object]],
) -> None:
    row = _select_existing_row_helper(
        conn,
        table_name=table_name,
        key_fields=key_fields,
        bucket_unix=bucket_unix,
        key_values=key_values,
    )

    if row is None:
        rolled = build_metric_rollup_values_fn(
            event_unix=event_unix,
            rx_snr=rx_snr,
            rx_rssi=rx_rssi,
            hops=hops,
        )
        _insert_metric_row_helper(
            conn,
            table_name=table_name,
            key_fields=key_fields,
            bucket_unix=bucket_unix,
            key_values=key_values,
            rolled=rolled,
        )
        return

    merged = merge_metric_rollup_row_fn(
        row=row,
        event_unix=event_unix,
        rx_snr=rx_snr,
        rx_rssi=rx_rssi,
        hops=hops,
    )
    _update_metric_row_helper(
        conn,
        table_name=table_name,
        key_fields=key_fields,
        bucket_unix=bucket_unix,
        key_values=key_values,
        merged=merged,
    )
