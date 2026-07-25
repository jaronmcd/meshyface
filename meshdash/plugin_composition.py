"""Application composition for the opt-in trusted plugin subsystem."""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from .plugins import (
    PluginManifest,
    compute_plugin_package_digest,
    discover_plugins,
    normalize_plugin_settings,
)
from .file_transfer_protocol import decode_file_transfer_packet
from .helpers import to_int, to_jsonable
from .helpers_packet_position import extract_position_fields
from .plugin_events import normalize_plugin_message_event, normalize_plugin_packet_event
from .plugin_runtime import (
    PluginRuntime,
    PluginRuntimeConfig,
    sanitize_plugin_status_error,
)
from .plugin_state import PluginStateStore
from .services_file_transfer_outbound import (
    ApprovedPathFileResolver,
    OutboundFileTransferService,
)


def _packet_sender_id(packet: Mapping[str, object]) -> str:
    raw = packet.get("from")
    numeric = to_int(raw)
    if numeric is not None and 0 <= numeric <= 0xFFFFFFFF:
        return f"!{numeric:08x}"
    for key in ("fromId", "from_id"):
        value = str(packet.get(key) or "").strip().lower()
        if value.startswith("!") and len(value) == 9:
            return value
    return ""


def _packet_destination_id(packet: Mapping[str, object]) -> str:
    raw = packet.get("to")
    numeric = to_int(raw)
    if numeric is not None and 0 <= numeric <= 0xFFFFFFFF:
        return f"!{numeric:08x}"
    for key in ("toId", "to_id"):
        value = str(packet.get(key) or "").strip().lower()
        if value.startswith("!") and len(value) == 9:
            return value
    return ""


def _node_snapshot(iface: object) -> list[dict[str, object]]:
    nodes_by_num = getattr(iface, "nodesByNum", None)
    if not isinstance(nodes_by_num, Mapping):
        return []
    rows: list[dict[str, object]] = []
    for node_num, raw in list(nodes_by_num.items())[:2048]:
        value = to_jsonable(raw)
        if not isinstance(value, dict):
            continue
        user = value.get("user")
        user_id = user.get("id") if isinstance(user, Mapping) else None
        numeric = to_int(node_num)
        row: dict[str, object] = {
            "id": str(user_id or (f"!{numeric:08x}" if numeric is not None else "")),
            "node_num": numeric,
            "long_name": user.get("longName") if isinstance(user, Mapping) else None,
            "short_name": user.get("shortName") if isinstance(user, Mapping) else None,
            "last_heard": value.get("lastHeard"),
            "snr": value.get("snr"),
            "hops": value.get("hopsAway"),
        }
        position = value.get("position")
        coordinates = extract_position_fields(position)
        if coordinates is not None:
            normalized_position: dict[str, object] = {
                "latitude": coordinates[0],
                "longitude": coordinates[1],
            }
            if isinstance(position, Mapping):
                altitude = position.get("altitude") or position.get("altitude_m")
                if altitude is not None:
                    normalized_position["altitude"] = altitude
            row["position"] = normalized_position
        rows.append(row)
    return rows


def _script_runtime_health(
    *,
    plugin_id: str,
    configured_enabled: bool,
    active: bool,
    runtime_enabled: bool,
    runtime_status: Mapping[str, object],
) -> tuple[str, str, bool]:
    if not runtime_enabled:
        return "master_disabled" if configured_enabled else "disabled", "", False
    restart_required = configured_enabled != active
    if restart_required:
        return "restart_pending", "", True
    if not active:
        return "disabled", "", False

    runtime_plugins = runtime_status.get("plugins")
    registration = runtime_plugins.get(plugin_id) if isinstance(runtime_plugins, Mapping) else None
    registration_error = (
        str(registration.get("error") or "").strip() if isinstance(registration, Mapping) else ""
    )
    if registration_error:
        return "error", registration_error, False

    worker_status = str(runtime_status.get("status") or "").strip().lower()
    if worker_status == "running" and isinstance(registration, Mapping):
        return "running", "", False
    if worker_status == "starting" or not worker_status:
        return "starting", "", False

    worker_error = str(runtime_status.get("last_error") or "").strip()
    return "error", worker_error or "Script worker is not running", False


def _script_view_statuses(
    *,
    manifest: PluginManifest,
    is_enabled: bool,
    is_active: bool,
    health: str,
    runtime_status: Mapping[str, object],
) -> list[dict[str, object]]:
    runtime_plugins = runtime_status.get("plugins")
    registration = (
        runtime_plugins.get(manifest.id)
        if isinstance(runtime_plugins, Mapping)
        else None
    )
    runtime_views = registration.get("views") if isinstance(registration, Mapping) else None
    runtime_views_by_id = {
        str(row.get("id") or ""): row
        for row in runtime_views
        if isinstance(row, Mapping)
    } if isinstance(runtime_views, list) else {}
    views: list[dict[str, object]] = []
    for definition in manifest.views:
        row: dict[str, object] = definition.to_dict(include_content=False)
        runtime_view = runtime_views_by_id.get(definition.id)
        content = (
            str(runtime_view.get("content") or "")
            if isinstance(runtime_view, Mapping)
            else ""
        )
        row.update(
            {
                "plugin_id": manifest.id,
                "plugin_name": manifest.name,
                "enabled": bool(is_enabled),
                "active": bool(is_active),
                "runtime_status": health,
                "content": content,
            }
        )
        views.append(row)
    return views


def _script_mesh_access_status(
    *,
    manifest: PluginManifest,
    runtime_status: Mapping[str, object],
) -> str:
    runtime_plugins = runtime_status.get("plugins")
    registration = (
        runtime_plugins.get(manifest.id)
        if isinstance(runtime_plugins, Mapping)
        else None
    )
    raw = (
        str(registration.get("mesh_access") or "").strip().lower()
        if isinstance(registration, Mapping)
        else ""
    )
    return raw if raw in {"none", "read_only", "read_write", "unknown"} else "unknown"


class PluginSubsystem:
    def __init__(
        self,
        *,
        state_store: PluginStateStore | None,
        runtime: PluginRuntime | None,
        outbound_files: OutboundFileTransferService | None,
        manifests: Sequence[PluginManifest] = (),
        enabled_plugin_ids: Sequence[str] = (),
        runtime_enabled: bool = True,
        error: str = "",
        discovery_errors: Sequence[str] = (),
        directory: str = "",
        detach_receive_fn: Callable[[], object] | None = None,
        runtime_factory: (
            Callable[
                [Sequence[PluginManifest]],
                tuple[PluginRuntime, OutboundFileTransferService | None],
            ]
            | None
        ) = None,
        state_changed_fn: Callable[[], object] | None = None,
    ) -> None:
        self._state_store = state_store
        self._runtime = runtime
        self._outbound_files = outbound_files
        self._manifests = tuple(manifests)
        self._enabled_plugin_ids = tuple(enabled_plugin_ids)
        self._runtime_enabled = bool(runtime_enabled)
        self._error = sanitize_plugin_status_error(error)
        self._discovery_errors = tuple(
            sanitize_plugin_status_error(value) for value in discovery_errors
        )
        self._directory = str(directory or "").strip()
        self._detach_receive_fn = detach_receive_fn
        self._runtime_factory = runtime_factory
        self._state_changed_fn = state_changed_fn
        self._lifecycle_lock = threading.RLock()
        self._closed = False

    def _route_policy_for_manifests(
        self,
        manifests: Sequence[PluginManifest],
    ) -> dict[str, dict[str, bool]]:
        if self._state_store is None:
            return {
                manifest.id: {
                    "mesh_enabled": True,
                    "console_enabled": True,
                    "ticker_enabled": True,
                    "view_enabled": True,
                }
                for manifest in manifests
            }
        return {
            manifest.id: self._state_store.plugin_route_policy(manifest.id)
            for manifest in manifests
        }

    def _configured_enabled_manifests(self) -> tuple[PluginManifest, ...]:
        if self._state_store is None:
            return tuple(
                manifest
                for manifest in self._manifests
                if manifest.effective_default_enabled
            )
        return tuple(
            manifest
            for manifest in self._manifests
            if self._state_store.plugin_enabled(
                manifest.id,
                package_digest=manifest.package_digest,
                default=manifest.effective_default_enabled,
            )
        )

    def on_receive(self, packet: object, interface: object, *, local_node_id_fn) -> None:
        if self._closed:
            return
        self.on_file_transfer_receive(packet, interface)
        runtime = self._runtime
        if runtime is None:
            return
        local_node_id = local_node_id_fn()
        packet_event = normalize_plugin_packet_event(
            packet,
            local_node_id=local_node_id,
        )
        if packet_event is not None:
            runtime.try_enqueue(packet_event)
        event = normalize_plugin_message_event(
            packet,
            local_node_id=local_node_id,
        )
        if event is not None:
            runtime.try_enqueue(event)

    def on_file_transfer_receive(self, packet: object, interface: object | None = None) -> None:
        del interface
        if self._closed:
            return
        service = self._outbound_files
        if service is None or not isinstance(packet, Mapping):
            return
        frame = decode_file_transfer_packet(packet)
        if frame is None:
            return
        sender_id = _packet_sender_id(packet)
        if not sender_id:
            return
        destination_id = _packet_destination_id(packet)
        if not destination_id:
            return
        kind = str(frame.get("kind") or "")
        if kind == "ack":
            service.handle_ack(
                sender_id=sender_id,
                frame=frame,
                channel_index=packet.get("channel"),
                destination_id=destination_id,
            )
        elif kind == "flow":
            service.handle_flow(
                sender_id=sender_id,
                frame=frame,
                channel_index=packet.get("channel"),
                destination_id=destination_id,
            )

    def status(self) -> dict[str, object]:
        with self._lifecycle_lock:
            runtime = self._runtime
            active_plugin_ids = tuple(self._enabled_plugin_ids)
            runtime_enabled = self._runtime_enabled
            active_ids = set(active_plugin_ids)
        runtime_status = runtime.status() if runtime is not None else {}
        route_policies = self._route_policy_for_manifests(self._manifests)
        ticker_enabled_by_id = {
            plugin_id: bool(policy.get("ticker_enabled", True))
            for plugin_id, policy in route_policies.items()
        }
        raw_tickers = runtime_status.get("tickers")
        if isinstance(raw_tickers, list):
            runtime_status = dict(runtime_status)
            runtime_status["tickers"] = [
                ticker
                for ticker in raw_tickers
                if not isinstance(ticker, Mapping)
                or ticker_enabled_by_id.get(
                    str(ticker.get("plugin_id") or "").strip().lower(),
                    True,
                )
            ]
        configured_enabled: dict[str, bool] = {}
        package_revision_states: dict[str, tuple[str, bool]] = {}
        for manifest in self._manifests:
            if self._state_store is None:
                configured_enabled[manifest.id] = manifest.effective_default_enabled
                package_revision_states[manifest.id] = ("new", False)
            else:
                configured_enabled[manifest.id] = self._state_store.plugin_enabled(
                    manifest.id,
                    package_digest=manifest.package_digest,
                    default=manifest.effective_default_enabled,
                )
                enablement_record = self._state_store.plugin_enablement_record(
                    manifest.id
                )
                if enablement_record is None:
                    package_revision_states[manifest.id] = (
                        ("bundled", False)
                        if manifest.source == "included"
                        else ("new", False)
                    )
                elif enablement_record[1] != manifest.package_digest:
                    package_revision_states[manifest.id] = (
                        "stale_revision",
                        True,
                    )
                elif enablement_record[0]:
                    package_revision_states[manifest.id] = ("known_enabled", False)
                else:
                    package_revision_states[manifest.id] = ("known_disabled", False)
        scripts: list[dict[str, object]] = []
        for manifest in self._manifests:
            is_enabled = configured_enabled[manifest.id]
            route_policy = route_policies.get(
                manifest.id,
                {
                    "mesh_enabled": True,
                    "console_enabled": True,
                    "ticker_enabled": True,
                    "view_enabled": True,
                },
            )
            package_revision_status, identity_changed = package_revision_states[
                manifest.id
            ]
            is_active = manifest.id in active_ids
            health, runtime_error, restart_required = _script_runtime_health(
                plugin_id=manifest.id,
                configured_enabled=is_enabled,
                active=is_active,
                runtime_enabled=runtime_enabled,
                runtime_status=runtime_status,
            )
            stored_settings = (
                self._state_store.plugin_settings(
                    manifest.id,
                    package_digest=manifest.package_digest,
                )
                if self._state_store is not None
                else {}
            )
            try:
                settings = normalize_plugin_settings(
                    manifest,
                    stored_settings,
                    require_all=False,
                )
            except ValueError:
                settings = normalize_plugin_settings(manifest, {}, require_all=False)
            script_status: dict[str, object] = {
                "id": manifest.id,
                "name": manifest.name,
                "version": manifest.version,
                "commands": list(manifest.commands),
                "source": manifest.source,
                "default_enabled": manifest.effective_default_enabled,
                "declared_default_enabled": manifest.default_enabled,
                "package_digest": manifest.package_digest,
                # Compatibility key retained for the current Scripts API.
                "approval_status": package_revision_status,
                "identity_changed": identity_changed,
                "enabled": is_enabled,
                "active": is_active,
                "mesh_enabled": bool(route_policy.get("mesh_enabled", True)),
                "mesh_access": _script_mesh_access_status(
                    manifest=manifest,
                    runtime_status=runtime_status,
                ),
                "console_enabled": bool(route_policy.get("console_enabled", True)),
                "ticker_enabled": bool(route_policy.get("ticker_enabled", True)),
                "view_enabled": bool(route_policy.get("view_enabled", True)),
                "runtime_status": health,
                "runtime_error": runtime_error,
                "restart_required": restart_required,
                "settings_schema": [
                    definition.to_dict() for definition in manifest.settings
                ],
                "settings": settings,
                "views": _script_view_statuses(
                    manifest=manifest,
                    is_enabled=is_enabled,
                    is_active=is_active,
                    health=health,
                    runtime_status=runtime_status,
                ),
            }
            if manifest.readme is not None:
                script_status["readme"] = manifest.readme.to_dict()
            scripts.append(script_status)
        return {
            "enabled": True,
            "runtime_enabled": runtime_enabled,
            "error": self._error,
            "discovery_errors": list(self._discovery_errors),
            "directory": self._directory,
            "discovered": len(self._manifests),
            "enabled_plugins": list(active_plugin_ids),
            "scripts": scripts,
            "runtime": runtime_status,
            "file_jobs": (
                self._outbound_files.get_status()
                if self._outbound_files is not None
                else {"available": False}
            ),
        }

    def set_plugin_enabled(
        self,
        plugin_id: object,
        enabled: bool,
        *,
        expected_package_digest: object,
    ) -> dict[str, object]:
        if self._state_store is None:
            return {
                "ok": False,
                "error": {
                    "code": "plugin_runtime_unavailable",
                    "message": self._error or "Plugin runtime is unavailable",
                },
            }
        clean_id = str(plugin_id or "").strip().lower()
        manifest = next(
            (candidate for candidate in self._manifests if candidate.id == clean_id),
            None,
        )
        if manifest is None:
            return {
                "ok": False,
                "error": {"code": "unknown_plugin", "message": "Unknown plugin ID"},
            }
        expected_digest = str(expected_package_digest or "").strip().lower()
        if expected_digest != manifest.package_digest:
            return {
                "ok": False,
                "error": {
                    "code": "plugin_identity_changed",
                    "message": (
                        "Plugin package revision is stale; refresh the Scripts "
                        "workspace and retry this change"
                    ),
                },
                "package_digest": manifest.package_digest,
            }
        requested_enabled = bool(enabled)
        settings_migration_attempted = False
        settings_migrated = False
        with self._lifecycle_lock:
            if self._closed:
                return {
                    "ok": False,
                    "error": {
                        "code": "plugin_runtime_unavailable",
                        "message": "Plugin runtime is closed",
                    },
                }
            if requested_enabled:
                try:
                    current_digest = compute_plugin_package_digest(
                        manifest.plugin_directory
                    )
                except Exception:
                    current_digest = ""
                if current_digest != manifest.package_digest:
                    return {
                        "ok": False,
                        "error": {
                            "code": "plugin_package_changed",
                            "message": (
                                "Plugin package changed after discovery; restart "
                                "Meshyface to load the current local revision"
                            ),
                        },
                    }
                enablement_record = self._state_store.plugin_enablement_record(
                    clean_id
                )
                settings_record = self._state_store.plugin_settings_record(clean_id)
                package_revision_changed = (
                    (
                        enablement_record is not None
                        and enablement_record[1] != manifest.package_digest
                    )
                    or (
                        settings_record is not None
                        and settings_record[1] != manifest.package_digest
                    )
                )
                if (
                    settings_record is not None
                    and settings_record[1] != manifest.package_digest
                ):
                    settings_migration_attempted = True
                    try:
                        migrated_settings = normalize_plugin_settings(
                            manifest,
                            settings_record[0],
                            require_all=False,
                        )
                    except ValueError:
                        pass
                    else:
                        self._state_store.set_plugin_settings(
                            clean_id,
                            migrated_settings,
                            package_digest=manifest.package_digest,
                        )
                        settings_migrated = True
                if package_revision_changed:
                    runtime = self._runtime
                    if runtime is None:
                        self._state_store.clear_sessions_for_plugin(clean_id)
                    else:
                        runtime.clear_sessions_for_plugin(clean_id)
            current_ids = set(self._enabled_plugin_ids)
            target_ids = set(current_ids)
            if requested_enabled:
                target_ids.add(clean_id)
            else:
                target_ids.discard(clean_id)
            target_manifests = tuple(
                manifest for manifest in self._manifests if manifest.id in target_ids
            )
            previous_setting = self._state_store.plugin_enabled(
                clean_id,
                package_digest=manifest.package_digest,
                default=manifest.effective_default_enabled,
            )
            self._state_store.set_plugin_enabled(
                clean_id,
                requested_enabled,
                package_digest=manifest.package_digest,
            )
            if not self._runtime_enabled:
                runtime = self._runtime
                if runtime is not None:
                    runtime.reconfigure((), route_policy={})
                    runtime.close()
                    self._runtime = None
                self._enabled_plugin_ids = ()
                if self._state_changed_fn is not None:
                    try:
                        self._state_changed_fn()
                    except Exception:
                        pass
                result = {
                    "ok": True,
                    "plugin_id": clean_id,
                    "enabled": requested_enabled,
                    "active": False,
                    "restart_required": False,
                }
                if settings_migration_attempted:
                    result["settings_migrated"] = settings_migrated
                return result
            try:
                runtime = self._runtime
                if target_manifests:
                    if runtime is None:
                        if self._runtime_factory is None:
                            raise RuntimeError("Plugin runtime cannot be started")
                        runtime, outbound = self._runtime_factory(target_manifests)
                        self._runtime = runtime
                        self._outbound_files = outbound
                    elif target_ids != current_ids:
                        runtime.reconfigure(
                            target_manifests,
                            route_policy=self._route_policy_for_manifests(
                                target_manifests
                            ),
                        )
                elif runtime is not None:
                    runtime.reconfigure((), route_policy={})
                    runtime.close()
                    self._runtime = None
                self._enabled_plugin_ids = tuple(manifest.id for manifest in target_manifests)
            except Exception as exc:
                self._state_store.set_plugin_enabled(
                    clean_id,
                    previous_setting,
                    package_digest=manifest.package_digest,
                )
                return {
                    "ok": False,
                    "error": {
                        "code": "plugin_lifecycle_failed",
                        "message": sanitize_plugin_status_error(exc),
                    },
                }
            if self._state_changed_fn is not None:
                try:
                    self._state_changed_fn()
                except Exception:
                    pass
            result: dict[str, object] = {
                "ok": True,
                "plugin_id": clean_id,
                "enabled": requested_enabled,
                "active": requested_enabled,
                "restart_required": False,
            }
            if settings_migration_attempted:
                result["settings_migrated"] = settings_migrated
            return result

    def set_runtime_enabled(self, enabled: bool) -> dict[str, object]:
        if self._state_store is None:
            return {
                "ok": False,
                "error": {
                    "code": "plugin_runtime_unavailable",
                    "message": self._error or "Plugin runtime is unavailable",
                },
            }
        requested_enabled = bool(enabled)
        with self._lifecycle_lock:
            if self._closed:
                return {
                    "ok": False,
                    "error": {
                        "code": "plugin_runtime_unavailable",
                        "message": "Plugin runtime is closed",
                    },
                }
            previous_enabled = self._runtime_enabled
            previous_runtime = self._runtime
            previous_outbound = self._outbound_files
            previous_ids = tuple(self._enabled_plugin_ids)
            self._state_store.set_runtime_enabled(requested_enabled)
            try:
                if not requested_enabled:
                    runtime = self._runtime
                    if runtime is not None:
                        runtime.reconfigure((), route_policy={})
                        runtime.close()
                    self._runtime = None
                    self._enabled_plugin_ids = ()
                else:
                    target_manifests = self._configured_enabled_manifests()
                    runtime = self._runtime
                    if target_manifests:
                        if runtime is None:
                            if self._runtime_factory is None:
                                raise RuntimeError("Plugin runtime cannot be started")
                            runtime, outbound = self._runtime_factory(target_manifests)
                            self._runtime = runtime
                            self._outbound_files = outbound
                        else:
                            runtime.reconfigure(
                                target_manifests,
                                route_policy=self._route_policy_for_manifests(
                                    target_manifests
                                ),
                            )
                    elif runtime is not None:
                        runtime.reconfigure((), route_policy={})
                        runtime.close()
                        self._runtime = None
                    self._enabled_plugin_ids = tuple(
                        manifest.id for manifest in target_manifests
                    )
                self._runtime_enabled = requested_enabled
            except Exception as exc:
                self._state_store.set_runtime_enabled(previous_enabled)
                self._runtime_enabled = previous_enabled
                self._runtime = previous_runtime
                self._outbound_files = previous_outbound
                self._enabled_plugin_ids = previous_ids
                return {
                    "ok": False,
                    "error": {
                        "code": "plugin_lifecycle_failed",
                        "message": sanitize_plugin_status_error(exc),
                    },
                }
            if self._state_changed_fn is not None:
                try:
                    self._state_changed_fn()
                except Exception:
                    pass
            return {
                "ok": True,
                "runtime_enabled": requested_enabled,
                "enabled_plugins": list(self._enabled_plugin_ids),
            }

    def run_console_command(
        self,
        *,
        command: object,
        text: object = "",
        session_id: object = None,
        handler: object = "auto",
    ) -> dict[str, object]:
        with self._lifecycle_lock:
            runtime = self._runtime
            closed = self._closed
            runtime_enabled = self._runtime_enabled
        if closed:
            return {
                "ok": False,
                "error": {
                    "code": "plugin_runtime_unavailable",
                    "message": self._error or "Plugin runtime is unavailable",
                },
            }
        if not runtime_enabled:
            return {
                "ok": False,
                "error": {
                    "code": "plugin_runtime_disabled",
                    "message": "Plugin runtime is disabled",
                },
            }
        if runtime is None:
            return {
                "ok": False,
                "error": {
                    "code": "plugin_runtime_unavailable",
                    "message": self._error or "Plugin runtime is unavailable",
                },
            }
        return runtime.run_console_command(
            command=command,
            text=text,
            session_id=session_id,
            handler=handler,
        )

    def set_plugin_route_policy(
        self,
        plugin_id: object,
        *,
        mesh_enabled: bool,
        console_enabled: bool,
        ticker_enabled: bool | None = None,
        view_enabled: bool | None = None,
        expected_package_digest: object,
    ) -> dict[str, object]:
        if self._state_store is None:
            return {
                "ok": False,
                "error": {
                    "code": "plugin_runtime_unavailable",
                    "message": self._error or "Plugin runtime is unavailable",
                },
            }
        clean_id = str(plugin_id or "").strip().lower()
        manifest = next(
            (candidate for candidate in self._manifests if candidate.id == clean_id),
            None,
        )
        if manifest is None:
            return {
                "ok": False,
                "error": {"code": "unknown_plugin", "message": "Unknown plugin ID"},
            }
        expected_digest = str(expected_package_digest or "").strip().lower()
        if expected_digest != manifest.package_digest:
            return {
                "ok": False,
                "error": {
                    "code": "plugin_identity_changed",
                    "message": (
                        "Plugin package revision is stale; refresh the Scripts "
                        "workspace and retry this change"
                    ),
                },
                "package_digest": manifest.package_digest,
            }
        requested_mesh = bool(mesh_enabled)
        requested_console = bool(console_enabled)
        requested_ticker = None if ticker_enabled is None else bool(ticker_enabled)
        requested_view = None if view_enabled is None else bool(view_enabled)
        with self._lifecycle_lock:
            if self._closed:
                return {
                    "ok": False,
                    "error": {
                        "code": "plugin_runtime_unavailable",
                        "message": "Plugin runtime is closed",
                    },
                }
            policy = self._state_store.set_plugin_route_policy(
                clean_id,
                mesh_enabled=requested_mesh,
                console_enabled=requested_console,
                ticker_enabled=requested_ticker,
                view_enabled=requested_view,
            )
            runtime = self._runtime
            if not requested_mesh:
                if runtime is None:
                    self._state_store.clear_sessions_for_plugin(clean_id)
                else:
                    runtime.clear_sessions_for_plugin(clean_id)
            if runtime is not None:
                active_ids = set(self._enabled_plugin_ids)
                runtime.update_route_policy(
                    self._route_policy_for_manifests(
                        [
                            manifest
                            for manifest in self._manifests
                            if manifest.id in active_ids
                        ]
                    )
                )
        if self._state_changed_fn is not None:
            try:
                self._state_changed_fn()
            except Exception:
                pass
        return {
            "ok": True,
            "plugin_id": clean_id,
            "mesh_enabled": policy["mesh_enabled"],
            "console_enabled": policy["console_enabled"],
            "ticker_enabled": policy["ticker_enabled"],
            "view_enabled": policy["view_enabled"],
        }

    def set_plugin_settings(
        self,
        plugin_id: object,
        settings: object,
        *,
        expected_package_digest: object,
    ) -> dict[str, object]:
        if self._state_store is None:
            return {
                "ok": False,
                "error": {
                    "code": "plugin_runtime_unavailable",
                    "message": self._error or "Plugin runtime is unavailable",
                },
            }
        clean_id = str(plugin_id or "").strip().lower()
        manifest = next(
            (candidate for candidate in self._manifests if candidate.id == clean_id),
            None,
        )
        if manifest is None:
            return {
                "ok": False,
                "error": {"code": "unknown_plugin", "message": "Unknown plugin ID"},
            }
        expected_digest = str(expected_package_digest or "").strip().lower()
        if expected_digest != manifest.package_digest:
            return {
                "ok": False,
                "error": {
                    "code": "plugin_identity_changed",
                    "message": (
                        "Plugin package revision is stale; refresh the Scripts "
                        "workspace and retry saving configuration"
                    ),
                },
                "package_digest": manifest.package_digest,
            }
        if not isinstance(settings, Mapping):
            raise ValueError("settings must be an object")
        if not manifest.settings:
            return {
                "ok": False,
                "error": {
                    "code": "plugin_has_no_settings",
                    "message": "This plugin does not declare any settings",
                },
            }
        normalized = normalize_plugin_settings(
            manifest,
            settings,
            require_all=True,
        )
        with self._lifecycle_lock:
            if self._closed:
                return {
                    "ok": False,
                    "error": {
                        "code": "plugin_runtime_unavailable",
                        "message": "Plugin runtime is closed",
                    },
                }
            self._state_store.set_plugin_settings(
                clean_id,
                normalized,
                package_digest=manifest.package_digest,
            )
        if self._state_changed_fn is not None:
            try:
                self._state_changed_fn()
            except Exception:
                pass
        return {
            "ok": True,
            "plugin_id": clean_id,
            "settings": normalized,
        }

    def close(self) -> None:
        with self._lifecycle_lock:
            if self._closed:
                return
            self._closed = True
            runtime = self._runtime
            self._runtime = None
        if self._detach_receive_fn is not None:
            try:
                self._detach_receive_fn()
            except Exception:
                pass
        if runtime is not None:
            runtime.close()
        if self._outbound_files is not None:
            self._outbound_files.close()
        if self._state_store is not None:
            self._state_store.close()


def build_plugin_subsystem(
    *,
    args: object,
    iface: object,
    tracker: object,
    send_chat_fn: Callable[..., object],
    local_node_id_fn: Callable[[], str],
    accept_file_offer_fn: Callable[[Mapping[str, object]], object] | None = None,
) -> PluginSubsystem:
    """Build only after the startup master switch has been checked."""

    state_store: PluginStateStore | None = None
    outbound: OutboundFileTransferService | None = None
    runtime: PluginRuntime | None = None
    try:
        local_directory = str(getattr(args, "plugins_directory", "mesh_dashboard_plugins"))
        included_directory = getattr(
            args,
            "plugins_included_directory",
            Path(__file__).with_name("included_plugins"),
        )
        discovery_errors: list[str] = []
        discovery_error_count = 0

        def _record_discovery_error(exc: Exception) -> None:
            nonlocal discovery_error_count
            discovery_error_count += 1
            if len(discovery_errors) < 32:
                discovery_errors.append(
                    sanitize_plugin_status_error(f"{type(exc).__name__}: {exc}")
                )

        discovered = discover_plugins(
            included_directory,
            local_directory,
            on_error=_record_discovery_error,
        )
        if discovery_error_count > len(discovery_errors):
            discovery_errors.append(
                f"{discovery_error_count - len(discovery_errors)} additional "
                "plugin discovery errors were omitted"
            )
        state_store = PluginStateStore(
            str(getattr(args, "plugins_state_db", "mesh_dashboard_plugin_state.sqlite3"))
        )
        by_id = {manifest.id: manifest for manifest in discovered}
        for manifest in discovered:
            enablement_record = state_store.plugin_enablement_record(manifest.id)
            if (
                enablement_record is None
                or enablement_record[1] == manifest.package_digest
            ):
                continue
            settings_record = state_store.plugin_settings_record(manifest.id)
            migrated_settings: dict[str, object] | None = None
            if (
                settings_record is not None
                and settings_record[1] != manifest.package_digest
            ):
                try:
                    migrated_settings = normalize_plugin_settings(
                        manifest,
                        settings_record[0],
                        require_all=False,
                    )
                except ValueError:
                    migrated_settings = None
            state_store.reconcile_plugin_identity(
                manifest.id,
                package_digest=manifest.package_digest,
                compatible_settings=migrated_settings,
                rebind_settings=migrated_settings is not None,
            )
        for raw_id in list(getattr(args, "plugin_enable", []) or []):
            plugin_id = str(raw_id or "").strip().lower()
            if plugin_id not in by_id:
                _record_discovery_error(
                    ValueError(
                        f"--plugin-enable references unknown plugin {plugin_id!r}"
                    )
                )
                continue
            applied = state_store.set_plugin_enabled_if_identity_matches(
                plugin_id,
                True,
                package_digest=by_id[plugin_id].package_digest,
            )
            if not applied:
                _record_discovery_error(
                    ValueError(
                        f"--plugin-enable could not update stale plugin record "
                        f"{plugin_id!r}; restart Meshyface and retry"
                    )
                )
        for raw_id in list(getattr(args, "plugin_disable", []) or []):
            plugin_id = str(raw_id or "").strip().lower()
            if plugin_id not in by_id:
                _record_discovery_error(
                    ValueError(
                        f"--plugin-disable references unknown plugin {plugin_id!r}"
                    )
                )
                continue
            state_store.set_plugin_enabled_if_identity_matches(
                plugin_id,
                False,
                package_digest=by_id[plugin_id].package_digest,
            )
        runtime_config = PluginRuntimeConfig(
            event_queue_size=max(
                1,
                int(getattr(args, "plugins_event_queue_size", 128)),
            ),
            handler_timeout_seconds=max(
                0.1,
                float(getattr(args, "plugins_handler_timeout", 5.0)),
            ),
            max_inbound_file_bytes=max(
                1,
                int(getattr(args, "file_transfer_max_bytes", 64 * 1024)),
            ),
        )

        def _mark_state_changed() -> None:
            tracker.state_revision = int(getattr(tracker, "state_revision", 0) or 0) + 1

        delivery_state_fn = getattr(tracker, "get_delivery_state", None)

        def _route_policy_for(
            manifests: Sequence[PluginManifest],
        ) -> dict[str, dict[str, bool]]:
            return {
                manifest.id: state_store.plugin_route_policy(manifest.id)
                for manifest in manifests
            }

        def _runtime_factory(
            manifests: Sequence[PluginManifest],
        ) -> tuple[PluginRuntime, OutboundFileTransferService | None]:
            nonlocal outbound
            if outbound is None and bool(getattr(args, "file_transfer_enable", False)):
                resolver = ApprovedPathFileResolver(
                    str(
                        getattr(
                            args,
                            "plugins_files_directory",
                            "mesh_dashboard_plugin_files",
                        )
                    ),
                    max_file_bytes=int(getattr(args, "file_transfer_max_bytes", 64 * 1024)),
                )
                outbound = OutboundFileTransferService(
                    file_resolver=resolver,
                    send_frame_fn=send_chat_fn,
                    max_file_bytes=int(getattr(args, "file_transfer_max_bytes", 64 * 1024)),
                )
            new_runtime = PluginRuntime(
                manifests=manifests,
                state_store=state_store,
                send_chat_fn=send_chat_fn,
                node_snapshot_fn=lambda: _node_snapshot(iface),
                submit_file_fn=outbound.submit if outbound is not None else None,
                accept_file_offer_fn=accept_file_offer_fn,
                get_delivery_state_fn=(
                    delivery_state_fn if callable(delivery_state_fn) else None
                ),
                config=runtime_config,
                route_policy=_route_policy_for(manifests),
                state_changed_fn=_mark_state_changed,
            )
            return new_runtime, outbound

        runtime_enabled = state_store.runtime_enabled(default=True)
        if runtime_enabled:
            enabled = tuple(
                manifest
                for manifest in discovered
                if state_store.plugin_enabled(
                    manifest.id,
                    package_digest=manifest.package_digest,
                    default=manifest.effective_default_enabled,
                )
            )
        else:
            enabled = ()

        if enabled:
            runtime, outbound = _runtime_factory(enabled)

        subsystem = PluginSubsystem(
            state_store=state_store,
            runtime=runtime,
            outbound_files=outbound,
            manifests=discovered,
            enabled_plugin_ids=[manifest.id for manifest in enabled],
            runtime_enabled=runtime_enabled,
            discovery_errors=discovery_errors,
            directory=local_directory,
            runtime_factory=_runtime_factory,
            state_changed_fn=_mark_state_changed,
        )
        add_listener = getattr(tracker, "add_accepted_packet_listener", None)
        remove_listener = getattr(tracker, "remove_accepted_packet_listener", None)
        listener = lambda packet, interface: subsystem.on_receive(  # noqa: E731
            packet,
            interface,
            local_node_id_fn=local_node_id_fn,
        )
        if callable(add_listener):
            add_listener(listener)
            if callable(remove_listener):
                subsystem._detach_receive_fn = lambda: remove_listener(listener)
        return subsystem
    except Exception as exc:
        if runtime is not None:
            runtime.close()
        if outbound is not None:
            outbound.close()
        if state_store is not None:
            state_store.close()
        return PluginSubsystem(
            state_store=None,
            runtime=None,
            outbound_files=None,
            error=f"{type(exc).__name__}: {exc}",
            directory=local_directory,
        )


__all__ = ["PluginSubsystem", "build_plugin_subsystem"]
