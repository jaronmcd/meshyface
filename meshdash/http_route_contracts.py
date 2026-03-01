from dataclasses import dataclass
from typing import Mapping, Optional, Protocol

from .api_inputs import (
    ChatSendRequest,
    NodeHistoryQuery,
    OnlineActivityQuery,
    RadioSettingsRequest,
    ThemeSettingsRequest,
)
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
    def __call__(self, hours_override: Optional[int]) -> dict[str, object]:
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


class GetThemeSettingsFn(Protocol):
    def __call__(self) -> dict[str, object]:
        ...


class SetThemePresetFn(Protocol):
    def __call__(self, preset_name: object) -> dict[str, object]:
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


class ParseThemeSettingsRequestFn(Protocol):
    def __call__(self, raw_body: bytes) -> ThemeSettingsRequest:
        ...


class ParseRadioSettingsRequestFn(Protocol):
    def __call__(self, raw_body: bytes) -> RadioSettingsRequest:
        ...


class ApplyRadioSettingsFn(Protocol):
    def __call__(self, request: RadioSettingsRequest) -> dict[str, object]:
        ...


class WriteHtmlResponseFn(Protocol):
    def __call__(
        self,
        handler: DashboardHttpHandler,
        *,
        html_text: str,
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
        extra_headers: Optional[Mapping[str, str]] = None,
    ) -> None:
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


@dataclass(frozen=True)
class DashboardPostRouteDependencies:
    send_chat_fn: Optional[SendChatFn]
    to_int_fn: ToIntFn
    validate_content_length_fn: ValidateContentLengthFn
    parse_chat_send_request_fn: ParseChatSendRequestFn
    write_json_response_fn: WriteJsonResponseFn
    set_theme_preset_fn: Optional[SetThemePresetFn] = None
    parse_theme_settings_request_fn: Optional[ParseThemeSettingsRequestFn] = None
    apply_radio_settings_fn: Optional[ApplyRadioSettingsFn] = None
    parse_radio_settings_request_fn: Optional[ParseRadioSettingsRequestFn] = None
