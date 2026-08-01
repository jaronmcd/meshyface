"""Strict, import-free manifest parsing and plugin discovery."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import os
from pathlib import Path
import re
import stat
import tomllib
from typing import Callable, Literal, Mapping

from .sdk import Script, ViewDefinition


SUPPORTED_API_VERSION = 1
MAX_MANIFEST_BYTES = 64 * 1024
MAX_DISCOVERED_PLUGINS = 64
MAX_DISCOVERY_ROOT_ENTRIES = 1024
MAX_PLUGIN_COMMANDS = 64
MAX_PLUGIN_VIEWS = 8
MAX_PLUGIN_PACKAGE_ENTRIES = 1024
MAX_PLUGIN_PACKAGE_BYTES = 64 * 1024 * 1024
MAX_PLUGIN_README_BYTES = 128 * 1024
PACKAGE_DIGEST_PREFIX = "sha256:"
_IGNORED_DEVELOPMENT_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        "__pycache__",
        "htmlcov",
    }
)
_IGNORED_DEVELOPMENT_FILES = frozenset({".coverage", ".git"})
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
_OPTIONAL_FIELDS = {"settings", "views"}
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
class PluginReadme:
    filename: str
    content: str
    truncated: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "filename": self.filename,
            "content": self.content,
            "truncated": self.truncated,
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
    package_digest: str
    settings: tuple[PluginSettingDefinition, ...] = ()
    views: tuple[ViewDefinition, ...] = ()
    readme: PluginReadme | None = None

    @property
    def effective_default_enabled(self) -> bool:
        """Return the host-owned default for this discovered package.

        Only packages shipped in Meshyface's included-plugin directory may opt
        in to automatic enablement. A new local package cannot grant itself
        execution merely by setting a manifest field.
        """

        return self.source == "included" and self.default_enabled


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
    if path.parent.is_symlink():
        raise ManifestError(f"{path}: plugin package directory must not be a symlink")
    if path.is_symlink():
        raise ManifestError(f"{path}: plugin manifest must not be a symlink")
    try:
        manifest_bytes = _read_regular_file(
            path,
            maximum_bytes=MAX_MANIFEST_BYTES,
            label="plugin manifest",
        )
        raw = tomllib.loads(manifest_bytes.decode("utf-8"))
    except FileNotFoundError as exc:
        raise ManifestError(f"{path}: manifest does not exist") from exc
    except UnicodeDecodeError as exc:
        raise ManifestError(f"{path}: manifest must be UTF-8") from exc
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
    views = _manifest_views(path, raw.get("views", []))
    default_enabled = raw["default_enabled"]
    if not isinstance(default_enabled, bool):
        raise ManifestError(f"{path}: default_enabled must be a boolean")

    resolved_manifest = path.absolute()
    plugin_directory = path.parent.absolute()
    entrypoint_path, entrypoint_object = _resolve_entrypoint(
        path,
        plugin_directory,
        entrypoint,
    )
    package_digest = compute_plugin_package_digest(plugin_directory)
    readme = _read_optional_plugin_readme(plugin_directory)
    try:
        current_manifest_bytes = _read_regular_file(
            path,
            maximum_bytes=MAX_MANIFEST_BYTES,
            label="plugin manifest",
        )
    except OSError as exc:
        raise ManifestError(f"{path}: cannot recheck manifest: {exc}") from exc
    if current_manifest_bytes != manifest_bytes:
        raise ManifestError(f"{path}: plugin manifest changed during discovery")
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
        package_digest=package_digest,
        settings=settings,
        views=views,
        readme=readme,
    )


def discover_plugins(
    included_directory: str | Path | None,
    local_directory: str | Path | None,
    *,
    on_error: Callable[[ManifestError], object] | None = None,
) -> tuple[PluginManifest, ...]:
    """Discover direct child plugin packages in deterministic source/name order.

    Discovery only parses ``plugin.toml`` files.  It never imports, compiles, or
    otherwise executes an entrypoint.  Missing roots are treated as empty so a
    first-run local directory need not already exist.
    """

    discovered: list[PluginManifest] = []
    by_id: dict[str, PluginManifest] = {}
    candidate_count = 0
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
        if root.is_symlink():
            _report_discovery_error(
                ManifestError(f"{root}: plugin discovery root must not be a symlink"),
                on_error,
            )
            continue
        if not root.is_dir():
            _report_discovery_error(
                ManifestError(f"{root}: plugin discovery root is not a directory"),
                on_error,
            )
            continue
        try:
            children: list[Path] = []
            with os.scandir(root) as entries:
                for entry in entries:
                    if len(children) >= MAX_DISCOVERY_ROOT_ENTRIES:
                        raise ManifestError(
                            f"{root}: plugin discovery root contains more than "
                            f"{MAX_DISCOVERY_ROOT_ENTRIES} entries"
                        )
                    children.append(Path(entry.path))
            children.sort(key=lambda item: item.name)
        except ManifestError as exc:
            _report_discovery_error(exc, on_error)
            continue
        except OSError as exc:
            _report_discovery_error(
                ManifestError(f"{root}: cannot enumerate plugin directory: {exc}"),
                on_error,
            )
            continue
        for child in children:
            if child.is_symlink():
                _report_discovery_error(
                    ManifestError(f"{child}: plugin package directory must not be a symlink"),
                    on_error,
                )
                continue
            if not child.is_dir():
                continue
            manifest_path = child / "plugin.toml"
            if manifest_path.is_symlink():
                _report_discovery_error(
                    ManifestError(f"{manifest_path}: plugin manifest must not be a symlink"),
                    on_error,
                )
                continue
            if not manifest_path.is_file():
                continue
            if candidate_count >= MAX_DISCOVERED_PLUGINS:
                _report_discovery_error(
                    ManifestError(
                        f"{root}: at most {MAX_DISCOVERED_PLUGINS} plugin packages "
                        "may be inspected"
                    ),
                    on_error,
                )
                return tuple(discovered)
            candidate_count += 1
            try:
                manifest = parse_manifest(manifest_path, source=source)
            except ManifestError as exc:
                _report_discovery_error(exc, on_error)
                continue
            previous = by_id.get(manifest.id)
            if previous is not None:
                _report_discovery_error(
                    DuplicatePluginIdError(
                        f"duplicate plugin id {manifest.id!r}: "
                        f"{previous.manifest_path} and {manifest.manifest_path}"
                    ),
                    on_error,
                )
                continue
            by_id[manifest.id] = manifest
            discovered.append(manifest)
    return tuple(discovered)


def compute_plugin_package_digest(plugin_directory: str | Path) -> str:
    """Hash every regular package file in stable path/content order.

    Symlinks and non-regular filesystem objects are rejected.  The same helper
    runs during import in the worker, preventing files changed after discovery
    from executing under the earlier package revision.
    """

    root = Path(plugin_directory)
    if root.is_symlink():
        raise ManifestError(f"{root}: plugin package directory must not be a symlink")
    try:
        root_stat = root.stat()
    except OSError as exc:
        raise ManifestError(f"{root}: cannot inspect plugin package: {exc}") from exc
    if not stat.S_ISDIR(root_stat.st_mode):
        raise ManifestError(f"{root}: plugin package is not a directory")
    _validate_trusted_file_metadata(root, root_stat, label="plugin package directory")

    files: list[tuple[bytes, Path]] = []
    pending = [root]
    entry_count = 0
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                rows = sorted(entries, key=lambda entry: entry.name)
        except OSError as exc:
            raise ManifestError(f"{directory}: cannot enumerate plugin package: {exc}") from exc
        for entry in rows:
            path = Path(entry.path)
            try:
                entry_stat = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise ManifestError(f"{path}: cannot inspect plugin package entry: {exc}") from exc
            if stat.S_ISLNK(entry_stat.st_mode):
                raise ManifestError(f"{path}: plugin package symlinks are not allowed")
            if (
                stat.S_ISDIR(entry_stat.st_mode)
                and entry.name in _IGNORED_DEVELOPMENT_DIRECTORIES
            ):
                continue
            if (
                stat.S_ISREG(entry_stat.st_mode)
                and entry.name in _IGNORED_DEVELOPMENT_FILES
            ):
                continue
            entry_count += 1
            if entry_count > MAX_PLUGIN_PACKAGE_ENTRIES:
                raise ManifestError(
                    f"{root}: plugin package contains more than "
                    f"{MAX_PLUGIN_PACKAGE_ENTRIES} entries"
                )
            if stat.S_ISDIR(entry_stat.st_mode):
                _validate_trusted_file_metadata(
                    path,
                    entry_stat,
                    label="plugin package directory",
                )
                pending.append(path)
                continue
            if not stat.S_ISREG(entry_stat.st_mode):
                raise ManifestError(
                    f"{path}: plugin package entries must be regular files or directories"
                )
            # Preserve POSIX filenames that are not valid UTF-8 without letting
            # a UnicodeEncodeError escape the package-level isolation boundary.
            relative_bytes = os.fsencode(path.relative_to(root).as_posix())
            if len(relative_bytes) > 4096:
                raise ManifestError(f"{path}: plugin package path is too long")
            files.append((relative_bytes, path))

    digest = hashlib.sha256()
    digest.update(b"meshyface-plugin-package-v1\0")
    total_bytes = 0
    for relative_bytes, path in sorted(files, key=lambda row: row[0]):
        try:
            data = _read_regular_file(
                path,
                maximum_bytes=MAX_PLUGIN_PACKAGE_BYTES - total_bytes,
                label="plugin package file",
            )
        except FileNotFoundError as exc:
            raise ManifestError(f"{path}: plugin package changed during inspection") from exc
        except OSError as exc:
            raise ManifestError(f"{path}: cannot read plugin package file: {exc}") from exc
        total_bytes += len(data)
        digest.update(len(relative_bytes).to_bytes(4, "big"))
        digest.update(relative_bytes)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return f"{PACKAGE_DIGEST_PREFIX}{digest.hexdigest()}"


def _read_regular_file(path: Path, *, maximum_bytes: int, label: str) -> bytes:
    if maximum_bytes < 0:
        raise ManifestError(f"{path}: plugin package exceeds {MAX_PLUGIN_PACKAGE_BYTES} bytes")
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ManifestError(f"{path}: {label} must be a regular file")
        _validate_trusted_file_metadata(path, before, label=label)
        if before.st_size > maximum_bytes:
            if label == "plugin manifest":
                raise ManifestError(
                    f"{path}: manifest exceeds the {MAX_MANIFEST_BYTES}-byte limit"
                )
            raise ManifestError(
                f"{path}: plugin package exceeds {MAX_PLUGIN_PACKAGE_BYTES} bytes"
            )
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        after = os.fstat(descriptor)
        if (
            len(data) != before.st_size
            or after.st_size != before.st_size
            or after.st_mtime_ns != before.st_mtime_ns
        ):
            raise ManifestError(f"{path}: {label} changed while it was being read")
        return data
    finally:
        os.close(descriptor)


def _read_optional_plugin_readme(plugin_directory: Path) -> PluginReadme | None:
    path = plugin_directory / "README.md"
    if not path.exists():
        return None
    try:
        data = _read_regular_file(
            path,
            maximum_bytes=MAX_PLUGIN_PACKAGE_BYTES,
            label="plugin README",
        )
    except FileNotFoundError:
        return None
    truncated = len(data) > MAX_PLUGIN_README_BYTES
    if truncated:
        data = data[:MAX_PLUGIN_README_BYTES]
    content = data.decode("utf-8", errors="replace").strip()
    if not content:
        return None
    return PluginReadme(
        filename=path.name,
        content=content,
        truncated=truncated,
    )


def _validate_trusted_file_metadata(
    path: Path,
    metadata: os.stat_result,
    *,
    label: str,
) -> None:
    """Reject package code writable by identities outside the service owner/root."""

    if os.name != "posix":
        return
    if metadata.st_mode & stat.S_IWOTH:
        raise ManifestError(
            f"{path}: {label} must not be world-writable"
        )
    effective_uid_fn = getattr(os, "geteuid", None)
    if not callable(effective_uid_fn):
        return
    effective_uid = int(effective_uid_fn())
    if int(metadata.st_uid) not in {0, effective_uid}:
        raise ManifestError(
            f"{path}: {label} must be owned by root or the dashboard service user"
        )
    if metadata.st_mode & stat.S_IWGRP and not _group_is_private_to_service_user(
        int(metadata.st_gid),
        effective_uid,
    ):
        raise ManifestError(
            f"{path}: {label} must not be writable by an unrelated group"
        )


@lru_cache(maxsize=16)
def _group_is_private_to_service_user(group_id: int, effective_uid: int) -> bool:
    """Allow the common user-private-group umask without trusting shared groups."""

    try:
        import grp
        import pwd

        service_entry = pwd.getpwuid(effective_uid)
        service_user = service_entry.pw_name
        # A service can intentionally run with a shared effective group (for
        # example, ``dialout``) while its package files remain owned by its
        # private primary group. Only that private primary group is trusted.
        if int(service_entry.pw_gid) != group_id:
            return False
        primary_users = {
            entry.pw_uid
            for entry in pwd.getpwall()
            if int(entry.pw_gid) == group_id
        }
        explicit_members = set(grp.getgrgid(group_id).gr_mem)
    except (ImportError, KeyError, OSError):
        return False
    return primary_users <= {effective_uid} and explicit_members <= {service_user}


def _report_discovery_error(
    error: ManifestError,
    on_error: Callable[[ManifestError], object] | None,
) -> None:
    if on_error is None:
        raise error
    on_error(error)


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
    script_views = set(script.views)
    manifest_views = {definition.id for definition in manifest.views}
    if script_views != manifest_views:
        missing = sorted(manifest_views - script_views)
        undeclared = sorted(script_views - manifest_views)
        if missing:
            mismatches.append(f"missing view declarations: {', '.join(missing)}")
        if undeclared:
            mismatches.append(f"undeclared view declarations: {', '.join(undeclared)}")
    for manifest_view in manifest.views:
        script_view = script.views.get(manifest_view.id)
        if script_view is None:
            continue
        if script_view.label != manifest_view.label:
            mismatches.append(
                f"view {manifest_view.id!r} label is {script_view.label!r}, "
                f"manifest declares {manifest_view.label!r}"
            )
        if script_view.icon != manifest_view.icon:
            mismatches.append(
                f"view {manifest_view.id!r} icon is {script_view.icon!r}, "
                f"manifest declares {manifest_view.icon!r}"
            )
        if script_view.description != manifest_view.description:
            mismatches.append(
                f"view {manifest_view.id!r} description does not match manifest"
            )
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
    if len(value) > MAX_PLUGIN_COMMANDS:
        raise ManifestError(
            f"{path}: commands may contain at most {MAX_PLUGIN_COMMANDS} entries"
        )
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


def _manifest_views(path: Path, value: object) -> tuple[ViewDefinition, ...]:
    if not isinstance(value, list):
        raise ManifestError(f"{path}: views must be an array of tables")
    if len(value) > MAX_PLUGIN_VIEWS:
        raise ManifestError(f"{path}: views may contain at most {MAX_PLUGIN_VIEWS} entries")
    definitions: list[ViewDefinition] = []
    seen: set[str] = set()
    for index, raw_view in enumerate(value):
        prefix = f"{path}: views[{index}]"
        if not isinstance(raw_view, Mapping):
            raise ManifestError(f"{prefix} must be a table")
        allowed = {"id", "label", "icon", "description"}
        missing = {"id", "label"} - set(raw_view)
        unknown = set(raw_view) - allowed
        if missing:
            raise ManifestError(f"{prefix} missing fields: {', '.join(sorted(missing))}")
        if unknown:
            raise ManifestError(f"{prefix} unknown fields: {', '.join(sorted(unknown))}")
        view_id = _setting_string(prefix, raw_view.get("id"), "id", maximum=32)
        if _COMMAND_RE.fullmatch(view_id) is None:
            raise ManifestError(f"{prefix}.id must match [a-z][a-z0-9_-]{{0,31}}")
        if view_id in seen:
            raise ManifestError(f"{path}: duplicate view id {view_id!r}")
        seen.add(view_id)
        label = _setting_string(prefix, raw_view.get("label"), "label", maximum=32)
        icon = _setting_optional_string(
            prefix,
            raw_view.get("icon", ""),
            "icon",
            maximum=4,
        )
        description = _setting_optional_string(
            prefix,
            raw_view.get("description", ""),
            "description",
            maximum=120,
        )
        try:
            definitions.append(
                ViewDefinition(
                    id=view_id,
                    label=label,
                    icon=icon,
                    description=description,
                )
            )
        except ValueError as exc:
            raise ManifestError(f"{prefix}.{exc}") from exc
    return tuple(definitions)


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
    try:
        resolved_entrypoint = (plugin_directory / relative_path).resolve(strict=True)
    except FileNotFoundError as exc:
        raise ManifestError(
            f"{manifest_path}: entrypoint file does not exist: {relative_text}"
        ) from exc
    except (OSError, RuntimeError) as exc:
        raise ManifestError(
            f"{manifest_path}: entrypoint path cannot be resolved"
        ) from exc
    try:
        resolved_entrypoint.relative_to(plugin_directory)
    except ValueError as exc:
        raise ManifestError(
            f"{manifest_path}: entrypoint must stay inside the plugin directory"
        ) from exc
    if not resolved_entrypoint.is_file():
        raise ManifestError(f"{manifest_path}: entrypoint file does not exist: {relative_text}")
    return resolved_entrypoint, object_name
