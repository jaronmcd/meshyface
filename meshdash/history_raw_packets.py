import json
import os
import sqlite3
import tempfile
import time
from collections.abc import Mapping
from typing import Callable

from .helpers import to_float, to_int, to_jsonable


_RAW_PACKET_SETTINGS_KEY = "raw_packet_capture_v1"
_RAW_PACKET_SETTINGS_DEFAULT = {
    "capture_enabled": False,
}


def raw_packet_db_path_for_history_db_path(history_db_path: object) -> str:
    clean_path = str(history_db_path or "").strip()
    if not clean_path:
        return ""
    if clean_path in {":memory:", "file::memory:"}:
        return clean_path
    if clean_path.startswith("file:") and "mode=memory" in clean_path:
        return ""
    root, ext = os.path.splitext(clean_path)
    if ext:
        return f"{root}.raw{ext}"
    return f"{clean_path}.raw.sqlite3"


def _file_size(path: object) -> int | None:
    clean_path = str(path or "").strip()
    if not clean_path or clean_path in {":memory:", "file::memory:"}:
        return None
    try:
        return int(os.path.getsize(clean_path))
    except Exception:
        return None


def _raw_packet_download_filename(raw_db_path: object) -> str:
    base = os.path.basename(str(raw_db_path or "").strip()) or "meshdash_raw_packets.sqlite3"
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in base).strip("._")
    if not safe:
        safe = "meshdash_raw_packets.sqlite3"
    root, ext = os.path.splitext(safe)
    if ext.lower() not in {".sqlite3", ".sqlite", ".db"}:
        ext = ".sqlite3"
    return f"{root or 'meshdash_raw_packets'}_{time.strftime('%Y%m%d_%H%M%S')}{ext}"


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "on", "enabled"}


def _normalize_raw_packet_settings(payload: object) -> dict[str, object]:
    if isinstance(payload, Mapping):
        if "settings" in payload and isinstance(payload.get("settings"), Mapping):
            payload = payload.get("settings")
        enabled = (
            payload.get("capture_enabled")
            if "capture_enabled" in payload
            else payload.get("captureEnabled", payload.get("enabled"))
        )
        return {
            "capture_enabled": _coerce_bool(enabled),
        }
    return dict(_RAW_PACKET_SETTINGS_DEFAULT)


def _load_raw_packet_settings(conn: object) -> dict[str, object]:
    try:
        row = conn.execute(
            "SELECT value_json FROM raw_packet_settings WHERE key = ?",
            (_RAW_PACKET_SETTINGS_KEY,),
        ).fetchone()
    except Exception:
        row = None
    if not row:
        return dict(_RAW_PACKET_SETTINGS_DEFAULT)
    raw_json = row[0] if len(row) > 0 else ""
    try:
        parsed = json.loads(raw_json if isinstance(raw_json, str) else "{}")
    except Exception:
        parsed = {}
    return _normalize_raw_packet_settings(parsed)


def _initialize_raw_packet_schema(conn: object) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS raw_packet_settings (
          key TEXT PRIMARY KEY,
          value_json TEXT NOT NULL,
          updated_unix INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS raw_packets (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_unix INTEGER NOT NULL,
          packet_id INTEGER,
          from_id TEXT,
          to_id TEXT,
          rx_time_unix INTEGER,
          rx_rssi REAL,
          rx_snr REAL,
          portnum TEXT,
          channel TEXT,
          encoding TEXT NOT NULL,
          byte_length INTEGER NOT NULL,
          packet_bytes BLOB NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_raw_packets_created_unix ON raw_packets(created_unix)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_raw_packets_packet_id ON raw_packets(packet_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_raw_packets_from_to ON raw_packets(from_id, to_id)"
    )


def open_raw_packet_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    try:
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass
    _initialize_raw_packet_schema(conn)
    conn.commit()
    return conn


def initialize_raw_packet_store_runtime(
    store: object,
    *,
    history_db_path: object,
    lock_factory: Callable[[], object],
    open_raw_packet_connection_fn: Callable[[str], object] = open_raw_packet_connection,
) -> None:
    raw_db_path = raw_packet_db_path_for_history_db_path(history_db_path)
    setattr(store, "raw_packet_db_path", raw_db_path)
    setattr(store, "_raw_packet_lock", lock_factory())
    setattr(store, "_raw_packet_conn", None)
    setattr(store, "_raw_packet_capture_enabled", False)
    setattr(store, "_raw_packet_error", "")
    if not raw_db_path:
        setattr(store, "_raw_packet_error", "raw packet database path unavailable")
        return
    try:
        conn = open_raw_packet_connection_fn(raw_db_path)
        settings = _load_raw_packet_settings(conn)
        setattr(store, "_raw_packet_conn", conn)
        setattr(store, "_raw_packet_capture_enabled", bool(settings.get("capture_enabled")))
    except Exception as exc:
        setattr(store, "_raw_packet_error", str(exc or "raw packet database open failed"))


def _fetch_one_int(conn: object, sql: str, params: tuple[object, ...] = ()) -> int:
    try:
        row = conn.execute(sql, params).fetchone()
    except Exception:
        row = None
    if not row or row[0] is None:
        return 0
    try:
        return max(0, int(row[0]))
    except Exception:
        return 0


def _fetch_range(conn: object) -> dict[str, int | None]:
    try:
        row = conn.execute("SELECT MIN(created_unix), MAX(created_unix) FROM raw_packets").fetchone()
    except Exception:
        row = None
    if not row:
        return {"first_unix": None, "last_unix": None}
    first = to_int(row[0])
    last = to_int(row[1])
    return {
        "first_unix": first if first and first > 0 else None,
        "last_unix": last if last and last > 0 else None,
    }


def _fetch_encoding_counts(conn: object) -> list[dict[str, object]]:
    try:
        rows = conn.execute(
            """
            SELECT encoding, COUNT(*), COALESCE(SUM(byte_length), 0)
            FROM raw_packets
            GROUP BY encoding
            ORDER BY COUNT(*) DESC, encoding
            """
        ).fetchall()
    except Exception:
        rows = []
    out: list[dict[str, object]] = []
    for row in rows:
        out.append(
            {
                "encoding": str(row[0] or "unknown"),
                "rows": max(0, int(to_int(row[1]) or 0)),
                "bytes": max(0, int(to_int(row[2]) or 0)),
            }
        )
    return out


def load_raw_packet_stats(store: object) -> dict[str, object]:
    conn = getattr(store, "_raw_packet_conn", None)
    raw_db_path = str(getattr(store, "raw_packet_db_path", "") or "")
    base_payload: dict[str, object] = {
        "available": conn is not None,
        "capture_enabled": bool(getattr(store, "_raw_packet_capture_enabled", False)),
        "path": raw_db_path,
        "generated_unix": int(time.time()),
    }
    if conn is None:
        base_payload.update(
            {
                "ok": False,
                "error": str(getattr(store, "_raw_packet_error", "") or "raw packet database unavailable"),
                "packet_rows": 0,
                "packet_bytes": 0,
                "encoding_counts": [],
            }
        )
        return base_payload

    lock = getattr(store, "_raw_packet_lock", None) or getattr(store, "_lock", None)
    if lock is None:
        return _load_raw_packet_stats_unlocked(store, conn, base_payload)
    with lock:
        return _load_raw_packet_stats_unlocked(store, conn, base_payload)


def build_raw_packet_database_download(
    store: object,
    *,
    temp_dir: str | None = None,
) -> dict[str, object]:
    conn = getattr(store, "_raw_packet_conn", None)
    if conn is None:
        return {
            "ok": False,
            "status_code": 503,
            "error": str(getattr(store, "_raw_packet_error", "") or "raw packet database unavailable"),
        }

    lock = getattr(store, "_raw_packet_lock", None) or getattr(store, "_lock", None)
    try:
        if lock is None:
            return _build_raw_packet_database_download_unlocked(store, conn, temp_dir=temp_dir)
        with lock:
            return _build_raw_packet_database_download_unlocked(store, conn, temp_dir=temp_dir)
    except Exception as exc:
        return {
            "ok": False,
            "status_code": 500,
            "error": str(exc or "raw packet database download failed"),
        }


def _build_raw_packet_database_download_unlocked(
    store: object,
    conn: object,
    *,
    temp_dir: str | None,
) -> dict[str, object]:
    backup_fn = getattr(conn, "backup", None)
    if not callable(backup_fn):
        return {
            "ok": False,
            "status_code": 503,
            "error": "raw packet database download is unavailable",
        }

    fd, temp_path = tempfile.mkstemp(
        prefix="meshdash_raw_packets_",
        suffix=".sqlite3",
        dir=temp_dir,
    )
    os.close(fd)
    try:
        dest = sqlite3.connect(temp_path)
        try:
            backup_fn(dest)
            dest.commit()
        finally:
            dest.close()
        with open(temp_path, "rb") as file_obj:
            payload = file_obj.read()
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass

    return {
        "ok": True,
        "filename": _raw_packet_download_filename(getattr(store, "raw_packet_db_path", "")),
        "content_type": "application/vnd.sqlite3",
        "bytes": payload,
        "size_bytes": len(payload),
    }


def _load_raw_packet_stats_unlocked(
    store: object,
    conn: object,
    base_payload: dict[str, object],
) -> dict[str, object]:
    packet_rows = _fetch_one_int(conn, "SELECT COUNT(*) FROM raw_packets")
    packet_bytes = _fetch_one_int(conn, "SELECT COALESCE(SUM(byte_length), 0) FROM raw_packets")
    page_count = _fetch_one_int(conn, "PRAGMA page_count")
    page_size = _fetch_one_int(conn, "PRAGMA page_size")
    freelist_count = _fetch_one_int(conn, "PRAGMA freelist_count")
    raw_db_path = str(getattr(store, "raw_packet_db_path", "") or "")
    db_size = _file_size(raw_db_path)
    wal_size = _file_size(f"{raw_db_path}-wal") if raw_db_path else None
    shm_size = _file_size(f"{raw_db_path}-shm") if raw_db_path else None
    total_size = sum(size for size in (db_size, wal_size, shm_size) if isinstance(size, int))
    base_payload.update(
        {
            "ok": True,
            "error": "",
            "size_bytes": db_size,
            "wal_size_bytes": wal_size,
            "shm_size_bytes": shm_size,
            "total_size_bytes": total_size,
            "page_count": page_count,
            "page_size": page_size,
            "freelist_count": freelist_count,
            "packet_rows": packet_rows,
            "packet_bytes": packet_bytes,
            "average_packet_bytes": (packet_bytes / packet_rows) if packet_rows > 0 else 0,
            "ranges": {
                "raw_packets": _fetch_range(conn),
            },
            "encoding_counts": _fetch_encoding_counts(conn),
        }
    )
    return base_payload


def save_raw_packet_settings(store: object, settings: object) -> dict[str, object]:
    conn = getattr(store, "_raw_packet_conn", None)
    if conn is None:
        payload = load_raw_packet_stats(store)
        payload["ok"] = False
        return payload

    normalized = _normalize_raw_packet_settings(settings)
    lock = getattr(store, "_raw_packet_lock", None) or getattr(store, "_lock", None)
    updated_unix = int(time.time())
    value_json = json.dumps(normalized, separators=(",", ":"))
    if lock is None:
        return _save_raw_packet_settings_unlocked(store, conn, value_json, updated_unix, normalized)
    with lock:
        return _save_raw_packet_settings_unlocked(store, conn, value_json, updated_unix, normalized)


def _save_raw_packet_settings_unlocked(
    store: object,
    conn: object,
    value_json: str,
    updated_unix: int,
    normalized: dict[str, object],
) -> dict[str, object]:
    previous = bool(getattr(store, "_raw_packet_capture_enabled", False))
    conn.execute(
        """
        INSERT INTO raw_packet_settings(key, value_json, updated_unix)
        VALUES(?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
          value_json = excluded.value_json,
          updated_unix = excluded.updated_unix
        """,
        (_RAW_PACKET_SETTINGS_KEY, value_json, updated_unix),
    )
    conn.commit()
    next_enabled = bool(normalized.get("capture_enabled"))
    setattr(store, "_raw_packet_capture_enabled", next_enabled)
    payload = _load_raw_packet_stats_unlocked(
        store,
        conn,
        {
            "available": True,
            "capture_enabled": next_enabled,
            "path": str(getattr(store, "raw_packet_db_path", "") or ""),
            "generated_unix": int(time.time()),
        },
    )
    payload["changed"] = previous != next_enabled
    return payload


def _mapping_get(root: object, *keys: str) -> object:
    if not isinstance(root, Mapping):
        return None
    for key in keys:
        if key in root:
            return root.get(key)
    return None


def _extract_decoded(packet: object) -> object:
    decoded = _mapping_get(packet, "decoded")
    return decoded if isinstance(decoded, Mapping) else {}


def _extract_packet_id(packet: object) -> int | None:
    packet_id = to_int(_mapping_get(packet, "id", "packet_id", "packetId"))
    return packet_id if packet_id is not None and packet_id >= 0 else None


def _extract_text(packet: object, *keys: str) -> str:
    value = _mapping_get(packet, *keys)
    return str(value or "").strip()


def _extract_raw_metadata(packet: object) -> dict[str, object]:
    decoded = _extract_decoded(packet)
    return {
        "packet_id": _extract_packet_id(packet),
        "from_id": _extract_text(packet, "fromId", "from_id", "from"),
        "to_id": _extract_text(packet, "toId", "to_id", "to"),
        "rx_time_unix": to_int(_mapping_get(packet, "rxTime", "rx_time", "rx_time_unix")),
        "rx_rssi": to_float(_mapping_get(packet, "rxRssi", "rx_rssi")),
        "rx_snr": to_float(_mapping_get(packet, "rxSnr", "rx_snr")),
        "portnum": _extract_text(decoded, "portnum", "port_num", "portNum"),
        "channel": _extract_text(packet, "channel"),
    }


def _bytes_from_value(value: object, *, field_name: str = "") -> tuple[bytes | None, str]:
    if value is None:
        return None, ""
    if isinstance(value, bytes):
        return bytes(value), field_name or "bytes"
    if isinstance(value, bytearray):
        return bytes(value), field_name or "bytearray"
    if isinstance(value, memoryview):
        return value.tobytes(), field_name or "memoryview"

    serialize = getattr(value, "SerializeToString", None)
    if callable(serialize):
        try:
            raw = serialize()
        except Exception:
            raw = None
        if isinstance(raw, (bytes, bytearray, memoryview)):
            return bytes(raw), field_name or "protobuf"

    if isinstance(value, str):
        clean = value.strip()
        if not clean:
            return None, ""
        hex_text = clean[2:] if clean.lower().startswith("0x") else clean
        if len(hex_text) % 2 == 0 and all(ch in "0123456789abcdefABCDEF" for ch in hex_text):
            try:
                return bytes.fromhex(hex_text), f"{field_name or 'text'}_hex"
            except Exception:
                return None, ""
    return None, ""


def extract_raw_packet_bytes(packet: object) -> tuple[bytes, str]:
    raw, encoding = _bytes_from_value(packet)
    if raw is not None:
        return raw, encoding or "bytes"

    if isinstance(packet, Mapping):
        for key in (
            "raw",
            "raw_bytes",
            "rawBytes",
            "packet_bytes",
            "packetBytes",
            "protobuf",
            "mesh_packet",
            "meshPacket",
        ):
            if key not in packet:
                continue
            raw, encoding = _bytes_from_value(packet.get(key), field_name=key)
            if raw is not None:
                return raw, encoding or key

    fallback = json.dumps(
        to_jsonable(packet),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return fallback, "json"


def save_raw_packet_capture(store: object, packet: object) -> bool:
    if not bool(getattr(store, "_raw_packet_capture_enabled", False)):
        return False
    conn = getattr(store, "_raw_packet_conn", None)
    if conn is None:
        return False
    try:
        raw_bytes, encoding = extract_raw_packet_bytes(packet)
    except Exception:
        return False
    if not raw_bytes:
        return False
    metadata = _extract_raw_metadata(packet)
    created_unix = int(time.time())
    lock = getattr(store, "_raw_packet_lock", None) or getattr(store, "_lock", None)
    if lock is None:
        return _save_raw_packet_capture_unlocked(conn, raw_bytes, encoding, metadata, created_unix)
    with lock:
        return _save_raw_packet_capture_unlocked(conn, raw_bytes, encoding, metadata, created_unix)


def _save_raw_packet_capture_unlocked(
    conn: object,
    raw_bytes: bytes,
    encoding: str,
    metadata: Mapping[str, object],
    created_unix: int,
) -> bool:
    conn.execute(
        """
        INSERT INTO raw_packets(
          created_unix,
          packet_id,
          from_id,
          to_id,
          rx_time_unix,
          rx_rssi,
          rx_snr,
          portnum,
          channel,
          encoding,
          byte_length,
          packet_bytes
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            created_unix,
            metadata.get("packet_id"),
            metadata.get("from_id") or None,
            metadata.get("to_id") or None,
            metadata.get("rx_time_unix"),
            metadata.get("rx_rssi"),
            metadata.get("rx_snr"),
            metadata.get("portnum") or None,
            metadata.get("channel") or None,
            str(encoding or "unknown"),
            len(raw_bytes),
            sqlite3.Binary(raw_bytes),
        ),
    )
    conn.commit()
    return True
