import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

pytest.importorskip("playwright.sync_api")
spec = importlib.util.spec_from_file_location(
    "mobile_preview", Path(__file__).resolve().parents[1] / "scripts" / "mobile_preview.py"
)
preview = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = preview
spec.loader.exec_module(preview)


@pytest.mark.parametrize("view", ['network:bogus', 'chat:map', 'games:settings', 'network:../../bad'])
def test_reject_invalid_subviews(view):
    with pytest.raises(ValueError):
        preview.ViewSpec.parse(view)


@pytest.mark.parametrize("device", ["0x800", "400x0", "400x800@nan", "400x800@-1"])
def test_reject_invalid_custom_device_dimensions(device):
    with pytest.raises(ValueError):
        preview.parse_device(SimpleNamespace(devices={}), device, landscape=False)


def test_report_escapes_url_error_and_labels(tmp_path):
    attack = '<script>alert("x")</script>'
    result = preview.ViewResult(device=attack, view=attack, error=attack)
    sheet = preview.write_contact_sheet(tmp_path, [result], SimpleNamespace(url=attack, api_from=attack))
    text = sheet.read_text()
    assert "<script>" not in text
    assert "&lt;script&gt;" in text


def test_empty_view_list_does_not_produce_successful_empty_report():
    with pytest.raises(SystemExit):
        preview.parse_args(["--views", " , "])


def test_custom_device_landscape():
    _, descriptor = preview.parse_device(SimpleNamespace(devices={}), "400x800@3", landscape=True)
    assert descriptor["viewport"] == {"width": 800, "height": 400}
    assert descriptor["device_scale_factor"] == 3


@pytest.mark.gui_benchmark
def test_audit_distinguishes_scroller_contents_from_real_overflow(request):
    if not request.config.getoption("--run-gui-benchmark"):
        pytest.skip("pass --run-gui-benchmark to run Chromium checks")
    with preview.sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=preview.find_browser(None), args=["--no-sandbox"])
        try:
            page = browser.new_page(viewport={"width": 400, "height": 800})
            page.set_content('<div style="width:200px;overflow-x:auto"><div id="ticker" style="width:1200px;height:20px">ticker</div></div>'
                             '<div id="real-overflow" style="width:700px;height:20px">overflow</div>')
            audit = page.evaluate(preview.AUDIT_JS)
            selectors = {entry["sel"] for entry in audit["overflow"]}
            assert "div#ticker" not in selectors
            assert "div#real-overflow" in selectors
            assert audit["horizontalPageOverflow"]
        finally:
            browser.close()


@pytest.mark.gui_benchmark
def test_boot_failure_is_retained_as_a_report_result(request, tmp_path):
    if not request.config.getoption("--run-gui-benchmark"):
        pytest.skip("pass --run-gui-benchmark to run Chromium checks")
    args = preview.parse_args(["--url", "data:text/html,broken", "--timeout", "1", "--settle-ms", "0"])
    with preview.sync_playwright() as pw:
        results = preview.audit_device(pw, args, preview.find_browser(None), "400x800",
                                       [preview.ViewSpec.parse("chat")], tmp_path)
    assert len(results) == 1
    assert results[0].view == "boot"
    assert not results[0].ok
    assert results[0].error
