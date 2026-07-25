import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.helpers import to_int
from meshdash.http_api import make_http_handler
from meshdash.http_api_post import build_post_route_dependencies
from meshdash.http_plugin_admin import request_is_loopback
from meshdash.http_routes_post import handle_dashboard_post


_PLUGIN_PACKAGE_DIGEST = "sha256:" + ("a" * 64)
_CURRENT_PLUGIN_PACKAGE_DIGEST = "sha256:" + ("b" * 64)


def _plugin_request_body(**values: object) -> bytes:
    return json.dumps(
        {
            **values,
            "package_digest": _PLUGIN_PACKAGE_DIGEST,
        }
    ).encode("utf-8")


def _plugin_runtime_request_body(**values: object) -> bytes:
    return json.dumps(values).encode("utf-8")


class _FakeHandler:
    def __init__(
        self,
        body: bytes = b"",
        *,
        headers: dict[str, object] | None = None,
        client_host: str = "127.0.0.1",
    ) -> None:
        self.path = "/"
        self.headers = dict(headers or {})
        self.headers.setdefault("Host", "127.0.0.1:8877")
        self.client_address = (client_host, 12345)
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
        "/api/settings/file_transfer",
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
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
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


def test_handle_dashboard_post_runs_plugin_console_command() -> None:
    body = json.dumps(
        {
            "command": "zork",
            "text": "zork",
            "handler": "command",
            "session_id": "session-1",
        }
    ).encode("utf-8")
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
        },
    )
    calls: list[tuple[int, object]] = []
    received: list[dict[str, object]] = []

    def _write_json_response(handler, *, status_code, payload_obj, **kwargs):
        calls.append((status_code, payload_obj))

    def _run_plugin_console_command(**kwargs: object) -> dict[str, object]:
        received.append(dict(kwargs))
        return {
            "ok": True,
            "reply_text": "started",
            "session_id": kwargs.get("session_id"),
            "active_session": True,
        }

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        run_plugin_console_command_fn=_run_plugin_console_command,
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": _write_json_response,
        }
    )

    handle_dashboard_post(handler, path="/api/plugins/console", deps=deps)

    assert received == [
        {
            "command": "zork",
            "text": "zork",
            "handler": "command",
            "session_id": "session-1",
        }
    ]
    assert calls == [
        (
            200,
            {
                "ok": True,
                "reply_text": "started",
                "session_id": "session-1",
                "active_session": True,
            },
        )
    ]


def test_plugin_console_requires_json_content_type() -> None:
    body = json.dumps({"command": "zork", "text": "zork"}).encode("utf-8")
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "text/plain",
            "Host": "127.0.0.1:8877",
            "Origin": "http://127.0.0.1:8877",
            "Sec-Fetch-Site": "same-origin",
        },
    )
    calls: list[tuple[int, object]] = []
    runs = 0

    def _run_plugin_console_command(**_kwargs: object) -> dict[str, object]:
        nonlocal runs
        runs += 1
        return {"ok": True}

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        run_plugin_console_command_fn=_run_plugin_console_command,
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/plugins/console", deps=deps)

    assert runs == 0
    assert calls == [
        (
            415,
            {
                "ok": False,
                "error": "Write endpoints require application/json",
            },
        )
    ]


def test_plugin_console_rejects_cross_origin_browser_write() -> None:
    body = json.dumps({"command": "zork", "text": "zork"}).encode("utf-8")
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json; charset=utf-8",
            "Host": "127.0.0.1:8877",
            "Origin": "https://attacker.example",
            "Sec-Fetch-Site": "cross-site",
        },
    )
    calls: list[tuple[int, object]] = []
    runs = 0

    def _run_plugin_console_command(**_kwargs: object) -> dict[str, object]:
        nonlocal runs
        runs += 1
        return {"ok": True}

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        run_plugin_console_command_fn=_run_plugin_console_command,
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/plugins/console", deps=deps)

    assert runs == 0
    assert calls == [
        (
            403,
            {
                "ok": False,
                "error": "Cross-origin writes are not allowed",
            },
        )
    ]


def test_remote_plugin_console_client_can_use_configured_token() -> None:
    body = json.dumps({"command": "zork", "text": "zork"}).encode("utf-8")
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
            "Host": "dashboard.example",
            "X-API-Token": "secret",
        },
        client_host="192.168.1.42",
    )
    calls: list[tuple[int, object]] = []
    runs = 0

    def _run_plugin_console_command(**_kwargs: object) -> dict[str, object]:
        nonlocal runs
        runs += 1
        return {"ok": True}

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        run_plugin_console_command_fn=_run_plugin_console_command,
        api_token="secret",
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/plugins/console", deps=deps)

    assert runs == 1
    assert calls == [(200, {"ok": True})]


def test_plugin_console_requires_api_token_when_configured() -> None:
    body = json.dumps({"command": "zork", "text": "zork"}).encode("utf-8")
    handler = _FakeHandler(body, headers={"Content-Length": str(len(body))})
    calls: list[tuple[int, object]] = []
    runs = 0

    def _run_plugin_console_command(**_kwargs: object) -> dict[str, object]:
        nonlocal runs
        runs += 1
        return {"ok": True}

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        run_plugin_console_command_fn=_run_plugin_console_command,
        api_token="secret",
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/plugins/console", deps=deps)

    assert runs == 0
    assert calls == [(401, {"ok": False, "error": "API token required for write endpoint"})]


def test_plugin_console_is_blocked_in_private_mode() -> None:
    body = json.dumps({"command": "zork", "text": "zork"}).encode("utf-8")
    handler = _FakeHandler(body, headers={"Content-Length": str(len(body))})
    calls: list[tuple[int, object]] = []
    runs = 0

    def _run_plugin_console_command(**_kwargs: object) -> dict[str, object]:
        nonlocal runs
        runs += 1
        return {"ok": True}

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        run_plugin_console_command_fn=_run_plugin_console_command,
        private_mode=True,
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/plugins/console", deps=deps)

    assert runs == 0
    assert calls == [
        (403, {"ok": False, "error": "This endpoint is disabled in private mode"})
    ]


def test_token_protected_write_rejects_cross_origin_browser_request() -> None:
    body = json.dumps({"text": "hello"}).encode("utf-8")
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
            "Host": "127.0.0.1:8877",
            "Origin": "https://attacker.example",
            "Sec-Fetch-Site": "cross-site",
        },
    )
    calls: list[tuple[int, object]] = []

    deps = build_post_route_dependencies(send_chat_fn=None, to_int_fn=to_int)
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/chat/send", deps=deps)

    assert calls == [(403, {"ok": False, "error": "Cross-origin writes are not allowed"})]


def test_token_protected_browser_write_requires_json_content_type() -> None:
    body = json.dumps({"text": "hello"}).encode("utf-8")
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "text/plain",
            "Host": "127.0.0.1:8877",
            "Origin": "http://127.0.0.1:8877",
            "Sec-Fetch-Site": "same-origin",
        },
    )
    calls: list[tuple[int, object]] = []

    deps = build_post_route_dependencies(send_chat_fn=None, to_int_fn=to_int)
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/chat/send", deps=deps)

    assert calls == [(415, {"ok": False, "error": "Write endpoints require application/json"})]


def test_tokenless_protected_write_allows_same_origin_lan_client() -> None:
    body = json.dumps({"text": "hello"}).encode("utf-8")
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
            "Host": "192.168.1.10:8877",
            "Origin": "http://192.168.1.10:8877",
            "Sec-Fetch-Site": "same-origin",
        },
        client_host="192.168.1.42",
    )
    calls: list[tuple[int, object]] = []
    runs = 0

    def _send_chat(**_kwargs: object) -> None:
        nonlocal runs
        runs += 1

    deps = build_post_route_dependencies(send_chat_fn=_send_chat, to_int_fn=to_int)
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/chat/send", deps=deps)

    assert runs == 1
    assert calls[0][0] == 200


def test_handle_dashboard_post_updates_raw_packet_capture_settings() -> None:
    body = json.dumps({"capture_enabled": True}).encode("utf-8")
    handler = _FakeHandler(body, headers={"Content-Length": str(len(body))})
    calls: list[tuple[int, object]] = []
    received: list[object] = []

    def _write_json_response(handler, *, status_code, payload_obj, **kwargs):
        calls.append((status_code, payload_obj))

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_raw_packet_capture_settings_fn=lambda settings: (
            received.append(settings)
            or {"ok": True, "capture_enabled": settings["capture_enabled"]}
        ),
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


def test_plugin_management_returns_structured_disabled_error() -> None:
    body = _plugin_request_body(plugin_id="echo", enabled=True)
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
        },
    )
    calls: list[tuple[int, object]] = []
    disabled = {
        "ok": False,
        "error": {
            "code": "plugin_runtime_disabled",
            "message": "Python plugin runtime is disabled at startup",
        },
    }
    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_plugin_enabled_fn=lambda _plugin_id, _enabled, *, expected_package_digest=None: disabled,
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/settings/plugins", deps=deps)

    assert calls == [(503, disabled)]


def test_plugin_management_applies_individual_setting_live() -> None:
    body = _plugin_request_body(plugin_id="echo", enabled=False)
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
        },
    )
    calls: list[tuple[int, object]] = []
    received: list[tuple[object, bool, object]] = []
    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_plugin_enabled_fn=lambda plugin_id, enabled, *, expected_package_digest=None: (
            received.append((plugin_id, enabled, expected_package_digest))
            or {
                "ok": True,
                "plugin_id": plugin_id,
                "enabled": enabled,
                "active": enabled,
                "restart_required": False,
            }
        ),
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/settings/plugins", deps=deps)

    assert received == [("echo", False, _PLUGIN_PACKAGE_DIGEST)]
    assert calls == [
        (
            200,
            {
                "ok": True,
                "plugin_id": "echo",
                "enabled": False,
                "active": False,
                "restart_required": False,
            },
        )
    ]


def test_plugin_management_returns_structured_unknown_plugin_error() -> None:
    body = _plugin_request_body(plugin_id="missing", enabled=True)
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
        },
    )
    calls: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_plugin_enabled_fn=lambda _plugin_id, _enabled, *, expected_package_digest=None: {
            "ok": False,
            "error": {"code": "unknown_plugin", "message": "Unknown plugin ID"},
        },
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/settings/plugins", deps=deps)

    assert calls == [
        (
            404,
            {
                "ok": False,
                "error": {"code": "unknown_plugin", "message": "Unknown plugin ID"},
            },
        )
    ]


def test_plugin_management_rejects_stale_package_digest() -> None:
    body = _plugin_request_body(plugin_id="echo", enabled=True)
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
        },
    )
    calls: list[tuple[int, object]] = []
    received: list[object] = []

    def _setter(
        _plugin_id: object,
        _enabled: bool,
        *,
        expected_package_digest: object | None = None,
    ) -> dict[str, object]:
        received.append(expected_package_digest)
        return {
            "ok": False,
            "error": {
                "code": "plugin_identity_changed",
                "message": "Plugin package identity changed; refresh and review it",
            },
            "package_digest": _CURRENT_PLUGIN_PACKAGE_DIGEST,
        }

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_plugin_enabled_fn=_setter,
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/settings/plugins", deps=deps)

    assert received == [_PLUGIN_PACKAGE_DIGEST]
    assert calls == [
        (
            409,
            {
                "ok": False,
                "error": {
                    "code": "plugin_identity_changed",
                    "message": "Plugin package identity changed; refresh and review it",
                },
                "package_digest": _CURRENT_PLUGIN_PACKAGE_DIGEST,
            },
        )
    ]


def test_plugin_management_returns_structured_invalid_request_error() -> None:
    body = _plugin_request_body(plugin_id="echo", enabled="yes")
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
        },
    )
    calls: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_plugin_enabled_fn=lambda _plugin_id, _enabled, *, expected_package_digest=None: {
            "ok": True
        },
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/settings/plugins", deps=deps)

    assert calls == [
        (
            400,
            {
                "ok": False,
                "error": {
                    "code": "invalid_request",
                    "message": "enabled must be a boolean",
                },
            },
        )
    ]


@pytest.mark.parametrize(
    ("path", "payload", "expected_message"),
    (
        (
            "/api/settings/plugins",
            {"plugin_id": "echo", "enabled": True},
            "request body must contain only plugin_id, enabled, and package_digest",
        ),
        (
            "/api/settings/plugins/config",
            {"plugin_id": "echo", "settings": {}},
            "request body must contain only plugin_id, settings, and package_digest",
        ),
        (
            "/api/settings/plugins/routes",
            {"plugin_id": "echo", "mesh_enabled": True, "console_enabled": True},
            (
                "request body must contain only plugin_id, mesh_enabled, "
                "console_enabled, ticker_enabled, view_enabled, and package_digest"
            ),
        ),
    ),
)
def test_plugin_mutations_require_package_digest(
    path: str,
    payload: dict[str, object],
    expected_message: str,
) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
        },
    )
    calls: list[tuple[int, object]] = []
    updates: list[str] = []

    def _set_enabled(
        _plugin_id: object,
        _enabled: bool,
        *,
        expected_package_digest: object,
    ) -> dict[str, object]:
        updates.append(str(expected_package_digest))
        return {"ok": True}

    def _set_settings(
        _plugin_id: object,
        _settings: object,
        *,
        expected_package_digest: object,
    ) -> dict[str, object]:
        updates.append(str(expected_package_digest))
        return {"ok": True}

    def _set_routes(
        _plugin_id: object,
        *,
        mesh_enabled: bool,
        console_enabled: bool,
        ticker_enabled: bool,
        view_enabled: bool,
        expected_package_digest: object,
    ) -> dict[str, object]:
        del mesh_enabled, console_enabled, ticker_enabled, view_enabled
        updates.append(str(expected_package_digest))
        return {"ok": True}

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_plugin_enabled_fn=_set_enabled,
        set_plugin_settings_fn=_set_settings,
        set_plugin_route_policy_fn=_set_routes,
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path=path, deps=deps)

    assert updates == []
    assert calls == [
        (
            400,
            {
                "ok": False,
                "error": {
                    "code": "invalid_request",
                    "message": expected_message,
                },
            },
        )
    ]


def test_plugin_configuration_applies_validated_settings() -> None:
    body = _plugin_request_body(
        plugin_id="configured",
        settings={"allowed_nodes": ["!01020304"]},
    )
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
        },
    )
    calls: list[tuple[int, object]] = []
    received: list[tuple[object, object, object]] = []
    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_plugin_settings_fn=lambda plugin_id, settings, *, expected_package_digest=None: (
            received.append((plugin_id, settings, expected_package_digest))
            or {"ok": True, "plugin_id": plugin_id, "settings": settings}
        ),
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/settings/plugins/config", deps=deps)

    assert received == [
        (
            "configured",
            {"allowed_nodes": ["!01020304"]},
            _PLUGIN_PACKAGE_DIGEST,
        )
    ]
    assert calls == [
        (
            200,
            {
                "ok": True,
                "plugin_id": "configured",
                "settings": {"allowed_nodes": ["!01020304"]},
            },
        )
    ]


def test_plugin_route_policy_applies_validated_booleans() -> None:
    body = _plugin_request_body(
        plugin_id="echo",
        mesh_enabled=False,
        console_enabled=True,
        ticker_enabled=False,
        view_enabled=False,
    )
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
        },
    )
    calls: list[tuple[int, object]] = []
    received: list[tuple[object, bool, bool, bool, bool, object]] = []
    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_plugin_route_policy_fn=(
            lambda plugin_id,
            *,
            mesh_enabled,
            console_enabled,
            ticker_enabled,
            view_enabled,
            expected_package_digest=None: (
                received.append(
                    (
                        plugin_id,
                        mesh_enabled,
                        console_enabled,
                        ticker_enabled,
                        view_enabled,
                        expected_package_digest,
                    )
                )
                or {
                    "ok": True,
                    "plugin_id": plugin_id,
                    "mesh_enabled": mesh_enabled,
                    "console_enabled": console_enabled,
                    "ticker_enabled": ticker_enabled,
                    "view_enabled": view_enabled,
                }
            )
        ),
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/settings/plugins/routes", deps=deps)

    assert received == [("echo", False, True, False, False, _PLUGIN_PACKAGE_DIGEST)]
    assert calls == [
        (
            200,
            {
                "ok": True,
                "plugin_id": "echo",
                "mesh_enabled": False,
                "console_enabled": True,
                "ticker_enabled": False,
                "view_enabled": False,
            },
        )
    ]


def test_plugin_runtime_master_applies_validated_boolean() -> None:
    body = _plugin_runtime_request_body(enabled=False)
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
        },
    )
    calls: list[tuple[int, object]] = []
    received: list[bool] = []
    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_plugin_runtime_enabled_fn=lambda enabled: (
            received.append(enabled)
            or {
                "ok": True,
                "runtime_enabled": enabled,
                "enabled_plugins": [],
            }
        ),
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/settings/plugins/runtime", deps=deps)

    assert received == [False]
    assert calls == [
        (
            200,
            {
                "ok": True,
                "runtime_enabled": False,
                "enabled_plugins": [],
            },
        )
    ]


def test_plugin_runtime_master_rejects_invalid_request() -> None:
    body = _plugin_runtime_request_body(enabled="false")
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
        },
    )
    calls: list[tuple[int, object]] = []
    updates = 0

    def _setter(_enabled: bool) -> dict[str, object]:
        nonlocal updates
        updates += 1
        return {"ok": True}

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_plugin_runtime_enabled_fn=_setter,
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/settings/plugins/runtime", deps=deps)

    assert updates == 0
    assert calls == [
        (
            400,
            {
                "ok": False,
                "error": {
                    "code": "invalid_request",
                    "message": "enabled must be a boolean",
                },
            },
        )
    ]


def test_plugin_configuration_rejects_stale_package_digest() -> None:
    body = _plugin_request_body(plugin_id="configured", settings={"mode": "safe"})
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
        },
    )
    calls: list[tuple[int, object]] = []
    received: list[object] = []

    def _setter(
        _plugin_id: object,
        _settings: object,
        *,
        expected_package_digest: object | None = None,
    ) -> dict[str, object]:
        received.append(expected_package_digest)
        return {
            "ok": False,
            "error": {
                "code": "plugin_identity_changed",
                "message": "Plugin package identity changed; refresh before saving",
            },
            "package_digest": _CURRENT_PLUGIN_PACKAGE_DIGEST,
        }

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_plugin_settings_fn=_setter,
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(
        handler,
        path="/api/settings/plugins/config",
        deps=deps,
    )

    assert received == [_PLUGIN_PACKAGE_DIGEST]
    assert calls == [
        (
            409,
            {
                "ok": False,
                "error": {
                    "code": "plugin_identity_changed",
                    "message": "Plugin package identity changed; refresh before saving",
                },
                "package_digest": _CURRENT_PLUGIN_PACKAGE_DIGEST,
            },
        )
    ]


def test_plugin_configuration_requires_api_token_when_configured() -> None:
    body = _plugin_request_body(plugin_id="configured", settings={})
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
        },
    )
    calls: list[tuple[int, object]] = []
    updates = 0

    def _setter(
        _plugin_id: object,
        _settings: object,
        *,
        expected_package_digest: object | None = None,
    ) -> dict[str, object]:
        nonlocal updates
        del expected_package_digest
        updates += 1
        return {"ok": True}

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_plugin_settings_fn=_setter,
        api_token="secret",
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/settings/plugins/config", deps=deps)

    assert updates == 0
    assert calls == [
        (
            401,
            {
                "ok": False,
                "error": "API token required for plugin administration",
            },
        )
    ]


def test_plugin_management_without_token_is_loopback_only() -> None:
    body = _plugin_request_body(plugin_id="echo", enabled=True)
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
        },
        client_host="192.0.2.20",
    )
    calls: list[tuple[int, object]] = []
    updates = 0

    def _setter(
        _plugin_id: object,
        _enabled: bool,
        *,
        expected_package_digest: object | None = None,
    ) -> dict[str, object]:
        nonlocal updates
        del expected_package_digest
        updates += 1
        return {"ok": True}

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_plugin_enabled_fn=_setter,
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/settings/plugins", deps=deps)

    assert updates == 0
    assert calls == [
        (
            403,
            {
                "ok": False,
                "error": (
                    "Plugin administration is tokenless only from loopback; "
                    "configure an API token for remote access"
                ),
            },
        )
    ]


@pytest.mark.parametrize(
    ("host_header", "client_host"),
    (
        ("localhost:8877", "127.0.0.1"),
        ("127.0.0.42:8877", "127.0.0.1"),
        ("[::1]:8877", "::1"),
    ),
)
def test_tokenless_plugin_admin_accepts_only_loopback_hosts(
    host_header: str,
    client_host: str,
) -> None:
    handler = _FakeHandler(
        headers={"Host": host_header},
        client_host=client_host,
    )

    assert request_is_loopback(handler) is True


@pytest.mark.parametrize(
    ("header_name", "header_value"),
    (
        ("X-Forwarded-For", "127.0.0.1"),
        ("X-Forwarded-Proto", "http"),
        ("Forwarded", "for=127.0.0.1"),
        ("X-Real-IP", "127.0.0.1"),
        ("Via", "1.1 local-proxy"),
    ),
)
def test_tokenless_plugin_admin_rejects_any_proxy_metadata(
    header_name: str,
    header_value: str,
) -> None:
    handler = _FakeHandler(
        headers={
            "Host": "127.0.0.1:8877",
            header_name: header_value,
        },
    )

    assert request_is_loopback(handler) is False


def test_plugin_management_rejects_non_loopback_host_from_loopback_client() -> None:
    body = _plugin_request_body(plugin_id="echo", enabled=True)
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
            "Host": "dashboard.example",
        },
    )
    calls: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_plugin_enabled_fn=lambda _plugin_id, _enabled, *, expected_package_digest=None: {
            "ok": True
        },
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/settings/plugins", deps=deps)

    assert calls == [
        (
            403,
            {
                "ok": False,
                "error": (
                    "Plugin administration is tokenless only from loopback; "
                    "configure an API token for remote access"
                ),
            },
        )
    ]


def test_plugin_management_requires_json_content_type() -> None:
    body = _plugin_request_body(plugin_id="echo", enabled=True)
    handler = _FakeHandler(
        body,
        headers={"Content-Length": str(len(body)), "Content-Type": "text/plain"},
    )
    calls: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_plugin_enabled_fn=lambda _plugin_id, _enabled, *, expected_package_digest=None: {
            "ok": True
        },
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/settings/plugins", deps=deps)

    assert calls == [
        (
            415,
            {
                "ok": False,
                "error": "Plugin administration requires application/json",
            },
        )
    ]


def test_plugin_management_rejects_cross_origin_browser_write() -> None:
    body = _plugin_request_body(plugin_id="echo", enabled=True)
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json; charset=utf-8",
            "Host": "127.0.0.1:8877",
            "Origin": "https://attacker.example",
            "Sec-Fetch-Site": "cross-site",
        },
    )
    calls: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_plugin_enabled_fn=lambda _plugin_id, _enabled, *, expected_package_digest=None: {
            "ok": True
        },
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/settings/plugins", deps=deps)

    assert calls == [
        (
            403,
            {
                "ok": False,
                "error": "Cross-origin plugin administration is not allowed",
            },
        )
    ]


def test_plugin_management_accepts_same_origin_browser_write() -> None:
    body = _plugin_request_body(plugin_id="echo", enabled=True)
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
            "Host": "localhost:8877",
            "Origin": "http://localhost:8877",
            "Sec-Fetch-Site": "same-origin",
        },
    )
    calls: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_plugin_enabled_fn=lambda plugin_id, enabled, *, expected_package_digest=None: {
            "ok": True,
            "plugin_id": plugin_id,
            "enabled": enabled,
        },
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/settings/plugins", deps=deps)

    assert calls == [
        (
            200,
            {
                "ok": True,
                "plugin_id": "echo",
                "enabled": True,
            },
        )
    ]


def test_remote_non_browser_plugin_client_can_use_configured_token() -> None:
    body = _plugin_request_body(plugin_id="echo", enabled=True)
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
            "X-API-Token": "secret",
            "X-Forwarded-For": "192.0.2.20",
        },
        client_host="192.0.2.20",
    )
    calls: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(
        send_chat_fn=None,
        set_plugin_enabled_fn=lambda plugin_id, enabled, *, expected_package_digest=None: {
            "ok": True,
            "plugin_id": plugin_id,
            "enabled": enabled,
            "active": enabled,
        },
        api_token="secret",
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/settings/plugins", deps=deps)

    assert calls == [
        (
            200,
            {
                "ok": True,
                "plugin_id": "echo",
                "enabled": True,
                "active": True,
            },
        )
    ]


def test_make_http_handler_wires_plugin_management_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "meshdash.http_api.build_get_route_dependencies",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(
        "meshdash.http_api.build_post_route_dependencies",
        lambda **kwargs: captured.update(kwargs) or object(),
    )
    monkeypatch.setattr(
        "meshdash.http_api.build_dashboard_handler_class",
        lambda **_kwargs: object,
    )

    def _state_fn() -> dict[str, object]:
        return {}

    def _set_plugin_enabled(
        plugin_id: object,
        enabled: bool,
        *,
        expected_package_digest: object | None = None,
    ) -> dict[str, object]:
        del expected_package_digest
        return {"ok": True, "plugin_id": plugin_id, "enabled": enabled}

    def _set_plugin_settings(
        plugin_id: object,
        settings: object,
        *,
        expected_package_digest: object | None = None,
    ) -> dict[str, object]:
        del expected_package_digest
        return {"ok": True, "plugin_id": plugin_id, "settings": settings}

    def _set_plugin_route_policy(
        plugin_id: object,
        *,
        mesh_enabled: bool,
        console_enabled: bool,
        ticker_enabled: bool,
        view_enabled: bool,
        expected_package_digest: object | None = None,
    ) -> dict[str, object]:
        del expected_package_digest
        return {
            "ok": True,
            "plugin_id": plugin_id,
            "mesh_enabled": mesh_enabled,
            "console_enabled": console_enabled,
            "ticker_enabled": ticker_enabled,
            "view_enabled": view_enabled,
        }

    def _set_plugin_runtime_enabled(enabled: bool) -> dict[str, object]:
        return {"ok": True, "runtime_enabled": enabled}

    def _run_plugin_console_command(**kwargs: object) -> dict[str, object]:
        return {"ok": True, "command": kwargs.get("command")}

    setattr(_state_fn, "set_plugin_enabled_fn", _set_plugin_enabled)
    setattr(_state_fn, "set_plugin_settings_fn", _set_plugin_settings)
    setattr(_state_fn, "set_plugin_route_policy_fn", _set_plugin_route_policy)
    setattr(_state_fn, "set_plugin_runtime_enabled_fn", _set_plugin_runtime_enabled)
    setattr(_state_fn, "run_plugin_console_command_fn", _run_plugin_console_command)

    make_http_handler("<html></html>", _state_fn)

    assert captured["set_plugin_enabled_fn"] is _set_plugin_enabled
    assert captured["set_plugin_settings_fn"] is _set_plugin_settings
    assert captured["set_plugin_route_policy_fn"] is _set_plugin_route_policy
    assert captured["set_plugin_runtime_enabled_fn"] is _set_plugin_runtime_enabled
    assert captured["run_plugin_console_command_fn"] is _run_plugin_console_command


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
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
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
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
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
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/system/update", deps=deps)

    assert update_calls == 0
    assert captured == {"target_branch": "main", "target_commit": "dddddddd"}
    assert calls == [
        (200, {"ok": True, "rollback": True, "rollback_branch": "rollback/main-dddddddd1111"})
    ]


def test_handle_dashboard_post_syncs_system_update_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/system/update/sync", deps=deps)

    assert captured["target_branch"] == "dev"
    assert calls == [
        (200, {"ok": True, "synced": True, "updated": False, "state": "update_available"})
    ]


def test_handle_dashboard_post_repairs_dirty_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _repair_checkout(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "ok": True,
            "repaired": True,
            "updated": False,
            "state": "up_to_date",
            "http_status": 200,
        }

    monkeypatch.setattr(
        "meshdash.http_routes_post._repair_dirty_update_checkout_helper",
        _repair_checkout,
    )
    body = b'{"branch":"main"}'
    handler = _FakeHandler(body, headers={"Content-Length": str(len(body))})
    calls: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(send_chat_fn=None, to_int_fn=to_int)
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: calls.append((status_code, payload_obj)),
        }
    )

    handle_dashboard_post(handler, path="/api/system/update/repair", deps=deps)

    assert captured["target_branch"] == "main"
    assert calls == [(200, {"ok": True, "repaired": True, "updated": False, "state": "up_to_date"})]


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
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
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


def test_handle_dashboard_post_requires_token_for_system_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/system/update", deps=deps)

    assert update_calls == 0
    assert calls == [(401, {"ok": False, "error": "API token required for write endpoint"})]


def test_handle_dashboard_post_requires_token_for_system_update_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sync_calls = 0

    def _sync_update(**kwargs: object) -> dict[str, object]:
        nonlocal sync_calls
        sync_calls += 1
        return {"ok": True}

    monkeypatch.setattr(
        "meshdash.http_routes_post._sync_update_branches_from_github_helper", _sync_update
    )
    handler = _FakeHandler()
    calls: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(send_chat_fn=None, api_token="secret", to_int_fn=to_int)
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/system/update/sync", deps=deps)

    assert sync_calls == 0
    assert calls == [(401, {"ok": False, "error": "API token required for write endpoint"})]


def test_handle_dashboard_post_requires_token_for_checkout_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repair_calls = 0

    def _repair_checkout(**kwargs: object) -> dict[str, object]:
        nonlocal repair_calls
        repair_calls += 1
        return {"ok": True}

    monkeypatch.setattr(
        "meshdash.http_routes_post._repair_dirty_update_checkout_helper",
        _repair_checkout,
    )
    handler = _FakeHandler()
    calls: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(send_chat_fn=None, api_token="secret", to_int_fn=to_int)
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/system/update/repair", deps=deps)

    assert repair_calls == 0
    assert calls == [(401, {"ok": False, "error": "API token required for write endpoint"})]


def test_handle_dashboard_post_requires_token_for_rollback_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
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
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
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
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: (
                calls.append((status_code, payload_obj))
            ),
        }
    )

    handle_dashboard_post(handler, path="/api/system/restart", deps=deps)

    assert restart_calls == 0
    assert calls == [(401, {"ok": False, "error": "API token required for write endpoint"})]
