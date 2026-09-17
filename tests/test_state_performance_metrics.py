import io
from types import SimpleNamespace

from meshdash.api_metrics import (
    STATE_BODY_BUDGET_BYTES,
    STATE_BUDGET_MIN_FULL_SAMPLES,
    STATE_BUDGET_WARNING_INTERVAL_SECONDS,
    STATE_RESPONSE_BUDGET_MS,
    DashboardApiMetrics,
    build_prometheus_metrics_text,
)
from meshdash.helpers import to_int
from meshdash.http_responses import write_json_response
from meshdash.http_routes_get import handle_dashboard_get


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_state_response_stats_report_percentiles_ratio_and_budget() -> None:
    metrics = DashboardApiMetrics(log_fn=lambda _message: None)
    for elapsed in (10.0, 20.0, 30.0, 40.0):
        metrics.record_state_response(profile="lite-chat", status_code=200, elapsed_ms=elapsed, body_bytes=5000)
    for _ in range(4):
        metrics.record_state_response(profile="lite-chat", status_code=304, elapsed_ms=1.0, body_bytes=None)

    stats = metrics.performance_snapshot()["state_profiles"]["lite-chat"]

    assert stats["samples"] == 8
    assert stats["full_samples"] == 4
    assert stats["not_modified_ratio"] == 0.5
    assert stats["full_ms_p50"] in (20.0, 30.0)
    assert stats["full_ms_max"] == 40.0
    assert stats["body_bytes_last"] == 5000
    assert stats["within_budget"] is True
    assert stats["responses_total"] == {"200": 4, "304": 4}


def test_slow_or_oversized_state_responses_log_rate_limited_warnings() -> None:
    clock = _Clock()
    messages: list[str] = []
    metrics = DashboardApiMetrics(monotonic_fn=clock, log_fn=messages.append)
    slow_ms = STATE_RESPONSE_BUDGET_MS + 300

    for _ in range(STATE_BUDGET_MIN_FULL_SAMPLES - 1):
        metrics.record_state_response(profile="lite", status_code=200, elapsed_ms=slow_ms, body_bytes=1000)
    assert messages == []  # too few samples to judge a p95

    metrics.record_state_response(profile="lite", status_code=200, elapsed_ms=slow_ms, body_bytes=1000)
    metrics.record_state_response(profile="lite", status_code=200, elapsed_ms=slow_ms, body_bytes=1000)
    assert len(messages) == 1
    assert "profile=lite p95 response" in messages[0]

    metrics.record_state_response(profile="lite", status_code=200, elapsed_ms=10, body_bytes=STATE_BODY_BUDGET_BYTES + 1)
    assert len(messages) == 2
    assert "exceeds the 1500000 byte budget" in messages[1]

    clock.now += STATE_BUDGET_WARNING_INTERVAL_SECONDS + 1
    metrics.record_state_response(profile="lite", status_code=200, elapsed_ms=slow_ms, body_bytes=1000)
    assert len(messages) == 3
    assert metrics.performance_snapshot()["state_profiles"]["lite"]["within_budget"] is False


def test_write_json_response_returns_uncompressed_json_size() -> None:
    handler = SimpleNamespace(
        headers={"Accept-Encoding": "gzip"},
        wfile=io.BytesIO(),
        send_response=lambda _code: None,
        send_header=lambda _key, _value: None,
        end_headers=lambda: None,
    )

    byte_count = write_json_response(handler, status_code=200, payload_obj={"message": "x" * 5000})

    assert byte_count == len('{"message":"' + "x" * 5000 + '"}')
    assert len(handler.wfile.getvalue()) < byte_count


def _route_deps(state_fn, metrics):
    recorded = SimpleNamespace(json=[], text=[])
    deps = SimpleNamespace(
        state_fn=state_fn,
        api_metrics=metrics,
        private_mode=False,
        to_int_fn=to_int,
        write_json_response_fn=lambda handler, *, status_code, payload_obj, no_store=False, **kwargs: (
            recorded.json.append((status_code, payload_obj)) or 1234
        ),
        write_text_response_fn=lambda handler, *, status_code, text, **kwargs: recorded.text.append((status_code, text)),
    )
    return deps, recorded


class _Headers(dict):
    def get(self, key, default=None):
        return super().get(key, default)


def test_state_route_records_full_and_not_modified_responses_by_profile() -> None:
    payload = {"summary": {"node_count": 2, "known_node_count": 5, "node_window_omitted_count": 3}, "traffic": {}}

    class _StateFn:
        def __call__(self):
            return payload

        def lite_chat(self):
            return payload

    state_fn = _StateFn()
    state_fn.lite_chat.__func__.etag = lambda: 'W/"lite-chat-1"'
    metrics = DashboardApiMetrics(log_fn=lambda _message: None)
    deps, recorded = _route_deps(state_fn, metrics)

    handle_dashboard_get(SimpleNamespace(headers=_Headers()), path="/api/state", query="lite=1&profile=chat", deps=deps)
    not_modified_handler = SimpleNamespace(
        headers=_Headers({"If-None-Match": 'W/"lite-chat-1"'}),
        send_response=lambda _code: None,
        send_header=lambda _key, _value: None,
        end_headers=lambda: None,
    )
    handle_dashboard_get(not_modified_handler, path="/api/state", query="lite=1&profile=chat", deps=deps)

    stats = metrics.performance_snapshot()["state_profiles"]["lite-chat"]
    assert stats["responses_total"] == {"200": 1, "304": 1}
    assert stats["body_bytes_last"] == 1234
    assert len(recorded.json) == 1

    handle_dashboard_get(object(), path="/metrics", query="", deps=deps)
    handle_dashboard_get(object(), path="/api/health", query="", deps=deps)
    metrics_text = recorded.text[-1][1]
    assert 'meshdash_state_responses_total{profile="lite-chat",status="304"} 1' in metrics_text
    assert 'meshdash_state_body_bytes{profile="lite-chat"} 1234' in metrics_text
    assert "meshdash_known_node_count 5" in metrics_text
    assert "meshdash_node_window_omitted_count 3" in metrics_text
    health = recorded.json[-1][1]
    assert health["performance"]["state_profiles"]["lite-chat"]["full_samples"] == 1


def test_prometheus_text_without_performance_is_unchanged_in_shape() -> None:
    text = build_prometheus_metrics_text(state_payload={"summary": {"node_count": 1}}, counters={})

    assert "meshdash_state_response_ms" not in text
    assert "meshdash_known_node_count" not in text
