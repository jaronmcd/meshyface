from collections.abc import Iterable
from typing import Optional

from .runtime_types import FormatEpochFn
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
    combined_keys = set(session_edges.keys()) | set(historical_edges.keys())
    for key in combined_keys:
        session_edge = session_edges.get(key)
        hist_edge = historical_edges.get(key)
        from_id, to_id = key

        session_count = int(session_edge["count"]) if session_edge else 0
        if hist_edge:
            lifetime_count = int(hist_edge["count"])
            first_seen = hist_edge.get("first_rx_time")
            last_seen = hist_edge.get("last_rx_time")
            last_hops = hist_edge.get("last_hops")
            hops_sum = int(hist_edge.get("hops_sum") or 0)
            hops_count = int(hist_edge.get("hops_count") or 0)
            port_set = set(hist_edge.get("portnums") or [])
        else:
            lifetime_count = session_count
            first_seen = session_edge.get("first_rx_time") if session_edge else None
            last_seen = session_edge.get("last_rx_time") if session_edge else None
            last_hops = session_edge.get("last_hops") if session_edge else None
            hops_sum = int(session_edge.get("hops_sum") or 0) if session_edge else 0
            hops_count = int(session_edge.get("hops_count") or 0) if session_edge else 0
            port_set = set(session_edge.get("portnums") or []) if session_edge else set()

        if session_edge:
            port_set |= set(session_edge.get("portnums") or [])
            if first_seen is None:
                first_seen = session_edge.get("first_rx_time")
            session_last = session_edge.get("last_rx_time")
            if session_last is not None and (last_seen is None or session_last > last_seen):
                last_seen = session_last
            if last_hops is None and session_edge.get("last_hops") is not None:
                last_hops = session_edge.get("last_hops")

        avg_hops: Optional[float] = None
        if hops_count > 0:
            avg_hops = round(hops_sum / hops_count, 2)
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
            "portnums": sorted(port_set),
        }
        src = nodes_by_id.get(from_id)
        dst = nodes_by_id.get(to_id)
        if src and dst and src.get("lat") is not None and dst.get("lat") is not None:
            row["src_lat"] = src.get("lat")
            row["src_lon"] = src.get("lon")
            row["dst_lat"] = dst.get("lat")
            row["dst_lon"] = dst.get("lon")
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
