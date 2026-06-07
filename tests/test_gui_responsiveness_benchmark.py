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
