from typing import Any, Callable, Dict, Optional


def empty_node_history(node_id: str) -> Dict[str, Any]:
    return {"node_id": str(node_id or ""), "points": [], "positions": [], "summary": {}}


def empty_online_activity(window_hours: int) -> Dict[str, Any]:
    clean_hours = int(window_hours) if isinstance(window_hours, int) and window_hours > 0 else 72
    return {
        "window_hours": clean_hours,
        "timezone": "local",
        "timezone_label": "local",
        "points": [],
        "hourly_profile": [
            {
                "hour": hour,
                "label": f"{hour:02d}:00",
                "avg_online_nodes": None,
                "sample_hours": 0,
                "peak_online_nodes": 0,
            }
            for hour in range(24)
        ],
        "summary": {
            "sample_hours": 0,
            "distinct_nodes": 0,
            "max_online_nodes": 0,
            "avg_online_nodes": None,
            "best_hour": None,
            "best_hour_label": None,
            "best_hour_avg_online_nodes": None,
            "window_start": None,
            "window_end": None,
        },
    }


def build_node_history_loader(
    history_store: Any,
    *,
    default_hours: int,
    default_points: int,
) -> Callable[[str, Optional[int], Optional[int]], Dict[str, Any]]:
    def node_history_loader(
        node_id: str,
        hours_override: Optional[int] = None,
        points_override: Optional[int] = None,
    ) -> Dict[str, Any]:
        clean_node_id = str(node_id or "").strip()
        if history_store is None:
            return empty_node_history(clean_node_id)
        hours = (
            hours_override
            if isinstance(hours_override, int) and hours_override > 0
            else int(default_hours)
        )
        points = (
            points_override
            if isinstance(points_override, int) and points_override > 0
            else int(default_points)
        )
        return history_store.load_node_history(
            node_id=clean_node_id,
            window_hours=hours,
            max_points=points,
        )

    return node_history_loader


def build_online_activity_loader(
    history_store: Any,
    *,
    default_hours: int,
) -> Callable[[Optional[int]], Dict[str, Any]]:
    def online_activity_loader(hours_override: Optional[int] = None) -> Dict[str, Any]:
        hours = (
            hours_override
            if isinstance(hours_override, int) and hours_override > 0
            else int(default_hours)
        )
        if history_store is None:
            return empty_online_activity(hours)
        return history_store.load_online_activity(window_hours=hours)

    return online_activity_loader


def send_chat_message(
    *,
    text: Any,
    destination: Any = None,
    channel_index: Optional[int] = None,
    reply_id: Optional[int] = None,
    retry_of: Optional[int] = None,
    emoji: Any = None,
    iface: Any,
    send_lock: Any,
    send_reaction_packet_fn: Callable[..., Any],
    local_node_id_fn: Callable[[], str],
    record_local_chat_fn: Callable[..., None],
    chat_max_bytes: int,
    normalize_single_emoji_fn: Callable[[Any], tuple[Optional[str], Optional[int]]],
    to_int_fn: Callable[[Any], Optional[int]],
    now_text_fn: Callable[[], str],
) -> Dict[str, Any]:
    clean_text = str(text or "").strip()
    clean_reply_id = to_int_fn(reply_id)
    clean_retry_of = to_int_fn(retry_of)
    clean_emoji, clean_emoji_codepoint = normalize_single_emoji_fn(emoji)

    has_reaction = bool(
        clean_reply_id is not None and clean_reply_id > 0 and clean_emoji and clean_emoji_codepoint
    )
    if clean_emoji and not has_reaction:
        raise ValueError("Emoji reactions require a valid reply_id")
    if clean_reply_id is not None and clean_reply_id <= 0:
        raise ValueError("reply_id must be a positive packet id")
    if has_reaction and clean_text:
        raise ValueError("Emoji reactions must not include text")
    if not clean_text and not has_reaction:
        raise ValueError("Message cannot be empty")

    if clean_text:
        payload_bytes = clean_text.encode("utf-8")
        if len(payload_bytes) > int(chat_max_bytes):
            raise ValueError(
                f"Message is too long ({len(payload_bytes)} bytes). Limit is {chat_max_bytes} bytes."
            )

    dest = str(destination or "^all").strip() or "^all"
    if dest.lower() in ("all", "broadcast"):
        dest = "^all"
    if not (dest == "^all" or dest.startswith("!")):
        raise ValueError("Destination must be '^all' or a node id like !abcdef12")

    chan = channel_index if isinstance(channel_index, int) and channel_index >= 0 else 0
    should_request_ack = bool(dest != "^all" and not has_reaction)
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
    delivery_state = "sent"
    if should_request_ack:
        if sent_packet_id is not None and sent_packet_id > 0:
            delivery_state = "pending"
        else:
            delivery_state = "error"
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
    response: Dict[str, Any] = {
        "ok": True,
        "sent_at": now_text_fn(),
        "from": local_id,
        "to": dest,
        "channel_index": chan,
        "message_id": sent_packet_id,
        "reply_id": clean_reply_id,
        "ack_requested": should_request_ack,
        "delivery_state": delivery_state,
    }
    if clean_retry_of is not None and clean_retry_of > 0:
        response["retry_of"] = clean_retry_of
    if has_reaction:
        response["reaction"] = clean_emoji
        response["reaction_codepoint"] = clean_emoji_codepoint
        response["text"] = ""
    else:
        response["text"] = clean_text
    return response
