from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Protocol

from .dashboard_setup_contracts import HistoryStoreLike
from .revision import RevisionInfo
from .runtime_types import (
    BuildNodeHistoryLoaderFn,
    BuildSummaryMetricsLoaderFn,
    BuildSendChatLoaderFn,
    BuildStateFn,
    BuildStateSnapshotLoaderFn,
    GetLocalNodeIdFn,
    NormalizeSingleEmojiFn,
    SendChatMessageFn,
    SendReactionPacketFn,
    ToIntFn,
    UtcNowFn,
)
from .send_chat_contracts import SendLock

if TYPE_CHECKING:
    from .dashboard_runtime_loaders import DashboardRuntimeLoaders


@dataclass(frozen=True)
class DashboardRuntimeLoaderDependencies:
    iface: object
    tracker: object
    send_lock: SendLock
    started_at: float
    target: str
    show_secrets: bool
    history_db_path: str
    revision_info: RevisionInfo
    history_store: Optional[HistoryStoreLike]
    default_node_history_hours: int
    default_node_history_points: int
    send_chat_message_fn: SendChatMessageFn
    send_reaction_packet_fn: SendReactionPacketFn
    get_local_node_id_fn: GetLocalNodeIdFn
    default_chat_max_bytes: int
    normalize_single_emoji_fn: NormalizeSingleEmojiFn
    to_int_fn: ToIntFn
    utc_now_fn: UtcNowFn
    build_state_fn: BuildStateFn
    build_state_snapshot_loader_fn: BuildStateSnapshotLoaderFn
    build_node_history_loader_fn: BuildNodeHistoryLoaderFn
    build_summary_metrics_loader_fn: BuildSummaryMetricsLoaderFn
    build_send_chat_loader_fn: BuildSendChatLoaderFn


class BuildDashboardRuntimeLoaderDependenciesFromLegacyArgsFn(Protocol):
    def __call__(
        self,
        *,
        iface: object,
        tracker: object,
        send_lock: SendLock,
        started_at: float,
        target: str,
        show_secrets: bool,
        history_db_path: str,
        revision_info: RevisionInfo,
        history_store: Optional[HistoryStoreLike],
        default_node_history_hours: int,
        default_node_history_points: int,
        send_chat_message_fn: SendChatMessageFn,
        send_reaction_packet_fn: SendReactionPacketFn,
        get_local_node_id_fn: GetLocalNodeIdFn,
        default_chat_max_bytes: int,
        normalize_single_emoji_fn: NormalizeSingleEmojiFn,
        to_int_fn: ToIntFn,
        utc_now_fn: UtcNowFn,
        build_state_fn: BuildStateFn,
        build_state_snapshot_loader_fn: BuildStateSnapshotLoaderFn,
        build_node_history_loader_fn: BuildNodeHistoryLoaderFn,
        build_summary_metrics_loader_fn: BuildSummaryMetricsLoaderFn,
        build_send_chat_loader_fn: BuildSendChatLoaderFn,
    ) -> DashboardRuntimeLoaderDependencies:
        ...


class BuildDashboardRuntimeLoadersWithDependenciesFn(Protocol):
    def __call__(
        self,
        *,
        dependencies: DashboardRuntimeLoaderDependencies,
    ) -> "DashboardRuntimeLoaders":
        ...


class BuildDashboardRuntimeLoadersFn(Protocol):
    def __call__(
        self,
        *,
        iface: object,
        tracker: object,
        send_lock: SendLock,
        started_at: float,
        target: str,
        show_secrets: bool,
        history_db_path: str,
        revision_info: RevisionInfo,
        history_store: Optional[HistoryStoreLike],
        default_node_history_hours: int,
        default_node_history_points: int,
        send_chat_message_fn: SendChatMessageFn,
        send_reaction_packet_fn: SendReactionPacketFn,
        get_local_node_id_fn: GetLocalNodeIdFn,
        default_chat_max_bytes: int,
        normalize_single_emoji_fn: NormalizeSingleEmojiFn,
        to_int_fn: ToIntFn,
        utc_now_fn: UtcNowFn,
        build_state_fn: BuildStateFn,
        build_state_snapshot_loader_fn: BuildStateSnapshotLoaderFn,
        build_node_history_loader_fn: BuildNodeHistoryLoaderFn,
        build_summary_metrics_loader_fn: BuildSummaryMetricsLoaderFn,
        build_send_chat_loader_fn: BuildSendChatLoaderFn,
    ) -> "DashboardRuntimeLoaders":
        ...
