from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re


@dataclass(frozen=True)
class ExternalizedDashboardAssets:
    html_text: str
    assets: dict[str, tuple[str, bytes]]


_STYLE_BLOCK_RE = re.compile(
    r"(?P<block>\s*<!-- mesh-dashboard-style:start -->\s*"
    r"<style>\n(?P<payload>.*?)\n\s*</style>\s*"
    r"<!-- mesh-dashboard-style:end -->)",
    re.DOTALL,
)

_APP_BLOCK_RE = re.compile(
    r"(?P<block>\s*<!-- mesh-dashboard-app:start -->\s*"
    r"<script>\n(?P<payload>.*?)\n\s*</script>\s*"
    r"<!-- mesh-dashboard-app:end -->)",
    re.DOTALL,
)


def _asset_path(payload: bytes, suffix: str) -> str:
    digest = sha256(payload).hexdigest()[:12]
    return f"/assets/dashboard.{digest}.{suffix}"


def externalize_dashboard_assets(html_text: str) -> ExternalizedDashboardAssets:
    """Move generated CSS/JS out of the no-store HTML response when markers exist."""
    if not isinstance(html_text, str) or not html_text:
        return ExternalizedDashboardAssets(html_text=str(html_text or ""), assets={})

    updated_html = html_text
    assets: dict[str, tuple[str, bytes]] = {}

    style_match = _STYLE_BLOCK_RE.search(updated_html)
    if style_match:
        css_payload = style_match.group("payload").encode("utf-8")
        css_path = _asset_path(css_payload, "css")
        assets[css_path] = ("text/css; charset=utf-8", css_payload)
        updated_html = (
            updated_html[: style_match.start("block")]
            + f'\n  <link rel="stylesheet" href="{css_path}" />'
            + updated_html[style_match.end("block") :]
        )

    app_match = _APP_BLOCK_RE.search(updated_html)
    if app_match:
        js_payload = app_match.group("payload").encode("utf-8")
        js_path = _asset_path(js_payload, "js")
        assets[js_path] = ("application/javascript; charset=utf-8", js_payload)
        updated_html = (
            updated_html[: app_match.start("block")]
            + f'\n  <script src="{js_path}"></script>'
            + updated_html[app_match.end("block") :]
        )

    return ExternalizedDashboardAssets(html_text=updated_html, assets=assets)
