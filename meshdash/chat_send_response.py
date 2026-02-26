from typing import Callable, Optional


def delivery_state_for_send(
    *,
    ack_requested: bool,
    sent_packet_id: Optional[int],
) -> str:
    if not ack_requested:
        return "sent"
    if sent_packet_id is not None and sent_packet_id > 0:
        return "pending"
    return "error"


def build_chat_send_response(
    *,
    now_text_fn: Callable[[], str],
    local_node_id: str,
    destination: str,
    channel_index: int,
    message_id: Optional[int],
    reply_id: Optional[int],
    retry_of: Optional[int],
    ack_requested: bool,
    delivery_state: str,
    text: str,
    is_reaction: bool,
    emoji: Optional[str],
    emoji_codepoint: Optional[int],
) -> dict[str, object]:
    response: dict[str, object] = {
        "ok": True,
        "sent_at": now_text_fn(),
        "from": local_node_id,
        "to": destination,
        "channel_index": channel_index,
        "message_id": message_id,
        "reply_id": reply_id,
        "ack_requested": ack_requested,
        "delivery_state": delivery_state,
    }
    if retry_of is not None and retry_of > 0:
        response["retry_of"] = retry_of
    if is_reaction:
        response["reaction"] = emoji
        response["reaction_codepoint"] = emoji_codepoint
        response["text"] = ""
    else:
        response["text"] = text
    return response
