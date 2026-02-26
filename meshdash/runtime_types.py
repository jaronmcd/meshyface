from typing import TYPE_CHECKING, Callable, Optional, Protocol

from .revision import RevisionInfo
from .state_payload_contracts import DashboardStatePayload

if TYPE_CHECKING:
    from .tracker_runtime_packet_contracts import TrackerPacketRuntimeDependencies
    from .tracker_runtime_types import TrackerReceiveRuntimeState

MeshTargetLabelFn = Callable[[object], str]
OpenMeshInterfaceFn = Callable[[object], object]
SubscribeFn = Callable[[object, str], None]
SeedTrackerFn = Callable[[object, object], None]
RevisionInfoFn = Callable[[], RevisionInfo]

StatePayload = DashboardStatePayload | dict[str, object]

BuildStateFn = Callable[..., StatePayload]
BuildNodeHistoryLoaderFn = Callable[..., Callable[..., dict]]
BuildOnlineActivityLoaderFn = Callable[..., Callable[..., dict]]
BuildSendChatLoaderFn = Callable[..., Callable[..., dict]]
BuildStateSnapshotLoaderFn = Callable[..., Callable[[], dict]]

SendChatMessageFn = Callable[..., dict]
SendReactionPacketFn = Callable[..., object]
RawGetLocalNodeIdFn = Callable[..., str]
GetLocalNodeIdFn = Callable[[object], str]
LocalNodeIdFn = Callable[[], str]
RecordLocalChatFn = Callable[..., None]

NormalizeSingleEmojiFn = Callable[[object], tuple[Optional[str], Optional[int]]]
ToIntFn = Callable[[object], Optional[int]]
UtcNowFn = Callable[[], str]
NowUnixFn = Callable[[], float]
GetTimeoutSecondsFn = Callable[[], int]
ParseUtcTextToUnixFn = Callable[[object], Optional[float]]

RenderHtmlFn = Callable[..., str]
MakeHttpHandlerFn = Callable[..., object]
ThreadingHttpServerCls = Callable[[tuple[str, int], object], object]
GuessLanIpv4Fn = Callable[[], Optional[str]]

StateFn = Callable[[], StatePayload]
NodeHistoryFn = Callable[..., dict]
OnlineActivityFn = Callable[..., dict]
SendChatFn = Callable[..., dict]

TrackerPacket = dict[str, object]
TrackerParsedPacket = dict[str, object]
TrackerEdgeMap = dict[object, dict[str, object]]
DirectEdgeKey = Optional[tuple[str, str]]

ExtractDeliveryUpdateFn = Callable[..., object]
SetDeliveryStateFn = Callable[..., None]
ApplyTrackerObservationFn = Callable[..., DirectEdgeKey]
ApplyRoutingDeliveryUpdateFn = Callable[..., object]
RecordDirectEdgeObservationFn = Callable[..., object]

BuildPacketSummaryFn = Callable[..., TrackerPacket]
BuildChatEntryFromPacketFn = Callable[..., Optional[TrackerPacket]]
BuildTrackerPacketArtifactsFn = Callable[..., tuple[TrackerPacket, Optional[TrackerPacket]]]
ApplyTrackerStorageUpdatesFn = Callable[..., None]
ParseTrackerPacketFn = Callable[..., TrackerParsedPacket]
ProcessParsedTrackerPacketFn = Callable[..., None]
GetNodeIdFromNumFn = Callable[[object, object], Optional[str]]
CalculateHopsFn = Callable[[object, object], Optional[int]]
ExtractPacketPositionFn = Callable[[TrackerPacket], Optional[TrackerPacket]]
ExtractPacketBatteryLevelFn = Callable[[TrackerPacket], Optional[int]]
ExtractReplyIdFn = Callable[[object], Optional[int]]
ExtractEmojiCodepointFn = Callable[[object], Optional[int]]
EmojiFromCodepointFn = Callable[[Optional[int]], Optional[str]]
FormatEpochFn = Callable[[object], str]
ToJsonableFn = Callable[[object], object]


class RecordTrackerPacketUnlockedFn(Protocol):
    def __call__(
        self,
        *,
        packet: TrackerPacket,
        interface: object,
        include_live_count: bool,
        session_edges: TrackerEdgeMap,
        historical_edges: TrackerEdgeMap,
        port_counts: object,
        recent_packets: object,
        recent_chat: object,
        history_store: object | None,
        extract_delivery_update_fn: ExtractDeliveryUpdateFn,
        set_delivery_state_fn: SetDeliveryStateFn,
        apply_tracker_observation_fn: ApplyTrackerObservationFn,
        apply_routing_delivery_update_fn: ApplyRoutingDeliveryUpdateFn,
        record_direct_edge_observation_fn: RecordDirectEdgeObservationFn,
        build_tracker_packet_artifacts_fn: BuildTrackerPacketArtifactsFn,
        build_packet_summary_fn: BuildPacketSummaryFn,
        build_chat_entry_from_packet_fn: BuildChatEntryFromPacketFn,
        apply_tracker_storage_updates_fn: ApplyTrackerStorageUpdatesFn,
        parse_tracker_packet_fn: ParseTrackerPacketFn,
        process_parsed_tracker_packet_fn: ProcessParsedTrackerPacketFn,
        get_node_id_from_num_fn: GetNodeIdFromNumFn,
        to_int_fn: ToIntFn,
        calculate_hops_fn: CalculateHopsFn,
        extract_packet_position_fn: ExtractPacketPositionFn,
        extract_packet_battery_level_fn: ExtractPacketBatteryLevelFn,
        extract_reply_id_fn: ExtractReplyIdFn,
        extract_emoji_codepoint_fn: ExtractEmojiCodepointFn,
        emoji_from_codepoint_fn: EmojiFromCodepointFn,
        utc_now_fn: UtcNowFn,
        format_epoch_fn: FormatEpochFn,
        to_jsonable_fn: ToJsonableFn,
    ) -> None:
        ...


class RecordTrackerPacketUnlockedWithDependenciesFn(Protocol):
    def __call__(
        self,
        *,
        packet: TrackerPacket,
        interface: object,
        include_live_count: bool,
        deps: "TrackerPacketRuntimeDependencies",
    ) -> None:
        ...


class RecordTrackerReceiveUnlockedFn(Protocol):
    def __call__(
        self,
        tracker: "TrackerReceiveRuntimeState",
        *,
        packet: TrackerPacket,
        interface: object,
        include_live_count: bool,
        get_node_id_from_num_fn: GetNodeIdFromNumFn,
        record_tracker_packet_unlocked_fn: RecordTrackerPacketUnlockedFn | None,
        record_tracker_packet_unlocked_with_dependencies_fn: RecordTrackerPacketUnlockedWithDependenciesFn,
    ) -> None:
        ...


class ResolveTrackerNodeIdFromNumFn(Protocol):
    def __call__(
        self,
        iface: object,
        node_num: object,
        *,
        get_node_id_from_num_fn: GetNodeIdFromNumFn,
    ) -> Optional[str]:
        ...
