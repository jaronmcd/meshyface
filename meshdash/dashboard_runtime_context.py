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
from .fault_recorder import FaultRecorder
from .bot_responder import (
    build_mesh_response_bot_from_env as _build_mesh_response_bot_from_env,
)
from .services_standalone_zork import (
    build_standalone_zork_service as _build_standalone_zork_service,
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

    fault_recorder = FaultRecorder(now_unix_fn=now_unix_fn)
    fault_history_fn = fault_recorder.recent_faults
    bot_fault_history_fn = lambda: fault_recorder.recent_faults(source="bot")
    try:
        setattr(loaders.state_fn, "fault_history_fn", fault_history_fn)
    except Exception:
        pass
    try:
        setattr(loaders.state_fn, "record_fault_fn", fault_recorder.record_fault)
    except Exception:
        pass
    try:
        setattr(loaders.state_fn, "bot_fault_history_fn", bot_fault_history_fn)
    except Exception:
        pass
    state_lite_fn = getattr(loaders.state_fn, "lite", None)
    if callable(state_lite_fn):
        try:
            setattr(state_lite_fn, "fault_history_fn", fault_history_fn)
        except Exception:
            pass
        try:
            setattr(state_lite_fn, "bot_fault_history_fn", bot_fault_history_fn)
        except Exception:
            pass

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

    # Optional: expose custom telemetry extraction rules persisted in history DB.
    if history_store is not None:
        get_custom_telemetry_settings_fn = getattr(history_store, "get_custom_telemetry_settings", None)
        set_custom_telemetry_settings_fn = getattr(history_store, "set_custom_telemetry_settings", None)
        if callable(get_custom_telemetry_settings_fn):
            try:
                setattr(loaders.state_fn, "get_custom_telemetry_settings_fn", get_custom_telemetry_settings_fn)
            except Exception:
                pass
            state_lite_fn = getattr(loaders.state_fn, "lite", None)
            if callable(state_lite_fn):
                try:
                    setattr(state_lite_fn, "get_custom_telemetry_settings_fn", get_custom_telemetry_settings_fn)
                except Exception:
                    pass
        if callable(set_custom_telemetry_settings_fn):
            def _set_custom_telemetry_settings(request):
                return set_custom_telemetry_settings_fn(getattr(request, "rules", None))

            try:
                setattr(loaders.state_fn, "set_custom_telemetry_settings_fn", _set_custom_telemetry_settings)
            except Exception:
                pass
            state_lite_fn = getattr(loaders.state_fn, "lite", None)
            if callable(state_lite_fn):
                try:
                    setattr(state_lite_fn, "set_custom_telemetry_settings_fn", _set_custom_telemetry_settings)
                except Exception:
                    pass

    # Optional: attach chat response bot hook (server-side, radio-wide behavior).
    try:
        def _bot_delivery_state_lookup(message_id: int) -> Optional[str]:
            clean_message_id = to_int_fn(message_id)
            if clean_message_id is None or clean_message_id <= 0:
                return None
            recent_chat = getattr(tracker, "recent_chat", None)
            if recent_chat is None:
                return None

            def _scan_recent_chat() -> Optional[str]:
                try:
                    iterator = reversed(recent_chat)
                except Exception:
                    try:
                        iterator = reversed(list(recent_chat))
                    except Exception:
                        return None
                for entry in iterator:
                    if not isinstance(entry, dict):
                        continue
                    if entry.get("local_echo") is not True:
                        continue
                    row_message_id = to_int_fn(
                        entry.get("message_id")
                        or entry.get("messageId")
                        or entry.get("packet_id")
                        or entry.get("packetId")
                    )
                    if row_message_id != clean_message_id:
                        continue
                    state = str(entry.get("delivery_state") or "").strip().lower()
                    return state or None
                return None

            tracker_lock = getattr(tracker, "_lock", None)
            if tracker_lock is not None and hasattr(tracker_lock, "__enter__") and hasattr(tracker_lock, "__exit__"):
                try:
                    with tracker_lock:
                        return _scan_recent_chat()
                except Exception:
                    return _scan_recent_chat()
            return _scan_recent_chat()

        response_bot = _build_mesh_response_bot_from_env(
            send_chat_fn=loaders.send_chat_fn,
            get_local_node_id_fn=get_local_node_id_fn,
            chat_max_bytes=default_chat_max_bytes,
            delivery_state_lookup_fn=_bot_delivery_state_lookup,
            record_fault_fn=fault_recorder.record_fault,
        )
    except Exception:
        response_bot = None

    if response_bot is not None:
        subscribe_fn(response_bot.on_receive, "meshtastic.receive")
        try:
            setattr(loaders.state_fn, "bot_responder", response_bot)
        except Exception:
            pass
        def _bot_settings_fn():
            settings = response_bot.bot_settings()
            settings["ok"] = True
            return settings
        def _apply_bot_settings_fn(request):
            return response_bot.configure(
                enabled=getattr(request, "enabled", None),
                log_enabled=getattr(request, "log_enabled", None),
                game_enabled=getattr(request, "game_enabled", None),
                game_public_start_enabled=getattr(request, "game_public_start_enabled", None),
                command_settings=getattr(request, "command_settings", None),
                hard_disabled_incoming_commands=getattr(
                    request,
                    "hard_disabled_incoming_commands",
                    None,
                ),
                ping_triggers=getattr(request, "ping_triggers", None),
                ping_response_template=getattr(request, "ping_response_template", None),
                pull_reel_symbols=getattr(request, "pull_reel_symbols", None),
                pull_response_template=getattr(request, "pull_response_template", None),
                joke_triggers=getattr(request, "joke_triggers", None),
                zork_triggers=getattr(request, "zork_triggers", None),
                joke_lines=getattr(request, "joke_lines", None),
                joke_near_guess_lines=getattr(request, "joke_near_guess_lines", None),
                joke_delay_punchline_enabled=getattr(
                    request,
                    "joke_delay_punchline_enabled",
                    None,
                ),
            )
        try:
            setattr(loaders.state_fn, "bot_request_history_fn", response_bot.recent_requests)
        except Exception:
            pass
        try:
            setattr(loaders.state_fn, "bot_settings_fn", _bot_settings_fn)
        except Exception:
            pass
        try:
            setattr(loaders.state_fn, "apply_bot_settings_fn", _apply_bot_settings_fn)
        except Exception:
            pass
        state_lite_fn = getattr(loaders.state_fn, "lite", None)
        if callable(state_lite_fn):
            try:
                setattr(state_lite_fn, "bot_request_history_fn", response_bot.recent_requests)
            except Exception:
                pass
            try:
                setattr(state_lite_fn, "bot_settings_fn", _bot_settings_fn)
            except Exception:
                pass

    try:
        standalone_zork = _build_standalone_zork_service()
    except Exception:
        standalone_zork = None

    if standalone_zork is not None:
        try:
            setattr(loaders.state_fn, "play_standalone_zork_fn", standalone_zork.play)
        except Exception:
            pass
        state_lite_fn = getattr(loaders.state_fn, "lite", None)
        if callable(state_lite_fn):
            try:
                setattr(state_lite_fn, "play_standalone_zork_fn", standalone_zork.play)
            except Exception:
                pass

    search_history_packets_fn = getattr(history_store, "search_packets", None)
    if callable(search_history_packets_fn):
        def _search_history_packets(
            query_text,
            *,
            limit=None,
            before=None,
            after=None,
            scope=None,
            scan_limit=None,
            source=None,
        ):
            kwargs = {
                "limit": limit,
                "before": before,
                "after": after,
                "scope": scope,
                "scan_limit": scan_limit,
            }
            if source is not None:
                kwargs["source"] = source
            return search_history_packets_fn(
                query_text,
                **kwargs,
            )

        try:
            setattr(loaders.state_fn, "search_history_packets_fn", _search_history_packets)
        except Exception:
            pass
        state_lite_fn = getattr(loaders.state_fn, "lite", None)
        if callable(state_lite_fn):
            try:
                setattr(state_lite_fn, "search_history_packets_fn", _search_history_packets)
            except Exception:
                pass

    load_environment_metrics_history_fn = getattr(
        history_store,
        "load_environment_metrics_history",
        None,
    )
    if callable(load_environment_metrics_history_fn):
        def _environment_metrics_history(
            *,
            window_hours=None,
            metric=None,
            node_id=None,
            limit=None,
        ):
            return load_environment_metrics_history_fn(
                window_hours=window_hours,
                metric=metric,
                node_id=node_id,
                limit=limit,
            )

        try:
            setattr(loaders.state_fn, "environment_metrics_history_fn", _environment_metrics_history)
        except Exception:
            pass
        state_lite_fn = getattr(loaders.state_fn, "lite", None)
        if callable(state_lite_fn):
            try:
                setattr(state_lite_fn, "environment_metrics_history_fn", _environment_metrics_history)
            except Exception:
                pass

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
