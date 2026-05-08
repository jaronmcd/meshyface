from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from .config import DEFAULT_CHAT_MAX_BYTES
from .games.zork import ZorkGame
from .helpers import to_int as _to_int
from .nodes_identity import (
    get_local_node_id as _get_local_node_id,
    get_node_id_from_num as _get_node_id_from_num,
)
from .runtime_types import RecordLocalChatFn
from .tracker_ingest import _normalize_packet_node_id

_BROADCAST_NUM = 0xFFFFFFFF
_REPLY_TEXT_RESERVE_BYTES = 36
_MAX_REPLY_SEGMENTS = 8


def _normalize_node_id(value: object) -> str:
    normalized = _normalize_packet_node_id(value)
    return str(normalized or "").strip()


def _packet_node_id(
    packet: dict[str, object],
    iface: object,
    *,
    text_key: str,
    number_key: str,
) -> str:
    raw_text_id = packet.get(text_key)
    if raw_text_id:
        return _normalize_node_id(raw_text_id)
    return _normalize_node_id(
        _get_node_id_from_num(
            iface,
            packet.get(number_key),
            broadcast_num=_BROADCAST_NUM,
            to_int_fn=_to_int,
        )
    )


def _packet_text(packet: dict[str, object]) -> str:
    decoded = packet.get("decoded")
    if not isinstance(decoded, dict):
        return ""
    value = decoded.get("text")
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return str(value or "").strip()


def _packet_channel_index(packet: dict[str, object]) -> int:
    raw_value = packet.get("channel")
    if raw_value is None:
        raw_value = packet.get("channelIndex")
    parsed = _to_int(raw_value)
    return parsed if parsed is not None and parsed >= 0 else 0


def _packet_id(packet: dict[str, object]) -> Optional[int]:
    parsed = _to_int(packet.get("id") or packet.get("packet_id") or packet.get("packetId"))
    return parsed if parsed is not None and parsed > 0 else None


def _sent_packet_id(sent_packet: object) -> Optional[int]:
    if isinstance(sent_packet, dict):
        parsed = _to_int(
            sent_packet.get("id")
            or sent_packet.get("packet_id")
            or sent_packet.get("packetId")
        )
    else:
        parsed = _to_int(getattr(sent_packet, "id", None))
    return parsed if parsed is not None and parsed > 0 else None


def _utf8_len(text: str) -> int:
    return len(str(text or "").encode("utf-8"))


def _trim_to_bytes(text: str, max_bytes: int) -> str:
    out: list[str] = []
    used = 0
    for ch in str(text or ""):
        size = _utf8_len(ch)
        if used + size > max_bytes:
            break
        out.append(ch)
        used += size
    return "".join(out).strip()


def _split_text_by_bytes(text: str, max_bytes: int) -> list[str]:
    clean = " ".join(str(text or "").strip().split())
    if not clean:
        return []
    limit = max(32, int(max_bytes))
    if _utf8_len(clean) <= limit:
        return [clean]

    chunks: list[str] = []
    current = ""
    for word in clean.split(" "):
        candidate = word if not current else f"{current} {word}"
        if _utf8_len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if _utf8_len(word) <= limit:
            current = word
            continue
        remainder = word
        while remainder:
            piece = _trim_to_bytes(remainder, limit)
            if not piece:
                break
            chunks.append(piece)
            remainder = remainder[len(piece):]
    if current:
        chunks.append(current)
    return chunks


def _reply_segments(text: object, *, max_bytes: int = DEFAULT_CHAT_MAX_BYTES) -> list[str]:
    clean = str(text or "").strip()
    if not clean:
        return []
    body_limit = max(32, int(max_bytes) - _REPLY_TEXT_RESERVE_BYTES)
    chunks = _split_text_by_bytes(clean, body_limit)
    if len(chunks) > _MAX_REPLY_SEGMENTS:
        chunks = chunks[:_MAX_REPLY_SEGMENTS]
        suffix = " ..."
        chunks[-1] = _trim_to_bytes(chunks[-1], max(1, body_limit - _utf8_len(suffix))) + suffix
    if len(chunks) <= 1:
        return chunks
    total = len(chunks)
    return [f"[{index}/{total}] {chunk}" for index, chunk in enumerate(chunks, start=1)]


class ZorkBotService:
    def __init__(
        self,
        *,
        game: ZorkGame | None = None,
        send_lock: object | None = None,
        now_unix_fn: Callable[[], float] = time.time,
    ) -> None:
        self._game = game or ZorkGame()
        self._send_lock = send_lock if send_lock is not None else threading.Lock()
        self._now_unix_fn = now_unix_fn
        self._lock = threading.Lock()

    def handle_packet(
        self,
        packet: dict[str, object],
        iface: object,
        *,
        record_local_chat_fn: RecordLocalChatFn | None = None,
    ) -> bool:
        text = _packet_text(packet)
        if not text:
            return False

        from_id = _packet_node_id(packet, iface, text_key="fromId", number_key="from")
        to_id = _packet_node_id(packet, iface, text_key="toId", number_key="to")
        local_node_id = _get_local_node_id(
            iface,
            broadcast_num=_BROADCAST_NUM,
            to_int_fn=_to_int,
        )
        local_node_id = _normalize_node_id(local_node_id)
        if not from_id or not to_id or not local_node_id:
            return False
        if from_id.lower() == local_node_id.lower():
            return False

        now_unix = int(self._now_unix_fn())
        with self._lock:
            result = self._game.try_handle_message(
                text=text,
                from_id=from_id,
                to_id=to_id,
                local_node_id=local_node_id,
                now_unix=now_unix,
                enabled=True,
            )
        if not getattr(result, "handled", False):
            return False

        segments = _reply_segments(getattr(result, "reply_text", "") or "")
        if not segments:
            return True

        channel_index = _packet_channel_index(packet)
        reply_id = _packet_id(packet)
        for segment in segments:
            sent_packet = self._send_text(
                iface,
                text=segment,
                destination_id=from_id,
                channel_index=channel_index,
                reply_id=reply_id,
            )
            if record_local_chat_fn is not None:
                record_local_chat_fn(
                    text=segment,
                    from_id=local_node_id,
                    to_id=from_id,
                    channel_index=channel_index,
                    message_id=_sent_packet_id(sent_packet),
                    reply_id=reply_id,
                    ack_requested=False,
                )
        return True

    def _send_text(
        self,
        iface: object,
        *,
        text: str,
        destination_id: str,
        channel_index: int,
        reply_id: Optional[int],
    ) -> object:
        send_text_fn = getattr(iface, "sendText")
        with self._send_lock:
            try:
                return send_text_fn(
                    text,
                    destinationId=destination_id,
                    wantAck=False,
                    channelIndex=channel_index,
                    replyId=reply_id if reply_id and reply_id > 0 else None,
                )
            except TypeError:
                return send_text_fn(
                    text,
                    destinationId=destination_id,
                    wantAck=False,
                    channelIndex=channel_index,
                )


def build_zork_bot_service(
    *,
    send_lock: object | None = None,
    now_unix_fn: Callable[[], float] = time.time,
) -> ZorkBotService:
    return ZorkBotService(send_lock=send_lock, now_unix_fn=now_unix_fn)


__all__ = ["ZorkBotService", "build_zork_bot_service"]
