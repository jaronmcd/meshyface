from __future__ import annotations

import os
import sys
import threading
from collections.abc import Callable, Sequence


_RESTART_LOCK = threading.Lock()
_RESTART_SCHEDULED = False


def _exec_python_process(executable: str, args: Sequence[str]) -> None:
    os.execv(executable, list(args))


def _restart_command(
    *,
    executable: str | None = None,
    argv: Sequence[object] | None = None,
) -> tuple[str, list[str]]:
    clean_executable = str(executable or sys.executable or "").strip()
    if not clean_executable:
        return "", []
    raw_argv = list(sys.argv if argv is None else argv)
    clean_argv = [str(value) for value in raw_argv if str(value or "").strip()]
    if not clean_argv:
        return clean_executable, [clean_executable]
    return clean_executable, [clean_executable, *clean_argv]


def schedule_backend_restart(
    *,
    delay_seconds: float = 0.45,
    exec_fn: Callable[[str, Sequence[str]], None] = _exec_python_process,
    timer_factory: Callable[[float, Callable[[], None]], threading.Timer] = threading.Timer,
) -> dict[str, object]:
    global _RESTART_SCHEDULED

    clean_delay = max(0.1, min(10.0, float(delay_seconds or 0.45)))
    executable, args = _restart_command()
    if not executable or not args:
        return {
            "ok": False,
            "restart_scheduled": False,
            "state": "unavailable",
            "error": "Python executable could not be determined.",
            "message": "Backend reload is unavailable for this dashboard process.",
            "http_status": 503,
        }

    with _RESTART_LOCK:
        if _RESTART_SCHEDULED:
            return {
                "ok": True,
                "restart_scheduled": True,
                "already_scheduled": True,
                "state": "pending",
                "message": "Backend reload is already scheduled.",
                "http_status": 202,
            }
        _RESTART_SCHEDULED = True

    def _run_restart() -> None:
        global _RESTART_SCHEDULED
        try:
            exec_fn(executable, args)
        except BaseException as exc:
            with _RESTART_LOCK:
                _RESTART_SCHEDULED = False
            print(f"Backend reload failed: {exc}", file=sys.stderr, flush=True)

    try:
        timer = timer_factory(clean_delay, _run_restart)
        timer.daemon = True
        timer.start()
    except Exception as exc:
        with _RESTART_LOCK:
            _RESTART_SCHEDULED = False
        return {
            "ok": False,
            "restart_scheduled": False,
            "state": "error",
            "error": str(exc or "backend reload could not be scheduled"),
            "message": "Backend reload could not be scheduled.",
            "http_status": 500,
        }

    return {
        "ok": True,
        "restart_scheduled": True,
        "state": "pending",
        "delay_seconds": clean_delay,
        "message": "Backend reload scheduled. The dashboard will reconnect shortly.",
        "http_status": 202,
    }
