"""Public SDK helpers for plugin authors.

This package is intentionally small and stable:
- ``CommandApp``: easiest path to create a new stateless command bot.
- ``CommandInvocation``: normalized request payload for handlers.
"""

from .command_app import CommandApp, CommandHandler, CommandInvocation

__all__ = [
    "CommandApp",
    "CommandHandler",
    "CommandInvocation",
]
