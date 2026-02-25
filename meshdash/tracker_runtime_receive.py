from typing import Any

from .helpers import (
    calculate_hops as _calculate_hops,
    emoji_from_codepoint as _emoji_from_codepoint,
    extract_emoji_codepoint as _extract_emoji_codepoint,
    extract_packet_battery_level as _extract_packet_battery_level,
    extract_packet_position as _extract_packet_position,
    extract_reply_id as _extract_reply_id,
    format_epoch as _format_epoch,
    to_int as _to_int,
    to_jsonable as _to_jsonable,
)
from .nodes import (
    utc_now as _utc_now,
)
from .tracker_delivery import (
    apply_routing_delivery_update as _apply_routing_delivery_update_helper,
)
from .tracker_edges import (
    record_direct_edge_observation as _record_direct_edge_observation_helper,
)
from .tracker_entries import (
    build_chat_entry_from_packet as _build_chat_entry_from_packet_helper,
    build_packet_summary as _build_packet_summary_helper,
)
from .tracker_ingest import (
    parse_tracker_packet as _parse_tracker_packet_helper,
)
from .tracker_observation import (
    apply_tracker_observation as _apply_tracker_observation_helper,
)
from .tracker_packet_artifacts import (
    build_tracker_packet_artifacts as _build_tracker_packet_artifacts_helper,
)
from .tracker_receive import (
    process_parsed_tracker_packet as _process_parsed_tracker_packet_helper,
)
from .tracker_runtime_record import (
    record_tracker_packet_unlocked_with_dependencies as _record_tracker_packet_unlocked_with_dependencies_helper,
)
from .tracker_runtime_receive_dependencies import (
    build_tracker_packet_runtime_dependencies as _build_tracker_packet_runtime_dependencies_helper,
    tracker_packet_runtime_dependencies_to_legacy_kwargs as _tracker_packet_runtime_dependencies_to_legacy_kwargs_helper,
)
from .tracker_runtime_types import (
    TrackerReceiveRuntimeState,
)
from .tracker_storage import (
    apply_tracker_storage_updates as _apply_tracker_storage_updates_helper,
)
from .runtime_types import (
    ApplyRoutingDeliveryUpdateFn,
    ApplyTrackerObservationFn,
    ApplyTrackerStorageUpdatesFn,
    BuildChatEntryFromPacketFn,
    BuildPacketSummaryFn,
    BuildTrackerPacketArtifactsFn,
    CalculateHopsFn,
    EmojiFromCodepointFn,
    ExtractPacketBatteryLevelFn,
    ExtractPacketPositionFn,
    ExtractReplyIdFn,
    ExtractEmojiCodepointFn,
    FormatEpochFn,
    GetNodeIdFromNumFn,
    ParseTrackerPacketFn,
    ProcessParsedTrackerPacketFn,
    RecordDirectEdgeObservationFn,
    RecordTrackerPacketUnlockedFn,
    RecordTrackerPacketUnlockedWithDependenciesFn,
    ToIntFn,
    ToJsonableFn,
    TrackerPacket,
    UtcNowFn,
)


def record_tracker_receive_unlocked(
    tracker: TrackerReceiveRuntimeState,
    *,
    packet: TrackerPacket,
    interface: Any,
    include_live_count: bool,
    get_node_id_from_num_fn: GetNodeIdFromNumFn,
    record_tracker_packet_unlocked_fn: RecordTrackerPacketUnlockedFn | None = None,
    record_tracker_packet_unlocked_with_dependencies_fn: RecordTrackerPacketUnlockedWithDependenciesFn = _record_tracker_packet_unlocked_with_dependencies_helper,
    apply_tracker_observation_fn: ApplyTrackerObservationFn = _apply_tracker_observation_helper,
    apply_routing_delivery_update_fn: ApplyRoutingDeliveryUpdateFn = _apply_routing_delivery_update_helper,
    record_direct_edge_observation_fn: RecordDirectEdgeObservationFn = _record_direct_edge_observation_helper,
    build_tracker_packet_artifacts_fn: BuildTrackerPacketArtifactsFn = _build_tracker_packet_artifacts_helper,
    build_packet_summary_fn: BuildPacketSummaryFn = _build_packet_summary_helper,
    build_chat_entry_from_packet_fn: BuildChatEntryFromPacketFn = _build_chat_entry_from_packet_helper,
    apply_tracker_storage_updates_fn: ApplyTrackerStorageUpdatesFn = _apply_tracker_storage_updates_helper,
    parse_tracker_packet_fn: ParseTrackerPacketFn = _parse_tracker_packet_helper,
    process_parsed_tracker_packet_fn: ProcessParsedTrackerPacketFn = _process_parsed_tracker_packet_helper,
    to_int_fn: ToIntFn = _to_int,
    calculate_hops_fn: CalculateHopsFn = _calculate_hops,
    extract_packet_position_fn: ExtractPacketPositionFn = _extract_packet_position,
    extract_packet_battery_level_fn: ExtractPacketBatteryLevelFn = _extract_packet_battery_level,
    extract_reply_id_fn: ExtractReplyIdFn = _extract_reply_id,
    extract_emoji_codepoint_fn: ExtractEmojiCodepointFn = _extract_emoji_codepoint,
    emoji_from_codepoint_fn: EmojiFromCodepointFn = _emoji_from_codepoint,
    utc_now_fn: UtcNowFn = _utc_now,
    format_epoch_fn: FormatEpochFn = _format_epoch,
    to_jsonable_fn: ToJsonableFn = _to_jsonable,
) -> None:
    deps = _build_tracker_packet_runtime_dependencies_helper(
        tracker,
        get_node_id_from_num_fn=get_node_id_from_num_fn,
        apply_tracker_observation_fn=apply_tracker_observation_fn,
        apply_routing_delivery_update_fn=apply_routing_delivery_update_fn,
        record_direct_edge_observation_fn=record_direct_edge_observation_fn,
        build_tracker_packet_artifacts_fn=build_tracker_packet_artifacts_fn,
        build_packet_summary_fn=build_packet_summary_fn,
        build_chat_entry_from_packet_fn=build_chat_entry_from_packet_fn,
        apply_tracker_storage_updates_fn=apply_tracker_storage_updates_fn,
        parse_tracker_packet_fn=parse_tracker_packet_fn,
        process_parsed_tracker_packet_fn=process_parsed_tracker_packet_fn,
        to_int_fn=to_int_fn,
        calculate_hops_fn=calculate_hops_fn,
        extract_packet_position_fn=extract_packet_position_fn,
        extract_packet_battery_level_fn=extract_packet_battery_level_fn,
        extract_reply_id_fn=extract_reply_id_fn,
        extract_emoji_codepoint_fn=extract_emoji_codepoint_fn,
        emoji_from_codepoint_fn=emoji_from_codepoint_fn,
        utc_now_fn=utc_now_fn,
        format_epoch_fn=format_epoch_fn,
        to_jsonable_fn=to_jsonable_fn,
    )
    if record_tracker_packet_unlocked_fn is not None:
        record_tracker_packet_unlocked_fn(
            packet=packet,
            interface=interface,
            include_live_count=include_live_count,
            **_tracker_packet_runtime_dependencies_to_legacy_kwargs_helper(deps),
        )
    else:
        record_tracker_packet_unlocked_with_dependencies_fn(
            packet=packet,
            interface=interface,
            include_live_count=include_live_count,
            deps=deps,
        )
    tracker._expire_pending_deliveries_fn()
