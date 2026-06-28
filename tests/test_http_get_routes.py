from types import SimpleNamespace

import pytest

from meshdash.api_input_history import parse_node_history_request, parse_online_activity_request
from meshdash.helpers import to_int
from meshdash.http_routes_get import handle_dashboard_get


class _StateFn:
    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self.payload = payload or {}

    def __call__(self) -> dict[str, object]:
        return self.payload

    def lite(self) -> dict[str, object]:
        return self.payload


class _Metrics:
    def __init__(self) -> None:
        self.state_polls = 0
        self.state_errors = 0
        self.private_blocks = 0

    def snapshot(self) -> dict[str, object]:
        return {
            "state_poll_requests_total": self.state_polls,
            "state_poll_errors_total": self.state_errors,
            "private_mode_blocks_total": self.private_blocks,
        }

    def record_state_poll_request(self) -> None:
        self.state_polls += 1

    def record_state_poll_error(self) -> None:
        self.state_errors += 1

    def record_private_mode_block(self) -> None:
        self.private_blocks += 1


def _make_deps(**overrides: object) -> SimpleNamespace:
    state_payload = {
        "summary": {
            "uptime_seconds": 42,
            "node_count": 3,
            "live_packet_count": 8,
            "radio_link": {"connected": True, "state": "connected"},
            "radio_connection": {"state": "connected"},
            "revision": {
                "version": "1.2.3",
                "commit": "abc123",
            },
        },
        "generated_at": 12345,
    }
    recorder = SimpleNamespace(html=[], json=[], text=[])
    deps = SimpleNamespace(
        html_text="<html>dashboard</html>",
        state_fn=_StateFn(state_payload),
        node_history_fn=None,
        online_activity_fn=None,
        summary_metrics_fn=None,
        default_node_history_hours=24,
        to_int_fn=to_int,
        parse_node_history_request_fn=parse_node_history_request,
        parse_online_activity_request_fn=parse_online_activity_request,
        empty_node_history_fn=lambda node_id: {"ok": False, "node_id": node_id, "points": []},
        empty_online_activity_fn=lambda hours: {"ok": False, "hours": hours, "items": []},
        empty_summary_metrics_fn=lambda hours: {"ok": False, "hours": hours, "points": []},
        write_html_response_fn=lambda handler, *, html_text, no_store=False, **kwargs: recorder.html.append(
            (html_text, no_store)
        ),
        write_json_response_fn=lambda handler, *, status_code, payload_obj, no_store=False, **kwargs: recorder.json.append(
            (status_code, payload_obj, no_store)
        ),
        write_text_response_fn=lambda handler, *, status_code, text, extra_headers=None, **kwargs: recorder.text.append(
            (status_code, text, extra_headers or {})
        ),
        get_theme_settings_fn=lambda: {"ok": True, "theme": "dark"},
        get_bbs_settings_fn=lambda: {"ok": True, "enabled": False},
        get_bbs_host_runtime_fn=lambda: {"ok": True, "running": False},
        get_custom_telemetry_settings_fn=lambda: {"ok": True, "rules": []},
        private_mode=False,
        api_metrics=_Metrics(),
        recorder=recorder,
    )
    for key, value in overrides.items():
        setattr(deps, key, value)
    return deps


def test_dashboard_get_serves_root_version_health_and_metrics() -> None:
    deps = _make_deps()

    handle_dashboard_get(object(), path="/", query="", deps=deps)
    handle_dashboard_get(object(), path="/api/version", query="", deps=deps)
    handle_dashboard_get(object(), path="/api/health", query="", deps=deps)
    handle_dashboard_get(object(), path="/metrics", query="", deps=deps)

    assert deps.recorder.html == [("<html>dashboard</html>", True)]
    assert deps.recorder.json[0][0] == 200
    assert deps.recorder.json[0][1]["version"] == "1.2.3"
    assert deps.recorder.json[0][1]["commit"] == "abc123"
    assert deps.recorder.json[1][0] == 200
    assert deps.recorder.json[1][1]["status"] == "ok"
    assert deps.recorder.json[1][1]["node_count"] == 3
    assert deps.recorder.text[0][0] == 200
    assert "meshdash_live_packet_count 8" in deps.recorder.text[0][1]
    assert "meshdash_radio_link_up 1" in deps.recorder.text[0][1]


def test_dashboard_get_reports_version_and_health_errors() -> None:
    def failing_state() -> dict[str, object]:
        raise RuntimeError("state unavailable")

    deps = _make_deps(state_fn=failing_state)

    handle_dashboard_get(object(), path="/api/version", query="", deps=deps)
    handle_dashboard_get(object(), path="/api/health", query="", deps=deps)

    assert deps.recorder.json[0][0] == 500
    assert deps.recorder.json[0][1]["ok"] is False
    assert "state unavailable" in deps.recorder.json[0][1]["error"]
    assert deps.recorder.json[1][0] == 503
    assert deps.recorder.json[1][1]["status"] == "error"


def test_dashboard_get_serves_system_update_status(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _status(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"ok": True, "available": True, "state": "up_to_date"}

    monkeypatch.setattr(
        "meshdash.http_routes_get._build_update_status_payload_helper",
        _status,
    )
    deps = _make_deps()

    handle_dashboard_get(object(), path="/api/system/update", query="branch=beta", deps=deps)

    assert captured["target_branch"] == "beta"
    assert deps.recorder.json == [(200, {"ok": True, "available": True, "state": "up_to_date"}, True)]


def test_dashboard_get_can_refresh_system_update_status(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _refresh(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"ok": True, "available": True, "state": "update_available", "refreshed": True}

    monkeypatch.setattr(
        "meshdash.http_routes_get._refresh_update_status_from_github_helper",
        _refresh,
    )
    deps = _make_deps()

    handle_dashboard_get(object(), path="/api/system/update", query="branch=beta&refresh=1", deps=deps)

    assert captured["target_branch"] == "beta"
    assert deps.recorder.json == [
        (200, {"ok": True, "available": True, "state": "update_available", "refreshed": True}, True)
    ]


def test_dashboard_get_serves_raw_payloads_from_helpers_and_snapshot() -> None:
    state_fn = _StateFn(
        {
            "my_info": {"id": "!fallback"},
            "metadata": {"firmware": "x"},
            "local_state": {"foo": "bar"},
            "nodes_full": [{"id": "!node"}],
        }
    )
    state_fn.raw_my_info = lambda: {"id": "!raw"}  # type: ignore[attr-defined]
    deps = _make_deps(state_fn=state_fn)

    handle_dashboard_get(object(), path="/api/raw/my_info", query="", deps=deps)
    handle_dashboard_get(object(), path="/api/raw/metadata", query="", deps=deps)
    handle_dashboard_get(object(), path="/api/raw/local_state", query="", deps=deps)
    handle_dashboard_get(object(), path="/api/raw/nodes_full", query="", deps=deps)

    assert deps.recorder.json == [
        (200, {"id": "!raw"}, True),
        (200, {"firmware": "x"}, True),
        (200, {"foo": "bar"}, True),
        (200, [{"id": "!node"}], True),
    ]


def test_dashboard_get_dispatches_history_summary_routes() -> None:
    node_calls: list[tuple[str, object, object]] = []
    online_calls: list[object] = []
    summary_calls: list[object] = []
    deps = _make_deps(
        node_history_fn=lambda node_id, hours_override, points_override: node_calls.append(
            (node_id, hours_override, points_override)
        )
        or {"ok": True, "node_id": node_id, "points": []},
        online_activity_fn=lambda hours_override: online_calls.append(hours_override)
        or {"ok": True, "hours": hours_override, "items": []},
        summary_metrics_fn=lambda hours_override: summary_calls.append(hours_override)
        or {"ok": True, "hours": hours_override, "points": []},
    )

    handle_dashboard_get(object(), path="/api/history/node", query="node_id=!abc&hours=12&points=5", deps=deps)
    handle_dashboard_get(object(), path="/api/history/online", query="hours=6", deps=deps)
    handle_dashboard_get(object(), path="/api/history/summary", query="hours=3", deps=deps)

    assert node_calls == [("!abc", 12, 5)]
    assert online_calls == [6]
    assert summary_calls == [3]
    assert [row[1]["ok"] for row in deps.recorder.json] == [True, True, True]


def test_dashboard_get_dispatches_top_nodes_links_environment_and_malformed_history() -> None:
    calls: dict[str, object] = {}
    state_fn = _StateFn(
        {
            "local_node_id": "!self",
            "my_info": {"id": "!self"},
        }
    )
    state_fn.top_nodes_fn = lambda **kwargs: calls.setdefault("top", kwargs) or {"ok": True, "items": []}  # type: ignore[attr-defined]
    state_fn.link_edges_fn = lambda **kwargs: calls.setdefault("links", kwargs) or {"ok": True, "edges": []}  # type: ignore[attr-defined]
    state_fn.location_estimates_fn = lambda **kwargs: calls.setdefault("location", kwargs) or {"ok": True, "estimates": []}  # type: ignore[attr-defined]
    state_fn.environment_metrics_history_fn = lambda **kwargs: calls.setdefault("environment", kwargs) or {  # type: ignore[attr-defined]
        "ok": True,
        "points": [],
    }
    state_fn.malformed_text_history_fn = lambda **kwargs: calls.setdefault("malformed", kwargs) or {  # type: ignore[attr-defined]
        "ok": True,
        "entries": [],
    }
    deps = _make_deps(state_fn=state_fn)

    handle_dashboard_get(object(), path="/api/history/top_nodes", query="category=chats&limit=4", deps=deps)
    handle_dashboard_get(object(), path="/api/history/links", query="window=24h&limit=7", deps=deps)
    handle_dashboard_get(object(), path="/api/history/location_estimates", query="window=7d&limit=8", deps=deps)
    handle_dashboard_get(
        object(),
        path="/api/history/environment",
        query="hours=2&metric=temperature&node_id=!abc&limit=9&gap_scan=0",
        deps=deps,
    )
    handle_dashboard_get(object(), path="/api/history/malformed", query="hours=1&node=!bad&limit=2", deps=deps)

    assert calls["top"] == {"category": "chats", "limit": 4, "exclude_node_ids": ["!self"]}
    assert calls["links"] == {"window": "24h", "limit": 7}
    assert calls["location"] == {"window": "7d", "limit": 8}
    assert calls["environment"] == {
        "window_hours": 2,
        "metric": "temperature",
        "node_id": "!abc",
        "limit": 9,
        "include_gap_scan": False,
    }
    assert calls["malformed"] == {"window_hours": 1, "node_id": "!bad", "limit": 2}
    assert all(row[0] == 200 for row in deps.recorder.json)


def test_dashboard_get_history_routes_return_unavailable_or_error_payloads() -> None:
    def bad_top_nodes(**kwargs: object) -> dict[str, object]:
        raise RuntimeError("top failed")

    def bad_links(**kwargs: object) -> dict[str, object]:
        raise RuntimeError("links failed")

    state_fn = _StateFn({})
    state_fn.top_nodes_fn = bad_top_nodes  # type: ignore[attr-defined]
    state_fn.link_edges_fn = bad_links  # type: ignore[attr-defined]
    state_fn.location_estimates_fn = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("location failed"))  # type: ignore[attr-defined]
    deps = _make_deps(state_fn=state_fn)

    handle_dashboard_get(object(), path="/api/history/top_nodes", query="category=saved_packets", deps=deps)
    handle_dashboard_get(object(), path="/api/history/links", query="", deps=deps)
    handle_dashboard_get(object(), path="/api/history/location_estimates", query="", deps=deps)
    handle_dashboard_get(object(), path="/api/history/environment", query="metric=humidity", deps=deps)
    handle_dashboard_get(object(), path="/api/history/malformed", query="node=!abc", deps=deps)

    assert deps.recorder.json[0][1]["error"] == "top failed"
    assert deps.recorder.json[1][1]["error"] == "links failed"
    assert deps.recorder.json[2][1]["error"] == "location failed"
    assert deps.recorder.json[3][1]["error"] == "environment history unavailable on this node"
    assert deps.recorder.json[4][1]["error"] == "malformed text history unavailable on this node"


def test_dashboard_get_history_search_handles_private_missing_success_and_errors() -> None:
    search_calls: list[tuple[str, dict[str, object]]] = []

    def search_fn(query_text: str, **kwargs: object) -> dict[str, object]:
        search_calls.append((query_text, kwargs))
        return {"ok": True, "query": query_text, "entries": [{"text": "hit"}], "matches": 1}

    state_fn = _StateFn({})
    state_fn.search_history_packets_fn = search_fn  # type: ignore[attr-defined]
    metrics = _Metrics()
    deps = _make_deps(state_fn=state_fn, api_metrics=metrics)

    handle_dashboard_get(object(), path="/api/history/search", query="", deps=deps)
    handle_dashboard_get(
        object(),
        path="/api/history/search",
        query="q=needle&limit=3&context=2&source=chat&scope=direct&scan=50",
        deps=deps,
    )
    handle_dashboard_get(object(), path="/api/history/search", query="q=blocked", deps=_make_deps(private_mode=True, api_metrics=metrics))

    assert deps.recorder.json[0][1]["error"] == "missing query text"
    assert search_calls == [
        (
            "needle",
            {
                "limit": 3,
                "before": 2,
                "after": 2,
                "scope": "direct",
                "scan_limit": 50,
                "source": "chat",
            },
        )
    ]
    assert deps.recorder.json[1][1]["matches"] == 1
    assert metrics.private_blocks == 1


def test_dashboard_get_private_emoji_and_not_found_routes() -> None:
    private_deps = _make_deps(private_mode=True)
    public_deps = _make_deps()

    handle_dashboard_get(object(), path="/api/chat/emoji-catalog", query="", deps=private_deps)
    handle_dashboard_get(object(), path="/api/chat/emoji-catalog", query="", deps=public_deps)
    handle_dashboard_get(object(), path="/missing", query="", deps=public_deps)

    assert private_deps.recorder.text == [(404, "Not Found", {})]
    assert public_deps.recorder.json[0][0] == 200
    assert public_deps.recorder.json[0][1]["ok"] is True
    assert public_deps.recorder.text == [(404, "Not Found", {})]
