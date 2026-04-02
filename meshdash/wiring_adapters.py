from .runtime_types import (
    BuildStateFn,
    BuildStateWithSensitiveFn,
    GetLocalNodeIdFn,
    MakeHttpHandlerFn,
    NodeHistoryFn,
    OnlineActivityFn,
    SummaryMetricsHistoryFn,
    RawGetLocalNodeIdFn,
    SendChatFn,
    SendReactionPacketFn,
    SendReactionPacketWithModulesFn,
    StateFn,
    ToIntFn,
    ToJsonableFn,
)


def build_state_builder(
    *,
    build_state_fn: BuildStateWithSensitiveFn,
    sensitive_field_names: set[str],
) -> BuildStateFn:
    def state_with_sensitive_fields(**kwargs: object) -> dict[str, object]:
        return build_state_fn(
            sensitive_field_names=sensitive_field_names,
            **kwargs,
        )

    # Expose the sensitive key list for optional on-demand/raw endpoints.
    # (Functions are objects in Python; attaching attributes keeps the public
    # type surface unchanged while still enabling optimizations.)
    try:
        setattr(state_with_sensitive_fields, "_sensitive_field_names", sensitive_field_names)
    except Exception:
        pass

    return state_with_sensitive_fields


def build_reaction_sender(
    *,
    send_emoji_reaction_packet_fn: SendReactionPacketWithModulesFn,
    mesh_pb2_module: object,
    portnums_pb2_module: object,
) -> SendReactionPacketFn:
    def send_reaction_packet(**kwargs: object) -> object:
        return send_emoji_reaction_packet_fn(
            mesh_pb2_module=mesh_pb2_module,
            portnums_pb2_module=portnums_pb2_module,
            **kwargs,
        )

    return send_reaction_packet


def build_local_node_id_getter(
    *,
    get_local_node_id_fn: RawGetLocalNodeIdFn,
    meshtastic_module: object,
    to_jsonable_fn: ToJsonableFn,
    to_int_fn: ToIntFn,
) -> GetLocalNodeIdFn:
    def get_local_node_id(iface: object) -> str:
        return get_local_node_id_fn(
            iface,
            meshtastic_module=meshtastic_module,
            to_jsonable_fn=to_jsonable_fn,
            to_int_fn=to_int_fn,
        )

    return get_local_node_id


def build_http_handler_factory(
    *,
    make_http_handler_fn: MakeHttpHandlerFn,
    default_node_history_hours: int,
    to_int_fn: ToIntFn,
) -> MakeHttpHandlerFn:
    def make_http_handler(
        html_text: str,
        state_fn: StateFn,
        node_history_fn: NodeHistoryFn | None = None,
        online_activity_fn: OnlineActivityFn | None = None,
        summary_metrics_fn: SummaryMetricsHistoryFn | None = None,
        send_chat_fn: SendChatFn | None = None,
    ) -> object:
        return make_http_handler_fn(
            html_text=html_text,
            state_fn=state_fn,
            node_history_fn=node_history_fn,
            online_activity_fn=online_activity_fn,
            summary_metrics_fn=summary_metrics_fn,
            send_chat_fn=send_chat_fn,
            default_node_history_hours=default_node_history_hours,
            to_int_fn=to_int_fn,
        )

    return make_http_handler
