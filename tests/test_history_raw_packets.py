import os
import sqlite3
import stat
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from meshdash import history_raw_packets
from meshdash.history_raw_packets import (
    build_raw_packet_database_download,
    extract_raw_packet_bytes,
    initialize_raw_packet_store_runtime,
    load_raw_packet_stats,
    open_raw_packet_connection,
    raw_packet_db_path_for_history_db_path,
    save_raw_packet_capture,
    save_raw_packet_settings,
)
from meshdash.history_store_runtime import HistoryStore


def _read_download_payload(download: dict[str, object]) -> bytes:
    path = Path(str(download.get("path") or ""))
    cleanup_fn = download.get("cleanup_fn")
    try:
        return path.read_bytes()
    finally:
        if callable(cleanup_fn):
            cleanup_fn()


def test_raw_packet_db_path_derives_sidecar_sqlite_path() -> None:
    assert raw_packet_db_path_for_history_db_path("/tmp/history.sqlite3") == "/tmp/history.raw.sqlite3"
    assert raw_packet_db_path_for_history_db_path("/tmp/history") == "/tmp/history.raw.sqlite3"
    assert raw_packet_db_path_for_history_db_path(":memory:") == ":memory:"


def test_history_store_raw_packet_capture_toggle_and_stats(tmp_path: Path) -> None:
    history_path = tmp_path / "mesh_dashboard_history.sqlite3"
    store = HistoryStore(
        db_path=str(history_path),
        max_rows=100,
        retention_days=30,
        event_max_rows=100,
        event_retention_days=30,
        rollup_retention_days=30,
    )
    try:
        raw_path = tmp_path / "mesh_dashboard_history.raw.sqlite3"
        stats = store.raw_packet_stats()
        assert stats["ok"] is True
        assert stats["available"] is True
        assert stats["capture_enabled"] is False
        assert stats["path"] == str(raw_path)
        assert stats["packet_rows"] == 0
        assert raw_path.exists()

        packet = {
            "id": 123,
            "fromId": "!01020304",
            "toId": "^all",
            "rxTime": 1_700_000_000,
            "rxRssi": -91,
            "rxSnr": 4.5,
            "channel": 0,
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "payload": b"hello",
                "text": "hello",
            },
        }
        assert store.save_raw_packet(packet) is False

        enabled = store.set_raw_packet_capture_settings({"capture_enabled": True})
        assert enabled["ok"] is True
        assert enabled["capture_enabled"] is True
        assert enabled["changed"] is True

        assert store.save_raw_packet(packet) is True
        stats = store.raw_packet_stats()
        assert stats["capture_enabled"] is True
        assert stats["packet_rows"] == 1
        assert stats["packet_bytes"] > 0
        assert stats["ranges"]["raw_packets"]["first_unix"] > 0  # type: ignore[index]
        encodings = stats["encoding_counts"]
        assert encodings and encodings[0]["encoding"] == "json"  # type: ignore[index]

        raw_packet = {**packet, "id": 124, "raw_bytes": b"\x01\x02\x03"}
        assert store.save_raw_packet(raw_packet) is True
        stats = store.raw_packet_stats()
        assert stats["packet_rows"] == 2
        encoding_names = {str(row["encoding"]) for row in stats["encoding_counts"]}  # type: ignore[index]
        assert "raw_bytes" in encoding_names

        with sqlite3.connect(raw_path) as conn:
            row = conn.execute(
                "SELECT encoding, packet_bytes FROM raw_packets WHERE packet_id = ?",
                (124,),
            ).fetchone()
        assert row == ("raw_bytes", b"\x01\x02\x03")

        download = store.raw_packet_database_download()
        assert download["ok"] is True
        assert download["content_type"] == "application/vnd.sqlite3"
        assert str(download["filename"]).endswith(".sqlite3")
        payload = _read_download_payload(download)
        assert payload.startswith(b"SQLite format 3\x00")
        snapshot_path = tmp_path / "raw_download.sqlite3"
        snapshot_path.write_bytes(payload)
        with sqlite3.connect(snapshot_path) as conn:
            rows = conn.execute("SELECT COUNT(*) FROM raw_packets").fetchone()[0]
            row = conn.execute(
                "SELECT encoding, packet_bytes FROM raw_packets WHERE packet_id = ?",
                (124,),
            ).fetchone()
        assert rows == 2
        assert row == ("raw_bytes", b"\x01\x02\x03")
    finally:
        store.close()


def test_raw_packet_db_file_permissions_ignore_permissive_umask(tmp_path: Path) -> None:
    raw_path = tmp_path / "private" / "history.raw.sqlite3"

    old_umask = os.umask(0)
    try:
        conn = open_raw_packet_connection(str(raw_path))
    finally:
        os.umask(old_umask)

    try:
        assert stat.S_IMODE(raw_path.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(raw_path.stat().st_mode) == 0o600
        for suffix in ("-journal", "-shm", "-wal"):
            sidecar_path = Path(f"{raw_path}{suffix}")
            if sidecar_path.exists():
                assert stat.S_IMODE(sidecar_path.stat().st_mode) == 0o600
    finally:
        conn.close()


def test_raw_packet_db_open_preserves_existing_file_permissions(tmp_path: Path) -> None:
    db_dir = tmp_path / "shared"
    raw_path = db_dir / "history.raw.sqlite3"
    db_dir.mkdir(mode=0o755)
    raw_path.touch()
    raw_path.chmod(0o664)

    conn = open_raw_packet_connection(str(raw_path))
    try:
        assert stat.S_IMODE(db_dir.stat().st_mode) == 0o755
        assert stat.S_IMODE(raw_path.stat().st_mode) == 0o664
    finally:
        conn.close()


class _RaisingConn:
    def execute(self, *args: object) -> object:
        raise RuntimeError("boom")


class _FixedRowConn:
    def __init__(self, row: object) -> None:
        self._row = row

    def execute(self, *args: object) -> object:
        row = self._row

        class _Cursor:
            @staticmethod
            def fetchone() -> object:
                return row

            @staticmethod
            def fetchall() -> list:
                return [row] if row else []

        return _Cursor()


def _memory_store(*, lock: object = None, capture_enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        raw_packet_db_path=":memory:",
        _raw_packet_conn=open_raw_packet_connection(":memory:"),
        _raw_packet_lock=lock,
        _raw_packet_capture_enabled=capture_enabled,
        _raw_packet_error="",
    )


def test_raw_packet_db_path_rejects_blank_and_memory_uri_paths() -> None:
    assert raw_packet_db_path_for_history_db_path("") == ""
    assert raw_packet_db_path_for_history_db_path(None) == ""
    assert raw_packet_db_path_for_history_db_path("file::memory:") == "file::memory:"
    assert raw_packet_db_path_for_history_db_path("file:hist?mode=memory") == ""


def test_raw_packet_download_filename_sanitizes_unusual_names() -> None:
    fallback = history_raw_packets._raw_packet_download_filename("...")
    assert fallback.startswith("meshdash_raw_packets_")
    assert fallback.endswith(".sqlite3")

    empty = history_raw_packets._raw_packet_download_filename("")
    assert empty.startswith("meshdash_raw_packets")
    assert empty.endswith(".sqlite3")

    renamed = history_raw_packets._raw_packet_download_filename("/tmp/packets.bin")
    assert renamed.startswith("packets_")
    assert renamed.endswith(".sqlite3")


def test_file_size_handles_memory_and_missing_paths(tmp_path: Path) -> None:
    assert history_raw_packets._file_size("") is None
    assert history_raw_packets._file_size(":memory:") is None
    assert history_raw_packets._file_size(str(tmp_path / "missing.sqlite3")) is None
    real = tmp_path / "real.bin"
    real.write_bytes(b"1234")
    assert history_raw_packets._file_size(str(real)) == 4


def test_normalize_raw_packet_settings_variants() -> None:
    normalize = history_raw_packets._normalize_raw_packet_settings
    assert normalize(None) == {"capture_enabled": False}
    assert normalize("nonsense") == {"capture_enabled": False}
    assert normalize({"settings": {"captureEnabled": "yes"}}) == {"capture_enabled": True}
    assert normalize({"enabled": True}) == {"capture_enabled": True}
    assert normalize({"capture_enabled": None}) == {"capture_enabled": False}
    assert normalize({"capture_enabled": "off"}) == {"capture_enabled": False}


def test_load_raw_packet_settings_defensive_paths() -> None:
    default = {"capture_enabled": False}
    assert history_raw_packets._load_raw_packet_settings(_RaisingConn()) == default

    conn = open_raw_packet_connection(":memory:")
    try:
        conn.execute(
            "INSERT INTO raw_packet_settings(key, value_json, updated_unix) VALUES(?, ?, ?)",
            ("raw_packet_capture_v1", "not valid json", 0),
        )
        assert history_raw_packets._load_raw_packet_settings(conn) == default

        conn.execute(
            "UPDATE raw_packet_settings SET value_json = ?",
            (sqlite3.Binary(b"\x00\x01"),),
        )
        assert history_raw_packets._load_raw_packet_settings(conn) == default
    finally:
        conn.close()


def test_initialize_store_runtime_without_db_path_reports_unavailable() -> None:
    store = SimpleNamespace()
    initialize_raw_packet_store_runtime(
        store, history_db_path="", lock_factory=threading.Lock
    )
    assert store.raw_packet_db_path == ""
    assert store._raw_packet_conn is None
    assert store._raw_packet_error == "raw packet database path unavailable"

    stats = load_raw_packet_stats(store)
    assert stats["ok"] is False
    assert stats["available"] is False
    assert stats["packet_rows"] == 0
    assert "unavailable" in str(stats["error"])

    download = build_raw_packet_database_download(store)
    assert download["ok"] is False
    assert download["status_code"] == 503

    saved = save_raw_packet_settings(store, {"capture_enabled": True})
    assert saved["ok"] is False

    store._raw_packet_capture_enabled = True
    assert save_raw_packet_capture(store, {"id": 1}) is False


def test_initialize_store_runtime_records_open_failure() -> None:
    def _broken_open(db_path: str) -> object:
        raise sqlite3.OperationalError("disk unavailable")

    store = SimpleNamespace()
    initialize_raw_packet_store_runtime(
        store,
        history_db_path="/tmp/history.sqlite3",
        lock_factory=threading.Lock,
        open_raw_packet_connection_fn=_broken_open,
    )
    assert store._raw_packet_conn is None
    assert "disk unavailable" in store._raw_packet_error


def test_raw_packet_operations_without_lock_use_unlocked_paths() -> None:
    store = _memory_store()
    try:
        stats = load_raw_packet_stats(store)
        assert stats["ok"] is True
        assert stats["size_bytes"] is None

        saved = save_raw_packet_settings(store, {"captureEnabled": "on"})
        assert saved["ok"] is True
        assert saved["capture_enabled"] is True
        assert saved["changed"] is False

        assert save_raw_packet_capture(store, b"\x01\x02") is True
        assert save_raw_packet_capture(store, b"") is False

        download = build_raw_packet_database_download(store)
        assert download["ok"] is True
        assert _read_download_payload(download).startswith(b"SQLite format 3\x00")
    finally:
        store._raw_packet_conn.close()


def test_raw_packet_capture_enforces_packet_and_storage_quotas() -> None:
    store = _memory_store()
    store._raw_packet_max_single_bytes = 4
    store._raw_packet_max_rows = 3
    store._raw_packet_max_bytes = 8
    store._raw_packet_retention_seconds = 3600
    store._raw_packet_writes_since_prune = 0
    try:
        assert save_raw_packet_capture(store, b"12345") is False
        for value in (b"aa", b"bb", b"cc", b"dd"):
            assert save_raw_packet_capture(store, value) is True

        history_raw_packets._prune_raw_packet_capture_unlocked(
            store,
            store._raw_packet_conn,
            now_unix=int(history_raw_packets.time.time()),
        )
        store._raw_packet_conn.commit()
        stats = load_raw_packet_stats(store)
        assert stats["packet_rows"] == 3
        assert stats["packet_bytes"] == 6
        assert stats["policy"] == {
            "max_rows": 3,
            "retention_seconds": 3600,
            "max_packet_bytes": 4,
            "max_stored_bytes": 8,
        }
    finally:
        store._raw_packet_conn.close()


def test_raw_packet_capture_prunes_expired_and_oldest_payload_rows() -> None:
    store = _memory_store()
    store._raw_packet_max_single_bytes = 16
    store._raw_packet_max_rows = 10
    store._raw_packet_max_bytes = 5
    store._raw_packet_retention_seconds = 10
    now_unix = 1_800_000_000
    conn = store._raw_packet_conn
    try:
        for created_unix, payload in (
            (now_unix - 20, b"old"),
            (now_unix - 2, b"abc"),
            (now_unix - 1, b"de"),
        ):
            conn.execute(
                "INSERT INTO raw_packets(created_unix, encoding, byte_length, packet_bytes) "
                "VALUES(?, 'bytes', ?, ?)",
                (created_unix, len(payload), sqlite3.Binary(payload)),
            )
        deleted = history_raw_packets._prune_raw_packet_capture_unlocked(
            store,
            conn,
            now_unix=now_unix,
        )
        conn.commit()
        assert deleted == 1
        rows = conn.execute(
            "SELECT packet_bytes FROM raw_packets ORDER BY id"
        ).fetchall()
        assert rows == [(b"abc",), (b"de",)]

        store._raw_packet_max_bytes = 3
        deleted = history_raw_packets._prune_raw_packet_capture_unlocked(
            store,
            conn,
            now_unix=now_unix,
        )
        conn.commit()
        assert deleted == 1
        assert conn.execute("SELECT packet_bytes FROM raw_packets").fetchall() == [(b"de",)]
    finally:
        conn.close()


def test_fetch_helpers_swallow_bad_rows_and_errors() -> None:
    fetch_one = history_raw_packets._fetch_one_int
    assert fetch_one(_RaisingConn(), "SELECT 1") == 0
    assert fetch_one(_FixedRowConn(None), "SELECT 1") == 0
    assert fetch_one(_FixedRowConn((None,)), "SELECT 1") == 0
    assert fetch_one(_FixedRowConn(("abc",)), "SELECT 1") == 0
    assert fetch_one(_FixedRowConn((-5,)), "SELECT 1") == 0
    assert fetch_one(_FixedRowConn((7,)), "SELECT 1") == 7

    empty_range = {"first_unix": None, "last_unix": None}
    assert history_raw_packets._fetch_range(_RaisingConn()) == empty_range
    assert history_raw_packets._fetch_range(_FixedRowConn(None)) == empty_range

    assert history_raw_packets._fetch_encoding_counts(_RaisingConn()) == []


def test_extract_raw_packet_bytes_encoding_fallbacks() -> None:
    assert extract_raw_packet_bytes(b"\x09") == (b"\x09", "bytes")
    assert extract_raw_packet_bytes({"raw_bytes": bytearray(b"ab")}) == (b"ab", "raw_bytes")
    assert extract_raw_packet_bytes({"packet_bytes": memoryview(b"cd")}) == (
        b"cd",
        "packet_bytes",
    )

    class _Proto:
        @staticmethod
        def SerializeToString() -> bytes:
            return b"\x08\x01"

    assert extract_raw_packet_bytes(_Proto()) == (b"\x08\x01", "protobuf")
    assert extract_raw_packet_bytes({"mesh_packet": _Proto()}) == (b"\x08\x01", "mesh_packet")

    class _BrokenProto:
        @staticmethod
        def SerializeToString() -> bytes:
            raise RuntimeError("no serialization")

    raw, encoding = extract_raw_packet_bytes({"mesh_packet": _BrokenProto(), "id": 5})
    assert encoding == "json"
    assert raw

    assert extract_raw_packet_bytes({"raw": "0x0102"}) == (b"\x01\x02", "raw_hex")
    assert extract_raw_packet_bytes({"raw": "0a0b"}) == (b"\x0a\x0b", "raw_hex")

    odd_raw, odd_encoding = extract_raw_packet_bytes({"raw": "0x123"})
    assert odd_encoding == "json"
    blank_raw, blank_encoding = extract_raw_packet_bytes({"raw": "   "})
    assert blank_encoding == "json"
    assert odd_raw and blank_raw


def test_build_download_reports_backup_failures() -> None:
    no_backup_store = SimpleNamespace(
        raw_packet_db_path=":memory:",
        _raw_packet_conn=SimpleNamespace(),
        _raw_packet_lock=None,
        _raw_packet_capture_enabled=False,
        _raw_packet_error="",
    )
    download = build_raw_packet_database_download(no_backup_store)
    assert download["ok"] is False
    assert download["status_code"] == 503

    def _broken_backup(dest: object) -> None:
        raise sqlite3.OperationalError("backup interrupted")

    broken_store = SimpleNamespace(
        raw_packet_db_path=":memory:",
        _raw_packet_conn=SimpleNamespace(backup=_broken_backup),
        _raw_packet_lock=None,
        _raw_packet_capture_enabled=False,
        _raw_packet_error="",
    )
    download = build_raw_packet_database_download(broken_store)
    assert download["ok"] is False
    assert download["status_code"] == 500
    assert "backup interrupted" in str(download["error"])


def test_raw_packet_download_rejects_concurrent_backup() -> None:
    store = _memory_store()
    try:
        first = build_raw_packet_database_download(store)
        assert first["ok"] is True
        blocked = build_raw_packet_database_download(store)
        assert blocked["ok"] is False
        assert blocked["status_code"] == 429

        cleanup_fn = first.get("cleanup_fn")
        assert callable(cleanup_fn)
        cleanup_fn()

        next_download = build_raw_packet_database_download(store)
        assert next_download["ok"] is True
        next_cleanup = next_download.get("cleanup_fn")
        assert callable(next_cleanup)
        next_cleanup()
    finally:
        store._raw_packet_conn.close()


def test_raw_packet_download_releases_lock_when_backup_size_probe_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _memory_store()
    real_getsize = history_raw_packets.os.path.getsize
    try:
        with monkeypatch.context() as scoped:
            scoped.setattr(
                history_raw_packets.os.path,
                "getsize",
                lambda _path: (_ for _ in ()).throw(OSError("size unavailable")),
            )
            failed = build_raw_packet_database_download(store)

        assert failed["ok"] is False
        assert failed["status_code"] == 500

        monkeypatch.setattr(history_raw_packets.os.path, "getsize", real_getsize)
        recovered = build_raw_packet_database_download(store)
        assert recovered["ok"] is True
        cleanup_fn = recovered.get("cleanup_fn")
        assert callable(cleanup_fn)
        cleanup_fn()
    finally:
        store._raw_packet_conn.close()


def test_save_raw_packet_capture_swallows_extract_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _memory_store()
    try:
        def _broken_extract(packet: object) -> tuple[bytes, str]:
            raise ValueError("unreadable packet")

        monkeypatch.setattr(
            history_raw_packets, "extract_raw_packet_bytes", _broken_extract
        )
        assert save_raw_packet_capture(store, {"id": 9}) is False
    finally:
        store._raw_packet_conn.close()
