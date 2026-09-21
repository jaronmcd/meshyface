import importlib.util
from pathlib import Path

import pytest


def _module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_pr_operations.py"
    spec = importlib.util.spec_from_file_location("benchmark_pr_operations", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _runs(module):
    return {side: [{**dict.fromkeys(module.METRICS, value), "map_markers": 150,
                    "roster_targets": 249, "quality_digest": "same"} for value in values]
            for side, values in (("base", [10, 20, 30]), ("current", [5, 10, 15]))}


def test_comparison_reports_spread_and_scoped_workload():
    module = _module()
    report = module.render_report({"base_commit": "a" * 40, "current_commit": "b" * 40,
                                   "scenarios": {"750": _runs(module)}})
    assert "20.0 [10.0–30.0] | 10.0 [5.0–15.0] | -50.0%" in report
    assert "Overlapping timing ranges are inconclusive" in report
    assert "excluding paint" in report


@pytest.mark.parametrize("fault", ["missing_run", "wrong_result", "empty_map", "invalid_time"])
def test_comparison_rejects_invalid_or_non_equivalent_runs(fault):
    module = _module()
    runs = _runs(module)
    if fault == "missing_run":
        runs["base"].pop()
    elif fault == "wrong_result":
        runs["current"][0]["quality_digest"] = "different"
    elif fault == "empty_map":
        runs["current"][0]["map_markers"] = 0
    else:
        runs["current"][0]["roster_ms"] = float("nan")
    with pytest.raises(ValueError):
        module.validate_runs(runs)
