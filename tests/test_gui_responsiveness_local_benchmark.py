import json
import os
import socket
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
TRUE_VALUES = {"1", "true", "yes", "on"}


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _benchmark_enabled(config: pytest.Config) -> bool:
    env_value = os.environ.get("MESH_GUI_BENCH_RUN", "").strip().lower()
    return bool(config.getoption("--run-gui-benchmark")) or env_value in TRUE_VALUES


def test_local_gui_benchmark_script_refuses_accidental_existing_server() -> None:
    script = (REPO_ROOT / "scripts" / "run_gui_responsiveness_local.sh").read_text(encoding="utf-8")

    assert 'curl -fsS "${URL}api/version"' in script
    assert "already responds" in script
    assert "MESH_GUI_BENCH_URL" in script
    assert "MESH_GUI_BENCH_PORT" in script
    assert "chat,scripts,network:map" in script


@pytest.mark.gui_benchmark
def test_local_gui_responsiveness_stays_within_thresholds(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> None:
    if not _benchmark_enabled(request.config):
        pytest.skip("set MESH_GUI_BENCH_RUN=1 or pass --run-gui-benchmark to run the browser benchmark")

    env = os.environ.copy()
    env.setdefault("MESH_GUI_BENCH_OUTPUT", str(tmp_path / "pytest-gui-responsiveness.json"))
    if "MESH_GUI_BENCH_URL" not in env:
        env.setdefault("MESH_GUI_BENCH_PORT", str(_free_local_port()))

    proc = subprocess.run(
        [str(REPO_ROOT / "scripts" / "run_gui_responsiveness_local.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=int(env.get("MESH_GUI_BENCH_PYTEST_TIMEOUT", "300")),
        check=False,
    )

    assert proc.returncode == 0, proc.stdout
    output_path = Path(env["MESH_GUI_BENCH_OUTPUT"])
    assert output_path.exists()
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert "ReferenceError" not in json.dumps(result)
    scripts_switches = [
        sample
        for sample in result["samples"]
        if sample.get("label") == "switch:scripts"
    ]
    assert scripts_switches
    assert all(not sample.get("error") for sample in scripts_switches)
    scripts_polls = [
        sample
        for sample in result["samples"]
        if sample.get("label") == "poll:scripts"
    ]
    assert scripts_polls
    assert all(not sample.get("error") for sample in scripts_polls)
    for sample in scripts_polls:
        contract = sample["detail"]["scripts"]
        assert contract["loading"] is False
        assert contract["scriptItems"] == 0
        assert contract["emptyItems"] == 1
        assert contract["emptyText"]
        assert contract["runtimeStatus"] != "Waiting for runtime status"
        assert contract["nodeRosterItems"] == contract["stateNodeCount"]
