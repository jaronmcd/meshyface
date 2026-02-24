from typing import Any, Callable, Dict

from .wiring_adapters import (
    build_http_handler_factory as _build_http_handler_factory_helper,
    build_local_node_id_getter as _build_local_node_id_getter_helper,
    build_reaction_sender as _build_reaction_sender_helper,
    build_state_builder as _build_state_builder_helper,
)


def ensure_runtime_dependencies(*, meshtastic_module: Any, pub_module: Any) -> None:
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
    meshtastic_module: Any,
    pub_module: Any,
    mesh_target_label_fn: Callable[[Any], str],
    open_mesh_interface_fn: Callable[[Any], Any],
    history_store_cls: Any,
    dashboard_tracker_cls: Any,
    seed_tracker_fn: Callable[..., None],
    revision_info_fn: Callable[[], dict],
    build_state_fn: Callable[..., dict],
    sensitive_field_names: set[str],
    build_node_history_loader_fn: Callable[..., Callable[..., dict]],
    build_online_activity_loader_fn: Callable[..., Callable[..., dict]],
    send_chat_message_fn: Callable[..., dict],
    send_emoji_reaction_packet_fn: Callable[..., Any],
    mesh_pb2_module: Any,
    portnums_pb2_module: Any,
    get_local_node_id_fn: Callable[..., str],
    to_jsonable_fn: Callable[[Any], Any],
    normalize_single_emoji_fn: Callable[[Any], Any],
    to_int_fn: Callable[[Any], Any],
    utc_now_fn: Callable[[], str],
    render_html_fn: Callable[..., str],
    make_http_handler_fn: Callable[..., Any],
    default_node_history_hours: int,
    guess_lan_ipv4_fn: Callable[[], Any],
    default_chat_max_bytes: int,
) -> Dict[str, Any]:
    build_state_with_sensitive_fields = _build_state_builder_helper(
        build_state_fn=build_state_fn,
        sensitive_field_names=sensitive_field_names,
    )
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

    return {
        "mesh_target_label_fn": mesh_target_label_fn,
        "open_mesh_interface_fn": open_mesh_interface_fn,
        "history_store_cls": history_store_cls,
        "dashboard_tracker_cls": dashboard_tracker_cls,
        "subscribe_fn": pub_module.subscribe,
        "seed_tracker_fn": seed_tracker_fn,
        "revision_info_fn": revision_info_fn,
        "build_state_fn": build_state_with_sensitive_fields,
        "build_node_history_loader_fn": build_node_history_loader_fn,
        "build_online_activity_loader_fn": build_online_activity_loader_fn,
        "send_chat_message_fn": send_chat_message_fn,
        "send_reaction_packet_fn": send_reaction_packet,
        "get_local_node_id_fn": get_local_node_id,
        "normalize_single_emoji_fn": normalize_single_emoji_fn,
        "to_int_fn": to_int_fn,
        "utc_now_fn": utc_now_fn,
        "render_html_fn": render_html_fn,
        "make_http_handler_fn": make_http_handler,
        "guess_lan_ipv4_fn": guess_lan_ipv4_fn,
        "default_chat_max_bytes": default_chat_max_bytes,
    }
