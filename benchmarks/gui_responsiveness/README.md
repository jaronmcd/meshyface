# GUI Responsiveness Benchmarks

CI runs `scripts/run_gui_responsiveness_ci.sh`, which starts a local dashboard, runs the headless browser benchmark, saves JSON output, and fails if `ci_thresholds.json` budgets are exceeded.

The local CI run is a smoke budget because it does not include the large live mesh database. To run the stricter real-data guard against the deployed dashboard:

```bash
MESH_GUI_BENCH_URL=http://192.168.1.87:8877/ \
MESH_GUI_BENCH_THRESHOLDS=benchmarks/gui_responsiveness/live_target_thresholds.json \
MESH_GUI_BENCH_OUTPUT=benchmarks/gui_responsiveness/results/ci-live-target.json \
scripts/run_gui_responsiveness_ci.sh
```

For one-off comparisons, use `scripts/benchmark_gui_responsiveness.py` directly and commit the dated result JSON or markdown summary that captures the before/after data.
