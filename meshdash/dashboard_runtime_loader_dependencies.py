from typing import Optional

from .dashboard_runtime_loader_contracts import DashboardRuntimeLoaderDependencies
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


def build_dashboard_runtime_loader_dependencies_from_legacy_args(
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
    return DashboardRuntimeLoaderDependencies(
        iface=iface,
        tracker=tracker,
        send_lock=send_lock,
        started_at=started_at,
        target=target,
        show_secrets=show_secrets,
        history_db_path=history_db_path,
        revision_info=revision_info,
        history_store=history_store,
        default_node_history_hours=default_node_history_hours,
        default_node_history_points=default_node_history_points,
        send_chat_message_fn=send_chat_message_fn,
        send_reaction_packet_fn=send_reaction_packet_fn,
        get_local_node_id_fn=get_local_node_id_fn,
        default_chat_max_bytes=default_chat_max_bytes,
        normalize_single_emoji_fn=normalize_single_emoji_fn,
        to_int_fn=to_int_fn,
        utc_now_fn=utc_now_fn,
        build_state_fn=build_state_fn,
        build_state_snapshot_loader_fn=build_state_snapshot_loader_fn,
        build_node_history_loader_fn=build_node_history_loader_fn,
        build_summary_metrics_loader_fn=build_summary_metrics_loader_fn,
        build_send_chat_loader_fn=build_send_chat_loader_fn,
    )
