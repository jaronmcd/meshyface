import gzip
import io
import json
import random

import pytest

from meshdash.http_responses import (
    _gzip_if_accepted,
    _header_value,
    json_bytes,
    write_html_response,
    write_json_response,
    write_text_response,
)


class _Handler:
    def __init__(self, *, headers: dict[str, object] | None = None) -> None:
        self.headers = headers or {}
        self.status_code: int | None = None
        self.sent_headers: list[tuple[str, str]] = []
        self.ended = False
        self.wfile = io.BytesIO()

    def send_response(self, code: int) -> None:
        self.status_code = code

    def send_header(self, key: str, value: str) -> None:
        self.sent_headers.append((key, value))

    def end_headers(self) -> None:
        self.ended = True

    def header_dict(self) -> dict[str, str]:
        return dict(self.sent_headers)


def test_json_bytes_and_header_lookup_are_compact_and_case_insensitive() -> None:
    assert json_bytes({"b": 2, "a": [1, True]}) == b'{"b":2,"a":[1,true]}'
    assert _header_value({"accept-encoding": "gzip"}, "Accept-Encoding") == "gzip"
    assert _header_value({"Accept-Encoding": "br"}, "Accept-Encoding") == "br"
    assert _header_value({"Other": "x"}, "Accept-Encoding") == ""


def test_gzip_if_accepted_checks_size_acceptance_and_compression_ratio(monkeypatch: pytest.MonkeyPatch) -> None:
    small_handler = _Handler(headers={"Accept-Encoding": "gzip"})
    assert _gzip_if_accepted(small_handler, b"x" * 10) == (b"x" * 10, None)

    no_accept_handler = _Handler(headers={"Accept-Encoding": "br"})
    assert _gzip_if_accepted(no_accept_handler, b"x" * 2048) == (b"x" * 2048, None)

    gzip_handler = _Handler(headers={"Accept-Encoding": "br, gzip"})
    compressed, encoding = _gzip_if_accepted(gzip_handler, b"x" * 2048)
    assert encoding == "gzip"
    assert gzip.decompress(compressed) == b"x" * 2048

    compact_payload = bytes(random.Random(0).randrange(256) for _ in range(2048))
    monkeypatch.setattr(gzip, "compress", lambda payload, *, compresslevel=5: payload)
    already_compact, compact_encoding = _gzip_if_accepted(gzip_handler, compact_payload)
    assert compact_encoding is None
    assert already_compact == compact_payload


def test_write_json_response_sets_headers_body_and_optional_gzip() -> None:
    handler = _Handler(headers={"Accept-Encoding": "gzip"})
    payload = {"message": "x" * 2000}

    write_json_response(
        handler,
        status_code=201,
        payload_obj=payload,
        no_store=True,
        extra_headers={"X-Test": "yes"},
    )

    headers = handler.header_dict()
    body = handler.wfile.getvalue()
    assert handler.status_code == 201
    assert handler.ended is True
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Test"] == "yes"
    assert headers["Content-Encoding"] == "gzip"
    assert headers["Vary"] == "Accept-Encoding"
    assert int(headers["Content-Length"]) == len(body)
    assert json.loads(gzip.decompress(body).decode("utf-8")) == payload


def test_write_html_and_text_responses_set_content_types_and_bodies() -> None:
    html_handler = _Handler()
    text_handler = _Handler(headers={"Accept-Encoding": "gzip"})

    write_html_response(
        html_handler,
        html_text="<html>ok</html>",
        no_store=True,
        extra_headers={"X-Frame-Options": "DENY"},
    )
    write_text_response(
        text_handler,
        status_code=404,
        text="not found",
        extra_headers={"X-Reason": "missing"},
    )

    html_headers = html_handler.header_dict()
    text_headers = text_handler.header_dict()
    assert html_handler.status_code == 200
    assert html_headers["Content-Type"] == "text/html; charset=utf-8"
    assert html_headers["Cache-Control"] == "no-store"
    assert html_headers["X-Frame-Options"] == "DENY"
    assert html_handler.wfile.getvalue() == b"<html>ok</html>"

    assert text_handler.status_code == 404
    assert text_headers["Content-Type"] == "text/plain; charset=utf-8"
    assert text_headers["X-Reason"] == "missing"
    assert text_handler.wfile.getvalue() == b"not found"
