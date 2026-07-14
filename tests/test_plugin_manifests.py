from __future__ import annotations

from pathlib import Path

import pytest

from meshdash.plugins import Script
from meshdash.plugins.manifest import (
    PluginDefinitionError,
    DuplicatePluginIdError,
    ManifestError,
    discover_plugins,
    parse_manifest,
    validate_script_against_manifest,
)


def _write_plugin(
    root: Path,
    directory_name: str,
    *,
    plugin_id: str | None = None,
    name: str = "Example",
    version: str = "1.0.0",
    entrypoint: str = "script.py:script",
    commands: tuple[str, ...] = ("hello",),
    default_enabled: bool = False,
    python_source: str = "this is deliberately not valid Python",
    extra_toml: str = "",
) -> Path:
    plugin = root / directory_name
    plugin.mkdir(parents=True)
    (plugin / "script.py").write_text(python_source, encoding="utf-8")
    command_list = ", ".join(f'"{command}"' for command in commands)
    declared_id = plugin_id if plugin_id is not None else directory_name
    (plugin / "plugin.toml").write_text(
        "\n".join(
            [
                "api_version = 1",
                f'id = "{declared_id}"',
                f'name = "{name}"',
                f'version = "{version}"',
                f'entrypoint = "{entrypoint}"',
                f"commands = [{command_list}]",
                f"default_enabled = {'true' if default_enabled else 'false'}",
                extra_toml,
            ]
        ),
        encoding="utf-8",
    )
    return plugin


def test_parse_valid_manifest_resolves_entrypoint_without_importing(tmp_path: Path) -> None:
    plugin = _write_plugin(tmp_path, "example", default_enabled=True)

    manifest = parse_manifest(plugin / "plugin.toml", source="included")

    assert manifest.api_version == 1
    assert manifest.id == "example"
    assert manifest.name == "Example"
    assert manifest.version == "1.0.0"
    assert manifest.entrypoint == "script.py:script"
    assert manifest.commands == ("hello",)
    assert manifest.default_enabled is True
    assert manifest.manifest_path == (plugin / "plugin.toml").resolve()
    assert manifest.plugin_directory == plugin.resolve()
    assert manifest.entrypoint_path == (plugin / "script.py").resolve()
    assert manifest.entrypoint_object == "script"
    assert manifest.source == "included"


def test_manifest_declares_and_normalizes_typed_settings(tmp_path: Path) -> None:
    plugin = _write_plugin(
        tmp_path,
        "configured",
        extra_toml="""
[[settings]]
key = "greeting"
label = "Greeting"
type = "text"
default = "hello"
placeholder = "Type a greeting"
max_length = 20

[[settings]]
key = "enabled"
label = "Enabled"
type = "boolean"
default = true

[[settings]]
key = "limit"
label = "Limit"
type = "integer"
default = 3
minimum = 1
maximum = 10

[[settings]]
key = "allowed_nodes"
label = "Allowed nodes"
type = "node_ids"
default = ["!AABBCCDD", "!aabbccdd", "!01020304"]
""",
    )

    manifest = parse_manifest(plugin / "plugin.toml")

    assert [definition.type for definition in manifest.settings] == [
        "text",
        "boolean",
        "integer",
        "node_ids",
    ]
    assert manifest.settings[0].max_length == 20
    assert manifest.settings[2].minimum == 1
    assert manifest.settings[2].maximum == 10
    assert manifest.settings[3].default == ("!aabbccdd", "!01020304")


@pytest.mark.parametrize(
    ("setting_toml", "message"),
    [
        (
            'key = "Bad Key"\nlabel = "Bad"\ntype = "text"\ndefault = "x"',
            "key must match",
        ),
        (
            'key = "flag"\nlabel = "Flag"\ntype = "boolean"\ndefault = "yes"',
            "must be a boolean",
        ),
        (
            'key = "limit"\nlabel = "Limit"\ntype = "integer"\ndefault = 0\nminimum = 1',
            "must be at least 1",
        ),
        (
            'key = "nodes"\nlabel = "Nodes"\ntype = "node_ids"\ndefault = ["bad"]',
            "must match !00000000",
        ),
    ],
)
def test_manifest_rejects_invalid_setting_definitions(
    tmp_path: Path,
    setting_toml: str,
    message: str,
) -> None:
    plugin = _write_plugin(
        tmp_path,
        "configured",
        extra_toml=f"[[settings]]\n{setting_toml}",
    )

    with pytest.raises(ManifestError, match=message):
        parse_manifest(plugin / "plugin.toml")


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ("api_version = true", "api_version must be an integer"),
        ("api_version = 2", "unsupported api_version"),
        ('id = "Bad ID"', "id must match"),
        ('commands = "hello"', "commands must be an array"),
        ('commands = ["Hello"]', r"commands\[0\] must match"),
        ('commands = ["hello", "hello"]', "duplicate command"),
        ('default_enabled = "false"', "default_enabled must be a boolean"),
        ('entrypoint = "script.py"', "entrypoint must use"),
        ('entrypoint = "/tmp/script.py:script"', "entrypoint must stay"),
        ('entrypoint = "../script.py:script"', "entrypoint must stay"),
    ],
)
def test_parse_manifest_rejects_invalid_values(
    tmp_path: Path,
    replacement: str,
    message: str,
) -> None:
    plugin = _write_plugin(tmp_path, "example")
    manifest_path = plugin / "plugin.toml"
    lines = manifest_path.read_text(encoding="utf-8").splitlines()
    key = replacement.split("=", 1)[0].strip()
    manifest_path.write_text(
        "\n".join(replacement if line.startswith(f"{key} =") else line for line in lines),
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match=message):
        parse_manifest(manifest_path)


def test_parse_manifest_rejects_missing_unknown_and_malformed_fields(tmp_path: Path) -> None:
    plugin = _write_plugin(tmp_path, "example")
    manifest_path = plugin / "plugin.toml"
    contents = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(contents.replace('name = "Example"\n', ""), encoding="utf-8")
    with pytest.raises(ManifestError, match="missing fields: name"):
        parse_manifest(manifest_path)

    plugin = _write_plugin(tmp_path, "unknown", extra_toml='typo_enabled = true')
    with pytest.raises(ManifestError, match="unknown fields: typo_enabled"):
        parse_manifest(plugin / "plugin.toml")

    (plugin / "plugin.toml").write_text("not = [valid", encoding="utf-8")
    with pytest.raises(ManifestError, match="invalid TOML"):
        parse_manifest(plugin / "plugin.toml")


def test_parse_manifest_rejects_entrypoint_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside.py"
    outside.write_text("script = None", encoding="utf-8")
    plugin = _write_plugin(tmp_path, "example", entrypoint="linked.py:script")
    (plugin / "linked.py").symlink_to(outside)

    with pytest.raises(ManifestError, match="must stay inside"):
        parse_manifest(plugin / "plugin.toml")


def test_discovery_is_deterministic_and_does_not_import_python(tmp_path: Path) -> None:
    included = tmp_path / "included"
    local = tmp_path / "local"
    _write_plugin(included, "zeta")
    _write_plugin(included, "alpha")
    _write_plugin(local, "middle")
    (local / "not-a-plugin").mkdir(parents=True)
    (local / "README.txt").write_text("ignored", encoding="utf-8")

    manifests = discover_plugins(included, local)

    assert [manifest.id for manifest in manifests] == ["alpha", "zeta", "middle"]
    assert [manifest.source for manifest in manifests] == ["included", "included", "local"]


def test_discovery_ignores_missing_roots_and_rejects_non_directory(tmp_path: Path) -> None:
    assert discover_plugins(tmp_path / "missing-included", tmp_path / "missing-local") == ()
    not_a_directory = tmp_path / "plugins.txt"
    not_a_directory.write_text("no", encoding="utf-8")
    with pytest.raises(ManifestError, match="not a directory"):
        discover_plugins(not_a_directory, None)


def test_discovery_rejects_duplicate_ids_with_both_paths(tmp_path: Path) -> None:
    included = tmp_path / "included"
    local = tmp_path / "local"
    first = _write_plugin(included, "first", plugin_id="duplicate")
    second = _write_plugin(local, "second", plugin_id="duplicate")

    with pytest.raises(DuplicatePluginIdError) as exc_info:
        discover_plugins(included, local)

    message = str(exc_info.value)
    assert "duplicate plugin id 'duplicate'" in message
    assert str((first / "plugin.toml").resolve()) in message
    assert str((second / "plugin.toml").resolve()) in message


def test_worker_validation_enforces_authoritative_manifest_metadata(tmp_path: Path) -> None:
    plugin = _write_plugin(tmp_path, "example", commands=("hello", "status"))
    manifest = parse_manifest(plugin / "plugin.toml")
    script = Script(id="example", name="Example", version="1.0.0")

    @script.command("hello")
    def hello(ctx: object) -> None:
        return None

    with pytest.raises(PluginDefinitionError, match="missing command handlers: status"):
        validate_script_against_manifest(manifest, script)

    @script.command("status")
    def status(ctx: object) -> None:
        return None

    assert validate_script_against_manifest(manifest, script) is script


def test_worker_validation_rejects_wrong_entrypoint_type_and_metadata(tmp_path: Path) -> None:
    plugin = _write_plugin(tmp_path, "example")
    manifest = parse_manifest(plugin / "plugin.toml")
    with pytest.raises(PluginDefinitionError, match="did not resolve to Script"):
        validate_script_against_manifest(manifest, object())

    script = Script(id="other", name="Other", version="2")

    @script.command("extra")
    def extra(ctx: object) -> None:
        return None

    with pytest.raises(PluginDefinitionError) as exc_info:
        validate_script_against_manifest(manifest, script)
    assert "id is 'other'" in str(exc_info.value)
    assert "name is 'Other'" in str(exc_info.value)
    assert "version is '2'" in str(exc_info.value)
    assert "missing command handlers: hello" in str(exc_info.value)
    assert "undeclared command handlers: extra" in str(exc_info.value)
