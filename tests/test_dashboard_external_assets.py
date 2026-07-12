import gzip
import io

from meshdash.http_api_get import build_get_route_dependencies
from meshdash.http_routes_get import handle_dashboard_get
from meshdash.html_external_assets import externalize_dashboard_assets


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


def _dashboard_html(*, css: str = "body { color: red; }", js: str = "console.log('ok');") -> str:
    return f"""<!doctype html>
<html>
<head>
  <!-- mesh-dashboard-style:start -->
  <style>
{css}
  </style>
  <!-- mesh-dashboard-style:end -->
</head>
<body>
  <!-- mesh-dashboard-app:start -->
  <script>
{js}
  </script>
  <!-- mesh-dashboard-app:end -->
</body>
</html>"""


def test_externalize_dashboard_assets_leaves_unmarked_html_untouched() -> None:
    html = "<html><body>plain</body></html>"

    result = externalize_dashboard_assets(html)

    assert result.html_text == html
    assert result.assets == {}


def test_get_route_dependencies_externalize_generated_dashboard_css_and_js() -> None:
    html = _dashboard_html()

    deps = build_get_route_dependencies(
        html_text=html,
        state_fn=lambda: {},
        node_history_fn=None,
        default_node_history_hours=24,
    )

    asset_map = deps.dashboard_asset_map or {}
    css_path = next(path for path in asset_map if path.endswith(".css"))
    js_path = next(path for path in asset_map if path.endswith(".js"))

    assert "<style>" not in deps.html_text
    assert "<script>\nconsole.log" not in deps.html_text
    assert f'href="{css_path}"' in deps.html_text
    assert f'src="{js_path}"' in deps.html_text
    assert asset_map[css_path] == ("text/css; charset=utf-8", b"body { color: red; }")
    assert asset_map[js_path] == ("application/javascript; charset=utf-8", b"console.log('ok');")


def test_dashboard_asset_route_serves_fingerprinted_asset_with_cache_headers() -> None:
    css = "body { color: red; }\n" * 200
    deps = build_get_route_dependencies(
        html_text=_dashboard_html(css=css),
        state_fn=lambda: {},
        node_history_fn=None,
        default_node_history_hours=24,
    )
    css_path = next(path for path in (deps.dashboard_asset_map or {}) if path.endswith(".css"))
    handler = _Handler(headers={"Accept-Encoding": "br, gzip"})

    handle_dashboard_get(handler, path=css_path, query="", deps=deps)

    headers = handler.header_dict()
    assert handler.status_code == 200
    assert handler.ended is True
    assert headers["Content-Type"] == "text/css; charset=utf-8"
    assert headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Content-Encoding"] == "gzip"
    assert headers["Vary"] == "Accept-Encoding"
    assert int(headers["Content-Length"]) == len(handler.wfile.getvalue())
    assert gzip.decompress(handler.wfile.getvalue()).decode("utf-8") == css.rstrip("\n")


def test_vendor_particles_asset_route_serves_bundled_script() -> None:
    deps = build_get_route_dependencies(
        html_text=_dashboard_html(),
        state_fn=lambda: {},
        node_history_fn=None,
        default_node_history_hours=24,
    )
    handler = _Handler()

    handle_dashboard_get(handler, path="/assets/vendor/particles-2.0.0.min.js", query="", deps=deps)

    headers = handler.header_dict()
    payload = handler.wfile.getvalue()
    assert handler.status_code == 200
    assert handler.ended is True
    assert headers["Content-Type"] == "application/javascript; charset=utf-8"
    assert headers["Cache-Control"] == "public, max-age=86400"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert int(headers["Content-Length"]) == len(payload)
    assert b"Vincent Garreau" in payload
    assert b"particlesJS" in payload
