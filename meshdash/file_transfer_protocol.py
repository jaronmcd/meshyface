import base64
import re
import urllib.parse

from .config import (
    DEFAULT_CHAT_MAX_BYTES,
    MAX_FILE_TRANSFER_MAX_BYTES,
)


FILE_TRANSFER_PROTOCOL_NAME = "MF_FILE_V1"
FILE_TRANSFER_PROTOCOL_PREFIX = f"{FILE_TRANSFER_PROTOCOL_NAME}|"
FILE_TRANSFER_CHUNK_BYTES = 64
FILE_TRANSFER_MAX_FILE_BYTES = int(MAX_FILE_TRANSFER_MAX_BYTES)
FILE_TRANSFER_MAX_CHUNKS = max(
    1,
    (FILE_TRANSFER_MAX_FILE_BYTES + FILE_TRANSFER_CHUNK_BYTES - 1)
    // FILE_TRANSFER_CHUNK_BYTES,
)
_FILE_TRANSFER_FRAME_TYPES = {"M", "C", "A", "F"}
_TRANSFER_ID_RE = re.compile(r"^[a-z0-9]{4,24}$")
_BASE64_RE = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")


def is_file_transfer_protocol_text(text: object) -> bool:
    if not isinstance(text, str):
        return False
    raw = text.strip()
    if not raw.startswith(FILE_TRANSFER_PROTOCOL_PREFIX):
        return False
    parts = raw.split("|", 3)
    if len(parts) < 3:
        return False
    frame_type = str(parts[1]).strip().upper()
    transfer_id = str(parts[2]).strip()
    return frame_type in _FILE_TRANSFER_FRAME_TYPES and bool(transfer_id)


def is_file_transfer_protocol_chat_entry(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    return is_file_transfer_protocol_text(entry.get("text"))


def _safe_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except Exception:
        return None


def _bounded_file_transfer_limits(
    *,
    max_file_bytes: object = FILE_TRANSFER_MAX_FILE_BYTES,
    max_total_chunks: object = None,
) -> tuple[int, int]:
    parsed_file_bytes = _safe_int(max_file_bytes)
    file_bytes = max(
        1,
        min(
            FILE_TRANSFER_MAX_FILE_BYTES,
            int(
                parsed_file_bytes
                if parsed_file_bytes is not None
                else FILE_TRANSFER_MAX_FILE_BYTES
            ),
        ),
    )
    derived_chunks = max(
        1,
        (file_bytes + FILE_TRANSFER_CHUNK_BYTES - 1) // FILE_TRANSFER_CHUNK_BYTES,
    )
    parsed_chunks = _safe_int(max_total_chunks)
    if parsed_chunks is not None:
        derived_chunks = max(1, min(derived_chunks, int(parsed_chunks)))
    return file_bytes, derived_chunks


def _decode_bounded_base64(value: str, *, max_decoded_bytes: int) -> bytes | None:
    if not value or len(value) > 4 * ((max(0, int(max_decoded_bytes)) + 2) // 3):
        return None
    if not _BASE64_RE.fullmatch(value):
        return None
    try:
        decoded = base64.b64decode(value, validate=True)
    except Exception:
        return None
    if not decoded or len(decoded) > max(0, int(max_decoded_bytes)):
        return None
    return decoded


def parse_file_transfer_frame_text(
    text: object,
    *,
    max_file_bytes: object = FILE_TRANSFER_MAX_FILE_BYTES,
    max_total_chunks: object = None,
    max_frame_bytes: object = DEFAULT_CHAT_MAX_BYTES,
) -> dict[str, object] | None:
    raw = str(text or "").strip()
    if not raw.startswith(FILE_TRANSFER_PROTOCOL_PREFIX):
        return None
    parsed_frame_bytes = _safe_int(max_frame_bytes)
    frame_bytes = max(
        1,
        int(parsed_frame_bytes if parsed_frame_bytes is not None else DEFAULT_CHAT_MAX_BYTES),
    )
    if len(raw.encode("utf-8")) > frame_bytes:
        return None
    file_byte_limit, chunk_limit = _bounded_file_transfer_limits(
        max_file_bytes=max_file_bytes,
        max_total_chunks=max_total_chunks,
    )
    parts = raw.split("|")
    if len(parts) < 4:
        return None
    frame_type = str(parts[1] or "").strip().upper()
    transfer_id = str(parts[2] or "").strip().lower()
    if not _TRANSFER_ID_RE.fullmatch(transfer_id):
        return None

    if frame_type == "M":
        if len(parts) < 6 or len(parts) > 8:
            return None
        file_size = _safe_int(parts[4])
        total_chunks = _safe_int(parts[5])
        if file_size is None or file_size <= 0 or file_size > file_byte_limit:
            return None
        if total_chunks is None or total_chunks <= 0 or total_chunks > chunk_limit:
            return None
        codec = str(parts[6] if len(parts) >= 7 else "raw").strip().lower() or "raw"
        if codec not in {"raw", "lzss"}:
            return None
        original_size = _safe_int(parts[7] if len(parts) >= 8 else file_size)
        if original_size is None or original_size <= 0 or original_size > file_byte_limit:
            return None
        expected_chunks = max(
            1,
            (int(file_size) + FILE_TRANSFER_CHUNK_BYTES - 1)
            // FILE_TRANSFER_CHUNK_BYTES,
        )
        if int(total_chunks) != expected_chunks:
            return None
        if codec == "raw" and int(original_size) != int(file_size):
            return None
        if codec == "lzss" and int(original_size) < int(file_size):
            return None
        return {
            "kind": "meta",
            "transfer_id": transfer_id,
            "file_name": urllib.parse.unquote(str(parts[3] or "").strip()),
            "file_size": int(file_size),
            "total_chunks": int(total_chunks),
            "codec": codec,
            "original_file_size": int(original_size),
        }

    if frame_type == "C":
        if len(parts) != 5:
            return None
        chunk_index = _safe_int(parts[3])
        chunk_data = str(parts[4] or "").strip()
        if chunk_index is None or chunk_index < 0 or chunk_index >= chunk_limit:
            return None
        if _decode_bounded_base64(
            chunk_data,
            max_decoded_bytes=FILE_TRANSFER_CHUNK_BYTES,
        ) is None:
            return None
        return {
            "kind": "chunk",
            "transfer_id": transfer_id,
            "chunk_index": int(chunk_index),
            "chunk_data": chunk_data,
        }

    if frame_type == "A":
        if len(parts) != 6:
            return None
        received_count = _safe_int(parts[3])
        total_chunks = _safe_int(parts[4])
        bitmap = str(parts[5] or "").strip()
        if received_count is None or received_count < 0:
            return None
        if total_chunks is None or total_chunks <= 0 or total_chunks > chunk_limit:
            return None
        if received_count > total_chunks:
            return None
        if _decode_bounded_base64(
            bitmap,
            max_decoded_bytes=max(1, (int(total_chunks) + 7) // 8),
        ) is None:
            return None
        return {
            "kind": "ack",
            "transfer_id": transfer_id,
            "received_count": int(received_count),
            "total_chunks": int(total_chunks),
            "bitmap": bitmap,
        }

    if frame_type == "F":
        if len(parts) != 4:
            return None
        action_code = str(parts[3] or "").strip().upper()
        action = {"P": "pause", "R": "resume", "X": "cancel"}.get(action_code, "")
        if not action:
            return None
        return {
            "kind": "flow",
            "transfer_id": transfer_id,
            "action": action,
        }

    return None


def build_file_transfer_ack_frame(
    *,
    transfer_id: object,
    total_chunks: object,
    received_indexes: object = None,
    max_total_chunks: object = FILE_TRANSFER_MAX_CHUNKS,
    max_frame_bytes: object = DEFAULT_CHAT_MAX_BYTES,
) -> str:
    clean_id = str(transfer_id or "").strip().lower()
    if not _TRANSFER_ID_RE.fullmatch(clean_id):
        return ""
    parsed_total = _safe_int(total_chunks)
    _file_byte_limit, chunk_limit = _bounded_file_transfer_limits(
        max_total_chunks=max_total_chunks,
    )
    if parsed_total is None or parsed_total <= 0 or parsed_total > chunk_limit:
        return ""
    total = int(parsed_total)
    parsed_frame_bytes = _safe_int(max_frame_bytes)
    frame_byte_limit = max(
        1,
        int(parsed_frame_bytes if parsed_frame_bytes is not None else DEFAULT_CHAT_MAX_BYTES),
    )
    source = received_indexes if received_indexes is not None else ()
    indexes: set[int] = set()
    try:
        iterator = iter(source)  # type: ignore[arg-type]
    except Exception:
        iterator = iter(())
    for idx_raw in iterator:
        idx = _safe_int(idx_raw)
        if idx is None or idx < 0 or idx >= total:
            continue
        indexes.add(int(idx))
        if len(indexes) >= total:
            break
    if len(indexes) >= total:
        # The count is authoritative for completion. Keep the final ACK small enough
        # to fit in one chat frame even for transfers with many chunks.
        bitmap = bytearray(1)
    else:
        max_index = max(indexes) if indexes else 0
        byte_len = max(1, (max_index // 8) + 1)
        frame_prefix = (
            f"{FILE_TRANSFER_PROTOCOL_NAME}|A|{clean_id}|"
            f"{len(indexes)}|{total}|"
        )
        encoded_len = 4 * ((byte_len + 2) // 3)
        if len(frame_prefix.encode("utf-8")) + encoded_len > frame_byte_limit:
            return ""
        bitmap = bytearray(byte_len)
        for idx in indexes:
            bitmap[idx // 8] |= 1 << (idx % 8)
    encoded = base64.b64encode(bytes(bitmap)).decode("ascii")
    frame = f"{FILE_TRANSFER_PROTOCOL_NAME}|A|{clean_id}|{len(indexes)}|{total}|{encoded}"
    if len(frame.encode("utf-8")) > frame_byte_limit:
        return ""
    return frame


__all__ = [
    "FILE_TRANSFER_PROTOCOL_NAME",
    "FILE_TRANSFER_PROTOCOL_PREFIX",
    "FILE_TRANSFER_CHUNK_BYTES",
    "FILE_TRANSFER_MAX_CHUNKS",
    "FILE_TRANSFER_MAX_FILE_BYTES",
    "build_file_transfer_ack_frame",
    "is_file_transfer_protocol_chat_entry",
    "is_file_transfer_protocol_text",
    "parse_file_transfer_frame_text",
]
