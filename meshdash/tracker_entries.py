import base64
from typing import Optional

from .chat_scope import chat_scope_for_destination
from .file_transfer_protocol import decode_file_transfer_packet, file_transfer_frame_text
from .runtime_types import FormatEpochFn, ToIntFn, UtcNowFn


_STORE_FORWARD_TEXT_RR_BY_VALUE = {
    8: "ROUTER_TEXT_DIRECT",
    9: "ROUTER_TEXT_BROADCAST",
}
_STORE_FORWARD_TEXT_RR_NAMES = frozenset(_STORE_FORWARD_TEXT_RR_BY_VALUE.values())


def _packet_channel_index(packet: dict[str, object]) -> int | None:
    if "channel" in packet:
        raw_value = packet.get("channel")
    elif "channelIndex" in packet:
        raw_value = packet.get("channelIndex")
    else:
        # Protobuf JSON omits the scalar default; on wire that means primary.
        return 0
    if isinstance(raw_value, bool):
        return None
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if 0 <= parsed <= 255 else None


def _decode_store_forward_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, (bytes, bytearray)):
        try:
            return bytes(value).decode("utf-8").strip()
        except Exception:
            return ""
    if not isinstance(value, str):
        return ""
    clean = value.strip()
    if not clean:
        return ""
    try:
        decoded_bytes = base64.b64decode(clean, validate=True)
        decoded_text = decoded_bytes.decode("utf-8").strip()
    except Exception:
        return clean
    return decoded_text or clean


def _store_forward_rr_name(value: object) -> str:
    if isinstance(value, str):
        clean = value.strip().upper()
        if not clean:
            return ""
        if clean.isdigit():
            return _STORE_FORWARD_TEXT_RR_BY_VALUE.get(int(clean), "")
        return clean.rsplit(".", 1)[-1]
    try:
        return _STORE_FORWARD_TEXT_RR_BY_VALUE.get(int(value), "")
    except Exception:
        return ""


def _extract_store_forward_text_from_decoded_payload(decoded: object) -> tuple[str, str]:
    if not isinstance(decoded, dict):
        return "", ""
    portnum = str(decoded.get("portnum") or "").strip().upper()
    if portnum and not portnum.endswith("STORE_FORWARD_APP"):
        return "", ""

    storeforward = decoded.get("storeforward")
    if storeforward is None:
        return "", ""
    storeforward_dict = storeforward if isinstance(storeforward, dict) else {}
    raw = storeforward_dict.get("raw") if storeforward_dict else storeforward

    rr_name = _store_forward_rr_name(storeforward_dict.get("rr"))
    if not rr_name and raw is not None:
        rr_name = _store_forward_rr_name(getattr(raw, "rr", None))
    if rr_name not in _STORE_FORWARD_TEXT_RR_NAMES:
        return "", ""

    text = _decode_store_forward_text(getattr(raw, "text", None) if raw is not None else None)
    if not text:
        text = _decode_store_forward_text(storeforward_dict.get("text"))
    if not text:
        return "", ""
    return text, rr_name


def _extract_alert_text_from_decoded_payload(decoded: object) -> str:
    if not isinstance(decoded, dict):
        return ""
    portnum = str(decoded.get("portnum") or "").strip().upper()
    if not portnum or not portnum.endswith("ALERT_APP"):
        return ""
    payload = decoded.get("payload")
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, memoryview):
        payload = payload.tobytes()
    if isinstance(payload, (bytes, bytearray)):
        try:
            return bytes(payload).decode("utf-8").strip()
        except Exception:
            return ""
    return ""


def build_packet_summary(
    *,
    packet: dict[str, object],
    decoded: object,
    from_id: object,
    to_id: object,
    packet_id: Optional[int],
    rx_time: Optional[int],
    hops: Optional[int],
    reply_id: Optional[int],
    emoji_glyph: Optional[str],
    emoji_codepoint: Optional[int],
    is_reaction: bool,
    packet_position: Optional[dict[str, object]],
    packet_battery: Optional[int],
    utc_now_fn: UtcNowFn,
    format_epoch_fn: FormatEpochFn,
    to_int_fn: ToIntFn,
) -> dict[str, object]:
    portnum = decoded.get("portnum") if isinstance(decoded, dict) else None
    file_frame = decode_file_transfer_packet(packet)
    file_frame_text = file_transfer_frame_text(file_frame) if file_frame is not None else ""
    summary = {
        "captured_at": utc_now_fn(),
        "live": True,
        "packet_id": packet_id,
        "from": from_id,
        "to": to_id,
        "from_num": to_int_fn(packet.get("from")),
        "to_num": to_int_fn(packet.get("to")),
        "portnum": str(portnum) if portnum is not None else None,
        "rx_time": format_epoch_fn(packet.get("rxTime")),
        "rx_time_unix": rx_time,
        "rx_rssi": packet.get("rxRssi"),
        "rx_snr": packet.get("rxSnr"),
        "hop_start": packet.get("hopStart"),
        "hop_limit": packet.get("hopLimit"),
        "hops": hops,
        "want_ack": packet.get("wantAck"),
        "priority": packet.get("priority"),
        "channel": _packet_channel_index(packet),
        "decoded_text": (
            file_frame_text
            if file_frame_text
            else decoded.get("text") if isinstance(decoded, dict) else None
        ),
        "reply_id": reply_id,
        "emoji": emoji_glyph,
        "emoji_codepoint": emoji_codepoint,
        "is_reaction": is_reaction,
    }
    if packet_position is not None:
        summary["position"] = packet_position
    if packet_battery is not None:
        summary["battery_level"] = packet_battery
    return summary


def build_chat_entry_from_packet(
    *,
    packet: dict[str, object],
    decoded: object,
    from_id: object,
    to_id: object,
    packet_id: Optional[int],
    hops: Optional[int],
    reply_id: Optional[int],
    emoji_glyph: Optional[str],
    emoji_codepoint: Optional[int],
    is_reaction: bool,
    utc_now_fn: UtcNowFn,
    format_epoch_fn: FormatEpochFn,
) -> Optional[dict[str, object]]:
    file_frame = decode_file_transfer_packet(packet)
    file_frame_text = file_transfer_frame_text(file_frame) if file_frame is not None else ""
    decoded_text = file_frame_text or (decoded.get("text") if isinstance(decoded, dict) else None)
    store_forward_text, store_forward_rr = _extract_store_forward_text_from_decoded_payload(decoded)
    store_forward_recovered = False
    if not (isinstance(decoded_text, str) and decoded_text.strip()):
        alert_text = _extract_alert_text_from_decoded_payload(decoded)
        if alert_text:
            decoded_text = alert_text
        elif store_forward_text:
            decoded_text = store_forward_text
            store_forward_recovered = True
    has_text = isinstance(decoded_text, str) and decoded_text.strip()
    if not (has_text or is_reaction):
        return None

    portnum = decoded.get("portnum") if isinstance(decoded, dict) else None
    source_portnum = str(portnum) if portnum is not None else None
    chat_to_id = "^all" if store_forward_rr == "ROUTER_TEXT_BROADCAST" else to_id
    chat_portnum = "TEXT_MESSAGE_APP" if store_forward_recovered else source_portnum
    chat_entry = {
        "captured_at": utc_now_fn(),
        "from": from_id,
        "to": chat_to_id,
        "scope": chat_scope_for_destination(chat_to_id),
        "portnum": chat_portnum,
        "channel": _packet_channel_index(packet),
        "rx_time": format_epoch_fn(packet.get("rxTime")),
        "rx_snr": packet.get("rxSnr"),
        "rx_rssi": packet.get("rxRssi"),
        "text": decoded_text if isinstance(decoded_text, str) else "",
        "hops": hops,
        "hop_start": packet.get("hopStart"),
        "hop_limit": packet.get("hopLimit"),
    }
    if packet_id is not None and packet_id > 0:
        chat_entry["message_id"] = packet_id
    if reply_id is not None and reply_id > 0:
        chat_entry["reply_id"] = reply_id
    if emoji_glyph:
        chat_entry["emoji"] = emoji_glyph
    if emoji_codepoint is not None and emoji_codepoint > 0:
        chat_entry["emoji_codepoint"] = emoji_codepoint
    if is_reaction:
        chat_entry["is_reaction"] = True
    if store_forward_recovered:
        chat_entry["store_forward_recovered"] = True
        chat_entry["store_forward_rr"] = store_forward_rr
        if source_portnum:
            chat_entry["source_portnum"] = source_portnum
    return chat_entry
