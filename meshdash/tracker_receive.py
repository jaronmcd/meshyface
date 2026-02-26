from .runtime_types import (
    ApplyRoutingDeliveryUpdateFn,
    ApplyTrackerObservationFn,
    ApplyTrackerStorageUpdatesFn,
    BuildChatEntryFromPacketFn,
    BuildPacketSummaryFn,
    BuildTrackerPacketArtifactsFn,
    ExtractDeliveryUpdateFn,
    FormatEpochFn,
    PortCounter,
    RecordDirectEdgeObservationFn,
    SetDeliveryStateFn,
    ToIntFn,
    ToJsonableFn,
    TrackerEdgeMap,
    TrackerPacket,
    TrackerParsedPacket,
    UtcNowFn,
)
from .tracker_storage_contracts import RecentChatBuffer, RecentPacketBuffer, TrackerHistoryWriter


def process_parsed_tracker_packet(
    *,
    packet: TrackerPacket,
    parsed: TrackerParsedPacket,
    include_live_count: bool,
    session_edges: TrackerEdgeMap,
    historical_edges: TrackerEdgeMap,
    port_counts: PortCounter,
    apply_tracker_observation_fn: ApplyTrackerObservationFn,
    apply_routing_delivery_update_fn: ApplyRoutingDeliveryUpdateFn,
    extract_update_fn: ExtractDeliveryUpdateFn,
    set_delivery_state_fn: SetDeliveryStateFn,
    record_direct_edge_observation_fn: RecordDirectEdgeObservationFn,
    build_tracker_packet_artifacts_fn: BuildTrackerPacketArtifactsFn,
    build_packet_summary_fn: BuildPacketSummaryFn,
    build_chat_entry_from_packet_fn: BuildChatEntryFromPacketFn,
    utc_now_fn: UtcNowFn,
    format_epoch_fn: FormatEpochFn,
    to_int_fn: ToIntFn,
    to_jsonable_fn: ToJsonableFn,
    apply_tracker_storage_updates_fn: ApplyTrackerStorageUpdatesFn,
    recent_packets: RecentPacketBuffer,
    recent_chat: RecentChatBuffer,
    history_store: TrackerHistoryWriter | None,
) -> None:
    rx_time = parsed["rx_time"]
    hops = parsed["hops"]
    portnum = parsed["portnum"]

    direct_key = apply_tracker_observation_fn(
        parsed=parsed,
        include_live_count=include_live_count,
        session_edges=session_edges,
        historical_edges=historical_edges,
        port_counts=port_counts,
        apply_routing_delivery_update_fn=apply_routing_delivery_update_fn,
        extract_update_fn=extract_update_fn,
        set_delivery_state_fn=set_delivery_state_fn,
        record_direct_edge_observation_fn=record_direct_edge_observation_fn,
    )

    packet_entry, chat_entry = build_tracker_packet_artifacts_fn(
        packet=packet,
        parsed=parsed,
        include_live_count=include_live_count,
        build_packet_summary_fn=build_packet_summary_fn,
        build_chat_entry_from_packet_fn=build_chat_entry_from_packet_fn,
        utc_now_fn=utc_now_fn,
        format_epoch_fn=format_epoch_fn,
        to_int_fn=to_int_fn,
        to_jsonable_fn=to_jsonable_fn,
    )
    apply_tracker_storage_updates_fn(
        recent_packets=recent_packets,
        recent_chat=recent_chat,
        history_store=history_store,
        include_live_count=include_live_count,
        direct_key=direct_key,
        rx_time=rx_time,
        portnum=portnum,
        hops=hops,
        packet_entry=packet_entry,
        chat_entry=chat_entry,
    )
