from dataclasses import dataclass


@dataclass(frozen=True)
class BotCommandSpec:
    name: str
    usage: str
    description: str
    kind: str = "builtin"


__all__ = ["BotCommandSpec"]
