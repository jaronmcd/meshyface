"""Strict, import-free manifest parsing and plugin discovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tomllib
from typing import Literal, Mapping

from .sdk import Script


SUPPORTED_API_VERSION = 1
_PLUGIN_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
_COMMAND_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
_REQUIRED_FIELDS = {
    "api_version",
    "id",
    "name",
    "version",
    "entrypoint",
    "commands",
    "default_enabled",
}
PluginSource = Literal["included", "local"]


class ManifestError(ValueError):
    """A plugin manifest or discovery directory is invalid."""


class DuplicatePluginIdError(ManifestError):
    """Two discovered manifests declare the same plugin ID."""


class PluginDefinitionError(ValueError):
    """An imported worker entrypoint disagrees with its manifest."""


@dataclass(frozen=True, slots=True)
class PluginManifest:
    api_version: int
    id: str
    name: str
    version: str
    entrypoint: str
    commands: tuple[str, ...]
    default_enabled: bool
    manifest_path: Path
    plugin_directory: Path
    entrypoint_path: Path
    entrypoint_object: str
    source: PluginSource


def parse_manifest(
    manifest_path: str | Path,
    *,
    source: PluginSource = "local",
) -> PluginManifest:
    """Parse one ``plugin.toml`` without loading its Python entrypoint.

    Unknown fields are rejected so misspelled configuration cannot silently
    change runtime behavior.  The returned paths are absolute and resolved.
    """

    path = Path(manifest_path)
    if path.name != "plugin.toml":
        raise ManifestError(f"{path}: manifest must be named plugin.toml")
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise ManifestError(f"{path}: manifest does not exist") from exc
    except OSError as exc:
        raise ManifestError(f"{path}: cannot read manifest: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"{path}: invalid TOML: {exc}") from exc

    if source not in ("included", "local"):
        raise ManifestError(f"{path}: source must be 'included' or 'local'")
    _validate_fields(path, raw)

    api_version = raw["api_version"]
    if isinstance(api_version, bool) or not isinstance(api_version, int):
        raise ManifestError(f"{path}: api_version must be an integer")
    if api_version != SUPPORTED_API_VERSION:
        raise ManifestError(
            f"{path}: unsupported api_version {api_version}; "
            f"expected {SUPPORTED_API_VERSION}"
        )

    plugin_id = _manifest_string(path, raw, "id", maximum=64)
    if _PLUGIN_ID_RE.fullmatch(plugin_id) is None:
        raise ManifestError(f"{path}: id must match [a-z][a-z0-9_-]{{0,63}}")
    name = _manifest_string(path, raw, "name", maximum=128)
    version = _manifest_string(path, raw, "version", maximum=64)
    entrypoint = _manifest_string(path, raw, "entrypoint")
    commands = _manifest_commands(path, raw["commands"])
    default_enabled = raw["default_enabled"]
    if not isinstance(default_enabled, bool):
        raise ManifestError(f"{path}: default_enabled must be a boolean")

    resolved_manifest = path.resolve()
    # Confinement is relative to the package containing the manifest path, not
    # to a possible symlink target of plugin.toml itself.
    plugin_directory = path.parent.resolve()
    entrypoint_path, entrypoint_object = _resolve_entrypoint(
        path,
        plugin_directory,
        entrypoint,
    )
    return PluginManifest(
        api_version=api_version,
        id=plugin_id,
        name=name,
        version=version,
        entrypoint=entrypoint,
        commands=commands,
        default_enabled=default_enabled,
        manifest_path=resolved_manifest,
        plugin_directory=plugin_directory,
        entrypoint_path=entrypoint_path,
        entrypoint_object=entrypoint_object,
        source=source,
    )


def discover_plugins(
    included_directory: str | Path | None,
    local_directory: str | Path | None,
) -> tuple[PluginManifest, ...]:
    """Discover direct child plugin packages in deterministic source/name order.

    Discovery only parses ``plugin.toml`` files.  It never imports, compiles, or
    otherwise executes an entrypoint.  Missing roots are treated as empty so a
    first-run local directory need not already exist.
    """

    discovered: list[PluginManifest] = []
    by_id: dict[str, PluginManifest] = {}
    roots: tuple[tuple[PluginSource, str | Path | None], ...] = (
        ("included", included_directory),
        ("local", local_directory),
    )
    for source, root_value in roots:
        if root_value is None:
            continue
        root = Path(root_value)
        if not root.exists():
            continue
        if not root.is_dir():
            raise ManifestError(f"{root}: plugin discovery root is not a directory")
        try:
            children = sorted(root.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            raise ManifestError(f"{root}: cannot enumerate plugin directory: {exc}") from exc
        for child in children:
            if not child.is_dir():
                continue
            manifest_path = child / "plugin.toml"
            if not manifest_path.is_file():
                continue
            manifest = parse_manifest(manifest_path, source=source)
            previous = by_id.get(manifest.id)
            if previous is not None:
                raise DuplicatePluginIdError(
                    f"duplicate plugin id {manifest.id!r}: "
                    f"{previous.manifest_path} and {manifest.manifest_path}"
                )
            by_id[manifest.id] = manifest
            discovered.append(manifest)
    return tuple(discovered)


def validate_script_against_manifest(manifest: PluginManifest, script: object) -> Script:
    """Validate an imported entrypoint in the worker process.

    The parent-side discovery path must not call this function because doing so
    would require importing plugin Python.  Manifest identity and command
    declarations are authoritative; the Script object must agree exactly.
    """

    if not isinstance(script, Script):
        raise PluginDefinitionError(
            f"script {manifest.id!r} entrypoint {manifest.entrypoint!r} did not resolve to Script"
        )
    mismatches: list[str] = []
    if script.id != manifest.id:
        mismatches.append(f"id is {script.id!r}, manifest declares {manifest.id!r}")
    if script.name != manifest.name:
        mismatches.append(f"name is {script.name!r}, manifest declares {manifest.name!r}")
    if script.version != manifest.version:
        mismatches.append(
            f"version is {script.version!r}, manifest declares {manifest.version!r}"
        )
    script_commands = set(script.commands)
    manifest_commands = set(manifest.commands)
    if script_commands != manifest_commands:
        missing = sorted(manifest_commands - script_commands)
        undeclared = sorted(script_commands - manifest_commands)
        if missing:
            mismatches.append(f"missing command handlers: {', '.join(missing)}")
        if undeclared:
            mismatches.append(f"undeclared command handlers: {', '.join(undeclared)}")
    if mismatches:
        raise PluginDefinitionError(f"script {manifest.id!r} does not match manifest: {'; '.join(mismatches)}")
    return script


def _validate_fields(path: Path, raw: Mapping[str, object]) -> None:
    fields = set(raw)
    missing = _REQUIRED_FIELDS - fields
    unknown = fields - _REQUIRED_FIELDS
    if missing:
        raise ManifestError(f"{path}: missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise ManifestError(f"{path}: unknown fields: {', '.join(sorted(unknown))}")


def _manifest_string(
    path: Path,
    raw: Mapping[str, object],
    field: str,
    *,
    maximum: int | None = None,
) -> str:
    value = raw[field]
    if not isinstance(value, str) or not value or value != value.strip():
        raise ManifestError(f"{path}: {field} must be a non-empty, trimmed string")
    if maximum is not None and len(value) > maximum:
        raise ManifestError(f"{path}: {field} must be at most {maximum} characters")
    return value


def _manifest_commands(path: Path, value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ManifestError(f"{path}: commands must be an array of strings")
    commands: list[str] = []
    seen: set[str] = set()
    for index, command_value in enumerate(value):
        if not isinstance(command_value, str) or _COMMAND_RE.fullmatch(command_value) is None:
            raise ManifestError(
                f"{path}: commands[{index}] must match [a-z][a-z0-9_-]{{0,31}}"
            )
        if command_value in seen:
            raise ManifestError(f"{path}: duplicate command {command_value!r}")
        seen.add(command_value)
        commands.append(command_value)
    return tuple(commands)


def _resolve_entrypoint(
    manifest_path: Path,
    plugin_directory: Path,
    entrypoint: str,
) -> tuple[Path, str]:
    if entrypoint.count(":") != 1:
        raise ManifestError(
            f"{manifest_path}: entrypoint must use relative_file.py:object syntax"
        )
    relative_text, object_name = entrypoint.split(":", 1)
    if (
        not relative_text
        or "\\" in relative_text
        or not relative_text.endswith(".py")
        or not object_name.isidentifier()
    ):
        raise ManifestError(
            f"{manifest_path}: entrypoint must use relative_file.py:object syntax"
        )
    relative_path = Path(relative_text)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ManifestError(f"{manifest_path}: entrypoint must stay inside the plugin directory")
    resolved_entrypoint = (plugin_directory / relative_path).resolve()
    try:
        resolved_entrypoint.relative_to(plugin_directory)
    except ValueError as exc:
        raise ManifestError(
            f"{manifest_path}: entrypoint must stay inside the plugin directory"
        ) from exc
    if not resolved_entrypoint.is_file():
        raise ManifestError(f"{manifest_path}: entrypoint file does not exist: {relative_text}")
    return resolved_entrypoint, object_name
