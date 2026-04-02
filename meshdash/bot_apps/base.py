from dataclasses import dataclass, field
from typing import Optional, Protocol

from ..bot_commands import BotCommandSpec


@dataclass(frozen=True)
class BotAppResult:
    handled: bool
    reply_text: Optional[str] = None
    command_name: str = ""
    command_args: tuple[str, ...] = field(default_factory=tuple)


class BotApp(Protocol):
    SPEC: BotCommandSpec

    def active_session_count(self) -> int: ...

    def has_active_session(self, from_id: str) -> bool: ...

    def clear_sessions(self) -> None: ...

    def try_handle_message(
        self,
        *,
        text: str,
        from_id: str,
        to_id: str,
        local_node_id: str,
        now_unix: int,
        enabled: bool,
    ) -> BotAppResult: ...


__all__ = ["BotApp", "BotAppResult"]
