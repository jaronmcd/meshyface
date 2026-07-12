import os
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
    StartupReceiveBuffer,
    build_dashboard_runtime_context,
)
from .dashboard_setup import open_optional_history_store
from .dashboard_server import (
    build_dashboard_server,
)
from .api_system_restart import schedule_backend_restart
from .helpers import format_epoch, to_int
from .history_profile import build_shared_history_db_path
from .runtime_types import (
    BuildNodeHistoryLoaderFn,
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
from .state_summary import (
    apply_node_historical_names,
    apply_node_position_counts,
    apply_node_saved_counts,
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


def _cached_history_node_rows(
    history_store: object | None,
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    if history_store is None:
        return [], {}

    load_capabilities_fn = getattr(history_store, "load_node_capabilities", None)
    load_position_counts_fn = getattr(history_store, "load_node_position_counts", None)
    load_saved_counts_fn = getattr(history_store, "load_node_saved_counts", None)
    if (
        not callable(load_capabilities_fn)
        and not callable(load_position_counts_fn)
        and not callable(load_saved_counts_fn)
    ):
        return [], {}

    try:
        raw_caps = load_capabilities_fn() if callable(load_capabilities_fn) else {}
    except Exception:
        raw_caps = {}
    try:
        raw_saved_counts = load_saved_counts_fn() if callable(load_saved_counts_fn) else {}
    except Exception:
        raw_saved_counts = {}
    try:
        raw_position_counts = load_position_counts_fn() if callable(load_position_counts_fn) else {}
    except Exception:
        raw_position_counts = {}

    caps_by_id = {
        str(node_id or "").strip(): dict(caps)
        for node_id, caps in (raw_caps.items() if isinstance(raw_caps, Mapping) else [])
        if str(node_id or "").strip() and isinstance(caps, Mapping)
    }
    saved_counts = {
        str(node_id or "").strip(): dict(stats)
        for node_id, stats in (raw_saved_counts.items() if isinstance(raw_saved_counts, Mapping) else [])
        if str(node_id or "").strip() and isinstance(stats, Mapping)
    }
    position_counts = {
        str(node_id or "").strip(): dict(stats)
        for node_id, stats in (raw_position_counts.items() if isinstance(raw_position_counts, Mapping) else [])
        if str(node_id or "").strip() and isinstance(stats, Mapping)
    }

    rows: list[dict[str, object]] = []
    for node_id in sorted(set(caps_by_id) | set(saved_counts) | set(position_counts)):
        caps = caps_by_id.get(node_id, {})
        last_seen_unix = to_int(caps.get("last_seen_unix")) or 0
        num: int | None = None
        if len(node_id) == 9 and node_id.startswith("!"):
            try:
                num = int(node_id[1:], 16)
            except ValueError:
                num = None
        rows.append(
            {
                "id": node_id,
                "num": num,
                "short_name": caps.get("last_short_name"),
                "long_name": caps.get("last_long_name") or node_id,
                "hardware_model": None,
                "role": None,
                "is_licensed": None,
                "last_heard": caps.get("last_seen") or format_epoch(last_seen_unix),
                "last_heard_unix": last_seen_unix,
                "snr": None,
                "rssi": None,
                "hops_away": caps.get("last_hops"),
                "is_favorite": None,
                "battery_level": caps.get("battery_level"),
                "voltage": None,
                "channel_utilization": None,
                "air_util_tx": None,
                "lat": None,
                "lon": None,
            }
        )

    apply_node_saved_counts(rows, saved_counts)
    apply_node_position_counts(rows, position_counts)
    apply_node_historical_names(rows, caps_by_id)
    rows.sort(key=lambda item: int(to_int(item.get("last_heard_unix")) or 0), reverse=True)
    return rows, caps_by_id


def _build_offline_state_loader(
    *,
    target: str,
    revision_info: object,
    startup_error: Exception,
    connecting: bool,
    started_at: float,
    utc_now_fn: UtcNowFn,
    history_store: object | None = None,
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
    radio_link_summary = {
        "state": "connecting" if connecting else "disconnected",
        "connected": False,
        "changed_unix": None,
        "reason": startup_error_text,
        "target": target,
        "source": "startup",
    }

    def state_fn() -> dict[str, object]:
        uptime_seconds = int(max(0, time.time() - started_at))
        cached_nodes, history_caps = _cached_history_node_rows(history_store)
        cached_position_count = sum(
            1
            for caps in history_caps.values()
            if isinstance(caps, Mapping) and bool(caps.get("has_position"))
        )
        return {
            "generated_at": utc_now_fn(),
            "summary": {
                "target": target,
                "uptime_seconds": uptime_seconds,
                "node_count": len(cached_nodes),
                "nodes_with_position": cached_position_count,
                "live_packet_count": 0,
                "edge_count": 0,
                "real_edge_count": 0,
                "recent_packet_buffer": 0,
                "modem_preset": None,
                "disk": {"free_percent": "n/a"},
                "revision": revision_payload,
                "saved_node_count": len(cached_nodes),
                "online_node_count": 0,
                "online_node_count_source": "offline",
                "radio_link": radio_link_summary,
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
            "nodes": cached_nodes,
            "history_caps": history_caps,
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
    history_store_cls: HistoryStoreFactory | None = None,
    mesh_target_label_fn: MeshTargetLabelFn,
    revision_info_fn: RevisionInfoFn,
    utc_now_fn: UtcNowFn,
) -> DashboardRuntimeContext:
    target = mesh_target_label_fn(args)
    revision_info = revision_info_fn()
    started_at = time.time()
    history_db_path = ""
    history_store = None
    if history_store_cls is not None:
        history_db_path = build_shared_history_db_path(
            os.path.abspath(os.path.expanduser(args.history_db))
        )
        history_store = open_optional_history_store(
            args,
            history_store_cls=history_store_cls,
            history_db_path=history_db_path,
        )
    state_fn = _build_offline_state_loader(
        target=target,
        revision_info=revision_info,
        startup_error=startup_error,
        connecting=connecting,
        started_at=started_at,
        utc_now_fn=utc_now_fn,
        history_store=history_store,
    )
    if bool(getattr(args, "games_enable", False)):
        _attach_standalone_zork_service(state_fn)
    return DashboardRuntimeContext(
        target=target,
        iface=_NoopCloseResource(),
        history_db_path=history_db_path if history_store is not None else "",
        history_store=history_store,
        tracker=_OfflineTracker(),
        send_lock=threading.Lock(),
        started_at=started_at,
        revision_info=revision_info,
        state_fn=state_fn,
        node_history_fn=None,  # type: ignore[arg-type]
        summary_metrics_fn=None,  # type: ignore[arg-type]
        send_chat_fn=None,  # type: ignore[arg-type]
        history_enabled=history_store is not None,
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
    build_summary_metrics_loader_fn: BuildSummaryMetricsLoaderFn,
    send_chat_message_fn: SendChatMessageFn,
    send_reaction_packet_fn: SendReactionPacketFn,
    get_local_node_id_fn: GetLocalNodeIdFn,
    normalize_single_emoji_fn: NormalizeSingleEmojiFn,
    to_int_fn: ToIntFn,
    utc_now_fn: UtcNowFn,
    default_chat_max_bytes: int,
    startup_receive_buffer: StartupReceiveBuffer | None = None,
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
        build_summary_metrics_loader_fn=build_summary_metrics_loader_fn,
        build_send_chat_loader_fn=build_send_chat_loader,
        startup_receive_buffer=startup_receive_buffer,
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
    preopened_iface: object | None = None
    preopened_receive_buffer: StartupReceiveBuffer | None = None
    preopened_iface_lock = threading.Lock()

    def _close_preopened_iface() -> None:
        nonlocal preopened_iface, preopened_receive_buffer
        with preopened_iface_lock:
            iface = preopened_iface
            receive_buffer = preopened_receive_buffer
            preopened_iface = None
            preopened_receive_buffer = None
        if receive_buffer is not None:
            receive_buffer.close()
        if iface is None:
            return
        close_fn = getattr(iface, "close", None)
        if callable(close_fn):
            try:
                close_fn()
            except Exception:
                pass

    while True:
        startup_offline = False
        startup_error: Optional[Exception] = None
        context_preopened_iface: object | None = None
        context_preopened_receive_buffer: StartupReceiveBuffer | None = None

        def _open_mesh_interface_with_preopened(open_args: DashboardArgs) -> object:
            nonlocal context_preopened_iface, context_preopened_receive_buffer
            nonlocal preopened_iface, preopened_receive_buffer
            with preopened_iface_lock:
                if preopened_iface is not None:
                    iface = preopened_iface
                    receive_buffer = preopened_receive_buffer
                    preopened_iface = None
                    preopened_receive_buffer = None
                    context_preopened_iface = iface
                    context_preopened_receive_buffer = receive_buffer
                    return iface
            return open_mesh_interface_fn(open_args)

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
                history_store_cls=history_store_cls,
                mesh_target_label_fn=mesh_target_label_fn,
                revision_info_fn=revision_info_fn,
                utc_now_fn=utc_now_fn,
            )
        elif auto_reconnect:
            with preopened_iface_lock:
                startup_receive_buffer = (
                    preopened_receive_buffer if preopened_iface is not None else None
                )
            try:
                context = _build_runtime_context_once(
                    args,
                    mesh_target_label_fn=mesh_target_label_fn,
                    open_mesh_interface_fn=_open_mesh_interface_with_preopened,
                    history_store_cls=history_store_cls,
                    dashboard_tracker_cls=dashboard_tracker_cls,
                    subscribe_fn=subscribe_fn,
                    seed_tracker_fn=seed_tracker_fn,
                    revision_info_fn=revision_info_fn,
                    build_state_fn=build_state_fn,
                    build_node_history_loader_fn=build_node_history_loader_fn,
                    build_summary_metrics_loader_fn=build_summary_metrics_loader_fn,
                    send_chat_message_fn=send_chat_message_fn,
                    send_reaction_packet_fn=send_reaction_packet_fn,
                    get_local_node_id_fn=get_local_node_id_fn,
                    normalize_single_emoji_fn=normalize_single_emoji_fn,
                    to_int_fn=to_int_fn,
                    utc_now_fn=utc_now_fn,
                    default_chat_max_bytes=default_chat_max_bytes,
                    startup_receive_buffer=startup_receive_buffer,
                )
                context_preopened_iface = None
                context_preopened_receive_buffer = None
            except Exception as exc:
                if context_preopened_receive_buffer is not None:
                    context_preopened_receive_buffer.close()
                    context_preopened_receive_buffer = None
                if context_preopened_iface is not None:
                    close_fn = getattr(context_preopened_iface, "close", None)
                    if callable(close_fn):
                        try:
                            close_fn()
                        except Exception:
                            pass
                    context_preopened_iface = None
                _close_preopened_iface()
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
                    history_store_cls=history_store_cls,
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
        try:
            setattr(context.state_fn, "schedule_backend_restart_fn", schedule_backend_restart)
        except Exception:
            pass

        server_parts = build_dashboard_server(
            args=args,
            revision_info=context.revision_info,
            history_enabled=context.history_enabled,
            state_fn=context.state_fn,
            node_history_fn=context.node_history_fn,
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
                nonlocal preopened_iface, preopened_receive_buffer
                attempt = 0
                delay_seconds = 0.5
                while not stop_watcher.wait(delay_seconds):
                    attempt += 1
                    receive_buffer = StartupReceiveBuffer()
                    subscribe_fn(receive_buffer.on_receive, "meshtastic.receive")
                    try:
                        probe_iface = open_mesh_interface_fn(args)
                    except Exception as exc:
                        receive_buffer.close()
                        delay_seconds = min(10.0, 1.0 + attempt)
                        if attempt == 1 or (attempt % 5) == 0:
                            print(
                                f"Waiting for radio link ({exc}). "
                                f"Retrying in {delay_seconds:.0f}s..."
                            )
                        continue
                    with preopened_iface_lock:
                        previous_iface = preopened_iface
                        previous_receive_buffer = preopened_receive_buffer
                        preopened_iface = probe_iface
                        preopened_receive_buffer = receive_buffer
                    if previous_receive_buffer is not None:
                        previous_receive_buffer.close()
                    if previous_iface is not None:
                        close_fn = getattr(previous_iface, "close", None)
                        if callable(close_fn):
                            try:
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
            close_receive_buffer = getattr(
                getattr(context.tracker, "_startup_receive_buffer", None),
                "close",
                None,
            )
            if callable(close_receive_buffer):
                try:
                    close_receive_buffer()
                except Exception:
                    pass
            close_file_transfer = getattr(
                getattr(context.tracker, "_file_transfer_auto_accept_service", None),
                "close",
                None,
            )
            if callable(close_file_transfer):
                try:
                    close_file_transfer()
                except Exception:
                    pass
            close_runtime_resources(
                server=server,
                iface=context.iface,
                history_store=context.history_store,
            )

        if interrupted:
            _close_preopened_iface()
            return
        if startup_offline and auto_reconnect and restart_requested.is_set():
            offline_bootstrap_error = None
            time.sleep(0.5)
            continue
        if startup_offline:
            _close_preopened_iface()
            return
        if auto_reconnect and restart_requested.is_set():
            reason = str(getattr(context.tracker, "radio_link_error", "") or "").strip()
            offline_bootstrap_error = RuntimeError(reason or "radio link lost")
            print("Radio link lost. Serving offline UI while reconnecting...")
            time.sleep(0.5)
            continue
        return
