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
_SETTING_KEY_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
_NODE_ID_RE = re.compile(r"![0-9a-f]{8}\Z")
_REQUIRED_FIELDS = {
    "api_version",
    "id",
    "name",
    "version",
    "entrypoint",
    "commands",
    "default_enabled",
}
_OPTIONAL_FIELDS = {"settings"}
PluginSource = Literal["included", "local"]
PluginSettingType = Literal["text", "boolean", "integer", "node_ids"]


class ManifestError(ValueError):
    """A plugin manifest or discovery directory is invalid."""


class DuplicatePluginIdError(ManifestError):
    """Two discovered manifests declare the same plugin ID."""


class PluginDefinitionError(ValueError):
    """An imported worker entrypoint disagrees with its manifest."""


@dataclass(frozen=True, slots=True)
class PluginSettingDefinition:
    key: str
    label: str
    type: PluginSettingType
    default: object
    description: str = ""
    placeholder: str = ""
    minimum: int | None = None
    maximum: int | None = None
    max_length: int | None = None

    def to_dict(self) -> dict[str, object]:
        default = list(self.default) if isinstance(self.default, tuple) else self.default
        return {
            "key": self.key,
            "label": self.label,
            "type": self.type,
            "default": default,
            "description": self.description,
            "placeholder": self.placeholder,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "max_length": self.max_length,
        }


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
    settings: tuple[PluginSettingDefinition, ...] = ()


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
    settings = _manifest_settings(path, raw.get("settings", []))
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
        settings=settings,
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
    unknown = fields - _REQUIRED_FIELDS - _OPTIONAL_FIELDS
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


def _manifest_settings(path: Path, value: object) -> tuple[PluginSettingDefinition, ...]:
    if not isinstance(value, list):
        raise ManifestError(f"{path}: settings must be an array of tables")
    if len(value) > 32:
        raise ManifestError(f"{path}: settings may contain at most 32 entries")
    definitions: list[PluginSettingDefinition] = []
    seen: set[str] = set()
    for index, raw_setting in enumerate(value):
        prefix = f"{path}: settings[{index}]"
        if not isinstance(raw_setting, Mapping):
            raise ManifestError(f"{prefix} must be a table")
        setting_type = raw_setting.get("type")
        if setting_type not in {"text", "boolean", "integer", "node_ids"}:
            raise ManifestError(
                f"{prefix}.type must be text, boolean, integer, or node_ids"
            )
        allowed = {"key", "label", "type", "default", "description"}
        if setting_type == "text":
            allowed.update({"placeholder", "max_length"})
        elif setting_type == "integer":
            allowed.update({"minimum", "maximum"})
        missing = {"key", "label", "type", "default"} - set(raw_setting)
        unknown = set(raw_setting) - allowed
        if missing:
            raise ManifestError(f"{prefix} missing fields: {', '.join(sorted(missing))}")
        if unknown:
            raise ManifestError(f"{prefix} unknown fields: {', '.join(sorted(unknown))}")
        key = _setting_string(prefix, raw_setting.get("key"), "key", maximum=32)
        if _SETTING_KEY_RE.fullmatch(key) is None:
            raise ManifestError(f"{prefix}.key must match [a-z][a-z0-9_-]{{0,31}}")
        if key in seen:
            raise ManifestError(f"{path}: duplicate setting key {key!r}")
        seen.add(key)
        label = _setting_string(prefix, raw_setting.get("label"), "label", maximum=64)
        description = _setting_optional_string(
            prefix,
            raw_setting.get("description", ""),
            "description",
            maximum=256,
        )
        placeholder = ""
        minimum: int | None = None
        maximum: int | None = None
        max_length: int | None = None
        if setting_type == "text":
            placeholder = _setting_optional_string(
                prefix,
                raw_setting.get("placeholder", ""),
                "placeholder",
                maximum=128,
            )
            max_length = _setting_integer(
                prefix,
                raw_setting.get("max_length", 256),
                "max_length",
                minimum=1,
                maximum=4096,
            )
        elif setting_type == "integer":
            if "minimum" in raw_setting:
                minimum = _setting_integer(prefix, raw_setting["minimum"], "minimum")
            if "maximum" in raw_setting:
                maximum = _setting_integer(prefix, raw_setting["maximum"], "maximum")
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ManifestError(f"{prefix}.minimum must not exceed maximum")
        definition = PluginSettingDefinition(
            key=key,
            label=label,
            type=setting_type,
            default=(),
            description=description,
            placeholder=placeholder,
            minimum=minimum,
            maximum=maximum,
            max_length=max_length,
        )
        try:
            default = normalize_plugin_setting_value(
                definition,
                raw_setting.get("default"),
                label=f"{prefix}.default",
            )
        except ValueError as exc:
            raise ManifestError(str(exc)) from exc
        definitions.append(
            PluginSettingDefinition(
                key=key,
                label=label,
                type=setting_type,
                default=tuple(default) if isinstance(default, list) else default,
                description=description,
                placeholder=placeholder,
                minimum=minimum,
                maximum=maximum,
                max_length=max_length,
            )
        )
    return tuple(definitions)


def _setting_string(prefix: str, value: object, field: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ManifestError(f"{prefix}.{field} must be a non-empty, trimmed string")
    if len(value) > maximum:
        raise ManifestError(f"{prefix}.{field} must be at most {maximum} characters")
    return value


def _setting_optional_string(
    prefix: str,
    value: object,
    field: str,
    *,
    maximum: int,
) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise ManifestError(f"{prefix}.{field} must be a trimmed string")
    if len(value) > maximum:
        raise ManifestError(f"{prefix}.{field} must be at most {maximum} characters")
    return value


def _setting_integer(
    prefix: str,
    value: object,
    field: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ManifestError(f"{prefix}.{field} must be an integer")
    if minimum is not None and value < minimum:
        raise ManifestError(f"{prefix}.{field} must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise ManifestError(f"{prefix}.{field} must be at most {maximum}")
    return value


def normalize_plugin_setting_value(
    definition: PluginSettingDefinition,
    value: object,
    *,
    label: str | None = None,
) -> object:
    field = label or definition.label
    if definition.type == "text":
        if not isinstance(value, str):
            raise ValueError(f"{field} must be text")
        if len(value) > int(definition.max_length or 256):
            raise ValueError(
                f"{field} must be at most {int(definition.max_length or 256)} characters"
            )
        return value
    if definition.type == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{field} must be a boolean")
        return value
    if definition.type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{field} must be an integer")
        if definition.minimum is not None and value < definition.minimum:
            raise ValueError(f"{field} must be at least {definition.minimum}")
        if definition.maximum is not None and value > definition.maximum:
            raise ValueError(f"{field} must be at most {definition.maximum}")
        return value
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field} must be an array of node IDs")
    if len(value) > 64:
        raise ValueError(f"{field} may contain at most 64 node IDs")
    node_ids: list[str] = []
    seen: set[str] = set()
    for index, raw_node_id in enumerate(value):
        if not isinstance(raw_node_id, str):
            raise ValueError(f"{field}[{index}] must be a node ID")
        node_id = raw_node_id.strip().lower()
        if _NODE_ID_RE.fullmatch(node_id) is None:
            raise ValueError(f"{field}[{index}] must match !00000000")
        if node_id not in seen:
            seen.add(node_id)
            node_ids.append(node_id)
    return node_ids


def normalize_plugin_settings(
    manifest: PluginManifest,
    values: Mapping[str, object],
    *,
    require_all: bool,
) -> dict[str, object]:
    definitions = {definition.key: definition for definition in manifest.settings}
    unknown = set(values) - set(definitions)
    missing = set(definitions) - set(values) if require_all else set()
    if unknown:
        raise ValueError(f"unknown settings: {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"missing settings: {', '.join(sorted(missing))}")
    normalized: dict[str, object] = {}
    for key, definition in definitions.items():
        raw_value = values[key] if key in values else definition.default
        normalized[key] = normalize_plugin_setting_value(definition, raw_value)
    return normalized


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
