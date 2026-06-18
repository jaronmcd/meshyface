import importlib.util
from collections.abc import Callable, Sequence
from pathlib import Path


def _load_benchmark_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_gui_responsiveness.py"
    spec = importlib.util.spec_from_file_location("benchmark_gui_responsiveness", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_report_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "render_gui_benchmark_report.py"
    spec = importlib.util.spec_from_file_location("render_gui_benchmark_report", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dashboard_js_includes_gui_responsiveness_benchmark(
    dashboard_js: str,
    assert_tokens_present: Callable[[str, Sequence[str]], None],
) -> None:
    assert_tokens_present(
        dashboard_js,
        (
            "window.__meshDashboardBenchmark",
            'meshGuiBenchmarkBoolQuery("mesh_gui_bench")',
            "meshGuiBenchmarkForcePoll",
            "meshGuiBenchmarkFetchJson",
            "meshGuiBenchmarkSummarizeSamples",
            "meshGuiBenchmarkTimingMetricNames",
            "meshGuiBenchmarkCountMetricNames",
            "meshGuiBenchmarkDomSnapshot",
            "meshGuiBenchmarkSampleDomFields",
            "domActiveSurfaceElements",
            "domChatFeedItems",
            "meshGuiBenchmarkSampleTimingBreakdown",
            "meshGuiBenchmarkPollView",
            "meshGuiBenchmarkCachedPoll",
            "includeCachedPoll",
            "includeInteractions",
            "meshGuiBenchmarkTypeChatInput",
            "meshGuiBenchmarkScrollChatFeed",
            "meshGuiBenchmarkSearchChatRoster",
            "meshGuiBenchmarkClickChatReply",
            "meshGuiBenchmarkOpenReactionPopover",
            "openReactionPopoverForSummary(button)",
            '"interact:chat-type"',
            '"interact:roster-search"',
            "`poll-cached:${suffix}`",
            "meshGuiBenchmarkChatRenderRunCount",
            "chatRenderRunsAdded",
            "meshGuiBenchmarkIsViewActive",
            "alreadyActive",
            "skipBenchmarkFrameWait",
            "callbackMs",
            "postCallbackFrameWaitMs",
            "actionSyncMs",
            "pollWorkMs",
            "pollOverheadMs",
            "meshGuiBenchmarkPollPerfRunCount",
            "pollPerfRunsAdded",
            "pollPerf: pollStats ?",
            "environmentMetricsRender: envMetricsStats ?",
            "meshGuiBenchmarkEnvironmentMetricsRenderRunCount",
            "environmentMetricsRenderRunsAdded",
            "meshGuiBenchmarkWaitForEnvironmentMetricsRender",
            "networkGraphRender: graphStats ?",
            "networkGraphRenderRunsAdded",
            'const stateProfiles = ["default", "chat", "network", "network-graph", "network-map", "status", "console"];',
            "mesh-gui-benchmark-result",
        ),
    )


def test_gui_responsiveness_thresholds_pass_for_values_inside_budget() -> None:
    benchmark = _load_benchmark_module()
    result = {
        "ok": True,
        "summary": {
            "longTaskCount": 0,
            "domTotalElements": {"p95": 1200},
            "byLabel": {"switch:chat": {"totalMs": {"p95": 14.5}}},
        },
    }
    thresholds = {
        "equals": {"/ok": True},
        "max": {
            "/summary/longTaskCount": 0,
            "/summary/domTotalElements/p95": 2000,
            "/summary/byLabel/switch:chat/totalMs/p95": 20,
        },
        "min": {"/summary/domTotalElements/p95": 1000},
    }

    assert benchmark.evaluate_thresholds(result, thresholds) == []


def test_gui_responsiveness_thresholds_report_budget_failures() -> None:
    benchmark = _load_benchmark_module()
    result = {
        "ok": True,
        "summary": {
            "longTaskCount": 1,
            "domTotalElements": {"p95": 2400},
        },
    }
    thresholds = {
        "equals": {"/ok": False},
        "max": {
            "/summary/longTaskCount": 0,
            "/summary/domTotalElements/p95": 2000,
            "/summary/missingMetric/p95": 1,
        },
        "min": {"/summary/domTotalElements/p95": 2500},
    }

    failures = benchmark.evaluate_thresholds(result, thresholds)

    assert "equals /ok: expected false, got true" in failures
    assert "max /summary/longTaskCount: expected <= 0, got 1" in failures
    assert "max /summary/domTotalElements/p95: expected <= 2000, got 2400" in failures
    assert "max /summary/missingMetric/p95: expected 1, got missing" in failures
    assert "min /summary/domTotalElements/p95: expected >= 2500, got 2400" in failures


def test_gui_responsiveness_redacts_url_credentials_from_saved_results() -> None:
    benchmark = _load_benchmark_module()

    assert (
        benchmark.redact_url_credentials("http://user:pass@192.0.2.10:8877/path?x=1")
        == "http://[redacted]@192.0.2.10:8877/path?x=1"
    )
    assert benchmark.redact_url_credentials("http://192.0.2.10:8877/") == "http://192.0.2.10:8877/"


def test_gui_benchmark_markdown_report_summarizes_key_metrics() -> None:
    report = _load_report_module()
    markdown = report.render_markdown_report(
        {
            "ok": True,
            "durationMs": 1234.56,
            "_runner": {
                "browser": "/usr/bin/chromium",
                "window_size": "1366,900",
            },
            "state": {
                "nodes": 2,
                "rawNodes": 3,
                "recentChat": 4,
                "dom": {
                    "totalElements": 1200,
                    "activeSurfaceElements": 340,
                    "bodyHtmlBytes": 2048,
                    "mapMarkers": 2,
                    "networkGraphNodes": 3,
                    "networkGraphEdges": 4,
                },
            },
            "summary": {
                "samples": 9,
                "longTaskCount": 1,
                "errors": 0,
                "totalMs": {"p50": 12.3, "p95": 45.6, "max": 78.9},
                "callbackMs": {"p50": 1, "p95": 2, "max": 3},
                "pollWorkMs": {"p50": 4, "p95": 5, "max": 6},
                "frameP95Ms": {"p50": 7, "p95": 8, "max": 9},
                "byLabel": {
                    "switch:chat": {
                        "totalMs": {"count": 1, "p95": 11},
                        "callbackMs": {"p95": 1},
                        "pollWorkMs": {"p95": 2},
                        "frameMaxMs": {"max": 3},
                        "domActiveSurfaceElements": {"p95": 340},
                        "longTaskCount": 0,
                    }
                },
            },
            "api": [
                {
                    "label": "state:default",
                    "ok": True,
                    "status": 200,
                    "totalMs": 10.5,
                    "bytes": 2048,
                }
            ],
        }
    )

    assert "# Meshyface GUI Benchmark Report" in markdown
    assert "| Result | pass |" in markdown
    assert "| Duration | 1234.6 ms |" in markdown
    assert "| Browser | /usr/bin/chromium |" in markdown
    assert "| Total sample | 12.3 ms | 45.6 ms | 78.9 ms |" in markdown
    assert "| Body HTML | 2.0 KB |" in markdown
    assert "| switch:chat | 11.0 ms | 1.0 ms | 2.0 ms | 3.0 ms | 340 | 0 |" in markdown
    assert "| state:default | ok | HTTP 200 | 10.5 ms | 2.0 KB |" in markdown
