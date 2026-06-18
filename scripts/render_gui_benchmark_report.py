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


def render_markdown_report(result: Mapping[str, object]) -> str:
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
    parser.add_argument("--output", type=Path, default=None, help="Optional Markdown output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = json.loads(args.input_json.read_text(encoding="utf-8"))
    if not isinstance(result, Mapping):
        raise SystemExit("Benchmark result must be a JSON object.")
    report = render_markdown_report(result)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
