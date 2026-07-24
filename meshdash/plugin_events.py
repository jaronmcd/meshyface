"""Normalize accepted Meshtastic packets for plugin dispatch."""

from __future__ import annotations

import math
import re
import time
from collections.abc import Mapping

from .plugins import MessageEvent
from .helpers import calculate_hops, extract_reply_id, to_int
from .helpers_json import to_jsonable


_BROADCAST_NODE_NUM = 0xFFFFFFFF
_CANONICAL_NODE_ID_RE = re.compile(r"![0-9a-f]{8}\Z")


def _node_id(value: object) -> str:
    if isinstance(value, str):
        clean = value.strip().lower()
        if clean in {"^all", "!ffffffff"}:
            return "^all"
        if (
            _CANONICAL_NODE_ID_RE.fullmatch(clean) is not None
            and clean != "!00000000"
        ):
            return clean
    numeric = to_int(value)
    if numeric is None or numeric <= 0 or numeric > _BROADCAST_NODE_NUM:
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
    if (
        not sender_id
        or sender_id == "^all"
        or not destination_id
        or not clean_local
        or clean_local == "^all"
    ):
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
    except (TypeError, ValueError, OverflowError):
        received_float = float(now_fn())
    if not math.isfinite(received_float):
        received_float = float(now_fn())
    snr_raw = packet.get("rxSnr") if packet.get("rxSnr") is not None else packet.get("snr")
    rssi_raw = packet.get("rxRssi") if packet.get("rxRssi") is not None else packet.get("rssi")
    try:
        snr = float(snr_raw) if snr_raw is not None else None
    except (TypeError, ValueError, OverflowError):
        snr = None
    if snr is not None and not math.isfinite(snr):
        snr = None
    try:
        rssi = float(rssi_raw) if rssi_raw is not None else None
    except (TypeError, ValueError, OverflowError):
        rssi = None
    if rssi is not None and not math.isfinite(rssi):
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


def normalize_plugin_packet_event(
    packet: object,
    *,
    local_node_id: object,
    allow_transit: bool = True,
    now_fn=time.time,
) -> MessageEvent | None:
    """Wrap one accepted packet for ``@script.on_packet`` handlers.

    Packet hooks preserve transit visibility for monitoring plugins.  Callers
    may explicitly disable it while retaining self-packet and channel checks.
    """

    if not isinstance(packet, Mapping):
        return None
    sender_id = _endpoint(packet, "from", ("fromId", "from_id"))
    destination_id = _endpoint(packet, "to", ("toId", "to_id"))
    clean_local = _node_id(local_node_id)
    if (
        not sender_id
        or sender_id == "^all"
        or not destination_id
        or not clean_local
        or clean_local == "^all"
    ):
        return None
    if sender_id == clean_local:
        return None
    is_broadcast = destination_id == "^all"
    is_direct = destination_id == clean_local
    if not allow_transit and not is_broadcast and not is_direct:
        return None
    channel = to_int(packet.get("channel"))
    if channel is None:
        channel = 0
    if channel < 0 or channel > 7:
        return None
    packet_id = to_int(packet.get("id") or packet.get("packet_id") or packet.get("packetId"))
    decoded = packet.get("decoded")
    portnum = (
        str(decoded.get("portnum") or "").strip().upper()
        if isinstance(decoded, Mapping)
        else ""
    )
    received_at = packet.get("rxTime") or packet.get("received_at") or now_fn()
    try:
        received_float = float(received_at)
    except (TypeError, ValueError, OverflowError):
        received_float = float(now_fn())
    if not math.isfinite(received_float):
        received_float = float(now_fn())
    clean_packet = to_jsonable(dict(packet))
    if not isinstance(clean_packet, dict):
        return None
    return MessageEvent(
        text="",
        sender_id=sender_id,
        destination_id=destination_id,
        local_node_id=clean_local,
        channel_index=int(channel),
        is_direct=is_direct,
        is_broadcast=is_broadcast,
        packet_id=max(0, int(packet_id or 0)),
        reply_packet_id=None,
        received_at=received_float,
        packet=clean_packet,
        portnum=portnum,
    )


__all__ = ["normalize_plugin_message_event", "normalize_plugin_packet_event"]
