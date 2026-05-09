from typing import Optional

from .send_chat_contracts import SendLock, SendTextInterface
from .runtime_send_contracts import SendChatRuntimeDependencies
from .runtime_send_dependencies import (
    TrackerChatRecorder,
    build_send_chat_runtime_dependencies_from_legacy_args,
)
from .runtime_types import (
    GetLocalNodeIdFn,
    NormalizeSingleEmojiFn,
    SendChatFn,
    SendChatMessageFn,
    SendReactionPacketFn,
    ToIntFn,
    UtcNowFn,
)


def build_send_chat_loader(
    *,
    iface: SendTextInterface,
    tracker: TrackerChatRecorder,
    send_lock: SendLock,
    send_chat_message_fn: SendChatMessageFn,
    send_reaction_packet_fn: SendReactionPacketFn,
    get_local_node_id_fn: GetLocalNodeIdFn,
    chat_max_bytes: int,
    normalize_single_emoji_fn: NormalizeSingleEmojiFn,
    to_int_fn: ToIntFn,
    utc_now_fn: UtcNowFn,
) -> SendChatFn:
    dependencies = build_send_chat_runtime_dependencies_from_legacy_args(
        iface=iface,
        tracker=tracker,
        send_lock=send_lock,
        send_reaction_packet_fn=send_reaction_packet_fn,
        get_local_node_id_fn=get_local_node_id_fn,
        chat_max_bytes=chat_max_bytes,
        normalize_single_emoji_fn=normalize_single_emoji_fn,
        to_int_fn=to_int_fn,
        utc_now_fn=utc_now_fn,
    )
    return build_send_chat_loader_with_dependencies(
        send_chat_message_fn=send_chat_message_fn,
        dependencies=dependencies,
    )


def build_send_chat_loader_with_dependencies(
    *,
    send_chat_message_fn: SendChatMessageFn,
    dependencies: SendChatRuntimeDependencies,
) -> SendChatFn:
    def send_chat_fn(
        text: object,
        destination: object = None,
        channel_index: Optional[int] = None,
        reply_id: Optional[int] = None,
        retry_of: Optional[int] = None,
        emoji: object = None,
    ) -> dict:
        return send_chat_message_fn(
            text=text,
            destination=destination,
            channel_index=channel_index,
            reply_id=reply_id,
            retry_of=retry_of,
            emoji=emoji,
            iface=dependencies.iface,
            send_lock=dependencies.send_lock,
            send_reaction_packet_fn=dependencies.send_reaction_packet_fn,
            local_node_id_fn=dependencies.local_node_id_fn,
            record_local_chat_fn=dependencies.record_local_chat_fn,
            get_delivery_state_fn=dependencies.get_delivery_state_fn,
            chat_max_bytes=dependencies.chat_max_bytes,
            normalize_single_emoji_fn=dependencies.normalize_single_emoji_fn,
            to_int_fn=dependencies.to_int_fn,
            now_text_fn=dependencies.utc_now_fn,
        )

    return send_chat_fn
