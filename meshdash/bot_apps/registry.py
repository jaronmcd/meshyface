from .base import BotApp
from .internal import build_internal_bot_apps
from .plugins import load_external_bot_apps
from ..bot_commands import normalize_bot_command_name


def build_builtin_bot_apps(*, env: dict[str, str] | None = None) -> list[BotApp]:
    # Zork remains internal/core; non-core bot apps can load from plugin modules.
    raw_apps = [
        *build_internal_bot_apps(),
        *load_external_bot_apps(env=env),
    ]
    out: list[BotApp] = []
    seen_names: set[str] = set()
    for app in raw_apps:
        name = normalize_bot_command_name(getattr(getattr(app, "SPEC", None), "name", ""))
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        out.append(app)
    return out


__all__ = ["build_builtin_bot_apps"]
