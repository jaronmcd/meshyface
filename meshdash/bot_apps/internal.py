from .base import BotApp
from ..games.zork.engine import ZorkGame


def build_internal_bot_apps() -> list[BotApp]:
    # Keep Zork internal/core while other bot apps migrate to plugins.
    return [ZorkGame()]


__all__ = ["build_internal_bot_apps"]
