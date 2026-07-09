from pathlib import Path


def test_local_ruff_runner_uses_clean_repo_config() -> None:
    script = Path("scripts/run_ruff_local.sh").read_text(encoding="utf-8")
    ci_workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "ruff check . --isolated" in script
    assert 'RUFF_CACHE_DIR="${RUFF_CACHE_DIR:-${ROOT_DIR}/.ruff_cache}"' in script
    assert "scripts/run_ruff_local.sh" in ci_workflow
    assert "scripts/run_ruff_local.sh" in readme
