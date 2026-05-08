import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Optional
from http.server import ThreadingHTTPServer

from .dashboard_args_contracts import DashboardArgs
from .dashboard_setup_contracts import DashboardTrackerFactory, HistoryStoreFactory
from .runtime_lifecycle import (
    close_runtime_resources,
    emit_startup_status,
)
from .runtime_callbacks import (
    build_send_chat_loader,
    build_state_snapshot_loader,
)
from .dashboard_runtime_context import (
    DashboardRuntimeContext,
    build_dashboard_runtime_context,
)
from .dashboard_server import (
    build_dashboard_server,
)
from .runtime_types import (
    BuildNodeHistoryLoaderFn,
    BuildOnlineActivityLoaderFn,
    BuildSummaryMetricsLoaderFn,
    BuildStateFn,
    GetLocalNodeIdFn,
    GuessLanIpv4Fn,
    MakeHttpHandlerFn,
    MeshTargetLabelFn,
    NormalizeSingleEmojiFn,
    OpenMeshInterfaceFn,
    RenderHtmlFn,
    RevisionInfoFn,
    SendChatMessageFn,
    SendReactionPacketFn,
    SeedTrackerFn,
    SubscribeFn,
    ThreadingHttpServerCls,
    ToIntFn,
    UtcNowFn,
)


@dataclass(frozen=True)
class _NoopCloseResource:
    def close(self) -> None:
        return


class _OfflineTracker:
    def stop_receiving(self) -> None:
        return


_SUMMARY_SAMPLE_INTERVAL_SECONDS = 15.0
_SUMMARY_SAMPLE_STARTUP_DELAY_SECONDS = 5.0
_SUMMARY_PERSIST_STARTUP_GRACE_SECONDS = 90


def _attach_standalone_zork_service(state_fn: object) -> None:
    try:
        from .services_standalone_zork import (
            build_standalone_zork_service as _build_standalone_zork_service,
        )
    except Exception:
        return

    try:
        standalone_zork = _build_standalone_zork_service()
    except Exception:
        return

    try:
        setattr(state_fn, "play_standalone_zork_fn", standalone_zork.play)
    except Exception:
        pass

    state_lite_fn = getattr(state_fn, "lite", None)
    if callable(state_lite_fn):
        try:
            setattr(state_lite_fn, "play_standalone_zork_fn", standalone_zork.play)
        except Exception:
            pass


def _summary_sampling_supported(context: DashboardRuntimeContext) -> bool:
    if not context.history_enabled:
        return False
    store = context.history_store
    if store is None:
        return False
    save_summary_fn = getattr(store, "save_summary_metrics", None)
    return callable(save_summary_fn)


def _extract_state_summary(payload: object) -> Mapping[str, object] | None:
    if isinstance(payload, Mapping):
        summary = payload.get("summary")
        return summary if isinstance(summary, Mapping) else None
    summary = getattr(payload, "summary", None)
    return summary if isinstance(summary, Mapping) else None


def _to_int_or_none(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except Exception:
        return None


def _should_skip_summary_persistence(summary: Mapping[str, object]) -> bool:
    uptime_seconds = _to_int_or_none(summary.get("uptime_seconds"))
    if uptime_seconds is None:
        return False
    return uptime_seconds < _SUMMARY_PERSIST_STARTUP_GRACE_SECONDS


def _resolve_summary_sampler_state_fn(state_fn: object):
    lite_fn = getattr(state_fn, "lite", None)
    if callable(lite_fn):
        return lite_fn
    return state_fn if callable(state_fn) else None


def _start_summary_sampler(context: DashboardRuntimeContext) -> tuple[threading.Event | None, threading.Thread | None]:
    if not _summary_sampling_supported(context):
        return None, None
    save_summary_fn = getattr(context.history_store, "save_summary_metrics", None)
    if not callable(save_summary_fn):
        return None, None
    sample_state_fn = _resolve_summary_sampler_state_fn(context.state_fn)
    if sample_state_fn is None:
        return None, None

    def _sample_once_and_persist() -> None:
        try:
            payload = sample_state_fn()
        except Exception:
            return
        summary = _extract_state_summary(payload)
        if summary is None:
            return
        if _should_skip_summary_persistence(summary):
            return
        try:
            save_summary_fn(summary)
        except Exception:
            # Sampling persistence is best-effort.
            pass

    # Prime the latest bucket at startup so charts are populated even before
    # the first background interval elapses.
    _sample_once_and_persist()

    stop_event = threading.Event()

    def _sample_loop() -> None:
        if stop_event.wait(_SUMMARY_SAMPLE_STARTUP_DELAY_SECONDS):
            return
        while not stop_event.wait(_SUMMARY_SAMPLE_INTERVAL_SECONDS):
            _sample_once_and_persist()

    thread = threading.Thread(
        target=_sample_loop,
        name="dashboard-summary-sampler",
        daemon=True,
    )
    thread.start()
    return stop_event, thread


def _enable_serial_auto_reconnect(args: DashboardArgs) -> bool:
    # Keep runtime sessions resilient for both serial and TCP links by
    # rebuilding the radio session when links are unavailable/lost.
    del args
    return True


def _build_offline_state_loader(
    *,
    target: str,
    revision_info: object,
    startup_error: Exception,
    connecting: bool,
    started_at: float,
    utc_now_fn: UtcNowFn,
):
    revision_payload = {}
    as_dict = getattr(revision_info, "as_dict", None)
    if callable(as_dict):
        try:
            revision_payload = dict(as_dict())
        except Exception:
            revision_payload = {}
    startup_error_text = str(startup_error).strip() or "radio unavailable"
    tracker_error_text = (
        f"radio connecting: {startup_error_text}"
        if connecting
        else f"radio link lost: {startup_error_text}"
    )
    radio_connection_summary = {
        "state": "connecting" if connecting else "lost",
        "target": target,
        "error": startup_error_text,
    }

    def state_fn() -> dict[str, object]:
        uptime_seconds = int(max(0, time.time() - started_at))
        return {
            "generated_at": utc_now_fn(),
            "summary": {
                "target": target,
                "uptime_seconds": uptime_seconds,
                "node_count": 0,
                "nodes_with_position": 0,
                "live_packet_count": 0,
                "edge_count": 0,
                "real_edge_count": 0,
                "recent_packet_buffer": 0,
                "modem_preset": None,
                "disk": {"free_percent": "n/a"},
                "revision": revision_payload,
                "radio_connection": radio_connection_summary,
            },
            "summary_error": None,
            "my_info": None,
            "my_info_error": None,
            "metadata": None,
            "metadata_error": None,
            "local_state": {},
            "local_state_error": startup_error_text,
            "nodes_error": startup_error_text,
            "tracker_error": tracker_error_text,
            "tracker_saved_counts_error": None,
            "tracker_capabilities_error": None,
            "nodes": [],
            "history_caps": {},
            "nodes_full": [],
            "traffic": {
                "edges": [],
                "port_counts": [],
                "recent_packets": [],
                "recent_chat": [],
            },
            "local_node_id": "local",
        }

    def state_fn_lite() -> dict[str, object]:
        payload = dict(state_fn())
        payload.pop("my_info", None)
        payload.pop("metadata", None)
        payload.pop("local_state", None)
        payload.pop("nodes_full", None)
        return payload

    try:
        setattr(state_fn, "lite", state_fn_lite)
    except Exception:
        pass

    return state_fn


def _build_offline_runtime_context(
    args: DashboardArgs,
    *,
    startup_error: Exception,
    connecting: bool,
    mesh_target_label_fn: MeshTargetLabelFn,
    revision_info_fn: RevisionInfoFn,
    utc_now_fn: UtcNowFn,
) -> DashboardRuntimeContext:
    target = mesh_target_label_fn(args)
    revision_info = revision_info_fn()
    started_at = time.time()
    state_fn = _build_offline_state_loader(
        target=target,
        revision_info=revision_info,
        startup_error=startup_error,
        connecting=connecting,
        started_at=started_at,
        utc_now_fn=utc_now_fn,
    )
    if bool(getattr(args, "zork_enable", False)):
        _attach_standalone_zork_service(state_fn)
    return DashboardRuntimeContext(
        target=target,
        iface=_NoopCloseResource(),
        history_db_path="",
        history_store=None,
        tracker=_OfflineTracker(),
        send_lock=threading.Lock(),
        started_at=started_at,
        revision_info=revision_info,
        state_fn=state_fn,
        node_history_fn=None,  # type: ignore[arg-type]
        online_activity_fn=None,  # type: ignore[arg-type]
        summary_metrics_fn=None,  # type: ignore[arg-type]
        send_chat_fn=None,  # type: ignore[arg-type]
        history_enabled=False,
    )


def _build_runtime_context_with_retry(
    args: DashboardArgs,
    *,
    auto_reconnect: bool,
    mesh_target_label_fn: MeshTargetLabelFn,
    open_mesh_interface_fn: OpenMeshInterfaceFn,
    history_store_cls: HistoryStoreFactory,
    dashboard_tracker_cls: DashboardTrackerFactory,
    subscribe_fn: SubscribeFn,
    seed_tracker_fn: SeedTrackerFn,
    revision_info_fn: RevisionInfoFn,
    build_state_fn: BuildStateFn,
    build_node_history_loader_fn: BuildNodeHistoryLoaderFn,
    build_online_activity_loader_fn: BuildOnlineActivityLoaderFn,
    build_summary_metrics_loader_fn: BuildSummaryMetricsLoaderFn,
    send_chat_message_fn: SendChatMessageFn,
    send_reaction_packet_fn: SendReactionPacketFn,
    get_local_node_id_fn: GetLocalNodeIdFn,
    normalize_single_emoji_fn: NormalizeSingleEmojiFn,
    to_int_fn: ToIntFn,
    utc_now_fn: UtcNowFn,
    default_chat_max_bytes: int,
):
    attempt = 0
    while True:
        try:
            return build_dashboard_runtime_context(
                args,
                mesh_target_label_fn=mesh_target_label_fn,
                open_mesh_interface_fn=open_mesh_interface_fn,
                history_store_cls=history_store_cls,
                dashboard_tracker_cls=dashboard_tracker_cls,
                subscribe_fn=subscribe_fn,
                seed_tracker_fn=seed_tracker_fn,
                revision_info_fn=revision_info_fn,
                send_chat_message_fn=send_chat_message_fn,
                send_reaction_packet_fn=send_reaction_packet_fn,
                get_local_node_id_fn=get_local_node_id_fn,
                default_chat_max_bytes=default_chat_max_bytes,
                normalize_single_emoji_fn=normalize_single_emoji_fn,
                to_int_fn=to_int_fn,
                utc_now_fn=utc_now_fn,
                build_state_fn=build_state_fn,
                build_state_snapshot_loader_fn=build_state_snapshot_loader,
                build_node_history_loader_fn=build_node_history_loader_fn,
                build_online_activity_loader_fn=build_online_activity_loader_fn,
                build_summary_metrics_loader_fn=build_summary_metrics_loader_fn,
                build_send_chat_loader_fn=build_send_chat_loader,
            )
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            if not auto_reconnect:
                raise
            attempt += 1
            delay_seconds = min(10, 1 + attempt)
            print(
                f"Radio unavailable ({exc}). Retrying connection in {delay_seconds}s..."
            )
            time.sleep(delay_seconds)


def _build_runtime_context_once(
    args: DashboardArgs,
    *,
    mesh_target_label_fn: MeshTargetLabelFn,
    open_mesh_interface_fn: OpenMeshInterfaceFn,
    history_store_cls: HistoryStoreFactory,
    dashboard_tracker_cls: DashboardTrackerFactory,
    subscribe_fn: SubscribeFn,
    seed_tracker_fn: SeedTrackerFn,
    revision_info_fn: RevisionInfoFn,
    build_state_fn: BuildStateFn,
    build_node_history_loader_fn: BuildNodeHistoryLoaderFn,
    build_online_activity_loader_fn: BuildOnlineActivityLoaderFn,
    build_summary_metrics_loader_fn: BuildSummaryMetricsLoaderFn,
    send_chat_message_fn: SendChatMessageFn,
    send_reaction_packet_fn: SendReactionPacketFn,
    get_local_node_id_fn: GetLocalNodeIdFn,
    normalize_single_emoji_fn: NormalizeSingleEmojiFn,
    to_int_fn: ToIntFn,
    utc_now_fn: UtcNowFn,
    default_chat_max_bytes: int,
):
    return build_dashboard_runtime_context(
        args,
        mesh_target_label_fn=mesh_target_label_fn,
        open_mesh_interface_fn=open_mesh_interface_fn,
        history_store_cls=history_store_cls,
        dashboard_tracker_cls=dashboard_tracker_cls,
        subscribe_fn=subscribe_fn,
        seed_tracker_fn=seed_tracker_fn,
        revision_info_fn=revision_info_fn,
        send_chat_message_fn=send_chat_message_fn,
        send_reaction_packet_fn=send_reaction_packet_fn,
        get_local_node_id_fn=get_local_node_id_fn,
        default_chat_max_bytes=default_chat_max_bytes,
        normalize_single_emoji_fn=normalize_single_emoji_fn,
        to_int_fn=to_int_fn,
        utc_now_fn=utc_now_fn,
        build_state_fn=build_state_fn,
        build_state_snapshot_loader_fn=build_state_snapshot_loader,
        build_node_history_loader_fn=build_node_history_loader_fn,
        build_online_activity_loader_fn=build_online_activity_loader_fn,
        build_summary_metrics_loader_fn=build_summary_metrics_loader_fn,
        build_send_chat_loader_fn=build_send_chat_loader,
    )


def run_dashboard_runtime(
    args: DashboardArgs,
    *,
    mesh_target_label_fn: MeshTargetLabelFn,
    open_mesh_interface_fn: OpenMeshInterfaceFn,
    history_store_cls: HistoryStoreFactory,
    dashboard_tracker_cls: DashboardTrackerFactory,
    subscribe_fn: SubscribeFn,
    seed_tracker_fn: SeedTrackerFn,
    revision_info_fn: RevisionInfoFn,
    build_state_fn: BuildStateFn,
    build_node_history_loader_fn: BuildNodeHistoryLoaderFn,
    build_online_activity_loader_fn: BuildOnlineActivityLoaderFn,
    build_summary_metrics_loader_fn: BuildSummaryMetricsLoaderFn,
    send_chat_message_fn: SendChatMessageFn,
    send_reaction_packet_fn: SendReactionPacketFn,
    get_local_node_id_fn: GetLocalNodeIdFn,
    normalize_single_emoji_fn: NormalizeSingleEmojiFn,
    to_int_fn: ToIntFn,
    utc_now_fn: UtcNowFn,
    render_html_fn: RenderHtmlFn,
    make_http_handler_fn: MakeHttpHandlerFn,
    guess_lan_ipv4_fn: GuessLanIpv4Fn,
    default_chat_max_bytes: int,
    threading_http_server_cls: ThreadingHttpServerCls = ThreadingHTTPServer,
) -> None:
    auto_reconnect = _enable_serial_auto_reconnect(args)
    first_session = True
    offline_bootstrap_error: Optional[Exception] = None
    while True:
        startup_offline = False
        startup_error: Optional[Exception] = None
        if auto_reconnect and (first_session or offline_bootstrap_error is not None):
            startup_offline = True
            connecting = offline_bootstrap_error is None
            startup_error = offline_bootstrap_error or RuntimeError(
                f"waiting for radio link on {mesh_target_label_fn(args)}"
            )
            if connecting:
                print(
                    f"Starting dashboard before radio connect ({startup_error}). "
                    "Serving UI now and retrying radio link in background..."
                )
            else:
                print(
                    f"Radio session unavailable ({startup_error}). "
                    "Serving offline UI and retrying radio link in background..."
                )
            context = _build_offline_runtime_context(
                args,
                startup_error=startup_error,
                connecting=connecting,
                mesh_target_label_fn=mesh_target_label_fn,
                revision_info_fn=revision_info_fn,
                utc_now_fn=utc_now_fn,
            )
        elif auto_reconnect:
            try:
                context = _build_runtime_context_once(
                    args,
                    mesh_target_label_fn=mesh_target_label_fn,
                    open_mesh_interface_fn=open_mesh_interface_fn,
                    history_store_cls=history_store_cls,
                    dashboard_tracker_cls=dashboard_tracker_cls,
                    subscribe_fn=subscribe_fn,
                    seed_tracker_fn=seed_tracker_fn,
                    revision_info_fn=revision_info_fn,
                    build_state_fn=build_state_fn,
                    build_node_history_loader_fn=build_node_history_loader_fn,
                    build_online_activity_loader_fn=build_online_activity_loader_fn,
                    build_summary_metrics_loader_fn=build_summary_metrics_loader_fn,
                    send_chat_message_fn=send_chat_message_fn,
                    send_reaction_packet_fn=send_reaction_packet_fn,
                    get_local_node_id_fn=get_local_node_id_fn,
                    normalize_single_emoji_fn=normalize_single_emoji_fn,
                    to_int_fn=to_int_fn,
                    utc_now_fn=utc_now_fn,
                    default_chat_max_bytes=default_chat_max_bytes,
                )
            except Exception as exc:
                startup_offline = True
                startup_error = exc
                print(
                    f"Radio unavailable ({exc}). "
                    "Serving offline UI and retrying radio link in background."
                )
                context = _build_offline_runtime_context(
                    args,
                    startup_error=exc,
                    connecting=True,
                    mesh_target_label_fn=mesh_target_label_fn,
                    revision_info_fn=revision_info_fn,
                    utc_now_fn=utc_now_fn,
                )
        else:
            context = _build_runtime_context_with_retry(
                args,
                auto_reconnect=auto_reconnect,
                mesh_target_label_fn=mesh_target_label_fn,
                open_mesh_interface_fn=open_mesh_interface_fn,
                history_store_cls=history_store_cls,
                dashboard_tracker_cls=dashboard_tracker_cls,
                subscribe_fn=subscribe_fn,
                seed_tracker_fn=seed_tracker_fn,
                revision_info_fn=revision_info_fn,
                build_state_fn=build_state_fn,
                build_node_history_loader_fn=build_node_history_loader_fn,
                build_online_activity_loader_fn=build_online_activity_loader_fn,
                build_summary_metrics_loader_fn=build_summary_metrics_loader_fn,
                send_chat_message_fn=send_chat_message_fn,
                send_reaction_packet_fn=send_reaction_packet_fn,
                get_local_node_id_fn=get_local_node_id_fn,
                normalize_single_emoji_fn=normalize_single_emoji_fn,
                to_int_fn=to_int_fn,
                utc_now_fn=utc_now_fn,
                default_chat_max_bytes=default_chat_max_bytes,
            )
        first_session = False

        server_parts = build_dashboard_server(
            args=args,
            revision_info=context.revision_info,
            history_enabled=context.history_enabled,
            state_fn=context.state_fn,
            node_history_fn=context.node_history_fn,
            online_activity_fn=context.online_activity_fn,
            summary_metrics_fn=context.summary_metrics_fn,
            send_chat_fn=context.send_chat_fn,
            render_html_fn=render_html_fn,
            make_http_handler_fn=make_http_handler_fn,
            threading_http_server_cls=threading_http_server_cls,
        )
        server = server_parts.server
        bound_host = server_parts.bound_host
        bound_port = server_parts.bound_port

        emit_startup_status(
            http_host=args.http_host,
            bound_host=bound_host,
            bound_port=bound_port,
            show_secrets=args.show_secrets,
            revision_info=context.revision_info,
            history_enabled=context.history_enabled,
            history_db_path=context.history_db_path,
            history_retention_days=args.history_retention_days,
            history_max_rows=args.history_max_rows,
            history_event_retention_days=args.history_event_retention_days,
            history_event_max_rows=args.history_event_max_rows,
            history_rollup_retention_days=args.history_rollup_retention_days,
            guess_lan_ipv4_fn=guess_lan_ipv4_fn,
        )
        if startup_offline and startup_error is not None:
            print(f"Offline reason: {startup_error}")

        restart_requested = threading.Event()
        stop_watcher = threading.Event()
        watcher_thread: threading.Thread | None = None
        stop_summary_sampler: threading.Event | None = None
        summary_sampler_thread: threading.Thread | None = None
        stop_summary_sampler, summary_sampler_thread = _start_summary_sampler(context)

        if auto_reconnect and startup_offline:

            def _watch_startup_radio_connect() -> None:
                attempt = 0
                delay_seconds = 0.5
                while not stop_watcher.wait(delay_seconds):
                    attempt += 1
                    try:
                        probe_iface = open_mesh_interface_fn(args)
                    except Exception as exc:
                        delay_seconds = min(10.0, 1.0 + attempt)
                        if attempt == 1 or (attempt % 5) == 0:
                            print(
                                f"Waiting for radio link ({exc}). "
                                f"Retrying in {delay_seconds:.0f}s..."
                            )
                        continue
                    try:
                        close_fn = getattr(probe_iface, "close", None)
                        if callable(close_fn):
                            close_fn()
                    except Exception:
                        pass
                    restart_requested.set()
                    print("Radio link detected. Switching dashboard to live session...")
                    shutdown_fn = getattr(server, "shutdown", None)
                    if callable(shutdown_fn):
                        try:
                            shutdown_fn()
                        except Exception:
                            pass
                    return

            watcher_thread = threading.Thread(
                target=_watch_startup_radio_connect,
                name="dashboard-startup-radio-watch",
                daemon=True,
            )
            watcher_thread.start()
        elif auto_reconnect and not startup_offline and hasattr(context.tracker, "radio_link_connected"):

            def _watch_radio_link_loss() -> None:
                while not stop_watcher.wait(0.5):
                    try:
                        connected = getattr(context.tracker, "radio_link_connected", None)
                    except Exception:
                        connected = None
                    if connected is not False:
                        continue
                    restart_requested.set()
                    shutdown_fn = getattr(server, "shutdown", None)
                    if callable(shutdown_fn):
                        try:
                            shutdown_fn()
                        except Exception:
                            pass
                    return

            watcher_thread = threading.Thread(
                target=_watch_radio_link_loss,
                name="dashboard-radio-watch",
                daemon=True,
            )
            watcher_thread.start()

        interrupted = False
        try:
            server.serve_forever(poll_interval=0.5)
        except KeyboardInterrupt:
            print("Stopping dashboard...")
            interrupted = True
        finally:
            stop_watcher.set()
            if watcher_thread is not None:
                watcher_thread.join(timeout=1.0)
            if stop_summary_sampler is not None:
                stop_summary_sampler.set()
            if summary_sampler_thread is not None:
                summary_sampler_thread.join(timeout=1.0)
            stop_receiving = getattr(context.tracker, "stop_receiving", None)
            if callable(stop_receiving):
                try:
                    stop_receiving()
                except Exception:
                    pass
            close_runtime_resources(
                server=server,
                iface=context.iface,
                history_store=context.history_store,
            )

        if interrupted:
            return
        if startup_offline and auto_reconnect and restart_requested.is_set():
            offline_bootstrap_error = None
            time.sleep(0.5)
            continue
        if startup_offline:
            return
        if auto_reconnect and restart_requested.is_set():
            reason = str(getattr(context.tracker, "radio_link_error", "") or "").strip()
            offline_bootstrap_error = RuntimeError(reason or "radio link lost")
            print("Radio link lost. Serving offline UI while reconnecting...")
            time.sleep(0.5)
            continue
        return
