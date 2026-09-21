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

The default view set includes **Scripts (Alpha)**. Its first measured poll must
replace the loading placeholder with either installed script cards or the empty
state, preserve the node navigator roster when nodes are present, and produce
no caught poll or poll-step errors. This turns renderer exceptions that the
long-running dashboard safely contains into benchmark failures instead of
silently green samples.

## Real-time scaling benchmark

The benchmark above uses Chromium virtual time. Virtual time hides wall-clock costs such as
network waits and long tasks, so it cannot catch a dashboard that gets slower as the mesh
grows. `scripts/benchmark_gui_realtime.py` drives Chromium in real time over the DevTools
protocol, as follows:

- It replaces `/api/state` with generated payloads (750 and 3,000 synthetic nodes by
  default). Every poll is a full `200` with a few freshly heard nodes.
- It records main-thread busy time, long tasks, event-loop lag, DOM size, and JavaScript
  exceptions for each scenario.

Absolute timings depend on the host, so the main budget is how cost scales from 750 to
3,000 nodes. A regression that is per node or per node pair shows up as a large ratio on
any machine. `realtime_thresholds.json` allows up to 4x busy time and 5x worst long task
for 4x the nodes. Before the 2026-09 fixes, the ratios were about 8x and 13x. After them,
they were about 2x and 2.5x.

Run it against a local dashboard, which only needs to serve the UI assets:

```bash
python scripts/benchmark_gui_realtime.py --url http://127.0.0.1:8877/ \
  --thresholds benchmarks/gui_responsiveness/realtime_thresholds.json
```

Add `--cpu-throttle 4` to approximate a slower laptop or phone. Pytest runs the gated
version as an opt-in test: it starts a temporary offline dashboard itself.

```bash
python -m pytest -m gui_benchmark --run-gui-benchmark tests/test_gui_realtime_benchmark.py
```

For one-off comparisons, use `scripts/benchmark_gui_responsiveness.py` directly and write outputs under `benchmarks/gui_responsiveness/results/`. That directory is ignored because benchmark output can include local hosts, URLs, and runtime-specific data.

To render a saved JSON result as a compact Markdown report:

```bash
python scripts/render_gui_benchmark_report.py \
  benchmarks/gui_responsiveness/results/local-gui-responsiveness.json \
  --output benchmarks/gui_responsiveness/results/local-gui-responsiveness.md
```

CI labels this offline check **GUI smoke test**. It reports view-switching errors
and basic responsiveness without comparing timings or DOM counts against a
previous run. The empty offline workload does not measure busy-mesh performance.
Normal local `pytest` runs skip browser checks unless explicitly enabled.

### Populated operation comparison

On pull requests, CI also checks out the exact PR base commit and runs the same
harness against both checkouts on the same runner. At 750 and 3,000 nodes, it
alternates base and PR execution across three independent runs and reports
median timings with minimum and maximum values. Overlapping ranges are
inconclusive; the comparison is advisory, not a percentage-based merge gate.

The workloads measure:

- State generation and JSON size with 25% recent nodes and 75% stale nodes.
- A SQLite-backed 30-day summary query with 172,800 rows, downsampled to 1,440 points.
- Link-quality path searches over connected graphs with about three edges per
  node, checking that the base and PR return identical results.
- Twenty unchanged presentation updates to 150 real Leaflet emoji markers,
  including the number of `setIcon` calls. Timing includes synchronous updates,
  not browser paint or end-to-end interaction latency.

Fixture construction and warmup are outside the measured operations. Each run
uses temporary databases and an isolated server without radio hardware. These
workloads cover specific operations; they do not establish performance for all
views, sensor queries, animations, or real radio traffic. Missing or failed
comparisons are reported as unavailable, never as a pass.

To compare two local checkouts:

```bash
python scripts/benchmark_pr_operations.py \
  --base /path/to/base-checkout \
  --current /path/to/pr-checkout \
  --browser /usr/bin/chromium \
  --output /tmp/mesh-operations.json
```

The harness writes raw results to the JSON path and a Markdown report beside it.
CI appends the populated comparison to the smoke-test comment and uploads both
reports. It does not reuse timings from unrelated runners or older CI runs.
