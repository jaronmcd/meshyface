from typing import Optional

from .chat_scope import chat_scope_for_destination
from .runtime_types import FormatEpochFn, ToIntFn, UtcNowFn


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
        "channel": packet.get("channel"),
        "decoded_text": decoded.get("text") if isinstance(decoded, dict) else None,
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
    decoded_text = decoded.get("text") if isinstance(decoded, dict) else None
    if not (isinstance(decoded_text, str) and decoded_text.strip()):
        alert_text = _extract_alert_text_from_decoded_payload(decoded)
        if alert_text:
            decoded_text = alert_text
    has_text = isinstance(decoded_text, str) and decoded_text.strip()
    if not (has_text or is_reaction):
        return None

    portnum = decoded.get("portnum") if isinstance(decoded, dict) else None
    chat_entry = {
        "captured_at": utc_now_fn(),
        "from": from_id,
        "to": to_id,
        "scope": chat_scope_for_destination(to_id),
        "portnum": str(portnum) if portnum is not None else None,
        "channel": packet.get("channel"),
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
    return chat_entry
