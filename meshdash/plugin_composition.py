"""Application composition for the opt-in trusted plugin subsystem."""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from .bots import BotManifest, discover_bots
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
    runtime_status: Mapping[str, object],
) -> tuple[str, str, bool]:
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


class PluginSubsystem:
    def __init__(
        self,
        *,
        state_store: PluginStateStore | None,
        runtime: PluginRuntime | None,
        outbound_files: OutboundFileTransferService | None,
        manifests: Sequence[BotManifest] = (),
        enabled_plugin_ids: Sequence[str] = (),
        error: str = "",
        detach_receive_fn: Callable[[], object] | None = None,
        runtime_factory: (
            Callable[
                [Sequence[BotManifest]],
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
        self._error = sanitize_plugin_status_error(error)
        self._detach_receive_fn = detach_receive_fn
        self._runtime_factory = runtime_factory
        self._state_changed_fn = state_changed_fn
        self._lifecycle_lock = threading.RLock()
        self._closed = False

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
        kind = str(frame.get("kind") or "")
        if kind == "ack":
            service.handle_ack(
                sender_id=sender_id,
                frame=frame,
                channel_index=packet.get("channel"),
            )
        elif kind == "flow":
            service.handle_flow(sender_id=sender_id, frame=frame)

    def status(self) -> dict[str, object]:
        with self._lifecycle_lock:
            runtime = self._runtime
            active_plugin_ids = tuple(self._enabled_plugin_ids)
            active_ids = set(active_plugin_ids)
        runtime_status = runtime.status() if runtime is not None else {}
        configured_enabled: dict[str, bool] = {}
        for manifest in self._manifests:
            if self._state_store is None:
                configured_enabled[manifest.id] = manifest.default_enabled
            else:
                configured_enabled[manifest.id] = self._state_store.plugin_enabled(
                    manifest.id,
                    default=manifest.default_enabled,
                )
        scripts: list[dict[str, object]] = []
        for manifest in self._manifests:
            is_enabled = configured_enabled[manifest.id]
            is_active = manifest.id in active_ids
            health, runtime_error, restart_required = _script_runtime_health(
                plugin_id=manifest.id,
                configured_enabled=is_enabled,
                active=is_active,
                runtime_status=runtime_status,
            )
            scripts.append(
                {
                    "id": manifest.id,
                    "name": manifest.name,
                    "version": manifest.version,
                    "commands": list(manifest.commands),
                    "source": manifest.source,
                    "default_enabled": manifest.default_enabled,
                    "enabled": is_enabled,
                    "active": is_active,
                    "runtime_status": health,
                    "runtime_error": runtime_error,
                    "restart_required": restart_required,
                }
            )
        return {
            "enabled": True,
            "error": self._error,
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

    def set_plugin_enabled(self, plugin_id: object, enabled: bool) -> dict[str, object]:
        if self._state_store is None:
            return {
                "ok": False,
                "error": {
                    "code": "plugin_runtime_unavailable",
                    "message": self._error or "Plugin runtime is unavailable",
                },
            }
        clean_id = str(plugin_id or "").strip().lower()
        known_ids = {manifest.id for manifest in self._manifests}
        if clean_id not in known_ids:
            return {
                "ok": False,
                "error": {"code": "unknown_plugin", "message": "Unknown plugin ID"},
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
                default=next(
                    manifest.default_enabled
                    for manifest in self._manifests
                    if manifest.id == clean_id
                ),
            )
            self._state_store.set_plugin_enabled(clean_id, requested_enabled)
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
                        runtime.reconfigure(target_manifests)
                elif runtime is not None:
                    runtime.reconfigure(())
                    runtime.close()
                    self._runtime = None
                self._enabled_plugin_ids = tuple(manifest.id for manifest in target_manifests)
            except Exception as exc:
                self._state_store.set_plugin_enabled(clean_id, previous_setting)
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
                "plugin_id": clean_id,
                "enabled": requested_enabled,
                "active": requested_enabled,
                "restart_required": False,
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
) -> PluginSubsystem:
    """Build only after the startup master switch has been checked."""

    state_store: PluginStateStore | None = None
    outbound: OutboundFileTransferService | None = None
    runtime: PluginRuntime | None = None
    try:
        local_directory = str(getattr(args, "bots_directory", "mesh_dashboard_plugins"))
        included_directory = Path(__file__).with_name("included_bots")
        discovered = discover_bots(included_directory, local_directory)
        state_store = PluginStateStore(
            str(getattr(args, "bots_state_db", "mesh_dashboard_plugin_state.sqlite3"))
        )
        by_id = {manifest.id: manifest for manifest in discovered}
        for raw_id in list(getattr(args, "bot_enable", []) or []):
            plugin_id = str(raw_id or "").strip().lower()
            if plugin_id not in by_id:
                raise ValueError(f"--bot-enable references unknown plugin {plugin_id!r}")
            state_store.set_plugin_enabled(plugin_id, True)
        for raw_id in list(getattr(args, "bot_disable", []) or []):
            plugin_id = str(raw_id or "").strip().lower()
            if plugin_id not in by_id:
                raise ValueError(f"--bot-disable references unknown plugin {plugin_id!r}")
            state_store.set_plugin_enabled(plugin_id, False)
        enabled = tuple(
            manifest
            for manifest in discovered
            if state_store.plugin_enabled(manifest.id, default=manifest.default_enabled)
        )
        runtime_config = PluginRuntimeConfig(
            event_queue_size=max(
                1,
                int(getattr(args, "bots_event_queue_size", 128)),
            ),
            handler_timeout_seconds=max(
                0.1,
                float(getattr(args, "bots_handler_timeout", 5.0)),
            ),
        )

        def _runtime_factory(
            manifests: Sequence[BotManifest],
        ) -> tuple[PluginRuntime, OutboundFileTransferService | None]:
            nonlocal outbound
            if outbound is None and bool(getattr(args, "file_transfer_enable", False)):
                resolver = ApprovedPathFileResolver(
                    str(
                        getattr(
                            args,
                            "bots_files_directory",
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
                config=runtime_config,
            )
            return new_runtime, outbound

        if enabled:
            runtime, outbound = _runtime_factory(enabled)

        def _mark_state_changed() -> None:
            tracker.state_revision = int(getattr(tracker, "state_revision", 0) or 0) + 1

        subsystem = PluginSubsystem(
            state_store=state_store,
            runtime=runtime,
            outbound_files=outbound,
            manifests=discovered,
            enabled_plugin_ids=[manifest.id for manifest in enabled],
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
        )


__all__ = ["PluginSubsystem", "build_plugin_subsystem"]
