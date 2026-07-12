import math
from collections.abc import Iterable
from typing import Optional

from .runtime_types import FormatEpochFn
from .tracker_edges import MAX_TRACKED_EDGE_KEYS
from .tracker_snapshot_build_contracts import (
    BuildEdgeSnapshotRowsFn,
    ChatRow,
    EdgeKey,
    EdgeRow,
    NodeRow,
    PacketRow,
    PortCounter,
)
from .tracker_snapshot_contracts import TrackerSnapshot


def _to_float(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _to_nonnegative_int(value: object, *, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    if parsed < 0 or (maximum is not None and parsed > maximum):
        return 0
    return parsed


def _to_optional_nonnegative_int(value: object, *, maximum: int | None = None) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed < 0 or (maximum is not None and parsed > maximum):
        return None
    return parsed


def _metric_average(sum_value: object, count_value: object) -> Optional[float]:
    total = _to_float(sum_value)
    count = _to_nonnegative_int(count_value)
    if total is None or count <= 0:
        return None
    average = total / count
    return round(average, 2) if math.isfinite(average) else None


def _edge_metric_values(edge: EdgeRow | None, prefix: str) -> tuple[float, int, float | None, float | None]:
    if edge is None:
        return 0.0, 0, None, None
    total = _to_float(edge.get(f"{prefix}_sum"))
    count = _to_nonnegative_int(edge.get(f"{prefix}_count"))
    if total is None or count <= 0:
        return 0.0, 0, None, None
    return (
        total,
        count,
        _to_float(edge.get(f"{prefix}_min")),
        _to_float(edge.get(f"{prefix}_max")),
    )


def _edge_hop_values(edge: EdgeRow | None) -> tuple[int, int]:
    if edge is None:
        return 0, 0
    total = _to_optional_nonnegative_int(edge.get("hops_sum"))
    count = _to_optional_nonnegative_int(edge.get("hops_count"))
    if total is None or count is None or count <= 0:
        return 0, 0
    return total, count


def _portnum_set(edge: EdgeRow | None) -> set[str]:
    if edge is None:
        return set()
    values = edge.get("portnums") or []
    if isinstance(values, (str, bytes, dict)) or not isinstance(values, Iterable):
        return set()
    out: set[str] = set()
    for value in values:
        clean = str(value)
        if len(clean) <= 64:
            out.add(clean)
        if len(out) >= 64:
            break
    return out


def _bounded_edge_keys(
    session_edges: dict[EdgeKey, EdgeRow],
    historical_edges: dict[EdgeKey, EdgeRow],
) -> list[EdgeKey]:
    keys: list[EdgeKey] = []
    seen: set[EdgeKey] = set()
    # Prefer current-session observations, then the most-recent historical
    # insertion order. Both input maps are also capped at ingestion/bootstrap.
    for edge_map in (session_edges, historical_edges):
        for key in reversed(edge_map):
            if key in seen:
                continue
            seen.add(key)
            keys.append(key)
            if len(keys) >= MAX_TRACKED_EDGE_KEYS:
                return keys
    return keys


def build_edge_snapshot_rows(
    *,
    session_edges: dict[EdgeKey, EdgeRow],
    historical_edges: dict[EdgeKey, EdgeRow],
    nodes_by_id: dict[str, NodeRow],
    min_real_link_count: int,
    format_epoch_fn: FormatEpochFn,
) -> tuple[list[EdgeRow], int]:
    edge_rows: list[EdgeRow] = []
    real_edge_count = 0
    combined_keys = _bounded_edge_keys(session_edges, historical_edges)
    for key in combined_keys:
        session_edge = session_edges.get(key)
        hist_edge = historical_edges.get(key)
        from_id, to_id = key

        session_count = _to_nonnegative_int(session_edge.get("count")) if session_edge else 0
        if hist_edge:
            lifetime_count = _to_nonnegative_int(hist_edge.get("count"))
            first_seen = _to_nonnegative_int(hist_edge.get("first_rx_time")) or None
            last_seen = _to_nonnegative_int(hist_edge.get("last_rx_time")) or None
            last_hops = _to_optional_nonnegative_int(hist_edge.get("last_hops"), maximum=255)
            hops_sum, hops_count = _edge_hop_values(hist_edge)
            port_set = _portnum_set(hist_edge)
            snr_sum, snr_count, snr_min, snr_max = _edge_metric_values(hist_edge, "snr")
            rssi_sum, rssi_count, rssi_min, rssi_max = _edge_metric_values(hist_edge, "rssi")
        else:
            lifetime_count = session_count
            first_seen = _to_nonnegative_int(session_edge.get("first_rx_time")) or None if session_edge else None
            last_seen = _to_nonnegative_int(session_edge.get("last_rx_time")) or None if session_edge else None
            last_hops = _to_optional_nonnegative_int(session_edge.get("last_hops"), maximum=255) if session_edge else None
            hops_sum, hops_count = _edge_hop_values(session_edge)
            port_set = _portnum_set(session_edge)
            snr_sum, snr_count, snr_min, snr_max = _edge_metric_values(session_edge, "snr")
            rssi_sum, rssi_count, rssi_min, rssi_max = _edge_metric_values(session_edge, "rssi")

        if session_edge:
            port_set |= _portnum_set(session_edge)
            if first_seen is None:
                first_seen = _to_nonnegative_int(session_edge.get("first_rx_time")) or None
            session_last = _to_nonnegative_int(session_edge.get("last_rx_time")) or None
            if session_last is not None and (last_seen is None or session_last > last_seen):
                last_seen = session_last
            if last_hops is None and session_edge.get("last_hops") is not None:
                last_hops = _to_optional_nonnegative_int(session_edge.get("last_hops"), maximum=255)
            if snr_count <= 0:
                snr_sum, snr_count, snr_min, snr_max = _edge_metric_values(session_edge, "snr")
            if rssi_count <= 0:
                rssi_sum, rssi_count, rssi_min, rssi_max = _edge_metric_values(session_edge, "rssi")

        avg_hops: Optional[float] = None
        if hops_count > 0:
            hops_average = hops_sum / hops_count
            avg_hops = round(hops_average, 2) if math.isfinite(hops_average) else None
        avg_snr = _metric_average(snr_sum, snr_count)
        avg_rssi = _metric_average(rssi_sum, rssi_count)
        is_real = lifetime_count >= int(min_real_link_count)
        if is_real:
            real_edge_count += 1

        row = {
            "from": from_id,
            "to": to_id,
            "count": lifetime_count,
            "session_count": session_count,
            "lifetime_count": lifetime_count,
            "is_real": is_real,
            "confidence": "confirmed" if is_real else "observed",
            "first_rx_time": format_epoch_fn(first_seen),
            "last_rx_time": format_epoch_fn(last_seen),
            "last_hops": last_hops,
            "avg_hops": avg_hops,
            "hops_samples": hops_count,
            "portnums": sorted(port_set)[:64],
            "avg_snr": avg_snr,
            "snr_samples": snr_count,
            "snr_min": snr_min,
            "snr_max": snr_max,
            "avg_rssi": avg_rssi,
            "rssi_samples": rssi_count,
            "rssi_min": rssi_min,
            "rssi_max": rssi_max,
        }
        src = nodes_by_id.get(from_id)
        dst = nodes_by_id.get(to_id)
        src_lat = _to_float(src.get("lat")) if isinstance(src, dict) else None
        src_lon = _to_float(src.get("lon")) if isinstance(src, dict) else None
        dst_lat = _to_float(dst.get("lat")) if isinstance(dst, dict) else None
        dst_lon = _to_float(dst.get("lon")) if isinstance(dst, dict) else None
        if src_lat is not None and src_lon is not None and dst_lat is not None and dst_lon is not None:
            row["src_lat"] = src_lat
            row["src_lon"] = src_lon
            row["dst_lat"] = dst_lat
            row["dst_lon"] = dst_lon
        edge_rows.append(row)

    edge_rows.sort(key=lambda item: (-item["lifetime_count"], item["from"], item["to"]))
    return edge_rows, real_edge_count


def build_tracker_snapshot_payload_typed(
    *,
    session_edges: dict[EdgeKey, EdgeRow],
    historical_edges: dict[EdgeKey, EdgeRow],
    nodes_by_id: dict[str, NodeRow],
    port_counts: PortCounter,
    recent_packets: Iterable[PacketRow],
    recent_chat: Iterable[ChatRow],
    live_packet_count: int,
    min_real_link_count: int,
    format_epoch_fn: FormatEpochFn,
    build_edge_snapshot_rows_fn: BuildEdgeSnapshotRowsFn = build_edge_snapshot_rows,
) -> TrackerSnapshot:
    edge_rows, real_edge_count = build_edge_snapshot_rows_fn(
        session_edges=session_edges,
        historical_edges=historical_edges,
        nodes_by_id=nodes_by_id,
        min_real_link_count=min_real_link_count,
        format_epoch_fn=format_epoch_fn,
    )
    port_rows = [
        {"portnum": portnum, "count": count}
        for portnum, count in port_counts.most_common()
    ]

    return TrackerSnapshot(
        live_packet_count=live_packet_count,
        real_edge_count=real_edge_count,
        edges=edge_rows,
        port_counts=port_rows,
        recent_packets=list(recent_packets),
        recent_chat=list(recent_chat),
    )


def build_tracker_snapshot_payload(
    *,
    session_edges: dict[EdgeKey, EdgeRow],
    historical_edges: dict[EdgeKey, EdgeRow],
    nodes_by_id: dict[str, NodeRow],
    port_counts: PortCounter,
    recent_packets: Iterable[PacketRow],
    recent_chat: Iterable[ChatRow],
    live_packet_count: int,
    min_real_link_count: int,
    format_epoch_fn: FormatEpochFn,
    build_edge_snapshot_rows_fn: BuildEdgeSnapshotRowsFn = build_edge_snapshot_rows,
) -> dict[str, object]:
    return build_tracker_snapshot_payload_typed(
        session_edges=session_edges,
        historical_edges=historical_edges,
        nodes_by_id=nodes_by_id,
        port_counts=port_counts,
        recent_packets=recent_packets,
        recent_chat=recent_chat,
        live_packet_count=live_packet_count,
        min_real_link_count=min_real_link_count,
        format_epoch_fn=format_epoch_fn,
        build_edge_snapshot_rows_fn=build_edge_snapshot_rows_fn,
    ).as_dict()
