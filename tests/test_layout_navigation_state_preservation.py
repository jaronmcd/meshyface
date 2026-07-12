import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_js import build_dashboard_js


def test_dashboard_js_keeps_layout_switches_in_app() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    start = js.index("function meshSelectLayoutView(viewName)")
    end = js.index("// Expose view switching globally", start)
    switcher_block = js[start:end]

    assert "function meshSelectLayoutView(viewName)" in js
    assert "Never hard-reload the page on a view switch miss." in switcher_block
    assert "window.location.reload()" not in switcher_block
    assert "window.requestAnimationFrame(() => {" in switcher_block


def test_dashboard_js_omits_removed_bbs_and_bots_views() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    known_layout_views = js.split(
        "const knownLayoutViews = new Set([", 1
    )[1].split("]);", 1)[0]
    assert "bbsFeatureEnabled" not in js
    assert 'clean === "bbs"' not in js
    assert '"bbs"' not in known_layout_views
    assert 'clean === "bots"' not in js
    assert '"bots"' not in known_layout_views
    assert 'if (clean === "games") {' in js



def test_dashboard_js_keeps_whois_builder_and_remote_stage_without_bot_bindings() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "function normalizeWhoisCommandPrefix(value)" in js
    assert "function nodeIdSuffixForWhois(nodeId)" in js
    assert "function buildWhoisCommandForNode(nodeId, prefixValue = chatWhoisQuickActionPrefix)" in js
    assert "function loadChatWhoisQuickActionConfig()" in js
    assert "function bindChatWhoisQuickActionControls()" not in js
    assert "chat-bot-" not in js
    assert 'const stageWhoisBtn = document.getElementById("remote-stage-whois-btn");' in js
    assert "stageRemoteChatCommand(nodeId, `whois ${nodeId}`, {" in js


def test_dashboard_js_binds_games_picker_select() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'const gamesLibrarySelect = document.getElementById("games-library-select");' in js
    assert 'if (gamesLibrarySelect instanceof HTMLSelectElement) {' in js
    assert 'gamesLibrarySelect.value = activeGameId;' in js
    assert 'gamesLibrarySelect.addEventListener("change", () => {' in js
    assert 'activeGameId = normalizeActiveGameId(gamesLibrarySelect.value);' in js


def test_dashboard_js_keeps_supported_gated_apps_in_channel_routing() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    start = js.index("function meshChannelAppRoutingRows() {")
    end = js.index("function normalizeMeshChannelAppId", start)
    routing_block = js[start:end]

    assert 'id: "bbs"' not in routing_block
    assert 'if (fileTransferFeatureEnabled) {' in routing_block
    assert 'id: "files"' in routing_block
    assert 'label: "Files"' in routing_block
    assert 'id: "bots"' not in routing_block
    assert 'label: "Bots"' not in routing_block
    assert 'id: "games"' in routing_block
    assert 'label: "Games"' in routing_block



def test_dashboard_js_exposes_files_in_app_channel_routing_when_enabled() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
        file_transfer_enabled=True,
    )

    start = js.index("function meshChannelAppRoutingRows() {")
    end = js.index("function normalizeMeshChannelAppId", start)
    routing_block = js[start:end]

    assert 'id: "files"' in routing_block
    assert 'label: "Files"' in routing_block
    assert 'if (token === "files" && fileTransferFeatureEnabled) return "files";' in js
    assert 'if (token === "bots"' not in js
    assert 'id: "games"' in routing_block
    assert 'label: "Games"' in routing_block


def test_dashboard_html_labels_files_destination_as_node() -> None:
    html_template = (Path(__file__).resolve().parents[1] / "meshdash/assets/dashboard.html.tmpl").read_text(encoding="utf-8")

    assert '<span class="files-label">Destination Node</span>' in html_template
    assert 'placeholder="Select a node or enter !1234abcd"' in html_template


def test_dashboard_html_orders_files_controls_table_and_console() -> None:
    html_template = (Path(__file__).resolve().parents[1] / "meshdash/assets/dashboard.html.tmpl").read_text(encoding="utf-8")

    channel_idx = html_template.index('<span class="files-label">Send Channel</span>')
    destination_idx = html_template.index('<span class="files-label">Destination Node</span>')
    file_row_idx = html_template.index('<div class="files-file-row">')
    file_input_idx = html_template.index('id="files-input"', file_row_idx)
    send_btn_idx = html_template.index('id="files-send-btn"', file_row_idx)
    table_idx = html_template.index('id="files-transfer-table"')
    splitter_idx = html_template.index('id="files-transfer-console-splitter"')
    console_idx = html_template.index('<div class="files-console">')

    assert channel_idx < destination_idx
    assert file_row_idx < file_input_idx < send_btn_idx
    assert table_idx < splitter_idx < console_idx


def test_dashboard_js_syncs_files_destination_from_node_selection() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
        file_transfer_enabled=True,
    )

    select_start = js.index("function selectNode(nodeId, shouldFocus = true, toggleIfSelected = true) {")
    select_end = js.index("function clearNodeSelection()", select_start)
    select_block = js[select_start:select_end]
    render_start = js.index("function renderFilesView(state = latestState) {")
    render_end = js.index('const useSelectedBtn = document.getElementById("files-use-selected-btn");', render_start)
    render_block = js[render_start:render_end]

    assert "function syncFileTransferDestinationFromSelectedNode(state = latestState, options = null) {" in js
    assert "function fileTransferDestinationDisplayLabel(nodeId, state = latestState) {" in js
    assert "return preferred ? `${preferred} (${clean})` : clean;" in js
    assert "let destination = extractFileTransferDestinationId(rawInput);" in js
    assert 'destination = normalizeNodeId(fileTransferDestinationId || "");' in js
    assert 'if (activeLayoutView === "files" && typeof syncFileTransferDestinationFromSelectedNode === "function") {' in select_block
    assert "syncFileTransferDestinationFromSelectedNode(latestState, { persist: true });" in select_block
    assert "const selectedSeed = syncFileTransferDestinationFromSelectedNode(state, { persist: true });" in render_block


def test_dashboard_js_uses_backend_file_transfer_runtime_for_rows_and_ack_suppression() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
        file_transfer_enabled=True,
        file_transfer_auto_accept=True,
    )

    assert "function fileTransferBackendRuntime(state = latestState)" in js
    assert "function fileTransferBackendAutoAcceptEnabled(state = latestState)" in js
    assert "function fileTransferBackendSessions(state = latestState)" in js
    assert "function mergeBackendFileTransferRuntimeRows(rows, state, context = null)" in js
    assert "const backendAutoAcceptEnabled = fileTransferBackendAutoAcceptEnabled(state);" in js
    assert "const backendAutoAcceptEnabled = fileTransferBackendAutoAcceptEnabled(latestState);" in js
    assert "toggle.disabled = !fileTransferFeatureEnabled || backendAutoAcceptEnabled;" in js
    assert "Backend auto accept is enabled for direct inbound file transfers." in js
    assert "if (backendAutoAcceptEnabled) {" in js
    assert "source: \"backend_auto_accept\"" in js
    assert "backendAuthoritative: true" in js
    assert "Complete on receiver" in js
    assert "Backend receiver has the complete transfer; this browser does not have download bytes." in js


def test_dashboard_js_bounds_inbound_file_transfer_metadata_and_ack_work() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
        file_transfer_enabled=True,
        file_transfer_max_bytes=1024,
    )

    assert "const fileTransferMaxChunks = Math.max(1, Math.ceil(fileTransferMaxFileBytes / fileTransferChunkBytes));" in js
    assert "totalChunks > fileTransferMaxChunks" in js
    assert "fileSize > fileTransferMaxFileBytes" in js
    assert "const expectedChunks = Math.max(1, Math.ceil(fileSize / fileTransferChunkBytes));" in js
    assert "if (totalChunks !== expectedChunks) return null;" in js
    assert "chunkBytes.length > fileTransferChunkBytes" in js
    assert "byteLen > fileTransferMaxAckBitmapBytes" in js
    assert "bytes.length > fileTransferMaxAckBitmapBytes" in js
    assert "const fileTransferChunkCacheMaxEntries = 96;" in js
    assert "function enforceFileTransferChunkCacheLimits(nowMs = Date.now())" in js
    assert "fileTransferChunkCacheByKey.size > fileTransferChunkCacheMaxEntries" in js
    assert "totalBytes > fileTransferChunkCacheMaxBytes" in js
    assert "const cacheMetadataMismatch = !!(" in js
    assert "clearFileTransferMaterializedStateForKey(key);" in js
    assert "if ((out.length + literalLen) > outputLimit) return null;" in js
    assert "if ((out.length + matchLen) > outputLimit) return null;" in js
    assert "function fileTransferKeyOf(fromId, toId, transferId, channelIndex)" in js
    assert "const directInbound = toId === localNodeId && fromId !== localNodeId;" in js
    assert "if (!directInbound && !directOutbound) continue;" in js
    assert "knownTotalChunks == null || frame.chunkIndex >= knownTotalChunks" in js
    assert "Final escape hatch" not in js
    assert "Math.trunc(Number(ack.totalChunks)) !== expectedTotalChunks" in js
    assert "fileTransferExplicitChannelIndex(ack.channelIndex) !== expectedChannel" in js
    assert "findAckForOutgoingSession(outgoingSession, ackByTransferKey, localNodeId)" in js
    assert "const fileTransferInboundStateMaxEntries = 1200;" in js
    assert "const fileTransferActiveInboundMaxEntries = fileTransferChunkCacheMaxEntries;" in js
    assert "function admitFileTransferAutoAcceptMetadata(senderIdRaw, nowMsRaw = Date.now())" in js
    assert "fileTransferMetaAdmissionByPeer" in js
    assert "fileTransferMetaAdmissionPeerCooldownMs" in js
    assert "fileTransferMetaAdmissionGlobalCooldownMs" in js
    assert "fileTransferAcceptedInboundDecisionCount() >= fileTransferActiveInboundMaxEntries" in js
    assert "fileTransferInboundDecisionByKey.size >= fileTransferInboundStateMaxEntries" in js
    assert "function setBoundedFileTransferMapEntry(targetMap, keyRaw, value, maxEntriesRaw)" in js
    assert "function enforceFileTransferAckObservedLimits()" in js
    assert "totalIndexes > fileTransferAckObservedMaxIndexes" in js
    assert "fileTransferAckSentState, transferKey" in js
    assert "const fileTransferMaterializedCacheMaxEntries = 8;" in js
    assert "const fileTransferMaterializedCacheMaxBytes = Math.max(" in js
    assert "function enforceFileTransferMaterializedCacheLimits(protectedKeyRaw = \"\")" in js
    assert "function materializeFileTransferRowBytes(row)" in js
    assert "merged.subarray(0, wireDeclaredBytes)" in js
    assert "fileTransferMaterializeFailureByKey" in js
    assert "const bytes = materializeFileTransferRowBytes(row);" in js
    rows_start = js.index("function buildFileTransferRows(state = latestState)")
    rows_end = js.index("function syncFileTransferBlobs(rows)", rows_start)
    assert "decodeFileTransferPayloadBytes(" not in js[rows_start:rows_end]
