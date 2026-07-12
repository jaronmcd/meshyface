from __future__ import annotations

import threading
import time
from collections.abc import Iterable
from typing import Callable, Optional

from .config import DEFAULT_CHAT_MAX_BYTES
from .games.zork import ZorkGame
from .helpers import to_int as _to_int
from .nodes_identity import (
    get_local_node_id as _get_local_node_id,
)
from .runtime_types import RecordLocalChatFn
from .tracker_ingest import _normalize_packet_node_id

_BROADCAST_NUM = 0xFFFFFFFF
_REPLY_TEXT_RESERVE_BYTES = 36
_MAX_REPLY_SEGMENTS = 8
_MAX_ASYNC_ZORK_REPLIES = 8
_ZORK_PEER_REQUEST_COOLDOWN_SECONDS = 2.0
_ZORK_GLOBAL_REQUEST_COOLDOWN_SECONDS = 0.5
_ZORK_MAX_RATE_TRACKED_PEERS = 128
_LIVE_REPLY_SEGMENT_DELAY_SECONDS = 2.0
_LIVE_REPLY_ACK_WAIT_SECONDS = 25.0
_LIVE_REPLY_ACK_POLL_SECONDS = 0.5
_LIVE_REPLY_RETRY_LIMIT = 1
_ACKED_DELIVERY_STATES = {"ack", "acked", "delivered"}
_PUBLIC_START_TRIGGER = "zork"


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
    del iface
    raw_node_num = packet.get(number_key)
    if raw_node_num is None:
        return _normalize_node_id(packet.get(text_key))
    if isinstance(raw_node_num, bool) or (
        isinstance(raw_node_num, float) and not raw_node_num.is_integer()
    ):
        return ""
    node_num = _to_int(raw_node_num)
    if node_num == _BROADCAST_NUM:
        return "^all"
    if node_num is not None and 0 <= node_num <= 0xFFFFFFFF:
        return f"!{node_num:08x}"
    return ""


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


def _is_public_start_trigger(
    *,
    text: str,
    to_id: str,
    public_start_triggers: Iterable[str],
) -> bool:
    trigger = str(text or "").strip().lower()
    return str(to_id or "").strip().lower() == "^all" and trigger in {
        str(value or "").strip().lower()
        for value in public_start_triggers
        if str(value or "").strip()
    }


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


def _game_command_name(game: object, result: object | None = None) -> str:
    raw = getattr(result, "command_name", None) if result is not None else None
    if not raw:
        spec = getattr(game, "SPEC", None)
        raw = getattr(spec, "name", None)
    return str(raw or "zork").strip().lower() or "zork"


class ZorkBotService:
    def __init__(
        self,
        *,
        game: ZorkGame | None = None,
        send_lock: object | None = None,
        now_unix_fn: Callable[[], float] = time.time,
        reply_segment_delay_seconds: float = _LIVE_REPLY_SEGMENT_DELAY_SECONDS,
        reply_ack_wait_seconds: float = _LIVE_REPLY_ACK_WAIT_SECONDS,
        reply_ack_poll_seconds: float = _LIVE_REPLY_ACK_POLL_SECONDS,
        reply_retry_limit: int = _LIVE_REPLY_RETRY_LIMIT,
        reply_async: bool = True,
        max_async_replies: int = _MAX_ASYNC_ZORK_REPLIES,
        peer_request_cooldown_seconds: float = _ZORK_PEER_REQUEST_COOLDOWN_SECONDS,
        global_request_cooldown_seconds: float = _ZORK_GLOBAL_REQUEST_COOLDOWN_SECONDS,
        monotonic_fn: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], None] = time.sleep,
        get_delivery_state_fn: Callable[[object], object] | None = None,
        public_start_triggers: Iterable[str] | None = None,
    ) -> None:
        self._game = game or ZorkGame()
        self._send_lock = send_lock if send_lock is not None else threading.Lock()
        self._now_unix_fn = now_unix_fn
        self._reply_segment_delay_seconds = max(0.0, float(reply_segment_delay_seconds))
        self._reply_ack_wait_seconds = max(0.0, float(reply_ack_wait_seconds))
        self._reply_ack_poll_seconds = max(0.05, float(reply_ack_poll_seconds))
        self._reply_retry_limit = max(0, int(reply_retry_limit))
        self._reply_async = bool(reply_async)
        self._async_reply_slots = threading.BoundedSemaphore(max(1, int(max_async_replies)))
        self._peer_request_cooldown_seconds = max(0.0, float(peer_request_cooldown_seconds))
        self._global_request_cooldown_seconds = max(0.0, float(global_request_cooldown_seconds))
        self._monotonic_fn = monotonic_fn
        self._request_monotonic_by_peer: dict[str, float] = {}
        self._last_request_monotonic: float | None = None
        self._closed = threading.Event()
        self._sleep_fn = sleep_fn
        self._get_delivery_state_fn = get_delivery_state_fn
        triggers = tuple(
            str(value or "").strip().lower()
            for value in (public_start_triggers or (_PUBLIC_START_TRIGGER,))
            if str(value or "").strip()
        )
        self._public_start_triggers = triggers or (_PUBLIC_START_TRIGGER,)
        self._lock = threading.Lock()

    def close(self) -> None:
        self._closed.set()
        with self._lock:
            self._request_monotonic_by_peer.clear()
            self._last_request_monotonic = None
            clear_fn = getattr(self._game, "clear_sessions", None)
            if callable(clear_fn):
                try:
                    clear_fn()
                except Exception:
                    pass

    def _admit_request_locked(self, peer_id: str) -> bool:
        if self._closed.is_set():
            return False
        try:
            now_monotonic = max(0.0, float(self._monotonic_fn()))
        except Exception:
            now_monotonic = time.monotonic()
        previous = self._request_monotonic_by_peer.get(peer_id)
        peer_ready = previous is None or (
            now_monotonic - previous >= self._peer_request_cooldown_seconds
        )
        global_ready = self._last_request_monotonic is None or (
            now_monotonic - self._last_request_monotonic
            >= self._global_request_cooldown_seconds
        )
        if not peer_ready or not global_ready:
            return False
        self._request_monotonic_by_peer[peer_id] = now_monotonic
        self._last_request_monotonic = now_monotonic
        while len(self._request_monotonic_by_peer) > _ZORK_MAX_RATE_TRACKED_PEERS:
            oldest_peer = min(
                self._request_monotonic_by_peer,
                key=self._request_monotonic_by_peer.get,
            )
            self._request_monotonic_by_peer.pop(oldest_peer, None)
        return True

    def _wait_or_running(self, seconds: float) -> bool:
        delay = max(0.0, float(seconds))
        if self._closed.is_set():
            return False
        if self._sleep_fn is time.sleep:
            return not self._closed.wait(delay)
        self._sleep_fn(delay)
        return not self._closed.is_set()

    def handle_packet(
        self,
        packet: dict[str, object],
        iface: object,
        *,
        record_local_chat_fn: RecordLocalChatFn | None = None,
    ) -> bool:
        if self._closed.is_set():
            return False
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

        public_start = _is_public_start_trigger(
            text=text,
            to_id=to_id,
            public_start_triggers=self._public_start_triggers,
        )
        if to_id.strip().lower() == "^all" and not public_start:
            return False

        now_unix = int(self._now_unix_fn())
        game_to_id = local_node_id if public_start else to_id
        with self._lock:
            if not self._admit_request_locked(from_id):
                return True
            result = self._game.try_handle_message(
                text=text,
                from_id=from_id,
                to_id=game_to_id,
                local_node_id=local_node_id,
                now_unix=now_unix,
                enabled=True,
            )
        if not getattr(result, "handled", False):
            return False

        segments = _reply_segments(getattr(result, "reply_text", "") or "")
        if not segments:
            return True

        bot_command = _game_command_name(self._game, result)
        channel_index = _packet_channel_index(packet)
        reply_id = _packet_id(packet)
        if self._reply_async:
            if not self._async_reply_slots.acquire(blocking=False):
                return True
            kwargs = {
                    "iface": iface,
                    "segments": segments,
                    "destination_id": from_id,
                    "local_node_id": local_node_id,
                    "channel_index": channel_index,
                    "reply_id": reply_id,
                    "bot_command": bot_command,
                    "record_local_chat_fn": record_local_chat_fn,
                }
            try:
                thread = threading.Thread(
                    target=self._send_live_reply_segments_with_slot,
                    kwargs=kwargs,
                    daemon=True,
                )
                thread.start()
            except Exception:
                self._async_reply_slots.release()
            return True

        self._send_live_reply_segments(
            iface=iface,
            segments=segments,
            destination_id=from_id,
            local_node_id=local_node_id,
            channel_index=channel_index,
            reply_id=reply_id,
            bot_command=bot_command,
            record_local_chat_fn=record_local_chat_fn,
        )
        return True

    def _send_live_reply_segments_with_slot(self, **kwargs: object) -> None:
        try:
            self._send_live_reply_segments(**kwargs)  # type: ignore[arg-type]
        finally:
            self._async_reply_slots.release()

    def _send_live_reply_segments(
        self,
        *,
        iface: object,
        segments: list[str],
        destination_id: str,
        local_node_id: str,
        channel_index: int,
        reply_id: Optional[int],
        bot_command: str,
        record_local_chat_fn: RecordLocalChatFn | None = None,
    ) -> None:
        for index, segment in enumerate(segments):
            if self._closed.is_set():
                return
            if index > 0:
                self._sleep_between_live_segments()
                if self._closed.is_set():
                    return
            if not self._send_live_reply_segment_until_acked(
                iface,
                text=segment,
                destination_id=destination_id,
                local_node_id=local_node_id,
                channel_index=channel_index,
                reply_id=reply_id,
                bot_command=bot_command,
                record_local_chat_fn=record_local_chat_fn,
            ):
                return

    def _sleep_between_live_segments(self) -> None:
        if self._reply_segment_delay_seconds > 0:
            self._wait_or_running(self._reply_segment_delay_seconds)

    def _send_live_reply_segment_until_acked(
        self,
        iface: object,
        *,
        text: str,
        destination_id: str,
        local_node_id: str,
        channel_index: int,
        reply_id: Optional[int],
        bot_command: str,
        record_local_chat_fn: RecordLocalChatFn | None = None,
    ) -> bool:
        attempt_message_ids: list[int] = []
        original_message_id: Optional[int] = None
        for attempt_index in range(self._reply_retry_limit + 1):
            if self._closed.is_set():
                return False
            try:
                sent_message_id = self._send_live_reply_segment(
                    iface,
                    text=text,
                    destination_id=destination_id,
                    local_node_id=local_node_id,
                    channel_index=channel_index,
                    reply_id=reply_id,
                    bot_command=bot_command,
                    record_local_chat_fn=record_local_chat_fn,
                    retry_of=original_message_id if attempt_index > 0 else None,
                )
            except Exception:
                return False
            if sent_message_id is None:
                return True
            if original_message_id is None:
                original_message_id = sent_message_id
            attempt_message_ids.append(sent_message_id)
            if not self._should_wait_for_reply_ack():
                return True
            if self._wait_for_live_reply_ack(attempt_message_ids):
                return True
        return False

    def _should_wait_for_reply_ack(self) -> bool:
        return self._reply_retry_limit > 0 and self._get_delivery_state_fn is not None

    def _send_live_reply_segment(
        self,
        iface: object,
        *,
        text: str,
        destination_id: str,
        local_node_id: str,
        channel_index: int,
        reply_id: Optional[int],
        bot_command: str,
        record_local_chat_fn: RecordLocalChatFn | None = None,
        retry_of: Optional[int] = None,
    ) -> Optional[int]:
        sent_packet = self._send_text(
            iface,
            text=text,
            destination_id=destination_id,
            channel_index=channel_index,
            reply_id=reply_id,
        )
        sent_message_id = _sent_packet_id(sent_packet)
        if record_local_chat_fn is not None:
            record_local_chat_fn(
                text=text,
                from_id=local_node_id,
                to_id=destination_id,
                channel_index=channel_index,
                message_id=sent_message_id,
                reply_id=reply_id,
                ack_requested=True,
                retry_of=retry_of,
                bot_command=bot_command,
            )
        return sent_message_id

    def _wait_for_live_reply_ack(self, message_ids: list[int]) -> bool:
        if self._any_delivery_is_acked(message_ids):
            return True
        if self._reply_ack_wait_seconds <= 0:
            return False
        deadline = time.monotonic() + self._reply_ack_wait_seconds
        while time.monotonic() < deadline:
            if self._closed.is_set():
                return False
            if self._any_delivery_is_acked(message_ids):
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return self._any_delivery_is_acked(message_ids)
            if not self._wait_or_running(min(self._reply_ack_poll_seconds, remaining)):
                return False
        return self._any_delivery_is_acked(message_ids)

    def _any_delivery_is_acked(self, message_ids: list[int]) -> bool:
        return any(self._delivery_is_acked(message_id) for message_id in message_ids)

    def _delivery_is_acked(self, message_id: object) -> bool:
        getter = self._get_delivery_state_fn
        if getter is None:
            return False
        try:
            state = getter(message_id)
        except Exception:
            return False
        if isinstance(state, dict):
            raw_state = state.get("delivery_state") or state.get("state")
        else:
            raw_state = state
        return str(raw_state or "").strip().lower() in _ACKED_DELIVERY_STATES

    def handle_local_chat(
        self,
        *,
        text: object,
        from_id: object,
        to_id: object,
        local_node_id: object,
        channel_index: int = 0,
        reply_id: Optional[int] = None,
        record_local_chat_fn: RecordLocalChatFn | None = None,
    ) -> bool:
        if self._closed.is_set():
            return False
        clean_text = str(text or "").strip()
        if not clean_text:
            return False
        clean_local = _normalize_node_id(local_node_id)
        clean_to = _normalize_node_id(to_id)
        clean_from = _normalize_node_id(from_id) or clean_local
        if not clean_local or not clean_to:
            return False

        peer_id = clean_from if clean_from.startswith("!") else clean_local
        now_unix = int(self._now_unix_fn())
        with self._lock:
            result = self._game.try_handle_message(
                text=clean_text,
                from_id=peer_id,
                to_id=clean_to,
                local_node_id=clean_local,
                now_unix=now_unix,
                enabled=True,
            )
        if not getattr(result, "handled", False):
            return False

        if record_local_chat_fn is None:
            return True

        bot_command = _game_command_name(self._game, result)
        for segment in _reply_segments(getattr(result, "reply_text", "") or ""):
            record_local_chat_fn(
                text=segment,
                from_id=clean_local,
                to_id=peer_id,
                channel_index=channel_index,
                message_id=None,
                reply_id=reply_id,
                ack_requested=False,
                bot_command=bot_command,
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
        if self._closed.is_set():
            raise RuntimeError("zork bot is closed")
        send_text_fn = getattr(iface, "sendText")
        with self._send_lock:
            try:
                return send_text_fn(
                    text,
                    destinationId=destination_id,
                    wantAck=True,
                    channelIndex=channel_index,
                    replyId=reply_id if reply_id and reply_id > 0 else None,
                )
            except TypeError:
                return send_text_fn(
                    text,
                    destinationId=destination_id,
                    wantAck=True,
                    channelIndex=channel_index,
                )

    def active_session_count(self) -> int:
        count_fn = getattr(self._game, "active_session_count", None)
        if not callable(count_fn):
            return 0
        with self._lock:
            try:
                prune_fn = getattr(self._game, "prune_expired_sessions", None)
                if callable(prune_fn):
                    prune_fn(int(self._now_unix_fn()))
                return max(0, int(count_fn()))
            except Exception:
                return 0

    def session_summaries(self) -> list[dict[str, object]]:
        summary_fn = getattr(self._game, "session_summaries", None)
        if not callable(summary_fn):
            return []
        with self._lock:
            try:
                sessions = summary_fn(int(self._now_unix_fn()))
            except Exception:
                return []
        return sessions if isinstance(sessions, list) else []

    def end_session(self, peer_id: object) -> bool:
        end_fn = getattr(self._game, "end_session", None)
        if not callable(end_fn):
            return False
        with self._lock:
            try:
                return bool(end_fn(str(peer_id or "")))
            except Exception:
                return False

    def clear_sessions(self) -> bool:
        clear_fn = getattr(self._game, "clear_sessions", None)
        if not callable(clear_fn):
            return False
        with self._lock:
            try:
                clear_fn()
            except Exception:
                return False
        return True


def build_zork_bot_service(
    *,
    send_lock: object | None = None,
    now_unix_fn: Callable[[], float] = time.time,
    reply_segment_delay_seconds: float = _LIVE_REPLY_SEGMENT_DELAY_SECONDS,
    reply_ack_wait_seconds: float = _LIVE_REPLY_ACK_WAIT_SECONDS,
    reply_ack_poll_seconds: float = _LIVE_REPLY_ACK_POLL_SECONDS,
    reply_retry_limit: int = _LIVE_REPLY_RETRY_LIMIT,
    reply_async: bool = True,
    peer_request_cooldown_seconds: float = _ZORK_PEER_REQUEST_COOLDOWN_SECONDS,
    global_request_cooldown_seconds: float = _ZORK_GLOBAL_REQUEST_COOLDOWN_SECONDS,
    monotonic_fn: Callable[[], float] = time.monotonic,
    sleep_fn: Callable[[float], None] = time.sleep,
    get_delivery_state_fn: Callable[[object], object] | None = None,
) -> ZorkBotService:
    return ZorkBotService(
        send_lock=send_lock,
        now_unix_fn=now_unix_fn,
        reply_segment_delay_seconds=reply_segment_delay_seconds,
        reply_ack_wait_seconds=reply_ack_wait_seconds,
        reply_ack_poll_seconds=reply_ack_poll_seconds,
        reply_retry_limit=reply_retry_limit,
        reply_async=reply_async,
        peer_request_cooldown_seconds=peer_request_cooldown_seconds,
        global_request_cooldown_seconds=global_request_cooldown_seconds,
        monotonic_fn=monotonic_fn,
        sleep_fn=sleep_fn,
        get_delivery_state_fn=get_delivery_state_fn,
    )


__all__ = ["ZorkBotService", "build_zork_bot_service"]
