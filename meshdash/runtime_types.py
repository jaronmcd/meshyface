from typing import TYPE_CHECKING, Callable, Optional, Protocol

from .revision import RevisionInfo
from .state_payload_contracts import DashboardStatePayload
from .tracker_storage_contracts import (
    RecentChatBuffer,
    RecentPacketBuffer,
    TrackerHistoryWriter,
)

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

ThreadingHttpServerCls = Callable[[tuple[str, int], object], object]
GuessLanIpv4Fn = Callable[[], Optional[str]]

class RenderHtmlFn(Protocol):
    def __call__(
        self,
        refresh_ms: int,
        packet_limit: int,
        show_secrets: bool,
        history_enabled: bool,
        history_max_rows: int,
        history_retention_days: int,
        node_history_hours: int,
        node_history_max_points: int,
        revision_label: str,
        revision_title: str,
        light_theme_vars: dict | None = None,
        dark_theme_vars: dict | None = None,
    ) -> str:
        ...


class StateFn(Protocol):
    def __call__(self) -> StatePayload:
        ...


class NodeHistoryFn(Protocol):
    def __call__(
        self,
        node_id: str,
        hours_override: Optional[int] = None,
        points_override: Optional[int] = None,
    ) -> dict[str, object]:
        ...


class OnlineActivityFn(Protocol):
    def __call__(self, hours_override: Optional[int] = None) -> dict[str, object]:
        ...


class SendChatFn(Protocol):
    def __call__(
        self,
        text: object,
        destination: object = None,
        channel_index: Optional[int] = None,
        reply_id: Optional[int] = None,
        retry_of: Optional[int] = None,
        emoji: object = None,
    ) -> dict[str, object]:
        ...


class MakeHttpHandlerFn(Protocol):
    def __call__(
        self,
        html_text: str,
        state_fn: StateFn,
        node_history_fn: NodeHistoryFn | None = None,
        online_activity_fn: OnlineActivityFn | None = None,
        send_chat_fn: SendChatFn | None = None,
        default_node_history_hours: int = 72,
        to_int_fn: ToIntFn = ...,
    ) -> object:
        ...

TrackerPacket = dict[str, object]
TrackerParsedPacket = dict[str, object]
TrackerEdgeMap = dict[object, dict[str, object]]
DirectEdgeKey = Optional[tuple[str, str]]

GetNodeIdFromNumFn = Callable[[object, object], Optional[str]]
CalculateHopsFn = Callable[[object, object], Optional[int]]
ExtractPacketPositionFn = Callable[[TrackerPacket], Optional[TrackerPacket]]
ExtractPacketBatteryLevelFn = Callable[[TrackerPacket], Optional[int]]
ExtractReplyIdFn = Callable[[object], Optional[int]]
ExtractEmojiCodepointFn = Callable[[object], Optional[int]]
EmojiFromCodepointFn = Callable[[Optional[int]], Optional[str]]
FormatEpochFn = Callable[[object], str]
ToJsonableFn = Callable[[object], object]


class BuildPacketSummaryFn(Protocol):
    def __call__(
        self,
        *,
        packet: TrackerPacket,
        decoded: object,
        from_id: object,
        to_id: object,
        packet_id: Optional[int],
        rx_time: Optional[int],
        hops: Optional[int],
        reply_id: Optional[int],
        emoji_glyph: Optional[str],
        emoji_codepoint: Optional[int],
        is_reaction: bool,
        packet_position: Optional[dict[str, object]],
        packet_battery: Optional[int],
        utc_now_fn: UtcNowFn,
        format_epoch_fn: FormatEpochFn,
        to_int_fn: ToIntFn,
    ) -> TrackerPacket:
        ...


class BuildChatEntryFromPacketFn(Protocol):
    def __call__(
        self,
        *,
        packet: TrackerPacket,
        decoded: object,
        from_id: object,
        to_id: object,
        packet_id: Optional[int],
        hops: Optional[int],
        reply_id: Optional[int],
        emoji_glyph: Optional[str],
        emoji_codepoint: Optional[int],
        is_reaction: bool,
        utc_now_fn: UtcNowFn,
        format_epoch_fn: FormatEpochFn,
    ) -> Optional[TrackerPacket]:
        ...


class BuildTrackerPacketArtifactsFn(Protocol):
    def __call__(
        self,
        *,
        packet: TrackerPacket,
        parsed: TrackerParsedPacket,
        include_live_count: bool,
        build_packet_summary_fn: BuildPacketSummaryFn,
        build_chat_entry_from_packet_fn: BuildChatEntryFromPacketFn,
        utc_now_fn: UtcNowFn,
        format_epoch_fn: FormatEpochFn,
        to_int_fn: ToIntFn,
        to_jsonable_fn: ToJsonableFn,
    ) -> tuple[TrackerPacket, Optional[TrackerPacket]]:
        ...


class ApplyTrackerStorageUpdatesFn(Protocol):
    def __call__(
        self,
        *,
        recent_packets: RecentPacketBuffer,
        recent_chat: RecentChatBuffer,
        history_store: TrackerHistoryWriter | None,
        include_live_count: bool,
        direct_key: DirectEdgeKey,
        rx_time: Optional[int],
        portnum: Optional[object],
        hops: Optional[int],
        packet_entry: TrackerPacket,
        chat_entry: Optional[TrackerPacket],
    ) -> None:
        ...


class PortCounter(Protocol):
    def get(self, key: str, default: int = 0) -> int:
        ...

    def __setitem__(self, key: str, value: int) -> None:
        ...

    def most_common(self) -> list[tuple[str, int]]:
        ...


class ExtractDeliveryUpdateFn(Protocol):
    def __call__(self, decoded: object) -> Optional[dict[str, object]]:
        ...


class SetDeliveryStateFn(Protocol):
    def __call__(
        self,
        message_id: object,
        state: str,
        error: Optional[str] = None,
    ) -> bool:
        ...


class ApplyRoutingDeliveryUpdateFn(Protocol):
    def __call__(
        self,
        decoded: object,
        *,
        extract_update_fn: ExtractDeliveryUpdateFn,
        set_delivery_state_fn: SetDeliveryStateFn,
    ) -> bool:
        ...


class RecordDirectEdgeObservationFn(Protocol):
    def __call__(
        self,
        *,
        session_edges: TrackerEdgeMap,
        historical_edges: TrackerEdgeMap,
        from_id: object,
        to_id: object,
        rx_time: Optional[int],
        portnum: Optional[object],
        hops: Optional[int],
        include_live_count: bool,
    ) -> DirectEdgeKey:
        ...


class ApplyTrackerObservationFn(Protocol):
    def __call__(
        self,
        *,
        parsed: TrackerParsedPacket,
        include_live_count: bool,
        session_edges: TrackerEdgeMap,
        historical_edges: TrackerEdgeMap,
        port_counts: PortCounter,
        apply_routing_delivery_update_fn: ApplyRoutingDeliveryUpdateFn,
        extract_update_fn: ExtractDeliveryUpdateFn,
        set_delivery_state_fn: SetDeliveryStateFn,
        record_direct_edge_observation_fn: RecordDirectEdgeObservationFn,
    ) -> DirectEdgeKey:
        ...


class ParseTrackerPacketFn(Protocol):
    def __call__(
        self,
        packet: TrackerPacket,
        interface: object,
        *,
        get_node_id_from_num_fn: GetNodeIdFromNumFn,
        to_int_fn: ToIntFn,
        calculate_hops_fn: CalculateHopsFn,
        extract_packet_position_fn: ExtractPacketPositionFn,
        extract_packet_battery_level_fn: ExtractPacketBatteryLevelFn,
        extract_reply_id_fn: ExtractReplyIdFn,
        extract_emoji_codepoint_fn: ExtractEmojiCodepointFn,
        emoji_from_codepoint_fn: EmojiFromCodepointFn,
    ) -> TrackerParsedPacket:
        ...


class ProcessParsedTrackerPacketFn(Protocol):
    def __call__(
        self,
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
        ...


class RecordTrackerPacketUnlockedFn(Protocol):
    def __call__(
        self,
        *,
        packet: TrackerPacket,
        interface: object,
        include_live_count: bool,
        session_edges: TrackerEdgeMap,
        historical_edges: TrackerEdgeMap,
        port_counts: PortCounter,
        recent_packets: RecentPacketBuffer,
        recent_chat: RecentChatBuffer,
        history_store: TrackerHistoryWriter | None,
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
