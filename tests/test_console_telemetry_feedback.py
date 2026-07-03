from pathlib import Path


def test_console_telemetry_command_emits_wait_feedback() -> None:
    src = Path(
        "meshdash/assets/dashboard.js.chat.events.console.commands.helpers.tmpl"
    ).read_text(encoding="utf-8")

    assert "function startConsoleTelemetryWaitFeedback" in src
    assert "request sent" in src
    assert "waiting up to" in src
    assert "still waiting" in src
    assert "const stopWaitFeedback = startConsoleTelemetryWaitFeedback(" in src
    assert "stopWaitFeedback();" in src
