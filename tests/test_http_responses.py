import io
import json

from meshdash import http_responses as responses
from meshdash.http_responses import (
    _gzip_if_accepted,
    _header_value,
    write_html_response,
    write_json_response,
    write_text_response,
)


class _FakeHandler:
    def __init__(self):
        self.wfile = io.BytesIO()
        self.status = None
        self.headers = []
        self._header_map = {}
        self.ended = False

    def send_response(self, status_code):
        self.status = status_code

    def send_header(self, key, value):
        self.headers.append((key, value))
        self._header_map[key] = value

    def end_headers(self):
        self.ended = True


def test_write_json_response_sets_headers_and_payload():
    handler = _FakeHandler()
    write_json_response(handler, status_code=200, payload_obj={"ok": True}, no_store=True)

    assert handler.status == 200
    assert ("Content-Type", "application/json; charset=utf-8") in handler.headers
    assert ("Cache-Control", "no-store") in handler.headers
    assert handler.ended is True
    assert json.loads(handler.wfile.getvalue().decode("utf-8")) == {"ok": True}


def test_write_html_response_sets_headers_and_payload():
    handler = _FakeHandler()
    write_html_response(handler, html_text="<html>ok</html>", no_store=True)

    assert handler.status == 200
    assert ("Content-Type", "text/html; charset=utf-8") in handler.headers
    assert ("Cache-Control", "no-store") in handler.headers
    assert handler.wfile.getvalue() == b"<html>ok</html>"


def test_write_text_response_sets_headers_and_payload():
    handler = _FakeHandler()
    write_text_response(handler, status_code=404, text="Not Found")

    assert handler.status == 404
    assert ("Content-Type", "text/plain; charset=utf-8") in handler.headers
    assert handler.wfile.getvalue() == b"Not Found"


def test_header_value_reads_direct_and_case_insensitive_entries():
    assert _header_value({"Accept-Encoding": "gzip"}, "Accept-Encoding") == "gzip"
    assert _header_value({"ACCEPT-encoding": "gzip"}, "Accept-Encoding") == "gzip"

    class _BadKey:
        def __str__(self):
            raise RuntimeError("bad key")

    class _BadMapping(dict):
        def get(self, _name):
            raise RuntimeError("bad get")

        def items(self):
            return [(_BadKey(), "x"), ("accept-encoding", "gzip, br")]

    assert _header_value(_BadMapping(), "Accept-Encoding") == "gzip, br"


def test_gzip_if_accepted_branches(monkeypatch):
    class _Handler:
        def __init__(self, headers):
            self.headers = headers

    payload = b"x" * 2000
    small_payload, small_encoding = _gzip_if_accepted(_Handler({"Accept-Encoding": "gzip"}), b"abc")
    assert small_payload == b"abc"
    assert small_encoding is None

    plain_payload, plain_encoding = _gzip_if_accepted(_Handler({"Accept-Encoding": "identity"}), payload)
    assert plain_payload == payload
    assert plain_encoding is None

    monkeypatch.setattr(responses.gzip, "compress", lambda data, compresslevel=5: data)
    unchanged_payload, unchanged_encoding = _gzip_if_accepted(_Handler({"Accept-Encoding": "gzip"}), payload)
    assert unchanged_payload == payload
    assert unchanged_encoding is None

    monkeypatch.setattr(
        responses.gzip,
        "compress",
        lambda data, compresslevel=5: (_ for _ in ()).throw(RuntimeError("zip fail")),
    )
    errored_payload, errored_encoding = _gzip_if_accepted(_Handler({"Accept-Encoding": "gzip"}), payload)
    assert errored_payload == payload
    assert errored_encoding is None

    monkeypatch.setattr(
        responses.gzip,
        "compress",
        lambda data, compresslevel=5: b"small",
    )
    gz_payload, gz_encoding = _gzip_if_accepted(_Handler({"Accept-Encoding": "gzip"}), payload)
    assert gz_payload == b"small"
    assert gz_encoding == "gzip"


def test_write_response_helpers_emit_extra_headers_and_gzip(monkeypatch):
    handler = _FakeHandler()

    monkeypatch.setattr(
        responses,
        "_gzip_if_accepted",
        lambda _handler, payload: (b"gz:" + payload, "gzip"),
    )

    write_json_response(
        handler,
        status_code=201,
        payload_obj={"ok": True},
        no_store=True,
        extra_headers={"X-Test": "1"},
    )
    assert ("X-Test", "1") in handler.headers
    assert ("Content-Encoding", "gzip") in handler.headers
    assert ("Vary", "Accept-Encoding") in handler.headers
    assert ("Cache-Control", "no-store") in handler.headers

    handler_html = _FakeHandler()
    write_html_response(handler_html, html_text="<h1>x</h1>", extra_headers={"X-HTML": "1"})
    assert ("X-HTML", "1") in handler_html.headers
    assert ("Content-Encoding", "gzip") in handler_html.headers

    handler_text = _FakeHandler()
    write_text_response(handler_text, status_code=418, text="teapot", extra_headers={"X-TEXT": "1"})
    assert ("X-TEXT", "1") in handler_text.headers
    assert ("Content-Encoding", "gzip") in handler_text.headers
