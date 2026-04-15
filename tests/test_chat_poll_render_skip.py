import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_js import build_dashboard_js


def test_dashboard_js_skips_redundant_chat_workspace_poll_renders() -> None:
    js = build_dashboard_js(
        refresh_ms=3000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'let chatPollStructuralSignature = "";' in js
    assert "const chatPollStructuralRefreshMs = 15000;" in js
    assert "function buildChatPollStructuralSignature(state = latestState) {" in js
    assert 'runPollStep("renderChat.workspace", () => renderChat(state, { allowPollSkip: true }));' in js
    assert "renderChat(latestState, { allowPollSkip: true });" in js
    assert '"/api/state?lite=1&profile=chat"' in js
    assert '"/api/state?lite=1&profile=network"' in js
    assert 'function statePollProfile() {' in js
    assert "&& pollStructuralSignature === chatPollStructuralSignature" in js
    assert "&& pollStructuralAgeMs < chatPollStructuralRefreshMs" in js
    assert 'markRenderChatPhase("poll-skip");' in js
    assert 'syncChatNodeDetailsDrawer(state, {' in js
    assert "!chatRenderedThisPoll304" in js
    assert "!chatRenderedThisPoll" in js
    assert 'const needsChatSection = !renderChatInDrawer || activeDrawerTab === "chat";' in js
    assert 'const linksSection = needsLinksSection && linkStats' in js
    assert "renderChatChangeSummary(nowUnix);" in js
    assert "function syncNetworkGraphSceneSelection(svg, options = {}) {" in js
    assert "function buildNetworkGraphSceneStructureSignature(scene) {" in js
    assert "function syncNetworkGraphSceneData(svg, scene) {" in js
    assert "const canPatchSelectionOnly = !!(" in js
    assert "const canSkipSceneRender = !!(" in js
    assert "const canPatchSceneDataOnly = !!(" in js
    assert "syncNetworkGraphSceneSelection(svg, { rootId, selectedId });" in js
    assert 'data-network-graph-edge-key="${escAttr(buildNetworkGraphEdgeDomKey(edge))}"' in js
    assert "syncNetworkGraphSceneData(svg, scene);" in js
    assert "hash = hashMixStr(hash, normalizeNodeId(selectedNodeId || \"\"));" not in js
