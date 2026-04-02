import gzip
import json
from collections.abc import Mapping
from typing import Optional

from .http_handler_contracts import DashboardHttpHandler


def json_bytes(payload_obj: object) -> bytes:
    return json.dumps(payload_obj, separators=(",", ":")).encode("utf-8")


def _header_value(headers: Mapping[str, object], name: str) -> str:
    """Fetch a header value from a Mapping with best-effort case handling."""
    try:
        direct = headers.get(name)  # type: ignore[attr-defined]
    except Exception:
        direct = None
    if direct is not None:
        return str(direct)
    name_l = name.lower()
    for key, value in headers.items():
        try:
            if str(key).lower() == name_l:
                return str(value)
        except Exception:
            continue
    return ""


def _gzip_if_accepted(
    handler: DashboardHttpHandler,
    payload: bytes,
    *,
    min_size: int = 1024,
    level: int = 5,
) -> tuple[bytes, Optional[str]]:
    """Return (payload, content_encoding) where content_encoding is 'gzip' or None."""
    try:
        if len(payload) < min_size:
            return payload, None
        accept_encoding = _header_value(handler.headers, "Accept-Encoding")
        if "gzip" not in accept_encoding.lower():
            return payload, None
        compressed = gzip.compress(payload, compresslevel=level)
        # Don't bother if we didn't materially shrink.
        if len(compressed) >= int(len(payload) * 0.98):
            return payload, None
        return compressed, "gzip"
    except Exception:
        return payload, None


def write_json_response(
    handler: DashboardHttpHandler,
    *,
    status_code: int,
    payload_obj: object,
    no_store: bool = False,
    extra_headers: Optional[Mapping[str, str]] = None,
) -> None:
    payload = json_bytes(payload_obj)
    payload, content_encoding = _gzip_if_accepted(handler, payload)
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    if no_store:
        handler.send_header("Cache-Control", "no-store")
    if extra_headers:
        for key, value in extra_headers.items():
            handler.send_header(str(key), str(value))
    if content_encoding:
        handler.send_header("Content-Encoding", content_encoding)
        handler.send_header("Vary", "Accept-Encoding")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def write_html_response(
    handler: DashboardHttpHandler,
    *,
    html_text: str,
    no_store: bool = False,
    extra_headers: Optional[Mapping[str, str]] = None,
) -> None:
    payload = html_text.encode("utf-8")
    payload, content_encoding = _gzip_if_accepted(handler, payload)
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    if no_store:
        handler.send_header("Cache-Control", "no-store")
    if extra_headers:
        for key, value in extra_headers.items():
            handler.send_header(str(key), str(value))
    if content_encoding:
        handler.send_header("Content-Encoding", content_encoding)
        handler.send_header("Vary", "Accept-Encoding")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def write_text_response(
    handler: DashboardHttpHandler,
    *,
    status_code: int,
    text: str,
    extra_headers: Optional[Mapping[str, str]] = None,
) -> None:
    payload = text.encode("utf-8")
    payload, content_encoding = _gzip_if_accepted(handler, payload)
    handler.send_response(status_code)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    if extra_headers:
        for key, value in extra_headers.items():
            handler.send_header(str(key), str(value))
    if content_encoding:
        handler.send_header("Content-Encoding", content_encoding)
        handler.send_header("Vary", "Accept-Encoding")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)
