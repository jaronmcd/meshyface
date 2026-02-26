from typing import Protocol

from .send_chat_contracts import SendLock, SendTextInterface
from .runtime_send_contracts import SendChatRuntimeDependencies
from .runtime_types import (
    GetLocalNodeIdFn,
    NormalizeSingleEmojiFn,
    RecordLocalChatFn,
    SendReactionPacketFn,
    ToIntFn,
    UtcNowFn,
)


class TrackerChatRecorder(Protocol):
    record_local_chat: RecordLocalChatFn


def build_send_chat_runtime_dependencies_from_legacy_args(
    *,
    iface: SendTextInterface,
    tracker: TrackerChatRecorder,
    send_lock: SendLock,
    send_reaction_packet_fn: SendReactionPacketFn,
    get_local_node_id_fn: GetLocalNodeIdFn,
    chat_max_bytes: int,
    normalize_single_emoji_fn: NormalizeSingleEmojiFn,
    to_int_fn: ToIntFn,
    utc_now_fn: UtcNowFn,
) -> SendChatRuntimeDependencies:
    return SendChatRuntimeDependencies(
        iface=iface,
        send_lock=send_lock,
        send_reaction_packet_fn=send_reaction_packet_fn,
        local_node_id_fn=lambda: get_local_node_id_fn(iface),
        record_local_chat_fn=tracker.record_local_chat,
        chat_max_bytes=chat_max_bytes,
        normalize_single_emoji_fn=normalize_single_emoji_fn,
        to_int_fn=to_int_fn,
        utc_now_fn=utc_now_fn,
    )
