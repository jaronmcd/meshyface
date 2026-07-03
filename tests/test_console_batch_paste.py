from pathlib import Path


def test_console_batch_paste_runs_multiline_commands() -> None:
    formatting_src = Path(
        "meshdash/assets/dashboard.js.chat.events.console.formatting.tmpl"
    ).read_text(encoding="utf-8")
    interaction_src = Path(
        "meshdash/assets/dashboard.js.chat.events.console.session.interaction.tmpl"
    ).read_text(encoding="utf-8")
    ui_src = Path("meshdash/assets/dashboard.js.chat.events.console.ui.tmpl").read_text(
        encoding="utf-8"
    )

    assert "function normalizeConsoleBatchLines" in formatting_src
    assert "function consoleBatchStripPromptPrefix" in formatting_src
    assert "function consoleBatchLineLooksLikeTranscriptOutput" in formatting_src
    assert "function consoleBatchTextContainsTranscriptOutput" in formatting_src
    assert "function splitConsoleBatchCompoundLine" in formatting_src
    assert "function validateConsoleBatchCommands" in formatting_src
    assert "async function runConsoleCommandBatch" in formatting_src
    assert ".filter((line) => !consoleBatchLineLooksLikeTranscriptOutput(line))" in formatting_src
    assert "[^\\]\\n]{{1,64}}" in formatting_src
    assert "pasted text looks like console help output" in formatting_src
    assert "unknown command in paste" in formatting_src
    assert "allowWhileRunning: true" in formatting_src
    assert "function handleConsolePastedText" in interaction_src
    assert "batchLines.length > 1" in interaction_src
    assert "hasTranscriptPaste" in interaction_src
    assert "batchLines.length > 1 || (hasTranscriptPaste && batchLines.length >= 1)" in interaction_src
    assert "pasted text does not look like a valid command batch" in interaction_src
    assert "void runConsoleCommandBatch(batchLines)" in interaction_src
    assert "handleConsolePastedText(pastedText, input)" in ui_src
