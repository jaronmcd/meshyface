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


@pytest.mark.parametrize(
    "path",
    (
        "/api/settings/bot",
        "/api/bots/zork",
        "/api/bots/ping",
    ),
)
def test_handle_dashboard_post_returns_not_found_for_removed_bot_routes(
    path: str,
) -> None:
    handler = _FakeHandler()
    calls: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(send_chat_fn=None, to_int_fn=to_int)
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: calls.append(
                (status_code, payload_obj)
            ),
        }
    )

    handle_dashboard_post(handler, path=path, deps=deps)

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


def test_handle_dashboard_post_rolls_back_system_update(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    update_calls = 0

    def _run_update(**kwargs: object) -> dict[str, object]:
        nonlocal update_calls
        update_calls += 1
        return {"ok": True}

    def _rollback_update(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "ok": True,
            "rollback": True,
            "rollback_branch": "rollback/main-dddddddd1111",
            "http_status": 200,
        }

    monkeypatch.setattr(
        "meshdash.http_routes_post._run_update_from_github_helper",
        _run_update,
    )
    monkeypatch.setattr(
        "meshdash.http_routes_post._rollback_update_to_commit_helper",
        _rollback_update,
    )
    body = b'{"branch":"main","rollback_commit":"dddddddd"}'
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

    assert update_calls == 0
    assert captured == {"target_branch": "main", "target_commit": "dddddddd"}
    assert calls == [(200, {"ok": True, "rollback": True, "rollback_branch": "rollback/main-dddddddd1111"})]


def test_handle_dashboard_post_syncs_system_update_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _sync_update(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "ok": True,
            "synced": True,
            "updated": False,
            "state": "update_available",
            "http_status": 200,
        }

    monkeypatch.setattr(
        "meshdash.http_routes_post._sync_update_branches_from_github_helper",
        _sync_update,
    )
    body = b'{"branch":"dev"}'
    handler = _FakeHandler(body, headers={"Content-Length": str(len(body))})
    calls: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(send_chat_fn=None, to_int_fn=to_int)
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: calls.append((status_code, payload_obj)),
        }
    )

    handle_dashboard_post(handler, path="/api/system/update/sync", deps=deps)

    assert captured["target_branch"] == "dev"
    assert calls == [(200, {"ok": True, "synced": True, "updated": False, "state": "update_available"})]


def test_handle_dashboard_post_cleans_rollback_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    cleanup_calls = 0

    def _cleanup_rollbacks(**kwargs: object) -> dict[str, object]:
        nonlocal cleanup_calls
        cleanup_calls += 1
        return {
            "ok": True,
            "cleanup": True,
            "deleted_count": 1,
            "deleted": ["rollback/main-dddddddd1111"],
            "http_status": 200,
        }

    monkeypatch.setattr(
        "meshdash.http_routes_post._cleanup_update_rollback_branches_helper",
        _cleanup_rollbacks,
    )
    handler = _FakeHandler()
    calls: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(send_chat_fn=None, to_int_fn=to_int)
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: calls.append((status_code, payload_obj)),
        }
    )

    handle_dashboard_post(handler, path="/api/system/update/rollback-cleanup", deps=deps)

    assert cleanup_calls == 1
    assert calls == [
        (
            200,
            {
                "ok": True,
                "cleanup": True,
                "deleted_count": 1,
                "deleted": ["rollback/main-dddddddd1111"],
            },
        )
    ]


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


def test_handle_dashboard_post_requires_token_for_system_update_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    sync_calls = 0

    def _sync_update(**kwargs: object) -> dict[str, object]:
        nonlocal sync_calls
        sync_calls += 1
        return {"ok": True}

    monkeypatch.setattr("meshdash.http_routes_post._sync_update_branches_from_github_helper", _sync_update)
    handler = _FakeHandler()
    calls: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(send_chat_fn=None, api_token="secret", to_int_fn=to_int)
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: calls.append((status_code, payload_obj)),
        }
    )

    handle_dashboard_post(handler, path="/api/system/update/sync", deps=deps)

    assert sync_calls == 0
    assert calls == [(401, {"ok": False, "error": "API token required for write endpoint"})]


def test_handle_dashboard_post_requires_token_for_rollback_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    cleanup_calls = 0

    def _cleanup_rollbacks(**kwargs: object) -> dict[str, object]:
        nonlocal cleanup_calls
        cleanup_calls += 1
        return {"ok": True}

    monkeypatch.setattr(
        "meshdash.http_routes_post._cleanup_update_rollback_branches_helper",
        _cleanup_rollbacks,
    )
    handler = _FakeHandler()
    calls: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(send_chat_fn=None, api_token="secret", to_int_fn=to_int)
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: calls.append((status_code, payload_obj)),
        }
    )

    handle_dashboard_post(handler, path="/api/system/update/rollback-cleanup", deps=deps)

    assert cleanup_calls == 0
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
