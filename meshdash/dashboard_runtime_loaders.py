from collections.abc import Mapping
from dataclasses import dataclass
from typing import Optional

from .dashboard_runtime_loader_contracts import DashboardRuntimeLoaderDependencies
from .dashboard_runtime_loader_dependencies import (
    build_dashboard_runtime_loader_dependencies_from_legacy_args,
)
from .dashboard_setup_contracts import HistoryStoreLike
from .revision import RevisionInfo
from .runtime_types import (
    BuildNodeHistoryLoaderFn,
    BuildOnlineActivityLoaderFn,
    BuildSummaryMetricsLoaderFn,
    BuildSendChatLoaderFn,
    BuildStateFn,
    BuildStateSnapshotLoaderFn,
    GetLocalNodeIdFn,
    NodeHistoryFn,
    NormalizeSingleEmojiFn,
    OnlineActivityFn,
    SummaryMetricsHistoryFn,
    SendChatFn,
    SendChatMessageFn,
    SendReactionPacketFn,
    StateFn,
    ToIntFn,
    UtcNowFn,
)
from .send_chat_contracts import SendLock


@dataclass(frozen=True)
class DashboardRuntimeLoaders:
    state_fn: StateFn
    node_history_fn: NodeHistoryFn
    online_activity_fn: OnlineActivityFn
    summary_metrics_fn: SummaryMetricsHistoryFn
    send_chat_fn: SendChatFn


def _extract_state_summary(payload: object) -> Mapping[str, object] | None:
    if isinstance(payload, Mapping):
        summary = payload.get("summary")
        return summary if isinstance(summary, Mapping) else None
    summary = getattr(payload, "summary", None)
    return summary if isinstance(summary, Mapping) else None


def _copy_state_fn_attrs(target_fn: object, source_fn: object) -> None:
    for name in (
        "etag",
        "raw_my_info",
        "raw_metadata",
        "raw_local_state",
        "raw_nodes_full",
        "_sensitive_field_names",
    ):
        attr = getattr(source_fn, name, None)
        if attr is None:
            continue
        try:
            setattr(target_fn, name, attr)
        except Exception:
            continue


def _with_summary_persistence(
    *,
    base_state_fn: StateFn,
    history_store: object | None,
) -> StateFn:
    save_summary_fn = getattr(history_store, "save_summary_metrics", None)
    if not callable(save_summary_fn):
        return base_state_fn

    def _persist_summary(payload: object) -> None:
        summary = _extract_state_summary(payload)
        if summary is None:
            return
        try:
            save_summary_fn(summary)
        except Exception:
            pass

    def _wrapped_state_fn() -> object:
        payload = base_state_fn()
        _persist_summary(payload)
        return payload

    _copy_state_fn_attrs(_wrapped_state_fn, base_state_fn)

    lite_fn = getattr(base_state_fn, "lite", None)
    if callable(lite_fn):
        def _wrapped_state_lite_fn() -> object:
            payload = lite_fn()
            _persist_summary(payload)
            return payload

        _copy_state_fn_attrs(_wrapped_state_lite_fn, lite_fn)
        try:
            setattr(_wrapped_state_fn, "lite", _wrapped_state_lite_fn)
        except Exception:
            pass

    return _wrapped_state_fn


def build_dashboard_runtime_loaders(
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
    build_online_activity_loader_fn: BuildOnlineActivityLoaderFn,
    build_summary_metrics_loader_fn: BuildSummaryMetricsLoaderFn,
    build_send_chat_loader_fn: BuildSendChatLoaderFn,
) -> DashboardRuntimeLoaders:
    dependencies = build_dashboard_runtime_loader_dependencies_from_legacy_args(
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
        build_online_activity_loader_fn=build_online_activity_loader_fn,
        build_summary_metrics_loader_fn=build_summary_metrics_loader_fn,
        build_send_chat_loader_fn=build_send_chat_loader_fn,
    )
    return build_dashboard_runtime_loaders_with_dependencies(dependencies=dependencies)


def build_dashboard_runtime_loaders_with_dependencies(
    *,
    dependencies: DashboardRuntimeLoaderDependencies,
) -> DashboardRuntimeLoaders:
    state_fn = dependencies.build_state_snapshot_loader_fn(
        iface=dependencies.iface,
        tracker=dependencies.tracker,
        started_at=dependencies.started_at,
        target=dependencies.target,
        show_secrets=dependencies.show_secrets,
        storage_probe_path=dependencies.history_db_path,
        revision_info=dependencies.revision_info,
        build_state_fn=dependencies.build_state_fn,
    )
    state_fn = _with_summary_persistence(
        base_state_fn=state_fn,
        history_store=dependencies.history_store,
    )

    node_history_fn = dependencies.build_node_history_loader_fn(
        history_store=dependencies.history_store,
        default_hours=dependencies.default_node_history_hours,
        default_points=dependencies.default_node_history_points,
    )
    online_activity_fn = dependencies.build_online_activity_loader_fn(
        history_store=dependencies.history_store,
        default_hours=dependencies.default_node_history_hours,
    )
    summary_metrics_fn = dependencies.build_summary_metrics_loader_fn(
        history_store=dependencies.history_store,
        default_hours=dependencies.default_node_history_hours,
    )

    send_chat_fn = dependencies.build_send_chat_loader_fn(
        iface=dependencies.iface,
        tracker=dependencies.tracker,
        send_lock=dependencies.send_lock,
        send_chat_message_fn=dependencies.send_chat_message_fn,
        send_reaction_packet_fn=dependencies.send_reaction_packet_fn,
        get_local_node_id_fn=dependencies.get_local_node_id_fn,
        chat_max_bytes=dependencies.default_chat_max_bytes,
        normalize_single_emoji_fn=dependencies.normalize_single_emoji_fn,
        to_int_fn=dependencies.to_int_fn,
        utc_now_fn=dependencies.utc_now_fn,
    )

    return DashboardRuntimeLoaders(
        state_fn=state_fn,
        node_history_fn=node_history_fn,
        online_activity_fn=online_activity_fn,
        summary_metrics_fn=summary_metrics_fn,
        send_chat_fn=send_chat_fn,
    )
