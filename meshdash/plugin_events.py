"""Normalize accepted Meshtastic text packets for plugin dispatch."""

from __future__ import annotations

import time
from collections.abc import Mapping

from .bots import MessageEvent
from .helpers import calculate_hops, extract_reply_id, to_int


_BROADCAST_NODE_NUM = 0xFFFFFFFF


def _node_id(value: object) -> str:
    if isinstance(value, str):
        clean = value.strip().lower()
        if clean == "^all":
            return clean
        if clean.startswith("!") and len(clean) == 9:
            return clean
    numeric = to_int(value)
    if numeric is None or numeric < 0 or numeric > _BROADCAST_NODE_NUM:
        return ""
    if numeric == _BROADCAST_NODE_NUM:
        return "^all"
    return f"!{numeric:08x}"


def _endpoint(packet: Mapping[str, object], primary: str, aliases: tuple[str, ...]) -> str:
    if packet.get(primary) is not None:
        resolved = _node_id(packet.get(primary))
        if resolved:
            return resolved
    for alias in aliases:
        resolved = _node_id(packet.get(alias))
        if resolved:
            return resolved
    return ""


def normalize_plugin_message_event(
    packet: object,
    *,
    local_node_id: object,
    now_fn=time.time,
) -> MessageEvent | None:
    if not isinstance(packet, Mapping):
        return None
    decoded = packet.get("decoded")
    if not isinstance(decoded, Mapping):
        return None
    portnum = str(decoded.get("portnum") or "").strip().upper()
    if portnum != "TEXT_MESSAGE_APP":
        return None
    text = decoded.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    if len(text.encode("utf-8")) > 1024:
        return None
    sender_id = _endpoint(packet, "from", ("fromId", "from_id"))
    destination_id = _endpoint(packet, "to", ("toId", "to_id"))
    clean_local = _node_id(local_node_id)
    if not sender_id or not destination_id or not clean_local:
        return None
    if sender_id == clean_local:
        return None
    is_broadcast = destination_id == "^all"
    is_direct = destination_id == clean_local
    if not is_broadcast and not is_direct:
        return None
    channel = to_int(packet.get("channel"))
    if channel is None:
        channel = 0
    if channel < 0 or channel > 7:
        return None
    packet_id = to_int(packet.get("id") or packet.get("packet_id") or packet.get("packetId"))
    received_at = packet.get("rxTime") or packet.get("received_at") or now_fn()
    try:
        received_float = float(received_at)
    except (TypeError, ValueError):
        received_float = float(now_fn())
    snr_raw = packet.get("rxSnr") if packet.get("rxSnr") is not None else packet.get("snr")
    rssi_raw = packet.get("rxRssi") if packet.get("rxRssi") is not None else packet.get("rssi")
    try:
        snr = float(snr_raw) if snr_raw is not None else None
    except (TypeError, ValueError):
        snr = None
    try:
        rssi = float(rssi_raw) if rssi_raw is not None else None
    except (TypeError, ValueError):
        rssi = None
    return MessageEvent(
        text=text.strip(),
        sender_id=sender_id,
        destination_id=destination_id,
        local_node_id=clean_local,
        channel_index=max(0, int(channel)),
        is_direct=is_direct,
        is_broadcast=is_broadcast,
        packet_id=max(0, int(packet_id or 0)),
        reply_packet_id=extract_reply_id(decoded),
        received_at=received_float,
        snr=snr,
        rssi=rssi,
        hops=calculate_hops(packet.get("hopStart"), packet.get("hopLimit")),
    )


__all__ = ["normalize_plugin_message_event"]
