import os
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from .dashboard_loaders import DashboardRuntimeLoaders
from .dashboard_args_contracts import DashboardArgs
from .dashboard_runtime_loader_contracts import (
    BuildDashboardRuntimeLoaderDependenciesFromLegacyArgsFn,
    BuildDashboardRuntimeLoadersFn,
    BuildDashboardRuntimeLoadersWithDependenciesFn,
)
from .dashboard_runtime_loader_dependencies import (
    build_dashboard_runtime_loader_dependencies_from_legacy_args,
)
from .dashboard_runtime_loaders import build_dashboard_runtime_loaders_with_dependencies
from .dashboard_setup_contracts import (
    DashboardTrackerFactory,
    DashboardTrackerLike,
    HistoryStoreFactory,
    HistoryStoreLike,
    OpenOptionalHistoryStoreFn,
    PrintLineFn,
    SeedTrackerIfEmptyFn,
)
from .revision import RevisionInfo
from .runtime_types import (
    BuildNodeHistoryLoaderFn,
    BuildOnlineActivityLoaderFn,
    BuildSummaryMetricsLoaderFn,
    BuildSendChatLoaderFn,
    BuildStateFn,
    BuildStateSnapshotLoaderFn,
    GetLocalNodeIdFn,
    MeshTargetLabelFn,
    NodeHistoryFn,
    NormalizeSingleEmojiFn,
    OpenMeshInterfaceFn,
    OnlineActivityFn,
    SummaryMetricsHistoryFn,
    RevisionInfoFn,
    SendChatFn,
    SendChatMessageFn,
    SendReactionPacketFn,
    SeedTrackerFn,
    StateFn,
    SubscribeFn,
    ToIntFn,
    UtcNowFn,
)
from .dashboard_setup import (
    open_optional_history_store,
    seed_tracker_if_empty,
)
from .send_chat_contracts import SendLock
from .history_profile import (
    build_profiled_history_db_path,
    resolve_history_profile_key,
)


@dataclass(frozen=True)
class DashboardRuntimeContext:
    target: str
    iface: object
    history_db_path: str
    history_store: Optional[HistoryStoreLike]
    tracker: DashboardTrackerLike
    send_lock: SendLock
    started_at: float
    revision_info: RevisionInfo
    state_fn: StateFn
    node_history_fn: NodeHistoryFn
    online_activity_fn: OnlineActivityFn
    summary_metrics_fn: SummaryMetricsHistoryFn
    send_chat_fn: SendChatFn
    history_enabled: bool


def build_dashboard_runtime_context(
    args: DashboardArgs,
    *,
    mesh_target_label_fn: MeshTargetLabelFn,
    open_mesh_interface_fn: OpenMeshInterfaceFn,
    history_store_cls: HistoryStoreFactory,
    dashboard_tracker_cls: DashboardTrackerFactory,
    subscribe_fn: SubscribeFn,
    seed_tracker_fn: SeedTrackerFn,
    revision_info_fn: RevisionInfoFn,
    send_chat_message_fn: SendChatMessageFn,
    send_reaction_packet_fn: SendReactionPacketFn,
    get_local_node_id_fn: GetLocalNodeIdFn,
    normalize_single_emoji_fn: NormalizeSingleEmojiFn,
    to_int_fn: ToIntFn,
    utc_now_fn: UtcNowFn,
    build_state_fn: BuildStateFn,
    build_state_snapshot_loader_fn: BuildStateSnapshotLoaderFn,
    build_node_history_loader_fn: BuildNodeHistoryLoaderFn,
    build_online_activity_loader_fn: BuildOnlineActivityLoaderFn,
    build_summary_metrics_loader_fn: BuildSummaryMetricsLoaderFn,
    build_send_chat_loader_fn: BuildSendChatLoaderFn,
    default_chat_max_bytes: int,
    print_fn: PrintLineFn = print,
    lock_factory: Callable[[], SendLock] = threading.Lock,
    now_unix_fn: Callable[[], float] = time.time,
    resolve_history_db_path_fn: Callable[[str], str] = lambda path: os.path.abspath(
        os.path.expanduser(path)
    ),
    open_optional_history_store_fn: OpenOptionalHistoryStoreFn = open_optional_history_store,
    seed_tracker_if_empty_fn: SeedTrackerIfEmptyFn = seed_tracker_if_empty,
    build_dashboard_runtime_loaders_fn: Optional[BuildDashboardRuntimeLoadersFn] = None,
    build_dashboard_runtime_loader_dependencies_from_legacy_args_fn: BuildDashboardRuntimeLoaderDependenciesFromLegacyArgsFn = build_dashboard_runtime_loader_dependencies_from_legacy_args,
    build_dashboard_runtime_loaders_with_dependencies_fn: BuildDashboardRuntimeLoadersWithDependenciesFn = build_dashboard_runtime_loaders_with_dependencies,
) -> DashboardRuntimeContext:
    target = mesh_target_label_fn(args)
    print_fn(f"Connecting to {target} ...")
    iface = open_mesh_interface_fn(args)

    history_db_base_path = resolve_history_db_path_fn(args.history_db)
    history_profile_key = resolve_history_profile_key(
        iface=iface,
        get_local_node_id_fn=get_local_node_id_fn,
        mesh_target_label=target,
        wait_for_id_seconds=2.0,
    )
    history_db_path = build_profiled_history_db_path(
        history_db_base_path,
        profile_key=history_profile_key,
    )
    history_store: Optional[HistoryStoreLike] = open_optional_history_store_fn(
        args,
        history_store_cls=history_store_cls,
        history_db_path=history_db_path,
    )

    tracker = dashboard_tracker_cls(packet_limit=args.packet_limit, history_store=history_store)
    send_lock = lock_factory()
    subscribe_fn(tracker.on_receive, "meshtastic.receive")
    on_connection_established = getattr(tracker, "on_connection_established", None)
    if callable(on_connection_established):
        subscribe_fn(on_connection_established, "meshtastic.connection.established")
    on_connection_lost = getattr(tracker, "on_connection_lost", None)
    if callable(on_connection_lost):
        subscribe_fn(on_connection_lost, "meshtastic.connection.lost")
    bootstrap_connection_state = getattr(tracker, "bootstrap_connection_state", None)
    if callable(bootstrap_connection_state):
        try:
            bootstrap_connection_state(iface)
        except Exception:
            pass
    if bool(getattr(args, "seed_from_node_db", False)):
        seed_tracker_if_empty_fn(tracker, iface, seed_tracker_fn=seed_tracker_fn)
    started_at = now_unix_fn()
    revision_info = revision_info_fn()

    loader_kwargs = {
        "iface": iface,
        "tracker": tracker,
        "send_lock": send_lock,
        "started_at": started_at,
        "target": target,
        "show_secrets": args.show_secrets,
        "history_db_path": history_db_path,
        "revision_info": revision_info,
        "history_store": history_store,
        "default_node_history_hours": args.node_history_hours,
        "default_node_history_points": args.node_history_max_points,
        "send_chat_message_fn": send_chat_message_fn,
        "send_reaction_packet_fn": send_reaction_packet_fn,
        "get_local_node_id_fn": get_local_node_id_fn,
        "default_chat_max_bytes": default_chat_max_bytes,
        "normalize_single_emoji_fn": normalize_single_emoji_fn,
        "to_int_fn": to_int_fn,
        "utc_now_fn": utc_now_fn,
        "build_state_fn": build_state_fn,
        "build_state_snapshot_loader_fn": build_state_snapshot_loader_fn,
        "build_node_history_loader_fn": build_node_history_loader_fn,
        "build_online_activity_loader_fn": build_online_activity_loader_fn,
        "build_summary_metrics_loader_fn": build_summary_metrics_loader_fn,
        "build_send_chat_loader_fn": build_send_chat_loader_fn,
    }

    if build_dashboard_runtime_loaders_fn is not None:
        loaders = build_dashboard_runtime_loaders_fn(**loader_kwargs)
    else:
        loader_dependencies = (
            build_dashboard_runtime_loader_dependencies_from_legacy_args_fn(
                **loader_kwargs
            )
        )
        loaders = build_dashboard_runtime_loaders_with_dependencies_fn(
            dependencies=loader_dependencies
        )

    # Optional: attach radio settings application hook.
    # We hang this off state_fn to avoid threading new dependencies through the
    # entire server wiring. (Same trick as state_fn.lite.)
    try:
        from .services_radio_settings import apply_radio_settings as _apply_radio_settings
    except Exception:
        _apply_radio_settings = None

    if _apply_radio_settings is not None:
        def _apply_radio_settings_fn(request):  # type: ignore[no-redef]
            return _apply_radio_settings(
                request,
                iface=iface,
                send_lock=send_lock,
                history_store=history_store,
                tracker=tracker,
            )

        setattr(loaders.state_fn, "apply_radio_settings_fn", _apply_radio_settings_fn)

    # Optional: attach channel settings application hook.
    try:
        from .services_channels import apply_channel_settings as _apply_channel_settings
    except Exception:
        _apply_channel_settings = None

    if _apply_channel_settings is not None:
        def _apply_channel_settings_fn(request):  # type: ignore[no-redef]
            return _apply_channel_settings(
                request,
                iface=iface,
                send_lock=send_lock,
                show_secrets=args.show_secrets,
            )

        setattr(loaders.state_fn, "apply_channel_settings_fn", _apply_channel_settings_fn)

    return DashboardRuntimeContext(
        target=target,
        iface=iface,
        history_db_path=history_db_path,
        history_store=history_store,
        tracker=tracker,
        send_lock=send_lock,
        started_at=started_at,
        revision_info=revision_info,
        state_fn=loaders.state_fn,
        node_history_fn=loaders.node_history_fn,
        online_activity_fn=loaders.online_activity_fn,
        summary_metrics_fn=loaders.summary_metrics_fn,
        send_chat_fn=loaders.send_chat_fn,
        history_enabled=history_store is not None,
    )
