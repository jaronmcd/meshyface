import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS = REPO_ROOT / "benchmarks" / "gui_responsiveness" / "realtime_thresholds.json"
TRUE_VALUES = {"1", "true", "yes", "on"}


def _load_realtime_module():
    script_path = REPO_ROOT / "scripts" / "benchmark_gui_realtime.py"
    spec = importlib.util.spec_from_file_location("benchmark_gui_realtime", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_synthetic_state_is_generated_deterministic_and_sized() -> None:
    realtime = _load_realtime_module()

    first = realtime.build_synthetic_state(750, now_unix=1_800_000_000)
    second = realtime.build_synthetic_state(750, now_unix=1_800_000_000)

    assert first == second
    assert len(first["nodes"]) == 750
    assert len({node["id"] for node in first["nodes"]}) == 750
    assert all(node["long_name"].startswith("Synthetic Node ") for node in first["nodes"])
    assert set(first["history_caps"]) == {node["id"] for node in first["nodes"]}
    positioned = sum(1 for node in first["nodes"] if "lat" in node)
    assert 300 < positioned < 525
    assert all(1_800_000_000 - node["last_heard_unix"] < 14 * 86400 for node in first["nodes"])


def test_scaling_ratios_use_floors_for_near_idle_small_scenarios() -> None:
    realtime = _load_realtime_module()
    result = {
        "scenarios": {
            "nodes=750,cpu=1": {"busy_percent": 0.4, "long_task_max_ms": 0.0},
            "nodes=3000,cpu=1": {"busy_percent": 6.0, "long_task_max_ms": 160.0},
        }
    }

    realtime.add_scaling(result, [750, 3000], [1.0])

    assert result["scaling"]["cpu=1"] == {
        "from_nodes": 750,
        "to_nodes": 3000,
        "busy_percent_ratio": 6.0,
        "long_task_max_ratio": 3.2,
    }


def test_realtime_thresholds_pass_current_costs_and_fail_quadratic_growth() -> None:
    realtime = _load_realtime_module()
    thresholds = json.loads(THRESHOLDS.read_text(encoding="utf-8"))

    def result_for(small: dict, large: dict) -> dict:
        base = {"polls": 10, "js_exceptions": 0}
        result = {
            "scenarios": {
                "nodes=750,cpu=1": {**base, **small},
                "nodes=3000,cpu=1": {**base, **large},
            }
        }
        realtime.add_scaling(result, [750, 3000], [1.0])
        return result

    # Measured on a development workstation after the 2026-09 performance fixes.
    healthy = result_for({"busy_percent": 3.5, "long_task_max_ms": 66}, {"busy_percent": 6.8, "long_task_max_ms": 178})
    # Measured before them: per-pair livemap links and a thrashing emoji cache.
    quadratic = result_for({"busy_percent": 3.4, "long_task_max_ms": 63}, {"busy_percent": 27.1, "long_task_max_ms": 807})

    assert realtime.evaluate_thresholds(healthy, thresholds) == []
    failures = realtime.evaluate_thresholds(quadratic, thresholds)
    assert any("busy_percent_ratio" in failure for failure in failures)
    assert any("long_task_max_ratio" in failure for failure in failures)


def test_node_emoji_memo_is_sized_for_large_meshes_and_evicts_gradually(dashboard_js: str) -> None:
    # Guard: a 4,096-entry memo cleared on overflow re-segmented every name each poll at
    # 3,000 nodes (short + long names exceed the cap).
    assert "const nodeTagEmojiByTextMaxEntries = 16384;" in dashboard_js
    assert "nodeTagEmojiByText.clear()" not in dashboard_js
    assert "if (evicted >= nodeTagEmojiByTextMaxEntries / 4) break;" in dashboard_js


def _benchmark_enabled(config: pytest.Config) -> bool:
    env_value = os.environ.get("MESH_GUI_BENCH_RUN", "").strip().lower()
    return bool(config.getoption("--run-gui-benchmark")) or env_value in TRUE_VALUES


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.mark.gui_benchmark
def test_realtime_gui_benchmark_stays_within_scaling_budgets(request: pytest.FixtureRequest, tmp_path: Path) -> None:
    if not _benchmark_enabled(request.config):
        pytest.skip("set MESH_GUI_BENCH_RUN=1 or pass --run-gui-benchmark to run the browser benchmark")

    port = _free_local_port()
    url = f"http://127.0.0.1:{port}/"
    server_log = (tmp_path / "dashboard.log").open("w", encoding="utf-8")
    server = subprocess.Popen(
        [
            sys.executable,
            str(REPO_ROOT / "mesh_dashboard.py"),
            "--mesh-host",
            "127.0.0.1",
            "--mesh-tcp-port",
            "1",
            "--http-host",
            "127.0.0.1",
            "--http-port",
            str(port),
            "--history-db",
            str(tmp_path / "history.sqlite3"),
        ],
        cwd=REPO_ROOT,
        stdout=server_log,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"{url}api/version", timeout=2)
                break
            except Exception:
                time.sleep(0.5)
        output = tmp_path / "realtime.json"
        proc = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "benchmark_gui_realtime.py"),
                "--url",
                url,
                "--thresholds",
                str(THRESHOLDS),
                "--output-json",
                str(output),
            ],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=int(os.environ.get("MESH_GUI_BENCH_PYTEST_TIMEOUT", "400")),
            check=False,
        )
        assert proc.returncode == 0, proc.stdout
        assert json.loads(output.read_text(encoding="utf-8"))["ok"] is True
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        server_log.close()
