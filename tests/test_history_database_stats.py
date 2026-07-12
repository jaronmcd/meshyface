import io
import json
import sqlite3
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.history_schema import initialize_history_schema
from meshdash.history_store_database_stats import load_database_stats
from meshdash.http_routes_get import handle_dashboard_get


class _DownloadHandler:
    def __init__(self) -> None:
        self.headers: dict[str, object] = {}
        self.client_address = ("127.0.0.1", 12345)
        self.sent_status: int | None = None
        self.sent_headers: list[tuple[str, str]] = []
        self.wfile = io.BytesIO()

    def send_response(self, code: int) -> None:
        self.sent_status = code

    def send_header(self, key: str, value: str) -> None:
        self.sent_headers.append((key, value))

    def end_headers(self) -> None:
        pass


def _make_store(conn: sqlite3.Connection, db_path: str) -> SimpleNamespace:
    return SimpleNamespace(
        _conn=conn,
        _read_conn=None,
        _lock=threading.Lock(),
        db_path=db_path,
        max_rows=250,
        retention_seconds=7 * 86400,
        event_max_rows=1000,
        event_retention_seconds=3 * 86400,
        rollup_retention_seconds=30 * 86400,
    )


def test_history_database_stats_counts_tables_and_policy(tmp_path: Path) -> None:
    db_path = tmp_path / "history.db"
    conn = sqlite3.connect(db_path)
    initialize_history_schema(conn)
    conn.executemany(
        "INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(?, ?, ?)",
        [
            (100, json.dumps({"portnum": "TEXT_MESSAGE_APP"}), json.dumps({"id": 1})),
            (200, json.dumps({"portnum": "NODEINFO_APP"}), json.dumps({"id": 2})),
        ],
    )
    conn.execute(
        """
        INSERT INTO packet_events(created_unix, from_id, to_id, portnum)
        VALUES(?, ?, ?, ?)
        """,
        (150, "!11111111", "^all", "TEXT_MESSAGE_APP"),
    )
    conn.execute(
        "INSERT INTO chat(created_unix, message_json) VALUES(?, ?)",
        (175, json.dumps({"text": "hello"})),
    )
    conn.commit()

    stats = load_database_stats(_make_store(conn, str(db_path)))

    assert stats["ok"] is True
    assert stats["enabled"] is True
    assert stats["path"] == str(db_path)
    assert stats["size_bytes"] > 0
    assert stats["total_size_bytes"] >= stats["size_bytes"]
    assert stats["table_counts"]["packets"] == 2
    assert stats["table_counts"]["packet_events"] == 1
    assert stats["table_counts"]["chat"] == 1
    assert stats["total_rows"] >= 4
    assert stats["ranges"]["packets"] == {"first_unix": 100, "last_unix": 200}
    assert stats["page_count"] > 0
    assert stats["page_size"] > 0
    assert stats["policy"]["retention_days"] == 7
    assert stats["policy"]["event_retention_days"] == 3
    assert stats["policy"]["rollup_retention_days"] == 30


def test_database_stats_route_uses_attached_state_helper() -> None:
    def state_fn() -> dict[str, object]:
        return {}

    setattr(state_fn, "database_stats_fn", lambda: {"ok": True, "enabled": True, "total_rows": 7})
    written: list[tuple[int, dict[str, object], bool]] = []
    deps = SimpleNamespace(
        state_fn=state_fn,
        allow_tokenless_raw_packet_download=True,
        write_json_response_fn=lambda _handler, *, status_code, payload_obj, no_store=False, **_kwargs: written.append(
            (status_code, payload_obj, no_store)
        ),
    )

    handle_dashboard_get(
        object(),
        path="/api/system/database",
        query="",
        deps=deps,
    )

    assert written == [(200, {"ok": True, "enabled": True, "total_rows": 7}, True)]


def test_database_stats_route_reports_unavailable_without_helper() -> None:
    written: list[tuple[int, dict[str, object], bool]] = []
    deps = SimpleNamespace(
        state_fn=lambda: {},
        allow_tokenless_raw_packet_download=True,
        write_json_response_fn=lambda _handler, *, status_code, payload_obj, no_store=False, **_kwargs: written.append(
            (status_code, payload_obj, no_store)
        ),
    )

    handle_dashboard_get(
        object(),
        path="/api/system/database",
        query="",
        deps=deps,
    )

    assert written == [
        (
            200,
            {
                "ok": False,
                "enabled": False,
                "error": "history database unavailable on this dashboard instance",
            },
            True,
        )
    ]


def test_raw_packet_database_download_route_streams_sqlite_bytes() -> None:
    payload = b"SQLite format 3\x00payload"

    def state_fn() -> dict[str, object]:
        return {}

    setattr(
        state_fn,
        "raw_packet_database_download_fn",
        lambda: {
            "ok": True,
            "filename": "mesh raw.sqlite3",
            "content_type": "application/vnd.sqlite3",
            "bytes": payload,
        },
    )
    written: list[tuple[int, dict[str, object], bool]] = []
    deps = SimpleNamespace(
        state_fn=state_fn,
        allow_tokenless_raw_packet_download=True,
        write_json_response_fn=lambda _handler, *, status_code, payload_obj, no_store=False, **_kwargs: written.append(
            (status_code, payload_obj, no_store)
        ),
    )
    handler = _DownloadHandler()

    handle_dashboard_get(
        handler,
        path="/api/system/database/raw_packets/download",
        query="",
        deps=deps,
    )

    headers = dict(handler.sent_headers)
    assert written == []
    assert handler.sent_status == 200
    assert headers["Content-Type"] == "application/vnd.sqlite3"
    assert headers["Content-Disposition"] == 'attachment; filename="mesh_raw.sqlite3"'
    assert headers["Content-Length"] == str(len(payload))
    assert headers["Cache-Control"].startswith("no-store")
    assert handler.wfile.getvalue() == payload


def test_raw_packet_database_download_route_streams_file_and_cleans_up(
    tmp_path: Path,
) -> None:
    payload = b"SQLite format 3\x00streamed"
    download_path = tmp_path / "raw-download.sqlite3"
    download_path.write_bytes(payload)
    cleaned = False

    def state_fn() -> dict[str, object]:
        return {}

    def _cleanup() -> None:
        nonlocal cleaned
        cleaned = True
        download_path.unlink(missing_ok=True)

    setattr(
        state_fn,
        "raw_packet_database_download_fn",
        lambda: {
            "ok": True,
            "filename": "raw.sqlite3",
            "content_type": "application/vnd.sqlite3",
            "path": str(download_path),
            "size_bytes": len(payload),
            "cleanup_fn": _cleanup,
        },
    )
    deps = SimpleNamespace(
        state_fn=state_fn,
        allow_tokenless_raw_packet_download=True,
        write_json_response_fn=lambda *_args, **_kwargs: None,
    )
    handler = _DownloadHandler()

    handle_dashboard_get(
        handler,
        path="/api/system/database/raw_packets/download",
        query="",
        deps=deps,
    )

    assert handler.sent_status == 200
    assert handler.wfile.getvalue() == payload
    assert cleaned is True
    assert download_path.exists() is False


def test_raw_packet_database_download_route_reports_unavailable_without_helper() -> None:
    written: list[tuple[int, dict[str, object], bool]] = []
    deps = SimpleNamespace(
        state_fn=lambda: {},
        allow_tokenless_raw_packet_download=True,
        write_json_response_fn=lambda _handler, *, status_code, payload_obj, no_store=False, **_kwargs: written.append(
            (status_code, payload_obj, no_store)
        ),
    )

    handle_dashboard_get(
        _DownloadHandler(),
        path="/api/system/database/raw_packets/download",
        query="",
        deps=deps,
    )

    assert written == [
        (
            503,
            {
                "ok": False,
                "error": "raw packet database unavailable on this dashboard instance",
            },
            True,
        )
    ]


def test_raw_packet_database_download_requires_configured_api_token() -> None:
    called = False

    def state_fn() -> dict[str, object]:
        return {}

    def _download() -> dict[str, object]:
        nonlocal called
        called = True
        return {"ok": True, "bytes": b"SQLite format 3\x00"}

    setattr(state_fn, "raw_packet_database_download_fn", _download)
    written: list[tuple[int, dict[str, object], bool, dict[str, str]]] = []
    deps = SimpleNamespace(
        state_fn=state_fn,
        api_token="secret-token",
        write_json_response_fn=lambda _handler, *, status_code, payload_obj, no_store=False, extra_headers=None, **_kwargs: written.append(
            (status_code, payload_obj, no_store, dict(extra_headers or {}))
        ),
    )
    handler = _DownloadHandler()

    handle_dashboard_get(
        handler,
        path="/api/system/database/raw_packets/download",
        query="",
        deps=deps,
    )

    assert called is False
    assert written == [
        (
            401,
            {"ok": False, "error": "API token required for raw packet download"},
            True,
            {"WWW-Authenticate": "Bearer"},
        )
    ]

    handler.headers["Authorization"] = "Bearer secret-token"
    handle_dashboard_get(
        handler,
        path="/api/system/database/raw_packets/download",
        query="",
        deps=deps,
    )
    assert called is True
    assert handler.sent_status == 200


def test_raw_packet_database_download_without_token_is_loopback_only() -> None:
    called = False

    def state_fn() -> dict[str, object]:
        return {}

    def _download() -> dict[str, object]:
        nonlocal called
        called = True
        return {"ok": True, "bytes": b"SQLite format 3\x00"}

    setattr(state_fn, "raw_packet_database_download_fn", _download)
    written: list[tuple[int, dict[str, object]]] = []
    deps = SimpleNamespace(
        state_fn=state_fn,
        api_token=None,
        allow_tokenless_raw_packet_download=True,
        write_json_response_fn=lambda _handler, *, status_code, payload_obj, **_kwargs: written.append(
            (status_code, payload_obj)
        ),
    )
    handler = _DownloadHandler()
    handler.client_address = ("192.0.2.10", 12345)

    handle_dashboard_get(
        handler,
        path="/api/system/database/raw_packets/download",
        query="",
        deps=deps,
    )

    assert called is False
    assert written == [
        (401, {"ok": False, "error": "API token required for raw packet download"})
    ]


def test_raw_packet_database_download_tokenless_mode_is_explicit_opt_in() -> None:
    called = False

    def state_fn() -> dict[str, object]:
        return {}

    def _download() -> dict[str, object]:
        nonlocal called
        called = True
        return {"ok": True, "bytes": b"SQLite format 3\x00"}

    setattr(state_fn, "raw_packet_database_download_fn", _download)
    written: list[int] = []
    deps = SimpleNamespace(
        state_fn=state_fn,
        api_token=None,
        allow_tokenless_raw_packet_download=False,
        write_json_response_fn=lambda _handler, *, status_code, **_kwargs: written.append(
            status_code
        ),
    )

    handle_dashboard_get(
        _DownloadHandler(),
        path="/api/system/database/raw_packets/download",
        query="",
        deps=deps,
    )

    assert called is False
    assert written == [401]
