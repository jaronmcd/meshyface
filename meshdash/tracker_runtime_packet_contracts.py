from dataclasses import dataclass
from .runtime_types import (
    ApplyRoutingDeliveryUpdateFn,
    ApplyTrackerObservationFn,
    ApplyTrackerStorageUpdatesFn,
    BuildChatEntryFromPacketFn,
    BuildPacketSummaryFn,
    BuildTrackerPacketArtifactsFn,
    CalculateHopsFn,
    EmojiFromCodepointFn,
    ExtractDeliveryUpdateFn,
    ExtractEmojiCodepointFn,
    ExtractPacketBatteryLevelFn,
    ExtractPacketPositionFn,
    ExtractReplyIdFn,
    FormatEpochFn,
    GetNodeIdFromNumFn,
    ParseTrackerPacketFn,
    ProcessParsedTrackerPacketFn,
    RecordDirectEdgeObservationFn,
    SetDeliveryStateFn,
    ToJsonableFn,
    TrackerEdgeMap,
    UtcNowFn,
    ToIntFn,
)
from .tracker_storage_contracts import RecentChatBuffer, RecentPacketBuffer, TrackerHistoryWriter


@dataclass(frozen=True)
class TrackerPacketRuntimeDependencies:
    session_edges: TrackerEdgeMap
    historical_edges: TrackerEdgeMap
    port_counts: object
    recent_packets: RecentPacketBuffer
    recent_chat: RecentChatBuffer
    history_store: TrackerHistoryWriter | None
    extract_delivery_update_fn: ExtractDeliveryUpdateFn
    set_delivery_state_fn: SetDeliveryStateFn
    apply_tracker_observation_fn: ApplyTrackerObservationFn
    apply_routing_delivery_update_fn: ApplyRoutingDeliveryUpdateFn
    record_direct_edge_observation_fn: RecordDirectEdgeObservationFn
    build_tracker_packet_artifacts_fn: BuildTrackerPacketArtifactsFn
    build_packet_summary_fn: BuildPacketSummaryFn
    build_chat_entry_from_packet_fn: BuildChatEntryFromPacketFn
    apply_tracker_storage_updates_fn: ApplyTrackerStorageUpdatesFn
    parse_tracker_packet_fn: ParseTrackerPacketFn
    process_parsed_tracker_packet_fn: ProcessParsedTrackerPacketFn
    get_node_id_from_num_fn: GetNodeIdFromNumFn
    to_int_fn: ToIntFn
    calculate_hops_fn: CalculateHopsFn
    extract_packet_position_fn: ExtractPacketPositionFn
    extract_packet_battery_level_fn: ExtractPacketBatteryLevelFn
    extract_reply_id_fn: ExtractReplyIdFn
    extract_emoji_codepoint_fn: ExtractEmojiCodepointFn
    emoji_from_codepoint_fn: EmojiFromCodepointFn
    utc_now_fn: UtcNowFn
    format_epoch_fn: FormatEpochFn
    to_jsonable_fn: ToJsonableFn
