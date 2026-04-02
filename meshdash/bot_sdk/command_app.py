"""Lightweight SDK helpers for external bot command plugins.

This module intentionally wraps the lower-level ``BotApp`` protocol with a
friendlier "single command handler" surface so contributors do not need to
re-implement session plumbing for simple bots.
"""

from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from ..bot_apps.base import BotAppResult
from ..bot_commands import BotCommandSpec, normalize_bot_command_name


def _canonical_head(token: object) -> str:
    """Normalize command heads to a shared canonical form.

    We accept common bot command prefixes (``/``, ``!``, ``#``) so plugin
    commands can match the same user input style used by built-in commands.
    """

    text = str(token or "").strip().lower()
    if not text:
        return ""
    if text.startswith("/"):
        text = text[1:]
    return normalize_bot_command_name(text)


def _parse_command_head_and_args(text: object) -> tuple[str, tuple[str, ...]] | None:
    """Parse incoming text into ``(command_head, args)``.

    Returns ``None`` when no command-like token is present.
    """

    raw = str(text or "").strip()
    if not raw:
        return None
    parts = [part for part in raw.split() if part]
    if not parts:
        return None
    head = _canonical_head(parts[0])
    if not head:
        return None
    return (head, tuple(str(part) for part in parts[1:]))


@dataclass(frozen=True)
class CommandInvocation:
    """Normalized request payload delivered to SDK command handlers.

    Keeping this payload explicit and immutable makes plugins easier to test and
    helps avoid accidental mutation of runtime request state.
    """

    raw_text: str
    command: str
    args: tuple[str, ...]
    from_id: str
    to_id: str
    local_node_id: str
    now_unix: int
    enabled: bool


CommandHandler = Callable[[CommandInvocation], str | BotAppResult | None]


class CommandApp:
    """Adapter that turns a simple command callback into a ``BotApp``.

    Why this exists:
    - Plugin authors often want one command with minimal boilerplate.
    - ``BotApp`` requires session methods even for stateless commands.
    - This adapter provides stable defaults (no sessions) and a tiny API.

    Usage pattern:
    1. Define a ``BotCommandSpec``.
    2. Provide a ``handler(invocation)`` callback.
    3. Return ``CommandApp(...)`` from your plugin module's ``build_bot_apps()``.
    """

    def __init__(
        self,
        *,
        spec: BotCommandSpec,
        handler: CommandHandler,
        aliases: Iterable[str] = (),
        require_direct_to_local: bool = False,
    ) -> None:
        self.SPEC = spec
        self._handler = handler
        self._require_direct_to_local = bool(require_direct_to_local)
        accepted = {_canonical_head(spec.name)}
        accepted.update(_canonical_head(value) for value in aliases)
        self._accepted_heads = {value for value in accepted if value}

    def active_session_count(self) -> int:
        # Stateless command apps never hold conversational session state.
        return 0

    def has_active_session(self, from_id: str) -> bool:
        del from_id
        return False

    def clear_sessions(self) -> None:
        # Stateless command apps have nothing to clear.
        return None

    def _command_matches(self, text: str) -> tuple[str, tuple[str, ...]] | None:
        parsed = _parse_command_head_and_args(text)
        if parsed is None:
            return None
        command, args = parsed
        if command not in self._accepted_heads:
            return None
        return (command, args)

    def try_handle_message(
        self,
        *,
        text: str,
        from_id: str,
        to_id: str,
        local_node_id: str,
        now_unix: int,
        enabled: bool,
    ) -> BotAppResult:
        matched = self._command_matches(text)
        if matched is None:
            return BotAppResult(handled=False)
        command, args = matched

        # Optional guardrail: command only fires when addressed directly.
        if self._require_direct_to_local:
            if str(to_id or "").strip().lower() != str(local_node_id or "").strip().lower():
                return BotAppResult(handled=False)

        if not enabled:
            return BotAppResult(
                handled=True,
                command_name=self.SPEC.name,
                command_args=args,
            )

        invocation = CommandInvocation(
            raw_text=str(text or ""),
            command=command,
            args=args,
            from_id=str(from_id or ""),
            to_id=str(to_id or ""),
            local_node_id=str(local_node_id or ""),
            now_unix=int(now_unix),
            enabled=bool(enabled),
        )
        result = self._handler(invocation)
        if isinstance(result, BotAppResult):
            if result.command_name:
                return result
            return BotAppResult(
                handled=result.handled,
                reply_text=result.reply_text,
                command_name=self.SPEC.name,
                command_args=result.command_args or args,
            )
        if result is None:
            return BotAppResult(
                handled=True,
                command_name=self.SPEC.name,
                command_args=args,
            )
        return BotAppResult(
            handled=True,
            reply_text=str(result),
            command_name=self.SPEC.name,
            command_args=args,
        )


__all__ = [
    "CommandApp",
    "CommandHandler",
    "CommandInvocation",
]
