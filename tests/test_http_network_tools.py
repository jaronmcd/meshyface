import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.api_input_network_tools import NetworkToolRequest
from meshdash.helpers import to_int
from meshdash.http_api import make_http_handler
from meshdash.http_api_post import build_post_route_dependencies
from meshdash.http_routes_post import handle_dashboard_post


class _FakeHandler:
    def __init__(self, body: bytes = b"", *, headers: dict[str, object] | None = None) -> None:
        self.path = "/api/tools/network"
        self.headers = dict(headers or {})
        self.headers.setdefault("Host", "127.0.0.1:8877")
        self.client_address = ("127.0.0.1", 12345)
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()

    def send_response(self, code: int) -> None:
        self._last_code = code

    def send_header(self, key: str, value: str) -> None:
        pass

    def end_headers(self) -> None:
        pass


def _same_origin_json_headers(body: bytes) -> dict[str, str]:
    return {
        "Content-Length": str(len(body)),
        "Content-Type": "application/json",
        "Host": "127.0.0.1:8877",
        "Origin": "http://127.0.0.1:8877",
        "Sec-Fetch-Site": "same-origin",
    }


def test_build_post_route_dependencies_exposes_network_parser_and_runner() -> None:
    def _runner(request: NetworkToolRequest) -> dict[str, object]:
        return {"ok": True, "command": request.command}

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        run_network_tool_fn=_runner,
        to_int_fn=to_int,
    )

    assert deps.run_network_tool_fn is _runner
    assert callable(deps.parse_network_tool_request_fn)


def test_make_http_handler_passes_run_network_tool_hook(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr("meshdash.http_api.build_get_route_dependencies", lambda **kwargs: object())

    def _fake_build_post_route_dependencies(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("meshdash.http_api.build_post_route_dependencies", _fake_build_post_route_dependencies)
    monkeypatch.setattr(
        "meshdash.http_api.build_dashboard_handler_class",
        lambda **kwargs: {"dispatch_get_fn": kwargs["dispatch_get_fn"], "dispatch_post_fn": kwargs["dispatch_post_fn"]},
    )

    def _state_fn():
        return {}

    def _run_network_tool_fn(request: NetworkToolRequest) -> dict[str, object]:
        return {"ok": True, "command": request.command}

    setattr(_state_fn, "run_network_tool_fn", _run_network_tool_fn)

    make_http_handler("<html></html>", _state_fn)

    assert captured["run_network_tool_fn"] is _run_network_tool_fn


def test_handle_dashboard_post_blocks_network_tools_in_private_mode() -> None:
    handler = _FakeHandler()
    calls: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(send_chat_fn=None, to_int_fn=to_int)
    deps = type(deps)(
        **{
            **deps.__dict__,
            "private_mode": True,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: calls.append((status_code, payload_obj)),
        }
    )

    handle_dashboard_post(handler, path="/api/tools/network", deps=deps)

    assert calls == [(403, {"ok": False, "error": "This endpoint is disabled in private mode"})]


def test_handle_dashboard_post_allows_browser_network_tools_when_token_configured() -> None:
    body = b'{"command":"nodes"}'
    handler = _FakeHandler(body, headers=_same_origin_json_headers(body))
    calls: list[tuple[int, object]] = []
    runs = 0

    def _run_network_tool(request: NetworkToolRequest) -> dict[str, object]:
        nonlocal runs
        runs += 1
        return {"ok": True, "command": request.command}

    deps = build_post_route_dependencies(send_chat_fn=None, api_token="secret", to_int_fn=to_int)
    deps = type(deps)(
        **{
            **deps.__dict__,
            "run_network_tool_fn": _run_network_tool,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: calls.append((status_code, payload_obj)),
        }
    )

    handle_dashboard_post(handler, path="/api/tools/network", deps=deps)

    assert runs == 1
    assert calls == [(200, {"ok": True, "command": "nodes"})]


def test_handle_dashboard_post_requires_token_for_external_network_tools() -> None:
    handler = _FakeHandler()
    calls: list[tuple[int, object]] = []
    runs = 0

    def _run_network_tool(request: NetworkToolRequest) -> dict[str, object]:
        nonlocal runs
        runs += 1
        return {"ok": True, "command": request.command}

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        run_network_tool_fn=_run_network_tool,
        api_token="secret",
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: calls.append((status_code, payload_obj)),
        }
    )

    handle_dashboard_post(handler, path="/api/tools/network", deps=deps)

    assert runs == 0
    assert calls == [(401, {"ok": False, "error": "API token required for write endpoint"})]


def test_handle_dashboard_post_rejects_cross_origin_network_tools() -> None:
    body = b'{"command":"nodes"}'
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
    runs = 0

    def _run_network_tool(request: NetworkToolRequest) -> dict[str, object]:
        nonlocal runs
        runs += 1
        return {"ok": True, "command": request.command}

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        run_network_tool_fn=_run_network_tool,
        api_token="secret",
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": lambda handler, *, status_code, payload_obj, **kwargs: calls.append((status_code, payload_obj)),
        }
    )

    handle_dashboard_post(handler, path="/api/tools/network", deps=deps)

    assert runs == 0
    assert calls == [(403, {"ok": False, "error": "Cross-origin writes are not allowed"})]


def test_handle_dashboard_post_dispatches_network_tool_requests() -> None:
    body = b'{"command":"nodes"}'
    handler = _FakeHandler(body, headers={"Content-Length": str(len(body))})
    calls: list[tuple[int, object]] = []

    def _write_json_response(handler, *, status_code, payload_obj, **kwargs):
        calls.append((status_code, payload_obj))

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        run_network_tool_fn=lambda request: {"ok": True, "command": request.command},
        to_int_fn=to_int,
    )
    deps = type(deps)(
        **{
            **deps.__dict__,
            "write_json_response_fn": _write_json_response,
        }
    )

    handle_dashboard_post(handler, path="/api/tools/network", deps=deps)

    assert calls == [(200, {"ok": True, "command": "nodes"})]
