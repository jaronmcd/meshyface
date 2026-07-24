import html
import json
import os
import shutil
import subprocess
from collections.abc import Callable

import pytest


_PEER_THREAD_START = (
    "const renderPeerDmThreadHost = (host, peerIdRaw, options = null) => {"
)
_PEER_THREAD_END = (
    'const drawerMessagesHost = document.getElementById("chat-node-details-messages-host");'
)


def _peer_thread_function(js: str) -> str:
    return _PEER_THREAD_START + js.split(_PEER_THREAD_START, 1)[1].split(
        _PEER_THREAD_END,
        1,
    )[0]


def test_peer_dm_thread_preserves_composer_when_messages_change(
    dashboard_js_factory: Callable[..., str],
) -> None:
    peer_thread_js = _peer_thread_function(dashboard_js_factory())

    assert "const nextThreadHtml = `<section" in peer_thread_js
    assert "const canPatchExistingThread = !!(" in peer_thread_js
    assert "&& threadComposer instanceof HTMLElement" in peer_thread_js
    assert "if (!canPatchExistingThread) {" in peer_thread_js
    assert "threadBody.innerHTML = messageRows;" in peer_thread_js
    assert "threadHeader.outerHTML = nextThreadHeaderHtml;" in peer_thread_js
    assert "threadComposer.innerHTML" not in peer_thread_js
    assert 'value="${escAttr(draft)}"' not in peer_thread_js
    assert "const inputHasFocus = document.activeElement === input;" in peer_thread_js
    assert "if (!inputHasFocus && input.value !== draft) {" in peer_thread_js
    assert "priorSelectionStart" not in peer_thread_js
    assert "input.setSelectionRange(" not in peer_thread_js
    assert "input.__meshPeerDmSubmitMessage = submitMessage;" in peer_thread_js
    assert "sendBtn.__meshPeerDmSubmitMessage = submitMessage;" in peer_thread_js
    assert 'if (ev.key !== "Enter" || ev.shiftKey) return;' in peer_thread_js
    assert "void callback();" in peer_thread_js
    assert "if (bodyEl instanceof HTMLElement && threadBodyChanged) {" in peer_thread_js


@pytest.mark.gui_benchmark
def test_peer_dm_thread_keeps_focused_input_node_in_browser(
    dashboard_js_factory: Callable[..., str],
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
        pytest.skip("Chromium is required for the peer composer regression probe")

    peer_thread_function = _peer_thread_function(dashboard_js_factory())
    probe_html = f"""<!doctype html><meta charset="utf-8">
<div id="host"></div><pre id="result"></pre><script>
const peerId = "!22222222";
const nodesById = new Map([[peerId, {{}}]]);
const state = {{}};
const directMessagesByPeer = new Map();
const peerDmDraftByPeer = new Map();
const unreadDirectFocusKeysByPeer = new Map();
const localNodeId = "!11111111";
const chatFeedMaxEntries = 100;
const nowUnix = 1_800_000_000;
let chatSendInFlight = false;
let latestState = null;
let activeLayoutView = "";
let channelLabel = "Ch 0";
const normalizeNodeId = (value) => String(value || "").toLowerCase();
const isCanonicalNodeId = (value) => /^![0-9a-f]{{8}}$/.test(normalizeNodeId(value));
const isSelfNodeId = (value) => normalizeNodeId(value) === localNodeId;
const resolveChatNodeFreshness = () => ({{ historyCaps: null }});
const preferredChatNodeName = () => "Peer";
const nodeTagEntryForNode = () => null;
const effectiveNodeAppearanceForNode = () => null;
const summarizePeerDmFileTransferState = () => null;
const normalizeMeshChannelIndex = (value) => Number(value) || 0;
const meshChannelSendContext = () => ({{ sendIndex: 0 }});
const meshChannelLabelForIndex = () => channelLabel;
const meshChannelColorMeta = () => ({{ fill: "#123456" }});
const hexColorRgbTriplet = () => "18, 52, 86";
const normalizeDeliveryState = (value) => String(value || "").toLowerCase();
const escAttr = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;");
const renderChat = () => {{}};
const syncChatChangeAutoDismiss = () => {{}};
const isChatWorkspaceLayoutView = () => false;
{peer_thread_function}
const host = document.getElementById("host");
renderPeerDmThreadHost(host, peerId);
const input = host.querySelector('[data-peer-dm-role="input"]');
const sendButton = host.querySelector('[data-peer-dm-role="send"]');
input.value = "test";
input.focus();
input.setSelectionRange(2, 2);
channelLabel = "Primary";
renderPeerDmThreadHost(host, peerId);
const result = {{
  sameInput: host.querySelector('[data-peer-dm-role="input"]') === input,
  sameSendButton: host.querySelector('[data-peer-dm-role="send"]') === sendButton,
  focused: document.activeElement === input,
  value: input.value,
  selectionStart: input.selectionStart,
  selectionEnd: input.selectionEnd,
  channelLabel: host.querySelector(".peer-dm-popout-channel").textContent,
}};
document.getElementById("result").textContent = JSON.stringify(result);
</script>"""
    probe_path = tmp_path / "peer_dm_composer_focus.html"
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
            f"Chromium peer composer probe failed with exit {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )

    payload_text = completed.stdout.split('<pre id="result">', 1)[1].split(
        "</pre>",
        1,
    )[0]
    payload = json.loads(html.unescape(payload_text))
    assert payload == {
        "sameInput": True,
        "sameSendButton": True,
        "focused": True,
        "value": "test",
        "selectionStart": 2,
        "selectionEnd": 2,
        "channelLabel": "Primary",
    }
