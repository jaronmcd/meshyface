from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping, Optional, Protocol

if TYPE_CHECKING:
    from .api_input_bots import ZorkBotToggleRequest
    from .api_input_bbs import BbsHostRequest, BbsSettingsRequest
    from .api_input_channels import ChannelSettingsRequest
    from .api_input_chat import ChatSendRequest
    from .api_input_custom_telemetry import CustomTelemetrySettingsRequest
    from .api_input_history import NodeHistoryQuery, OnlineActivityQuery
    from .api_input_meshyface_profile import MeshyfaceProfileThemeRequest
    from .api_input_network_tools import NetworkToolRequest
    from .api_input_radio import RadioSettingsRequest
    from .api_input_raw_packets import RawPacketCaptureSettingsRequest
    from .api_input_theme import ThemeSettingsRequest
    from .api_input_zork import StandaloneZorkRequest
else:
    BbsHostRequest = object
    BbsSettingsRequest = object
    ChannelSettingsRequest = object
    ChatSendRequest = object
    CustomTelemetrySettingsRequest = object
    MeshyfaceProfileThemeRequest = object
    NodeHistoryQuery = object
    NetworkToolRequest = object
    OnlineActivityQuery = object
    RadioSettingsRequest = object
    RawPacketCaptureSettingsRequest = object
    ThemeSettingsRequest = object
    StandaloneZorkRequest = object
    ZorkBotToggleRequest = object
from .http_handler_contracts import DashboardHttpHandler
from .state_payload_contracts import DashboardStatePayload

StatePayload = DashboardStatePayload | dict[str, object]


class StateFn(Protocol):
    def __call__(self) -> StatePayload:
        ...


class NodeHistoryFn(Protocol):
    def __call__(
        self,
        node_id: str,
        hours_override: Optional[int],
        points_override: Optional[int],
    ) -> dict[str, object]:
        ...


class OnlineActivityFn(Protocol):
    def __call__(self, hours_override: Optional[int]) -> dict[str, object]:
        ...


class SummaryMetricsHistoryFn(Protocol):
    def __call__(
        self,
        hours_override: Optional[int],
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


class SendMeshyfaceProfileFn(Protocol):
    def __call__(
        self,
        *,
        theme: object,
        channel_index: object = 0,
    ) -> dict[str, object]:
        ...


class GetThemeSettingsFn(Protocol):
    def __call__(self) -> dict[str, object]:
        ...


class GetBbsSettingsFn(Protocol):
    def __call__(self) -> dict[str, object]:
        ...


class GetBbsHostRuntimeFn(Protocol):
    def __call__(self) -> dict[str, object]:
        ...


class SetThemePresetFn(Protocol):
    def __call__(self, payload: object) -> dict[str, object]:
        ...


class SetBbsSettingsFn(Protocol):
    def __call__(self, settings: object) -> dict[str, object]:
        ...


class SetZorkBotEnabledFn(Protocol):
    def __call__(self, enabled: bool) -> dict[str, object]:
        ...


class SetPingBotEnabledFn(Protocol):
    def __call__(self, enabled: bool) -> dict[str, object]:
        ...


class SetPingBotMessageOnlyFn(Protocol):
    def __call__(self, message_only: bool) -> dict[str, object]:
        ...


class ManageZorkBotFn(Protocol):
    def __call__(self, action: object, *, peer_id: object = None) -> dict[str, object]:
        ...


class StartBbsHostFn(Protocol):
    def __call__(self, request: BbsHostRequest) -> dict[str, object]:
        ...


class StopBbsHostFn(Protocol):
    def __call__(self) -> dict[str, object]:
        ...


class AppendBbsHostPostFn(Protocol):
    def __call__(self, request: BbsHostRequest) -> dict[str, object]:
        ...


class GetCustomTelemetrySettingsFn(Protocol):
    def __call__(self) -> dict[str, object]:
        ...


class SetCustomTelemetrySettingsFn(Protocol):
    def __call__(self, rules: object) -> dict[str, object]:
        ...


class SetRawPacketCaptureSettingsFn(Protocol):
    def __call__(self, settings: object) -> dict[str, object]:
        ...


class ToIntFn(Protocol):
    def __call__(self, value: object) -> Optional[int]:
        ...


class ParseNodeHistoryRequestFn(Protocol):
    def __call__(
        self,
        raw_query: str,
        *,
        to_int_fn: ToIntFn,
    ) -> NodeHistoryQuery:
        ...


class ParseOnlineActivityRequestFn(Protocol):
    def __call__(
        self,
        raw_query: str,
        *,
        to_int_fn: ToIntFn,
    ) -> OnlineActivityQuery:
        ...


class EmptyNodeHistoryFn(Protocol):
    def __call__(self, node_id: str) -> dict[str, object]:
        ...


class EmptyOnlineActivityFn(Protocol):
    def __call__(self, hours: int) -> dict[str, object]:
        ...


class EmptySummaryMetricsFn(Protocol):
    def __call__(self, hours: int) -> dict[str, object]:
        ...


class ValidateContentLengthFn(Protocol):
    def __call__(
        self,
        headers: Mapping[str, object],
        *,
        to_int_fn: ToIntFn,
        max_bytes: int = 8192,
    ) -> int:
        ...


class ParseChatSendRequestFn(Protocol):
    def __call__(
        self,
        raw_body: bytes,
        *,
        to_int_fn: ToIntFn,
    ) -> ChatSendRequest:
        ...


class ParseMeshyfaceProfileThemeRequestFn(Protocol):
    def __call__(
        self,
        raw_body: bytes,
        *,
        to_int_fn: ToIntFn,
    ) -> MeshyfaceProfileThemeRequest:
        ...


class ParseThemeSettingsRequestFn(Protocol):
    def __call__(self, raw_body: bytes) -> ThemeSettingsRequest:
        ...


class ParseBbsSettingsRequestFn(Protocol):
    def __call__(self, raw_body: bytes) -> BbsSettingsRequest:
        ...


class ParseBbsHostRequestFn(Protocol):
    def __call__(self, raw_body: bytes) -> BbsHostRequest:
        ...


class ParseCustomTelemetrySettingsRequestFn(Protocol):
    def __call__(self, raw_body: bytes) -> CustomTelemetrySettingsRequest:
        ...


class ParseRawPacketCaptureSettingsRequestFn(Protocol):
    def __call__(self, raw_body: bytes) -> RawPacketCaptureSettingsRequest:
        ...


class ParseRadioSettingsRequestFn(Protocol):
    def __call__(self, raw_body: bytes) -> RadioSettingsRequest:
        ...


class ParseChannelSettingsRequestFn(Protocol):
    def __call__(self, raw_body: bytes) -> ChannelSettingsRequest:
        ...


class ParseNetworkToolRequestFn(Protocol):
    def __call__(
        self,
        raw_body: bytes,
        *,
        to_int_fn: ToIntFn,
    ) -> NetworkToolRequest:
        ...


class ParseZorkBotToggleRequestFn(Protocol):
    def __call__(self, raw_body: bytes) -> ZorkBotToggleRequest:
        ...


class ApplyRadioSettingsFn(Protocol):
    def __call__(self, request: RadioSettingsRequest) -> dict[str, object]:
        ...


class ApplyChannelSettingsFn(Protocol):
    def __call__(self, request: ChannelSettingsRequest) -> dict[str, object]:
        ...


class ParseStandaloneZorkRequestFn(Protocol):
    def __call__(self, raw_body: bytes) -> StandaloneZorkRequest:
        ...


class PlayStandaloneZorkFn(Protocol):
    def __call__(
        self,
        *,
        text: object,
        session_id: object = None,
    ) -> dict[str, object]:
        ...


class RunNetworkToolFn(Protocol):
    def __call__(self, request: NetworkToolRequest) -> dict[str, object]:
        ...


class ScheduleBackendRestartFn(Protocol):
    def __call__(self) -> dict[str, object]:
        ...


class WriteHtmlResponseFn(Protocol):
    def __call__(
        self,
        handler: DashboardHttpHandler,
        *,
        html_text: str,
        no_store: bool = False,
        extra_headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        ...


class WriteJsonResponseFn(Protocol):
    def __call__(
        self,
        handler: DashboardHttpHandler,
        *,
        status_code: int,
        payload_obj: object,
        no_store: bool = False,
        extra_headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        ...


class WriteTextResponseFn(Protocol):
    def __call__(
        self,
        handler: DashboardHttpHandler,
        *,
        status_code: int,
        text: str,
        no_store: bool = False,
        extra_headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        ...


class ApiMetricsRecorder(Protocol):
    def record_state_poll_request(self) -> None:
        ...

    def record_state_poll_error(self) -> None:
        ...

    def record_write_auth_denied(self) -> None:
        ...

    def record_private_mode_block(self) -> None:
        ...

    def snapshot(self) -> dict[str, int]:
        ...


@dataclass(frozen=True)
class DashboardGetRouteDependencies:
    html_text: str
    state_fn: StateFn
    node_history_fn: Optional[NodeHistoryFn]
    online_activity_fn: Optional[OnlineActivityFn]
    summary_metrics_fn: Optional[SummaryMetricsHistoryFn]
    default_node_history_hours: int
    to_int_fn: ToIntFn
    parse_node_history_request_fn: ParseNodeHistoryRequestFn
    parse_online_activity_request_fn: ParseOnlineActivityRequestFn
    empty_node_history_fn: EmptyNodeHistoryFn
    empty_online_activity_fn: EmptyOnlineActivityFn
    empty_summary_metrics_fn: EmptySummaryMetricsFn
    write_html_response_fn: WriteHtmlResponseFn
    write_json_response_fn: WriteJsonResponseFn
    write_text_response_fn: WriteTextResponseFn
    get_theme_settings_fn: Optional[GetThemeSettingsFn] = None
    get_bbs_settings_fn: Optional[GetBbsSettingsFn] = None
    get_bbs_host_runtime_fn: Optional[GetBbsHostRuntimeFn] = None
    get_custom_telemetry_settings_fn: Optional[GetCustomTelemetrySettingsFn] = None
    private_mode: bool = False
    api_metrics: Optional[ApiMetricsRecorder] = None
    dashboard_asset_map: Mapping[str, tuple[str, bytes]] | None = None


@dataclass(frozen=True)
class DashboardPostRouteDependencies:
    send_chat_fn: Optional[SendChatFn]
    to_int_fn: ToIntFn
    validate_content_length_fn: ValidateContentLengthFn
    parse_chat_send_request_fn: ParseChatSendRequestFn
    write_json_response_fn: WriteJsonResponseFn
    send_meshyface_profile_fn: Optional[SendMeshyfaceProfileFn] = None
    parse_meshyface_profile_theme_request_fn: Optional[
        ParseMeshyfaceProfileThemeRequestFn
    ] = None
    set_theme_preset_fn: Optional[SetThemePresetFn] = None
    parse_theme_settings_request_fn: Optional[ParseThemeSettingsRequestFn] = None
    set_bbs_settings_fn: Optional[SetBbsSettingsFn] = None
    parse_bbs_settings_request_fn: Optional[ParseBbsSettingsRequestFn] = None
    set_zork_bot_enabled_fn: Optional[SetZorkBotEnabledFn] = None
    set_ping_bot_enabled_fn: Optional[SetPingBotEnabledFn] = None
    set_ping_bot_message_only_fn: Optional[SetPingBotMessageOnlyFn] = None
    manage_zork_bot_fn: Optional[ManageZorkBotFn] = None
    parse_zork_bot_toggle_request_fn: Optional[ParseZorkBotToggleRequestFn] = None
    start_bbs_host_fn: Optional[StartBbsHostFn] = None
    stop_bbs_host_fn: Optional[StopBbsHostFn] = None
    append_bbs_host_post_fn: Optional[AppendBbsHostPostFn] = None
    parse_bbs_host_request_fn: Optional[ParseBbsHostRequestFn] = None
    set_custom_telemetry_settings_fn: Optional[SetCustomTelemetrySettingsFn] = None
    parse_custom_telemetry_settings_request_fn: Optional[ParseCustomTelemetrySettingsRequestFn] = None
    set_raw_packet_capture_settings_fn: Optional[SetRawPacketCaptureSettingsFn] = None
    parse_raw_packet_capture_settings_request_fn: Optional[ParseRawPacketCaptureSettingsRequestFn] = None
    apply_radio_settings_fn: Optional[ApplyRadioSettingsFn] = None
    parse_radio_settings_request_fn: Optional[ParseRadioSettingsRequestFn] = None
    apply_channel_settings_fn: Optional[ApplyChannelSettingsFn] = None
    parse_channel_settings_request_fn: Optional[ParseChannelSettingsRequestFn] = None
    play_standalone_zork_fn: Optional[PlayStandaloneZorkFn] = None
    parse_standalone_zork_request_fn: Optional[ParseStandaloneZorkRequestFn] = None
    run_network_tool_fn: Optional[RunNetworkToolFn] = None
    parse_network_tool_request_fn: Optional[ParseNetworkToolRequestFn] = None
    schedule_backend_restart_fn: Optional[ScheduleBackendRestartFn] = None
    api_token: Optional[str] = None
    private_mode: bool = False
    api_metrics: Optional[ApiMetricsRecorder] = None
