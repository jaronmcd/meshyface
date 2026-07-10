from __future__ import annotations

import os
import sys

import pytest

from meshdash import api_system_restart
from meshdash.api_system_restart import (
    _exec_python_process,
    _restart_command,
    schedule_backend_restart,
)


@pytest.fixture(autouse=True)
def _reset_restart_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_system_restart, "_RESTART_SCHEDULED", False)


class _FakeTimer:
    def __init__(self, delay: float, callback) -> None:
        self.delay = delay
        self.callback = callback
        self.daemon = False
        self.started = False

    def start(self) -> None:
        self.started = True


def test_exec_python_process_uses_execv(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(os, "execv", lambda executable, args: calls.append((executable, args)))

    _exec_python_process("/usr/bin/python3", ("/usr/bin/python3", "app.py"))

    assert calls == [("/usr/bin/python3", ["/usr/bin/python3", "app.py"])]


def test_restart_command_prepends_executable_and_filters_blank_args() -> None:
    executable, args = _restart_command(
        executable="/usr/bin/python3",
        argv=["app.py", "", None, "--flag"],
    )
    assert executable == "/usr/bin/python3"
    assert args == ["/usr/bin/python3", "app.py", "--flag"]


def test_restart_command_without_argv_still_returns_executable() -> None:
    assert _restart_command(executable="/usr/bin/python3", argv=[]) == (
        "/usr/bin/python3",
        ["/usr/bin/python3"],
    )
    assert _restart_command(executable="/usr/bin/python3", argv=["", None]) == (
        "/usr/bin/python3",
        ["/usr/bin/python3"],
    )


def test_restart_command_without_executable_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "executable", "")
    assert _restart_command(executable="   ", argv=["app.py"]) == ("", [])


def test_schedule_restart_unavailable_without_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "executable", "")

    payload = schedule_backend_restart(timer_factory=_FakeTimer)

    assert payload["ok"] is False
    assert payload["restart_scheduled"] is False
    assert payload["state"] == "unavailable"
    assert payload["http_status"] == 503


def test_schedule_restart_starts_daemon_timer_and_dedupes() -> None:
    timers: list[_FakeTimer] = []

    def _factory(delay: float, callback) -> _FakeTimer:
        timer = _FakeTimer(delay, callback)
        timers.append(timer)
        return timer

    payload = schedule_backend_restart(delay_seconds=0.2, timer_factory=_factory)

    assert payload["ok"] is True
    assert payload["restart_scheduled"] is True
    assert payload["state"] == "pending"
    assert payload["delay_seconds"] == pytest.approx(0.2)
    assert payload["http_status"] == 202
    assert len(timers) == 1
    assert timers[0].daemon is True
    assert timers[0].started is True

    repeat = schedule_backend_restart(timer_factory=_factory)
    assert repeat["ok"] is True
    assert repeat["already_scheduled"] is True
    assert repeat["state"] == "pending"
    assert len(timers) == 1


def test_schedule_restart_clamps_delay() -> None:
    payload = schedule_backend_restart(delay_seconds=99.0, timer_factory=_FakeTimer)
    assert payload["delay_seconds"] == pytest.approx(10.0)


def test_schedule_restart_zero_delay_falls_back_to_default() -> None:
    payload = schedule_backend_restart(delay_seconds=0, timer_factory=_FakeTimer)
    assert payload["delay_seconds"] == pytest.approx(0.45)


def test_schedule_restart_minimum_delay_floor() -> None:
    payload = schedule_backend_restart(delay_seconds=0.01, timer_factory=_FakeTimer)
    assert payload["delay_seconds"] == pytest.approx(0.1)


def test_run_restart_callback_invokes_exec_fn() -> None:
    timers: list[_FakeTimer] = []
    calls: list[tuple[str, list[str]]] = []

    def _factory(delay: float, callback) -> _FakeTimer:
        timer = _FakeTimer(delay, callback)
        timers.append(timer)
        return timer

    payload = schedule_backend_restart(
        exec_fn=lambda executable, args: calls.append((executable, list(args))),
        timer_factory=_factory,
    )
    assert payload["ok"] is True

    timers[0].callback()

    assert len(calls) == 1
    executable, args = calls[0]
    assert executable == sys.executable
    assert args[0] == sys.executable


def test_run_restart_failure_resets_flag_and_logs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    timers: list[_FakeTimer] = []

    def _factory(delay: float, callback) -> _FakeTimer:
        timer = _FakeTimer(delay, callback)
        timers.append(timer)
        return timer

    def _failing_exec(executable: str, args) -> None:
        raise OSError("exec blocked")

    payload = schedule_backend_restart(exec_fn=_failing_exec, timer_factory=_factory)
    assert payload["ok"] is True

    timers[0].callback()

    assert "exec blocked" in capsys.readouterr().err
    retry = schedule_backend_restart(timer_factory=_factory)
    assert retry.get("already_scheduled") is None
    assert retry["restart_scheduled"] is True


def test_schedule_restart_timer_failure_returns_error_and_resets_flag() -> None:
    def _broken_factory(delay: float, callback) -> _FakeTimer:
        raise RuntimeError("no timers today")

    payload = schedule_backend_restart(timer_factory=_broken_factory)

    assert payload["ok"] is False
    assert payload["state"] == "error"
    assert payload["http_status"] == 500
    assert "no timers today" in str(payload["error"])

    retry = schedule_backend_restart(timer_factory=_FakeTimer)
    assert retry["ok"] is True
    assert retry.get("already_scheduled") is None
