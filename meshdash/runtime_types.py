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

GetLocalNodeIdFn = Callable[[object], str]
LocalNodeIdFn = Callable[[], str]

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
        reset_ticker_scale_on_restart: bool = True,
        debug_mode: bool = False,
        light_theme_vars: dict | None = None,
        dark_theme_vars: dict | None = None,
        file_transfer_enabled: bool = False,
        games_enabled: bool = False,
        file_transfer_max_bytes: int = 64 * 1024,
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


class SummaryMetricsHistoryFn(Protocol):
    def __call__(
        self,
        hours_override: Optional[int] = None,
        *,
        include_packet_series: bool = True,
    ) -> dict[str, object]:
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
        summary_metrics_fn: SummaryMetricsHistoryFn | None = None,
        send_chat_fn: SendChatFn | None = None,
        api_token: str | None = None,
        private_mode: bool = False,
        default_node_history_hours: int = 72,
        to_int_fn: ToIntFn = ...,
    ) -> object:
        ...

TrackerPacket = dict[str, object]
TrackerParsedPacket = dict[str, object]
TrackerEdgeMap = dict[object, dict[str, object]]
DirectEdgeKey = Optional[tuple[str, str]]
DirectEdgeKeys = tuple[tuple[str, str], ...]

GetNodeIdFromNumFn = Callable[[object, object], Optional[str]]
CalculateHopsFn = Callable[[object, object], Optional[int]]
ExtractPacketPositionFn = Callable[[TrackerPacket], Optional[TrackerPacket]]
ExtractPacketBatteryLevelFn = Callable[[TrackerPacket], Optional[int]]
ExtractReplyIdFn = Callable[[object], Optional[int]]
ExtractEmojiCodepointFn = Callable[[object], Optional[int]]
EmojiFromCodepointFn = Callable[[Optional[int]], Optional[str]]
FormatEpochFn = Callable[[object], str]
ToJsonableFn = Callable[[object], object]


class RecordLocalChatFn(Protocol):
    def __call__(
        self,
        *,
        text: str,
        from_id: str = "local",
        to_id: str = "^all",
        channel_index: int = 0,
        message_id: Optional[int] = None,
        reply_id: Optional[int] = None,
        emoji: Optional[str] = None,
        emoji_codepoint: Optional[int] = None,
        is_reaction: bool = False,
        ack_requested: bool = False,
        retry_of: Optional[int] = None,
        bot_command: Optional[str] = None,
    ) -> None:
        ...


class SendReactionPacketFn(Protocol):
    def __call__(
        self,
        *,
        iface: object,
        destination_id: str,
        channel_index: int,
        reply_id: int,
        emoji_codepoint: int,
        emoji_text: str,
        want_ack: bool,
    ) -> object:
        ...


class SendChatMessageFn(Protocol):
    def __call__(
        self,
        *,
        text: object,
        destination: object = None,
        channel_index: Optional[int] = None,
        reply_id: Optional[int] = None,
        retry_of: Optional[int] = None,
        emoji: object = None,
        iface: object,
        send_lock: object,
        send_reaction_packet_fn: SendReactionPacketFn,
        local_node_id_fn: LocalNodeIdFn,
        record_local_chat_fn: RecordLocalChatFn,
        chat_max_bytes: int,
        normalize_single_emoji_fn: NormalizeSingleEmojiFn,
        to_int_fn: ToIntFn,
        now_text_fn: UtcNowFn,
        get_delivery_state_fn: Optional[Callable[[object], object]] = None,
        outgoing_retry_wait_seconds: float = ...,
        outgoing_retry_poll_seconds: float = ...,
        outgoing_retry_limit: int = ...,
        outgoing_retry_async: bool = ...,
        sleep_fn: Callable[[float], None] = ...,
    ) -> dict[str, object]:
        ...


class BuildStateWithSensitiveFn(Protocol):
    def __call__(
        self,
        *,
        iface: object,
        tracker: object,
        started_at: float,
        target: str,
        show_secrets: bool,
        storage_probe_path: Optional[str],
        revision_info: object,
        sensitive_field_names: set[str],
    ) -> StatePayload:
        ...


class BuildStateFn(Protocol):
    def __call__(
        self,
        *,
        iface: object,
        tracker: object,
        started_at: float,
        target: str,
        show_secrets: bool,
        storage_probe_path: Optional[str],
        revision_info: object,
    ) -> StatePayload:
        ...


class BuildStateSnapshotLoaderFn(Protocol):
    def __call__(
        self,
        *,
        iface: object,
        tracker: object,
        started_at: float,
        target: str,
        show_secrets: bool,
        storage_probe_path: Optional[str],
        revision_info: RevisionInfo,
        build_state_fn: BuildStateFn,
    ) -> StateFn:
        ...


class BuildNodeHistoryLoaderFn(Protocol):
    def __call__(
        self,
        history_store: object | None,
        *,
        default_hours: int,
        default_points: int,
    ) -> NodeHistoryFn:
        ...


class BuildOnlineActivityLoaderFn(Protocol):
    def __call__(
        self,
        history_store: object | None,
        *,
        default_hours: int,
    ) -> OnlineActivityFn:
        ...


class BuildSummaryMetricsLoaderFn(Protocol):
    def __call__(
        self,
        history_store: object | None,
        *,
        default_hours: int,
    ) -> SummaryMetricsHistoryFn:
        ...


class BuildSendChatLoaderFn(Protocol):
    def __call__(
        self,
        *,
        iface: object,
        tracker: object,
        send_lock: object,
        send_chat_message_fn: SendChatMessageFn,
        send_reaction_packet_fn: SendReactionPacketFn,
        get_local_node_id_fn: GetLocalNodeIdFn,
        chat_max_bytes: int,
        normalize_single_emoji_fn: NormalizeSingleEmojiFn,
        to_int_fn: ToIntFn,
        utc_now_fn: UtcNowFn,
    ) -> SendChatFn:
        ...


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
        direct_keys: DirectEdgeKeys,
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
        *,
        ack_from_id: object = None,
        ack_to_id: object = None,
    ) -> bool:
        ...


class ApplyRoutingDeliveryUpdateFn(Protocol):
    def __call__(
        self,
        decoded: object,
        *,
        from_id: object = None,
        to_id: object = None,
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
        rx_snr: Optional[object],
        rx_rssi: Optional[object],
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
    ) -> DirectEdgeKeys:
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
