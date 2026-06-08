import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field

from .config import DEFAULT_CHAT_MAX_BYTES
from .file_transfer_protocol import (
    build_file_transfer_ack_frame,
    parse_file_transfer_frame_text,
)
from .helpers import to_int as _to_int
from .helpers_node_names import normalize_node_id_text as _normalize_node_id_text
from .nodes_identity import get_node_id_from_num as _get_node_id_from_num


_BROADCAST_NODE_NUM = 0xFFFFFFFF
_ACK_COOLDOWN_SECONDS = 0.9
_META_ACK_REFRESH_SECONDS = 2.5
_SESSION_TTL_SECONDS = 20 * 60
_MAX_SESSIONS = 96


@dataclass
class _InboundTransferSession:
    sender_id: str
    receiver_id: str
    transfer_id: str
    channel_index: int
    total_chunks: int
    file_name: str = "mesh-file.bin"
    file_size: int = 0
    original_file_size: int = 0
    codec: str = "raw"
    received_indexes: set[int] = field(default_factory=set)
    created_monotonic: float = 0.0
    updated_monotonic: float = 0.0
    created_unix: int = 0
    updated_unix: int = 0
    last_ack_monotonic: float = 0.0
    last_ack_signature: str = ""


def _is_canonical_node_id(value: object) -> bool:
    text = _normalize_node_id_text(value)
    return bool(text.startswith("!") and len(text) == 9)


def _normalize_channel_index(value: object, *, fallback: int = 0) -> int:
    candidate = _to_int(value)
    if candidate is None or candidate < 0:
        return max(0, int(fallback))
    return int(candidate)


def _extract_packet_text(packet: object) -> str:
    if not isinstance(packet, Mapping):
        return ""
    decoded = packet.get("decoded")
    if isinstance(decoded, Mapping):
        text = decoded.get("text")
        if isinstance(text, str):
            return text.strip()
    text = packet.get("decoded_text")
    if isinstance(text, str):
        return text.strip()
    return ""


def _node_id_from_num(interface: object | None, node_num: object) -> str:
    numeric = _to_int(node_num)
    if numeric is None:
        return ""
    if numeric == _BROADCAST_NODE_NUM:
        return "^all"
    if interface is not None:
        try:
            node_id = _get_node_id_from_num(
                interface,
                numeric,
                broadcast_num=_BROADCAST_NODE_NUM,
            )
        except Exception:
            node_id = None
        if node_id:
            return _normalize_node_id_text(node_id)
    return f"!{int(numeric):08x}"


def _packet_endpoint_id(packet: Mapping[str, object], endpoint: str, interface: object | None) -> str:
    if endpoint == "from":
        for key in ("fromId", "from_id"):
            value = packet.get(key)
            if value:
                return _normalize_node_id_text(value)
        return _node_id_from_num(interface, packet.get("from"))
    for key in ("toId", "to_id"):
        value = packet.get(key)
        if value:
            return _normalize_node_id_text(value)
    return _node_id_from_num(interface, packet.get("to"))


class FileTransferAutoAcceptService:
    def __init__(
        self,
        *,
        local_node_id_fn,
        send_chat_fn,
        enabled: bool = True,
        now_monotonic_fn=time.monotonic,
        now_unix_fn=time.time,
        ack_cooldown_seconds: float = _ACK_COOLDOWN_SECONDS,
        meta_ack_refresh_seconds: float = _META_ACK_REFRESH_SECONDS,
        session_ttl_seconds: int = _SESSION_TTL_SECONDS,
        max_sessions: int = _MAX_SESSIONS,
        max_ack_frame_bytes: int = DEFAULT_CHAT_MAX_BYTES,
    ) -> None:
        self._lock = threading.Lock()
        self._local_node_id_fn = local_node_id_fn
        self._send_chat_fn = send_chat_fn
        self._enabled = bool(enabled)
        self._now_monotonic_fn = now_monotonic_fn
        self._now_unix_fn = now_unix_fn
        self._ack_cooldown_seconds = max(0.0, float(ack_cooldown_seconds))
        self._meta_ack_refresh_seconds = max(0.0, float(meta_ack_refresh_seconds))
        self._session_ttl_seconds = max(60, int(session_ttl_seconds))
        self._max_sessions = max(1, int(max_sessions))
        self._max_ack_frame_bytes = max(1, int(max_ack_frame_bytes))
        self._sessions_by_key: dict[str, _InboundTransferSession] = {}
        self._sent_ack_count = 0
        self._last_error = ""

    def _now_unix(self) -> int:
        try:
            return max(0, int(self._now_unix_fn()))
        except Exception:
            return 0

    def _session_runtime_row(
        self,
        session: _InboundTransferSession,
        *,
        now_monotonic: float,
    ) -> dict[str, object]:
        total_chunks = max(1, int(session.total_chunks or 1))
        received_indexes = sorted(
            idx for idx in session.received_indexes if 0 <= int(idx) < total_chunks
        )
        received_chunks = min(total_chunks, len(received_indexes))
        missing_chunks = max(0, total_chunks - received_chunks)
        percent = round((received_chunks / total_chunks) * 100, 1)
        key = self._session_key(
            session.sender_id,
            session.receiver_id,
            session.transfer_id,
        )
        age_seconds = max(0.0, float(now_monotonic) - float(session.created_monotonic or now_monotonic))
        idle_seconds = max(0.0, float(now_monotonic) - float(session.updated_monotonic or now_monotonic))
        return {
            "key": key,
            "source": "backend_auto_accept",
            "authoritative": True,
            "sender_id": session.sender_id,
            "receiver_id": session.receiver_id,
            "transfer_id": session.transfer_id,
            "channel_index": int(session.channel_index),
            "file_name": session.file_name or "mesh-file.bin",
            "file_size": max(0, int(session.file_size or 0)),
            "original_file_size": max(0, int(session.original_file_size or session.file_size or 0)),
            "codec": session.codec or "raw",
            "total_chunks": total_chunks,
            "received_chunks": received_chunks,
            "missing_chunks": missing_chunks,
            "received_indexes": received_indexes,
            "percent": percent,
            "complete": received_chunks >= total_chunks,
            "created_unix": max(0, int(session.created_unix or 0)),
            "updated_unix": max(0, int(session.updated_unix or 0)),
            "age_seconds": round(age_seconds, 3),
            "idle_seconds": round(idle_seconds, 3),
            "last_ack_age_seconds": (
                round(max(0.0, float(now_monotonic) - float(session.last_ack_monotonic)), 3)
                if session.last_ack_monotonic > 0
                else None
            ),
        }

    def get_runtime(self) -> dict[str, object]:
        with self._lock:
            now_monotonic = float(self._now_monotonic_fn())
            sessions = [
                self._session_runtime_row(session, now_monotonic=now_monotonic)
                for session in self._sessions_by_key.values()
            ]
            sessions.sort(
                key=lambda row: (
                    int(row.get("updated_unix") or 0),
                    str(row.get("key") or ""),
                ),
                reverse=True,
            )
            return {
                "ok": True,
                "enabled": bool(self._enabled),
                "active_sessions": len(self._sessions_by_key),
                "sessions": sessions,
                "sent_ack_count": int(self._sent_ack_count),
                "last_error": self._last_error,
            }

    def _local_node_id(self) -> str:
        try:
            return _normalize_node_id_text(self._local_node_id_fn())
        except Exception:
            return ""

    def _session_key(self, sender_id: str, receiver_id: str, transfer_id: str) -> str:
        return f"{sender_id}|{receiver_id}|{transfer_id}"

    def _prune_locked(self, now_monotonic: float) -> None:
        stale_before = now_monotonic - self._session_ttl_seconds
        stale_keys = [
            key
            for key, session in self._sessions_by_key.items()
            if session.updated_monotonic < stale_before
        ]
        for key in stale_keys:
            self._sessions_by_key.pop(key, None)
        if len(self._sessions_by_key) <= self._max_sessions:
            return
        ordered = sorted(
            self._sessions_by_key.items(),
            key=lambda item: item[1].updated_monotonic,
        )
        while len(ordered) > self._max_sessions:
            key, _session = ordered.pop(0)
            self._sessions_by_key.pop(key, None)

    def _ack_signature(self, session: _InboundTransferSession) -> str:
        indexes = ",".join(str(idx) for idx in sorted(session.received_indexes))
        return f"{len(session.received_indexes)}/{session.total_chunks}|{indexes}"

    def _build_ack_send(
        self,
        session: _InboundTransferSession,
        *,
        now_monotonic: float,
        force: bool = False,
        final: bool = False,
    ) -> tuple[str, str, int] | None:
        signature = self._ack_signature(session)
        signature_changed = signature != session.last_ack_signature
        due = (
            session.last_ack_monotonic <= 0
            or (now_monotonic - session.last_ack_monotonic) >= self._ack_cooldown_seconds
        )
        if force:
            due = (
                session.last_ack_monotonic <= 0
                or (now_monotonic - session.last_ack_monotonic) >= self._meta_ack_refresh_seconds
            )
        if final:
            due = True
        if not (final or (signature_changed and due) or force and due):
            return None
        frame = build_file_transfer_ack_frame(
            transfer_id=session.transfer_id,
            total_chunks=session.total_chunks,
            received_indexes=session.received_indexes,
        )
        if not frame:
            return None
        if len(frame.encode("utf-8")) > self._max_ack_frame_bytes:
            return None
        session.last_ack_signature = signature
        session.last_ack_monotonic = now_monotonic
        return frame, session.sender_id, session.channel_index

    def _send_ack(self, payload: tuple[str, str, int] | None) -> None:
        if payload is None:
            return
        frame, destination, channel_index = payload
        try:
            response = self._send_chat_fn(
                text=frame,
                destination=destination,
                channel_index=channel_index,
            )
            if isinstance(response, Mapping) and response.get("ok") is False:
                with self._lock:
                    self._last_error = str(response.get("error") or "send failed")
                return
        except Exception as exc:
            with self._lock:
                self._last_error = str(exc)
            return
        with self._lock:
            self._sent_ack_count += 1
            self._last_error = ""

    def _handle_meta(
        self,
        *,
        sender_id: str,
        receiver_id: str,
        channel_index: int,
        frame: Mapping[str, object],
        now_monotonic: float,
    ) -> tuple[str, str, int] | None:
        transfer_id = str(frame.get("transfer_id") or "").strip().lower()
        total_chunks = max(1, int(frame.get("total_chunks") or 1))
        file_name = str(frame.get("file_name") or "mesh-file.bin").strip() or "mesh-file.bin"
        file_size = max(0, int(frame.get("file_size") or 0))
        original_file_size = max(0, int(frame.get("original_file_size") or file_size or 0))
        codec = str(frame.get("codec") or "raw").strip().lower() or "raw"
        key = self._session_key(sender_id, receiver_id, transfer_id)
        now_unix = self._now_unix()
        with self._lock:
            self._prune_locked(now_monotonic)
            session = self._sessions_by_key.get(key)
            if session is None:
                session = _InboundTransferSession(
                    sender_id=sender_id,
                    receiver_id=receiver_id,
                    transfer_id=transfer_id,
                    channel_index=channel_index,
                    total_chunks=total_chunks,
                    file_name=file_name,
                    file_size=file_size,
                    original_file_size=original_file_size,
                    codec=codec,
                    created_monotonic=now_monotonic,
                    updated_monotonic=now_monotonic,
                    created_unix=now_unix,
                    updated_unix=now_unix,
                )
                self._sessions_by_key[key] = session
            else:
                session.channel_index = channel_index
                session.total_chunks = total_chunks
                session.file_name = file_name
                session.file_size = file_size
                session.original_file_size = original_file_size
                session.codec = codec
                session.updated_monotonic = now_monotonic
                session.updated_unix = now_unix
                session.received_indexes = {
                    idx for idx in session.received_indexes if 0 <= idx < total_chunks
                }
            return self._build_ack_send(session, now_monotonic=now_monotonic, force=True)

    def _handle_chunk(
        self,
        *,
        sender_id: str,
        receiver_id: str,
        channel_index: int,
        frame: Mapping[str, object],
        now_monotonic: float,
    ) -> tuple[str, str, int] | None:
        transfer_id = str(frame.get("transfer_id") or "").strip().lower()
        chunk_index = _to_int(frame.get("chunk_index"))
        if chunk_index is None or chunk_index < 0:
            return None
        key = self._session_key(sender_id, receiver_id, transfer_id)
        now_unix = self._now_unix()
        with self._lock:
            self._prune_locked(now_monotonic)
            session = self._sessions_by_key.get(key)
            if session is None:
                return None
            session.channel_index = channel_index
            session.updated_monotonic = now_monotonic
            session.updated_unix = now_unix
            if chunk_index < session.total_chunks:
                session.received_indexes.add(int(chunk_index))
            final = len(session.received_indexes) >= session.total_chunks
            return self._build_ack_send(
                session,
                now_monotonic=now_monotonic,
                final=final,
            )

    def _handle_flow(
        self,
        *,
        sender_id: str,
        receiver_id: str,
        frame: Mapping[str, object],
        now_monotonic: float,
    ) -> None:
        action = str(frame.get("action") or "").strip().lower()
        if action != "cancel":
            return
        transfer_id = str(frame.get("transfer_id") or "").strip().lower()
        key = self._session_key(sender_id, receiver_id, transfer_id)
        with self._lock:
            self._prune_locked(now_monotonic)
            self._sessions_by_key.pop(key, None)

    def on_receive(self, packet: object, interface: object | None = None) -> None:
        if not self._enabled:
            return
        if not isinstance(packet, Mapping):
            return
        frame = parse_file_transfer_frame_text(_extract_packet_text(packet))
        if frame is None:
            return
        kind = str(frame.get("kind") or "").strip().lower()
        if kind not in {"meta", "chunk", "flow"}:
            return

        local_id = self._local_node_id()
        if not _is_canonical_node_id(local_id):
            return
        sender_id = _packet_endpoint_id(packet, "from", interface)
        receiver_id = _packet_endpoint_id(packet, "to", interface)
        if not _is_canonical_node_id(sender_id):
            return
        if receiver_id != local_id:
            return
        if sender_id == local_id:
            return

        now_monotonic = float(self._now_monotonic_fn())
        channel_index = _normalize_channel_index(packet.get("channel"))
        if kind == "meta":
            payload = self._handle_meta(
                sender_id=sender_id,
                receiver_id=receiver_id,
                channel_index=channel_index,
                frame=frame,
                now_monotonic=now_monotonic,
            )
            self._send_ack(payload)
            return
        if kind == "chunk":
            payload = self._handle_chunk(
                sender_id=sender_id,
                receiver_id=receiver_id,
                channel_index=channel_index,
                frame=frame,
                now_monotonic=now_monotonic,
            )
            self._send_ack(payload)
            return
        self._handle_flow(
            sender_id=sender_id,
            receiver_id=receiver_id,
            frame=frame,
            now_monotonic=now_monotonic,
        )


def build_file_transfer_auto_accept_service(**kwargs: object) -> FileTransferAutoAcceptService:
    return FileTransferAutoAcceptService(**kwargs)


__all__ = [
    "FileTransferAutoAcceptService",
    "build_file_transfer_auto_accept_service",
]
