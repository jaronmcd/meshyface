#!/usr/bin/env python3
"""Compare populated operation workloads in two checkouts using one shared harness."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import urllib.request

HARNESS = Path(__file__).resolve()
METRICS = {
    "state_ms": "State generation + JSON (ms)",
    "state_bytes": "State JSON (bytes)",
    "history_ms": "30-day summary query + JSON (ms)",
    "roster_ms": "Link-quality search (ms)",
    "map_refresh_ms": "20 unchanged marker refreshes (ms)",
    "map_icon_writes": "Marker setIcon calls",
}


def timed(fn):
    started = time.perf_counter()
    value = fn()
    return (time.perf_counter() - started) * 1000, value


def backend_workloads(directory: Path, node_count: int) -> dict:
    from meshdash.api_history_summary import build_summary_metrics_response
    from meshdash.api_input_history import parse_history_window_request
    from meshdash.helpers import to_int
    from meshdash.history_store_runtime_impl import HistoryStore
    from meshdash.history_views import empty_summary_metrics
    from meshdash.state_node_contracts import CollectedNodes
    from meshdash.state_service import build_dashboard_state_lite
    from meshdash.tracker_snapshot_contracts import empty_tracker_snapshot

    now = int(time.time())
    rows = [{"id": f"!{0x20000000 + i:08x}", "short_name": f"N{i}",
             "last_heard_unix": now - (60 if i < node_count // 4 else 40 * 86400)}
            for i in range(node_count)]
    snapshot = empty_tracker_snapshot()

    def state():
        payload = build_dashboard_state_lite(
            iface=SimpleNamespace(localNode=None), tracker=SimpleNamespace(),
            target="benchmark", started_at=now, storage_probe_path=None,
            show_secrets=False, sensitive_field_names=set(), revision_info={"version": "benchmark"},
            profile="chat",
            collect_nodes_fn=lambda _: CollectedNodes(
                rows=[dict(r) for r in rows], full=[], by_id={r["id"]: dict(r) for r in rows},
                with_position_count=0),
            load_tracker_snapshot_safe_fn=lambda *_: (snapshot, None),
            load_tracker_node_saved_counts_safe_fn=lambda *_: ({}, None),
            load_tracker_node_capabilities_safe_fn=lambda *_: ({}, None),
        )
        assert len(payload["nodes"]) >= node_count // 4
        return json.dumps(payload, separators=(",", ":")).encode()

    state()
    state_ms, state_body = timed(state)
    store = HistoryStore(str(directory / "history.sqlite3"), 500000, 90, 500000, 90, 90)
    try:
        start = now - 30 * 86400 + 15
        store._conn.executemany(
            "INSERT INTO summary_metrics_1m (bucket_unix, node_count, saved_node_count, "
            "online_node_count, nodes_with_position, live_packet_count, edge_count, "
            "real_edge_count, last_seen_unix) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ((start + i * 15, node_count, node_count, 200, 150, i, 500, 500, start + i * 15)
             for i in range(172800)),
        )
        store._conn.commit()

        def history():
            payload = build_summary_metrics_response(
                query="hours=720&points=1440&packet_series=0",
                summary_metrics_fn=store.load_summary_metrics, default_node_history_hours=24,
                to_int_fn=to_int, parse_history_window_request_fn=parse_history_window_request,
                empty_summary_metrics_fn=empty_summary_metrics,
            )
            assert 1000 <= len(payload["points"]) <= 1440
            return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

        history()
        history_ms, history_body = timed(history)
    finally:
        store.close()
    return {"state_ms": state_ms, "state_bytes": len(state_body), "history_ms": history_ms,
            "history_points": len(json.loads(history_body)["points"])}


def worker(repo: Path, browser: str, node_count: int) -> dict:
    sys.path.insert(0, str(repo))
    from benchmark_gui_realtime import _free_port, build_synthetic_state, run_scenario

    with tempfile.TemporaryDirectory(prefix="mesh-pr-operations-") as temp:
        directory = Path(temp)
        result = backend_workloads(directory, node_count)
        port = _free_port()
        url = f"http://127.0.0.1:{port}/"
        with (directory / "server.log").open("w+") as log:
            server = subprocess.Popen(
                [sys.executable, str(repo / "mesh_dashboard.py"), "--mesh-host", "127.0.0.1",
                 "--mesh-tcp-port", "1", "--http-host", "127.0.0.1", "--http-port", str(port),
                 "--refresh-ms", "1000", "--history-db", str(directory / "server.sqlite3")],
                cwd=repo, stdout=log, stderr=subprocess.STDOUT,
            )
            try:
                for _ in range(100):
                    try:
                        with urllib.request.urlopen(url + "api/version", timeout=1):
                            break
                    except OSError:
                        if server.poll() is not None:
                            log.seek(0)
                            raise RuntimeError(log.read()[-4000:])
                        time.sleep(0.1)
                else:
                    raise RuntimeError("Benchmark server did not start")
                fixture = build_synthetic_state(node_count, now_unix=1_800_000_000)
                probe = HARNESS.with_suffix(".js").read_text().replace("BENCH_FIXTURE", json.dumps(fixture))
                scenario = run_scenario(
                    url=url, browser=browser, node_count=node_count, cpu_throttle=1,
                    warmup_s=5, measure_s=1, extra_browser_args=["--no-sandbox"], operation_probe=probe,
                )
                if scenario["js_exceptions"]:
                    raise RuntimeError(f"Browser exceptions: {scenario['js_exceptions']}")
                operations = scenario["operations"]
                quality = operations.pop("quality")
                result.update(operations)
                result["quality_digest"] = hashlib.sha256(json.dumps(quality).encode()).hexdigest()
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
        return result


def validate_runs(runs: dict) -> None:
    for side in ("base", "current"):
        if len(runs.get(side, [])) != 3:
            raise ValueError("Comparison requires three complete runs of each checkout")
        for run in runs[side]:
            for metric in METRICS:
                value = run.get(metric)
                if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError(f"Invalid measurement: {side}/{metric}")
            if run.get("map_markers") != 150 or run.get("roster_targets", 0) < 200:
                raise ValueError("Populated browser workload was not exercised")
    if len({r["quality_digest"] for side in runs.values() for r in side}) != 1:
        raise ValueError("Link-quality results differ; no performance claim is valid")


def render_report(result: dict) -> str:
    lines = ["## Populated operation comparison", "",
             f"Base `{result['base_commit'][:12]}` vs PR `{result['current_commit'][:12]}`.", "",
             "Same harness and generated data, alternating base/PR execution on the same runner; "
             "three independent runs per size. Values are median [min–max]. Lower is less work.", "",
             "These are operation timings, not end-to-end user latency. Map timings cover synchronous "
             "refresh work on 150 real Leaflet emoji markers, excluding paint. State inputs are 25% "
             "recent nodes; history contains 172,800 SQLite summary rows. Roster graphs have about "
             "three edges per node and search one-third of nodes. Overlapping timing ranges are inconclusive.", "",
             "| Nodes | Operation | Base | PR | Median change |", "| --- | --- | --- | --- | --- |"]
    for nodes, runs in result["scenarios"].items():
        validate_runs(runs)
        for metric, label in METRICS.items():
            before = [r[metric] for r in runs["base"]]
            after = [r[metric] for r in runs["current"]]
            def fmt(values):
                return f"{statistics.median(values):,.1f} [{min(values):,.1f}–{max(values):,.1f}]"
            median_before = statistics.median(before)
            delta = ((statistics.median(after) / median_before - 1) * 100) if median_before else None
            change = "n/a" if delta is None else f"{delta:+.1f}%"
            lines.append(f"| {nodes} | {label} | {fmt(before)} | {fmt(after)} | {change} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path)
    parser.add_argument("--current", type=Path, default=Path.cwd())
    parser.add_argument("--browser", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--nodes", type=int, default=750)
    args = parser.parse_args()
    # Keep user environment overrides from changing the workload in just one checkout.
    os.environ["MESH_DASH_STATE_NODE_WINDOW_DAYS"] = "14"
    if args.worker:
        print(json.dumps(worker(args.worker.resolve(), args.browser, args.nodes)))
        return
    if not args.base or not args.output:
        parser.error("--base and --output are required for comparisons")
    repos = {"base": args.base.resolve(), "current": args.current.resolve()}
    result = {f"{side}_commit": subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip() for side, repo in repos.items()}
    result["scenarios"] = {}
    result["complete"] = False
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix(".md").unlink(missing_ok=True)
    for nodes in (750, 3000):
        runs = {"base": [], "current": []}
        result["scenarios"][str(nodes)] = runs
        for repeat in range(3):
            for side in (("base", "current") if repeat % 2 == 0 else ("current", "base")):
                print(f"Running {side}, {nodes} nodes, repetition {repeat + 1}", flush=True)
                output = subprocess.check_output(
                    [sys.executable, str(HARNESS), "--worker", str(repos[side]), "--browser", args.browser,
                     "--nodes", str(nodes)], text=True, timeout=300,
                )
                runs[side].append(json.loads(output))
                args.output.write_text(json.dumps(result, indent=2) + "\n")
        validate_runs(runs)
    result["complete"] = True
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    args.output.with_suffix(".md").write_text(render_report(result))


if __name__ == "__main__":
    main()
