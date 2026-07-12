from __future__ import annotations

import math
import threading
import time
from typing import Callable, Optional

from .helpers import to_float as _to_float, to_int as _to_int
from .nodes_identity import (
    get_local_node_id as _get_local_node_id,
)
from .runtime_types import RecordLocalChatFn
from .tracker_ingest import _normalize_packet_node_id

_BROADCAST_NUM = 0xFFFFFFFF
_PING_HEADS = {"ping", "test"}
_NATURAL_PING_TRIGGERS = {"can you see this", "can you see this?"}
_MAX_DIRECT_PING_REPEAT_COUNT = 8
_MAX_ASYNC_PING_REPLIES = 8
_PING_PEER_REQUEST_COOLDOWN_SECONDS = 5.0
_PING_GLOBAL_REQUEST_COOLDOWN_SECONDS = 1.0
_PING_MAX_RATE_TRACKED_PEERS = 128
_LIVE_REPEAT_DELAY_SECONDS = 0.35
_LIVE_REPEAT_MAX_PACED_COUNT = 8
_LIVE_REPEAT_SEND_RETRY_LIMIT = 2
_LIVE_REPEAT_SEND_RETRY_DELAY_SECONDS = 0.2
_LIVE_REPEAT_WAIT_FOR_ACK = True
_LIVE_REPEAT_ACK_WAIT_SECONDS = 8.0
_LIVE_REPEAT_ACK_POLL_SECONDS = 0.25
_LIVE_REPEAT_ACK_RETRY_LIMIT = 1
_LIVE_REPEAT_ASYNC = True
_ACKED_DELIVERY_STATES = {"ack", "acked", "delivered"}


def _normalize_node_id(value: object) -> str:
    normalized = _normalize_packet_node_id(value)
    return str(normalized or "").strip()


def _clean_text_token(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    out: list[str] = []
    for ch in text:
        if ("a" <= ch <= "z") or ("0" <= ch <= "9") or ch in (" ", "_", "-"):
            out.append(ch)
        elif ch in (".", ",", "!", "?", ":", ";", "/", "\\", "(", ")", "[", "]", "{", "}"):
            out.append(" ")
    clean = " ".join("".join(out).split())
    return clean


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


def _nonnegative_int(value: object) -> Optional[int]:
    parsed = _to_int(value)
    if parsed is None or parsed < 0:
        return None
    return parsed


def _finite_float(value: object) -> Optional[float]:
    parsed = _to_float(value)
    if parsed is None or not math.isfinite(parsed):
        return None
    return float(parsed)


def _packet_hops_from_mapping(container: object, _seen: Optional[set[int]] = None) -> Optional[int]:
    if not isinstance(container, dict):
        return None
    seen = _seen if isinstance(_seen, set) else set()
    marker = id(container)
    if marker in seen:
        return None
    seen.add(marker)

    for key in ("hops", "hop_count", "hopCount", "hopsAway", "hops_away", "last_hops", "lastHops"):
        hops = _nonnegative_int(container.get(key))
        if hops is not None:
            return hops

    hop_start_raw = container.get("hopStart")
    if hop_start_raw is None:
        hop_start_raw = container.get("hop_start")
    hop_limit_raw = container.get("hopLimit")
    if hop_limit_raw is None:
        hop_limit_raw = container.get("hop_limit")
    hop_start = _to_int(hop_start_raw)
    hop_limit = _to_int(hop_limit_raw)
    if hop_start is not None and hop_limit is not None:
        derived = hop_start - hop_limit
        if derived >= 0:
            return derived

    for key in ("routing", "route", "metadata", "meta", "rx_metadata", "rxMetadata", "summary", "packet", "payload", "raw"):
        nested_hops = _packet_hops_from_mapping(container.get(key), seen)
        if nested_hops is not None:
            return nested_hops
    return None


def _packet_hops(packet: dict[str, object]) -> Optional[int]:
    hops = _packet_hops_from_mapping(packet)
    if hops is not None:
        return hops
    decoded = packet.get("decoded")
    return _packet_hops_from_mapping(decoded)


def _packet_signal_from_mapping(
    container: object,
    _seen: Optional[set[int]] = None,
) -> tuple[Optional[float], Optional[float]]:
    if not isinstance(container, dict):
        return None, None
    seen = _seen if isinstance(_seen, set) else set()
    marker = id(container)
    if marker in seen:
        return None, None
    seen.add(marker)

    snr = None
    for key in ("rxSnr", "rx_snr", "snr"):
        snr = _finite_float(container.get(key))
        if snr is not None:
            break

    rssi = None
    for key in ("rxRssi", "rx_rssi", "rssi"):
        rssi = _finite_float(container.get(key))
        if rssi is not None:
            break

    if snr is not None and rssi is not None:
        return snr, rssi

    for key in ("routing", "route", "metadata", "meta", "rx_metadata", "rxMetadata", "summary", "packet", "payload", "raw"):
        nested_snr, nested_rssi = _packet_signal_from_mapping(container.get(key), seen)
        if snr is None and nested_snr is not None:
            snr = nested_snr
        if rssi is None and nested_rssi is not None:
            rssi = nested_rssi
        if snr is not None and rssi is not None:
            break

    return snr, rssi


def _packet_signal(packet: dict[str, object]) -> tuple[Optional[float], Optional[float]]:
    snr, rssi = _packet_signal_from_mapping(packet)
    if snr is not None or rssi is not None:
        return snr, rssi
    decoded = packet.get("decoded")
    return _packet_signal_from_mapping(decoded)


def _node_hops(node: object) -> Optional[int]:
    if not isinstance(node, dict):
        return None
    for key in ("hopsAway", "hops_away", "hops", "last_hops", "lastHops"):
        hops = _nonnegative_int(node.get(key))
        if hops is not None:
            return hops
    return None


def _node_signal(node: object) -> tuple[Optional[float], Optional[float]]:
    if not isinstance(node, dict):
        return None, None
    snr = None
    for key in ("snr", "rxSnr", "rx_snr"):
        snr = _finite_float(node.get(key))
        if snr is not None:
            break
    rssi = None
    for key in ("rssi", "rxRssi", "rx_rssi"):
        rssi = _finite_float(node.get(key))
        if rssi is not None:
            break
    return snr, rssi


def _iter_nodes_by_id(iface: object) -> dict[str, dict[str, object]]:
    nodes_by_num = getattr(iface, "nodesByNum", None)
    if not isinstance(nodes_by_num, dict):
        return {}
    out: dict[str, dict[str, object]] = {}
    for raw_num, info in nodes_by_num.items():
        if not isinstance(info, dict):
            continue
        user = info.get("user")
        node_id = ""
        if isinstance(user, dict):
            node_id = _normalize_node_id(user.get("id") or user.get("node_id"))
        if not node_id:
            numeric = _to_int(raw_num)
            if numeric is None or numeric < 0:
                continue
            node_id = _normalize_node_id(f"!{numeric:08x}")
        if not node_id:
            continue
        out[node_id.lower()] = info
    return out


def _local_aliases(iface: object, local_node_id: str) -> set[str]:
    aliases: set[str] = set()
    clean_local = _normalize_node_id(local_node_id)
    if clean_local.startswith("!"):
        aliases.add(clean_local[1:])
        aliases.add(clean_local[1:][-4:])
    local_num = None
    my_info = getattr(iface, "myInfo", None)
    if isinstance(my_info, dict):
        local_num = _to_int(my_info.get("my_node_num") or my_info.get("myNodeNum"))
    nodes_by_num = getattr(iface, "nodesByNum", None)
    if local_num is not None and isinstance(nodes_by_num, dict):
        info = nodes_by_num.get(local_num)
        if isinstance(info, dict):
            user = info.get("user")
            if isinstance(user, dict):
                short_name = _clean_text_token(user.get("shortName") or user.get("short_name"))
                long_name = _clean_text_token(user.get("longName") or user.get("long_name"))
                if short_name:
                    aliases.add(short_name)
                if long_name:
                    aliases.add(long_name)
    return {alias for alias in aliases if alias}


def _target_matches_local(target: str, *, local_node_id: str, local_aliases: set[str]) -> bool:
    clean_target = _clean_text_token(target).replace(" ", "")
    if not clean_target:
        return True
    target_norm = clean_target.lstrip("!")
    local_norm = _normalize_node_id(local_node_id).lower().lstrip("!")
    if not local_norm:
        return False
    if target_norm == local_norm:
        return True
    if len(target_norm) <= len(local_norm) and local_norm.endswith(target_norm):
        return True
    return target_norm in {alias.replace(" ", "") for alias in local_aliases}


def _parse_ping_request(text: str, *, local_aliases: set[str]) -> tuple[str, list[str]] | None:
    clean = _clean_text_token(text)
    if not clean:
        return None
    if clean in _NATURAL_PING_TRIGGERS:
        return "ping", []

    alias_stripped = clean
    for alias in sorted((a for a in local_aliases if " " in a), key=len, reverse=True):
        if alias_stripped.startswith(f"{alias} "):
            alias_stripped = alias_stripped[len(alias):].strip()
            break
    if alias_stripped == clean:
        first, _, rest = clean.partition(" ")
        if first in local_aliases and rest:
            alias_stripped = rest.strip()

    command_text = alias_stripped
    if command_text.startswith("!") or command_text.startswith("#"):
        command_text = command_text[1:].strip()
    if command_text in _NATURAL_PING_TRIGGERS:
        return "ping", []

    head, _, tail = command_text.partition(" ")
    if head not in _PING_HEADS:
        return None
    args = [part for part in tail.split(" ") if part] if tail else []
    return "ping", args


def _format_hops_label(hops: Optional[int]) -> str:
    if hops is None:
        return "hop count n/a."
    if hops == 1:
        return "1 hop."
    return f"{hops} hops."


def _format_signal_label(snr: Optional[float], rssi: Optional[float]) -> str:
    parts: list[str] = []
    if snr is not None:
        parts.append(f"SNR {snr:.2f}dB")
    if rssi is not None:
        parts.append(f"RSSI {int(round(rssi))}dBm")
    return " ".join(parts)


class PingBotService:
    def __init__(
        self,
        *,
        send_lock: object | None = None,
        public_start_enabled: bool = True,
        repeat_delay_seconds: float = _LIVE_REPEAT_DELAY_SECONDS,
        repeat_max_paced_count: int = _LIVE_REPEAT_MAX_PACED_COUNT,
        repeat_send_retry_limit: int = _LIVE_REPEAT_SEND_RETRY_LIMIT,
        repeat_send_retry_delay_seconds: float = _LIVE_REPEAT_SEND_RETRY_DELAY_SECONDS,
        repeat_wait_for_ack: bool = _LIVE_REPEAT_WAIT_FOR_ACK,
        repeat_ack_wait_seconds: float = _LIVE_REPEAT_ACK_WAIT_SECONDS,
        repeat_ack_poll_seconds: float = _LIVE_REPEAT_ACK_POLL_SECONDS,
        repeat_ack_retry_limit: int = _LIVE_REPEAT_ACK_RETRY_LIMIT,
        repeat_async: bool = _LIVE_REPEAT_ASYNC,
        max_async_replies: int = _MAX_ASYNC_PING_REPLIES,
        peer_request_cooldown_seconds: float = _PING_PEER_REQUEST_COOLDOWN_SECONDS,
        global_request_cooldown_seconds: float = _PING_GLOBAL_REQUEST_COOLDOWN_SECONDS,
        monotonic_fn: Callable[[], float] = time.monotonic,
        get_delivery_state_fn: Callable[[object], object] | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._send_lock = send_lock if send_lock is not None else threading.Lock()
        self._mode_lock = threading.Lock()
        self._public_start_enabled = bool(public_start_enabled)
        self._repeat_delay_seconds = max(0.0, float(repeat_delay_seconds))
        self._repeat_max_paced_count = max(1, int(repeat_max_paced_count))
        self._repeat_send_retry_limit = max(0, int(repeat_send_retry_limit))
        self._repeat_send_retry_delay_seconds = max(0.0, float(repeat_send_retry_delay_seconds))
        self._repeat_wait_for_ack = bool(repeat_wait_for_ack)
        self._repeat_ack_wait_seconds = max(0.0, float(repeat_ack_wait_seconds))
        self._repeat_ack_poll_seconds = max(0.05, float(repeat_ack_poll_seconds))
        self._repeat_ack_retry_limit = max(0, int(repeat_ack_retry_limit))
        self._repeat_async = bool(repeat_async)
        self._async_reply_slots = threading.BoundedSemaphore(max(1, int(max_async_replies)))
        self._peer_request_cooldown_seconds = max(0.0, float(peer_request_cooldown_seconds))
        self._global_request_cooldown_seconds = max(0.0, float(global_request_cooldown_seconds))
        self._monotonic_fn = monotonic_fn
        self._request_monotonic_by_peer: dict[str, float] = {}
        self._last_request_monotonic: float | None = None
        self._closed = threading.Event()
        self._get_delivery_state_fn = get_delivery_state_fn
        self._sleep_fn = sleep_fn if callable(sleep_fn) else time.sleep

    def set_public_start_enabled(self, enabled: object) -> bool:
        next_value = bool(enabled)
        with self._mode_lock:
            changed = self._public_start_enabled != next_value
            self._public_start_enabled = next_value
        return changed

    def public_start_enabled(self) -> bool:
        with self._mode_lock:
            return bool(self._public_start_enabled)

    def close(self) -> None:
        self._closed.set()
        with self._mode_lock:
            self._request_monotonic_by_peer.clear()
            self._last_request_monotonic = None

    def _admit_request(self, peer_id: str) -> bool:
        if self._closed.is_set():
            return False
        try:
            now_monotonic = max(0.0, float(self._monotonic_fn()))
        except Exception:
            now_monotonic = time.monotonic()
        with self._mode_lock:
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
            while len(self._request_monotonic_by_peer) > _PING_MAX_RATE_TRACKED_PEERS:
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
        local_node_id = _normalize_node_id(
            _get_local_node_id(
                iface,
                broadcast_num=_BROADCAST_NUM,
                to_int_fn=_to_int,
            )
        )
        if not from_id or not to_id or not local_node_id:
            return False
        to_id_lower = to_id.lower()
        local_id_lower = local_node_id.lower()
        if to_id_lower not in (local_id_lower, "^all"):
            return False
        if to_id_lower == "^all" and not self.public_start_enabled():
            return False
        if from_id.lower() == local_node_id.lower():
            return False

        local_aliases = _local_aliases(iface, local_node_id)
        parsed = _parse_ping_request(text, local_aliases=local_aliases)
        if parsed is None:
            return False
        _, args = parsed
        direct_message = to_id_lower == local_id_lower
        target = ""
        repeat_count = 1
        if args:
            first_arg = args[0]
            if direct_message:
                direct_repeat = _to_int(first_arg)
                if direct_repeat is not None and direct_repeat > 0:
                    repeat_count = min(direct_repeat, _MAX_DIRECT_PING_REPEAT_COUNT)
                else:
                    target = first_arg
                    if len(args) > 1:
                        trailing_repeat = _to_int(args[1])
                        if trailing_repeat is not None and trailing_repeat > 0:
                            repeat_count = min(trailing_repeat, _MAX_DIRECT_PING_REPEAT_COUNT)
            else:
                target = first_arg
        if not _target_matches_local(target, local_node_id=local_node_id, local_aliases=local_aliases):
            return False
        if not self._admit_request(from_id):
            return True

        requester = _iter_nodes_by_id(iface).get(from_id.lower())
        response_texts: list[str] = []
        if direct_message and repeat_count > 1:
            response_texts = [f"{index}/{repeat_count}" for index in range(1, repeat_count + 1)]
        else:
            hops = _packet_hops(packet)
            if hops is None:
                hops = _node_hops(requester)

            signal_snr, signal_rssi = _packet_signal(packet)
            if signal_snr is None or signal_rssi is None:
                node_snr, node_rssi = _node_signal(requester)
                if signal_snr is None:
                    signal_snr = node_snr
                if signal_rssi is None:
                    signal_rssi = node_rssi

            response_text = _format_hops_label(hops)
            signal_text = _format_signal_label(signal_snr, signal_rssi)
            if signal_text:
                response_text = f"{response_text} {signal_text}"
            response_texts = [response_text]
        channel_index = _packet_channel_index(packet)
        reply_id = _packet_id(packet)
        if len(response_texts) <= 1:
            response_text = response_texts[0] if response_texts else ""
            if response_text:
                self._send_ping_reply_with_send_retries(
                    iface,
                    text=response_text,
                    destination_id=from_id,
                    local_node_id=local_node_id,
                    channel_index=channel_index,
                    reply_id=reply_id,
                    retry_of=None,
                    record_local_chat_fn=record_local_chat_fn,
                )
            return True

        should_async_repeat = (
            len(response_texts) > 1
            and self._repeat_async
            and self._should_wait_for_repeat_ack()
        )
        if should_async_repeat:
            if not self._async_reply_slots.acquire(blocking=False):
                return True
            kwargs = {
                    "iface": iface,
                    "responses": response_texts,
                    "destination_id": from_id,
                    "local_node_id": local_node_id,
                    "channel_index": channel_index,
                    "reply_id": reply_id,
                    "record_local_chat_fn": record_local_chat_fn,
                }
            try:
                thread = threading.Thread(
                    target=self._send_repeat_responses_with_slot,
                    kwargs=kwargs,
                    daemon=True,
                )
                thread.start()
            except Exception:
                self._async_reply_slots.release()
            return True

        self._send_repeat_responses(
            iface=iface,
            responses=response_texts,
            destination_id=from_id,
            local_node_id=local_node_id,
            channel_index=channel_index,
            reply_id=reply_id,
            record_local_chat_fn=record_local_chat_fn,
        )
        return True

    def _send_repeat_responses_with_slot(self, **kwargs: object) -> None:
        try:
            self._send_repeat_responses(**kwargs)  # type: ignore[arg-type]
        finally:
            self._async_reply_slots.release()

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
        del text, from_id, to_id, local_node_id, channel_index, reply_id, record_local_chat_fn
        return False

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
            raise RuntimeError("ping bot is closed")
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

    def _sleep_between_repeat_messages(self) -> None:
        if self._repeat_delay_seconds > 0:
            self._wait_or_running(self._repeat_delay_seconds)

    def _sleep_between_repeat_retries(self) -> None:
        if self._repeat_send_retry_delay_seconds > 0:
            self._wait_or_running(self._repeat_send_retry_delay_seconds)

    def _send_repeat_responses(
        self,
        *,
        iface: object,
        responses: list[str],
        destination_id: str,
        local_node_id: str,
        channel_index: int,
        reply_id: Optional[int],
        record_local_chat_fn: RecordLocalChatFn | None = None,
    ) -> None:
        pace_repeat_messages = (
            len(responses) > 1 and len(responses) <= self._repeat_max_paced_count
        )
        for index, response_text in enumerate(responses):
            if self._closed.is_set():
                return
            if index > 0 and pace_repeat_messages:
                self._sleep_between_repeat_messages()
                if self._closed.is_set():
                    return
            if not self._send_ping_reply_until_acked(
                iface,
                text=response_text,
                destination_id=destination_id,
                local_node_id=local_node_id,
                channel_index=channel_index,
                reply_id=reply_id,
                record_local_chat_fn=record_local_chat_fn,
            ):
                return

    def _send_ping_reply_until_acked(
        self,
        iface: object,
        *,
        text: str,
        destination_id: str,
        local_node_id: str,
        channel_index: int,
        reply_id: Optional[int],
        record_local_chat_fn: RecordLocalChatFn | None = None,
    ) -> bool:
        attempt_message_ids: list[int] = []
        original_message_id: Optional[int] = None
        for attempt_index in range(self._repeat_ack_retry_limit + 1):
            if self._closed.is_set():
                return False
            retry_of = original_message_id if attempt_index > 0 else None
            send_ok, sent_message_id = self._send_ping_reply_with_send_retries(
                iface,
                text=text,
                destination_id=destination_id,
                local_node_id=local_node_id,
                channel_index=channel_index,
                reply_id=reply_id,
                retry_of=retry_of,
                record_local_chat_fn=record_local_chat_fn,
            )
            if not send_ok:
                return False
            if original_message_id is None and sent_message_id is not None:
                original_message_id = sent_message_id
            if sent_message_id is not None and sent_message_id > 0:
                attempt_message_ids.append(int(sent_message_id))
            if not self._should_wait_for_repeat_ack():
                return True
            if self._wait_for_repeat_ack(attempt_message_ids):
                return True
        return not self._should_wait_for_repeat_ack()

    def _should_wait_for_repeat_ack(self) -> bool:
        return bool(self._repeat_wait_for_ack and self._get_delivery_state_fn is not None)

    def _wait_for_repeat_ack(self, message_ids: list[int]) -> bool:
        if not message_ids:
            return True
        if self._any_delivery_is_acked(message_ids):
            return True
        if self._repeat_ack_wait_seconds <= 0:
            return False
        deadline = time.monotonic() + self._repeat_ack_wait_seconds
        while time.monotonic() < deadline:
            if self._closed.is_set():
                return False
            if self._any_delivery_is_acked(message_ids):
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return self._any_delivery_is_acked(message_ids)
            if not self._wait_or_running(min(self._repeat_ack_poll_seconds, remaining)):
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

    def _send_ping_reply_with_send_retries(
        self,
        iface: object,
        *,
        text: str,
        destination_id: str,
        local_node_id: str,
        channel_index: int,
        reply_id: Optional[int],
        retry_of: Optional[int] = None,
        record_local_chat_fn: RecordLocalChatFn | None = None,
    ) -> tuple[bool, Optional[int]]:
        for attempt_index in range(self._repeat_send_retry_limit + 1):
            if self._closed.is_set():
                return False, None
            try:
                sent_message_id = self._send_ping_reply(
                    iface,
                    text=text,
                    destination_id=destination_id,
                    local_node_id=local_node_id,
                    channel_index=channel_index,
                    reply_id=reply_id,
                    retry_of=retry_of,
                    record_local_chat_fn=record_local_chat_fn,
                )
            except Exception:
                if attempt_index < self._repeat_send_retry_limit:
                    self._sleep_between_repeat_retries()
                    continue
                return False, None
            return True, sent_message_id
        return False, None

    def _send_ping_reply(
        self,
        iface: object,
        *,
        text: str,
        destination_id: str,
        local_node_id: str,
        channel_index: int,
        reply_id: Optional[int],
        retry_of: Optional[int] = None,
        record_local_chat_fn: RecordLocalChatFn | None = None,
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
                bot_command="ping",
            )
        return sent_message_id


def build_ping_bot_service(
    *,
    send_lock: object | None = None,
    public_start_enabled: bool = True,
    repeat_delay_seconds: float = _LIVE_REPEAT_DELAY_SECONDS,
    repeat_max_paced_count: int = _LIVE_REPEAT_MAX_PACED_COUNT,
    repeat_send_retry_limit: int = _LIVE_REPEAT_SEND_RETRY_LIMIT,
    repeat_send_retry_delay_seconds: float = _LIVE_REPEAT_SEND_RETRY_DELAY_SECONDS,
    repeat_wait_for_ack: bool = _LIVE_REPEAT_WAIT_FOR_ACK,
    repeat_ack_wait_seconds: float = _LIVE_REPEAT_ACK_WAIT_SECONDS,
    repeat_ack_poll_seconds: float = _LIVE_REPEAT_ACK_POLL_SECONDS,
    repeat_ack_retry_limit: int = _LIVE_REPEAT_ACK_RETRY_LIMIT,
    repeat_async: bool = _LIVE_REPEAT_ASYNC,
    peer_request_cooldown_seconds: float = _PING_PEER_REQUEST_COOLDOWN_SECONDS,
    global_request_cooldown_seconds: float = _PING_GLOBAL_REQUEST_COOLDOWN_SECONDS,
    monotonic_fn: Callable[[], float] = time.monotonic,
    get_delivery_state_fn: Callable[[object], object] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> PingBotService:
    return PingBotService(
        send_lock=send_lock,
        public_start_enabled=public_start_enabled,
        repeat_delay_seconds=repeat_delay_seconds,
        repeat_max_paced_count=repeat_max_paced_count,
        repeat_send_retry_limit=repeat_send_retry_limit,
        repeat_send_retry_delay_seconds=repeat_send_retry_delay_seconds,
        repeat_wait_for_ack=repeat_wait_for_ack,
        repeat_ack_wait_seconds=repeat_ack_wait_seconds,
        repeat_ack_poll_seconds=repeat_ack_poll_seconds,
        repeat_ack_retry_limit=repeat_ack_retry_limit,
        repeat_async=repeat_async,
        peer_request_cooldown_seconds=peer_request_cooldown_seconds,
        global_request_cooldown_seconds=global_request_cooldown_seconds,
        monotonic_fn=monotonic_fn,
        get_delivery_state_fn=get_delivery_state_fn,
        sleep_fn=sleep_fn,
    )


__all__ = ["PingBotService", "build_ping_bot_service"]
