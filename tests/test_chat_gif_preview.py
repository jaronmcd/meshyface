from email.message import Message
from io import BytesIO
from types import SimpleNamespace
from urllib.parse import urlencode
from urllib.request import Request

import pytest

from meshdash import chat_gif_preview as preview
from meshdash import http_routes_get as routes
from meshdash.http_responses import write_text_response


SHARE_URL = "https://tenor.com/iT6gMPRoaCs.gif"
VIEW_URL = "https://tenor.com/view/i-don%27t-know-idk-gif-7336250873949261946"
IMAGE_URL = "https://media1.tenor.com/m/Zc-ZTPzlEHoAAAAC/i-don%27t-know-idk.gif"


@pytest.fixture(autouse=True)
def clear_preview_cache():
    preview._resolve_tenor_gif.cache_clear()
    yield
    preview._resolve_tenor_gif.cache_clear()


class _Page(BytesIO):
    def __init__(self, body: bytes, content_type: str = "text/html") -> None:
        super().__init__(body)
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def geturl(self) -> str:
        return VIEW_URL


def test_resolver_uses_gif_metadata_and_caches_equivalent_share_urls(monkeypatch):
    calls = []

    def open_page(request, *, timeout):
        calls.append((request.full_url, timeout))
        return _Page(f'<meta property="og:image" content="{IMAGE_URL}">'.encode())

    monkeypatch.setattr(preview, "build_opener", lambda *_: SimpleNamespace(open=open_page))
    assert preview.resolve_tenor_gif(SHARE_URL + "?utm_source=share#preview") == IMAGE_URL
    assert preview.resolve_tenor_gif(SHARE_URL) == IMAGE_URL
    assert calls == [(SHARE_URL, 5)]


@pytest.mark.parametrize("url", [
    "https://127.0.0.1/test.gif",
    "https://tenor.com.evil.example/test.gif",
    "https://tenor.com@127.0.0.1/test.gif",
    "https://user:secret@tenor.com/test.gif",
    "https://tenor.com:8443/test.gif",
    "http://tenor.com/test.gif",
    "file:///tmp/test.gif",
    "https://tenor.com/search/cats",
    "https://tenor.com/test.gif\r\nX-Test: header",
    "https://tenor.com/" + "x" * 2050 + ".gif",
])
def test_resolver_rejects_unsupported_urls_before_network_access(monkeypatch, url):
    def unexpected_open(*_):
        pytest.fail("Invalid URL caused a network request")

    monkeypatch.setattr(preview, "build_opener", unexpected_open)
    with pytest.raises(ValueError):
        preview.resolve_tenor_gif(url)


def test_redirects_stay_on_tenor_share_pages():
    redirect = preview._TenorRedirectHandler()
    request = Request(SHARE_URL)
    allowed = redirect.redirect_request(request, None, 302, "Found", {}, VIEW_URL)
    assert allowed.full_url == VIEW_URL
    for url in ("https://127.0.0.1/secret", "https://evil.example/test.gif", "http://tenor.com/test.gif"):
        with pytest.raises(ValueError):
            redirect.redirect_request(request, None, 302, "Found", {}, url)


@pytest.mark.parametrize("body,content_type", [
    (b'<meta property="og:image" content="http://127.0.0.1/secret.gif">', "text/html"),
    (b'<meta property="og:image" content="https://evil.example/test.gif">', "text/html"),
    (b'<meta property="og:image" content="https://media.tenor.com/test.png">', "text/html"),
    (b"no metadata", "text/html"),
    (b"x" * (512 * 1024 + 1), "text/html"),
    (b"GIF89a", "image/gif"),
])
def test_resolver_rejects_missing_unsafe_or_oversized_metadata(monkeypatch, body, content_type):
    monkeypatch.setattr(preview, "build_opener", lambda *_: SimpleNamespace(
        open=lambda *args, **kwargs: _Page(body, content_type),
    ))
    with pytest.raises(ValueError):
        preview.resolve_tenor_gif(SHARE_URL)


class _Handler:
    def __init__(self):
        self.headers = {}
        self.response_headers = {}
        self.wfile = BytesIO()
        self.status = None

    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        self.response_headers[key] = value

    def end_headers(self):
        pass


@pytest.mark.parametrize("private,url,error,status", [
    (False, SHARE_URL, None, 302),
    (True, SHARE_URL, None, 404),
    (False, "https://127.0.0.1/test.gif", None, 400),
    (False, SHARE_URL, TimeoutError("offline"), 502),
    (False, SHARE_URL, ValueError("missing metadata"), 502),
])
def test_preview_route_redirects_or_fails_without_leaking_details(monkeypatch, private, url, error, status):
    calls = []

    def resolve(value):
        calls.append(value)
        if error:
            raise error
        return IMAGE_URL

    monkeypatch.setattr(routes, "resolve_tenor_gif", resolve)
    handler = _Handler()
    deps = SimpleNamespace(private_mode=private, api_metrics=None, write_text_response_fn=write_text_response)
    routes.handle_dashboard_get(
        handler, path="/api/chat/gif-preview", query=urlencode({"url": url}), deps=deps,
    )
    assert handler.status == status
    assert calls == ([] if status in {400, 404} else [SHARE_URL])
    if status == 302:
        assert handler.response_headers["Location"] == IMAGE_URL
        assert handler.response_headers["Content-Length"] == "0"
        assert handler.wfile.getvalue() == b""
    else:
        assert "Location" not in handler.response_headers
        assert b"offline" not in handler.wfile.getvalue()
