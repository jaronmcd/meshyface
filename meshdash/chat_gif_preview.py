from functools import lru_cache
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


_TENOR_PAGE_HOSTS = {"tenor.com", "www.tenor.com"}
_TENOR_MEDIA_HOSTS = {"media.tenor.com", "media1.tenor.com", "c.tenor.com"}
_TENOR_PAGE_PATH = re.compile(r"/(?:[A-Za-z0-9]{1,32}\.gif|view/[A-Za-z0-9%'-]+-\d+)/?\Z")
_MAX_PAGE_BYTES = 512 * 1024


def _checked_url(value: str, hosts: set[str]) -> str:
    if len(value) > 2048 or any(ord(char) < 33 for char in value):
        raise ValueError("Invalid GIF URL")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in hosts
        or parsed.port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("Unsupported GIF host")
    return urlunsplit(("https", parsed.hostname, parsed.path, "", ""))


def normalize_tenor_page_url(value: str) -> str:
    url = _checked_url(value, _TENOR_PAGE_HOSTS)
    if not _TENOR_PAGE_PATH.fullmatch(urlsplit(url).path):
        raise ValueError("Unsupported Tenor share URL")
    return url


class _TenorRedirectHandler(HTTPRedirectHandler):
    max_redirections = 3

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked = normalize_tenor_page_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, checked)


class _GifMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.image_url = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        fields = dict(attrs)
        if fields.get("property") != "og:image":
            return
        try:
            image_url = _checked_url(fields.get("content") or "", _TENOR_MEDIA_HOSTS)
        except ValueError:
            return
        if urlsplit(image_url).path.lower().endswith(".gif"):
            self.image_url = image_url


@lru_cache(maxsize=256)
def _resolve_tenor_gif(page_url: str) -> str:
    request = Request(page_url, headers={"User-Agent": "Meshyface", "Accept": "text/html"})
    opener = build_opener(_TenorRedirectHandler())
    with opener.open(request, timeout=5) as response:
        normalize_tenor_page_url(response.geturl())
        if response.headers.get_content_type() != "text/html":
            raise ValueError("Tenor preview page is unavailable")
        page = response.read(_MAX_PAGE_BYTES + 1)
        if len(page) > _MAX_PAGE_BYTES:
            raise ValueError("Tenor preview page is too large")
    parser = _GifMetadataParser()
    parser.feed(page.decode("utf-8", errors="replace"))
    if not parser.image_url:
        raise ValueError("Tenor GIF is unavailable")
    return parser.image_url


def resolve_tenor_gif(value: str) -> str:
    return _resolve_tenor_gif(normalize_tenor_page_url(value))
