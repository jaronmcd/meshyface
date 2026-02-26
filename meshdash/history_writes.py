import time
from typing import Callable

from .helpers import extract_position_fields as _extract_position_fields
from .history_capability_writes import (
    upsert_node_capability as _upsert_node_capability,
)
from .history_metric_writes import (
    upsert_link_metric as _upsert_link_metric,
    upsert_node_metric as _upsert_node_metric,
)
from .history_packet_events import (
    build_packet_event_insert_values as _build_packet_event_insert_values,
    normalize_packet_event_summary as _normalize_packet_event_summary,
)
from .history_positions import (
    insert_node_position_if_changed as _insert_node_position_if_changed,
)
from .history_rollups import bucket_minute as _bucket_minute
from .sql_contracts import SqlConnection


def save_packet_event_and_rollups(
    conn: SqlConnection,
    summary: dict[str, object],
    *,
    now_unix_fn: Callable[[], float] = time.time,
) -> None:
    normalized = _normalize_packet_event_summary(summary, now_unix_fn=now_unix_fn)
    event_unix = normalized["event_unix"]
    from_id = normalized["from_id"]
    to_id = normalized["to_id"]
    rx_snr = normalized["rx_snr"]
    rx_rssi = normalized["rx_rssi"]
    hops = normalized["hops"]
    position_data = normalized["position_data"]
    battery_level = normalized["battery_level"]

    conn.execute(
        """
        INSERT INTO packet_events(
          created_unix, from_id, to_id, portnum,
          rx_snr, rx_rssi, hops, hop_start, hop_limit,
          channel, want_ack, priority, summary_json
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        _build_packet_event_insert_values(normalized),
    )

    bucket_unix = _bucket_minute(event_unix)
    if from_id:
        _upsert_node_metric(
            conn,
            bucket_unix=bucket_unix,
            node_id=from_id,
            event_unix=event_unix,
            rx_snr=rx_snr,
            rx_rssi=rx_rssi,
            hops=hops,
        )
        _insert_node_position_if_changed(
            conn,
            node_id=from_id,
            event_unix=event_unix,
            position_data=position_data,
        )
        _upsert_node_capability(
            conn,
            node_id=from_id,
            event_unix=event_unix,
            has_position=_extract_position_fields(position_data) is not None,
            last_hops=hops,
            battery_level=battery_level,
        )
    if from_id and to_id and from_id != to_id:
        _upsert_link_metric(
            conn,
            bucket_unix=bucket_unix,
            from_id=from_id,
            to_id=to_id,
            event_unix=event_unix,
            rx_snr=rx_snr,
            rx_rssi=rx_rssi,
            hops=hops,
        )
