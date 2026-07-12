import os
import threading
import time
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Callable, Optional

from .config import DEFAULT_FILE_TRANSFER_MAX_BYTES
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
    BuildSummaryMetricsLoaderFn,
    BuildSendChatLoaderFn,
    BuildStateFn,
    BuildStateSnapshotLoaderFn,
    GetLocalNodeIdFn,
    MeshTargetLabelFn,
    NodeHistoryFn,
    NormalizeSingleEmojiFn,
    OpenMeshInterfaceFn,
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
    summary_metrics_fn: SummaryMetricsHistoryFn
    send_chat_fn: SendChatFn
    history_enabled: bool


class StartupReceiveBuffer:
    """Buffer startup packets until runtime state is ready to ingest them."""

    def __init__(self, *, max_packets: int = 2048) -> None:
        self._lock = threading.Lock()
        self._max_packets = max(1, int(max_packets))
        self._packets: deque[tuple[object, object]] = deque(maxlen=self._max_packets)
        self._dropped_packets = 0
        self._callback: Optional[Callable[[object, object], object]] = None
        self._closed = False

    def on_receive(self, packet: object, interface: object) -> None:
        callback: Optional[Callable[[object, object], object]]
        with self._lock:
            if self._closed:
                return
            callback = self._callback
            if callback is None:
                if len(self._packets) >= self._max_packets:
                    self._dropped_packets += 1
                self._packets.append((packet, interface))
                return
        callback(packet, interface)

    def activate(self, callback: Callable[[object, object], object]) -> None:
        with self._lock:
            if self._closed:
                return
            buffered_packets = list(self._packets)
            self._packets.clear()
            for packet, interface in buffered_packets:
                callback(packet, interface)
            self._callback = callback

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._packets.clear()
            self._callback = None

    @property
    def dropped_packets(self) -> int:
        with self._lock:
            return int(self._dropped_packets)


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
    startup_receive_buffer: Optional[StartupReceiveBuffer] = None,
    build_dashboard_runtime_loaders_fn: Optional[BuildDashboardRuntimeLoadersFn] = None,
    build_dashboard_runtime_loader_dependencies_from_legacy_args_fn: BuildDashboardRuntimeLoaderDependenciesFromLegacyArgsFn = build_dashboard_runtime_loader_dependencies_from_legacy_args,
    build_dashboard_runtime_loaders_with_dependencies_fn: BuildDashboardRuntimeLoadersWithDependenciesFn = build_dashboard_runtime_loaders_with_dependencies,
) -> DashboardRuntimeContext:
    target = mesh_target_label_fn(args)
    history_db_path = build_shared_history_db_path(
        resolve_history_db_path_fn(args.history_db)
    )
    history_store: Optional[HistoryStoreLike] = open_optional_history_store_fn(
        args,
        history_store_cls=history_store_cls,
        history_db_path=history_db_path,
    )

    tracker = dashboard_tracker_cls(packet_limit=args.packet_limit, history_store=history_store)
    send_lock = lock_factory()

    receive_buffer = startup_receive_buffer or StartupReceiveBuffer()
    if startup_receive_buffer is None:
        subscribe_fn(receive_buffer.on_receive, "meshtastic.receive")

    print_fn(f"Connecting to {target} ...")
    try:
        iface = open_mesh_interface_fn(args)
    except Exception:
        receive_buffer.close()
        close_history_store = getattr(history_store, "close", None)
        if callable(close_history_store):
            try:
                close_history_store()
            except Exception:
                pass
        raise

    history_local_node_id = resolve_history_local_node_id(
        iface=iface,
        get_local_node_id_fn=get_local_node_id_fn,
        wait_for_id_seconds=2.0,
    )
    if history_store is not None and history_local_node_id:
        try:
            setattr(history_store, "local_node_id", history_local_node_id)
        except Exception:
            pass

    receive_buffer.activate(tracker.on_receive)
    try:
        setattr(tracker, "_startup_receive_buffer", receive_buffer)
    except Exception:
        pass

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

    # Attach the Meshyface profile broadcaster to the state loader so HTTP
    # wiring can discover it without adding another server-wide dependency.
    try:
        from .services_meshyface_profile import (
            send_meshyface_profile_theme as _send_meshyface_profile_theme,
        )
    except Exception:
        _send_meshyface_profile_theme = None

    if _send_meshyface_profile_theme is not None:
        def _send_meshyface_profile_fn(  # type: ignore[no-redef]
            *,
            theme,
            channel_index=0,
            ghost=None,
        ):
            status_fn = getattr(tracker, "meshyface_profile_processing_status", None)
            if callable(status_fn):
                status = status_fn()
                if isinstance(status, Mapping) and not bool(status.get("enabled", False)):
                    raise ValueError("node appearance sharing is disabled")
            elif not bool(getattr(tracker, "meshyface_profile_processing_enabled", False)):
                raise ValueError("node appearance sharing is disabled")
            return _send_meshyface_profile_theme(
                channel_index=channel_index,
                theme=theme,
                ghost=ghost,
                iface=iface,
                send_lock=send_lock,
                local_node_id_fn=lambda: get_local_node_id_fn(iface),
            )

        setattr(
            loaders.state_fn,
            "send_meshyface_profile_fn",
            _send_meshyface_profile_fn,
        )
        state_lite_fn = getattr(loaders.state_fn, "lite", None)
        if callable(state_lite_fn):
            try:
                setattr(
                    state_lite_fn,
                    "send_meshyface_profile_fn",
                    _send_meshyface_profile_fn,
                )
            except Exception:
                pass

    set_meshyface_profile_processing_enabled = getattr(
        tracker,
        "set_meshyface_profile_processing_enabled",
        None,
    )
    if callable(set_meshyface_profile_processing_enabled):
        def _set_meshyface_profile_processing_enabled_fn(  # type: ignore[no-redef]
            enabled,
        ):
            return set_meshyface_profile_processing_enabled(bool(enabled))

        try:
            setattr(
                loaders.state_fn,
                "set_meshyface_profile_processing_enabled_fn",
                _set_meshyface_profile_processing_enabled_fn,
            )
        except Exception:
            pass
        state_lite_fn = getattr(loaders.state_fn, "lite", None)
        if callable(state_lite_fn):
            try:
                setattr(
                    state_lite_fn,
                    "set_meshyface_profile_processing_enabled_fn",
                    _set_meshyface_profile_processing_enabled_fn,
                )
            except Exception:
                pass

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

    if bool(getattr(args, "file_transfer_enable", False)):
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
                enabled=bool(getattr(args, "file_transfer_auto_accept", False)),
                max_ack_frame_bytes=1024,
                max_file_bytes=getattr(
                    args,
                    "file_transfer_max_bytes",
                    DEFAULT_FILE_TRANSFER_MAX_BYTES,
                ),
            )
            subscribe_fn(file_transfer_auto_accept_service.on_receive, "meshtastic.receive")
            try:
                setattr(
                    tracker,
                    "_file_transfer_auto_accept_service",
                    file_transfer_auto_accept_service,
                )
            except Exception:
                pass
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
                setattr(
                    loaders.state_fn,
                    "set_file_transfer_auto_accept_enabled_fn",
                    file_transfer_auto_accept_service.set_enabled,
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
                    setattr(
                        state_lite_fn,
                        "set_file_transfer_auto_accept_enabled_fn",
                        file_transfer_auto_accept_service.set_enabled,
                    )
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
            include_gap_scan=True,
            catalog_only=False,
        ):
            return load_environment_metrics_history_fn(
                window_hours=window_hours,
                metric=metric,
                node_id=node_id,
                limit=limit,
                include_gap_scan=include_gap_scan,
                catalog_only=catalog_only,
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
        summary_metrics_fn=loaders.summary_metrics_fn,
        send_chat_fn=loaders.send_chat_fn,
        history_enabled=history_store is not None,
    )
