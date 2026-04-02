from meshdash import http_routes_get as routes_get
from meshdash.api_inputs import NodeHistoryQuery, OnlineActivityQuery
from meshdash.http_route_contracts import DashboardGetRouteDependencies


def _build_get_deps(*, state_fn, json_calls, text_calls, html_calls, private_mode=False, api_metrics=None):
    return DashboardGetRouteDependencies(
        html_text="<html></html>",
        state_fn=state_fn,
        node_history_fn=lambda node_id, hours_override, points_override: {
            "node_id": node_id,
            "hours": hours_override,
            "points": points_override,
        },
        online_activity_fn=lambda hours_override: {"window_hours": hours_override},
        summary_metrics_fn=lambda hours_override: {"summary_hours": hours_override},
        default_node_history_hours=72,
        to_int_fn=lambda value: int(value) if value not in (None, "") else None,
        parse_node_history_request_fn=lambda _query, **_kwargs: NodeHistoryQuery(
            node_id="!abcd1234",
            hours_override=24,
            points_override=99,
        ),
        parse_online_activity_request_fn=lambda _query, **_kwargs: OnlineActivityQuery(hours_override=12),
        empty_node_history_fn=lambda node_id: {"node_id": node_id, "empty": True},
        empty_online_activity_fn=lambda hours: {"hours": hours, "empty": True},
        empty_summary_metrics_fn=lambda hours: {"hours": hours, "points": []},
        write_html_response_fn=lambda _handler, **kwargs: html_calls.append(kwargs),
        write_json_response_fn=lambda _handler, **kwargs: json_calls.append(kwargs),
        write_text_response_fn=lambda _handler, **kwargs: text_calls.append(kwargs),
        get_theme_settings_fn=lambda: {"ok": True, "selected_preset": "default"},
        get_custom_telemetry_settings_fn=lambda: {"ok": True, "rules": [], "updated_unix": 0},
        private_mode=private_mode,
        api_metrics=api_metrics,
    )


def test_handle_dashboard_get_main_routes(monkeypatch):
    json_calls = []
    text_calls = []
    html_calls = []
    state_seen = {}

    def _state_get_helper(handler, **kwargs):
        del handler
        state_seen.update(kwargs)

    monkeypatch.setattr(routes_get, "_handle_state_get_helper", _state_get_helper)
    monkeypatch.setattr(routes_get, "_load_offline_atlas_payload_helper", lambda: {"layers": [{"id": "osm"}]})
    monkeypatch.setattr(
        routes_get,
        "_load_chat_emoji_catalog_payload_helper",
        lambda: {
            "ok": True,
            "version": "17.0",
            "groups": [{"id": "smileys-emotion", "label": "Smileys & Emotion", "emojis": ["😀"]}],
        },
    )

    class _State:
        def __call__(self):
            return {"ok": True}

        def environment_metrics_history_fn(self, **kwargs):
            return {
                "ok": True,
                "window_hours": kwargs.get("window_hours"),
                "query": {
                    "metric": kwargs.get("metric"),
                    "node_id": kwargs.get("node_id"),
                    "limit": kwargs.get("limit"),
                },
                "points": [],
                "metrics": [],
                "nodes": [],
            }

        def search_history_packets_fn(self, query_text, **kwargs):
            return {
                "ok": True,
                "query": query_text,
                "kwargs": kwargs,
                "entries": [],
                "matches": 0,
                "returned_matches": 0,
            }

    deps = _build_get_deps(state_fn=_State(), json_calls=json_calls, text_calls=text_calls, html_calls=html_calls)
    handler = object()

    routes_get.handle_dashboard_get(handler, path="/", query="", deps=deps)
    routes_get.handle_dashboard_get(handler, path="/api/state", query="lite=1", deps=deps)
    routes_get.handle_dashboard_get(handler, path="/api/settings/theme", query="", deps=deps)
    routes_get.handle_dashboard_get(handler, path="/api/settings/custom_telemetry", query="", deps=deps)
    routes_get.handle_dashboard_get(handler, path="/api/history/node", query="node_id=!x", deps=deps)
    routes_get.handle_dashboard_get(handler, path="/api/history/online", query="hours=12", deps=deps)
    routes_get.handle_dashboard_get(handler, path="/api/history/summary", query="hours=12", deps=deps)
    routes_get.handle_dashboard_get(
        handler,
        path="/api/history/environment",
        query="hours=36&metric=temperature&node_id=!abcd1234&limit=500",
        deps=deps,
    )
    routes_get.handle_dashboard_get(
        handler,
        path="/api/history/search",
        query="q=!3369d0b8&before=1&after=2&scope=both&source=chat&scan=300",
        deps=deps,
    )
    routes_get.handle_dashboard_get(handler, path="/api/offline/atlas", query="", deps=deps)
    routes_get.handle_dashboard_get(handler, path="/api/chat/emoji-catalog", query="", deps=deps)
    routes_get.handle_dashboard_get(handler, path="/missing", query="", deps=deps)

    assert html_calls[0]["html_text"] == "<html></html>"
    assert html_calls[0]["no_store"] is True
    assert state_seen["query"] == "lite=1"
    assert state_seen["state_fn"] is deps.state_fn
    assert state_seen["write_json_response_fn"] is deps.write_json_response_fn
    assert json_calls[0]["payload_obj"]["selected_preset"] == "default"
    assert json_calls[1]["payload_obj"]["ok"] is True
    assert json_calls[1]["payload_obj"]["rules"] == []
    assert json_calls[2]["payload_obj"]["node_id"] == "!abcd1234"
    assert json_calls[3]["payload_obj"]["window_hours"] == 12
    assert json_calls[4]["payload_obj"]["summary_hours"] == 12
    assert json_calls[5]["payload_obj"]["query"]["metric"] == "temperature"
    assert json_calls[5]["payload_obj"]["query"]["node_id"] == "!abcd1234"
    assert json_calls[5]["payload_obj"]["query"]["limit"] == 500
    assert json_calls[6]["payload_obj"]["query"] == "!3369d0b8"
    assert json_calls[6]["payload_obj"]["kwargs"]["before"] == 1
    assert json_calls[6]["payload_obj"]["kwargs"]["after"] == 2
    assert json_calls[6]["payload_obj"]["kwargs"]["scope"] == "both"
    assert json_calls[6]["payload_obj"]["kwargs"]["source"] == "chat"
    assert json_calls[6]["payload_obj"]["kwargs"]["scan_limit"] == 300
    assert json_calls[7]["payload_obj"]["layers"][0]["id"] == "osm"
    assert json_calls[8]["payload_obj"]["version"] == "17.0"
    assert json_calls[8]["payload_obj"]["groups"][0]["id"] == "smileys-emotion"
    assert text_calls[0]["status_code"] == 404


def test_handle_dashboard_get_raw_endpoints_prefer_raw_methods_and_fallback_to_snapshot():
    json_calls = []
    text_calls = []
    html_calls = []

    class _State:
        def __init__(self):
            self._snapshot = {
                "my_info": {"id": "!mine"},
                "metadata": {"region": "US"},
                "local_state": {"enabled": True},
                "nodes_full": [{"id": "!x"}],
            }

        def __call__(self):
            return dict(self._snapshot)

        def raw_my_info(self):
            return {"id": "!raw"}

        def raw_metadata(self):
            return {"region": "RAW"}

        def raw_local_state(self):
            return {"enabled": "raw"}

        def raw_nodes_full(self):
            return [{"id": "!raw-node"}]

    state_fn = _State()
    deps = _build_get_deps(state_fn=state_fn, json_calls=json_calls, text_calls=text_calls, html_calls=html_calls)

    handler = object()
    routes_get.handle_dashboard_get(handler, path="/api/raw/my_info", query="", deps=deps)
    routes_get.handle_dashboard_get(handler, path="/api/raw/metadata", query="", deps=deps)
    routes_get.handle_dashboard_get(handler, path="/api/raw/local_state", query="", deps=deps)
    routes_get.handle_dashboard_get(handler, path="/api/raw/nodes_full", query="", deps=deps)

    assert json_calls[0]["payload_obj"]["id"] == "!raw"
    assert json_calls[1]["payload_obj"]["region"] == "RAW"
    assert json_calls[2]["payload_obj"]["enabled"] == "raw"
    assert json_calls[3]["payload_obj"][0]["id"] == "!raw-node"
    assert all(call["no_store"] is True for call in json_calls)

    # Replace raw helpers with non-callables to exercise snapshot fallback branches.
    state_fn.raw_my_info = None
    state_fn.raw_metadata = None
    state_fn.raw_local_state = None
    state_fn.raw_nodes_full = None
    routes_get.handle_dashboard_get(handler, path="/api/raw/my_info", query="", deps=deps)
    routes_get.handle_dashboard_get(handler, path="/api/raw/metadata", query="", deps=deps)
    routes_get.handle_dashboard_get(handler, path="/api/raw/local_state", query="", deps=deps)
    routes_get.handle_dashboard_get(handler, path="/api/raw/nodes_full", query="", deps=deps)

    assert json_calls[4]["payload_obj"]["id"] == "!mine"
    assert json_calls[5]["payload_obj"]["region"] == "US"
    assert json_calls[6]["payload_obj"]["enabled"] is True
    assert json_calls[7]["payload_obj"][0]["id"] == "!x"


def test_handle_dashboard_get_history_search_returns_error_payload_when_unavailable():
    json_calls = []
    deps = _build_get_deps(
        state_fn=lambda: {"ok": True},
        json_calls=json_calls,
        text_calls=[],
        html_calls=[],
    )

    handler = object()
    routes_get.handle_dashboard_get(
        handler,
        path="/api/history/search",
        query="q=needle",
        deps=deps,
    )
    routes_get.handle_dashboard_get(
        handler,
        path="/api/history/search",
        query="q=",
        deps=deps,
    )

    assert json_calls[0]["status_code"] == 200
    assert json_calls[0]["payload_obj"]["ok"] is False
    assert "unavailable" in json_calls[0]["payload_obj"]["error"]
    assert json_calls[1]["payload_obj"]["ok"] is False
    assert "missing query text" in json_calls[1]["payload_obj"]["error"]


def test_handle_dashboard_get_environment_history_returns_error_payload_when_unavailable():
    json_calls = []
    deps = _build_get_deps(
        state_fn=lambda: {"ok": True},
        json_calls=json_calls,
        text_calls=[],
        html_calls=[],
    )
    handler = object()
    routes_get.handle_dashboard_get(
        handler,
        path="/api/history/environment",
        query="hours=24&metric=temperature&node_id=!abcd1234",
        deps=deps,
    )
    assert json_calls[0]["status_code"] == 200
    assert json_calls[0]["payload_obj"]["ok"] is False
    assert "unavailable" in json_calls[0]["payload_obj"]["error"]


def test_handle_dashboard_get_custom_telemetry_settings_returns_error_when_unavailable():
    json_calls = []
    deps = _build_get_deps(
        state_fn=lambda: {"ok": True},
        json_calls=json_calls,
        text_calls=[],
        html_calls=[],
    )
    deps = DashboardGetRouteDependencies(
        html_text=deps.html_text,
        state_fn=deps.state_fn,
        node_history_fn=deps.node_history_fn,
        online_activity_fn=deps.online_activity_fn,
        summary_metrics_fn=deps.summary_metrics_fn,
        default_node_history_hours=deps.default_node_history_hours,
        to_int_fn=deps.to_int_fn,
        parse_node_history_request_fn=deps.parse_node_history_request_fn,
        parse_online_activity_request_fn=deps.parse_online_activity_request_fn,
        empty_node_history_fn=deps.empty_node_history_fn,
        empty_online_activity_fn=deps.empty_online_activity_fn,
        empty_summary_metrics_fn=deps.empty_summary_metrics_fn,
        write_html_response_fn=deps.write_html_response_fn,
        write_json_response_fn=deps.write_json_response_fn,
        write_text_response_fn=deps.write_text_response_fn,
        get_theme_settings_fn=deps.get_theme_settings_fn,
        get_custom_telemetry_settings_fn=None,
        private_mode=deps.private_mode,
        api_metrics=deps.api_metrics,
    )
    handler = object()
    routes_get.handle_dashboard_get(
        handler,
        path="/api/settings/custom_telemetry",
        query="",
        deps=deps,
    )
    assert json_calls[0]["status_code"] == 503
    assert "custom telemetry settings are not enabled" in json_calls[0]["payload_obj"]["error"].lower()


def test_handle_dashboard_get_version_health_and_metrics_endpoints():
    json_calls = []
    text_calls = []
    deps = _build_get_deps(
        state_fn=lambda: {
            "generated_at": "2026-03-24T12:00:00Z",
            "summary": {
                "uptime_seconds": 120,
                "node_count": 3,
                "live_packet_count": 11,
                "revision": {
                    "version": "0.1.0",
                    "commit": "abc123",
                    "label": "Rev: v0.1.0 (abc123)",
                    "title": "Dashboard revision: version 0.1.0, commit abc123",
                },
                "radio_connection": {"state": "connected"},
            },
            "tracker_error": None,
            "summary_error": None,
            "traffic": {
                "recent_packets": [{"rx_time_unix": 100}, {"rx_time_unix": 101}],
                "recent_chat": [{"text": "hello"}],
            },
        },
        json_calls=json_calls,
        text_calls=text_calls,
        html_calls=[],
    )
    handler = object()

    routes_get.handle_dashboard_get(handler, path="/api/version", query="", deps=deps)
    routes_get.handle_dashboard_get(handler, path="/api/health", query="", deps=deps)
    routes_get.handle_dashboard_get(handler, path="/metrics", query="", deps=deps)

    assert json_calls[0]["status_code"] == 200
    assert json_calls[0]["payload_obj"]["version"] == "0.1.0"
    assert json_calls[0]["payload_obj"]["commit"] == "abc123"

    assert json_calls[1]["status_code"] == 200
    assert json_calls[1]["payload_obj"]["status"] == "ok"
    assert json_calls[1]["payload_obj"]["node_count"] == 3
    assert json_calls[1]["payload_obj"]["radio_link_up"] == 1

    assert text_calls[0]["status_code"] == 200
    assert "meshdash_packet_rate_per_second" in text_calls[0]["text"]
    assert "meshdash_node_count" in text_calls[0]["text"]
    assert "meshdash_state_poll_errors_total" in text_calls[0]["text"]
    assert "meshdash_radio_link_up" in text_calls[0]["text"]


def test_handle_dashboard_get_private_mode_blocks_chat_message_routes():
    json_calls = []
    text_calls = []
    deps = _build_get_deps(
        state_fn=lambda: {"ok": True},
        json_calls=json_calls,
        text_calls=text_calls,
        html_calls=[],
        private_mode=True,
    )
    handler = object()

    routes_get.handle_dashboard_get(
        handler,
        path="/api/history/search",
        query="q=needle",
        deps=deps,
    )
    routes_get.handle_dashboard_get(
        handler,
        path="/api/chat/emoji-catalog",
        query="",
        deps=deps,
    )

    assert json_calls[0]["status_code"] == 403
    assert "private mode" in json_calls[0]["payload_obj"]["error"].lower()
    assert text_calls[0]["status_code"] == 404


def test_handle_dashboard_get_state_poll_error_writes_500_and_records_metric(monkeypatch):
    json_calls = []

    class _Metrics:
        def __init__(self):
            self.state_requests = 0
            self.state_errors = 0

        def record_state_poll_request(self):
            self.state_requests += 1

        def record_state_poll_error(self):
            self.state_errors += 1

        def record_write_auth_denied(self):
            return None

        def record_private_mode_block(self):
            return None

        def snapshot(self):
            return {}

    metrics = _Metrics()
    deps = _build_get_deps(
        state_fn=lambda: {"ok": True},
        json_calls=json_calls,
        text_calls=[],
        html_calls=[],
        api_metrics=metrics,
    )

    monkeypatch.setattr(
        routes_get,
        "_handle_state_get_helper",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("state blew up")),
    )

    routes_get.handle_dashboard_get(object(), path="/api/state", query="", deps=deps)

    assert metrics.state_requests == 1
    assert metrics.state_errors == 1
    assert json_calls[0]["status_code"] == 500
    assert "state poll failed" in json_calls[0]["payload_obj"]["error"]
