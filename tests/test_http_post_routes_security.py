import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.helpers import to_int
from meshdash.http_api_post import build_post_route_dependencies
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


def test_handle_dashboard_post_returns_not_found_for_removed_bot_settings_route() -> None:
    handler = _FakeHandler()
    calls: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(send_chat_fn=None, to_int_fn=to_int)
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: calls.append((status_code, payload_obj)),
        }
    )

    handle_dashboard_post(handler, path="/api/settings/bot", deps=deps)

    assert calls == [(404, {"ok": False, "error": "Not Found"})]


def test_handle_dashboard_post_keeps_standalone_zork_route_available() -> None:
    body = json.dumps({"text": "zork", "session_id": "session-1"}).encode("utf-8")
    handler = _FakeHandler(body, headers={"Content-Length": str(len(body))})
    calls: list[tuple[int, object]] = []

    def _write_json_response(handler, *, status_code, payload_obj, **kwargs):
        calls.append((status_code, payload_obj))

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        play_standalone_zork_fn=lambda *, text, session_id=None: {
            "ok": True,
            "reply_text": f"started:{text}",
            "session_id": session_id,
            "active_session": True,
        },
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": _write_json_response,
        }
    )

    handle_dashboard_post(handler, path="/api/games/zork", deps=deps)

    assert calls == [
        (
            200,
            {
                "ok": True,
                "reply_text": "started:zork",
                "session_id": "session-1",
                "active_session": True,
            },
        )
    ]


def test_handle_dashboard_post_toggles_zork_bot_runtime() -> None:
    body = json.dumps({"enabled": False}).encode("utf-8")
    handler = _FakeHandler(body, headers={"Content-Length": str(len(body))})
    calls: list[tuple[int, object]] = []
    toggles: list[bool] = []

    def _write_json_response(handler, *, status_code, payload_obj, **kwargs):
        calls.append((status_code, payload_obj))

    def _set_zork_bot_enabled(enabled: bool) -> dict[str, object]:
        toggles.append(enabled)
        return {
            "ok": True,
            "available": True,
            "zork": {
                "enabled": enabled,
                "active_session_count": 0,
            },
        }

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_zork_bot_enabled_fn=_set_zork_bot_enabled,
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": _write_json_response,
        }
    )

    handle_dashboard_post(handler, path="/api/bots/zork", deps=deps)

    assert toggles == [False]
    assert calls == [
        (
            200,
            {
                "ok": True,
                "available": True,
                "zork": {
                    "enabled": False,
                    "active_session_count": 0,
                },
            },
        )
    ]


def test_handle_dashboard_post_rejects_zork_bot_toggle_when_runtime_unavailable() -> None:
    body = json.dumps({"enabled": True}).encode("utf-8")
    handler = _FakeHandler(body, headers={"Content-Length": str(len(body))})
    calls: list[tuple[int, object]] = []

    def _write_json_response(handler, *, status_code, payload_obj, **kwargs):
        calls.append((status_code, payload_obj))

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": _write_json_response,
        }
    )

    handle_dashboard_post(handler, path="/api/bots/zork", deps=deps)

    assert calls == [
        (
            400,
            {"ok": False, "error": "Zork bot runtime toggle is unavailable"},
        )
    ]


def test_handle_dashboard_post_toggles_ping_bot_runtime() -> None:
    body = json.dumps({"enabled": True}).encode("utf-8")
    handler = _FakeHandler(body, headers={"Content-Length": str(len(body))})
    calls: list[tuple[int, object]] = []
    toggles: list[bool] = []

    def _write_json_response(handler, *, status_code, payload_obj, **kwargs):
        calls.append((status_code, payload_obj))

    def _set_ping_bot_enabled(enabled: bool) -> dict[str, object]:
        toggles.append(enabled)
        return {
            "ok": True,
            "available": True,
            "ping": {
                "enabled": enabled,
                "active_session_count": 0,
            },
        }

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_ping_bot_enabled_fn=_set_ping_bot_enabled,
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": _write_json_response,
        }
    )

    handle_dashboard_post(handler, path="/api/bots/ping", deps=deps)

    assert toggles == [True]
    assert calls == [
        (
            200,
            {
                "ok": True,
                "available": True,
                "ping": {
                    "enabled": True,
                    "active_session_count": 0,
                },
            },
        )
    ]


def test_handle_dashboard_post_updates_raw_packet_capture_settings() -> None:
    body = json.dumps({"capture_enabled": True}).encode("utf-8")
    handler = _FakeHandler(body, headers={"Content-Length": str(len(body))})
    calls: list[tuple[int, object]] = []
    received: list[object] = []

    def _write_json_response(handler, *, status_code, payload_obj, **kwargs):
        calls.append((status_code, payload_obj))

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_raw_packet_capture_settings_fn=lambda settings: received.append(settings)
        or {"ok": True, "capture_enabled": settings["capture_enabled"]},
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": _write_json_response,
        }
    )

    handle_dashboard_post(handler, path="/api/settings/raw_packets", deps=deps)

    assert received == [{"capture_enabled": True}]
    assert calls == [(200, {"ok": True, "capture_enabled": True})]


def test_handle_dashboard_post_requires_token_for_raw_packet_capture_settings() -> None:
    body = json.dumps({"capture_enabled": True}).encode("utf-8")
    handler = _FakeHandler(body, headers={"Content-Length": str(len(body))})
    calls: list[tuple[int, object]] = []
    updates = 0

    def _set_raw_packet_capture_settings(settings: object) -> dict[str, object]:
        nonlocal updates
        updates += 1
        return {"ok": True}

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_raw_packet_capture_settings_fn=_set_raw_packet_capture_settings,
        api_token="secret",
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: calls.append((status_code, payload_obj)),
        }
    )

    handle_dashboard_post(handler, path="/api/settings/raw_packets", deps=deps)

    assert updates == 0
    assert calls == [(401, {"ok": False, "error": "API token required for write endpoint"})]


def test_handle_dashboard_post_rejects_ping_bot_toggle_when_runtime_unavailable() -> None:
    body = json.dumps({"enabled": True}).encode("utf-8")
    handler = _FakeHandler(body, headers={"Content-Length": str(len(body))})
    calls: list[tuple[int, object]] = []

    def _write_json_response(handler, *, status_code, payload_obj, **kwargs):
        calls.append((status_code, payload_obj))

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": _write_json_response,
        }
    )

    handle_dashboard_post(handler, path="/api/bots/ping", deps=deps)

    assert calls == [
        (
            400,
            {"ok": False, "error": "Ping bot runtime toggle is unavailable"},
        )
    ]


def test_handle_dashboard_post_runs_system_update(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _run_update(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"ok": True, "updated": False, "state": "up_to_date", "http_status": 200}

    monkeypatch.setattr(
        "meshdash.http_routes_post._run_update_from_github_helper",
        _run_update,
    )
    body = b'{"branch":"beta"}'
    handler = _FakeHandler(body, headers={"Content-Length": str(len(body))})
    calls: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(send_chat_fn=None, to_int_fn=to_int)
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: calls.append((status_code, payload_obj)),
        }
    )

    handle_dashboard_post(handler, path="/api/system/update", deps=deps)

    assert captured["target_branch"] == "beta"
    assert calls == [(200, {"ok": True, "updated": False, "state": "up_to_date"})]


def test_handle_dashboard_post_requires_token_for_system_update(monkeypatch: pytest.MonkeyPatch) -> None:
    update_calls = 0

    def _run_update(**kwargs: object) -> dict[str, object]:
        nonlocal update_calls
        update_calls += 1
        return {"ok": True}

    monkeypatch.setattr("meshdash.http_routes_post._run_update_from_github_helper", _run_update)
    handler = _FakeHandler()
    calls: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(send_chat_fn=None, api_token="secret", to_int_fn=to_int)
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: calls.append((status_code, payload_obj)),
        }
    )

    handle_dashboard_post(handler, path="/api/system/update", deps=deps)

    assert update_calls == 0
    assert calls == [(401, {"ok": False, "error": "API token required for write endpoint"})]


def test_handle_dashboard_post_schedules_system_restart() -> None:
    handler = _FakeHandler()
    calls: list[tuple[int, object]] = []
    restart_calls = 0

    def _schedule_restart() -> dict[str, object]:
        nonlocal restart_calls
        restart_calls += 1
        return {
            "ok": True,
            "restart_scheduled": True,
            "state": "pending",
            "message": "Backend reload scheduled.",
            "http_status": 202,
        }

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        schedule_backend_restart_fn=_schedule_restart,
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: calls.append((status_code, payload_obj)),
        }
    )

    handle_dashboard_post(handler, path="/api/system/restart", deps=deps)

    assert restart_calls == 1
    assert calls == [
        (
            202,
            {
                "ok": True,
                "restart_scheduled": True,
                "state": "pending",
                "message": "Backend reload scheduled.",
            },
        )
    ]


def test_handle_dashboard_post_requires_token_for_system_restart() -> None:
    restart_calls = 0

    def _schedule_restart() -> dict[str, object]:
        nonlocal restart_calls
        restart_calls += 1
        return {"ok": True}

    handler = _FakeHandler()
    calls: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(
        send_chat_fn=None,
        schedule_backend_restart_fn=_schedule_restart,
        api_token="secret",
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: calls.append((status_code, payload_obj)),
        }
    )

    handle_dashboard_post(handler, path="/api/system/restart", deps=deps)

    assert restart_calls == 0
    assert calls == [(401, {"ok": False, "error": "API token required for write endpoint"})]


def test_handle_dashboard_post_sets_ping_message_only_mode() -> None:
    body = json.dumps({"action": "set_mode", "message_only": True}).encode("utf-8")
    handler = _FakeHandler(body, headers={"Content-Length": str(len(body))})
    calls: list[tuple[int, object]] = []
    mode_updates: list[bool] = []

    def _write_json_response(handler, *, status_code, payload_obj, **kwargs):
        calls.append((status_code, payload_obj))

    def _set_ping_bot_message_only(message_only: bool) -> dict[str, object]:
        mode_updates.append(message_only)
        return {
            "ok": True,
            "available": True,
            "ping": {
                "enabled": True,
                "public_start_enabled": not message_only,
                "direct_message_enabled": True,
                "message_only": message_only,
            },
        }

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_ping_bot_message_only_fn=_set_ping_bot_message_only,
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": _write_json_response,
        }
    )

    handle_dashboard_post(handler, path="/api/bots/ping", deps=deps)

    assert mode_updates == [True]
    assert calls == [
        (
            200,
            {
                "ok": True,
                "available": True,
                "ping": {
                    "enabled": True,
                    "public_start_enabled": False,
                    "direct_message_enabled": True,
                    "message_only": True,
                },
            },
        )
    ]


def test_handle_dashboard_post_manages_zork_bot_sessions() -> None:
    body = json.dumps({"action": "end_session", "peer_id": "!01020304"}).encode("utf-8")
    handler = _FakeHandler(body, headers={"Content-Length": str(len(body))})
    calls: list[tuple[int, object]] = []
    actions: list[tuple[object, object]] = []

    def _write_json_response(handler, *, status_code, payload_obj, **kwargs):
        calls.append((status_code, payload_obj))

    def _manage_zork_bot(action: object, *, peer_id: object = None) -> dict[str, object]:
        actions.append((action, peer_id))
        return {
            "ok": True,
            "changed": True,
            "available": True,
            "zork": {
                "enabled": True,
                "active_session_count": 0,
                "sessions": [],
            },
        }

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        manage_zork_bot_fn=_manage_zork_bot,
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": _write_json_response,
        }
    )

    handle_dashboard_post(handler, path="/api/bots/zork", deps=deps)

    assert actions == [("end_session", "!01020304")]
    assert calls == [
        (
            200,
            {
                "ok": True,
                "changed": True,
                "available": True,
                "zork": {
                    "enabled": True,
                    "active_session_count": 0,
                    "sessions": [],
                },
            },
        )
    ]
