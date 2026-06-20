import importlib.util
from pathlib import Path


def _load_report_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "render_coverage_report.py"
    spec = importlib.util.spec_from_file_location("render_coverage_report", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_coverage_report_summarizes_total_and_largest_gaps() -> None:
    report = _load_report_module()
    payload = {
        "totals": {
            "covered_lines": 80,
            "num_statements": 100,
            "percent_covered": 80.0,
            "missing_lines": 20,
        },
        "files": {
            "meshdash/small_gap.py": {
                "summary": {
                    "covered_lines": 9,
                    "num_statements": 10,
                    "percent_covered": 90,
                    "missing_lines": 1,
                }
            },
            "meshdash/big_gap.py": {
                "summary": {
                    "covered_lines": 10,
                    "num_statements": 50,
                    "percent_covered": 20,
                    "missing_lines": 40,
                }
            },
        },
    }

    markdown = report.render_markdown_report(
        payload,
        limit=2,
        run_url="https://example.test/run",
        pr_comment=True,
    )

    assert "<!-- meshyface-coverage-report -->" in markdown
    assert "Coverage minimum: 80.0%" in markdown
    assert "| Coverage | 80.0% |" in markdown
    assert "| Statements | 100 |" in markdown
    assert "| Missing | 20 |" in markdown
    assert markdown.index("meshdash/big_gap.py") < markdown.index("meshdash/small_gap.py")
    assert "[Actions run](https://example.test/run)" in markdown


def test_local_coverage_gate_stays_stricter_than_ci() -> None:
    ci_workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    local_runner = Path("scripts/run_coverage_local.sh").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "--cov-fail-under=80" in ci_workflow
    assert 'COVERAGE_MIN="${MESH_LOCAL_COVERAGE_MIN:-85}"' in local_runner
    assert '--cov-fail-under="${COVERAGE_MIN}"' in local_runner
    assert "stricter 85% minimum" in readme
    assert "fails below 80%" in readme
