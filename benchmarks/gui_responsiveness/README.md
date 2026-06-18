# GUI Responsiveness Benchmarks

The local test suite includes an opt-in `gui_benchmark` pytest test. It starts a local dashboard, runs the headless browser benchmark, saves ignored local JSON output, and fails if `local_thresholds.json` budgets are exceeded.

Normal `pytest` skips the browser benchmark so quick unit-test runs do not launch Chromium. Run the local performance gate with:

```bash
python -m pytest -m gui_benchmark --run-gui-benchmark
```

The local run is a smoke budget because it does not include the large live mesh database. To run the stricter real-data guard against a deployed dashboard, replace `<dashboard-host>` with that host name or IP:

```bash
MESH_GUI_BENCH_URL=http://<dashboard-host>:8877/ \
MESH_GUI_BENCH_THRESHOLDS=benchmarks/gui_responsiveness/live_target_thresholds.json \
MESH_GUI_BENCH_OUTPUT=benchmarks/gui_responsiveness/results/local-live-target.json \
python -m pytest -m gui_benchmark --run-gui-benchmark
```

For one-off comparisons, use `scripts/benchmark_gui_responsiveness.py` directly and write outputs under `benchmarks/gui_responsiveness/results/`. That directory is ignored because benchmark output can include local hosts, URLs, and runtime-specific data.

To render a saved JSON result as a compact Markdown report:

```bash
python scripts/render_gui_benchmark_report.py \
  benchmarks/gui_responsiveness/results/local-gui-responsiveness.json \
  --output benchmarks/gui_responsiveness/results/local-gui-responsiveness.md
```

GitHub Actions runs the same offline benchmark as an advisory report job. It
does not require Meshtastic hardware and normal local `pytest` runs continue to
skip the browser benchmark unless explicitly enabled.
