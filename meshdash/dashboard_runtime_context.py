import os
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Callable, Optional

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
    build_shared_history_db_path,
    resolve_history_local_node_id,
)
from .fault_recorder import FaultRecorder


def _build_standalone_zork_service():
    # Lazy import so slim public builds can omit game modules.
    from .services_standalone_zork import build_standalone_zork_service as _impl

    return _impl()


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

    history_db_path = build_shared_history_db_path(
        resolve_history_db_path_fn(args.history_db)
    )
    history_local_node_id = resolve_history_local_node_id(
        iface=iface,
        get_local_node_id_fn=get_local_node_id_fn,
        wait_for_id_seconds=2.0,
    )
    history_store: Optional[HistoryStoreLike] = open_optional_history_store_fn(
        args,
        history_store_cls=history_store_cls,
        history_db_path=history_db_path,
    )
    if history_store is not None and history_local_node_id:
        try:
            setattr(history_store, "local_node_id", history_local_node_id)
        except Exception:
            pass

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
    try:
        setattr(loaders.state_fn, "fault_history_fn", fault_history_fn)
    except Exception:
        pass
    try:
        setattr(loaders.state_fn, "record_fault_fn", fault_recorder.record_fault)
    except Exception:
        pass
    state_lite_fn = getattr(loaders.state_fn, "lite", None)
    if callable(state_lite_fn):
        try:
            setattr(state_lite_fn, "fault_history_fn", fault_history_fn)
        except Exception:
            pass

    games_runtime_enabled = bool(getattr(args, "games_enable", False))
    set_zork_bot_enabled = (
        getattr(tracker, "set_zork_bot_enabled", None) if games_runtime_enabled else None
    )
    set_ping_bot_enabled = (
        getattr(tracker, "set_ping_bot_enabled", None) if games_runtime_enabled else None
    )
    set_ping_bot_message_only = (
        getattr(tracker, "set_ping_bot_message_only", None) if games_runtime_enabled else None
    )
    manage_zork_bot = getattr(tracker, "manage_zork_bot", None) if games_runtime_enabled else None
    get_zork_bot_runtime = getattr(tracker, "get_zork_bot_runtime", None) if games_runtime_enabled else None
    get_bot_runtime_settings_fn = None
    set_bot_runtime_settings_fn = None
    if history_store is not None:
        get_bot_runtime_settings_fn = getattr(history_store, "get_bot_runtime_settings", None)
        set_bot_runtime_settings_fn = getattr(history_store, "set_bot_runtime_settings", None)
    if not callable(get_bot_runtime_settings_fn):
        get_bot_runtime_settings_fn = None
    if not callable(set_bot_runtime_settings_fn):
        set_bot_runtime_settings_fn = None

    def _bot_runtime_settings_from_payload(payload: object) -> dict[str, object]:
        if not isinstance(payload, Mapping):
            return {
                "zork_enabled": False,
                "ping_enabled": False,
                "ping_message_only": False,
            }
        zork = payload.get("zork")
        ping = payload.get("ping")
        zork_enabled = False
        ping_enabled = False
        ping_message_only = False
        if isinstance(zork, Mapping):
            zork_enabled = bool(zork.get("enabled"))
        if isinstance(ping, Mapping):
            ping_enabled = bool(ping.get("enabled"))
            if "message_only" in ping:
                ping_message_only = bool(ping.get("message_only"))
            elif "messageOnly" in ping:
                ping_message_only = bool(ping.get("messageOnly"))
            else:
                ping_message_only = not bool(
                    ping.get("public_start_enabled", ping.get("publicStartEnabled", True))
                )
        return {
            "zork_enabled": zork_enabled,
            "ping_enabled": ping_enabled,
            "ping_message_only": ping_message_only,
        }

    def _persist_bot_runtime_settings(
        runtime_payload: object | None = None,
    ) -> str | None:
        if set_bot_runtime_settings_fn is None:
            return None
        payload = runtime_payload
        if not isinstance(payload, Mapping) and callable(get_zork_bot_runtime):
            try:
                payload = get_zork_bot_runtime()
            except Exception:
                payload = None
        settings = _bot_runtime_settings_from_payload(payload)
        try:
            set_bot_runtime_settings_fn(settings)
        except Exception as exc:
            return str(exc)
        return None

    if games_runtime_enabled and get_bot_runtime_settings_fn is not None:
        try:
            persisted = get_bot_runtime_settings_fn()
        except Exception:
            persisted = None
        settings_payload = (
            persisted.get("settings") if isinstance(persisted, Mapping) else None
        )
        if isinstance(settings_payload, Mapping):
            ping_message_only = bool(
                settings_payload.get(
                    "ping_message_only",
                    settings_payload.get("pingMessageOnly", False),
                )
            )
            if callable(set_ping_bot_message_only):
                try:
                    set_ping_bot_message_only(ping_message_only)
                except Exception:
                    pass
            if callable(set_zork_bot_enabled):
                try:
                    set_zork_bot_enabled(
                        bool(settings_payload.get("zork_enabled", settings_payload.get("zorkEnabled", False))),
                        send_lock=send_lock,
                    )
                except Exception:
                    pass
            if callable(set_ping_bot_enabled):
                try:
                    set_ping_bot_enabled(
                        bool(settings_payload.get("ping_enabled", settings_payload.get("pingEnabled", False))),
                        send_lock=send_lock,
                    )
                except Exception:
                    pass

    def _attach_persist_error(response_obj: object) -> object:
        persist_error = _persist_bot_runtime_settings(response_obj)
        if not persist_error:
            return response_obj
        if isinstance(response_obj, dict):
            with_error = dict(response_obj)
        else:
            with_error = {"ok": bool(response_obj)}
        with_error["persist_error"] = persist_error
        return with_error

    if callable(set_zork_bot_enabled):
        def _set_zork_bot_enabled_fn(enabled):  # type: ignore[no-redef]
            response_obj = set_zork_bot_enabled(bool(enabled), send_lock=send_lock)
            return _attach_persist_error(response_obj)

        try:
            setattr(loaders.state_fn, "set_zork_bot_enabled_fn", _set_zork_bot_enabled_fn)
        except Exception:
            pass
        state_lite_fn = getattr(loaders.state_fn, "lite", None)
        if callable(state_lite_fn):
            try:
                setattr(state_lite_fn, "set_zork_bot_enabled_fn", _set_zork_bot_enabled_fn)
            except Exception:
                pass

    if callable(set_ping_bot_enabled):
        def _set_ping_bot_enabled_fn(enabled):  # type: ignore[no-redef]
            response_obj = set_ping_bot_enabled(bool(enabled), send_lock=send_lock)
            return _attach_persist_error(response_obj)

        try:
            setattr(loaders.state_fn, "set_ping_bot_enabled_fn", _set_ping_bot_enabled_fn)
        except Exception:
            pass
        state_lite_fn = getattr(loaders.state_fn, "lite", None)
        if callable(state_lite_fn):
            try:
                setattr(state_lite_fn, "set_ping_bot_enabled_fn", _set_ping_bot_enabled_fn)
            except Exception:
                pass

    if callable(set_ping_bot_message_only):
        def _set_ping_bot_message_only_fn(message_only):  # type: ignore[no-redef]
            response_obj = set_ping_bot_message_only(bool(message_only))
            return _attach_persist_error(response_obj)

        try:
            setattr(loaders.state_fn, "set_ping_bot_message_only_fn", _set_ping_bot_message_only_fn)
        except Exception:
            pass
        state_lite_fn = getattr(loaders.state_fn, "lite", None)
        if callable(state_lite_fn):
            try:
                setattr(state_lite_fn, "set_ping_bot_message_only_fn", _set_ping_bot_message_only_fn)
            except Exception:
                pass

    if callable(manage_zork_bot):
        def _manage_zork_bot_fn(action, *, peer_id=None):  # type: ignore[no-redef]
            return manage_zork_bot(action, peer_id=peer_id)

        try:
            setattr(loaders.state_fn, "manage_zork_bot_fn", _manage_zork_bot_fn)
        except Exception:
            pass
        state_lite_fn = getattr(loaders.state_fn, "lite", None)
        if callable(state_lite_fn):
            try:
                setattr(state_lite_fn, "manage_zork_bot_fn", _manage_zork_bot_fn)
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

    # Optional: attach network tools service hook.
    try:
        from .services_network_tools import run_network_tool as _run_network_tool
    except Exception:
        _run_network_tool = None

    if _run_network_tool is not None:
        def _run_network_tool_fn(request):  # type: ignore[no-redef]
            return _run_network_tool(
                request,
                iface=iface,
                send_lock=send_lock,
                to_int_fn=to_int_fn,
            )

        setattr(loaders.state_fn, "run_network_tool_fn", _run_network_tool_fn)

    # Optional: expose custom telemetry extraction rules persisted in history DB.
    if history_store is not None:
        database_stats_fn = getattr(history_store, "database_stats", None)
        if callable(database_stats_fn):
            try:
                setattr(loaders.state_fn, "database_stats_fn", database_stats_fn)
            except Exception:
                pass
            state_lite_fn = getattr(loaders.state_fn, "lite", None)
            if callable(state_lite_fn):
                try:
                    setattr(state_lite_fn, "database_stats_fn", database_stats_fn)
                except Exception:
                    pass

        set_raw_packet_capture_settings_fn = getattr(
            history_store,
            "set_raw_packet_capture_settings",
            None,
        )
        raw_packet_database_download_fn = getattr(
            history_store,
            "raw_packet_database_download",
            None,
        )
        if callable(set_raw_packet_capture_settings_fn):
            try:
                setattr(
                    loaders.state_fn,
                    "set_raw_packet_capture_settings_fn",
                    set_raw_packet_capture_settings_fn,
                )
            except Exception:
                pass
            state_lite_fn = getattr(loaders.state_fn, "lite", None)
            if callable(state_lite_fn):
                try:
                    setattr(
                        state_lite_fn,
                        "set_raw_packet_capture_settings_fn",
                        set_raw_packet_capture_settings_fn,
                    )
                except Exception:
                    pass
        if callable(raw_packet_database_download_fn):
            try:
                setattr(
                    loaders.state_fn,
                    "raw_packet_database_download_fn",
                    raw_packet_database_download_fn,
                )
            except Exception:
                pass
            state_lite_fn = getattr(loaders.state_fn, "lite", None)
            if callable(state_lite_fn):
                try:
                    setattr(
                        state_lite_fn,
                        "raw_packet_database_download_fn",
                        raw_packet_database_download_fn,
                    )
                except Exception:
                    pass

        get_bbs_settings_fn = getattr(history_store, "get_bbs_settings", None)
        set_bbs_settings_fn = getattr(history_store, "set_bbs_settings", None)
        if callable(get_bbs_settings_fn):
            try:
                setattr(loaders.state_fn, "get_bbs_settings_fn", get_bbs_settings_fn)
            except Exception:
                pass
            state_lite_fn = getattr(loaders.state_fn, "lite", None)
            if callable(state_lite_fn):
                try:
                    setattr(state_lite_fn, "get_bbs_settings_fn", get_bbs_settings_fn)
                except Exception:
                    pass
        if callable(set_bbs_settings_fn):
            def _set_bbs_settings(request):
                return set_bbs_settings_fn(
                    {
                        "title": getattr(request, "title", None),
                        "board_id": getattr(request, "board_id", None),
                        "motd": getattr(request, "motd", None),
                    }
                )

            try:
                setattr(loaders.state_fn, "set_bbs_settings_fn", _set_bbs_settings)
            except Exception:
                pass
            state_lite_fn = getattr(loaders.state_fn, "lite", None)
            if callable(state_lite_fn):
                try:
                    setattr(state_lite_fn, "set_bbs_settings_fn", _set_bbs_settings)
                except Exception:
                    pass

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

    standalone_zork = None
    if bool(getattr(args, "games_enable", False)):
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

    if bool(getattr(args, "file_transfer_enable", False)) and bool(
        getattr(args, "file_transfer_auto_accept", False)
    ):
        try:
            from .services_file_transfer_auto_accept import (
                build_file_transfer_auto_accept_service as _build_file_transfer_auto_accept_service,
            )
        except Exception:
            _build_file_transfer_auto_accept_service = None

        if _build_file_transfer_auto_accept_service is not None:
            file_transfer_auto_accept_service = _build_file_transfer_auto_accept_service(
                local_node_id_fn=lambda: get_local_node_id_fn(iface),
                send_chat_fn=loaders.send_chat_fn,
                max_ack_frame_bytes=default_chat_max_bytes,
            )
            subscribe_fn(file_transfer_auto_accept_service.on_receive, "meshtastic.receive")
            try:
                setattr(
                    tracker,
                    "get_file_transfer_runtime",
                    file_transfer_auto_accept_service.get_runtime,
                )
            except Exception:
                pass
            try:
                setattr(
                    loaders.state_fn,
                    "get_file_transfer_auto_accept_runtime_fn",
                    file_transfer_auto_accept_service.get_runtime,
                )
            except Exception:
                pass
            state_lite_fn = getattr(loaders.state_fn, "lite", None)
            if callable(state_lite_fn):
                try:
                    setattr(
                        state_lite_fn,
                        "get_file_transfer_auto_accept_runtime_fn",
                        file_transfer_auto_accept_service.get_runtime,
                    )
                except Exception:
                    pass

    if bool(getattr(args, "bbs_enable", False)):
        try:
            from .services_bbs_host import build_bbs_host_service as _build_bbs_host_service
        except Exception:
            _build_bbs_host_service = None

        if _build_bbs_host_service is not None:
            get_bbs_settings_for_host = getattr(history_store, "get_bbs_settings", None)
            set_bbs_settings_for_host = getattr(history_store, "set_bbs_settings", None)
            get_bbs_posts_for_host = getattr(history_store, "get_bbs_posts", None)
            append_bbs_post_for_host = getattr(history_store, "append_bbs_post", None)
            def _get_chat_delivery_state(message_id: object):
                clean_message_id = to_int_fn(message_id)
                if clean_message_id is None or clean_message_id <= 0:
                    return None
                tracker_lock = getattr(tracker, "_lock", None)
                recent_chat = getattr(tracker, "recent_chat", None)
                if recent_chat is None:
                    return None

                def _scan_recent_chat():
                    for entry in reversed(recent_chat):
                        if not isinstance(entry, dict):
                            continue
                        if entry.get("local_echo") is not True:
                            continue
                        entry_message_id = to_int_fn(
                            entry.get("message_id")
                            or entry.get("messageId")
                            or entry.get("packet_id")
                            or entry.get("packetId")
                        )
                        if entry_message_id != clean_message_id:
                            continue
                        return {
                            "delivery_state": str(entry.get("delivery_state") or "").strip().lower(),
                            "delivery_updated_unix": to_int_fn(
                                entry.get("delivery_updated_unix") or entry.get("deliveryUpdatedUnix")
                            )
                            or 0,
                        }
                    return None

                if hasattr(tracker_lock, "__enter__") and hasattr(tracker_lock, "__exit__"):
                    with tracker_lock:
                        return _scan_recent_chat()
                return _scan_recent_chat()

            bbs_host_service = _build_bbs_host_service(
                local_node_id_fn=lambda: get_local_node_id_fn(iface),
                send_chat_fn=loaders.send_chat_fn,
                get_bbs_settings_fn=(
                    get_bbs_settings_for_host if callable(get_bbs_settings_for_host) else None
                ),
                set_bbs_settings_fn=(
                    set_bbs_settings_for_host if callable(set_bbs_settings_for_host) else None
                ),
                get_bbs_posts_fn=(
                    get_bbs_posts_for_host if callable(get_bbs_posts_for_host) else None
                ),
                append_bbs_post_fn=(
                    append_bbs_post_for_host if callable(append_bbs_post_for_host) else None
                ),
                get_delivery_state_fn=_get_chat_delivery_state,
            )
            restore_bbs_host_runtime = getattr(bbs_host_service, "restore_persisted_runtime", None)
            if callable(restore_bbs_host_runtime):
                try:
                    restore_bbs_host_runtime()
                except Exception:
                    pass
            subscribe_fn(bbs_host_service.on_receive, "meshtastic.receive")
            try:
                setattr(loaders.state_fn, "get_bbs_host_runtime_fn", bbs_host_service.get_runtime)
                setattr(loaders.state_fn, "start_bbs_host_fn", bbs_host_service.start)
                setattr(loaders.state_fn, "stop_bbs_host_fn", bbs_host_service.stop)
                setattr(loaders.state_fn, "append_bbs_host_post_fn", bbs_host_service.append_post)
            except Exception:
                pass
            state_lite_fn = getattr(loaders.state_fn, "lite", None)
            if callable(state_lite_fn):
                try:
                    setattr(state_lite_fn, "get_bbs_host_runtime_fn", bbs_host_service.get_runtime)
                    setattr(state_lite_fn, "start_bbs_host_fn", bbs_host_service.start)
                    setattr(state_lite_fn, "stop_bbs_host_fn", bbs_host_service.stop)
                    setattr(state_lite_fn, "append_bbs_host_post_fn", bbs_host_service.append_post)
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

    load_malformed_text_history_fn = getattr(
        history_store,
        "load_malformed_text_history",
        None,
    )
    if callable(load_malformed_text_history_fn):
        def _malformed_text_history(
            *,
            window_hours=None,
            node_id=None,
            limit=None,
        ):
            return load_malformed_text_history_fn(
                window_hours=window_hours,
                node_id=node_id,
                limit=limit,
            )

        try:
            setattr(loaders.state_fn, "malformed_text_history_fn", _malformed_text_history)
        except Exception:
            pass
        state_lite_fn = getattr(loaders.state_fn, "lite", None)
        if callable(state_lite_fn):
            try:
                setattr(state_lite_fn, "malformed_text_history_fn", _malformed_text_history)
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
