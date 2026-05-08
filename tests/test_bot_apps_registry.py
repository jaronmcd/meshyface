import importlib

import pytest

from meshdash.bot_apps.registry import build_builtin_bot_apps
from meshdash.bot_commands import normalize_bot_command_name


def _app_names(apps: list[object]) -> list[str]:
    out: list[str] = []
    for app in apps:
        spec = getattr(app, "SPEC", None)
        name = normalize_bot_command_name(getattr(spec, "name", ""))
        if name:
            out.append(name)
    return out


def test_build_builtin_bot_apps_includes_internal_zork():
    names = _app_names(build_builtin_bot_apps(env={}))
    assert "zork" in names


def test_build_builtin_bot_apps_loads_external_plugin_modules(tmp_path, monkeypatch):
    module_name = "mesh_plugin_echo"
    module_path = tmp_path / f"{module_name}.py"
    module_path.write_text(
        (
            "from meshdash.bot_apps.base import BotAppResult\n"
            "from meshdash.bot_commands import BotCommandSpec\n"
            "\n"
            "class EchoPlugin:\n"
            "    SPEC = BotCommandSpec(\n"
            "        name='echoext',\n"
            "        usage='echoext',\n"
            "        description='external plugin test command',\n"
            "    )\n"
            "\n"
            "    def active_session_count(self):\n"
            "        return 0\n"
            "\n"
            "    def has_active_session(self, from_id):\n"
            "        return False\n"
            "\n"
            "    def clear_sessions(self):\n"
            "        return None\n"
            "\n"
            "    def try_handle_message(self, **kwargs):\n"
            "        return BotAppResult(handled=False)\n"
            "\n"
            "def build_bot_apps():\n"
            "    return [EchoPlugin()]\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()

    names = _app_names(
        build_builtin_bot_apps(
            env={
                "MESH_DASH_BOT_PLUGIN_MODULES": module_name,
            }
        )
    )
    assert "zork" in names
    assert "echoext" in names


def test_build_builtin_bot_apps_ignores_bad_plugin_modules_by_default():
    names = _app_names(
        build_builtin_bot_apps(
            env={
                "MESH_DASH_BOT_PLUGIN_MODULES": "module_does_not_exist_12345",
            }
        )
    )
    assert "zork" in names


def test_build_builtin_bot_apps_can_strict_fail_on_bad_plugin_modules():
    with pytest.raises(ModuleNotFoundError):
        build_builtin_bot_apps(
            env={
                "MESH_DASH_BOT_PLUGIN_MODULES": "module_does_not_exist_12345",
                "MESH_DASH_BOT_PLUGIN_STRICT": "1",
            }
        )


def test_build_builtin_bot_apps_skips_underscore_template_modules():
    names = _app_names(build_builtin_bot_apps(env={}))
    assert "echo" not in names
