#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path


def _stat(payload: Mapping[str, object], name: str, field: str) -> object:
    value = payload.get(name)
    if isinstance(value, Mapping):
        return value.get(field)
    return None


def _as_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _percent_delta(current: float, baseline: float) -> str:
    if baseline == 0:
        return "n/a"
    percent = ((current - baseline) / abs(baseline)) * 100
    if round(percent, 1) == 0:
        percent = 0.0
    return f"{percent:+.1f}%"


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
    for unit in ("B", "KB", "MB"):
        if size < 1024 or unit == "MB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(round(size))} B"
        size /= 1024
    return "n/a"


def _fmt_signed_ms(value: object) -> str:
    number = _as_number(value)
    return "n/a" if number is None else f"{number:+.1f} ms"


def _fmt_signed_count(value: object) -> str:
    number = _as_number(value)
    return "n/a" if number is None else f"{number:+,.0f}"


def _fmt_signed_bytes(value: object) -> str:
    number = _as_number(value)
    if number is None:
        return "n/a"
    sign = "+" if number >= 0 else "-"
    return sign + _fmt_bytes(abs(number))


def _escape_cell(value: object) -> str:
    text = str(value if value is not None else "n/a")
    return text.replace("|", "\\|").replace("\n", " ")


def _rank_label(item: tuple[str, object]) -> tuple[float, str]:
    label, raw_data = item
    data = raw_data if isinstance(raw_data, Mapping) else {}
    for metric in ("actionSyncMs", "pollWorkMs", "totalMs"):
        stats = data.get(metric)
        if isinstance(stats, Mapping) and stats.get("count"):
            try:
                return (float(stats.get("p95") or 0), label)
            except (TypeError, ValueError):
                return (0.0, label)
    return (0.0, label)


def _table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = [
        "| " + " | ".join(_escape_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_escape_cell(cell) for cell in row) + " |")
    return lines


def _comparison_metric(
    label: str,
    current: object,
    baseline: object,
    formatter,
    delta_formatter,
) -> list[object]:
    current_number = _as_number(current)
    baseline_number = _as_number(baseline)
    if current_number is None or baseline_number is None:
        return [label, formatter(baseline), formatter(current), "n/a", "n/a"]
    delta = current_number - baseline_number
    return [
        label,
        formatter(baseline_number),
        formatter(current_number),
        delta_formatter(delta),
        _percent_delta(current_number, baseline_number),
    ]


def _summary_mapping(payload: Mapping[str, object]) -> Mapping[str, object]:
    summary = payload.get("summary")
    return summary if isinstance(summary, Mapping) else {}


def _baseline_app_signal_rows(
    result: Mapping[str, object],
    baseline: Mapping[str, object],
) -> list[list[object]]:
    current_summary = _summary_mapping(result)
    baseline_summary = _summary_mapping(baseline)
    return [
        _comparison_metric(
            "Poll work p95",
            _stat(current_summary, "pollWorkMs", "p95"),
            _stat(baseline_summary, "pollWorkMs", "p95"),
            _fmt_ms,
            _fmt_signed_ms,
        ),
        _comparison_metric(
            "Long tasks",
            current_summary.get("longTaskCount"),
            baseline_summary.get("longTaskCount"),
            _fmt_count,
            _fmt_signed_count,
        ),
        _comparison_metric(
            "Total DOM p95",
            _stat(current_summary, "domTotalElements", "p95"),
            _stat(baseline_summary, "domTotalElements", "p95"),
            _fmt_count,
            _fmt_signed_count,
        ),
        _comparison_metric(
            "Active DOM p95",
            _stat(current_summary, "domActiveSurfaceElements", "p95"),
            _stat(baseline_summary, "domActiveSurfaceElements", "p95"),
            _fmt_count,
            _fmt_signed_count,
        ),
        _comparison_metric(
            "Body HTML p95",
            _stat(current_summary, "domBodyHtmlBytes", "p95"),
            _stat(baseline_summary, "domBodyHtmlBytes", "p95"),
            _fmt_bytes,
            _fmt_signed_bytes,
        ),
    ]


def _baseline_timing_rows(
    result: Mapping[str, object],
    baseline: Mapping[str, object],
) -> list[list[object]]:
    current_summary = _summary_mapping(result)
    baseline_summary = _summary_mapping(baseline)
    return [
        _comparison_metric(
            "Total sample p95",
            _stat(current_summary, "totalMs", "p95"),
            _stat(baseline_summary, "totalMs", "p95"),
            _fmt_ms,
            _fmt_signed_ms,
        ),
        _comparison_metric(
            "Callback p95",
            _stat(current_summary, "callbackMs", "p95"),
            _stat(baseline_summary, "callbackMs", "p95"),
            _fmt_ms,
            _fmt_signed_ms,
        ),
        _comparison_metric(
            "Frame p95",
            _stat(current_summary, "frameP95Ms", "p95"),
            _stat(baseline_summary, "frameP95Ms", "p95"),
            _fmt_ms,
            _fmt_signed_ms,
        ),
    ]


def render_baseline_comparison(
    result: Mapping[str, object],
    baseline: Mapping[str, object],
) -> list[str]:
    lines = [
        "",
        "## Baseline Comparison",
        "",
        "Compared with the latest successful `gui-benchmark-report` artifact from the base branch.",
        (
            "App-owned signals are the primary regression check because same-code browser "
            "timing can move on GitHub-hosted runners."
        ),
        "Positive deltas mean the current run is higher than baseline.",
        "",
    ]
    lines.extend(
        _table(
            ["Metric", "Before (base)", "After (current)", "Delta", "Delta %"],
            _baseline_app_signal_rows(result, baseline),
        )
    )
    lines.extend(
        [
            "",
            "### Browser/Runner Timing",
            "",
            (
                "These rows include headless browser scheduling and are informational; "
                "wall-clock duration is shown as run metadata only."
            ),
            "",
        ]
    )
    lines.extend(
        _table(
            ["Metric", "Before (base)", "After (current)", "Delta", "Delta %"],
            _baseline_timing_rows(result, baseline),
        )
    )
    return lines


def render_pr_comment(
    result: Mapping[str, object],
    *,
    baseline: Mapping[str, object] | None = None,
    run_url: str | None = None,
) -> str:
    summary = _summary_mapping(result)
    summary_rows = [
        ["Result", "pass" if result.get("ok") else "fail"],
        ["Duration", _fmt_ms(result.get("durationMs"))],
        ["Samples", _fmt_count(summary.get("samples"))],
        ["Long tasks", _fmt_count(summary.get("longTaskCount"))],
        ["Errors", _fmt_count(summary.get("errors"))],
    ]
    lines = [
        "<!-- meshyface-gui-benchmark-report -->",
        "## GUI Benchmark Before/After",
        "",
        "This comment is updated by CI on each PR run.",
    ]

    if baseline is None:
        lines.extend(
            [
                "",
                "No base-branch benchmark artifact was available for a before/after comparison.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "App-owned signals are compared against the latest successful base-branch benchmark.",
                "These are the main before/after rows to use when judging a PR.",
                "",
            ]
        )
        lines.extend(
            _table(
                ["Metric", "Before (base)", "After (PR)", "Delta", "Delta %"],
                _baseline_app_signal_rows(result, baseline),
            )
        )
        lines.extend(
            [
                "",
                "<details>",
                "<summary>Browser/runner timing details</summary>",
                "",
                (
                    "These rows include headless browser scheduling and can change between "
                    "same-code CI runs. Duration is shown above as run metadata only."
                ),
                "",
            ]
        )
        lines.extend(
            _table(
                ["Metric", "Before (base)", "After (PR)", "Delta", "Delta %"],
                _baseline_timing_rows(result, baseline),
            )
        )
        lines.extend(["", "</details>"])

    lines.extend(["", "### Run Summary", ""])
    lines.extend(_table(["Field", "Value"], summary_rows))

    if run_url:
        lines.extend(["", f"Full report and raw JSON: [Actions run]({run_url})."])
    lines.append("")
    return "\n".join(lines)


def render_markdown_report(
    result: Mapping[str, object],
    *,
    baseline: Mapping[str, object] | None = None,
) -> str:
    summary = result.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    state = result.get("state")
    state = state if isinstance(state, Mapping) else {}
    dom = state.get("dom")
    dom = dom if isinstance(dom, Mapping) else {}
    runner = result.get("_runner")
    runner = runner if isinstance(runner, Mapping) else {}

    lines = ["# Meshyface GUI Benchmark Report", ""]
    lines.extend(
        _table(
            ["Field", "Value"],
            [
                ["Result", "pass" if result.get("ok") else "fail"],
                ["Duration", _fmt_ms(result.get("durationMs"))],
                ["Samples", _fmt_count(summary.get("samples"))],
                ["Long tasks", _fmt_count(summary.get("longTaskCount"))],
                ["Errors", _fmt_count(summary.get("errors"))],
                ["Browser", runner.get("browser", "n/a")],
                ["Window", runner.get("window_size", "n/a")],
            ],
        )
    )

    if baseline is not None:
        lines.extend(render_baseline_comparison(result, baseline))

    lines.extend(["", "## Timing", ""])
    lines.extend(
        _table(
            ["Metric", "p50", "p95", "max"],
            [
                [
                    "Total sample",
                    _fmt_ms(_stat(summary, "totalMs", "p50")),
                    _fmt_ms(_stat(summary, "totalMs", "p95")),
                    _fmt_ms(_stat(summary, "totalMs", "max")),
                ],
                [
                    "Callback",
                    _fmt_ms(_stat(summary, "callbackMs", "p50")),
                    _fmt_ms(_stat(summary, "callbackMs", "p95")),
                    _fmt_ms(_stat(summary, "callbackMs", "max")),
                ],
                [
                    "Poll work",
                    _fmt_ms(_stat(summary, "pollWorkMs", "p50")),
                    _fmt_ms(_stat(summary, "pollWorkMs", "p95")),
                    _fmt_ms(_stat(summary, "pollWorkMs", "max")),
                ],
                [
                    "Frame p95",
                    _fmt_ms(_stat(summary, "frameP95Ms", "p50")),
                    _fmt_ms(_stat(summary, "frameP95Ms", "p95")),
                    _fmt_ms(_stat(summary, "frameP95Ms", "max")),
                ],
            ],
        )
    )

    lines.extend(["", "## DOM And State", ""])
    lines.extend(
        _table(
            ["Metric", "Value"],
            [
                ["Visible nodes", _fmt_count(state.get("nodes"))],
                ["Raw nodes", _fmt_count(state.get("rawNodes"))],
                ["Recent chat rows", _fmt_count(state.get("recentChat"))],
                ["Total DOM elements", _fmt_count(dom.get("totalElements"))],
                ["Active surface elements", _fmt_count(dom.get("activeSurfaceElements"))],
                ["Body HTML", _fmt_bytes(dom.get("bodyHtmlBytes"))],
                ["Map markers", _fmt_count(dom.get("mapMarkers"))],
                ["Graph nodes", _fmt_count(dom.get("networkGraphNodes"))],
                ["Graph edges", _fmt_count(dom.get("networkGraphEdges"))],
            ],
        )
    )

    by_label = summary.get("byLabel")
    by_label = by_label if isinstance(by_label, Mapping) else {}
    if by_label:
        rows: list[list[object]] = []
        for label, raw_data in sorted(by_label.items(), key=_rank_label, reverse=True)[:8]:
            data = raw_data if isinstance(raw_data, Mapping) else {}
            rows.append(
                [
                    label,
                    _fmt_ms(_stat(data, "totalMs", "p95")),
                    _fmt_ms(_stat(data, "callbackMs", "p95")),
                    _fmt_ms(_stat(data, "pollWorkMs", "p95")),
                    _fmt_ms(_stat(data, "frameMaxMs", "max")),
                    _fmt_count(_stat(data, "domActiveSurfaceElements", "p95")),
                    _fmt_count(data.get("longTaskCount")),
                ]
            )
        lines.extend(["", "## Slowest Labels", ""])
        lines.extend(
            _table(
                [
                    "Label",
                    "Total p95",
                    "Callback p95",
                    "Poll work p95",
                    "Max frame",
                    "Active DOM p95",
                    "Long tasks",
                ],
                rows,
            )
        )

    api_rows = result.get("api")
    if isinstance(api_rows, list) and api_rows:
        rows = []
        for raw_row in api_rows[:12]:
            if not isinstance(raw_row, Mapping):
                continue
            status = f"HTTP {raw_row.get('status')}" if raw_row.get("status") else "n/a"
            rows.append(
                [
                    raw_row.get("label", "api"),
                    "ok" if raw_row.get("ok") else "fail",
                    status,
                    _fmt_ms(raw_row.get("totalMs")),
                    _fmt_bytes(raw_row.get("bytes")),
                ]
            )
        if rows:
            lines.extend(["", "## API Probes", ""])
            lines.extend(_table(["Label", "Result", "Status", "Total", "Size"], rows))

    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a Meshyface GUI benchmark JSON result as a compact Markdown report."
    )
    parser.add_argument("input_json", type=Path, help="Benchmark JSON produced by benchmark_gui_responsiveness.py.")
    parser.add_argument("--baseline-json", type=Path, default=None, help="Optional baseline benchmark JSON.")
    parser.add_argument("--output", type=Path, default=None, help="Optional Markdown output path.")
    parser.add_argument("--pr-comment-output", type=Path, default=None, help="Optional compact PR comment output path.")
    parser.add_argument("--run-url", default=None, help="Optional GitHub Actions run URL to include in PR comment output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = json.loads(args.input_json.read_text(encoding="utf-8"))
    if not isinstance(result, Mapping):
        raise SystemExit("Benchmark result must be a JSON object.")
    baseline = None
    if args.baseline_json:
        baseline = json.loads(args.baseline_json.read_text(encoding="utf-8"))
        if not isinstance(baseline, Mapping):
            raise SystemExit("Baseline benchmark result must be a JSON object.")
    report = render_markdown_report(result, baseline=baseline)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    if args.pr_comment_output:
        comment = render_pr_comment(result, baseline=baseline, run_url=args.run_url)
        args.pr_comment_output.parent.mkdir(parents=True, exist_ok=True)
        args.pr_comment_output.write_text(comment, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
