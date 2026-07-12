import base64
import re
import struct
import urllib.parse
from collections.abc import Mapping

from .config import MAX_FILE_TRANSFER_MAX_BYTES


FILE_TRANSFER_PROTOCOL_NAME = "MF_FILE_V2"
FILE_TRANSFER_PROTOCOL_PREFIX = f"{FILE_TRANSFER_PROTOCOL_NAME}|"
FILE_TRANSFER_PORTNUM = 258
FILE_TRANSFER_CHUNK_BYTES = 160
FILE_TRANSFER_MAX_WIRE_BYTES = 233
FILE_TRANSFER_MAX_FILE_BYTES = int(MAX_FILE_TRANSFER_MAX_BYTES)
FILE_TRANSFER_MAX_CHUNKS = max(
    1,
    (FILE_TRANSFER_MAX_FILE_BYTES + FILE_TRANSFER_CHUNK_BYTES - 1)
    // FILE_TRANSFER_CHUNK_BYTES,
)

_WIRE_MAGIC = b"MF2"
_FRAME_TYPES = {"M", "C", "A", "F"}
_TRANSFER_ID_RE = re.compile(r"^[a-z0-9]{4,24}$")
_BASE64_RE = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
_CODEC_TO_BYTE = {"raw": 0, "lzss": 1}
_BYTE_TO_CODEC = {value: key for key, value in _CODEC_TO_BYTE.items()}
_ACTION_TO_BYTE = {"pause": 0, "resume": 1, "cancel": 2}
_BYTE_TO_ACTION = {value: key for key, value in _ACTION_TO_BYTE.items()}


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


def _clean_transfer_id(value: object) -> str:
    clean = str(value or "").strip().lower()
    return clean if _TRANSFER_ID_RE.fullmatch(clean) else ""


def _wire_prefix(frame_type: str, transfer_id: str) -> bytes:
    encoded_id = transfer_id.encode("ascii")
    return _WIRE_MAGIC + frame_type.encode("ascii") + bytes((len(encoded_id),)) + encoded_id


def is_file_transfer_protocol_text(text: object) -> bool:
    return parse_file_transfer_frame_text(text) is not None


def is_file_transfer_protocol_chat_entry(entry: object) -> bool:
    return isinstance(entry, dict) and is_file_transfer_protocol_text(entry.get("text"))


def parse_file_transfer_frame_text(
    text: object,
    *,
    max_file_bytes: object = FILE_TRANSFER_MAX_FILE_BYTES,
    max_total_chunks: object = None,
    max_frame_bytes: object = 1024,
) -> dict[str, object] | None:
    raw = str(text or "").strip()
    if not raw.startswith(FILE_TRANSFER_PROTOCOL_PREFIX):
        return None
    parsed_frame_bytes = _safe_int(max_frame_bytes)
    frame_bytes = max(1, int(parsed_frame_bytes if parsed_frame_bytes is not None else 1024))
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
    transfer_id = _clean_transfer_id(parts[2])
    if not transfer_id:
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
        if codec not in _CODEC_TO_BYTE:
            return None
        original_size = _safe_int(parts[7] if len(parts) >= 8 else file_size)
        if original_size is None or original_size <= 0 or original_size > file_byte_limit:
            return None
        expected_chunks = max(1, (int(file_size) + FILE_TRANSFER_CHUNK_BYTES - 1) // FILE_TRANSFER_CHUNK_BYTES)
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
        decoded = _decode_bounded_base64(chunk_data, max_decoded_bytes=FILE_TRANSFER_CHUNK_BYTES)
        if chunk_index is None or chunk_index < 0 or chunk_index >= chunk_limit or decoded is None:
            return None
        return {
            "kind": "chunk",
            "transfer_id": transfer_id,
            "chunk_index": int(chunk_index),
            "chunk_data": chunk_data,
            "chunk_bytes": decoded,
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
        decoded = _decode_bounded_base64(bitmap, max_decoded_bytes=max(1, (int(total_chunks) + 7) // 8))
        if decoded is None:
            return None
        return {
            "kind": "ack",
            "transfer_id": transfer_id,
            "received_count": int(received_count),
            "total_chunks": int(total_chunks),
            "bitmap": bitmap,
            "bitmap_bytes": decoded,
        }

    if frame_type == "F":
        if len(parts) != 4:
            return None
        action = {"P": "pause", "R": "resume", "X": "cancel"}.get(str(parts[3] or "").strip().upper(), "")
        if not action:
            return None
        return {"kind": "flow", "transfer_id": transfer_id, "action": action}
    return None


def encode_file_transfer_frame(frame: Mapping[str, object]) -> bytes:
    kind = str(frame.get("kind") or "").strip().lower()
    transfer_id = _clean_transfer_id(frame.get("transfer_id"))
    frame_type = {"meta": "M", "chunk": "C", "ack": "A", "flow": "F"}.get(kind, "")
    if not frame_type or not transfer_id:
        raise ValueError("invalid MF_FILE_V2 frame")
    prefix = _wire_prefix(frame_type, transfer_id)
    if kind == "meta":
        file_size = _safe_int(frame.get("file_size"))
        original_size = _safe_int(frame.get("original_file_size"))
        total_chunks = _safe_int(frame.get("total_chunks"))
        codec = str(frame.get("codec") or "raw").strip().lower()
        if file_size is None or original_size is None or total_chunks is None or codec not in _CODEC_TO_BYTE:
            raise ValueError("invalid MF_FILE_V2 metadata")
        file_name = str(frame.get("file_name") or "").encode("utf-8")
        payload = prefix + struct.pack(">IIHB", file_size, original_size, total_chunks, _CODEC_TO_BYTE[codec]) + file_name
    elif kind == "chunk":
        chunk_index = _safe_int(frame.get("chunk_index"))
        chunk_bytes = frame.get("chunk_bytes")
        if not isinstance(chunk_bytes, (bytes, bytearray, memoryview)):
            chunk_bytes = _decode_bounded_base64(str(frame.get("chunk_data") or ""), max_decoded_bytes=FILE_TRANSFER_CHUNK_BYTES)
        if chunk_index is None or chunk_index < 0 or chunk_bytes is None:
            raise ValueError("invalid MF_FILE_V2 chunk")
        payload = prefix + struct.pack(">H", chunk_index) + bytes(chunk_bytes)
    elif kind == "ack":
        received_count = _safe_int(frame.get("received_count"))
        total_chunks = _safe_int(frame.get("total_chunks"))
        bitmap_bytes = frame.get("bitmap_bytes")
        if not isinstance(bitmap_bytes, (bytes, bytearray, memoryview)):
            bitmap_bytes = _decode_bounded_base64(str(frame.get("bitmap") or ""), max_decoded_bytes=max(1, ((total_chunks or 0) + 7) // 8))
        if received_count is None or total_chunks is None or bitmap_bytes is None:
            raise ValueError("invalid MF_FILE_V2 acknowledgement")
        payload = prefix + struct.pack(">HH", received_count, total_chunks) + bytes(bitmap_bytes)
    else:
        action = str(frame.get("action") or "").strip().lower()
        if action not in _ACTION_TO_BYTE:
            raise ValueError("invalid MF_FILE_V2 flow action")
        payload = prefix + bytes((_ACTION_TO_BYTE[action],))
    if len(payload) > FILE_TRANSFER_MAX_WIRE_BYTES:
        raise ValueError(f"MF_FILE_V2 packet exceeds {FILE_TRANSFER_MAX_WIRE_BYTES}-byte limit")
    return payload


def decode_file_transfer_payload(
    payload: object,
    *,
    max_file_bytes: object = FILE_TRANSFER_MAX_FILE_BYTES,
    max_total_chunks: object = None,
) -> dict[str, object] | None:
    if isinstance(payload, memoryview):
        payload = payload.tobytes()
    if isinstance(payload, (list, tuple)):
        try:
            payload = bytes(int(part) & 0xFF for part in payload)
        except Exception:
            return None
    if not isinstance(payload, (bytes, bytearray)):
        return None
    raw = bytes(payload)
    if len(raw) < 9 or len(raw) > FILE_TRANSFER_MAX_WIRE_BYTES or raw[:3] != _WIRE_MAGIC:
        return None
    try:
        frame_type = chr(raw[3])
    except Exception:
        return None
    id_len = raw[4]
    body_offset = 5 + id_len
    if frame_type not in _FRAME_TYPES or body_offset > len(raw):
        return None
    try:
        transfer_id = raw[5:body_offset].decode("ascii")
    except Exception:
        return None
    if not _clean_transfer_id(transfer_id):
        return None
    file_limit, chunk_limit = _bounded_file_transfer_limits(max_file_bytes=max_file_bytes, max_total_chunks=max_total_chunks)
    body = raw[body_offset:]
    if frame_type == "M":
        if len(body) < 12:
            return None
        file_size, original_size, total_chunks, codec_byte = struct.unpack(">IIHB", body[:11])
        codec = _BYTE_TO_CODEC.get(codec_byte)
        try:
            file_name = body[11:].decode("utf-8", errors="strict")
        except Exception:
            return None
        expected_chunks = max(1, (file_size + FILE_TRANSFER_CHUNK_BYTES - 1) // FILE_TRANSFER_CHUNK_BYTES)
        if not (0 < file_size <= file_limit and 0 < original_size <= file_limit and 0 < total_chunks <= chunk_limit):
            return None
        if total_chunks != expected_chunks or codec is None:
            return None
        if (codec == "raw" and original_size != file_size) or (codec == "lzss" and original_size < file_size):
            return None
        return {"kind": "meta", "transfer_id": transfer_id, "file_name": file_name, "file_size": file_size, "total_chunks": total_chunks, "codec": codec, "original_file_size": original_size}
    if frame_type == "C":
        if len(body) < 3 or len(body) > FILE_TRANSFER_CHUNK_BYTES + 2:
            return None
        chunk_index = struct.unpack(">H", body[:2])[0]
        if chunk_index >= chunk_limit:
            return None
        chunk_bytes = body[2:]
        return {"kind": "chunk", "transfer_id": transfer_id, "chunk_index": chunk_index, "chunk_data": base64.b64encode(chunk_bytes).decode("ascii"), "chunk_bytes": chunk_bytes}
    if frame_type == "A":
        if len(body) < 5:
            return None
        received_count, total_chunks = struct.unpack(">HH", body[:4])
        bitmap_bytes = body[4:]
        if not (0 < total_chunks <= chunk_limit and received_count <= total_chunks):
            return None
        if not bitmap_bytes or len(bitmap_bytes) > max(1, (total_chunks + 7) // 8):
            return None
        return {"kind": "ack", "transfer_id": transfer_id, "received_count": received_count, "total_chunks": total_chunks, "bitmap": base64.b64encode(bitmap_bytes).decode("ascii"), "bitmap_bytes": bitmap_bytes}
    if len(body) != 1 or body[0] not in _BYTE_TO_ACTION:
        return None
    return {"kind": "flow", "transfer_id": transfer_id, "action": _BYTE_TO_ACTION[body[0]]}


def file_transfer_frame_text(frame: Mapping[str, object]) -> str:
    kind = str(frame.get("kind") or "").strip().lower()
    transfer_id = _clean_transfer_id(frame.get("transfer_id"))
    if kind == "meta":
        name = urllib.parse.quote(str(frame.get("file_name") or ""), safe="._-()[]")
        return f"{FILE_TRANSFER_PROTOCOL_NAME}|M|{transfer_id}|{name}|{int(frame['file_size'])}|{int(frame['total_chunks'])}|{frame.get('codec') or 'raw'}|{int(frame['original_file_size'])}"
    if kind == "chunk":
        return f"{FILE_TRANSFER_PROTOCOL_NAME}|C|{transfer_id}|{int(frame['chunk_index'])}|{frame['chunk_data']}"
    if kind == "ack":
        return f"{FILE_TRANSFER_PROTOCOL_NAME}|A|{transfer_id}|{int(frame['received_count'])}|{int(frame['total_chunks'])}|{frame['bitmap']}"
    if kind == "flow":
        action = {"pause": "P", "resume": "R", "cancel": "X"}.get(str(frame.get("action") or "").lower(), "")
        return f"{FILE_TRANSFER_PROTOCOL_NAME}|F|{transfer_id}|{action}"
    return ""


def _portnum_matches(value: object) -> bool:
    if isinstance(value, bool):
        return False
    parsed = _safe_int(value)
    return parsed == FILE_TRANSFER_PORTNUM if parsed is not None else False


def decode_file_transfer_packet(packet: object, **kwargs: object) -> dict[str, object] | None:
    if not isinstance(packet, Mapping):
        return None
    decoded = packet.get("decoded")
    if not isinstance(decoded, Mapping) or not _portnum_matches(decoded.get("portnum")):
        return None
    return decode_file_transfer_payload(decoded.get("payload"), **kwargs)


def build_file_transfer_ack_frame(
    *,
    transfer_id: object,
    total_chunks: object,
    received_indexes: object = None,
    max_total_chunks: object = FILE_TRANSFER_MAX_CHUNKS,
    max_frame_bytes: object = 1024,
) -> str:
    clean_id = _clean_transfer_id(transfer_id)
    parsed_total = _safe_int(total_chunks)
    _file_limit, chunk_limit = _bounded_file_transfer_limits(max_total_chunks=max_total_chunks)
    if not clean_id or parsed_total is None or parsed_total <= 0 or parsed_total > chunk_limit:
        return ""
    total = int(parsed_total)
    indexes: set[int] = set()
    try:
        iterator = iter(received_indexes if received_indexes is not None else ())
    except Exception:
        iterator = iter(())
    for idx_raw in iterator:
        idx = _safe_int(idx_raw)
        if idx is not None and 0 <= idx < total:
            indexes.add(idx)
    if len(indexes) >= total:
        bitmap = bytearray(1)
    else:
        byte_len = max(1, ((max(indexes) if indexes else 0) // 8) + 1)
        bitmap = bytearray(byte_len)
        for idx in indexes:
            bitmap[idx // 8] |= 1 << (idx % 8)
    frame = {"kind": "ack", "transfer_id": clean_id, "received_count": len(indexes), "total_chunks": total, "bitmap": base64.b64encode(bytes(bitmap)).decode("ascii")}
    text = file_transfer_frame_text(frame)
    parsed_limit = _safe_int(max_frame_bytes)
    return text if len(text.encode("utf-8")) <= int(parsed_limit or 1024) else ""


__all__ = [
    "FILE_TRANSFER_PROTOCOL_NAME", "FILE_TRANSFER_PROTOCOL_PREFIX", "FILE_TRANSFER_PORTNUM",
    "FILE_TRANSFER_CHUNK_BYTES", "FILE_TRANSFER_MAX_CHUNKS", "FILE_TRANSFER_MAX_FILE_BYTES",
    "build_file_transfer_ack_frame", "decode_file_transfer_packet", "decode_file_transfer_payload",
    "encode_file_transfer_frame", "file_transfer_frame_text", "is_file_transfer_protocol_chat_entry",
    "is_file_transfer_protocol_text", "parse_file_transfer_frame_text",
]
