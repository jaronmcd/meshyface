import time

from .history_queries import (
    fetch_chat_search_rows as _fetch_chat_search_rows_helper,
    fetch_environment_metric_packet_rows as _fetch_environment_metric_packet_rows_helper,
    fetch_environment_metric_rollup_rows as _fetch_environment_metric_rollup_rows_helper,
    fetch_packet_search_rows as _fetch_packet_search_rows_helper,
    fetch_recent_packet_rows as _fetch_recent_packet_rows_helper,
)
from .history_raw_writes import (
    save_packet_record as _save_packet_record_helper,
)
from .helpers import (
    format_epoch as _format_epoch,
    safe_json_loads as _safe_json_loads,
    to_int as _to_int,
)
from .history_read_api import (
    load_recent_packets_data as _load_recent_packets_data_helper,
)
from .history_readers import (
    decode_recent_packets_rows as _decode_recent_packets_rows_helper,
)
from .history_store_runtime_contracts import (
    HistoryStoreReadState,
    HistoryStoreWriteState,
)
from .history_env_metrics import (
    collect_environment_metric_containers as _collect_environment_metric_containers,
    format_env_metric_label as _format_env_metric_label,
    metric_float as _metric_float,
    normalize_env_metric_key as _normalize_env_metric_key,
)
from .history_writes import (
    save_packet_event_and_rollups as _save_packet_event_and_rollups_helper,
)
from .history_time import (
    clamp_future_unix as _clamp_future_unix,
    latest_unix as _latest_unix,
    normalize_unix_seconds as _normalize_unix_seconds,
)

_LOCAL_NOISE_PORTS = {"ADMIN_APP"}
_LOCAL_TELEMETRY_PORT = "TELEMETRY_APP"


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


def _should_skip_local_noise_packet(
    packet_entry: dict[str, object],
    *,
    local_node_id: object,
) -> bool:
    clean_local_node_id = _canonical_node_id(local_node_id)
    if not (clean_local_node_id.startswith("!") and len(clean_local_node_id) == 9):
        return False
    summary = packet_entry.get("summary")
    if not isinstance(summary, dict):
        return False
    from_id = _canonical_node_id(
        summary.get("from")
        or summary.get("from_id")
        or summary.get("from_num")
    )
    if from_id != clean_local_node_id:
        return False
    portnum = str(summary.get("portnum") or "").strip().upper()
    return bool(portnum) and portnum in _LOCAL_NOISE_PORTS


def _local_telemetry_sample_unix(
    packet_entry: dict[str, object],
    *,
    local_node_id: object,
) -> int | None:
    clean_local_node_id = _canonical_node_id(local_node_id)
    if not (clean_local_node_id.startswith("!") and len(clean_local_node_id) == 9):
        return None
    summary = packet_entry.get("summary")
    if not isinstance(summary, dict):
        return None
    from_id = _canonical_node_id(
        summary.get("from")
        or summary.get("from_id")
        or summary.get("from_num")
    )
    if from_id != clean_local_node_id:
        return None
    portnum = str(summary.get("portnum") or "").strip().upper()
    if portnum != _LOCAL_TELEMETRY_PORT:
        return None

    packet = packet_entry.get("packet")
    decoded = packet.get("decoded") if isinstance(packet, dict) else None
    telemetry = decoded.get("telemetry") if isinstance(decoded, dict) else None
    if isinstance(telemetry, dict):
        telemetry_unix = _normalize_unix_seconds(telemetry.get("time"))
        if telemetry_unix is not None and telemetry_unix > 0:
            return telemetry_unix

    sample_unix = _latest_unix(
        summary.get("rx_time_unix"),
        summary.get("time"),
        summary.get("captured_at_unix"),
        packet.get("rxTime") if isinstance(packet, dict) else None,
        packet.get("rx_time") if isinstance(packet, dict) else None,
    )
    return sample_unix if sample_unix > 0 else None


def _should_skip_local_telemetry_duplicate(
    packet_entry: dict[str, object],
    *,
    local_node_id: object,
    last_saved_sample_unix: object,
) -> tuple[bool, int]:
    sample_unix = _local_telemetry_sample_unix(
        packet_entry,
        local_node_id=local_node_id,
    )
    if sample_unix is None or sample_unix <= 0:
        return False, 0
    last_saved_unix = _normalize_unix_seconds(last_saved_sample_unix) or 0
    if last_saved_unix > 0 and sample_unix <= last_saved_unix:
        return True, sample_unix
    return False, sample_unix


def _extract_node_label(summary: dict[str, object], packet: dict[str, object], fallback: str) -> str:
    decoded = packet.get("decoded")
    user = decoded.get("user") if isinstance(decoded, dict) else None
    candidates = (
        summary.get("from_long_name"),
        summary.get("from_short_name"),
        summary.get("from_name"),
        user.get("longName") if isinstance(user, dict) else None,
        user.get("shortName") if isinstance(user, dict) else None,
        fallback,
    )
    for candidate in candidates:
        text = str(candidate or "").strip()
        if text:
            return text
    return fallback


def _build_environment_points(
    rows: list[tuple[object, ...]],
    *,
    metric_filter: str,
    node_filter: str,
    custom_telemetry_rules: object = None,
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    points: list[dict[str, object]] = []
    metric_meta: dict[str, dict[str, object]] = {}
    node_meta: dict[str, dict[str, object]] = {}
    now_unix = int(time.time())

    for row in rows:
        packet_row_id = _to_int(row[0]) if len(row) > 0 else None
        created_unix = _to_int(row[1]) if len(row) > 1 else None
        summary_json = row[2] if len(row) > 2 else None
        packet_json = row[3] if len(row) > 3 else None

        summary = _safe_json_loads(summary_json, {})
        if not isinstance(summary, dict):
            summary = {}
        packet = _safe_json_loads(packet_json, {})
        if not isinstance(packet, dict):
            packet = {}
        decoded = packet.get("decoded")
        if not isinstance(decoded, dict):
            decoded = {}

        containers = _collect_environment_metric_containers(
            decoded,
            summary=summary,
            packet=packet,
            custom_rules=custom_telemetry_rules,
        )
        if not containers:
            continue

        node_id = _canonical_node_id(
            summary.get("from")
            or summary.get("from_id")
            or summary.get("from_num")
            or packet.get("fromId")
            or packet.get("from_id")
            or packet.get("from")
        )
        if not node_id:
            continue
        if node_filter and node_id != node_filter:
            continue
        node_label = _extract_node_label(summary, packet, node_id)

        telemetry = decoded.get("telemetry")
        if not isinstance(telemetry, dict):
            telemetry = {}
        receive_unix = _latest_unix(
            summary.get("rx_time_unix"),
            summary.get("time"),
            summary.get("captured_at_unix"),
            packet.get("rxTime"),
            packet.get("rx_time"),
            created_unix,
        )
        sample_unix = _latest_unix(receive_unix, telemetry.get("time"))
        sample_unix = _clamp_future_unix(
            sample_unix,
            now_unix=now_unix,
            fallback_unix=receive_unix,
            default_to_now=False,
        )
        if sample_unix <= 0:
            continue

        for container in containers:
            for raw_key, raw_value in container.items():
                metric_key = _normalize_env_metric_key(raw_key)
                if not metric_key:
                    continue
                if metric_filter and metric_key != metric_filter:
                    continue
                numeric_value = _metric_float(raw_value)
                if numeric_value is None:
                    continue

                point = {
                    "packet_row_id": packet_row_id,
                    "unix": sample_unix,
                    "time": _format_epoch(sample_unix) if sample_unix > 0 else "n/a",
                    "node_id": node_id,
                    "node_label": node_label,
                    "metric_key": metric_key,
                    "metric_label": _format_env_metric_label(raw_key),
                    "value": numeric_value,
                }
                points.append(point)

                metric_state = metric_meta.setdefault(
                    metric_key,
                    {
                        "key": metric_key,
                        "label": _format_env_metric_label(raw_key),
                        "count": 0,
                        "node_ids": set(),
                        "min": numeric_value,
                        "max": numeric_value,
                    },
                )
                metric_state["count"] = int(metric_state.get("count", 0)) + 1
                metric_state["node_ids"].add(node_id)
                metric_state["min"] = min(float(metric_state.get("min", numeric_value)), numeric_value)
                metric_state["max"] = max(float(metric_state.get("max", numeric_value)), numeric_value)

                node_state = node_meta.setdefault(
                    node_id,
                    {
                        "id": node_id,
                        "label": node_label,
                        "count": 0,
                        "metric_keys": set(),
                        "last_unix": sample_unix,
                    },
                )
                node_state["count"] = int(node_state.get("count", 0)) + 1
                node_state["metric_keys"].add(metric_key)
                node_state["last_unix"] = max(int(node_state.get("last_unix", 0)), sample_unix)
                if node_state.get("label") in ("", node_id):
                    node_state["label"] = node_label

    points.sort(
        key=lambda point: (
            int(_to_int(point.get("unix")) or 0),
            str(point.get("node_id") or ""),
            str(point.get("metric_key") or ""),
        )
    )
    return points, metric_meta, node_meta


def _build_environment_points_from_rollups(
    rows: list[tuple[object, ...]],
    *,
    metric_filter: str,
    node_filter: str,
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    points: list[dict[str, object]] = []
    metric_meta: dict[str, dict[str, object]] = {}
    node_meta: dict[str, dict[str, object]] = {}
    now_unix = int(time.time())

    for row in rows:
        bucket_unix = _to_int(row[0]) if len(row) > 0 else None
        node_id = _canonical_node_id(row[1] if len(row) > 1 else None)
        node_label = str(row[2] if len(row) > 2 and row[2] is not None else "").strip()
        metric_key = _normalize_env_metric_key(row[3] if len(row) > 3 else "")
        metric_label = _format_env_metric_label(row[4] if len(row) > 4 else metric_key)
        sample_count = max(1, int(_to_int(row[5]) or 0))
        value_sum = _metric_float(row[6] if len(row) > 6 else None)
        value_min = _metric_float(row[7] if len(row) > 7 else None)
        value_max = _metric_float(row[8] if len(row) > 8 else None)
        last_value = _metric_float(row[9] if len(row) > 9 else None)
        last_seen_unix = _to_int(row[10]) if len(row) > 10 else None

        if not node_id or not metric_key:
            continue
        if node_filter and node_id != node_filter:
            continue
        if metric_filter and metric_key != metric_filter:
            continue
        if value_sum is None and last_value is None:
            continue

        value = (
            float(value_sum) / float(sample_count)
            if value_sum is not None and sample_count > 0
            else float(last_value or 0.0)
        )
        point_unix = _clamp_future_unix(
            int(last_seen_unix or bucket_unix or 0),
            now_unix=now_unix,
            fallback_unix=bucket_unix,
            default_to_now=False,
        )
        if point_unix <= 0:
            continue

        clean_node_label = node_label or node_id
        point = {
            "packet_row_id": None,
            "unix": point_unix,
            "time": _format_epoch(point_unix),
            "node_id": node_id,
            "node_label": clean_node_label,
            "metric_key": metric_key,
            "metric_label": metric_label,
            "value": value,
            "sample_count": sample_count,
            "value_min": value_min,
            "value_max": value_max,
            "last_value": last_value,
        }
        points.append(point)

        metric_state = metric_meta.setdefault(
            metric_key,
            {
                "key": metric_key,
                "label": metric_label,
                "count": 0,
                "node_ids": set(),
                "min": value,
                "max": value,
            },
        )
        metric_state["count"] = int(metric_state.get("count", 0)) + sample_count
        metric_state["node_ids"].add(node_id)
        metric_state["min"] = min(float(metric_state.get("min", value)), value)
        metric_state["max"] = max(float(metric_state.get("max", value)), value)

        node_state = node_meta.setdefault(
            node_id,
            {
                "id": node_id,
                "label": clean_node_label,
                "count": 0,
                "metric_keys": set(),
                "last_unix": point_unix,
            },
        )
        node_state["count"] = int(node_state.get("count", 0)) + sample_count
        node_state["metric_keys"].add(metric_key)
        node_state["last_unix"] = max(int(node_state.get("last_unix", 0)), point_unix)
        if node_state.get("label") in ("", node_id):
            node_state["label"] = clean_node_label

    points.sort(
        key=lambda point: (
            int(_to_int(point.get("unix")) or 0),
            str(point.get("node_id") or ""),
            str(point.get("metric_key") or ""),
        )
    )
    return points, metric_meta, node_meta


def _merge_environment_meta_maps(
    base_metric_meta: dict[str, dict[str, object]],
    base_node_meta: dict[str, dict[str, object]],
    extra_metric_meta: dict[str, dict[str, object]],
    extra_node_meta: dict[str, dict[str, object]],
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    for metric_key, extra in extra_metric_meta.items():
        if metric_key not in base_metric_meta:
            cloned = dict(extra)
            cloned["node_ids"] = set(extra.get("node_ids") or [])
            base_metric_meta[metric_key] = cloned
            continue
        merged = base_metric_meta[metric_key]
        merged["count"] = int(merged.get("count", 0)) + int(extra.get("count", 0))
        merged_node_ids = set(merged.get("node_ids") or [])
        merged_node_ids |= set(extra.get("node_ids") or [])
        merged["node_ids"] = merged_node_ids
        merged["min"] = min(
            float(merged.get("min", extra.get("min", 0.0)) or 0.0),
            float(extra.get("min", merged.get("min", 0.0)) or 0.0),
        )
        merged["max"] = max(
            float(merged.get("max", extra.get("max", 0.0)) or 0.0),
            float(extra.get("max", merged.get("max", 0.0)) or 0.0),
        )

    for node_id, extra in extra_node_meta.items():
        if node_id not in base_node_meta:
            cloned = dict(extra)
            cloned["metric_keys"] = set(extra.get("metric_keys") or [])
            base_node_meta[node_id] = cloned
            continue
        merged = base_node_meta[node_id]
        merged["count"] = int(merged.get("count", 0)) + int(extra.get("count", 0))
        merged_metric_keys = set(merged.get("metric_keys") or [])
        merged_metric_keys |= set(extra.get("metric_keys") or [])
        merged["metric_keys"] = merged_metric_keys
        merged["last_unix"] = max(
            int(_to_int(merged.get("last_unix")) or 0),
            int(_to_int(extra.get("last_unix")) or 0),
        )
        merged_label = str(merged.get("label") or "").strip()
        if merged_label in ("", node_id):
            merged["label"] = str(extra.get("label") or node_id)

    return base_metric_meta, base_node_meta


def _derive_environment_meta_from_points(
    points: list[dict[str, object]],
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    metric_meta: dict[str, dict[str, object]] = {}
    node_meta: dict[str, dict[str, object]] = {}
    for point in points:
        metric_key = _normalize_env_metric_key(point.get("metric_key") or "")
        node_id = _canonical_node_id(point.get("node_id"))
        if not metric_key or not node_id:
            continue
        metric_label = _format_env_metric_label(point.get("metric_label") or metric_key)
        node_label = str(point.get("node_label") or node_id)
        value = _metric_float(point.get("value"))
        if value is None:
            continue
        sample_count = max(1, int(_to_int(point.get("sample_count")) or 1))
        unix = int(_to_int(point.get("unix")) or 0)

        metric_state = metric_meta.setdefault(
            metric_key,
            {
                "key": metric_key,
                "label": metric_label,
                "count": 0,
                "node_ids": set(),
                "min": value,
                "max": value,
            },
        )
        metric_state["count"] = int(metric_state.get("count", 0)) + sample_count
        metric_state["node_ids"].add(node_id)
        metric_state["min"] = min(float(metric_state.get("min", value)), value)
        metric_state["max"] = max(float(metric_state.get("max", value)), value)

        node_state = node_meta.setdefault(
            node_id,
            {
                "id": node_id,
                "label": node_label,
                "count": 0,
                "metric_keys": set(),
                "last_unix": unix,
            },
        )
        node_state["count"] = int(node_state.get("count", 0)) + sample_count
        node_state["metric_keys"].add(metric_key)
        node_state["last_unix"] = max(int(node_state.get("last_unix", 0)), unix)
        if node_state.get("label") in ("", node_id):
            node_state["label"] = node_label

    return metric_meta, node_meta


def load_recent_packets(store: HistoryStoreReadState, limit: int) -> list[dict[str, object]]:
    read_conn = getattr(store, "_read_conn", None)
    if read_conn is None or read_conn is store._conn:
        read_conn = store._conn
        read_lock = store._lock
    else:
        read_lock = getattr(store, "_read_lock", None) or store._lock
    with read_lock:
        return _load_recent_packets_data_helper(
            read_conn,
            limit=limit,
            fetch_recent_packet_rows_fn=_fetch_recent_packet_rows_helper,
            decode_recent_packets_rows_fn=_decode_recent_packets_rows_helper,
        )


def search_packets(
    store: HistoryStoreReadState,
    needle: str,
    *,
    limit: int | None = None,
    before: int | None = None,
    after: int | None = None,
    scope: str | None = None,
    scan_limit: int | None = None,
    source: str | None = None,
) -> dict[str, object]:
    clean_needle = str(needle or "").strip()
    clean_scope = str(scope or "both").strip().lower()
    if clean_scope not in {"both", "summary", "packet"}:
        clean_scope = "both"
    clean_source = str(source or "both").strip().lower()
    if clean_source not in {"both", "packet", "chat"}:
        clean_source = "both"

    clean_limit = max(1, min(500, int(limit) if isinstance(limit, int) else 120))
    clean_before = max(0, min(30, int(before) if isinstance(before, int) else 0))
    clean_after = max(0, min(30, int(after) if isinstance(after, int) else 0))
    clean_scan_limit = (
        max(1, min(50000, int(scan_limit)))
        if isinstance(scan_limit, int) and scan_limit > 0
        else 0
    )

    read_conn = getattr(store, "_read_conn", None)
    if read_conn is None or read_conn is store._conn:
        read_conn = store._conn
        read_lock = store._lock
    else:
        read_lock = getattr(store, "_read_lock", None) or store._lock

    with read_lock:
        packet_rows = (
            list(_fetch_packet_search_rows_helper(read_conn, clean_scan_limit))
            if clean_source in {"both", "packet"}
            else []
        )
        chat_rows = (
            list(_fetch_chat_search_rows_helper(read_conn, clean_scan_limit))
            if clean_source in {"both", "chat"}
            else []
        )

    rows: list[dict[str, object]] = []
    for packet_row in packet_rows:
        packet_id, created_unix, summary_json, packet_json = packet_row
        summary_text = str(summary_json or "")
        packet_text = str(packet_json or "")
        if clean_scope == "summary":
            haystack = summary_text
        elif clean_scope == "packet":
            haystack = packet_text
        else:
            haystack = f"{summary_text}\n{packet_text}"
        rows.append(
            {
                "source": "packet",
                "row_id": int(packet_id) if packet_id is not None else None,
                "created_unix": int(created_unix) if created_unix is not None else None,
                "summary_json": summary_json,
                "packet_json": packet_json,
                "haystack": haystack,
            }
        )

    for chat_row in chat_rows:
        chat_id, created_unix, message_json = chat_row
        message_text = str(message_json or "")
        rows.append(
            {
                "source": "chat",
                "row_id": int(chat_id) if chat_id is not None else None,
                "created_unix": int(created_unix) if created_unix is not None else None,
                "message_json": message_json,
                "haystack": message_text,
            }
        )

    rows.sort(
        key=lambda row: (
            int(_to_int(row.get("created_unix")) or 0),
            0 if str(row.get("source") or "") == "packet" else 1,
            int(_to_int(row.get("row_id")) or 0),
        )
    )

    scanned_packets = len(packet_rows)
    scanned_chat = len(chat_rows)
    scanned_total = len(rows)
    if not clean_needle:
        return {
            "ok": True,
            "query": "",
            "scope": clean_scope,
            "source": clean_source,
            "limit": clean_limit,
            "before": clean_before,
            "after": clean_after,
            "scan_limit": clean_scan_limit,
            "scanned_packets": scanned_packets,
            "scanned_chat": scanned_chat,
            "scanned_total": scanned_total,
            "matches": 0,
            "returned_matches": 0,
            "entries": [],
        }

    needle_lower = clean_needle.lower()
    match_indexes: list[int] = []
    for idx, row in enumerate(rows):
        haystack = str(row.get("haystack") or "")
        if needle_lower in haystack.lower():
            match_indexes.append(idx)

    total_matches = len(match_indexes)
    selected_match_indexes = match_indexes[-clean_limit:]
    selected_match_set = set(selected_match_indexes)

    if not selected_match_indexes:
        return {
            "ok": True,
            "query": clean_needle,
            "scope": clean_scope,
            "source": clean_source,
            "limit": clean_limit,
            "before": clean_before,
            "after": clean_after,
            "scan_limit": clean_scan_limit,
            "scanned_packets": scanned_packets,
            "scanned_chat": scanned_chat,
            "scanned_total": scanned_total,
            "matches": 0,
            "returned_matches": 0,
            "entries": [],
        }

    ranges: list[tuple[int, int]] = []
    for idx in selected_match_indexes:
        start = max(0, idx - clean_before)
        end = min(scanned_total - 1, idx + clean_after)
        if not ranges or start > (ranges[-1][1] + 1):
            ranges.append((start, end))
        else:
            ranges[-1] = (ranges[-1][0], max(ranges[-1][1], end))

    entries: list[dict[str, object]] = []
    for range_idx, (start, end) in enumerate(ranges):
        if range_idx > 0:
            entries.append({"separator": True})
        for idx in range(start, end + 1):
            row = rows[idx]
            source_kind = str(row.get("source") or "packet")
            if source_kind == "chat":
                message_json = row.get("message_json")
                chat = _safe_json_loads(message_json, {})
                if not isinstance(chat, dict):
                    chat = {}
                entries.append(
                    {
                        "separator": False,
                        "source": "chat",
                        "match": idx in selected_match_set,
                        "chat_row_id": int(_to_int(row.get("row_id")) or 0) or None,
                        "created_unix": int(_to_int(row.get("created_unix")) or 0) or None,
                        "chat": chat,
                    }
                )
                continue

            summary_json = row.get("summary_json")
            packet_json = row.get("packet_json")
            summary = _safe_json_loads(summary_json, {})
            if not isinstance(summary, dict):
                summary = {}
            packet = _safe_json_loads(packet_json, {})
            if not isinstance(packet, dict):
                packet = {}
            entries.append(
                {
                    "separator": False,
                    "source": "packet",
                    "match": idx in selected_match_set,
                    "packet_row_id": int(_to_int(row.get("row_id")) or 0) or None,
                    "created_unix": int(_to_int(row.get("created_unix")) or 0) or None,
                    "summary": summary,
                    "packet": packet,
                }
            )

    return {
        "ok": True,
        "query": clean_needle,
        "scope": clean_scope,
        "source": clean_source,
        "limit": clean_limit,
        "before": clean_before,
        "after": clean_after,
        "scan_limit": clean_scan_limit,
        "scanned_packets": scanned_packets,
        "scanned_chat": scanned_chat,
        "scanned_total": scanned_total,
        "matches": total_matches,
        "returned_matches": len(selected_match_indexes),
        "entries": entries,
    }


def load_environment_metrics_history(
    store: HistoryStoreReadState,
    *,
    window_hours: int | None = None,
    metric: str | None = None,
    node_id: str | None = None,
    limit: int | None = None,
) -> dict[str, object]:
    clean_hours = max(1, min(24 * 365, int(window_hours) if isinstance(window_hours, int) else 72))
    clean_limit = max(200, min(100000, int(limit) if isinstance(limit, int) else 20000))
    clean_metric = _normalize_env_metric_key(metric or "")
    clean_node_id = _canonical_node_id(node_id or "")

    cutoff = int(time.time()) - (clean_hours * 3600)
    read_conn = getattr(store, "_read_conn", None)
    if read_conn is None or read_conn is store._conn:
        read_conn = store._conn
        read_lock = store._lock
    else:
        read_lock = getattr(store, "_read_lock", None) or store._lock

    with read_lock:
        rollup_rows = list(
            _fetch_environment_metric_rollup_rows_helper(
                read_conn,
                cutoff=cutoff,
                limit=clean_limit,
                metric=clean_metric or None,
                node_id=clean_node_id or None,
            )
        )
        packet_rows: list[tuple[object, ...]] = []
        earliest_rollup_unix = 0
        if rollup_rows:
            for row in rollup_rows:
                rollup_unix = _to_int(row[10]) if len(row) > 10 else None
                if rollup_unix is None or rollup_unix <= 0:
                    rollup_unix = _to_int(row[0]) if len(row) > 0 else None
                if rollup_unix is None or rollup_unix <= 0:
                    continue
                if earliest_rollup_unix <= 0 or rollup_unix < earliest_rollup_unix:
                    earliest_rollup_unix = int(rollup_unix)
        need_packet_gap_fill = (not rollup_rows) or (
            earliest_rollup_unix > 0 and earliest_rollup_unix > cutoff
        )
        if need_packet_gap_fill:
            packet_rows = list(
                _fetch_environment_metric_packet_rows_helper(
                    read_conn,
                    cutoff=cutoff,
                    limit=clean_limit,
                )
            )

    if rollup_rows:
        points, metric_meta_map, node_meta_map = _build_environment_points_from_rollups(
            rollup_rows,
            metric_filter=clean_metric,
            node_filter=clean_node_id,
        )
        scanned_count = len(rollup_rows)
        source_kind = "rollup_1m"
        if packet_rows:
            packet_points, _packet_metric_meta_map, _packet_node_meta_map = _build_environment_points(
                packet_rows,
                metric_filter=clean_metric,
                node_filter=clean_node_id,
                custom_telemetry_rules=getattr(store, "_custom_telemetry_rules", None),
            )
            if earliest_rollup_unix > 0:
                packet_points = [
                    point
                    for point in packet_points
                    if int(_to_int(point.get("unix")) or 0) < earliest_rollup_unix
                ]
            if packet_points:
                points.extend(packet_points)
                points.sort(
                    key=lambda point: (
                        int(_to_int(point.get("unix")) or 0),
                        str(point.get("node_id") or ""),
                        str(point.get("metric_key") or ""),
                    )
                )
                packet_metric_meta_map, packet_node_meta_map = _derive_environment_meta_from_points(
                    packet_points
                )
                metric_meta_map, node_meta_map = _merge_environment_meta_maps(
                    metric_meta_map,
                    node_meta_map,
                    packet_metric_meta_map,
                    packet_node_meta_map,
                )
            scanned_count += len(packet_rows)
            source_kind = "rollup_1m+packet_scan"
    else:
        points, metric_meta_map, node_meta_map = _build_environment_points(
            packet_rows,
            metric_filter=clean_metric,
            node_filter=clean_node_id,
            custom_telemetry_rules=getattr(store, "_custom_telemetry_rules", None),
        )
        scanned_count = len(packet_rows)
        source_kind = "packet_scan"

    metric_rows = [
        {
            "key": str(meta.get("key") or ""),
            "label": str(meta.get("label") or "Metric"),
            "count": int(meta.get("count") or 0),
            "nodes": len(meta.get("node_ids") or []),
            "min": float(meta.get("min") or 0.0),
            "max": float(meta.get("max") or 0.0),
        }
        for meta in metric_meta_map.values()
    ]
    metric_rows.sort(key=lambda item: (-int(item["count"]), str(item["label"])))

    node_rows = [
        {
            "id": str(meta.get("id") or ""),
            "label": str(meta.get("label") or meta.get("id") or "node"),
            "count": int(meta.get("count") or 0),
            "metrics": len(meta.get("metric_keys") or []),
            "last_unix": int(meta.get("last_unix") or 0),
            "last_seen": _format_epoch(int(meta.get("last_unix") or 0)) if int(meta.get("last_unix") or 0) > 0 else "n/a",
        }
        for meta in node_meta_map.values()
    ]
    node_rows.sort(key=lambda item: (-int(item["count"]), str(item["label"]), str(item["id"])))

    return {
        "ok": True,
        "window_hours": clean_hours,
        "cutoff_unix": cutoff,
        "cutoff_time": _format_epoch(cutoff),
        "query": {
            "metric": clean_metric,
            "node_id": clean_node_id,
            "limit": clean_limit,
        },
        "source": source_kind,
        "scanned_packets": scanned_count,
        "total_points": len(points),
        "returned_points": len(points),
        "metrics": metric_rows,
        "nodes": node_rows,
        "points": points,
    }


def save_packet(store: HistoryStoreWriteState, packet_entry: dict[str, object]) -> None:
    with store._lock:
        local_node_id = getattr(store, "local_node_id", "")
        if _should_skip_local_noise_packet(
            packet_entry,
            local_node_id=local_node_id,
        ):
            return
        skip_local_telemetry, local_telemetry_sample_unix = _should_skip_local_telemetry_duplicate(
            packet_entry,
            local_node_id=local_node_id,
            last_saved_sample_unix=getattr(store, "_last_local_telemetry_sample_unix", 0),
        )
        if skip_local_telemetry:
            return
        _save_packet_record_helper(
            store._conn,
            packet_entry,
            now_unix_fn=time.time,
            save_packet_event_and_rollups_fn=_save_packet_event_and_rollups_helper,
            custom_telemetry_rules=getattr(store, "_custom_telemetry_rules", None),
        )
        if local_telemetry_sample_unix > 0:
            setattr(store, "_last_local_telemetry_sample_unix", int(local_telemetry_sample_unix))
        store._maybe_prune_unlocked()
        store._conn.commit()
