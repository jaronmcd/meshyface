from __future__ import annotations

import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from meshdash.html_css import build_dashboard_css  # noqa: E402
from meshdash.html_js import build_dashboard_js  # noqa: E402
from meshdash.html_sections import build_html_shell  # noqa: E402


DEFAULT_DASHBOARD_JS_KWARGS = {
    "refresh_ms": 1000,
    "node_history_hours": 24,
    "node_history_max_points": 240,
}

DEFAULT_DASHBOARD_HTML_KWARGS = {
    "app_title": "Meshyface",
    "app_heading": "Meshyface",
    "style_css": "",
    "app_js": "",
    "revision_title": "rev",
    "revision_label": "rev",
    "safety_label": "safe",
    "packet_limit": 100,
    "history_label": "history",
    "refresh_ms": 1000,
}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-gui-benchmark",
        action="store_true",
        default=False,
        help="Run the local headless browser GUI responsiveness benchmark.",
    )


@pytest.fixture(scope="session")
def dashboard_js_factory() -> Callable[..., str]:
    def _build(**overrides: object) -> str:
        return build_dashboard_js(**(DEFAULT_DASHBOARD_JS_KWARGS | overrides))

    return _build


@pytest.fixture(scope="session")
def dashboard_css_factory() -> Callable[..., str]:
    def _build(**overrides: object) -> str:
        return build_dashboard_css(theme_css="", **overrides)

    return _build


@pytest.fixture(scope="session")
def dashboard_html_factory() -> Callable[..., str]:
    def _build(**overrides: object) -> str:
        return build_html_shell(**(DEFAULT_DASHBOARD_HTML_KWARGS | overrides))

    return _build


@pytest.fixture
def dashboard_js(dashboard_js_factory: Callable[..., str]) -> str:
    return dashboard_js_factory()


@pytest.fixture
def dashboard_css(dashboard_css_factory: Callable[..., str]) -> str:
    return dashboard_css_factory()


@pytest.fixture
def dashboard_html(dashboard_html_factory: Callable[..., str]) -> str:
    return dashboard_html_factory()


@pytest.fixture(scope="session")
def template_text() -> Callable[[str], str]:
    def _read(relative_path: str) -> str:
        return (REPO_ROOT / relative_path).read_text(encoding="utf-8")

    return _read


@pytest.fixture(scope="session")
def assert_tokens_present() -> Callable[[str, Sequence[str]], None]:
    def _assert(rendered_text: str, tokens: Sequence[str]) -> None:
        missing = [token for token in tokens if token not in rendered_text]
        assert not missing, "Missing expected tokens:\n" + "\n".join(missing)

    return _assert


@pytest.fixture(scope="session")
def extract_css_block() -> Callable[[str, str], str]:
    def _extract(css_text: str, selector: str) -> str:
        match = re.search(rf"(?m)(^|}})\s*{re.escape(selector)}\s*(?:,|\{{)", css_text)
        if not match:
            raise AssertionError(f"Unable to locate CSS block for selector: {selector}")
        block_start = css_text.find("{", match.start())
        if block_start < 0:
            raise AssertionError(f"Unable to locate CSS block for selector: {selector}")
        block_end = css_text.find("}", block_start)
        if block_end < 0:
            raise AssertionError(f"Unable to locate CSS block for selector: {selector}")
        return css_text[block_start + 1:block_end]

    return _extract
