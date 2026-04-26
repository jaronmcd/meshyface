import io
import json
import sqlite3
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.helpers import to_int
from meshdash.history_schema import initialize_history_schema
from meshdash.history_store_settings import (
    append_bbs_post,
    load_bbs_posts,
    load_bbs_settings,
    save_bbs_settings,
)
from meshdash.html_js import build_dashboard_js
from meshdash.http_api import make_http_handler
from meshdash.http_api_get import build_get_route_dependencies
from meshdash.http_api_post import build_post_route_dependencies
from meshdash.http_routes_get import handle_dashboard_get
from meshdash.http_routes_post import handle_dashboard_post


class _FakeHandler:
    def __init__(self, body: bytes = b"", *, headers: dict[str, object] | None = None) -> None:
        self.path = "/"
        self.headers = headers or {}
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()

    def send_response(self, code: int) -> None:
        self._last_code = code

    def send_header(self, key: str, value: str) -> None:
        pass

    def end_headers(self) -> None:
        pass


def _make_store(conn: sqlite3.Connection) -> SimpleNamespace:
    return SimpleNamespace(
        _conn=conn,
        _read_conn=None,
        _read_lock=None,
        _lock=threading.Lock(),
        _maybe_prune_unlocked=lambda: None,
    )


def test_bbs_settings_store_round_trips_normalized_values() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    store = _make_store(conn)

    saved = save_bbs_settings(
        store,
        settings={
            "title": "  My   Packet Exchange  ",
            "board_id": " My Packet Exchange!!! ",
            "motd": "  hello   mesh   world  ",
        },
    )

    assert saved["ok"] is True
    assert saved["settings"] == {
        "title": "My Packet Exchange",
        "board_id": "my-packet-exchange",
        "motd": "hello mesh world",
        "enabled": False,
        "channel_index": 0,
        "started_unix": 0,
    }

    loaded = load_bbs_settings(store)

    assert loaded["ok"] is True
    assert loaded["settings"] == saved["settings"]
    assert int(loaded["updated_unix"]) > 0


def test_bbs_settings_store_preserves_runtime_fields_when_settings_change() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    store = _make_store(conn)

    online = save_bbs_settings(
        store,
        settings={
            "title": "zorkworld",
            "board_id": "zork-world",
            "motd": "welcome",
            "enabled": True,
            "channel_index": 4,
            "started_unix": 1234,
        },
    )

    saved = save_bbs_settings(
        store,
        settings={
            "title": "zorkworld 2",
            "board_id": "zork-world-2",
            "motd": "still here",
        },
    )

    assert online["settings"]["enabled"] is True
    assert saved["settings"] == {
        "title": "zorkworld 2",
        "board_id": "zork-world-2",
        "motd": "still here",
        "enabled": True,
        "channel_index": 4,
        "started_unix": 1234,
    }


def test_bbs_post_store_round_trips_and_truncates() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    store = _make_store(conn)

    appended = append_bbs_post(
        store,
        post={
            "entry_id": "post-1",
            "author_id": "!12345678",
            "author_name": "Zorkbot",
            "text": "  hello   board  ",
            "unix": 123,
        },
    )

    assert appended["ok"] is True
    assert appended["post"] == {
        "entry_id": "post-1",
        "author_id": "!12345678",
        "author_name": "Zorkbot",
        "text": "hello board",
        "unix": 123,
    }

    loaded = load_bbs_posts(store)

    assert loaded["ok"] is True
    assert loaded["posts"] == [appended["post"]]
    assert int(loaded["updated_unix"]) >= 123


def test_handle_dashboard_get_dispatches_bbs_settings_route() -> None:
    handler = _FakeHandler()
    calls: list[tuple[int, object, bool]] = []

    deps = build_get_route_dependencies(
        html_text="<html></html>",
        state_fn=lambda: {},
        node_history_fn=None,
        online_activity_fn=None,
        default_node_history_hours=24,
        get_bbs_settings_fn=lambda: {
            "ok": True,
            "settings": {
                "title": "Packet Exchange",
                "board_id": "packet-exchange",
                "motd": "2400 baud online.",
            },
            "updated_unix": 123,
        },
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, no_store=False, **kwargs: calls.append(
                (status_code, payload_obj, bool(no_store))
            ),
        }
    )

    handle_dashboard_get(handler, path="/api/settings/bbs", query="", deps=deps)

    assert calls == [
        (
            200,
            {
                "ok": True,
                "settings": {
                    "title": "Packet Exchange",
                    "board_id": "packet-exchange",
                    "motd": "2400 baud online.",
                },
                "updated_unix": 123,
            },
            True,
        )
    ]


def test_handle_dashboard_get_dispatches_bbs_host_route() -> None:
    handler = _FakeHandler()
    calls: list[tuple[int, object, bool]] = []

    deps = build_get_route_dependencies(
        html_text="<html></html>",
        state_fn=lambda: {},
        node_history_fn=None,
        online_activity_fn=None,
        default_node_history_hours=24,
        get_bbs_host_runtime_fn=lambda: {
            "ok": True,
            "host": {
                "enabled": True,
                "title": "Packet Exchange",
                "board_id": "packet-exchange",
                "motd": "2400 baud online.",
                "started_unix": 123,
                "channel_index": 2,
                "host_id": "!12345678",
            },
        },
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, no_store=False, **kwargs: calls.append(
                (status_code, payload_obj, bool(no_store))
            ),
        }
    )

    handle_dashboard_get(handler, path="/api/bbs/host", query="", deps=deps)

    assert calls == [
        (
            200,
            {
                "ok": True,
                "host": {
                    "enabled": True,
                    "title": "Packet Exchange",
                    "board_id": "packet-exchange",
                    "motd": "2400 baud online.",
                    "started_unix": 123,
                    "channel_index": 2,
                    "host_id": "!12345678",
                },
            },
            True,
        )
    ]


def test_handle_dashboard_post_dispatches_bbs_settings_route() -> None:
    body = json.dumps(
        {
            "settings": {
                "title": "Node Space",
                "board_id": "node-space",
                "motd": "hello",
            }
        }
    ).encode("utf-8")
    handler = _FakeHandler(body, headers={"Content-Length": str(len(body))})
    calls: list[tuple[int, object, bool]] = []

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_bbs_settings_fn=lambda request: {
            "ok": True,
            "settings": {
                "title": str(request.title),
                "board_id": str(request.board_id),
                "motd": str(request.motd),
            },
            "updated_unix": 456,
        },
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, no_store=False, **kwargs: calls.append(
                (status_code, payload_obj, bool(no_store))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/settings/bbs", deps=deps)

    assert calls == [
        (
            200,
            {
                "ok": True,
                "settings": {
                    "title": "Node Space",
                    "board_id": "node-space",
                    "motd": "hello",
                },
                "updated_unix": 456,
            },
            True,
        )
    ]


def test_handle_dashboard_post_dispatches_bbs_host_route() -> None:
    body = json.dumps(
        {
            "action": "start",
            "channel_index": 3,
            "settings": {
                "title": "Node Space",
                "board_id": "node-space",
                "motd": "hello",
            },
        }
    ).encode("utf-8")
    handler = _FakeHandler(body, headers={"Content-Length": str(len(body))})
    calls: list[tuple[int, object, bool]] = []

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        start_bbs_host_fn=lambda request: {
            "ok": True,
            "host": {
                "enabled": True,
                "title": str(request.title),
                "board_id": str(request.board_id),
                "motd": str(request.motd),
                "started_unix": 456,
                "channel_index": int(request.channel_index),
                "host_id": "!12345678",
            },
        },
        stop_bbs_host_fn=lambda: {"ok": True, "host": {"enabled": False}},
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, no_store=False, **kwargs: calls.append(
                (status_code, payload_obj, bool(no_store))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/bbs/host", deps=deps)

    assert calls == [
        (
            200,
            {
                "ok": True,
                "host": {
                    "enabled": True,
                    "title": "Node Space",
                    "board_id": "node-space",
                    "motd": "hello",
                    "started_unix": 456,
                    "channel_index": 3,
                    "host_id": "!12345678",
                },
            },
            True,
        )
    ]


def test_handle_dashboard_post_dispatches_bbs_host_post_action() -> None:
    body = json.dumps(
        {
            "action": "post",
            "text": "hello",
            "author_name": "zorkbot",
            "entry_id": "post-1",
        }
    ).encode("utf-8")
    handler = _FakeHandler(body, headers={"Content-Length": str(len(body))})
    calls: list[tuple[int, object, bool]] = []

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        start_bbs_host_fn=lambda request: {"ok": True, "host": {"enabled": True}},
        stop_bbs_host_fn=lambda: {"ok": True, "host": {"enabled": False}},
        append_bbs_host_post_fn=lambda request: {
            "ok": True,
            "host": {"enabled": True},
            "post": {
                "entry_id": str(request.entry_id),
                "author_name": str(request.author_name),
                "text": str(request.text),
            },
        },
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, no_store=False, **kwargs: calls.append(
                (status_code, payload_obj, bool(no_store))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/bbs/host", deps=deps)

    assert calls == [
        (
            200,
            {
                "ok": True,
                "host": {"enabled": True},
                "post": {
                    "entry_id": "post-1",
                    "author_name": "zorkbot",
                    "text": "hello",
                },
            },
            True,
        )
    ]


def test_make_http_handler_passes_bbs_settings_hooks(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_get: dict[str, object] = {}
    captured_post: dict[str, object] = {}

    def _fake_build_get_route_dependencies(**kwargs):
        captured_get.update(kwargs)
        return object()

    def _fake_build_post_route_dependencies(**kwargs):
        captured_post.update(kwargs)
        return object()

    monkeypatch.setattr("meshdash.http_api.build_get_route_dependencies", _fake_build_get_route_dependencies)
    monkeypatch.setattr("meshdash.http_api.build_post_route_dependencies", _fake_build_post_route_dependencies)
    monkeypatch.setattr(
        "meshdash.http_api.build_dashboard_handler_class",
        lambda **kwargs: {"dispatch_get_fn": kwargs["dispatch_get_fn"], "dispatch_post_fn": kwargs["dispatch_post_fn"]},
    )

    def _state_fn():
        return {}

    def _get_bbs_settings_fn() -> dict[str, object]:
        return {"ok": True, "settings": {}}

    def _set_bbs_settings_fn(payload: object) -> dict[str, object]:
        return {"ok": True, "settings": payload}

    def _get_bbs_host_runtime_fn() -> dict[str, object]:
        return {"ok": True, "host": {"enabled": True}}

    def _start_bbs_host_fn(payload: object) -> dict[str, object]:
        return {"ok": True, "host": payload}

    def _stop_bbs_host_fn() -> dict[str, object]:
        return {"ok": True, "host": {"enabled": False}}

    def _append_bbs_host_post_fn(payload: object) -> dict[str, object]:
        return {"ok": True, "post": payload}

    setattr(_state_fn, "get_bbs_settings_fn", _get_bbs_settings_fn)
    setattr(_state_fn, "set_bbs_settings_fn", _set_bbs_settings_fn)
    setattr(_state_fn, "get_bbs_host_runtime_fn", _get_bbs_host_runtime_fn)
    setattr(_state_fn, "start_bbs_host_fn", _start_bbs_host_fn)
    setattr(_state_fn, "stop_bbs_host_fn", _stop_bbs_host_fn)
    setattr(_state_fn, "append_bbs_host_post_fn", _append_bbs_host_post_fn)

    make_http_handler("<html></html>", _state_fn)

    assert captured_get["get_bbs_settings_fn"] is _get_bbs_settings_fn
    assert captured_get["get_bbs_host_runtime_fn"] is _get_bbs_host_runtime_fn
    assert captured_post["set_bbs_settings_fn"] is _set_bbs_settings_fn
    assert captured_post["start_bbs_host_fn"] is _start_bbs_host_fn
    assert captured_post["stop_bbs_host_fn"] is _stop_bbs_host_fn
    assert captured_post["append_bbs_host_post_fn"] is _append_bbs_host_post_fn


def test_dashboard_js_includes_bbs_settings_sync_flow() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
        bbs_enabled=True,
    )

    assert 'const bbsSettingsEndpoint = "/api/settings/bbs";' in js
    assert 'const bbsHostEndpoint = "/api/bbs/host";' in js
    assert 'const bbsHostSettingsSaveDebounceMs = 360;' in js
    assert 'const bbsProfileRequestTimeoutMs = 15 * 1000;' in js
    assert "async function fetchBbsHostSettings(options = null) {" in js
    assert "async function saveBbsHostSettings(options = null) {" in js
    assert "async function fetchBbsHostRuntime(options = null) {" in js
    assert "async function postBbsHostCommand(action, options = null) {" in js
    assert "function bbsReplaceBoardPosts(boardKey, posts = []) {" in js
    assert "function bbsLatestPostCursorForBoard(boardKey) {" in js
    assert "let bbsForgottenBoardKeys = new Set();" in js
    assert "replica_version: 2," in js
    assert "const canRestoreBoardReplica = storedReplicaVersion >= 2;" in js
    assert "forgotten_board_keys: payload.forgotten_board_keys," in js
    assert "function bbsForgetDirectoryKey(boardKey) {" in js
    assert "function bbsAllowDirectoryKeysForHost(hostId) {" in js
    assert "bbsForgottenBoardKeys = new Set(" in js
    assert "payload.posts_by_key = postsByKey;" in js
    assert "if (Array.isArray(cachedPosts) && cachedPosts.length > 0) return true;" in js
    assert "function bbsResolvePendingLoadFromContent(hostId, boardKey, state = latestState) {" in js
    assert "function bbsIsOfflineLocalBoard(hostId, state = latestState) {" in js
    assert 'if (bbsIsOfflineLocalBoard(hostId) && row.force !== true) return "";' in js
    assert 'if (bbsForgottenBoardKeys.has(key) && row.force !== true) return "";' in js
    assert "bbsForgetDirectoryKey(key);" in js
    assert "if (bbsAllowDirectoryKeysForHost(cleanNodeId)) {" in js
    assert "const shouldShowRuntimeHost = !!(hostKey && bbsHostState.enabled);" in js
    assert "bbsRemoveDirectoryRowByKey(hostKey, { persist: false });" in js
    assert "const bbsSnapshotTransferKeysImported = new Set();" in js
    assert 'source.kind !== "easyface-bbs-snapshot-v1"' in js
    assert "function syncBbsSnapshotTransfers(state = latestState) {" in js
    assert 'fileName.startsWith("bbs-snapshot-")' in js
    assert 'setFileTransferInboundDecisionByKey(key, "accepted", {' in js
    assert "syncBbsSnapshotTransfers(safeState);" in js
    assert 'String(bbsPostStatusText || "").startsWith("No BBS reply from ")' in js
    assert "openFields.push(requestBoardId, requestSinceUnix, requestTailEntryId);" in js
    assert "const wireUnix = bbsPostUnixFromWire(parsed.parts[8]);" in js
    assert 'if (parsed.type === "batch") {' in js
    assert "function bbsDecodeBatchPayload(rawPayload) {" in js
    assert "function forgetSelectedBbsBoard() {" in js
    assert 'document.getElementById("bbs-forget-directory-btn")' in js
    assert "async function requestBbsSpaceForNode(nodeId, options = null) {" in js
    assert "async function respondToBbsOpenRequest(nodeId, requestToken, channelIndex, state = latestState) {" in js
    assert "function openBbsBoardForHost(nodeId) {" in js
    assert 'body: JSON.stringify({ settings }),' in js
    assert 'body: JSON.stringify(body),' in js
    assert 'body.text = String(opts.text == null ? "" : opts.text);' in js
    assert 'queueBbsHostSettingsSave();' in js
    assert 'void fetchBbsHostSettings({ silent: true });' in js
    assert 'void fetchBbsHostRuntime({ silent: true });' in js
    assert 'data-bbs-node-id="' in js
    assert 'destination: cleanNodeId,' in js
    assert 'destination: activeRow.host_id,' in js
    assert 'if (parsed.type === "open") {' in js
    assert 'if (parsed.type === "profile") {' in js
    assert 'Replies only to direct BBS requests.' in js
    assert "Profile reply channel:" not in js
    assert "Direct reply channel:" not in js

    address_gate = (
        'if (!toAll) {\n'
        '          if (!isCanonicalNodeId(localId)) continue;\n'
        '          if (!isCanonicalNodeId(toId) || toId !== localId) continue;\n'
        '        }'
    )
    dedupe_marker = "const dedupeKey = bbsProtocolMessageKey(msg, parsed);"
    assert address_gate in js
    assert js.index(address_gate) < js.index(dedupe_marker)
