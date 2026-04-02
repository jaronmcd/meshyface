"""Template plugin module for new bot commands.

This file is intentionally underscore-prefixed so the auto-loader ignores it.
Copy it to a non-underscore module name (for example ``echo_tools.py``) to
activate it.
"""

from meshdash.bot_commands import BotCommandSpec
from meshdash.bot_sdk import CommandApp, CommandInvocation


def _handle_echo(invocation: CommandInvocation) -> str:
    # Friendly usage message keeps first-run UX obvious for contributors.
    if not invocation.args:
        return "echo: usage echo <text>"

    # SDK invocations already provide normalized command + args. We can focus on
    # command behavior and avoid packet/session plumbing here.
    message = " ".join(invocation.args).strip()
    return f"echo: {message}"


def build_bot_apps() -> list[CommandApp]:
    # ``CommandApp`` wraps a simple callback into the full BotApp protocol.
    # Aliases are optional; these heads resolve after common prefix cleanup.
    return [
        CommandApp(
            spec=BotCommandSpec(
                name="echo",
                usage="echo <text>",
                description="repeat text back to the sender",
            ),
            handler=_handle_echo,
            aliases=("say",),
        )
    ]

