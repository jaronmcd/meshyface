import json
import shutil
import subprocess

import pytest

from meshdash.html_js import build_dashboard_js


def _function_block(source: str, start: str, end: str) -> str:
    return start + source.split(start, 1)[1].split(end, 1)[0]


def test_chat_received_timeline_contract_in_browser(tmp_path) -> None:
    chromium = shutil.which("chromium") or shutil.which("chromium-browser")
    if not chromium:
        pytest.skip("Chromium is required for the JavaScript timeline contract probe")

    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    parse_time = _function_block(
        js,
        "function parseDashboardTimeToMs(value) {",
        "function parseDashboardTimeToUnix",
    )
    parse_message_id = _function_block(
        js,
        "function parsePositiveMessageId(value) {",
        "function messageIdAliasKeys",
    )
    received_helpers = _function_block(
        js,
        "function firstValidTimestampMs(...values) {",
        "function nestedPathValue",
    )

    rows = [
        {"id": "unknown-1"},
        {
            "id": "capture-first",
            "captured_at": "2026-06-03 00:00:01Z",
            "rx_time": "2026-06-03 00:02:00Z",
        },
        {
            "id": "capture-second",
            "captured_at": "2026-06-03 00:00:02Z",
            "rx_time": "2026-06-03 00:01:00Z",
        },
        {"id": "fallback-first", "rx_time": "2026-06-03 00:00:03Z"},
        {"id": "fallback-second", "rx_time": "2026-06-03 00:00:04Z"},
        {"id": "tie-b", "captured_at": "2026-06-03 00:00:05Z"},
        {"id": "tie-a", "captured_at": "2026-06-03 00:00:05Z"},
        {
            "id": "history-later",
            "captured_at": "2026-06-03 00:00:06Z",
            "_history_id": 20,
        },
        {
            "id": "history-earlier",
            "captured_at": "2026-06-03 00:00:06Z",
            "_history_id": 10,
        },
        {"id": "unknown-2"},
    ]
    html = f"""<!doctype html><meta charset=\"utf-8\"><pre id=\"result\"></pre><script>
{parse_time}
{parse_message_id}
{received_helpers}
const rows = {json.dumps(rows)};
const replyRows = chatMessagesInReceivedTimelineOrder([
  {{
    message_id: 501,
    reply_id: 500,
    text: "child received first",
    captured_at: "2026-06-03 00:00:07Z",
    rx_time: "2026-06-03 00:02:00Z",
  }},
  {{
    message_id: 500,
    text: "parent received second",
    captured_at: "2026-06-03 00:00:08Z",
    rx_time: "2026-06-03 00:01:00Z",
  }},
]);
const replyIndex = new Map(
  replyRows.map((row) => [String(row.msg.message_id), row.msg])
);
const replyChild = replyRows.find((row) => row.msg.reply_id === 500).msg;
const result = {{
  order: chatMessagesInReceivedTimelineOrder(rows).map((row) => row.msg.id),
  selected: [
    chatMessageReceivedRaw(rows[1]),
    chatMessageReceivedRaw(rows[3]),
  ],
  replyParentText: replyIndex.get(String(replyChild.reply_id)).text,
}};
document.getElementById("result").textContent = JSON.stringify(result);
</script>"""
    probe_path = tmp_path / "chat_received_timeline.html"
    probe_path.write_text(html, encoding="utf-8")
    profile_path = tmp_path / "chromium-profile"

    completed = subprocess.run(
        [
            chromium,
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            f"--user-data-dir={profile_path}",
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
            f"Chromium timeline probe failed with exit {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    payload_text = completed.stdout.split('<pre id="result">', 1)[1].split("</pre>", 1)[0]
    payload = json.loads(payload_text)

    assert payload["order"] == [
        "unknown-1",
        "unknown-2",
        "capture-first",
        "capture-second",
        "fallback-first",
        "fallback-second",
        "tie-b",
        "tie-a",
        "history-earlier",
        "history-later",
    ]
    assert payload["selected"] == [
        "2026-06-03 00:00:01Z",
        "2026-06-03 00:00:03Z",
    ]
    assert payload["replyParentText"] == "parent received second"
