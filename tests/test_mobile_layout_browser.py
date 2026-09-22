"""Optional real-browser guards for mobile sizing and navigation."""
import importlib.util
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

pw_api = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def mobile_server(request, tmp_path_factory):
    if not request.config.getoption("--run-gui-benchmark"):
        pytest.skip("pass --run-gui-benchmark for mobile browser checks")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    temp = tmp_path_factory.mktemp("mobile-layout")
    with (temp / "server.log").open("w") as log:
        process = subprocess.Popen(
            [sys.executable, str(ROOT / "mesh_dashboard.py"), "--mesh-host", "127.0.0.1",
             "--mesh-tcp-port", "1", "--http-host", "127.0.0.1", "--http-port", str(port),
             "--history-db", str(temp / "history.sqlite3")], cwd=ROOT, stdout=log, stderr=log,
        )
        url = f"http://127.0.0.1:{port}/"
        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen(url + "api/version", timeout=1):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                pytest.fail("Mobile test server did not start")
            yield url
        finally:
            process.terminate()
            process.wait(timeout=10)


def module_from_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.gui_benchmark
@pytest.mark.parametrize("width,theme", [(320, "light"), (390, "dark"), (412, "light"), (1280, "light")])
def test_mobile_surfaces_and_controls_fit(mobile_server, tmp_path, width, theme):
    preview = module_from_script("mobile_preview")
    benchmark = module_from_script("benchmark_gui_realtime")
    state = benchmark.build_synthetic_state(50)
    state["nodes"][1]["long_name"] = "Long node name " * 12
    state["traffic"]["recent_chat"][0]["text"] = "LongMessage" * 80
    with pw_api.sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=preview.find_browser(None), args=["--no-sandbox"])
        try:
            context = browser.new_context(viewport={"width": width, "height": 800},
                                          is_mobile=width < 760, has_touch=width < 760, color_scheme=theme)
            context.route("**/api/state*", lambda route: route.fulfill(json=state))
            page = context.new_page()
            page.goto(mobile_server)
            preview.wait_for_boot(page, 15000)
            page.wait_for_timeout(800)
            def fits(selector):
                rect = page.locator(selector).first.bounding_box()
                assert rect is not None, selector
                assert rect["x"] >= -1 and rect["x"] + rect["width"] <= width + 1, (selector, rect)
                return rect
            fits("#dashboard-layout")
            fits("#chat-input")
            fits("#chat-send-btn")
            if width < 760:
                page.locator("#summary-ticker-density-toggle").click()
                assert page.locator(".topbar").evaluate("el => el.classList.contains('ticker-expanded')")
                page.locator("#summary-ticker-density-toggle").click()
                assert page.locator("#mesh-channel-select").is_visible()
                page.select_option("#mesh-channel-select", "-1")
                assert page.evaluate("activeMeshChannelIndex") == -1
                before = fits(".chat-log-scroll")
                page.locator("#chat-panel-collapse-btn").click()
                assert page.locator("#chat-user-search-input").is_visible()
                after = fits(".chat-log-scroll")
                assert abs(before["height"] - after["height"]) < 2
                fits(".chat-users-section")
                page.locator("#chat-panel-collapse-btn").click()
                assert not page.locator("#chat-user-search-input").is_visible()
                page.locator("#chat-input").focus()
                page.set_viewport_size({"width": width, "height": 420})
                page.wait_for_timeout(300)
                composer = fits("#chat-send-btn")
                assert composer["y"] + composer["height"] <= 421
                page.set_viewport_size({"width": width, "height": 800})
                page.locator("#chat-input").blur()
                page.wait_for_timeout(300)
            else:
                assert not page.locator("#mesh-channel-select").is_visible()
                assert page.locator("#mesh-channel-pill-strip").is_visible()
            page.screenshot(path=str(tmp_path / f"chat-{width}.png"))
            preview.switch_view(page, preview.ViewSpec.parse("network:map"), timeout_ms=10000)
            page.wait_for_timeout(500)
            for selector in ("#dashboard-layout", ".map-frame", "#map", "#network-map-chrome"):
                fits(selector)
            if width < 760:
                assert page.locator(".map-link-legend-collapsed-btn").is_visible()
                page.locator(".map-link-legend-collapsed-btn").click(timeout=3000)
                assert page.locator(".map-link-legend-list").is_visible()
                fits(".map-link-legend")
                page.locator(".map-link-legend-collapse-btn").click()
            assert not page.locator("#network-map-panel-diagnostics").is_visible()
            frame = fits(".map-frame")
            map_rect = fits("#map")
            chrome_rect = fits("#network-map-chrome")
            assert map_rect["height"] >= max(300, frame["height"] - 8), (frame, map_rect)
            assert chrome_rect["y"] >= frame["y"], (frame, chrome_rect)
            page.screenshot(path=str(tmp_path / f"map-{width}.png"))
        finally:
            browser.close()
