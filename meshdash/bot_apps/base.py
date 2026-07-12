from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class BotAppResult:
    handled: bool
    reply_text: Optional[str] = None
    command_name: str = ""
    command_args: tuple[str, ...] = field(default_factory=tuple)


__all__ = ["BotAppResult"]
