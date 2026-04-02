import importlib
import os
import pkgutil
from types import ModuleType
from typing import Iterable, Optional

from .base import BotApp
from ..bot_commands import normalize_bot_command_name

_DEFAULT_PLUGIN_NAMESPACE = "meshdash.bot_plugins"
_BOT_PLUGIN_MODULES_ENV = "MESH_DASH_BOT_PLUGIN_MODULES"
_BOT_PLUGIN_STRICT_ENV = "MESH_DASH_BOT_PLUGIN_STRICT"


def _parse_bool_token(value: object, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value == 1:
            return True
        if value == 0:
            return False
    text = str(value).strip().lower()
    if not text:
        return bool(default)
    if text in ("1", "true", "yes", "on", "enable", "enabled"):
        return True
    if text in ("0", "false", "no", "off", "disable", "disabled"):
        return False
    return bool(default)


def _normalize_plugin_module_names(raw: object) -> list[str]:
    text = str(raw or "").strip()
    if not text:
        return []
    normalized = text.replace(";", "\n").replace(",", "\n")
    out: list[str] = []
    seen: set[str] = set()
    for part in normalized.splitlines():
        name = str(part or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _discover_namespace_modules(namespace: str) -> list[str]:
    clean = str(namespace or "").strip()
    if not clean:
        return []
    try:
        package = importlib.import_module(clean)
    except Exception:
        return []
    package_path = getattr(package, "__path__", None)
    if not package_path:
        return []
    out: list[str] = []
    for module_info in pkgutil.iter_modules(package_path):
        # Treat underscore-prefixed modules as templates/private helpers.
        if str(module_info.name).startswith("_"):
            continue
        out.append(f"{clean}.{module_info.name}")
    return sorted(out)


def _load_module(module_name: str, *, strict: bool) -> Optional[ModuleType]:
    try:
        return importlib.import_module(module_name)
    except Exception:
        if strict:
            raise
        return None


def _coerce_plugin_apps(raw: object) -> list[BotApp]:
    if raw is None:
        return []
    if isinstance(raw, (str, bytes)):
        return []
    if isinstance(raw, Iterable):
        items = list(raw)
    else:
        return []
    out: list[BotApp] = []
    for item in items:
        app = item
        if isinstance(app, type):
            try:
                app = app()
            except Exception:
                continue
        spec = getattr(app, "SPEC", None)
        name = normalize_bot_command_name(getattr(spec, "name", ""))
        if not name:
            continue
        out.append(app)
    return out


def _load_apps_from_module(module: ModuleType, *, strict: bool) -> list[BotApp]:
    builder = getattr(module, "build_bot_apps", None)
    if callable(builder):
        try:
            return _coerce_plugin_apps(builder())
        except Exception:
            if strict:
                raise
            return []
    return _coerce_plugin_apps(getattr(module, "BOT_APPS", None))


def load_external_bot_apps(*, env: Optional[dict[str, str]] = None) -> list[BotApp]:
    env_map = env if isinstance(env, dict) else dict(os.environ)
    strict = _parse_bool_token(env_map.get(_BOT_PLUGIN_STRICT_ENV), False)
    discovered = _discover_namespace_modules(_DEFAULT_PLUGIN_NAMESPACE)
    configured = _normalize_plugin_module_names(env_map.get(_BOT_PLUGIN_MODULES_ENV))
    module_names: list[str] = []
    seen_modules: set[str] = set()
    for module_name in [*discovered, *configured]:
        if module_name in seen_modules:
            continue
        seen_modules.add(module_name)
        module_names.append(module_name)

    out: list[BotApp] = []
    for module_name in module_names:
        module = _load_module(module_name, strict=strict)
        if module is None:
            continue
        out.extend(_load_apps_from_module(module, strict=strict))
    return out


__all__ = ["load_external_bot_apps"]
