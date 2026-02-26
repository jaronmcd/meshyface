from typing import Optional

from .chat_send import (
    build_chat_send_response,
    delivery_state_for_send,
    prepare_chat_send_input,
)
from .send_chat_contracts import SendLock, SendTextInterface
from .runtime_types import (
    LocalNodeIdFn,
    NormalizeSingleEmojiFn,
    RecordLocalChatFn,
    SendReactionPacketFn,
    ToIntFn,
    UtcNowFn,
)


def send_chat_message(
    *,
    text: object,
    destination: object = None,
    channel_index: Optional[int] = None,
    reply_id: Optional[int] = None,
    retry_of: Optional[int] = None,
    emoji: object = None,
    iface: SendTextInterface,
    send_lock: SendLock,
    send_reaction_packet_fn: SendReactionPacketFn,
    local_node_id_fn: LocalNodeIdFn,
    record_local_chat_fn: RecordLocalChatFn,
    chat_max_bytes: int,
    normalize_single_emoji_fn: NormalizeSingleEmojiFn,
    to_int_fn: ToIntFn,
    now_text_fn: UtcNowFn,
) -> dict[str, object]:
    prepared = prepare_chat_send_input(
        text=text,
        destination=destination,
        channel_index=channel_index,
        reply_id=reply_id,
        retry_of=retry_of,
        emoji=emoji,
        chat_max_bytes=chat_max_bytes,
        normalize_single_emoji_fn=normalize_single_emoji_fn,
        to_int_fn=to_int_fn,
    )

    dest = str(prepared.get("destination") or "^all")
    chan_candidate = to_int_fn(prepared.get("channel_index"))
    chan = chan_candidate if chan_candidate is not None and chan_candidate >= 0 else 0
    clean_text = str(prepared.get("text") or "")
    clean_reply_id = to_int_fn(prepared.get("reply_id"))
    clean_retry_of = to_int_fn(prepared.get("retry_of"))
    clean_emoji_raw = prepared.get("emoji")
    clean_emoji = str(clean_emoji_raw or "") if clean_emoji_raw is not None else None
    clean_emoji_codepoint = to_int_fn(prepared.get("emoji_codepoint"))
    has_reaction = bool(prepared.get("is_reaction"))
    should_request_ack = bool(prepared.get("ack_requested"))
    with send_lock:
        if has_reaction:
            sent_packet = send_reaction_packet_fn(
                iface=iface,
                destination_id=dest,
                channel_index=chan,
                reply_id=clean_reply_id,
                emoji_codepoint=clean_emoji_codepoint,
                emoji_text=clean_emoji,
                want_ack=False,
            )
        else:
            sent_packet = iface.sendText(
                clean_text,
                destinationId=dest,
                wantAck=should_request_ack,
                channelIndex=chan,
                replyId=clean_reply_id if clean_reply_id and clean_reply_id > 0 else None,
            )

    local_id = local_node_id_fn()
    sent_packet_id = to_int_fn(getattr(sent_packet, "id", None))
    delivery_state = delivery_state_for_send(
        ack_requested=should_request_ack,
        sent_packet_id=sent_packet_id,
    )
    record_local_chat_fn(
        text=clean_text if clean_text else "",
        from_id=local_id,
        to_id=dest,
        channel_index=chan,
        message_id=sent_packet_id,
        reply_id=clean_reply_id,
        emoji=clean_emoji,
        emoji_codepoint=clean_emoji_codepoint,
        is_reaction=has_reaction,
        ack_requested=should_request_ack,
        retry_of=clean_retry_of,
    )
    return build_chat_send_response(
        now_text_fn=now_text_fn,
        local_node_id=local_id,
        destination=dest,
        channel_index=chan,
        message_id=sent_packet_id,
        reply_id=clean_reply_id,
        retry_of=clean_retry_of,
        ack_requested=should_request_ack,
        delivery_state=delivery_state,
        text=clean_text,
        is_reaction=has_reaction,
        emoji=clean_emoji,
        emoji_codepoint=clean_emoji_codepoint,
    )
