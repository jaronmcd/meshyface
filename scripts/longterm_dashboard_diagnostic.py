#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ENDPOINTS = (
    "/api/version",
    "/api/state?lite=1",
    "/api/state?lite=1&profile=chat",
)

DEFAULT_PROCESS_PATTERNS = ("mesh_dashboard.py",)

_STOP = False


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be > 0")
    return parsed


def _non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return parsed


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return parsed


def _handle_stop(signum: int, frame: object) -> None:
    del signum, frame
    global _STOP
    _STOP = True


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def append_cachebuster(url: str, value: str) -> str:
    parts = urllib.parse.urlsplit(url)
    query = dict(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
    query["_mesh_diag"] = value
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path or "/", urllib.parse.urlencode(query), parts.fragment)
    )


def endpoint_url(base_url: str, endpoint: str) -> str:
    endpoint = endpoint.strip()
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        return endpoint
    parts = urllib.parse.urlsplit(base_url)
    base = urllib.parse.urlunsplit((parts.scheme, parts.netloc, "/", "", ""))
    return urllib.parse.urljoin(base, endpoint.lstrip("/"))


def fetch_endpoint(base_url: str, endpoint: str, *, timeout: float, cachebuster: str) -> dict[str, Any]:
    url = append_cachebuster(endpoint_url(base_url, endpoint), cachebuster)
    started = time.monotonic()
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json,*/*;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "meshyface-longterm-diagnostic/1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            elapsed = time.monotonic() - started
            return {
                "endpoint": endpoint,
                "url": url,
                "ok": True,
                "status": int(response.status),
                "seconds": round(elapsed, 6),
                "bytes": len(body),
                "content_type": response.headers.get("Content-Type", ""),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read() if hasattr(exc, "read") else b""
        elapsed = time.monotonic() - started
        return {
            "endpoint": endpoint,
            "url": url,
            "ok": False,
            "status": int(exc.code),
            "seconds": round(elapsed, 6),
            "bytes": len(body),
            "error": str(exc),
        }
    except Exception as exc:
        elapsed = time.monotonic() - started
        return {
            "endpoint": endpoint,
            "url": url,
            "ok": False,
            "seconds": round(elapsed, 6),
            "bytes": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def parse_proc_status(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        value = raw_value.strip()
        parts = value.split()
        if len(parts) >= 2 and parts[1] == "kB":
            try:
                out[f"{key}_kb"] = int(parts[0])
            except ValueError:
                out[key] = value
        elif len(parts) == 1:
            try:
                out[key] = int(parts[0])
            except ValueError:
                out[key] = value
        else:
            out[key] = value
    return out


def parse_proc_stat(text: str) -> dict[str, Any]:
    # /proc/<pid>/stat has the command in parentheses, so split after the final ") ".
    if ") " not in text:
        return {}
    rest = text.rsplit(") ", 1)[1].split()
    if len(rest) < 22:
        return {}
    fields = {
        "state": rest[0],
        "ppid": rest[1],
        "utime_ticks": rest[11],
        "stime_ticks": rest[12],
        "num_threads": rest[17],
        "starttime_ticks": rest[19],
        "vsize_bytes": rest[20],
        "rss_pages": rest[21],
    }
    out: dict[str, Any] = {}
    for key, value in fields.items():
        if key == "state":
            out[key] = value
            continue
        try:
            out[key] = int(value)
        except ValueError:
            out[key] = value
    return out


def proc_cmdline(pid: int) -> str:
    raw = read_text(Path("/proc") / str(pid) / "cmdline")
    if raw is None:
        return ""
    return raw.replace("\x00", " ").strip()


def matching_pids(patterns: Iterable[str]) -> list[int]:
    clean_patterns = [pattern for pattern in (p.strip() for p in patterns) if pattern]
    if not clean_patterns:
        return []
    current_pid = os.getpid()
    pids: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == current_pid:
            continue
        cmdline = proc_cmdline(pid)
        if not cmdline:
            continue
        if any(pattern in cmdline for pattern in clean_patterns):
            pids.append(pid)
    return sorted(pids)


def process_metrics(pid: int) -> dict[str, Any]:
    base = Path("/proc") / str(pid)
    status_text = read_text(base / "status")
    stat_text = read_text(base / "stat")
    fd_count: int | None = None
    try:
        fd_count = len(list((base / "fd").iterdir()))
    except OSError:
        fd_count = None
    return {
        "pid": pid,
        "cmdline": proc_cmdline(pid),
        "fd_count": fd_count,
        "status": parse_proc_status(status_text or ""),
        "stat": parse_proc_stat(stat_text or ""),
    }


def aggregate_process_metrics(processes: list[dict[str, Any]]) -> dict[str, Any]:
    rss_kb = 0
    vm_size_kb = 0
    threads = 0
    fd_count = 0
    fd_count_known = True
    for proc in processes:
        status = proc.get("status") if isinstance(proc.get("status"), Mapping) else {}
        rss_kb += int(status.get("VmRSS_kb") or 0)
        vm_size_kb += int(status.get("VmSize_kb") or 0)
        threads += int(status.get("Threads") or 0)
        if proc.get("fd_count") is None:
            fd_count_known = False
        else:
            fd_count += int(proc["fd_count"])
    return {
        "count": len(processes),
        "rss_kb": rss_kb,
        "vm_size_kb": vm_size_kb,
        "threads": threads,
        "fd_count": fd_count if fd_count_known else None,
    }


def file_family_sizes(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    base = Path(path)
    out: dict[str, Any] = {"path": str(base)}
    for label, candidate in (
        ("db_bytes", base),
        ("wal_bytes", Path(f"{base}-wal")),
        ("shm_bytes", Path(f"{base}-shm")),
    ):
        try:
            out[label] = candidate.stat().st_size
        except OSError:
            out[label] = None
    return out


def sqlite_table_counts(path: str | None, *, timeout: float = 2.0) -> dict[str, Any]:
    if not path:
        return {}
    db_path = Path(path)
    if not db_path.exists():
        return {"path": str(db_path), "ok": False, "error": "missing"}
    started = time.monotonic()
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=timeout)
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
            counts = {}
            for (name,) in rows:
                escaped = str(name).replace('"', '""')
                counts[str(name)] = int(conn.execute(f'SELECT COUNT(*) FROM "{escaped}"').fetchone()[0])
            return {
                "path": str(db_path),
                "ok": True,
                "seconds": round(time.monotonic() - started, 6),
                "tables": counts,
            }
        finally:
            conn.close()
    except Exception as exc:
        return {
            "path": str(db_path),
            "ok": False,
            "seconds": round(time.monotonic() - started, 6),
            "error": f"{type(exc).__name__}: {exc}",
        }


def system_metrics() -> dict[str, Any]:
    meminfo: dict[str, int] = {}
    meminfo_text = read_text(Path("/proc/meminfo"))
    if meminfo_text:
        for line in meminfo_text.splitlines():
            parts = line.replace(":", "").split()
            if len(parts) >= 3 and parts[2] == "kB":
                try:
                    meminfo[f"{parts[0]}_kb"] = int(parts[1])
                except ValueError:
                    pass
    loadavg = read_text(Path("/proc/loadavg"))
    return {
        "loadavg": loadavg.strip() if loadavg else None,
        "meminfo": meminfo,
    }


def collect_sample(args: argparse.Namespace, sample_index: int) -> dict[str, Any]:
    cachebuster = f"{int(time.time() * 1000)}-{os.getpid()}-{sample_index}"
    process_patterns = list(args.process_pattern or DEFAULT_PROCESS_PATTERNS)
    processes = [process_metrics(pid) for pid in matching_pids(process_patterns)]
    sample: dict[str, Any] = {
        "schema": "meshyface.longterm_diagnostic.v1",
        "sample_index": sample_index,
        "ts_utc": utc_now_iso(),
        "ts_unix": round(time.time(), 3),
        "hostname": socket.gethostname(),
        "url": args.url,
        "system": system_metrics(),
        "process_patterns": process_patterns,
        "processes": processes,
        "process_totals": aggregate_process_metrics(processes),
        "files": {
            "history_db": file_family_sizes(args.history_db),
            "raw_db": file_family_sizes(args.raw_db),
        },
        "endpoints": [
            fetch_endpoint(args.url, endpoint, timeout=args.timeout_sec, cachebuster=cachebuster)
            for endpoint in args.endpoint
        ],
    }
    if args.db_count_every > 0 and sample_index % args.db_count_every == 0:
        sample["db_counts"] = {
            "history_db": sqlite_table_counts(args.history_db, timeout=args.db_timeout_sec),
            "raw_db": sqlite_table_counts(args.raw_db, timeout=args.db_timeout_sec),
        }
    return sample


def write_sample(output: Path, sample: Mapping[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as handle:
        json.dump(sample, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
        handle.flush()


def run(args: argparse.Namespace) -> int:
    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)
    output = args.output
    started = time.monotonic()
    sample_index = 0
    while not _STOP:
        sample_started = time.monotonic()
        sample = collect_sample(args, sample_index)
        write_sample(output, sample)
        sample_index += 1
        if args.duration_sec > 0 and time.monotonic() - started >= args.duration_sec:
            break
        sleep_for = max(0.0, args.interval_sec - (time.monotonic() - sample_started))
        end_sleep_at = time.monotonic() + sleep_for
        while not _STOP and time.monotonic() < end_sleep_at:
            time.sleep(min(1.0, end_sleep_at - time.monotonic()))
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect long-running Meshyface dashboard diagnostics as JSONL samples."
    )
    parser.add_argument("--url", default="http://127.0.0.1:8877", help="Dashboard base URL to sample.")
    parser.add_argument(
        "--endpoint",
        action="append",
        default=list(DEFAULT_ENDPOINTS),
        help="Endpoint path or absolute URL to fetch each sample. May be passed more than once.",
    )
    parser.add_argument(
        "--process-pattern",
        action="append",
        default=[],
        help="Substring to match against /proc/*/cmdline. May be passed more than once.",
    )
    parser.add_argument("--history-db", default="", help="History SQLite DB path to size/count.")
    parser.add_argument("--raw-db", default="", help="Raw packet SQLite DB path to size/count.")
    parser.add_argument("--output", type=Path, required=True, help="JSONL output path.")
    parser.add_argument("--interval-sec", type=_positive_float, default=60.0, help="Seconds between samples.")
    parser.add_argument(
        "--duration-sec",
        type=_non_negative_float,
        default=0.0,
        help="Total run time in seconds. 0 means run until stopped.",
    )
    parser.add_argument("--timeout-sec", type=_positive_float, default=10.0, help="HTTP fetch timeout.")
    parser.add_argument("--db-timeout-sec", type=_positive_float, default=2.0, help="SQLite read timeout.")
    parser.add_argument(
        "--db-count-every",
        type=_non_negative_int,
        default=10,
        help="Count SQLite tables every N samples. 0 disables counts.",
    )
    args = parser.parse_args(argv)
    if not args.process_pattern:
        args.process_pattern = list(DEFAULT_PROCESS_PATTERNS)
    return args


def main() -> int:
    return run(parse_args(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
