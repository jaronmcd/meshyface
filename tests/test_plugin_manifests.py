from __future__ import annotations

import os
from pathlib import Path

import pytest

from meshdash.plugins import Script
from meshdash.plugins.manifest import (
    MAX_DISCOVERED_PLUGINS,
    MAX_MANIFEST_BYTES,
    MAX_PLUGIN_COMMANDS,
    PluginDefinitionError,
    DuplicatePluginIdError,
    ManifestError,
    discover_plugins,
    parse_manifest,
    validate_script_against_manifest,
)
from meshdash.plugin_worker import _load_script


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
    assert manifest.effective_default_enabled is True
    assert manifest.package_digest.startswith("sha256:")
    assert len(manifest.package_digest) == 71


def test_local_package_cannot_self_enable_from_its_manifest(tmp_path: Path) -> None:
    plugin = _write_plugin(tmp_path, "example", default_enabled=True)

    local = parse_manifest(plugin / "plugin.toml", source="local")
    included = parse_manifest(plugin / "plugin.toml", source="included")

    assert local.default_enabled is True
    assert local.effective_default_enabled is False
    assert included.effective_default_enabled is True


def test_package_digest_covers_non_entrypoint_files_deterministically(tmp_path: Path) -> None:
    plugin = _write_plugin(tmp_path, "example")
    extra = plugin / "README.md"
    extra.write_text("package notes", encoding="utf-8")

    first = parse_manifest(plugin / "plugin.toml").package_digest
    assert parse_manifest(plugin / "plugin.toml").package_digest == first

    extra.write_text("changed package notes", encoding="utf-8")
    second = parse_manifest(plugin / "plugin.toml").package_digest
    assert second != first


def test_package_digest_ignores_common_local_development_metadata(tmp_path: Path) -> None:
    plugin = _write_plugin(tmp_path, "example")
    baseline = parse_manifest(plugin / "plugin.toml").package_digest
    git_dir = plugin / ".git"
    cache_dir = plugin / "__pycache__"
    pytest_cache = plugin / ".pytest_cache"
    git_dir.mkdir()
    cache_dir.mkdir()
    pytest_cache.mkdir()
    (git_dir / "index").write_bytes(b"changing checkout metadata")
    (cache_dir / "script.cpython-313.pyc").write_bytes(b"changing bytecode cache")
    (pytest_cache / "README.md").write_text("changing test cache", encoding="utf-8")
    (plugin / ".coverage").write_bytes(b"changing coverage data")

    assert parse_manifest(plugin / "plugin.toml").package_digest == baseline

    (plugin / "script.py").write_text("changed = True\n", encoding="utf-8")
    assert parse_manifest(plugin / "plugin.toml").package_digest != baseline


@pytest.mark.skipif(os.name != "posix", reason="surrogate-escaped filenames are POSIX-specific")
def test_package_digest_handles_non_utf8_filename(tmp_path: Path) -> None:
    plugin = _write_plugin(tmp_path, "example")
    non_utf8_name = os.fsdecode(b"package-\xff.dat")
    (plugin / non_utf8_name).write_bytes(b"package data")

    manifest = parse_manifest(plugin / "plugin.toml")

    assert manifest.package_digest.startswith("sha256:")


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


def test_discovery_isolates_entrypoint_symlink_loop(tmp_path: Path) -> None:
    root = tmp_path / "plugins"
    plugin = _write_plugin(root, "looped", entrypoint="loop.py:script")
    (plugin / "loop.py").symlink_to("loop.py")
    errors: list[ManifestError] = []

    assert discover_plugins(None, root, on_error=errors.append) == ()
    assert any("entrypoint path cannot be resolved" in str(error) for error in errors)


def test_parse_manifest_rejects_any_package_symlink(tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    plugin = _write_plugin(tmp_path / "plugins", "example")
    (plugin / "linked-data.txt").symlink_to(outside)

    with pytest.raises(ManifestError, match="package symlinks are not allowed"):
        parse_manifest(plugin / "plugin.toml")


def test_parse_manifest_rejects_world_writable_package_code(
    tmp_path: Path,
) -> None:
    plugin = _write_plugin(tmp_path, "example")
    script_path = plugin / "script.py"
    script_path.chmod(0o666)

    with pytest.raises(ManifestError, match="must not be world-writable"):
        parse_manifest(plugin / "plugin.toml")


def test_manifest_and_package_directory_symlinks_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "plugins"
    target = _write_plugin(tmp_path / "targets", "example")
    root.mkdir()
    (root / "linked-package").symlink_to(target, target_is_directory=True)

    with pytest.raises(ManifestError, match="package directory must not be a symlink"):
        discover_plugins(None, root)

    package = _write_plugin(root, "direct")
    contents = (package / "plugin.toml").read_text(encoding="utf-8")
    (package / "plugin.toml").unlink()
    outside_manifest = tmp_path / "outside-plugin.toml"
    outside_manifest.write_text(contents, encoding="utf-8")
    (package / "plugin.toml").symlink_to(outside_manifest)

    errors: list[ManifestError] = []
    assert discover_plugins(None, root, on_error=errors.append) == ()
    assert any("plugin manifest must not be a symlink" in str(error) for error in errors)


def test_discovery_isolates_malformed_and_duplicate_packages_when_requested(
    tmp_path: Path,
) -> None:
    root = tmp_path / "plugins"
    _write_plugin(root, "healthy")
    malformed = _write_plugin(root, "malformed")
    (malformed / "plugin.toml").write_text("not = [valid", encoding="utf-8")
    _write_plugin(root, "duplicate", plugin_id="healthy")
    errors: list[ManifestError] = []

    manifests = discover_plugins(None, root, on_error=errors.append)

    assert [manifest.id for manifest in manifests] == ["healthy"]
    assert len(errors) == 2
    assert any("invalid TOML" in str(error) for error in errors)
    assert any(isinstance(error, DuplicatePluginIdError) for error in errors)


def test_discovery_bounds_total_candidate_packages(tmp_path: Path) -> None:
    root = tmp_path / "plugins"
    for index in range(MAX_DISCOVERED_PLUGINS + 1):
        _write_plugin(root, f"plugin{index:02d}")

    with pytest.raises(ManifestError, match="plugin packages may be inspected"):
        discover_plugins(None, root)


def test_manifest_and_command_metadata_limits_are_enforced(tmp_path: Path) -> None:
    plugin = _write_plugin(tmp_path, "oversized")
    manifest_path = plugin / "plugin.toml"
    manifest_path.write_bytes(b"#" * (MAX_MANIFEST_BYTES + 1))
    with pytest.raises(ManifestError, match="manifest exceeds"):
        parse_manifest(manifest_path)

    commands = tuple(f"c{index}" for index in range(MAX_PLUGIN_COMMANDS + 1))
    plugin = _write_plugin(tmp_path, "commands", commands=commands)
    with pytest.raises(ManifestError, match="commands may contain at most"):
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


def test_worker_rejects_package_changed_after_discovery(tmp_path: Path) -> None:
    plugin = _write_plugin(
        tmp_path,
        "example",
        python_source="""
from meshdash.plugins import Script
script = Script(id="example", name="Example", version="1.0.0")
@script.command("hello")
def hello(ctx):
    return None
""",
    )
    manifest = parse_manifest(plugin / "plugin.toml")
    (plugin / "new-code.py").write_text("changed = True\n", encoding="utf-8")

    with pytest.raises(ImportError, match="package changed after discovery"):
        _load_script(manifest)


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
