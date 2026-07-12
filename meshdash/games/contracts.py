from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class GameResult:
    handled: bool
    reply_text: Optional[str] = None
    command_name: str = ""
    command_args: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class GameCommandSpec:
    name: str
    usage: str
    description: str
    kind: str = "builtin"


__all__ = ["GameCommandSpec", "GameResult"]
