from __future__ import annotations

import socket
import struct
import time
from datetime import datetime, timezone
from typing import Callable

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - only on very old Python builds
    ZoneInfo = None  # type: ignore[assignment]

_DEFAULT_TIME_SERVER = "pool.ntp.org"
_DEFAULT_TIMEOUT_SECONDS = 2.0
_NTP_PORT = 123
_NTP_PACKET_SIZE = 48
_NTP_UNIX_EPOCH_DELTA_SECONDS = 2_208_988_800


def normalize_time_sync_timezone(value: object) -> str:
    clean = str(value or "").strip()
    if not clean:
        return "local"

    lowered = clean.lower()
    if lowered in {"local", "system", "browser"}:
        return "local"
    if lowered in {"utc", "z"}:
        return "UTC"

    if ZoneInfo is None:
        return "local"
    try:
        ZoneInfo(clean)
    except Exception:
        return "local"
    return clean


def _format_utc_text(unix_seconds: int) -> str:
    return datetime.fromtimestamp(unix_seconds, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def _format_timezone_text(unix_seconds: int, timezone_name: str) -> str:
    dt_utc = datetime.fromtimestamp(unix_seconds, tz=timezone.utc)
    if timezone_name == "UTC":
        return dt_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    if timezone_name == "local":
        return dt_utc.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    if ZoneInfo is not None:
        try:
            return dt_utc.astimezone(ZoneInfo(timezone_name)).strftime("%Y-%m-%d %H:%M:%S %Z")
        except Exception:
            pass
    return dt_utc.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def _coerce_timeout_seconds(timeout_ms: object) -> float:
    if timeout_ms is None:
        return _DEFAULT_TIMEOUT_SECONDS
    try:
        timeout_raw = float(timeout_ms)
    except Exception:
        return _DEFAULT_TIMEOUT_SECONDS
    if timeout_raw <= 0:
        return _DEFAULT_TIMEOUT_SECONDS
    timeout_seconds = timeout_raw / 1000.0
    return max(0.25, min(10.0, timeout_seconds))


def query_time_server_unix(
    server: str,
    *,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> float:
    clean_server = str(server or "").strip() or _DEFAULT_TIME_SERVER
    request = b"\x1b" + (b"\0" * (_NTP_PACKET_SIZE - 1))

    last_error: Exception | None = None
    for family, socktype, proto, _canonname, sockaddr in socket.getaddrinfo(
        clean_server,
        _NTP_PORT,
        type=socket.SOCK_DGRAM,
    ):
        try:
            with socket.socket(family, socktype, proto) as sock:
                sock.settimeout(timeout_seconds)
                sock.sendto(request, sockaddr)
                data, _peer = sock.recvfrom(_NTP_PACKET_SIZE)
        except Exception as exc:
            last_error = exc
            continue

        if len(data) < _NTP_PACKET_SIZE:
            raise RuntimeError("time server returned an incomplete response")

        transmit_seconds, transmit_fraction = struct.unpack("!II", data[40:48])
        unix_seconds = (
            float(transmit_seconds - _NTP_UNIX_EPOCH_DELTA_SECONDS)
            + (float(transmit_fraction) / float(1 << 32))
        )
        return unix_seconds

    if last_error is not None:
        raise RuntimeError(f"time server query failed: {last_error}")
    raise RuntimeError("time server query failed")


def resolve_time_sync(
    *,
    use_time_server: bool,
    server: object = None,
    timezone_name: object = None,
    timeout_ms: object = None,
    now_fn: Callable[[], float] = time.time,
    query_time_server_unix_fn: Callable[..., float] = query_time_server_unix,
) -> dict[str, object]:
    host_now = float(now_fn())
    host_unix = int(host_now)
    clean_timezone = normalize_time_sync_timezone(timezone_name)
    clean_server = str(server or "").strip() or _DEFAULT_TIME_SERVER
    timeout_seconds = _coerce_timeout_seconds(timeout_ms)

    if not use_time_server:
        return {
            "ok": True,
            "source": "host_clock",
            "timezone": clean_timezone,
            "server": "",
            "host_unix": host_unix,
            "applied_unix": host_unix,
            "applied_utc": _format_utc_text(host_unix),
            "applied_local": _format_timezone_text(host_unix, clean_timezone),
            "offset_seconds": 0.0,
        }

    try:
        server_unix_float = float(
            query_time_server_unix_fn(
                clean_server,
                timeout_seconds=timeout_seconds,
            )
        )
    except Exception as exc:
        return {
            "ok": False,
            "source": "time_server",
            "server": clean_server,
            "timezone": clean_timezone,
            "host_unix": host_unix,
            "error": str(exc),
        }

    applied_unix = int(server_unix_float)
    return {
        "ok": True,
        "source": "time_server",
        "server": clean_server,
        "timezone": clean_timezone,
        "host_unix": host_unix,
        "applied_unix": applied_unix,
        "applied_utc": _format_utc_text(applied_unix),
        "applied_local": _format_timezone_text(applied_unix, clean_timezone),
        "offset_seconds": round(server_unix_float - host_now, 6),
    }

