import html
import json
import os
import shutil
import subprocess

import pytest

from meshdash.html_css import build_dashboard_css


@pytest.mark.gui_benchmark
def test_profiled_roster_watermark_keeps_row_geometry_in_browser(
    request: pytest.FixtureRequest,
    tmp_path,
) -> None:
    enabled = bool(request.config.getoption("--run-gui-benchmark")) or (
        os.environ.get("MESH_GUI_BENCH_RUN", "").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    if not enabled:
        pytest.skip("set MESH_GUI_BENCH_RUN=1 or pass --run-gui-benchmark")
    chromium = shutil.which("chromium") or shutil.which("chromium-browser")
    if not chromium:
        pytest.skip("Chromium is required for the roster geometry regression probe")

    css = build_dashboard_css(theme_css="")
    rows = []
    for index in range(12):
        profiled = index == 5
        classes = "chat-member-item status-online" + (" profiled-node" if profiled else "")
        style = ""
        if profiled:
            style = (
                ' style="--node-profile-ghost-text:\'TEST\';'
                "--node-profile-ghost-opacity:.5;"
                "--node-profile-ghost-font-size:37px;"
                "--node-profile-ghost-anchor-x:70%;"
                "--node-profile-ghost-transform:rotate(-8deg) scale(1.14);"
                '"'
            )
        rows.append(
            f'<div id="row-{index}" class="{classes}"{style}>'
            '<span class="chat-member-status chat-member-status-dot status-online">●</span>'
            '<span class="chat-member-main"><span class="chat-member-name-row">'
            f'<span class="chat-member-name-left"><span class="chat-member-name">Node {index}</span></span>'
            "</span><span class=\"chat-member-meta-row\">Idle: 1m ago</span></span></div>"
        )

    probe_script = """
const row = document.getElementById("row-5");
const next = document.getElementById("row-6");
const normal = document.getElementById("row-4");
const rect = row.getBoundingClientRect();
const nextRect = next.getBoundingClientRect();
const result = {
  height: rect.height,
  normalHeight: normal.getBoundingClientRect().height,
  nextTop: nextRect.top,
  bottom: rect.bottom,
  flex: getComputedStyle(row).flex,
  overflow: getComputedStyle(row).overflow,
  watermarkContent: getComputedStyle(row, "::after").content,
  watermarkPosition: getComputedStyle(row, "::after").position,
};
document.getElementById("result").textContent = JSON.stringify(result);
"""
    probe_html = (
        "<!doctype html><meta charset=\"utf-8\"><style>"
        + css
        + "\n#probe-list{width:320px;height:64px;}</style>"
        + '<div id="probe-list" class="chat-member-list">'
        + "".join(rows)
        + '</div><pre id="result"></pre><script>'
        + probe_script
        + "</script>"
    )
    probe_path = tmp_path / "profiled_roster_watermark.html"
    probe_path.write_text(probe_html, encoding="utf-8")

    completed = subprocess.run(
        [
            chromium,
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            f"--user-data-dir={tmp_path / 'chromium-profile'}",
            "--dump-dom",
            probe_path.as_uri(),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        if "Operation not permitted" in completed.stderr:
            pytest.skip("Chromium launch is blocked by the current process sandbox")
        pytest.fail(
            f"Chromium roster geometry probe failed with exit {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )

    payload_text = completed.stdout.split('<pre id="result">', 1)[1].split("</pre>", 1)[0]
    payload = json.loads(html.unescape(payload_text))

    assert payload["flex"] == "0 0 auto"
    assert payload["overflow"] == "hidden"
    assert payload["height"] >= 26
    assert payload["height"] == payload["normalHeight"]
    assert payload["bottom"] <= payload["nextTop"] + 0.1
    assert payload["watermarkContent"] == '"TEST"'
    assert payload["watermarkPosition"] == "absolute"
