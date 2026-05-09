import threading
import time
from typing import Callable, Optional

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


_OUTGOING_RETRY_ACK_WAIT_SECONDS = 45.0
_OUTGOING_RETRY_ACK_POLL_SECONDS = 1.0
_OUTGOING_RETRY_LIMIT = 1
_ACKED_DELIVERY_STATES = {"ack", "acked", "delivered"}


def _sent_packet_id(sent_packet: object, *, to_int_fn: ToIntFn) -> Optional[int]:
    if isinstance(sent_packet, dict):
        parsed = to_int_fn(
            sent_packet.get("id")
            or sent_packet.get("packet_id")
            or sent_packet.get("packetId")
        )
    else:
        parsed = to_int_fn(getattr(sent_packet, "id", None))
    return parsed if parsed is not None and parsed > 0 else None


def _delivery_is_acked(
    get_delivery_state_fn: Callable[[object], object] | None,
    message_id: object,
) -> bool:
    if get_delivery_state_fn is None:
        return False
    try:
        state = get_delivery_state_fn(message_id)
    except Exception:
        return False
    if isinstance(state, dict):
        raw_state = state.get("delivery_state") or state.get("state")
    else:
        raw_state = state
    return str(raw_state or "").strip().lower() in _ACKED_DELIVERY_STATES


def _wait_for_ack_or_timeout(
    *,
    get_delivery_state_fn: Callable[[object], object] | None,
    message_id: int,
    wait_seconds: float,
    poll_seconds: float,
    sleep_fn: Callable[[float], None],
) -> bool:
    if _delivery_is_acked(get_delivery_state_fn, message_id):
        return True
    if wait_seconds <= 0:
        return False
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if _delivery_is_acked(get_delivery_state_fn, message_id):
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return _delivery_is_acked(get_delivery_state_fn, message_id)
        sleep_fn(min(max(0.05, poll_seconds), remaining))
    return _delivery_is_acked(get_delivery_state_fn, message_id)


def _retry_outgoing_chat_once_if_unacked(
    *,
    text: str,
    destination: str,
    channel_index: int,
    reply_id: Optional[int],
    original_message_id: int,
    iface: SendTextInterface,
    send_lock: SendLock,
    record_local_chat_fn: RecordLocalChatFn,
    local_node_id: str,
    to_int_fn: ToIntFn,
    get_delivery_state_fn: Callable[[object], object] | None,
    wait_seconds: float,
    poll_seconds: float,
    sleep_fn: Callable[[float], None],
) -> None:
    if _wait_for_ack_or_timeout(
        get_delivery_state_fn=get_delivery_state_fn,
        message_id=original_message_id,
        wait_seconds=wait_seconds,
        poll_seconds=poll_seconds,
        sleep_fn=sleep_fn,
    ):
        return
    with send_lock:
        sent_packet = iface.sendText(
            text,
            destinationId=destination,
            wantAck=True,
            channelIndex=channel_index,
            replyId=reply_id if reply_id and reply_id > 0 else None,
        )
    record_local_chat_fn(
        text=text,
        from_id=local_node_id,
        to_id=destination,
        channel_index=channel_index,
        message_id=_sent_packet_id(sent_packet, to_int_fn=to_int_fn),
        reply_id=reply_id,
        ack_requested=True,
        retry_of=original_message_id,
    )


def _start_outgoing_retry_if_needed(
    *,
    should_request_ack: bool,
    has_reaction: bool,
    retry_of: Optional[int],
    destination: str,
    text: str,
    channel_index: int,
    reply_id: Optional[int],
    sent_packet_id: Optional[int],
    iface: SendTextInterface,
    send_lock: SendLock,
    record_local_chat_fn: RecordLocalChatFn,
    local_node_id: str,
    to_int_fn: ToIntFn,
    get_delivery_state_fn: Callable[[object], object] | None,
    outgoing_retry_limit: int,
    outgoing_retry_wait_seconds: float,
    outgoing_retry_poll_seconds: float,
    outgoing_retry_async: bool,
    sleep_fn: Callable[[float], None],
) -> None:
    if not should_request_ack or has_reaction:
        return
    if retry_of is not None and retry_of > 0:
        return
    if destination == "^all" or sent_packet_id is None or sent_packet_id <= 0:
        return
    if get_delivery_state_fn is None or outgoing_retry_limit <= 0:
        return

    kwargs = {
        "text": text,
        "destination": destination,
        "channel_index": channel_index,
        "reply_id": reply_id,
        "original_message_id": sent_packet_id,
        "iface": iface,
        "send_lock": send_lock,
        "record_local_chat_fn": record_local_chat_fn,
        "local_node_id": local_node_id,
        "to_int_fn": to_int_fn,
        "get_delivery_state_fn": get_delivery_state_fn,
        "wait_seconds": max(0.0, float(outgoing_retry_wait_seconds)),
        "poll_seconds": max(0.05, float(outgoing_retry_poll_seconds)),
        "sleep_fn": sleep_fn,
    }
    if outgoing_retry_async:
        threading.Thread(
            target=_retry_outgoing_chat_once_if_unacked,
            kwargs=kwargs,
            daemon=True,
        ).start()
        return
    _retry_outgoing_chat_once_if_unacked(**kwargs)


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
    get_delivery_state_fn: Callable[[object], object] | None = None,
    outgoing_retry_wait_seconds: float = _OUTGOING_RETRY_ACK_WAIT_SECONDS,
    outgoing_retry_poll_seconds: float = _OUTGOING_RETRY_ACK_POLL_SECONDS,
    outgoing_retry_limit: int = _OUTGOING_RETRY_LIMIT,
    outgoing_retry_async: bool = True,
    sleep_fn: Callable[[float], None] = time.sleep,
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
    sent_packet_id = _sent_packet_id(sent_packet, to_int_fn=to_int_fn)
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
    _start_outgoing_retry_if_needed(
        should_request_ack=should_request_ack,
        has_reaction=has_reaction,
        retry_of=clean_retry_of,
        destination=dest,
        text=clean_text,
        channel_index=chan,
        reply_id=clean_reply_id,
        sent_packet_id=sent_packet_id,
        iface=iface,
        send_lock=send_lock,
        record_local_chat_fn=record_local_chat_fn,
        local_node_id=local_id,
        to_int_fn=to_int_fn,
        get_delivery_state_fn=get_delivery_state_fn,
        outgoing_retry_limit=outgoing_retry_limit,
        outgoing_retry_wait_seconds=outgoing_retry_wait_seconds,
        outgoing_retry_poll_seconds=outgoing_retry_poll_seconds,
        outgoing_retry_async=outgoing_retry_async,
        sleep_fn=sleep_fn,
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
