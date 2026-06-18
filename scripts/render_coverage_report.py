#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path


def _as_mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _as_number(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fmt_count(value: object) -> str:
    return f"{int(round(_as_number(value))):,}"


def _fmt_percent(value: object) -> str:
    return f"{_as_number(value):.1f}%"


def _escape_cell(value: object) -> str:
    text = str(value if value is not None else "n/a")
    return text.replace("|", "\\|").replace("\n", " ")


def _table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = [
        "| " + " | ".join(_escape_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_escape_cell(cell) for cell in row) + " |")
    return lines


def _summary_rows(payload: Mapping[str, object]) -> list[list[object]]:
    totals = _as_mapping(payload.get("totals"))
    return [
        ["Coverage", _fmt_percent(totals.get("percent_covered"))],
        ["Statements", _fmt_count(totals.get("num_statements"))],
        ["Covered", _fmt_count(totals.get("covered_lines"))],
        ["Missing", _fmt_count(totals.get("missing_lines"))],
    ]


def _gap_rows(payload: Mapping[str, object], *, limit: int) -> list[list[object]]:
    files = _as_mapping(payload.get("files"))
    rows = []
    for path, raw_data in files.items():
        data = _as_mapping(raw_data)
        summary = _as_mapping(data.get("summary"))
        statements = _as_number(summary.get("num_statements"))
        if statements <= 0:
            continue
        missing = _as_number(summary.get("missing_lines"))
        if missing <= 0:
            continue
        rows.append(
            {
                "path": str(path),
                "coverage": _as_number(summary.get("percent_covered")),
                "statements": statements,
                "missing": missing,
            }
        )
    rows.sort(key=lambda item: (-item["missing"], item["coverage"], item["path"]))
    return [
        [
            row["path"],
            _fmt_percent(row["coverage"]),
            _fmt_count(row["statements"]),
            _fmt_count(row["missing"]),
        ]
        for row in rows[:limit]
    ]


def render_markdown_report(
    payload: Mapping[str, object],
    *,
    limit: int = 15,
    run_url: str | None = None,
    pr_comment: bool = False,
) -> str:
    lines = []
    if pr_comment:
        lines.append("<!-- meshyface-coverage-report -->")
    lines.extend(
        [
            "## Coverage Report" if pr_comment else "# Meshyface Coverage Report",
            "",
            "Coverage is advisory; no minimum is enforced yet.",
            "",
        ]
    )
    lines.extend(_table(["Metric", "Value"], _summary_rows(payload)))

    gap_rows = _gap_rows(payload, limit=limit)
    if gap_rows:
        lines.extend(
            [
                "",
                "### Largest Gaps",
                "",
                "Files are sorted by missing statements so the next test targets are obvious.",
                "",
            ]
        )
        lines.extend(_table(["File", "Coverage", "Statements", "Missing"], gap_rows))

    if run_url:
        lines.extend(["", f"Full coverage artifacts: [Actions run]({run_url})."])
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render coverage.py JSON output as Markdown.")
    parser.add_argument("input_json", type=Path, help="coverage json output.")
    parser.add_argument("--output", type=Path, default=None, help="Optional Markdown report output path.")
    parser.add_argument("--pr-comment-output", type=Path, default=None, help="Optional PR comment Markdown output path.")
    parser.add_argument("--run-url", default=None, help="Optional GitHub Actions run URL.")
    parser.add_argument("--limit", type=int, default=15, help="Maximum number of gap rows to show.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise SystemExit("Coverage JSON must be a JSON object.")
    report = render_markdown_report(payload, limit=args.limit, run_url=args.run_url)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    if args.pr_comment_output:
        comment = render_markdown_report(
            payload,
            limit=args.limit,
            run_url=args.run_url,
            pr_comment=True,
        )
        args.pr_comment_output.parent.mkdir(parents=True, exist_ok=True)
        args.pr_comment_output.write_text(comment, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
