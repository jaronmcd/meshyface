import time
from typing import Callable

from .helpers import (
    extract_position_fields as _extract_position_fields,
    to_float as _to_float,
    to_int as _to_int,
)
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
from .history_env_metrics import (
    collect_environment_metric_containers as _collect_environment_metric_containers,
    format_env_metric_label as _format_env_metric_label,
    metric_float as _metric_float,
    normalize_env_metric_key as _normalize_env_metric_key,
)
from .history_time import (
    clamp_future_unix as _clamp_future_unix,
    latest_unix as _latest_unix,
)
from .history_positions import (
    insert_node_position_if_changed as _insert_node_position_if_changed,
)
from .history_rollups import bucket_minute as _bucket_minute
from .history_rollups import clean_node_id as _clean_node_id
from .sql_contracts import SqlConnection

def _is_hex_text(value: str) -> bool:
    return bool(value) and all(ch in "0123456789abcdefABCDEF" for ch in value)


def _canonical_node_id(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in {"^all", "all", "broadcast", "!ffffffff", "ffffffff", "0xffffffff", "4294967295"}:
        return "^all"
    if text.startswith("!") and len(text) == 9 and _is_hex_text(text[1:]):
        return f"!{text[1:].lower()}"
    if len(text) == 8 and _is_hex_text(text):
        return f"!{text.lower()}"

    parsed_num: int | None = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        parsed_num = int(value)
    elif text.isdigit():
        try:
            parsed_num = int(text, 10)
        except Exception:
            parsed_num = None
    if parsed_num is not None and 0 <= parsed_num <= 0xFFFFFFFF:
        return f"!{parsed_num:08x}"
    return text


def _extract_node_label(summary: dict[str, object], fallback: str) -> str:
    candidates = (
        summary.get("from_long_name"),
        summary.get("from_short_name"),
        summary.get("from_name"),
        fallback,
    )
    for candidate in candidates:
        text = str(candidate or "").strip()
        if text:
            return text
    return fallback


def _upsert_environment_metric_rollup(
    conn: SqlConnection,
    *,
    bucket_unix: int,
    node_id: str,
    node_label: str,
    metric_key: str,
    metric_label: str,
    value: float,
    sample_unix: int,
) -> None:
    row = conn.execute(
        """
        SELECT sample_count, value_sum, value_min, value_max, last_value, last_seen_unix, node_label
        FROM environment_metrics_1m
        WHERE bucket_unix = ? AND node_id = ? AND metric_key = ?
        """,
        (bucket_unix, node_id, metric_key),
    ).fetchone()
    if row is None:
        conn.execute(
            """
            INSERT INTO environment_metrics_1m(
              bucket_unix, node_id, node_label, metric_key, metric_label,
              sample_count, value_sum, value_min, value_max, last_value, last_seen_unix
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(bucket_unix),
                node_id,
                node_label,
                metric_key,
                metric_label,
                1,
                float(value),
                float(value),
                float(value),
                float(value),
                int(sample_unix),
            ),
        )
        return

    sample_count = int(row[0] or 0) + 1
    value_sum = float(row[1] or 0.0) + float(value)
    prev_min = _to_float(row[2])
    prev_max = _to_float(row[3])
    prev_last_value = _to_float(row[4])
    prev_last_seen = _to_int(row[5]) or 0
    prev_node_label = str(row[6] or "").strip()

    value_min = float(value) if prev_min is None else min(float(prev_min), float(value))
    value_max = float(value) if prev_max is None else max(float(prev_max), float(value))

    if int(sample_unix) >= prev_last_seen or prev_last_value is None:
        last_value = float(value)
    else:
        last_value = float(prev_last_value)
    last_seen_unix = max(prev_last_seen, int(sample_unix))
    merged_node_label = node_label if node_label else prev_node_label

    conn.execute(
        """
        UPDATE environment_metrics_1m
        SET node_label = ?,
            metric_label = ?,
            sample_count = ?,
            value_sum = ?,
            value_min = ?,
            value_max = ?,
            last_value = ?,
            last_seen_unix = ?
        WHERE bucket_unix = ? AND node_id = ? AND metric_key = ?
        """,
        (
            merged_node_label,
            metric_label,
            int(sample_count),
            float(value_sum),
            float(value_min),
            float(value_max),
            float(last_value),
            int(last_seen_unix),
            int(bucket_unix),
            node_id,
            metric_key,
        ),
    )


def _save_environment_metric_rollups(
    conn: SqlConnection,
    *,
    summary: dict[str, object],
    packet: dict[str, object] | None,
    now_unix_fn: Callable[[], float],
    custom_telemetry_rules: object = None,
) -> None:
    if not isinstance(packet, dict):
        return
    decoded = packet.get("decoded")
    if not isinstance(decoded, dict):
        return
    containers = _collect_environment_metric_containers(
        decoded,
        summary=summary,
        packet=packet,
        custom_rules=custom_telemetry_rules,
    )
    if not containers:
        return

    node_id = _canonical_node_id(
        summary.get("from")
        or summary.get("from_id")
        or summary.get("from_num")
        or packet.get("fromId")
        or packet.get("from_id")
        or packet.get("from")
    )
    node_id = _clean_node_id(node_id)
    if not node_id:
        return
    node_label = _extract_node_label(summary, node_id)
    telemetry = decoded.get("telemetry")
    if not isinstance(telemetry, dict):
        telemetry = {}
    now_unix = int(now_unix_fn())
    receive_unix = _latest_unix(
        summary.get("rx_time_unix"),
        summary.get("time"),
        summary.get("captured_at_unix"),
        packet.get("rxTime"),
        packet.get("rx_time"),
    )
    sample_unix = _latest_unix(
        receive_unix,
        telemetry.get("time"),
    )
    sample_unix = _clamp_future_unix(
        sample_unix,
        now_unix=now_unix,
        fallback_unix=receive_unix,
    )
    bucket_unix = _bucket_minute(sample_unix)

    for container in containers:
        for raw_key, raw_value in container.items():
            metric_key = _normalize_env_metric_key(raw_key)
            if not metric_key:
                continue
            metric_value = _metric_float(raw_value)
            if metric_value is None:
                continue
            _upsert_environment_metric_rollup(
                conn,
                bucket_unix=bucket_unix,
                node_id=node_id,
                node_label=node_label,
                metric_key=metric_key,
                metric_label=_format_env_metric_label(raw_key),
                value=metric_value,
                sample_unix=sample_unix,
            )


def save_environment_metric_rollups(
    conn: SqlConnection,
    *,
    summary: dict[str, object],
    packet: dict[str, object] | None,
    now_unix_fn: Callable[[], float] = time.time,
    custom_telemetry_rules: object = None,
) -> None:
    _save_environment_metric_rollups(
        conn,
        summary=summary,
        packet=packet,
        now_unix_fn=now_unix_fn,
        custom_telemetry_rules=custom_telemetry_rules,
    )


def save_packet_event_and_rollups(
    conn: SqlConnection,
    summary: dict[str, object],
    *,
    packet: dict[str, object] | None = None,
    now_unix_fn: Callable[[], float] = time.time,
    custom_telemetry_rules: object = None,
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
    _save_environment_metric_rollups(
        conn,
        summary=summary,
        packet=packet,
        now_unix_fn=now_unix_fn,
        custom_telemetry_rules=custom_telemetry_rules,
    )
