import base64
import hashlib
import json
import re
import threading
import time
from collections import deque
from collections.abc import Mapping

from .config import DEFAULT_CHAT_MAX_BYTES
from .helpers import to_int as _to_int
from .helpers_node_names import normalize_node_id_text as _normalize_node_id_text
from .nodes_identity import get_local_node_num as _get_local_node_num

_BBS_PROTOCOL_VERSION = "bbs1"
_BBS_MAX_POST_HISTORY_REPLY = 32
_BBS_MAX_POST_SYNC_REPLY = 260
_BBS_MAX_WIRE_BYTES = DEFAULT_CHAT_MAX_BYTES
_BBS_MAX_POST_CHARS = DEFAULT_CHAT_MAX_BYTES
_BBS_MAX_SUBSCRIBERS = 24
_BBS_SUBSCRIBER_TTL_SECONDS = 20 * 60
_BBS_SEND_SPACING_SECONDS = 0.45
_BBS_DELIVERY_WAIT_TIMEOUT_SECONDS = 4.5
_BBS_DELIVERY_POLL_SECONDS = 0.15
_BBS_MAX_SEND_ATTEMPTS = 3
_BBS_RETRY_BACKOFF_SECONDS = 1.0
_FILE_TRANSFER_PROTOCOL_PREFIX = "MF_FILE_V1"
_BBS_SNAPSHOT_TRANSFER_CHUNK_BYTES = 64
_BBS_SNAPSHOT_MAX_RESENDS = 8


def _sanitize_bbs_text(value: object, max_chars: int) -> str:
    limit = max(1, int(max_chars))
    return (
        " ".join(str(value if value is not None else "").replace("|", " ").split())
        .strip()
        [:limit]
    )


def _normalize_bbs_board_id(value: object, fallback: object = "") -> str:
    text = str(value or fallback or "").strip().lower()
    text = re.sub(r"[^a-z0-9_-]+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = re.sub(r"^[-_]+|[-_]+$", "", text)
    return text[:24]


def _coerce_bbs_enabled(value: object, *, fallback: bool = False) -> bool:
    if value is None:
        return bool(fallback)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "enabled", "online"}:
        return True
    if text in {"0", "false", "no", "off", "disabled", "offline"}:
        return False
    return bool(fallback)


def _normalize_bbs_settings(payload: object) -> dict[str, object]:
    source = payload if isinstance(payload, Mapping) else {}
    title = _sanitize_bbs_text(source.get("title"), 42) or "Packet Exchange"
    board_id = _normalize_bbs_board_id(
        source.get("board_id", source.get("boardId")),
        title,
    )
    motd = _sanitize_bbs_text(source.get("motd"), 120) or "2400 baud online."
    return {
        "title": title,
        "board_id": board_id,
        "motd": motd,
        "enabled": _coerce_bbs_enabled(source.get("enabled")),
        "channel_index": _normalize_channel_index(source.get("channel_index", source.get("channelIndex"))),
        "started_unix": _positive_unix(source.get("started_unix", source.get("startedUnix"))),
    }


def _normalize_channel_index(value: object, *, fallback: int = 0) -> int:
    candidate = _to_int(value)
    if candidate is None or candidate < 0:
        return max(0, int(fallback))
    return int(candidate)


def _is_canonical_node_id(value: object) -> bool:
    text = _normalize_node_id_text(value)
    return bool(text.startswith("!") and len(text) == 9)


def _normalize_request_settings(request: object) -> dict[str, object]:
    return _normalize_bbs_settings(
        {
            "title": getattr(request, "title", None),
            "board_id": getattr(request, "board_id", None),
            "motd": getattr(request, "motd", None),
        }
    )


def _generate_post_entry_id(now_unix: int, author_id: str, text: str) -> str:
    seed = f"{now_unix}|{author_id}|{text}"
    return f"bbs-{now_unix:x}-{abs(hash(seed)) & 0xFFFFFFFF:08x}"


def _normalize_post_payload(payload: object) -> dict[str, object] | None:
    source = payload if isinstance(payload, Mapping) else {}
    text = _sanitize_bbs_text(source.get("text"), _BBS_MAX_POST_CHARS)
    if not text:
        return None
    author_id = _normalize_node_id_text(source.get("author_id", source.get("authorId")))
    if not _is_canonical_node_id(author_id):
        author_id = ""
    author_name = _sanitize_bbs_text(
        source.get("author_name", source.get("authorName")),
        48,
    )
    entry_id = _sanitize_bbs_text(
        source.get("entry_id", source.get("entryId")),
        60,
    )
    try:
        unix_value = int(source.get("unix") or 0)
    except Exception:
        unix_value = 0
    unix_value = max(0, unix_value)
    if not entry_id:
        entry_id = _generate_post_entry_id(unix_value, author_id, text)
    return {
        "entry_id": entry_id,
        "author_id": author_id,
        "author_name": author_name or author_id or "anon",
        "text": text,
        "unix": unix_value,
    }


def _post_sort_key(post: Mapping[str, object]) -> tuple[int, str]:
    try:
        unix_value = int(post.get("unix") or 0)
    except Exception:
        unix_value = 0
    return max(0, unix_value), str(post.get("entry_id") or "").strip()


def _posts_after_cursor(
    posts: list[dict[str, object]],
    *,
    current_board_id: object,
    requested_board_id: object,
    since_unix: object,
    tail_entry_id: object,
) -> list[dict[str, object]]:
    rows = sorted(posts, key=_post_sort_key)
    requested_board = _normalize_bbs_board_id(requested_board_id)
    current_board = _normalize_bbs_board_id(current_board_id)
    try:
        cursor_unix = max(0, int(since_unix or 0))
    except Exception:
        cursor_unix = 0
    cursor_entry = _sanitize_bbs_text(tail_entry_id, 60)
    cursor_matches_board = bool(cursor_unix > 0 and (not requested_board or requested_board == current_board))
    if not cursor_matches_board:
        return rows[-_BBS_MAX_POST_HISTORY_REPLY:]
    if cursor_entry:
        for idx, post in enumerate(rows):
            if str(post.get("entry_id") or "").strip() == cursor_entry:
                return rows[idx + 1 :][-_BBS_MAX_POST_SYNC_REPLY:]
    return [post for post in rows if _post_sort_key(post)[0] >= cursor_unix][-_BBS_MAX_POST_SYNC_REPLY:]


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


def _parse_protocol_message(text: object) -> tuple[str, list[str]] | None:
    raw = str(text or "").strip()
    if not raw or not raw.startswith(f"{_BBS_PROTOCOL_VERSION}|"):
        return None
    parts = [str(part or "").strip() for part in raw.split("|")]
    if len(parts) < 2:
        return None
    message_type = str(parts[1] or "").strip().lower()
    if not message_type:
        return None
    return message_type, parts


def _parse_file_transfer_ack(text: object) -> dict[str, object] | None:
    raw = str(text or "").strip()
    if not raw.startswith(f"{_FILE_TRANSFER_PROTOCOL_PREFIX}|A|"):
        return None
    parts = [str(part or "").strip() for part in raw.split("|")]
    if len(parts) < 6:
        return None
    transfer_id = parts[2].lower()
    if not re.fullmatch(r"[a-z0-9]{4,24}", transfer_id):
        return None
    try:
        received_count = max(0, int(parts[3] or 0))
        total_chunks = max(1, int(parts[4] or 1))
    except Exception:
        return None
    bitmap_raw = parts[5]
    received_indexes: set[int] = set()
    if bitmap_raw:
        try:
            bitmap = base64.b64decode(bitmap_raw, validate=True)
        except Exception:
            bitmap = b""
        for idx in range(total_chunks):
            byte_idx = idx // 8
            if byte_idx >= len(bitmap):
                break
            if bitmap[byte_idx] & (1 << (idx % 8)):
                received_indexes.add(idx)
    return {
        "transfer_id": transfer_id,
        "received_count": min(received_count, total_chunks),
        "total_chunks": total_chunks,
        "received_indexes": received_indexes,
    }


def _encode_protocol_message(message_type: object, *fields: object) -> str:
    clean_type = str(message_type or "").strip().lower()
    if not clean_type:
        return ""
    encoded = [_BBS_PROTOCOL_VERSION, clean_type]
    for field in fields:
        encoded.append(_sanitize_bbs_text(field, _BBS_MAX_POST_CHARS))
    return "|".join(encoded)


def _positive_unix(value: object) -> int:
    try:
        unix_value = int(value or 0)
    except Exception:
        unix_value = 0
    return max(0, unix_value)


def _post_protocol_fields(
    *,
    board_id: object,
    host_id: object,
    post: Mapping[str, object],
) -> list[object]:
    return [
        board_id,
        host_id,
        post.get("entry_id"),
        post.get("author_id"),
        post.get("author_name"),
        post.get("text"),
        post.get("unix"),
    ]


def _compact_batch_row(post: Mapping[str, object]) -> list[object]:
    return [
        _sanitize_bbs_text(post.get("entry_id"), 60),
        _normalize_node_id_text(post.get("author_id")),
        _sanitize_bbs_text(post.get("author_name"), 48),
        _sanitize_bbs_text(post.get("text"), _BBS_MAX_POST_CHARS),
        _positive_unix(post.get("unix")),
    ]


def _encode_bbs_batch_message(
    *,
    board_id: object,
    host_id: object,
    posts: list[Mapping[str, object]],
) -> str:
    if not posts:
        return ""
    clean_board = _normalize_bbs_board_id(board_id)
    clean_host = _normalize_node_id_text(host_id)
    if not clean_board or not _is_canonical_node_id(clean_host):
        return ""
    rows = [_compact_batch_row(post) for post in posts]
    payload_json = json.dumps(rows, separators=(",", ":"), ensure_ascii=True)
    payload = (
        base64.urlsafe_b64encode(payload_json.encode("ascii"))
        .decode("ascii")
        .rstrip("=")
    )
    if not payload:
        return ""
    message = f"{_BBS_PROTOCOL_VERSION}|batch|{clean_board}|{clean_host}|{payload}"
    if len(message.encode("utf-8")) > _BBS_MAX_WIRE_BYTES:
        return ""
    return message


def _queueable_history_messages(
    *,
    board_id: object,
    host_id: object,
    posts: list[dict[str, object]],
) -> list[str]:
    messages: list[str] = []
    batch: list[dict[str, object]] = []

    def flush_batch() -> None:
        nonlocal batch
        if not batch:
            return
        if len(batch) >= 2:
            batch_message = _encode_bbs_batch_message(
                board_id=board_id,
                host_id=host_id,
                posts=batch,
            )
            if batch_message:
                messages.append(batch_message)
                batch = []
                return
        for post in batch:
            messages.append(
                _encode_protocol_message(
                    "post",
                    *_post_protocol_fields(board_id=board_id, host_id=host_id, post=post),
                )
            )
        batch = []

    for post in posts:
        candidate = [*batch, post]
        candidate_message = _encode_bbs_batch_message(
            board_id=board_id,
            host_id=host_id,
            posts=candidate,
        )
        if candidate_message:
            batch = candidate
            continue
        flush_batch()
        single_batch_message = _encode_bbs_batch_message(
            board_id=board_id,
            host_id=host_id,
            posts=[post],
        )
        if single_batch_message:
            batch = [post]
        else:
            messages.append(
                _encode_protocol_message(
                    "post",
                    *_post_protocol_fields(board_id=board_id, host_id=host_id, post=post),
                )
            )
    flush_batch()
    return [message for message in messages if message]


def _build_snapshot_transfer_id(request_token: object, board_id: object, host_id: object) -> str:
    seed = f"{request_token}|{board_id}|{host_id}|{time.time_ns()}"
    digest = hashlib.sha1(seed.encode("utf-8"), usedforsecurity=False).hexdigest()
    return f"bbs{digest[:15]}"


def _build_snapshot_file_name(board_id: object, host_id: object) -> str:
    clean_board = _normalize_bbs_board_id(board_id) or "board"
    clean_host = _normalize_node_id_text(host_id).replace("!", "") or "host"
    return f"bbs-snapshot-{clean_board}-{clean_host}.json"[:92]


def _encode_file_transfer_meta_frame(
    *,
    transfer_id: str,
    file_name: str,
    file_size: int,
    total_chunks: int,
) -> str:
    return (
        f"{_FILE_TRANSFER_PROTOCOL_PREFIX}|M|{transfer_id}|{file_name}|"
        f"{max(0, int(file_size))}|{max(1, int(total_chunks))}|raw|{max(0, int(file_size))}"
    )


def _encode_file_transfer_chunk_frame(
    *,
    transfer_id: str,
    chunk_index: int,
    chunk: bytes,
) -> str:
    payload = base64.b64encode(chunk).decode("ascii")
    return f"{_FILE_TRANSFER_PROTOCOL_PREFIX}|C|{transfer_id}|{max(0, int(chunk_index))}|{payload}"


def _build_bbs_snapshot_file_frames(
    *,
    request_token: object,
    settings: Mapping[str, object],
    host_id: object,
    posts: list[dict[str, object]],
    total_post_count: object = None,
    latest_unix: object = None,
    latest_entry_id: object = None,
) -> dict[str, object] | None:
    clean_host = _normalize_node_id_text(host_id)
    clean_board = _normalize_bbs_board_id(settings.get("board_id"))
    if not clean_board or not _is_canonical_node_id(clean_host):
        return None
    sorted_posts = sorted(posts, key=_post_sort_key)[-_BBS_MAX_POST_SYNC_REPLY:]
    latest_post = sorted_posts[-1] if sorted_posts else {}
    try:
        total_count = max(0, int(total_post_count if total_post_count is not None else len(sorted_posts)))
    except Exception:
        total_count = len(sorted_posts)
    latest_unix_value = _positive_unix(latest_unix)
    if latest_unix_value <= 0 and latest_post:
        latest_unix_value = _post_sort_key(latest_post)[0]
    latest_entry_value = _sanitize_bbs_text(latest_entry_id, 60)
    if not latest_entry_value and latest_post:
        latest_entry_value = str(latest_post.get("entry_id") or "")
    snapshot = {
        "kind": "easyface-bbs-snapshot-v1",
        "board_id": clean_board,
        "host_id": clean_host,
        "title": _sanitize_bbs_text(settings.get("title"), 42) or clean_board,
        "motd": _sanitize_bbs_text(settings.get("motd"), 120),
        "post_count": total_count,
        "included_post_count": len(sorted_posts),
        "latest_unix": latest_unix_value,
        "latest_entry_id": latest_entry_value,
        "posts": [_compact_batch_row(post) for post in sorted_posts],
    }
    payload = json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if not payload:
        return None
    transfer_id = _build_snapshot_transfer_id(request_token, clean_board, clean_host)
    chunks = [
        payload[idx : idx + _BBS_SNAPSHOT_TRANSFER_CHUNK_BYTES]
        for idx in range(0, len(payload), _BBS_SNAPSHOT_TRANSFER_CHUNK_BYTES)
    ] or [b""]
    file_name = _build_snapshot_file_name(clean_board, clean_host)
    meta_frame = _encode_file_transfer_meta_frame(
        transfer_id=transfer_id,
        file_name=file_name,
        file_size=len(payload),
        total_chunks=len(chunks),
    )
    chunk_frames = [
        _encode_file_transfer_chunk_frame(
            transfer_id=transfer_id,
            chunk_index=idx,
            chunk=chunk,
        )
        for idx, chunk in enumerate(chunks)
    ]
    return {
        "transfer_id": transfer_id,
        "file_name": file_name,
        "meta_frame": meta_frame,
        "chunk_frames": chunk_frames,
    }


class BbsHostService:
    def __init__(
        self,
        *,
        local_node_id_fn,
        send_chat_fn,
        get_bbs_settings_fn=None,
        set_bbs_settings_fn=None,
        get_bbs_posts_fn=None,
        append_bbs_post_fn=None,
        get_delivery_state_fn=None,
        now_unix_fn=time.time,
        send_spacing_seconds: float = _BBS_SEND_SPACING_SECONDS,
        subscriber_ttl_seconds: int = _BBS_SUBSCRIBER_TTL_SECONDS,
        delivery_wait_timeout_seconds: float = _BBS_DELIVERY_WAIT_TIMEOUT_SECONDS,
        delivery_poll_seconds: float = _BBS_DELIVERY_POLL_SECONDS,
        max_send_attempts: int = _BBS_MAX_SEND_ATTEMPTS,
        retry_backoff_seconds: float = _BBS_RETRY_BACKOFF_SECONDS,
    ) -> None:
        self._lock = threading.Lock()
        self._send_cond = threading.Condition()
        self._local_node_id_fn = local_node_id_fn
        self._send_chat_fn = send_chat_fn
        self._get_bbs_settings_fn = get_bbs_settings_fn
        self._set_bbs_settings_fn = set_bbs_settings_fn
        self._get_bbs_posts_fn = get_bbs_posts_fn
        self._append_bbs_post_fn = append_bbs_post_fn
        self._get_delivery_state_fn = get_delivery_state_fn
        self._now_unix_fn = now_unix_fn
        self._send_spacing_seconds = max(0.0, float(send_spacing_seconds))
        self._subscriber_ttl_seconds = max(60, int(subscriber_ttl_seconds))
        self._delivery_wait_timeout_seconds = max(0.0, float(delivery_wait_timeout_seconds))
        self._delivery_poll_seconds = max(0.01, float(delivery_poll_seconds))
        self._max_send_attempts = max(1, int(max_send_attempts))
        self._retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))
        self._enabled = False
        self._channel_index = 0
        self._started_unix = 0
        self._settings_cache = _normalize_bbs_settings({})
        self._posts_cache: list[dict[str, object]] = []
        self._subscribers_by_id: dict[str, dict[str, int]] = {}
        self._snapshot_sessions_by_id: dict[str, dict[str, object]] = {}
        self._outbound_queue: deque[dict[str, object]] = deque()
        self._outbound_sending = False
        self._outbound_shutdown = False
        self._outbound_next_send_monotonic = 0.0
        self._outbound_thread = threading.Thread(
            target=self._outbound_loop,
            name="bbs-host-send",
            daemon=True,
        )
        self._outbound_thread.start()

    def _load_settings(self) -> dict[str, object]:
        getter = self._get_bbs_settings_fn
        if callable(getter):
            try:
                payload = getter()
            except Exception:
                payload = None
            if isinstance(payload, Mapping):
                raw_settings = payload.get("settings", payload)
                normalized = _normalize_bbs_settings(raw_settings)
                with self._lock:
                    self._settings_cache = dict(normalized)
                return normalized
        with self._lock:
            return dict(self._settings_cache)

    def _save_settings(self, request: object | None) -> dict[str, object]:
        normalized = _normalize_request_settings(request)
        setter = self._set_bbs_settings_fn
        if callable(setter):
            response = setter(
                {
                    "title": normalized["title"],
                    "board_id": normalized["board_id"],
                    "motd": normalized["motd"],
                }
            )
            if isinstance(response, Mapping):
                raw_settings = response.get("settings", response)
                normalized = _normalize_bbs_settings(raw_settings)
        with self._lock:
            self._settings_cache = dict(normalized)
        return normalized

    def _persist_runtime_state(
        self,
        *,
        enabled: bool,
        channel_index: int,
        started_unix: int,
    ) -> None:
        setter = self._set_bbs_settings_fn
        if not callable(setter):
            return
        settings = self._load_settings()
        payload = {
            "title": settings["title"],
            "board_id": settings["board_id"],
            "motd": settings["motd"],
            "enabled": bool(enabled),
            "channel_index": _normalize_channel_index(channel_index),
            "started_unix": _positive_unix(started_unix) if enabled else 0,
        }
        try:
            response = setter(payload)
        except Exception:
            return
        if isinstance(response, Mapping):
            raw_settings = response.get("settings", response)
            normalized = _normalize_bbs_settings(raw_settings)
            with self._lock:
                self._settings_cache = dict(normalized)

    def restore_persisted_runtime(self) -> dict[str, object]:
        settings = self._load_settings()
        if not _coerce_bbs_enabled(settings.get("enabled")):
            return self.get_runtime()
        local_id = _normalize_node_id_text(self._local_node_id_fn())
        if not _is_canonical_node_id(local_id):
            return self.get_runtime()
        channel_index = _normalize_channel_index(settings.get("channel_index"))
        started_unix = _positive_unix(settings.get("started_unix")) or int(self._now_unix_fn())
        with self._lock:
            self._enabled = True
            self._channel_index = channel_index
            self._started_unix = started_unix
        return self.get_runtime()

    def _load_posts(self) -> list[dict[str, object]]:
        getter = self._get_bbs_posts_fn
        if callable(getter):
            try:
                payload = getter()
            except Exception:
                payload = None
            if isinstance(payload, Mapping):
                source = payload.get("posts", payload)
                if isinstance(source, list):
                    rows = [_normalize_post_payload(row) for row in source]
                    normalized = [row for row in rows if row]
                    with self._lock:
                        self._posts_cache = list(normalized)
                    return list(normalized)
        with self._lock:
            return list(self._posts_cache)

    def _append_post(self, post: object) -> dict[str, object]:
        normalized = _normalize_post_payload(post)
        if normalized is None:
            raise ValueError("BBS post text is required")
        setter = self._append_bbs_post_fn
        if callable(setter):
            response = setter(normalized)
            if isinstance(response, Mapping):
                payload_post = response.get("post", normalized)
                loaded_post = _normalize_post_payload(payload_post)
                if loaded_post:
                    normalized = loaded_post
                payload_posts = response.get("posts")
                if isinstance(payload_posts, list):
                    normalized_posts = [_normalize_post_payload(row) for row in payload_posts]
                    with self._lock:
                        self._posts_cache = [row for row in normalized_posts if row]
                    return dict(normalized)
        with self._lock:
            rows = list(self._posts_cache)
            entry_id = str(normalized.get("entry_id") or "").strip()
            if not any(str(row.get("entry_id") or "").strip() == entry_id for row in rows):
                rows.append(normalized)
            rows.sort(key=lambda row: (int(row.get("unix") or 0), str(row.get("entry_id") or "")))
            self._posts_cache = rows[-260:]
        return dict(normalized)

    def _status_payload(self) -> dict[str, object]:
        settings = self._load_settings()
        local_id = _normalize_node_id_text(self._local_node_id_fn())
        with self._lock:
            enabled = bool(self._enabled)
            started_unix = int(self._started_unix)
            channel_index = int(self._channel_index)
        return {
            "enabled": enabled,
            "title": settings["title"],
            "board_id": settings["board_id"],
            "motd": settings["motd"],
            "started_unix": started_unix if enabled else 0,
            "channel_index": channel_index,
            "host_id": local_id if _is_canonical_node_id(local_id) else "",
        }

    def _remember_subscriber(
        self,
        subscriber_id: object,
        *,
        channel_index: object,
        now_unix: int | None = None,
    ) -> None:
        clean_id = _normalize_node_id_text(subscriber_id)
        if not _is_canonical_node_id(clean_id):
            return
        seen_unix = max(0, int(self._now_unix_fn() if now_unix is None else now_unix))
        normalized_channel = _normalize_channel_index(channel_index)
        with self._lock:
            self._subscribers_by_id[clean_id] = {
                "channel_index": normalized_channel,
                "last_seen_unix": seen_unix,
            }
            if len(self._subscribers_by_id) > _BBS_MAX_SUBSCRIBERS:
                ordered = sorted(
                    self._subscribers_by_id.items(),
                    key=lambda item: int(item[1].get("last_seen_unix") or 0),
                )
                while len(ordered) > _BBS_MAX_SUBSCRIBERS:
                    stale_id, _ = ordered.pop(0)
                    self._subscribers_by_id.pop(stale_id, None)

    def _active_subscribers(self, *, now_unix: int | None = None) -> list[tuple[str, int]]:
        seen_unix = max(0, int(self._now_unix_fn() if now_unix is None else now_unix))
        min_seen = seen_unix - self._subscriber_ttl_seconds
        with self._lock:
            stale_ids = [
                node_id
                for node_id, meta in self._subscribers_by_id.items()
                if int(meta.get("last_seen_unix") or 0) < min_seen
            ]
            for node_id in stale_ids:
                self._subscribers_by_id.pop(node_id, None)
            return [
                (
                    node_id,
                    _normalize_channel_index(meta.get("channel_index")),
                )
                for node_id, meta in self._subscribers_by_id.items()
            ]

    def get_runtime(self) -> dict[str, object]:
        return {
            "ok": True,
            "host": self._status_payload(),
            "posts": self._load_posts(),
        }

    def start(self, request: object | None = None) -> dict[str, object]:
        if request is not None:
            self._save_settings(request)
        local_id = _normalize_node_id_text(self._local_node_id_fn())
        if not _is_canonical_node_id(local_id):
            return {
                "ok": False,
                "error": "Local node ID is unavailable. Wait for sync and try again.",
            }
        next_channel = _normalize_channel_index(
            getattr(request, "channel_index", None),
            fallback=self._status_payload().get("channel_index", 0),
        )
        now_unix = int(self._now_unix_fn())
        with self._lock:
            if not self._enabled or self._started_unix <= 0:
                self._started_unix = now_unix
            self._enabled = True
            self._channel_index = next_channel
            started_unix = int(self._started_unix)
        self._persist_runtime_state(
            enabled=True,
            channel_index=next_channel,
            started_unix=started_unix,
        )
        response = self.get_runtime()
        response["message"] = "BBS host is online."
        return response

    def stop(self) -> dict[str, object]:
        with self._lock:
            channel_index = int(self._channel_index)
            self._enabled = False
            self._started_unix = 0
            self._subscribers_by_id = {}
            self._snapshot_sessions_by_id = {}
        self._persist_runtime_state(
            enabled=False,
            channel_index=channel_index,
            started_unix=0,
        )
        response = self.get_runtime()
        response["message"] = "BBS host is offline."
        return response

    def append_post(self, request: object) -> dict[str, object]:
        with self._lock:
            enabled = bool(self._enabled)
        if not enabled:
            return {
                "ok": False,
                "error": "BBS host is offline.",
            }
        local_id = _normalize_node_id_text(self._local_node_id_fn())
        if not _is_canonical_node_id(local_id):
            return {
                "ok": False,
                "error": "Local node ID is unavailable. Wait for sync and try again.",
            }
        now_unix = int(self._now_unix_fn())
        post = _normalize_post_payload(
            {
                "entry_id": getattr(request, "entry_id", None),
                "author_id": local_id,
                "author_name": getattr(request, "author_name", None),
                "text": getattr(request, "text", None),
                "unix": now_unix,
            }
        )
        if post is None:
            return {
                "ok": False,
                "error": "BBS post text is required.",
            }
        appended = self._append_post(post)
        self._fanout_post(appended)
        response = self.get_runtime()
        response["post"] = appended
        response["message"] = "BBS post saved."
        return response

    def _send_wire_message_now(
        self,
        *,
        text: str,
        destination: str,
        channel_index: int,
        wait_delivery: bool = True,
    ) -> str:
        payload = str(text or "").strip()
        if not payload:
            return "invalid"
        last_outcome = "send_error"
        for attempt in range(self._max_send_attempts):
            if attempt > 0 and self._retry_backoff_seconds > 0:
                time.sleep(self._retry_backoff_seconds)
            try:
                response = self._send_chat_fn(
                    text=payload,
                    destination=destination,
                    channel_index=channel_index,
                )
            except Exception:
                last_outcome = "send_error"
                continue
            if isinstance(response, Mapping) and response.get("ok") is False:
                last_outcome = str(response.get("error") or "send_error")
                continue
            message_id = None
            if isinstance(response, Mapping):
                message_id = response.get("message_id", response.get("messageId"))
            if not wait_delivery:
                return "sent"
            last_outcome = self._wait_for_delivery_settle(message_id)
            if last_outcome in ("sent", "acked", "received", "delivered", "complete", "completed"):
                return last_outcome
        return last_outcome

    def _send_protocol_message_now(
        self,
        *,
        message_type: str,
        fields: list[object],
        destination: str,
        channel_index: int,
        wait_delivery: bool = True,
    ) -> str:
        payload = _encode_protocol_message(message_type, *fields)
        return self._send_wire_message_now(
            text=payload,
            destination=destination,
            channel_index=channel_index,
            wait_delivery=wait_delivery,
        )

    def _wait_for_delivery_settle(self, message_id: object) -> str:
        getter = self._get_delivery_state_fn
        clean_message_id = _to_int(message_id)
        if not callable(getter) or clean_message_id is None or clean_message_id <= 0:
            return "sent"
        timeout_seconds = float(self._delivery_wait_timeout_seconds)
        if timeout_seconds <= 0:
            return "sent"
        deadline = time.monotonic() + timeout_seconds
        final_states = {
            "acked",
            "received",
            "delivered",
            "complete",
            "completed",
            "timeout",
            "failed",
            "error",
            "expired",
            "rejected",
            "declined",
            "cancelled",
            "canceled",
        }
        latest_state = ""
        while time.monotonic() < deadline:
            state = ""
            try:
                current = getter(clean_message_id)
            except Exception:
                return latest_state or "send_error"
            if isinstance(current, Mapping):
                state = str(
                    current.get("delivery_state")
                    or current.get("deliveryState")
                    or current.get("state")
                    or ""
                ).strip().lower()
            else:
                state = str(current or "").strip().lower()
            latest_state = state or latest_state
            if state in final_states:
                return state
            time.sleep(self._delivery_poll_seconds)
        return latest_state or "unsettled"

    def _queue_protocol_message(
        self,
        *,
        message_type: str,
        fields: list[object],
        destination: str,
        channel_index: int,
        wait_delivery: bool = True,
    ) -> None:
        clean_destination = _normalize_node_id_text(destination)
        if not _is_canonical_node_id(clean_destination):
            return
        payload = {
            "message_type": str(message_type or "").strip().lower(),
            "fields": list(fields or []),
            "destination": clean_destination,
            "channel_index": _normalize_channel_index(channel_index),
            "wait_delivery": bool(wait_delivery),
        }
        if not payload["message_type"]:
            return
        with self._send_cond:
            self._outbound_queue.append(payload)
            self._send_cond.notify_all()

    def _queue_wire_message(
        self,
        *,
        text: str,
        destination: str,
        channel_index: int,
        wait_delivery: bool = True,
    ) -> None:
        clean_destination = _normalize_node_id_text(destination)
        clean_text = str(text or "").strip()
        if not _is_canonical_node_id(clean_destination) or not clean_text:
            return
        payload = {
            "text": clean_text,
            "destination": clean_destination,
            "channel_index": _normalize_channel_index(channel_index),
            "wait_delivery": bool(wait_delivery),
        }
        with self._send_cond:
            self._outbound_queue.append(payload)
            self._send_cond.notify_all()

    def _queue_history_snapshot(
        self,
        *,
        destination: str,
        channel_index: int,
        request_token: str,
        requested_board_id: object = "",
        since_unix: object = 0,
        tail_entry_id: object = "",
    ) -> None:
        settings = self._load_settings()
        local_id = _normalize_node_id_text(self._local_node_id_fn())
        if not _is_canonical_node_id(local_id):
            return
        posts = self._load_posts()
        sorted_posts = sorted(posts, key=_post_sort_key)
        latest_post = sorted_posts[-1] if sorted_posts else {}
        latest_unix = _post_sort_key(latest_post)[0] if latest_post else 0
        latest_entry_id = str(latest_post.get("entry_id") or "") if latest_post else ""
        self._queue_protocol_message(
            message_type="profile",
            fields=[
                request_token,
                settings["board_id"],
                local_id,
                settings["title"],
                settings["motd"],
                len(sorted_posts),
                latest_unix,
                latest_entry_id,
            ],
            destination=destination,
            channel_index=channel_index,
            wait_delivery=False,
        )
        reply_posts = _posts_after_cursor(
            sorted_posts,
            current_board_id=settings["board_id"],
            requested_board_id=requested_board_id,
            since_unix=since_unix,
            tail_entry_id=tail_entry_id,
        )
        snapshot = _build_bbs_snapshot_file_frames(
            request_token=request_token,
            settings=settings,
            host_id=local_id,
            posts=reply_posts,
            total_post_count=len(sorted_posts),
            latest_unix=latest_unix,
            latest_entry_id=latest_entry_id,
        )
        if snapshot:
            transfer_id = str(snapshot.get("transfer_id") or "").strip().lower()
            chunk_frames = [
                str(frame or "").strip()
                for frame in snapshot.get("chunk_frames", [])
                if str(frame or "").strip()
            ]
            meta_frame = str(snapshot.get("meta_frame") or "").strip()
            if transfer_id and meta_frame and chunk_frames:
                with self._lock:
                    self._snapshot_sessions_by_id[transfer_id] = {
                        "destination": _normalize_node_id_text(destination),
                        "channel_index": _normalize_channel_index(channel_index),
                        "meta_frame": meta_frame,
                        "chunk_frames": list(chunk_frames),
                        "resend_count": 0,
                    }
                self._queue_wire_message(
                    text=meta_frame,
                    destination=destination,
                    channel_index=channel_index,
                    wait_delivery=False,
                )
                for frame in chunk_frames:
                    self._queue_wire_message(
                        text=frame,
                        destination=destination,
                        channel_index=channel_index,
                        wait_delivery=False,
                    )
                return
        for message in _queueable_history_messages(
            board_id=settings["board_id"],
            host_id=local_id,
            posts=reply_posts,
        ):
            self._queue_wire_message(
                text=message,
                destination=destination,
                channel_index=channel_index,
                wait_delivery=False,
            )

    def _handle_snapshot_ack(self, sender_id: str, ack: Mapping[str, object]) -> None:
        transfer_id = str(ack.get("transfer_id") or "").strip().lower()
        if not transfer_id:
            return
        received_indexes_raw = ack.get("received_indexes")
        received_indexes = (
            set(received_indexes_raw)
            if isinstance(received_indexes_raw, set)
            else set()
        )
        try:
            total_chunks = max(1, int(ack.get("total_chunks") or 1))
            received_count = max(0, int(ack.get("received_count") or 0))
        except Exception:
            return
        resend_frames: list[str] = []
        destination = _normalize_node_id_text(sender_id)
        channel_index = 0
        meta_frame = ""
        with self._lock:
            session = self._snapshot_sessions_by_id.get(transfer_id)
            if not isinstance(session, dict):
                return
            session_destination = _normalize_node_id_text(session.get("destination"))
            if session_destination != destination:
                return
            chunk_frames = list(session.get("chunk_frames") or [])
            if total_chunks != len(chunk_frames):
                return
            if received_count >= total_chunks or len(received_indexes) >= total_chunks:
                self._snapshot_sessions_by_id.pop(transfer_id, None)
                return
            resend_count = int(session.get("resend_count") or 0)
            if resend_count >= _BBS_SNAPSHOT_MAX_RESENDS:
                self._snapshot_sessions_by_id.pop(transfer_id, None)
                return
            session["resend_count"] = resend_count + 1
            channel_index = _normalize_channel_index(session.get("channel_index"))
            meta_frame = str(session.get("meta_frame") or "").strip()
            missing_indexes = [
                idx
                for idx in range(len(chunk_frames))
                if idx not in received_indexes
            ]
            resend_frames = [
                str(chunk_frames[idx] or "").strip()
                for idx in missing_indexes
                if str(chunk_frames[idx] or "").strip()
            ]
        if meta_frame:
            self._queue_wire_message(
                text=meta_frame,
                destination=destination,
                channel_index=channel_index,
                wait_delivery=False,
            )
        for frame in resend_frames:
            self._queue_wire_message(
                text=frame,
                destination=destination,
                channel_index=channel_index,
                wait_delivery=False,
            )

    def _fanout_post(self, post: Mapping[str, object]) -> None:
        settings = self._load_settings()
        local_id = _normalize_node_id_text(self._local_node_id_fn())
        if not _is_canonical_node_id(local_id):
            return
        subscribers = self._active_subscribers()
        if not subscribers:
            return
        fields = [
            settings["board_id"],
            local_id,
            post.get("entry_id"),
            post.get("author_id"),
            post.get("author_name"),
            post.get("text"),
            post.get("unix"),
        ]
        for destination, channel_index in subscribers:
            self._queue_protocol_message(
                message_type="post",
                fields=fields,
                destination=destination,
                channel_index=channel_index,
            )

    def _outbound_loop(self) -> None:
        while True:
            with self._send_cond:
                while not self._outbound_shutdown and not self._outbound_queue:
                    self._outbound_sending = False
                    self._send_cond.notify_all()
                    self._send_cond.wait()
                if self._outbound_shutdown:
                    self._outbound_sending = False
                    self._send_cond.notify_all()
                    return
                payload = self._outbound_queue.popleft()
                self._outbound_sending = True
                spacing_seconds = self._send_spacing_seconds
                next_send_monotonic = float(self._outbound_next_send_monotonic)
            if spacing_seconds > 0:
                sleep_seconds = next_send_monotonic - time.monotonic()
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
            wait_delivery = bool(payload.get("wait_delivery", True))
            raw_text = str(payload.get("text") or "").strip()
            if raw_text:
                self._send_wire_message_now(
                    text=raw_text,
                    destination=str(payload.get("destination") or ""),
                    channel_index=_normalize_channel_index(payload.get("channel_index")),
                    wait_delivery=wait_delivery,
                )
            else:
                self._send_protocol_message_now(
                    message_type=str(payload.get("message_type") or ""),
                    fields=list(payload.get("fields") or []),
                    destination=str(payload.get("destination") or ""),
                    channel_index=_normalize_channel_index(payload.get("channel_index")),
                    wait_delivery=wait_delivery,
                )
            with self._send_cond:
                self._outbound_next_send_monotonic = time.monotonic() + max(0.0, spacing_seconds)
                if not self._outbound_queue:
                    self._outbound_sending = False
                self._send_cond.notify_all()

    def wait_for_idle(self, timeout_seconds: float = 1.0) -> bool:
        deadline = time.monotonic() + max(0.01, float(timeout_seconds))
        with self._send_cond:
            while self._outbound_sending or self._outbound_queue:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._send_cond.wait(timeout=remaining)
        return True

    def on_receive(self, packet: object, interface: object | None = None) -> None:
        packet_text = _extract_packet_text(packet)
        parsed = _parse_protocol_message(packet_text)
        file_ack = _parse_file_transfer_ack(packet_text)
        if parsed is None and file_ack is None:
            return
        if not isinstance(packet, Mapping):
            return
        with self._lock:
            enabled = bool(self._enabled)
            fallback_channel = int(self._channel_index)
        if not enabled:
            return
        local_num = _get_local_node_num(interface) if interface is not None else None
        packet_to = _to_int(packet.get("to"))
        if local_num is None or packet_to is None or packet_to != int(local_num):
            return
        sender_num = _to_int(packet.get("from"))
        if sender_num is None:
            return
        nodes_by_num = getattr(interface, "nodesByNum", None) if interface is not None else None
        sender_user = {}
        if isinstance(nodes_by_num, dict):
            sender_info = nodes_by_num.get(sender_num, {})
            if isinstance(sender_info, Mapping):
                sender_user = sender_info.get("user", {}) if isinstance(sender_info.get("user"), Mapping) else {}
        sender_id = _normalize_node_id_text(sender_user.get("id") if isinstance(sender_user, Mapping) else "")
        if not _is_canonical_node_id(sender_id):
            sender_id = f"!{int(sender_num):08x}"
        local_id = _normalize_node_id_text(self._local_node_id_fn())
        if not _is_canonical_node_id(local_id):
            return
        if file_ack is not None:
            self._handle_snapshot_ack(sender_id, file_ack)
            if parsed is None:
                return
        if parsed is None:
            return
        message_type, parts = parsed
        settings = self._load_settings()
        reply_channel = _normalize_channel_index(packet.get("channel"), fallback=fallback_channel)
        if message_type == "open":
            request_token = _sanitize_bbs_text(parts[2] if len(parts) > 2 else "", 40)
            if not request_token:
                return
            requested_board_id = _normalize_bbs_board_id(parts[3] if len(parts) > 3 else "")
            since_unix = _to_int(parts[4] if len(parts) > 4 else 0) or 0
            tail_entry_id = _sanitize_bbs_text(parts[5] if len(parts) > 5 else "", 60)
            self._remember_subscriber(
                sender_id,
                channel_index=reply_channel,
                now_unix=int(self._now_unix_fn()),
            )
            self._queue_history_snapshot(
                destination=sender_id,
                channel_index=reply_channel,
                request_token=request_token,
                requested_board_id=requested_board_id,
                since_unix=since_unix,
                tail_entry_id=tail_entry_id,
            )
            return
        if message_type != "post":
            return
        board_id = _normalize_bbs_board_id(parts[2] if len(parts) > 2 else "")
        host_id = _normalize_node_id_text(parts[3] if len(parts) > 3 else "")
        if not board_id or board_id != str(settings.get("board_id") or ""):
            return
        if host_id != local_id:
            return
        post = _normalize_post_payload(
            {
                "entry_id": parts[4] if len(parts) > 4 else "",
                "author_id": parts[5] if len(parts) > 5 else sender_id,
                "author_name": parts[6] if len(parts) > 6 else sender_id,
                "text": parts[7] if len(parts) > 7 else "",
                "unix": int(self._now_unix_fn()),
            }
        )
        if post is None:
            return
        try:
            appended = self._append_post(post)
        except Exception:
            return
        self._remember_subscriber(
            sender_id,
            channel_index=reply_channel,
            now_unix=int(self._now_unix_fn()),
        )
        self._fanout_post(appended)


def build_bbs_host_service(**kwargs: object) -> BbsHostService:
    return BbsHostService(**kwargs)


__all__ = [
    "BbsHostService",
    "build_bbs_host_service",
]
