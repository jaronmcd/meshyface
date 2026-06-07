#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


RESULT_RE = re.compile(
    r'<pre[^>]+id=["\']mesh-gui-benchmark-result["\'][^>]*>(?P<json>.*?)</pre>',
    re.IGNORECASE | re.DOTALL,
)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be > 0")
    return parsed


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return parsed


def _browser_candidates() -> list[str]:
    env_browser = os.environ.get("MESH_GUI_BENCH_BROWSER", "").strip()
    candidates = [env_browser] if env_browser else []
    candidates.extend(
        [
            "chromium",
            "chromium-browser",
            "google-chrome",
            "google-chrome-stable",
            "chrome",
        ]
    )
    return [candidate for candidate in candidates if candidate]


def find_browser(explicit: str | None) -> str:
    if explicit:
        resolved = shutil.which(explicit) if os.sep not in explicit else explicit
        if resolved and Path(resolved).exists():
            return resolved
        raise SystemExit(f"Browser not found: {explicit}")
    for candidate in _browser_candidates():
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise SystemExit(
        "No Chromium-compatible browser found. Install chromium or pass --browser /path/to/chrome."
    )


def build_benchmark_url(
    base_url: str,
    *,
    iterations: int,
    warmup: int,
    views: str,
    settle_ms: int,
    include_api: bool,
    include_selection: bool,
    include_cached_poll: bool,
    include_interactions: bool,
) -> str:
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update(
        {
            "mesh_gui_bench": "1",
            "mesh_gui_bench_iterations": str(iterations),
            "mesh_gui_bench_warmup": str(warmup),
            "mesh_gui_bench_views": views,
            "mesh_gui_bench_settle_ms": str(settle_ms),
            "mesh_gui_bench_api": "1" if include_api else "0",
            "mesh_gui_bench_select": "1" if include_selection else "0",
            "mesh_gui_bench_cached_poll": "1" if include_cached_poll else "0",
            "mesh_gui_bench_interactions": "1" if include_interactions else "0",
            "chat_perf": "1",
            "_mesh_gui_bench": str(os.getpid()),
        }
    )
    path = parts.path or "/"
    return urlunsplit((parts.scheme, parts.netloc, path, urlencode(query), parts.fragment))


def browser_command(
    browser: str,
    url: str,
    *,
    window_size: str,
    virtual_time_budget_ms: int,
    user_data_dir: str,
    headless_flag: str,
    extra_args: list[str],
) -> list[str]:
    return [
        browser,
        headless_flag,
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-background-networking",
        "--disable-sync",
        "--metrics-recording-only",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={user_data_dir}",
        f"--window-size={window_size}",
        f"--virtual-time-budget={virtual_time_budget_ms}",
        "--dump-dom",
        *extra_args,
        url,
    ]


def run_browser(cmd: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def parse_result(dump_dom: str) -> dict:
    match = RESULT_RE.search(dump_dom)
    if not match:
        tail = dump_dom[-2000:].strip()
        raise ValueError(
            "Benchmark result marker was not found in browser output."
            + (f"\nLast browser output:\n{tail}" if tail else "")
        )
    payload = html.unescape(match.group("json"))
    return json.loads(payload)


def run_benchmark(args: argparse.Namespace) -> dict:
    browser = find_browser(args.browser)
    url = build_benchmark_url(
        args.url,
        iterations=args.iterations,
        warmup=args.warmup,
        views=args.views,
        settle_ms=args.settle_ms,
        include_api=not args.no_api,
        include_selection=not args.no_selection,
        include_cached_poll=not args.no_cached_poll,
        include_interactions=not args.no_interactions,
    )
    extra_args = list(args.browser_arg or [])
    with tempfile.TemporaryDirectory(prefix="mesh-gui-bench-") as user_data_dir:
        cmd = browser_command(
            browser,
            url,
            window_size=args.window_size,
            virtual_time_budget_ms=args.virtual_time_budget_ms,
            user_data_dir=user_data_dir,
            headless_flag="--headless=new",
            extra_args=extra_args,
        )
        proc = run_browser(cmd, args.timeout)
        if proc.returncode != 0 and "--headless=new" in cmd:
            fallback_cmd = browser_command(
                browser,
                url,
                window_size=args.window_size,
                virtual_time_budget_ms=args.virtual_time_budget_ms,
                user_data_dir=user_data_dir,
                headless_flag="--headless",
                extra_args=extra_args,
            )
            fallback_proc = run_browser(fallback_cmd, args.timeout)
            if fallback_proc.returncode == 0:
                proc = fallback_proc
            else:
                proc = proc
        if proc.returncode != 0:
            raise SystemExit(
                "Browser benchmark failed with exit code "
                f"{proc.returncode}.\nSTDERR:\n{proc.stderr[-4000:]}"
            )
        try:
            result = parse_result(proc.stdout)
        except Exception as exc:
            stderr_tail = proc.stderr[-4000:].strip()
            raise SystemExit(
                f"{exc}\nBrowser stderr:\n{stderr_tail}" if stderr_tail else str(exc)
            ) from exc
    result["_runner"] = {
        "browser": browser,
        "url": args.url,
        "window_size": args.window_size,
        "virtual_time_budget_ms": args.virtual_time_budget_ms,
    }
    return result


_MISSING = object()


def _json_pointer_get(payload: object, pointer: str) -> object:
    if pointer == "":
        return payload
    if not pointer.startswith("/"):
        raise ValueError(f"JSON pointer must be empty or start with '/': {pointer}")
    current = payload
    for raw_part in pointer.split("/")[1:]:
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping):
            if part not in current:
                return _MISSING
            current = current[part]
        elif isinstance(current, list):
            try:
                index = int(part)
            except ValueError:
                return _MISSING
            if index < 0 or index >= len(current):
                return _MISSING
            current = current[index]
        else:
            return _MISSING
    return current


def _as_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _display_value(value: object) -> str:
    if value is _MISSING:
        return "missing"
    try:
        return json.dumps(value, sort_keys=True)
    except TypeError:
        return str(value)


def load_thresholds(path: Path) -> dict:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"Unable to read benchmark thresholds {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid benchmark thresholds JSON {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise SystemExit(f"Benchmark thresholds must be a JSON object: {path}")
    return loaded


def evaluate_thresholds(result: Mapping[str, object], thresholds: Mapping[str, object]) -> list[str]:
    failures: list[str] = []
    for group_name in ("max", "min", "equals"):
        group = thresholds.get(group_name) or {}
        if not isinstance(group, Mapping):
            failures.append(f"{group_name} thresholds must be an object")
            continue
        for pointer, expected in group.items():
            if not isinstance(pointer, str):
                failures.append(f"{group_name} threshold path must be a string: {_display_value(pointer)}")
                continue
            try:
                actual = _json_pointer_get(result, pointer)
            except ValueError as exc:
                failures.append(f"{group_name} {pointer}: {exc}")
                continue
            if actual is _MISSING:
                failures.append(f"{group_name} {pointer}: expected {_display_value(expected)}, got missing")
                continue
            if group_name == "equals":
                if actual != expected:
                    failures.append(
                        f"equals {pointer}: expected {_display_value(expected)}, got {_display_value(actual)}"
                    )
                continue
            actual_number = _as_number(actual)
            expected_number = _as_number(expected)
            if expected_number is None:
                failures.append(
                    f"{group_name} {pointer}: threshold must be numeric, got {_display_value(expected)}"
                )
                continue
            if actual_number is None:
                failures.append(
                    f"{group_name} {pointer}: expected numeric value, got {_display_value(actual)}"
                )
                continue
            if group_name == "max" and actual_number > expected_number:
                failures.append(
                    f"max {pointer}: expected <= {_display_value(expected)}, got {_display_value(actual)}"
                )
            elif group_name == "min" and actual_number < expected_number:
                failures.append(
                    f"min {pointer}: expected >= {_display_value(expected)}, got {_display_value(actual)}"
                )
    return failures


def _fmt_ms(value: object) -> str:
    try:
        return f"{float(value):.1f} ms"
    except (TypeError, ValueError):
        return "n/a"


def _fmt_count(value: object) -> str:
    try:
        return f"{int(round(float(value))):,}"
    except (TypeError, ValueError):
        return "n/a"


def _fmt_bytes(value: object) -> str:
    try:
        size = float(value)
    except (TypeError, ValueError):
        return "n/a"
    units = ["B", "KB", "MB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(round(size))} B"
        size /= 1024
    return "n/a"


def print_summary(result: dict) -> None:
    summary = result.get("summary") or {}
    total = summary.get("totalMs") or {}
    callback = summary.get("callbackMs") or {}
    poll_work = summary.get("pollWorkMs") or {}
    poll_overhead = summary.get("pollOverheadMs") or {}
    frame_max = summary.get("frameMaxMs") or {}
    frame_p95 = summary.get("frameP95Ms") or {}
    state = result.get("state") or {}
    print("Mesh GUI responsiveness benchmark")
    print(f"  ok: {result.get('ok')}")
    print(f"  duration: {_fmt_ms(result.get('durationMs'))}")
    print(
        "  state: "
        f"{state.get('nodes', 0)} visible nodes, "
        f"{state.get('rawNodes', 0)} raw nodes, "
        f"{state.get('historyCaps', 0)} history caps, "
        f"{state.get('recentChat', 0)} recent chat rows"
    )
    dom = state.get("dom") or {}
    if dom:
        print(
            "  DOM: "
            f"{_fmt_count(dom.get('totalElements'))} elements, "
            f"{_fmt_bytes(dom.get('bodyHtmlBytes'))} body HTML, "
            f"{_fmt_count(dom.get('activeSurfaceElements'))} active surface elements"
        )
        print(
            "  DOM surfaces: "
            f"chat {_fmt_count(dom.get('chatFeedItems'))} feed / "
            f"{_fmt_count(dom.get('chatRosterVisibleItems'))} visible roster, "
            f"nodes {_fmt_count(dom.get('nodesTableRows'))} rows, "
            f"map {_fmt_count(dom.get('mapMarkers'))} markers, "
            f"graph {_fmt_count(dom.get('networkGraphNodes'))} nodes / "
            f"{_fmt_count(dom.get('networkGraphEdges'))} edges, "
            f"sensors {_fmt_count(dom.get('sensorElements'))} elems"
        )
    print(
        "  sample total: "
        f"p50 {_fmt_ms(total.get('p50'))}, "
        f"p95 {_fmt_ms(total.get('p95'))}, "
        f"max {_fmt_ms(total.get('max'))}"
    )
    if callback.get("count"):
        print(
            "  sample callback: "
            f"p50 {_fmt_ms(callback.get('p50'))}, "
            f"p95 {_fmt_ms(callback.get('p95'))}, "
            f"max {_fmt_ms(callback.get('max'))}"
        )
    if poll_work.get("count"):
        print(
            "  poll work: "
            f"p50 {_fmt_ms(poll_work.get('p50'))}, "
            f"p95 {_fmt_ms(poll_work.get('p95'))}, "
            f"overhead p95 {_fmt_ms(poll_overhead.get('p95'))}"
        )
    print(
        "  frame delay: "
        f"p95 {_fmt_ms(frame_p95.get('p95'))}, "
        f"max {_fmt_ms(frame_max.get('max'))}, "
        f"long tasks {summary.get('longTaskCount', 0)}"
    )
    api_rows = result.get("api") or []
    if api_rows:
        print("  API timings:")
        for row in api_rows:
            label = row.get("label", "api")
            status = row.get("status", "err")
            size = row.get("bytes", 0)
            total_ms = row.get("totalMs", 0)
            ok = "ok" if row.get("ok") else "fail"
            print(f"    {label}: {ok} HTTP {status}, {_fmt_ms(total_ms)}, {size} bytes")
    by_label = summary.get("byLabel") or {}
    if by_label:
        print("  Slowest labels by p95 work/total:")
        def _label_rank(item: tuple[str, dict]) -> tuple[float, str]:
            label, data = item
            action_stats = data.get("actionSyncMs") or {}
            if action_stats.get("count"):
                return (float(action_stats.get("p95") or 0), label)
            poll_stats = data.get("pollWorkMs") or {}
            if poll_stats.get("count"):
                return (float(poll_stats.get("p95") or 0), label)
            total_stats = data.get("totalMs") or {}
            return (float(total_stats.get("p95") or 0), label)

        ranked = sorted(
            by_label.items(),
            key=_label_rank,
            reverse=True,
        )
        for label, data in ranked[:8]:
            stats = data.get("totalMs") or {}
            callback_stats = data.get("callbackMs") or {}
            frame_stats = data.get("frameMaxMs") or {}
            poll_stats = data.get("pollWorkMs") or {}
            action_stats = data.get("actionSyncMs") or {}
            active_dom_stats = data.get("domActiveSurfaceElements") or {}
            action_suffix = (
                f", action p95 {_fmt_ms(action_stats.get('p95'))}"
                if action_stats.get("count")
                else ""
            )
            poll_suffix = (
                f", poll work p95 {_fmt_ms(poll_stats.get('p95'))}"
                if poll_stats.get("count")
                else ""
            )
            dom_suffix = (
                f", active DOM p95 {_fmt_count(active_dom_stats.get('p95'))}"
                if active_dom_stats.get("count")
                else ""
            )
            print(
                f"    {label}: p95 {_fmt_ms(stats.get('p95'))}, "
                f"callback p95 {_fmt_ms(callback_stats.get('p95'))}, "
                f"max frame {_fmt_ms(frame_stats.get('max'))}, "
                f"long tasks {data.get('longTaskCount', 0)}"
                f"{action_suffix}"
                f"{poll_suffix}"
                f"{dom_suffix}"
            )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Meshyface in-browser GUI responsiveness benchmark with headless Chromium."
    )
    parser.add_argument("--url", default="http://127.0.0.1:8877/", help="Dashboard base URL.")
    parser.add_argument("--browser", default=None, help="Chromium/Chrome executable path or name.")
    parser.add_argument("--iterations", type=_positive_int, default=5, help="Measured iterations per view.")
    parser.add_argument("--warmup", type=_non_negative_int, default=1, help="Initial unmeasured poll warmups.")
    parser.add_argument(
        "--views",
        default="chat,network:map,network:graph,history,settings,console",
        help="Comma-separated views; network subviews use view:subview.",
    )
    parser.add_argument("--settle-ms", type=_non_negative_int, default=80, help="Delay between measured actions.")
    parser.add_argument("--window-size", default="1366,900", help="Headless browser window size.")
    parser.add_argument(
        "--virtual-time-budget-ms",
        type=_positive_int,
        default=90000,
        help="Chromium virtual-time budget for the benchmark page.",
    )
    parser.add_argument("--timeout", type=_positive_int, default=120, help="Browser process timeout in seconds.")
    parser.add_argument("--output-json", type=Path, default=None, help="Write full benchmark JSON to this path.")
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=None,
        help="JSON file with max/min/equals JSON-pointer thresholds. Fails nonzero on budget regressions.",
    )
    parser.add_argument("--json", action="store_true", help="Print full benchmark JSON instead of text summary.")
    parser.add_argument("--no-api", action="store_true", help="Skip direct API timing probes.")
    parser.add_argument("--no-selection", action="store_true", help="Skip node selection timing probes.")
    parser.add_argument("--no-cached-poll", action="store_true", help="Skip conditional 304 poll timing samples.")
    parser.add_argument("--no-interactions", action="store_true", help="Skip chat typing, scroll, roster, reply, and reaction interaction samples.")
    parser.add_argument(
        "--browser-arg",
        action="append",
        default=[],
        help="Extra argument passed through to Chromium. May be repeated.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    result = run_benchmark(args)
    threshold_failures: list[str] = []
    if args.thresholds:
        threshold_failures = evaluate_thresholds(result, load_thresholds(args.thresholds))
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print_summary(result)
    if threshold_failures:
        print("Benchmark threshold failures:")
        for failure in threshold_failures:
            print(f"  - {failure}")
    if not result.get("ok"):
        return 1
    return 2 if threshold_failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
