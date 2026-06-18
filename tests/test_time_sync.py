import socket
import struct

import pytest

from meshdash import time_sync


def test_normalize_time_sync_timezone_handles_common_values() -> None:
    assert time_sync.normalize_time_sync_timezone("") == "local"
    assert time_sync.normalize_time_sync_timezone(" system ") == "local"
    assert time_sync.normalize_time_sync_timezone("utc") == "UTC"
    assert time_sync.normalize_time_sync_timezone("America/Chicago") == "America/Chicago"
    assert time_sync.normalize_time_sync_timezone("Not/AZone") == "local"


def test_resolve_time_sync_uses_host_clock_without_server() -> None:
    result = time_sync.resolve_time_sync(
        use_time_server=False,
        timezone_name="UTC",
        now_fn=lambda: 1234.75,
    )

    assert result["ok"] is True
    assert result["source"] == "host_clock"
    assert result["host_unix"] == 1234
    assert result["applied_unix"] == 1234
    assert result["applied_utc"] == "1970-01-01 00:20:34Z"
    assert result["applied_local"] == "1970-01-01 00:20:34 UTC"
    assert result["offset_seconds"] == 0.0


def test_resolve_time_sync_uses_server_time_and_coerces_timeout() -> None:
    calls: list[dict[str, object]] = []

    def _query(server: str, *, timeout_seconds: float) -> float:
        calls.append({"server": server, "timeout_seconds": timeout_seconds})
        return 1300.25

    result = time_sync.resolve_time_sync(
        use_time_server=True,
        server="time.example",
        timezone_name="UTC",
        timeout_ms=500,
        now_fn=lambda: 1200.0,
        query_time_server_unix_fn=_query,
    )

    assert result["ok"] is True
    assert result["source"] == "time_server"
    assert result["server"] == "time.example"
    assert result["applied_unix"] == 1300
    assert result["offset_seconds"] == 100.25
    assert calls == [{"server": "time.example", "timeout_seconds": 0.5}]


def test_resolve_time_sync_reports_server_query_failure() -> None:
    result = time_sync.resolve_time_sync(
        use_time_server=True,
        server="",
        timeout_ms="bad",
        now_fn=lambda: 2000.0,
        query_time_server_unix_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("no reply")),
    )

    assert result == {
        "ok": False,
        "source": "time_server",
        "server": "pool.ntp.org",
        "timezone": "local",
        "host_unix": 2000,
        "error": "no reply",
    }


class _FakeSocket:
    def __init__(self, payload: bytes | None = None, *, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.timeout = None
        self.sent: list[tuple[bytes, object]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def sendto(self, data: bytes, sockaddr: object) -> None:
        self.sent.append((data, sockaddr))
        if self.error is not None:
            raise self.error

    def recvfrom(self, size: int) -> tuple[bytes, object]:
        assert size == 48
        return self.payload or b"", ("127.0.0.1", 123)


def _ntp_payload(unix_seconds: int) -> bytes:
    transmit_seconds = unix_seconds + time_sync._NTP_UNIX_EPOCH_DELTA_SECONDS
    return (b"\0" * 40) + struct.pack("!II", transmit_seconds, 0)


def test_query_time_server_unix_reads_ntp_response(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_socket = _FakeSocket(_ntp_payload(42))
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_DGRAM, 0, "", ("127.0.0.1", 123))],
    )
    monkeypatch.setattr(socket, "socket", lambda *_args, **_kwargs: fake_socket)

    result = time_sync.query_time_server_unix("time.example", timeout_seconds=1.25)

    assert result == 42.0
    assert fake_socket.timeout == 1.25
    assert fake_socket.sent == [(b"\x1b" + (b"\0" * 47), ("127.0.0.1", 123))]


def test_query_time_server_unix_reports_incomplete_and_send_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_DGRAM, 0, "", ("127.0.0.1", 123))],
    )
    monkeypatch.setattr(socket, "socket", lambda *_args, **_kwargs: _FakeSocket(b"short"))

    with pytest.raises(RuntimeError, match="incomplete response"):
        time_sync.query_time_server_unix("time.example")

    monkeypatch.setattr(socket, "socket", lambda *_args, **_kwargs: _FakeSocket(error=OSError("blocked")))

    with pytest.raises(RuntimeError, match="time server query failed: blocked"):
        time_sync.query_time_server_unix("time.example")


def test_query_time_server_unix_reports_empty_address_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [])

    with pytest.raises(RuntimeError, match="time server query failed"):
        time_sync.query_time_server_unix("time.example")
