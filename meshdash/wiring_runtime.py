from dataclasses import dataclass
from typing import Protocol

from .dashboard_setup_contracts import DashboardTrackerFactory, HistoryStoreFactory
from .runtime_types import (
    BuildNodeHistoryLoaderFn,
    BuildSummaryMetricsLoaderFn,
    BuildStateFn,
    BuildStateWithSensitiveFn,
    GetLocalNodeIdFn,
    GuessLanIpv4Fn,
    MakeHttpHandlerFn,
    MeshTargetLabelFn,
    NodeHistoryFn,
    NormalizeSingleEmojiFn,
    OpenMeshInterfaceFn,
    RevisionInfoFn,
    RenderHtmlFn,
    SendChatFn,
    SendChatMessageFn,
    SendReactionPacketFn,
    SeedTrackerFn,
    StateFn,
    SummaryMetricsHistoryFn,
    SubscribeFn,
    ToIntFn,
    UtcNowFn,
)


def _build_state_builder(
    *,
    build_state_fn: BuildStateWithSensitiveFn,
    sensitive_field_names: set[str],
) -> BuildStateFn:
    def state_with_sensitive_fields(**kwargs: object) -> dict[str, object]:
        return build_state_fn(
            sensitive_field_names=sensitive_field_names,
            **kwargs,
        )

    try:
        setattr(state_with_sensitive_fields, "_sensitive_field_names", sensitive_field_names)
    except Exception:
        pass

    return state_with_sensitive_fields


def _build_http_handler_factory(
    *,
    make_http_handler_fn: MakeHttpHandlerFn,
    default_node_history_hours: int,
    to_int_fn: ToIntFn,
) -> MakeHttpHandlerFn:
    def make_http_handler(
        html_text: str,
        state_fn: StateFn,
        node_history_fn: NodeHistoryFn | None = None,
        summary_metrics_fn: SummaryMetricsHistoryFn | None = None,
        send_chat_fn: SendChatFn | None = None,
    ) -> object:
        return make_http_handler_fn(
            html_text=html_text,
            state_fn=state_fn,
            node_history_fn=node_history_fn,
            summary_metrics_fn=summary_metrics_fn,
            send_chat_fn=send_chat_fn,
            default_node_history_hours=default_node_history_hours,
            to_int_fn=to_int_fn,
        )

    return make_http_handler


@dataclass(frozen=True)
class DashboardRuntimeDependencies:
    mesh_target_label_fn: MeshTargetLabelFn
    open_mesh_interface_fn: OpenMeshInterfaceFn
    history_store_cls: HistoryStoreFactory
    dashboard_tracker_cls: DashboardTrackerFactory
    subscribe_fn: SubscribeFn
    seed_tracker_fn: SeedTrackerFn
    revision_info_fn: RevisionInfoFn
    build_state_fn: BuildStateFn
    build_node_history_loader_fn: BuildNodeHistoryLoaderFn
    build_summary_metrics_loader_fn: BuildSummaryMetricsLoaderFn
    send_chat_message_fn: SendChatMessageFn
    send_reaction_packet_fn: SendReactionPacketFn
    get_local_node_id_fn: GetLocalNodeIdFn
    normalize_single_emoji_fn: NormalizeSingleEmojiFn
    to_int_fn: ToIntFn
    utc_now_fn: UtcNowFn
    render_html_fn: RenderHtmlFn
    make_http_handler_fn: MakeHttpHandlerFn
    guess_lan_ipv4_fn: GuessLanIpv4Fn
    default_chat_max_bytes: int


class PubSubModule(Protocol):
    def subscribe(self, callback: object, topic: str) -> None:
        ...


def ensure_runtime_dependencies(*, meshtastic_module: object | None, pub_module: object | None) -> None:
    if meshtastic_module is None:
        raise RuntimeError(
            "meshtastic Python package is required. Install with: pip install meshtastic"
        )
    if pub_module is None:
        raise RuntimeError(
            "pypubsub is required. Install with: pip install pypubsub"
        )


def build_dashboard_runtime_dependencies(
    *,
    pub_module: PubSubModule,
    mesh_target_label_fn: MeshTargetLabelFn,
    open_mesh_interface_fn: OpenMeshInterfaceFn,
    history_store_cls: HistoryStoreFactory,
    dashboard_tracker_cls: DashboardTrackerFactory,
    seed_tracker_fn: SeedTrackerFn,
    revision_info_fn: RevisionInfoFn,
    build_state_fn: BuildStateWithSensitiveFn,
    build_state_lite_fn: BuildStateWithSensitiveFn | None = None,
    build_state_lite_chat_fn: BuildStateWithSensitiveFn | None = None,
    build_state_lite_network_fn: BuildStateWithSensitiveFn | None = None,
    build_state_lite_network_graph_fn: BuildStateWithSensitiveFn | None = None,
    build_state_lite_network_map_fn: BuildStateWithSensitiveFn | None = None,
    build_state_lite_status_fn: BuildStateWithSensitiveFn | None = None,
    build_state_lite_console_fn: BuildStateWithSensitiveFn | None = None,
    sensitive_field_names: set[str],
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
    default_node_history_hours: int,
    guess_lan_ipv4_fn: GuessLanIpv4Fn,
    default_chat_max_bytes: int,
) -> DashboardRuntimeDependencies:
    build_state_with_sensitive_fields = _build_state_builder(
        build_state_fn=build_state_fn,
        sensitive_field_names=sensitive_field_names,
    )
    if build_state_lite_fn is not None:
        build_state_lite_with_sensitive_fields = _build_state_builder(
            build_state_fn=build_state_lite_fn,
            sensitive_field_names=sensitive_field_names,
        )
        # Attach the lite builder so downstream components can opt into it
        # without expanding every Protocol/dataclass.
        try:
            setattr(build_state_with_sensitive_fields, "lite", build_state_lite_with_sensitive_fields)
        except Exception:
            pass
    if build_state_lite_chat_fn is not None:
        build_state_lite_chat_with_sensitive_fields = _build_state_builder(
            build_state_fn=build_state_lite_chat_fn,
            sensitive_field_names=sensitive_field_names,
        )
        try:
            setattr(build_state_with_sensitive_fields, "lite_chat", build_state_lite_chat_with_sensitive_fields)
        except Exception:
            pass
    if build_state_lite_network_fn is not None:
        build_state_lite_network_with_sensitive_fields = _build_state_builder(
            build_state_fn=build_state_lite_network_fn,
            sensitive_field_names=sensitive_field_names,
        )
        try:
            setattr(build_state_with_sensitive_fields, "lite_network", build_state_lite_network_with_sensitive_fields)
        except Exception:
            pass
    if build_state_lite_network_graph_fn is not None:
        build_state_lite_network_graph_with_sensitive_fields = _build_state_builder(
            build_state_fn=build_state_lite_network_graph_fn,
            sensitive_field_names=sensitive_field_names,
        )
        try:
            setattr(
                build_state_with_sensitive_fields,
                "lite_network_graph",
                build_state_lite_network_graph_with_sensitive_fields,
            )
        except Exception:
            pass
    if build_state_lite_network_map_fn is not None:
        build_state_lite_network_map_with_sensitive_fields = _build_state_builder(
            build_state_fn=build_state_lite_network_map_fn,
            sensitive_field_names=sensitive_field_names,
        )
        try:
            setattr(build_state_with_sensitive_fields, "lite_network_map", build_state_lite_network_map_with_sensitive_fields)
        except Exception:
            pass
    if build_state_lite_status_fn is not None:
        build_state_lite_status_with_sensitive_fields = _build_state_builder(
            build_state_fn=build_state_lite_status_fn,
            sensitive_field_names=sensitive_field_names,
        )
        try:
            setattr(build_state_with_sensitive_fields, "lite_status", build_state_lite_status_with_sensitive_fields)
        except Exception:
            pass
    if build_state_lite_console_fn is not None:
        build_state_lite_console_with_sensitive_fields = _build_state_builder(
            build_state_fn=build_state_lite_console_fn,
            sensitive_field_names=sensitive_field_names,
        )
        try:
            setattr(build_state_with_sensitive_fields, "lite_console", build_state_lite_console_with_sensitive_fields)
        except Exception:
            pass
    make_http_handler = _build_http_handler_factory(
        make_http_handler_fn=make_http_handler_fn,
        default_node_history_hours=default_node_history_hours,
        to_int_fn=to_int_fn,
    )

    return DashboardRuntimeDependencies(
        mesh_target_label_fn=mesh_target_label_fn,
        open_mesh_interface_fn=open_mesh_interface_fn,
        history_store_cls=history_store_cls,
        dashboard_tracker_cls=dashboard_tracker_cls,
        subscribe_fn=pub_module.subscribe,
        seed_tracker_fn=seed_tracker_fn,
        revision_info_fn=revision_info_fn,
        build_state_fn=build_state_with_sensitive_fields,
        build_node_history_loader_fn=build_node_history_loader_fn,
        build_summary_metrics_loader_fn=build_summary_metrics_loader_fn,
        send_chat_message_fn=send_chat_message_fn,
        send_reaction_packet_fn=send_reaction_packet_fn,
        get_local_node_id_fn=get_local_node_id_fn,
        normalize_single_emoji_fn=normalize_single_emoji_fn,
        to_int_fn=to_int_fn,
        utc_now_fn=utc_now_fn,
        render_html_fn=render_html_fn,
        make_http_handler_fn=make_http_handler,
        guess_lan_ipv4_fn=guess_lan_ipv4_fn,
        default_chat_max_bytes=default_chat_max_bytes,
    )
