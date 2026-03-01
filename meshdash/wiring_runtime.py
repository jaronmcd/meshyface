from dataclasses import dataclass
from typing import Protocol

from .dashboard_setup_contracts import DashboardTrackerFactory, HistoryStoreFactory
from .runtime_types import (
    BuildNodeHistoryLoaderFn,
    BuildOnlineActivityLoaderFn,
    BuildSummaryMetricsLoaderFn,
    BuildStateFn,
    BuildStateWithSensitiveFn,
    GetLocalNodeIdFn,
    GuessLanIpv4Fn,
    MakeHttpHandlerFn,
    MeshTargetLabelFn,
    NormalizeSingleEmojiFn,
    OpenMeshInterfaceFn,
    RevisionInfoFn,
    RenderHtmlFn,
    SendChatMessageFn,
    SendReactionPacketFn,
    SendReactionPacketWithModulesFn,
    SeedTrackerFn,
    SubscribeFn,
    ToIntFn,
    ToJsonableFn,
    UtcNowFn,
)
from .wiring_adapters import (
    build_http_handler_factory as _build_http_handler_factory_helper,
    build_local_node_id_getter as _build_local_node_id_getter_helper,
    build_reaction_sender as _build_reaction_sender_helper,
    build_state_builder as _build_state_builder_helper,
)


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
    build_online_activity_loader_fn: BuildOnlineActivityLoaderFn
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
    meshtastic_module: object,
    pub_module: PubSubModule,
    mesh_target_label_fn: MeshTargetLabelFn,
    open_mesh_interface_fn: OpenMeshInterfaceFn,
    history_store_cls: HistoryStoreFactory,
    dashboard_tracker_cls: DashboardTrackerFactory,
    seed_tracker_fn: SeedTrackerFn,
    revision_info_fn: RevisionInfoFn,
    build_state_fn: BuildStateWithSensitiveFn,
    build_state_lite_fn: BuildStateWithSensitiveFn | None = None,
    sensitive_field_names: set[str],
    build_node_history_loader_fn: BuildNodeHistoryLoaderFn,
    build_online_activity_loader_fn: BuildOnlineActivityLoaderFn,
    build_summary_metrics_loader_fn: BuildSummaryMetricsLoaderFn,
    send_chat_message_fn: SendChatMessageFn,
    send_emoji_reaction_packet_fn: SendReactionPacketWithModulesFn,
    mesh_pb2_module: object,
    portnums_pb2_module: object,
    get_local_node_id_fn: GetLocalNodeIdFn,
    to_jsonable_fn: ToJsonableFn,
    normalize_single_emoji_fn: NormalizeSingleEmojiFn,
    to_int_fn: ToIntFn,
    utc_now_fn: UtcNowFn,
    render_html_fn: RenderHtmlFn,
    make_http_handler_fn: MakeHttpHandlerFn,
    default_node_history_hours: int,
    guess_lan_ipv4_fn: GuessLanIpv4Fn,
    default_chat_max_bytes: int,
) -> DashboardRuntimeDependencies:
    build_state_with_sensitive_fields = _build_state_builder_helper(
        build_state_fn=build_state_fn,
        sensitive_field_names=sensitive_field_names,
    )
    if build_state_lite_fn is not None:
        build_state_lite_with_sensitive_fields = _build_state_builder_helper(
            build_state_fn=build_state_lite_fn,
            sensitive_field_names=sensitive_field_names,
        )
        # Attach the lite builder so downstream components can opt into it
        # without expanding every Protocol/dataclass.
        try:
            setattr(build_state_with_sensitive_fields, "lite", build_state_lite_with_sensitive_fields)
        except Exception:
            pass
    send_reaction_packet = _build_reaction_sender_helper(
        send_emoji_reaction_packet_fn=send_emoji_reaction_packet_fn,
        mesh_pb2_module=mesh_pb2_module,
        portnums_pb2_module=portnums_pb2_module,
    )
    get_local_node_id = _build_local_node_id_getter_helper(
        get_local_node_id_fn=get_local_node_id_fn,
        meshtastic_module=meshtastic_module,
        to_jsonable_fn=to_jsonable_fn,
        to_int_fn=to_int_fn,
    )
    make_http_handler = _build_http_handler_factory_helper(
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
        build_online_activity_loader_fn=build_online_activity_loader_fn,
        build_summary_metrics_loader_fn=build_summary_metrics_loader_fn,
        send_chat_message_fn=send_chat_message_fn,
        send_reaction_packet_fn=send_reaction_packet,
        get_local_node_id_fn=get_local_node_id,
        normalize_single_emoji_fn=normalize_single_emoji_fn,
        to_int_fn=to_int_fn,
        utc_now_fn=utc_now_fn,
        render_html_fn=render_html_fn,
        make_http_handler_fn=make_http_handler,
        guess_lan_ipv4_fn=guess_lan_ipv4_fn,
        default_chat_max_bytes=default_chat_max_bytes,
    )
