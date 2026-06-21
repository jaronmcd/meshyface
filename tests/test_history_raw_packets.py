import sqlite3
from pathlib import Path

from meshdash.history_raw_packets import raw_packet_db_path_for_history_db_path
from meshdash.history_store_runtime import HistoryStore


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
        payload = download["bytes"]
        assert isinstance(payload, bytes)
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
