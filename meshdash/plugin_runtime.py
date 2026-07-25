"""Host-side supervision, routing, state, and action execution for plugins."""

from __future__ import annotations

import json
import math
import multiprocessing
import queue
import re
import signal
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import cast

from .plugins import (
    AcceptFileOfferAction,
    ScriptAction,
    PluginManifest,
    MessageEvent,
    ReplyAction,
    SendChannelAction,
    SendFileAction,
    SendTextAction,
    SessionAction,
    action_from_dict,
    normalize_plugin_settings,
)
from .helpers_json import JsonValue, to_jsonable
from .file_transfer_protocol import (
    FILE_TRANSFER_CHUNK_BYTES,
    FILE_TRANSFER_MAX_CHUNKS,
    FILE_TRANSFER_MAX_WIRE_BYTES,
)
from .config import DEFAULT_FILE_TRANSFER_MAX_BYTES
from .plugin_protocol import MAX_PROTOCOL_FRAME_BYTES, decode_message, encode_message
from .plugin_state import PluginStateQuotaExceeded, PluginStateStore
from .plugin_worker import plugin_worker_main


_NODE_ID_RE = re.compile(r"![0-9a-f]{8}\Z")
_COMMAND_RE = re.compile(r"!([a-z][a-z0-9_-]{0,31})(?:\s|\Z)", re.IGNORECASE)
_COMMAND_NAME_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
_TICKER_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
_VIEW_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
_VIEW_ICON_RE = re.compile(r"[A-Z0-9]{1,4}\Z")
_NODE_FIELD_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
_NODE_FIELD_VALUE_TYPES = frozenset({"text", "number", "integer", "timestamp", "boolean"})
_NODE_FIELD_RENDER_KINDS = frozenset(
    {"text", "chip", "pill", "badge", "metric", "bar", "sparkline", "timestamp", "icon"}
)
_MESH_ACCESS_VALUES = frozenset({"none", "read_only", "read_write", "unknown"})
_QUIT_COMMANDS = {"!quit", "!exit"}
_RESERVED_NODE_IDS = {"!00000000", "!ffffffff"}
_ACKED_DELIVERY_STATES = {"ack", "acked", "delivered"}
_QUEUE_STOP = object()
_CONSOLE_LOCAL_NODE_ID = "!7a000001"
_ABSOLUTE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:[A-Za-z]:[\\/]|/)"
    r"(?:[^\\/\s:;,'\"()<>\[\]{}]+[\\/])*"
    r"[^\\/\s:;,'\"()<>\[\]{}]+"
)


@dataclass(frozen=True)
class PluginRuntimeConfig:
    event_queue_size: int = 128
    control_queue_size: int = 16
    action_queue_size: int = 128
    startup_timeout_seconds: float = 10.0
    handler_timeout_seconds: float = 5.0
    restart_backoff_seconds: float = 0.25
    max_restart_backoff_seconds: float = 30.0
    max_action_text_bytes: int = 4096
    chat_max_bytes: int = 200
    max_inbound_file_bytes: int = DEFAULT_FILE_TRANSFER_MAX_BYTES
    long_reply_pace_seconds: float = 1.0
    long_reply_ack_wait_seconds: float = 25.0
    long_reply_ack_poll_seconds: float = 0.5
    long_reply_retry_limit: int = 1
    max_actions_per_minute: int = 60
    max_synchronous_radio_frames_per_batch: int = 64
    max_radio_frames_per_minute: int = 2048
    max_radio_bytes_per_minute: int = 512 * 1024
    max_global_radio_frames_per_minute: int = 4096
    max_global_radio_bytes_per_minute: int = 1024 * 1024


@dataclass(frozen=True)
class _Invocation:
    plugin_id: str
    handler: str
    event: MessageEvent
    command: str = ""


@dataclass(frozen=True)
class _QueuedAction:
    plugin_id: str
    event: MessageEvent
    action: ScriptAction
    radio_frames: int = 0
    radio_bytes: int = 0


@dataclass(frozen=True)
class _RoutePolicy:
    mesh_enabled: bool = True
    console_enabled: bool = True


@dataclass
class _QueuedActionBatch:
    actions: tuple[_QueuedAction, ...]
    ready: threading.Event
    canceled: bool = False


@dataclass
class _ReconfigureRequest:
    manifests: tuple[PluginManifest, ...]
    manifest_by_id: dict[str, PluginManifest]
    command_plugins: dict[str, str]
    route_policy: dict[str, _RoutePolicy]
    ready: threading.Event
    error: str = ""


@dataclass
class _ConsoleInvocationRequest:
    plugin_id: str
    command: str
    event: MessageEvent
    session_id: str
    handler: str
    ready: threading.Event
    actions: list[ScriptAction] = field(default_factory=list)
    ok: bool = False
    error_code: str = ""
    error_message: str = ""
    active_session: bool = False


def _validated_manifest_configuration(
    manifests: Sequence[PluginManifest],
    *,
    allow_empty: bool = False,
) -> tuple[tuple[PluginManifest, ...], dict[str, PluginManifest], dict[str, str]]:
    configured = tuple(manifests)
    if not configured and not allow_empty:
        raise ValueError("at least one enabled plugin manifest is required")
    if len(configured) > 64:
        raise ValueError("at most 64 plugins may be enabled")
    manifest_by_id = {manifest.id: manifest for manifest in configured}
    if len(manifest_by_id) != len(configured):
        raise ValueError("plugin IDs must be unique")
    command_plugins: dict[str, str] = {}
    for manifest in configured:
        for command in manifest.commands:
            previous = command_plugins.get(command)
            if previous is not None:
                raise ValueError(
                    f"command {command!r} is declared by both {previous!r} and {manifest.id!r}"
                )
            command_plugins[command] = manifest.id
    return configured, manifest_by_id, command_plugins


def _validated_route_policy(
    manifest_by_id: Mapping[str, PluginManifest],
    route_policy: Mapping[str, Mapping[str, object]] | None,
) -> dict[str, _RoutePolicy]:
    policies: dict[str, _RoutePolicy] = {}
    for plugin_id in manifest_by_id:
        raw = route_policy.get(plugin_id) if route_policy is not None else None
        if isinstance(raw, Mapping):
            policies[plugin_id] = _RoutePolicy(
                mesh_enabled=bool(raw.get("mesh_enabled", True)),
                console_enabled=bool(raw.get("console_enabled", True)),
            )
        else:
            policies[plugin_id] = _RoutePolicy()
    return policies


def _manifest_payload(manifest: PluginManifest) -> dict[str, JsonValue]:
    return {
        "api_version": manifest.api_version,
        "id": manifest.id,
        "name": manifest.name,
        "version": manifest.version,
        "package_digest": manifest.package_digest,
        "entrypoint": manifest.entrypoint,
        "commands": list(manifest.commands),
        "default_enabled": manifest.default_enabled,
        "manifest_path": str(manifest.manifest_path),
        "plugin_directory": str(manifest.plugin_directory),
        "entrypoint_path": str(manifest.entrypoint_path),
        "entrypoint_object": manifest.entrypoint_object,
        "source": manifest.source,
        "views": [definition.to_dict(include_content=False) for definition in manifest.views],
    }


def _validated_mesh_access(value: object) -> str:
    clean = str(value or "").strip().lower()
    return clean if clean in _MESH_ACCESS_VALUES else "unknown"


def _system_event() -> MessageEvent:
    return MessageEvent(
        text="",
        sender_id="system",
        destination_id="system",
        local_node_id="system",
        channel_index=0,
        is_direct=False,
        is_broadcast=False,
        packet_id=0,
        reply_packet_id=None,
        received_at=time.time(),
    )


def _console_peer_id(plugin_id: str, session_id: str) -> str:
    token = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"meshyface:plugin-console:{plugin_id}:{session_id}",
    ).hex[:8]
    return f"!{token}"


def _console_command_text(command: str, text: object) -> str:
    clean_text = str(text or "").strip()
    if not clean_text:
        return f"!{command}"
    match = _COMMAND_RE.match(clean_text)
    if match and match.group(1).lower() == command:
        return clean_text
    if clean_text.lower() == command:
        return f"!{command}"
    if clean_text.lower().startswith(f"{command} "):
        return f"!{clean_text}"
    return f"!{command} {clean_text}"


def _console_action_summary(action: ScriptAction) -> dict[str, JsonValue]:
    if isinstance(action, ReplyAction):
        return {"type": "reply", "text": action.text, "long": action.long}
    if isinstance(action, SendTextAction):
        return {"type": "send_text", "suppressed": True}
    if isinstance(action, SendChannelAction):
        return {"type": "send_channel", "suppressed": True}
    if isinstance(action, SendFileAction):
        return {"type": "send_file", "suppressed": True}
    if isinstance(action, AcceptFileOfferAction):
        return {"type": "accept_file_offer", "suppressed": True}
    if isinstance(action, SessionAction):
        return {"type": "session", "operation": action.operation}
    return {"type": "unknown", "suppressed": True}


def sanitize_plugin_status_error(value: object) -> str:
    """Return a bounded single-line error that cannot expose an absolute path."""

    compact = " ".join(str(value or "").split()).strip()
    if not compact:
        return ""
    scrubbed = _ABSOLUTE_PATH_RE.sub("[path]", compact)
    if len(scrubbed) > 512:
        return f"{scrubbed[:509]}..."
    return scrubbed


def _terminal_safe_text(value: object) -> str:
    """Escape terminal control bytes while preserving printable Unicode."""

    escaped: list[str] = []
    for character in str(value):
        codepoint = ord(character)
        if character == "\n":
            escaped.append(r"\n")
        elif character == "\r":
            escaped.append(r"\r")
        elif character == "\t":
            escaped.append(r"\t")
        elif codepoint < 0x20 or 0x7F <= codepoint <= 0x9F:
            escaped.append(f"\\x{codepoint:02x}")
        else:
            escaped.append(character)
    return "".join(escaped)


def _utf8_segments(text: str, maximum_bytes: int) -> list[str]:
    if maximum_bytes <= 0:
        raise ValueError("maximum_bytes must be positive")
    remaining = str(text)
    segments: list[str] = []
    while remaining:
        used = 0
        end = 0
        for index, character in enumerate(remaining):
            size = len(character.encode("utf-8"))
            if used + size > maximum_bytes:
                break
            used += size
            end = index + 1
        if end <= 0:
            raise ValueError("chat byte limit cannot fit one Unicode character")
        if end < len(remaining):
            whitespace = max(remaining.rfind(" ", 0, end), remaining.rfind("\n", 0, end))
            if whitespace > 0:
                end = whitespace + 1
        segment = remaining[:end].strip()
        remaining = remaining[end:].lstrip()
        if segment:
            segments.append(segment)
    return segments


def _numbered_utf8_segments(text: str, maximum_bytes: int) -> list[str]:
    segments = _utf8_segments(text, maximum_bytes)
    if len(segments) <= 1:
        return segments

    total = len(segments)
    for _attempt in range(8):
        prefix_bytes = len(f"[{total}/{total}] ".encode("utf-8"))
        if prefix_bytes >= maximum_bytes:
            return segments
        next_segments = _utf8_segments(text, maximum_bytes - prefix_bytes)
        next_total = len(next_segments)
        segments = next_segments
        if next_total == total:
            break
        total = next_total

    total = len(segments)
    return [
        f"[{index}/{total}] {segment}"
        for index, segment in enumerate(segments, start=1)
    ]


def _sent_message_id(send_result: object) -> int | None:
    if not isinstance(send_result, Mapping):
        return None
    raw_message_id = (
        send_result.get("message_id")
        or send_result.get("packet_id")
        or send_result.get("messageId")
        or send_result.get("packetId")
    )
    if isinstance(raw_message_id, bool):
        return None
    try:
        message_id = int(raw_message_id)
    except (TypeError, ValueError, OverflowError):
        return None
    return message_id if message_id > 0 else None


class PluginRuntime:
    """Own one spawned worker and keep all host objects in the parent process."""

    def __init__(
        self,
        *,
        manifests: Sequence[PluginManifest],
        state_store: PluginStateStore,
        send_chat_fn: Callable[..., object],
        node_snapshot_fn: Callable[[], Sequence[Mapping[str, object]]] = tuple,
        submit_file_fn: Callable[..., object] | None = None,
        accept_file_offer_fn: Callable[[Mapping[str, JsonValue]], object] | None = None,
        get_delivery_state_fn: Callable[[object], object] | None = None,
        config: PluginRuntimeConfig = PluginRuntimeConfig(),
        route_policy: Mapping[str, Mapping[str, object]] | None = None,
        mp_context: object | None = None,
        monotonic_fn: Callable[[], float] = time.monotonic,
        state_changed_fn: Callable[[], object] | None = None,
    ) -> None:
        (
            self._manifests,
            self._manifest_by_id,
            self._command_plugins,
        ) = _validated_manifest_configuration(manifests)
        self._state_store = state_store
        self._send_chat_fn = send_chat_fn
        self._node_snapshot_fn = node_snapshot_fn
        self._submit_file_fn = submit_file_fn
        self._accept_file_offer_fn = accept_file_offer_fn
        self._get_delivery_state_fn = get_delivery_state_fn
        self._config = config
        self._route_policy_lock = threading.Lock()
        self._route_policy = _validated_route_policy(
            self._manifest_by_id,
            route_policy,
        )
        self._mp = mp_context or multiprocessing.get_context("spawn")
        self._monotonic_fn = monotonic_fn
        self._state_changed_fn = state_changed_fn
        self._event_queue: queue.Queue[object] = queue.Queue(
            maxsize=max(1, int(config.event_queue_size))
        )
        self._control_queue: queue.Queue[object] = queue.Queue(
            maxsize=max(1, int(config.control_queue_size))
        )
        self._action_queue: queue.Queue[object] = queue.Queue(
            maxsize=max(1, int(config.action_queue_size))
        )
        self._console_queue: queue.Queue[object] = queue.Queue(
            maxsize=max(1, int(config.control_queue_size))
        )
        self._management_queue: queue.Queue[_ReconfigureRequest] = queue.Queue(maxsize=4)
        self._stop = threading.Event()
        self._closing = threading.Event()
        self._status_lock = threading.Lock()
        self._registry: dict[str, dict[str, object]] = {}
        self._ticker_values: dict[tuple[str, str], dict[str, object]] = {}
        self._process: object | None = None
        self._connection: object | None = None
        self._worker_ready = False
        self._worker_plugin_ids: frozenset[str] = frozenset()
        self._generation = 0
        self._dropped_events = 0
        self._dropped_control_events = 0
        self._dropped_actions = 0
        self._timeouts = 0
        self._crashes = 0
        self._restarts = 0
        self._last_error = ""
        self._current_plugin = ""
        self._debug_sequence = 0
        self._debug_records: deque[dict[str, JsonValue]] = deque(maxlen=50)
        self._plugin_failures: dict[str, int] = {}
        self._plugin_last_errors: dict[str, str] = {}
        self._plugin_quarantined_until: dict[str, float] = {}
        self._startup_quarantined_identities: dict[str, str] = {}
        self._action_times: dict[str, deque[float]] = {}
        self._radio_usage: dict[str, deque[tuple[float, int, int]]] = {}
        self._global_radio_usage: deque[tuple[float, int, int]] = deque()
        self._admission_lock = threading.Lock()
        self._worker_start_failures = 0
        self._next_worker_attempt_at = 0.0
        self._started_generation = 0
        self._session_lock = threading.Lock()
        self._sessions = {
            (local_node_id, peer_id, channel_index): plugin_id
            for local_node_id, peer_id, channel_index, plugin_id in state_store.list_sessions()
        }
        self._session_versions: dict[tuple[str, str, int], int] = {}
        self._dispatcher = threading.Thread(
            target=self._dispatch_loop,
            name="meshyface-plugin-dispatcher",
            daemon=True,
        )
        self._action_worker = threading.Thread(
            target=self._action_loop,
            name="meshyface-plugin-actions",
            daemon=True,
        )
        self._control_worker = threading.Thread(
            target=self._control_loop,
            name="meshyface-plugin-controls",
            daemon=True,
        )
        self._dispatcher.start()
        self._action_worker.start()
        self._control_worker.start()

    def try_enqueue(self, event: MessageEvent) -> bool:
        """Route one already-accepted event without blocking its receive callback."""

        if self._stop.is_set() or self._closing.is_set() or not self._manifests:
            return False
        clean_text = event.text.strip()
        if event.is_direct and clean_text.lower() in _QUIT_COMMANDS:
            try:
                self._control_queue.put_nowait(event)
                return True
            except queue.Full:
                with self._status_lock:
                    self._dropped_control_events += 1
                return False
        try:
            self._event_queue.put_nowait(event)
            return True
        except queue.Full:
            with self._status_lock:
                self._dropped_events += 1
            return False

    def run_console_command(
        self,
        *,
        command: object,
        text: object = "",
        session_id: object = None,
        handler: object = "auto",
    ) -> dict[str, object]:
        """Invoke one manifest-declared command through a local direct-message session."""

        if self._stop.is_set() or self._closing.is_set():
            return {
                "ok": False,
                "error": {
                    "code": "plugin_runtime_unavailable",
                    "message": "Plugin runtime is closing",
                },
            }
        clean_command = str(command or "").strip().lower()
        if _COMMAND_NAME_RE.fullmatch(clean_command) is None:
            return {
                "ok": False,
                "error": {
                    "code": "invalid_command",
                    "message": "Plugin command must match [a-z][a-z0-9_-]{0,31}",
                },
            }
        clean_handler = str(handler or "auto").strip().lower() or "auto"
        if clean_handler not in {"auto", "command", "session", "message"}:
            return {
                "ok": False,
                "error": {
                    "code": "invalid_handler",
                    "message": "Plugin console handler must be auto, command, session, or message",
                },
            }
        plugin_id = self._command_plugins.get(clean_command)
        if not plugin_id:
            return {
                "ok": False,
                "error": {
                    "code": "unknown_command",
                    "message": "No enabled plugin declares that command",
                },
            }
        if not self._console_route_enabled(plugin_id):
            return {
                "ok": False,
                "error": {
                    "code": "plugin_console_disabled",
                    "message": "Plugin console route is disabled",
                },
            }
        clean_text = str(text or "").strip()
        if not clean_text and clean_handler != "command":
            return {
                "ok": False,
                "error": {"code": "empty_command", "message": "Enter a command."},
            }
        if len(clean_text.encode("utf-8")) > self._config.max_action_text_bytes:
            return {
                "ok": False,
                "error": {
                    "code": "invalid_request",
                    "message": "Plugin console command is too large",
                },
            }
        clean_session_id = str(session_id or "").strip()[:128] or uuid.uuid4().hex
        event_text = (
            _console_command_text(clean_command, clean_text)
            if clean_handler == "command"
            else clean_text
        )
        event = MessageEvent(
            text=event_text,
            sender_id=_console_peer_id(plugin_id, clean_session_id),
            destination_id=_CONSOLE_LOCAL_NODE_ID,
            local_node_id=_CONSOLE_LOCAL_NODE_ID,
            channel_index=0,
            is_direct=True,
            is_broadcast=False,
            packet_id=0,
            reply_packet_id=None,
            received_at=time.time(),
            portnum="TEXT_MESSAGE_APP",
        )
        request = _ConsoleInvocationRequest(
            plugin_id=plugin_id,
            command=clean_command,
            event=event,
            session_id=clean_session_id,
            handler=clean_handler,
            ready=threading.Event(),
        )
        try:
            self._console_queue.put_nowait(request)
        except queue.Full:
            return {
                "ok": False,
                "error": {
                    "code": "plugin_console_busy",
                    "message": "Plugin console queue is full",
                },
            }
        wait_seconds = max(
            2.0,
            self._config.startup_timeout_seconds
            + self._config.handler_timeout_seconds
            + 1.0,
        )
        if not request.ready.wait(timeout=wait_seconds):
            return {
                "ok": False,
                "session_id": clean_session_id,
                "plugin_id": plugin_id,
                "command": clean_command,
                "active_session": False,
                "error": {
                    "code": "plugin_console_timeout",
                    "message": "Plugin console command timed out",
                },
            }
        response: dict[str, object] = {
            "ok": request.ok,
            "session_id": clean_session_id,
            "plugin_id": plugin_id,
            "command": clean_command,
            "active_session": request.active_session,
            "actions": [_console_action_summary(action) for action in request.actions],
            "reply_text": "\n".join(
                action.text
                for action in request.actions
                if isinstance(action, ReplyAction)
            ).strip(),
        }
        if not request.ok:
            response["error"] = {
                "code": request.error_code or "plugin_console_failed",
                "message": request.error_message or "Plugin console command failed",
            }
        return response

    def reconfigure(
        self,
        manifests: Sequence[PluginManifest],
        *,
        route_policy: Mapping[str, Mapping[str, object]] | None = None,
    ) -> None:
        """Replace the enabled plugin set without restarting MeshyFace."""

        configured, manifest_by_id, command_plugins = _validated_manifest_configuration(
            manifests,
            allow_empty=True,
        )
        if self._closing.is_set() or self._stop.is_set():
            raise RuntimeError("plugin runtime is closing")
        request = _ReconfigureRequest(
            manifests=configured,
            manifest_by_id=manifest_by_id,
            command_plugins=command_plugins,
            route_policy=_validated_route_policy(manifest_by_id, route_policy),
            ready=threading.Event(),
        )
        try:
            self._management_queue.put(request, timeout=1.0)
        except queue.Full as exc:
            raise RuntimeError("plugin runtime management queue is full") from exc
        wait_seconds = max(
            2.0,
            self._config.startup_timeout_seconds + self._config.handler_timeout_seconds + 1.0,
        )
        if not request.ready.wait(timeout=wait_seconds):
            raise TimeoutError("plugin runtime reconfiguration timed out")
        if request.error:
            raise RuntimeError(request.error)

    def clear_sessions_for_plugin(self, plugin_id: object) -> int:
        """Clear durable and in-memory conversations for one plugin."""

        clean_plugin = str(plugin_id or "").strip().lower()
        with self._session_lock:
            removed_from_store = self._state_store.clear_sessions_for_plugin(
                clean_plugin
            )
            session_keys = [
                key
                for key, active_plugin in self._sessions.items()
                if active_plugin == clean_plugin
            ]
            for key in session_keys:
                self._session_versions[key] = self._session_versions.get(key, 0) + 1
                self._sessions.pop(key, None)
        return max(removed_from_store, len(session_keys))

    def update_route_policy(
        self,
        route_policy: Mapping[str, Mapping[str, object]],
    ) -> None:
        with self._route_policy_lock:
            self._route_policy = _validated_route_policy(
                self._manifest_by_id,
                route_policy,
            )

    def _route_enabled(self, plugin_id: str, route: str) -> bool:
        with self._route_policy_lock:
            policy = self._route_policy.get(plugin_id, _RoutePolicy())
        if route == "mesh":
            return policy.mesh_enabled
        if route == "console":
            return policy.console_enabled
        return True

    def _mesh_route_enabled(self, plugin_id: str) -> bool:
        return self._route_enabled(plugin_id, "mesh")

    def _console_route_enabled(self, plugin_id: str) -> bool:
        return self._route_enabled(plugin_id, "console")

    def _route_event(self, event: MessageEvent) -> tuple[_Invocation, ...]:
        if event.packet is not None:
            with self._status_lock:
                packet_plugins = [
                    plugin_id
                    for plugin_id, registration in self._registry.items()
                    if (
                        bool(registration.get("on_packet"))
                        and not registration.get("error")
                        and self._mesh_route_enabled(plugin_id)
                    )
                ]
            return tuple(_Invocation(plugin_id, "packet", event) for plugin_id in packet_plugins)
        clean_text = event.text.strip()
        command_match = _COMMAND_RE.match(clean_text)
        invocations: list[_Invocation] = []
        if command_match:
            command = command_match.group(1).lower()
            plugin_id = self._command_plugins.get(command)
            if plugin_id and self._mesh_route_enabled(plugin_id):
                invocations.append(_Invocation(plugin_id, "command", event, command))
            else:
                return ()
        if not invocations and event.is_direct:
            with self._session_lock:
                session_plugin = self._sessions.get(
                    (
                        event.local_node_id,
                        event.sender_id,
                        event.channel_index,
                    )
                )
            registration = self._registry.get(session_plugin or "", {})
            if (
                session_plugin
                and bool(registration.get("session"))
                and self._mesh_route_enabled(session_plugin)
            ):
                invocations.append(_Invocation(session_plugin, "session", event))
        if not invocations:
            with self._status_lock:
                message_plugins = [
                    plugin_id
                    for plugin_id, registration in self._registry.items()
                    if (
                        bool(registration.get("on_message"))
                        and not registration.get("error")
                        and self._mesh_route_enabled(plugin_id)
                    )
                ]
            invocations.extend(
                _Invocation(plugin_id, "message", event) for plugin_id in message_plugins
            )
        return tuple(invocations)

    def status(self) -> dict[str, object]:
        with self._status_lock:
            process = self._process
            pid = getattr(process, "pid", None) if process is not None else None
            alive_fn = getattr(process, "is_alive", None)
            alive = bool(alive_fn()) if callable(alive_fn) else False
            ready = self._worker_ready
            if self._closing.is_set() or self._stop.is_set():
                runtime_status = "stopped"
            elif not self._manifests:
                runtime_status = "stopped"
            elif alive and ready:
                runtime_status = "running"
            elif alive or (self._generation == 0 and not self._last_error):
                runtime_status = "starting"
            else:
                runtime_status = "error"
            plugins: dict[str, dict[str, object]] = {}
            tickers: list[dict[str, object]] = []
            node_fields: list[dict[str, object]] = []
            for plugin_id, registration in self._registry.items():
                public_registration = dict(registration)
                registration_error = sanitize_plugin_status_error(registration.get("error"))
                last_error = sanitize_plugin_status_error(registration.get("last_error"))
                if registration_error:
                    public_registration["error"] = registration_error
                    plugin_status = "error"
                elif runtime_status == "running":
                    plugin_status = "running"
                elif runtime_status == "starting":
                    plugin_status = "starting"
                elif runtime_status == "stopped":
                    plugin_status = "stopped"
                else:
                    plugin_status = "error"
                if last_error:
                    public_registration["last_error"] = last_error
                public_registration["runtime_status"] = plugin_status
                plugins[plugin_id] = public_registration
                definitions = registration.get("tickers")
                if isinstance(definitions, list):
                    for definition in definitions:
                        if not isinstance(definition, Mapping):
                            continue
                        ticker_id = str(definition.get("id") or "").strip().lower()
                        if not ticker_id:
                            continue
                        value = self._ticker_values.get((plugin_id, ticker_id), {})
                        tickers.append(
                            {
                                "id": f"script:{plugin_id}:{ticker_id}",
                                "plugin_id": plugin_id,
                                "ticker_id": ticker_id,
                                "label": str(definition.get("label") or ticker_id),
                                "metric": bool(definition.get("metric", False)),
                                "default_enabled": bool(
                                    definition.get("default_enabled", True)
                                ),
                                "value": value.get("value", "n/a"),
                                "rows": list(value.get("rows", []))
                                if isinstance(value.get("rows"), list)
                                else [],
                                "state": str(value.get("state") or "neutral"),
                                "detail": str(value.get("detail") or ""),
                                "metric_value": value.get("metric_value"),
                                "updated_at": value.get("updated_at"),
                                "runtime_status": plugin_status,
                            }
                        )
                field_definitions = registration.get("node_fields")
                if isinstance(field_definitions, list):
                    for definition in field_definitions:
                        if not isinstance(definition, Mapping):
                            continue
                        field_id = str(definition.get("id") or "").strip().lower()
                        if not field_id:
                            continue
                        render_kinds = definition.get("render_kinds")
                        node_fields.append(
                            {
                                "id": f"plugin:{plugin_id}:{field_id}",
                                "plugin_id": plugin_id,
                                "field_id": field_id,
                                "label": str(definition.get("label") or field_id),
                                "group": str(definition.get("group") or "Plugins"),
                                "value_type": str(definition.get("value_type") or "text"),
                                "render_kinds": list(render_kinds)
                                if isinstance(render_kinds, list)
                                else [],
                                "default_render_kind": str(
                                    definition.get("default_render_kind") or "text"
                                ),
                                "default_visible": bool(
                                    definition.get("default_visible", False)
                                ),
                                "sortable": bool(definition.get("sortable", False)),
                                "runtime_status": plugin_status,
                            }
                        )
            return {
                "enabled": True,
                "status": runtime_status,
                "worker_alive": alive,
                "worker_ready": ready,
                "worker_pid": pid,
                "generation": self._generation,
                "queue_depth": self._event_queue.qsize(),
                "control_queue_depth": self._control_queue.qsize(),
                "action_queue_depth": self._action_queue.qsize(),
                "dropped_events": self._dropped_events,
                "dropped_control_events": self._dropped_control_events,
                "dropped_actions": self._dropped_actions,
                "timeouts": self._timeouts,
                "crashes": self._crashes,
                "restarts": self._restarts,
                "consecutive_start_failures": self._worker_start_failures,
                "next_restart_in_seconds": max(
                    0.0,
                    self._next_worker_attempt_at - self._monotonic_fn(),
                ),
                "current_plugin": self._current_plugin,
                "last_error": sanitize_plugin_status_error(self._last_error),
                "debug_sequence": self._debug_sequence,
                "debug": list(self._debug_records),
                "plugins": plugins,
                "tickers": tickers,
                "node_fields": node_fields,
            }

    def close(self) -> None:
        if self._closing.is_set():
            return
        self._closing.set()
        while True:
            try:
                self._event_queue.get_nowait()
            except queue.Empty:
                break
        while True:
            try:
                self._control_queue.get_nowait()
            except queue.Empty:
                break
        while True:
            try:
                item = self._console_queue.get_nowait()
            except queue.Empty:
                break
            if isinstance(item, _ConsoleInvocationRequest):
                item.error_code = "plugin_runtime_unavailable"
                item.error_message = "Plugin runtime is closing"
                item.ready.set()
        try:
            self._event_queue.put(_QUEUE_STOP, timeout=1.0)
        except queue.Full:
            pass
        try:
            self._control_queue.put(_QUEUE_STOP, timeout=1.0)
        except queue.Full:
            pass
        self._dispatcher.join(timeout=max(1.0, self._config.handler_timeout_seconds + 0.5))
        self._stop.set()
        self._stop_worker()
        try:
            self._action_queue.put_nowait(_QUEUE_STOP)
        except queue.Full:
            pass
        self._control_worker.join(timeout=2.0)
        self._action_worker.join(timeout=2.0)

    def _queue_action(self, queued: _QueuedAction) -> bool:
        ready = threading.Event()
        ready.set()
        batch = _QueuedActionBatch((queued,), ready)
        try:
            self._action_queue.put_nowait(batch)
            return True
        except queue.Full:
            with self._status_lock:
                self._dropped_actions += 1
            return False

    def _dispatch_loop(self) -> None:
        while not self._stop.is_set():
            try:
                management_request = self._management_queue.get_nowait()
            except queue.Empty:
                management_request = None
            if management_request is not None:
                self._apply_reconfiguration(management_request)
                continue
            if not self._manifests:
                if self._closing.is_set():
                    return
                try:
                    management_request = self._management_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                self._apply_reconfiguration(management_request)
                continue
            if not self._ensure_worker():
                retry_wait = max(
                    0.05,
                    self._next_worker_attempt_at - self._monotonic_fn(),
                )
                # Poll management requests and shutdown promptly even during a
                # long exponential restart delay.
                if self._stop.wait(min(0.5, retry_wait)):
                    return
                continue
            if self._started_generation != self._generation:
                self._started_generation = self._generation
                for plugin_id, registration in list(self._registry.items()):
                    if registration.get("on_start") and not self._is_quarantined(plugin_id):
                        if not self._invoke(_Invocation(plugin_id, "start", _system_event())):
                            break
                continue
            try:
                console_request = self._console_queue.get_nowait()
            except queue.Empty:
                console_request = None
            if isinstance(console_request, _ConsoleInvocationRequest):
                self._handle_console_invocation(console_request)
                continue
            try:
                item = self._event_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if item is _QUEUE_STOP:
                for plugin_id, registration in list(self._registry.items()):
                    if registration.get("on_stop") and not self._is_quarantined(plugin_id):
                        if not self._invoke(_Invocation(plugin_id, "stop", _system_event())):
                            break
                return
            if not isinstance(item, MessageEvent):
                continue
            for invocation in self._route_event(item):
                if self._is_quarantined(invocation.plugin_id):
                    continue
                if not self._invoke(invocation):
                    break

    def _apply_reconfiguration(self, request: _ReconfigureRequest) -> None:
        try:
            # A disabled plugin must not finish queued handlers or emit later actions.
            # Publish the new registry before terminating the shared worker so the
            # action thread rejects queued work from a newly disabled plugin.
            self._manifests = request.manifests
            self._manifest_by_id = request.manifest_by_id
            self._command_plugins = request.command_plugins
            with self._route_policy_lock:
                self._route_policy = request.route_policy
            self._stop_worker(force=True)
            self._started_generation = self._generation
            enabled_ids = set(self._manifest_by_id)
            self._plugin_failures = {
                plugin_id: failures
                for plugin_id, failures in self._plugin_failures.items()
                if plugin_id in enabled_ids
            }
            self._plugin_last_errors = {
                plugin_id: error
                for plugin_id, error in self._plugin_last_errors.items()
                if plugin_id in enabled_ids
            }
            self._plugin_quarantined_until = {
                plugin_id: deadline
                for plugin_id, deadline in self._plugin_quarantined_until.items()
                if plugin_id in enabled_ids
            }
            self._startup_quarantined_identities = {
                plugin_id: package_digest
                for plugin_id, package_digest in self._startup_quarantined_identities.items()
                if (
                    plugin_id in enabled_ids
                    and request.manifest_by_id[plugin_id].package_digest == package_digest
                )
            }
            self._action_times = {
                plugin_id: times
                for plugin_id, times in self._action_times.items()
                if plugin_id in enabled_ids
            }
            self._radio_usage = {
                plugin_id: usage
                for plugin_id, usage in self._radio_usage.items()
                if plugin_id in enabled_ids
            }
            self._worker_start_failures = 0
            self._next_worker_attempt_at = 0.0
            with self._status_lock:
                self._ticker_values = {
                    key: value
                    for key, value in self._ticker_values.items()
                    if key[0] in enabled_ids
                }
            while True:
                try:
                    self._event_queue.get_nowait()
                except queue.Empty:
                    break
            while True:
                try:
                    item = self._console_queue.get_nowait()
                except queue.Empty:
                    break
                if isinstance(item, _ConsoleInvocationRequest):
                    item.error_code = "plugin_reconfigured"
                    item.error_message = "Plugin runtime was reconfigured"
                    item.ready.set()
        except Exception as exc:
            request.error = f"{type(exc).__name__}: {exc}"
        finally:
            request.ready.set()

    def _control_loop(self) -> None:
        while not self._closing.is_set():
            try:
                item = self._control_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if item is _QUEUE_STOP:
                return
            if not isinstance(item, MessageEvent):
                continue
            self._end_session(item)

    def _end_session(self, event: MessageEvent) -> None:
        session_key = (
            event.local_node_id,
            event.sender_id,
            event.channel_index,
        )
        try:
            with self._session_lock:
                self._session_versions[session_key] = self._session_versions.get(session_key, 0) + 1
                ended = self._state_store.end_session(
                    event.local_node_id,
                    event.sender_id,
                    event.channel_index,
                )
                ended = self._sessions.pop(session_key, None) is not None or ended
        except Exception as exc:
            with self._status_lock:
                self._last_error = f"host session end failed: {exc}"
            return
        if ended and not self._closing.is_set():
            self._queue_action(_QueuedAction("host", event, ReplyAction("Session ended.")))

    def _console_session_active(self, plugin_id: str, event: MessageEvent) -> bool:
        with self._session_lock:
            return (
                self._sessions.get(
                    (
                        event.local_node_id,
                        event.sender_id,
                        event.channel_index,
                    )
                )
                == plugin_id
            )

    def _resolve_console_handler(
        self,
        request: _ConsoleInvocationRequest,
    ) -> tuple[str, str, str]:
        plugin_id = request.plugin_id
        if self._command_plugins.get(request.command) != plugin_id:
            return "", "unknown_command", "No enabled plugin declares that command"
        if not self._console_route_enabled(plugin_id):
            return "", "plugin_console_disabled", "Plugin console route is disabled"
        if self._is_quarantined(plugin_id):
            return "", "plugin_quarantined", "Plugin is temporarily quarantined"
        registration = self._registry.get(plugin_id, {})
        if registration.get("error"):
            return (
                "",
                "plugin_unavailable",
                sanitize_plugin_status_error(registration.get("error"))
                or "Plugin is unavailable",
            )

        requested = request.handler
        if requested == "command":
            return "command", "", ""
        if requested == "session":
            if bool(registration.get("session")):
                return "session", "", ""
            return "", "plugin_handler_unavailable", "Plugin does not declare a session handler"
        if requested == "message":
            if bool(registration.get("on_message")):
                return "message", "", ""
            return "", "plugin_handler_unavailable", "Plugin does not declare a message handler"

        command_match = _COMMAND_RE.match(request.event.text.strip())
        if command_match and command_match.group(1).lower() == request.command:
            return "command", "", ""
        if self._console_session_active(plugin_id, request.event) and bool(
            registration.get("session")
        ):
            return "session", "", ""
        if bool(registration.get("on_message")):
            return "message", "", ""
        return "command", "", ""

    def _handle_console_invocation(self, request: _ConsoleInvocationRequest) -> None:
        try:
            handler, error_code, error_message = self._resolve_console_handler(request)
            if not handler:
                request.error_code = error_code or "plugin_console_failed"
                request.error_message = error_message or "Plugin console command failed"
                return
            invocation = _Invocation(
                request.plugin_id,
                handler,
                request.event,
                request.command if handler == "command" else "",
            )
            captured_actions: list[ScriptAction] = []
            request.ok = self._invoke(invocation, capture_actions=captured_actions)
            request.actions = captured_actions
            request.active_session = self._console_session_active(
                request.plugin_id,
                request.event,
            )
            if not request.ok:
                request.error_code = "plugin_worker_unavailable"
                request.error_message = "Plugin worker is unavailable"
        except Exception as exc:
            request.ok = False
            request.error_code = "plugin_console_failed"
            request.error_message = sanitize_plugin_status_error(exc)
        finally:
            request.ready.set()

    def _ensure_worker(self) -> bool:
        active_manifests = [
            manifest for manifest in self._manifests if not self._is_quarantined(manifest.id)
        ]
        active_plugin_ids = frozenset(manifest.id for manifest in active_manifests)
        process = self._process
        alive_fn = getattr(process, "is_alive", None) if process is not None else None
        if callable(alive_fn) and alive_fn() and self._connection is not None:
            if active_plugin_ids == self._worker_plugin_ids:
                return True
            self._stop_worker()
            process = None
        if process is not None:
            self._record_worker_failure("plugin worker exited unexpectedly")
            self._stop_worker()
            self._schedule_worker_retry()
            return False
        now = self._monotonic_fn()
        if now < self._next_worker_attempt_at:
            return False
        if not active_manifests:
            quarantine_deadlines = [
                self._plugin_quarantined_until.get(manifest.id, 0.0)
                for manifest in self._manifests
            ]
            future_deadlines = [deadline for deadline in quarantine_deadlines if deadline > now]
            self._next_worker_attempt_at = (
                min(future_deadlines) if future_deadlines else now + 0.5
            )
            self._publish_quarantined_registry()
            return False
        loading_plugin = ""
        try:
            parent_connection, child_connection = self._mp.Pipe(duplex=True)
            process = self._mp.Process(
                target=plugin_worker_main,
                args=(child_connection,),
                name="meshyface-plugin-worker",
            )
            process.start()
            child_connection.close()
            self._process = process
            self._connection = parent_connection
            self._generation += 1
            if self._generation > 1:
                self._restarts += 1
            parent_connection.send_bytes(
                encode_message(
                    {
                        "type": "init",
                        "manifests": [_manifest_payload(manifest) for manifest in active_manifests],
                    }
                )
            )
            deadline = self._monotonic_fn() + self._config.startup_timeout_seconds
            while True:
                remaining = deadline - self._monotonic_fn()
                if remaining <= 0 or not parent_connection.poll(min(0.1, remaining)):
                    if remaining <= 0:
                        raise TimeoutError("plugin worker startup timed out")
                    if self._closing.is_set():
                        raise RuntimeError("plugin runtime is closing")
                    continue
                response = decode_message(parent_connection.recv_bytes(MAX_PROTOCOL_FRAME_BYTES))
                if response.get("type") == "loading":
                    loading_plugin = str(response.get("plugin_id") or "")
                    continue
                if response.get("type") != "ready" or not isinstance(
                    response.get("registry"), list
                ):
                    raise RuntimeError(
                        str(response.get("error") or "plugin worker failed to start")
                    )
                break
            registry: dict[str, dict[str, object]] = {}
            for row in cast(list[object], response["registry"]):
                if not isinstance(row, Mapping):
                    raise RuntimeError("plugin worker returned an invalid registry")
                plugin_id = str(row.get("id") or "")
                if plugin_id not in self._manifest_by_id:
                    raise RuntimeError("plugin worker returned an unknown plugin")
                clean_registration = dict(row)
                clean_registration["tickers"] = list(
                    self._validated_ticker_definitions(row.get("tickers"))
                )
                clean_registration["views"] = list(
                    self._validated_view_definitions(row.get("views"))
                )
                clean_registration["node_fields"] = list(
                    self._validated_node_field_definitions(row.get("node_fields"))
                )
                clean_registration["mesh_access"] = _validated_mesh_access(
                    row.get("mesh_access")
                )
                registry[plugin_id] = clean_registration
            for manifest in self._manifests:
                if manifest.id not in registry:
                    registry[manifest.id] = {
                        "id": manifest.id,
                        "commands": [],
                        "on_message": False,
                        "on_packet": False,
                        "session": False,
                        "on_start": False,
                        "on_stop": False,
                        "mesh_access": "unknown",
                        "tickers": [],
                        "views": [definition.to_dict(include_content=False) for definition in manifest.views],
                        "node_fields": [],
                        "error": self._quarantine_error(manifest.id),
                        "failures": self._plugin_failures.get(manifest.id, 0),
                        "last_error": self._plugin_last_errors.get(manifest.id, ""),
                    }
            with self._status_lock:
                self._registry = registry
                self._last_error = ""
                self._worker_ready = True
            self._worker_plugin_ids = active_plugin_ids
            self._worker_start_failures = 0
            self._next_worker_attempt_at = 0.0
            return True
        except Exception as exc:
            error = self._worker_startup_error(exc, process)
            if loading_plugin and not self._closing.is_set():
                self._record_plugin_failure(loading_plugin, error)
                manifest = self._manifest_by_id.get(loading_plugin)
                if manifest is not None:
                    self._startup_quarantined_identities[loading_plugin] = (
                        manifest.package_digest
                    )
            self._record_worker_failure(error)
            self._stop_worker()
            if not self._closing.is_set():
                self._schedule_worker_retry()
            return False

    def _schedule_worker_retry(self) -> None:
        self._worker_start_failures += 1
        base = max(0.05, float(self._config.restart_backoff_seconds))
        maximum = max(base, float(self._config.max_restart_backoff_seconds))
        exponent = min(10, self._worker_start_failures - 1)
        delay = min(maximum, base * float(2**exponent))
        self._next_worker_attempt_at = self._monotonic_fn() + delay

    def _worker_startup_error(self, exc: Exception, process: object) -> str:
        message = str(exc).strip()
        if not isinstance(exc, (EOFError, BrokenPipeError, OSError)):
            return message or type(exc).__name__
        join = getattr(process, "join", None)
        if callable(join):
            try:
                join(timeout=0.1)
            except Exception:
                pass
        exit_code = getattr(process, "exitcode", None)
        if isinstance(exit_code, int):
            if exit_code < 0:
                try:
                    signal_name = signal.Signals(-exit_code).name
                except (ValueError, OSError):
                    signal_name = f"signal {-exit_code}"
                return f"plugin worker exited during startup from {signal_name}"
            return f"plugin worker exited during startup with code {exit_code}"
        return message or "plugin worker connection closed during startup"

    def _publish_quarantined_registry(self) -> None:
        registry: dict[str, dict[str, object]] = {}
        for manifest in self._manifests:
            registry[manifest.id] = {
                "id": manifest.id,
                "commands": [],
                "on_message": False,
                "on_packet": False,
                "session": False,
                "on_start": False,
                "on_stop": False,
                "mesh_access": "unknown",
                "tickers": [],
                "views": [definition.to_dict(include_content=False) for definition in manifest.views],
                "node_fields": [],
                "error": self._quarantine_error(manifest.id),
                "failures": self._plugin_failures.get(manifest.id, 0),
                "last_error": self._plugin_last_errors.get(manifest.id, ""),
            }
        with self._status_lock:
            self._registry = registry

    def _invoke(
        self,
        invocation: _Invocation,
        *,
        capture_actions: list[ScriptAction] | None = None,
    ) -> bool:
        connection = self._connection
        if connection is None:
            return False
        mesh_route_enabled = self._mesh_route_enabled(invocation.plugin_id)
        registration = self._registry.get(invocation.plugin_id, {})
        if registration.get("error"):
            return True
        state = self._state_store.snapshot(
            invocation.plugin_id,
            invocation.event.sender_id,
            invocation.event.channel_index,
        )
        manifest = self._manifest_by_id[invocation.plugin_id]
        stored_settings = self._state_store.plugin_settings(
            invocation.plugin_id,
            package_digest=manifest.package_digest,
        )
        try:
            plugin_config = normalize_plugin_settings(
                manifest,
                stored_settings,
                require_all=False,
            )
        except ValueError:
            plugin_config = normalize_plugin_settings(manifest, {}, require_all=False)
        with self._session_lock:
            session_key = (
                invocation.event.local_node_id,
                invocation.event.sender_id,
                invocation.event.channel_index,
            )
            session_active = self._sessions.get(session_key) == invocation.plugin_id
            session_version = self._session_versions.get(session_key, 0)
        request_id = uuid.uuid4().hex
        if mesh_route_enabled:
            try:
                raw_nodes = self._node_snapshot_fn()
                nodes = to_jsonable(list(raw_nodes))
                if not isinstance(nodes, list):
                    nodes = []
            except Exception:
                nodes = []
        else:
            nodes = []
        request = {
            "type": "invoke",
            "generation": self._generation,
            "request_id": request_id,
            "plugin_id": invocation.plugin_id,
            "handler": invocation.handler,
            "command": invocation.command,
            "event": invocation.event.to_dict(),
            "state": state.state,
            "state_revision": state.state_revision,
            "peer_state": state.peer_state,
            "peer_state_revision": state.peer_state_revision,
            "config": plugin_config,
            "session_active": session_active,
            "nodes": nodes,
        }
        with self._status_lock:
            self._current_plugin = invocation.plugin_id
        try:
            connection.send_bytes(encode_message(request))
            deadline = self._monotonic_fn() + self._config.handler_timeout_seconds
            while not self._stop.is_set():
                remaining = deadline - self._monotonic_fn()
                if remaining <= 0:
                    raise TimeoutError("plugin handler timed out")
                if connection.poll(min(0.1, remaining)):
                    break
            else:
                return False
            response = decode_message(connection.recv_bytes(MAX_PROTOCOL_FRAME_BYTES))
            if response.get("generation") != self._generation:
                raise RuntimeError("stale plugin worker response")
            if response.get("request_id") != request_id:
                raise RuntimeError("mismatched plugin worker response")
            if response.get("type") == "handler_error":
                self._record_plugin_failure(
                    invocation.plugin_id,
                    str(response.get("error") or "plugin handler failed"),
                )
                if capture_actions is not None:
                    return False
                return True
            if response.get("type") != "result":
                raise RuntimeError("plugin worker returned an invalid result")
            actions = self._validated_actions(response.get("actions"))
            debug_entries = self._validated_debug(response.get("debug"))
            ticker_updates = self._validated_ticker_updates(
                invocation.plugin_id,
                response.get("tickers"),
            )
            session_actions = [action for action in actions if isinstance(action, SessionAction)]
            if len(session_actions) > 1:
                raise ValueError("plugin result contains conflicting session actions")
            if session_actions and not invocation.event.is_direct:
                raise ValueError("sessions may only be changed by direct messages")
            if invocation.handler in {"start", "stop"} and any(
                isinstance(action, (ReplyAction, SessionAction)) for action in actions
            ):
                raise ValueError("lifecycle handlers cannot reply or change sessions")
            returned_state = response.get("state")
            returned_peer_state = response.get("peer_state")
            if not isinstance(returned_state, Mapping) or not isinstance(
                returned_peer_state, Mapping
            ):
                raise ValueError("plugin worker returned invalid state")
            external_script_actions = tuple(
                action for action in actions if not isinstance(action, SessionAction)
            )
            if (
                not mesh_route_enabled
                and capture_actions is None
                and external_script_actions
            ):
                raise ValueError("plugin mesh route is disabled")
            external_actions = (
                ()
                if capture_actions is not None
                else tuple(
                    self._queued_external_action(
                        invocation.plugin_id,
                        invocation.event,
                        action,
                    )
                    for action in external_script_actions
                )
            )
            action_batch: _QueuedActionBatch | None = None
            if external_actions:
                if not self._admit_action_batch(
                    invocation.plugin_id,
                    external_actions,
                ):
                    raise ValueError("plugin action rate limit exceeded")
                action_batch = _QueuedActionBatch(
                    external_actions,
                    threading.Event(),
                )
                try:
                    self._action_queue.put_nowait(action_batch)
                except queue.Full as exc:
                    with self._status_lock:
                        self._dropped_actions += len(external_actions)
                    raise ValueError("plugin action queue is full") from exc
            try:
                with self._session_lock:
                    effective_session_actions = (
                        session_actions
                        if self._session_versions.get(session_key, 0) == session_version
                        else []
                    )
                    self._state_store.commit(
                        invocation.plugin_id,
                        invocation.event.sender_id,
                        state=returned_state,
                        peer_state=returned_peer_state,
                        expected_state_revision=state.state_revision,
                        expected_peer_state_revision=state.peer_state_revision,
                        channel_index=invocation.event.channel_index,
                        session_local_node_id=(
                            invocation.event.local_node_id if effective_session_actions else None
                        ),
                        session_operation=(
                            effective_session_actions[0].operation
                            if effective_session_actions
                            else None
                        ),
                    )
                    if effective_session_actions:
                        self._apply_session_action_unlocked(
                            invocation,
                            effective_session_actions[0],
                        )
            except Exception:
                if action_batch is not None:
                    action_batch.canceled = True
                    action_batch.ready.set()
                raise
            if action_batch is not None:
                action_batch.ready.set()
            if capture_actions is not None:
                capture_actions.extend(external_script_actions)
            if ticker_updates:
                self._publish_ticker_updates(invocation.plugin_id, ticker_updates)
            self._publish_debug(invocation.plugin_id, debug_entries)
            self._plugin_failures[invocation.plugin_id] = 0
            self._plugin_last_errors.pop(invocation.plugin_id, None)
            with self._status_lock:
                self._last_error = ""
            return True
        except PluginStateQuotaExceeded as exc:
            self._record_plugin_failure(invocation.plugin_id, str(exc))
            return True
        except TimeoutError as exc:
            with self._status_lock:
                self._timeouts += 1
            self._record_plugin_failure(invocation.plugin_id, str(exc))
            self._stop_worker(force=True)
            return False
        except (EOFError, OSError, BrokenPipeError) as exc:
            self._record_worker_failure(str(exc))
            self._record_plugin_failure(invocation.plugin_id, str(exc))
            self._stop_worker(force=True)
            return False
        except Exception as exc:
            self._record_plugin_failure(invocation.plugin_id, str(exc))
            self._stop_worker(force=True)
            return False
        finally:
            with self._status_lock:
                self._current_plugin = ""

    def _validated_actions(self, raw: object) -> tuple[ScriptAction, ...]:
        if not isinstance(raw, list) or len(raw) > 16:
            raise ValueError("plugin result has an invalid action list")
        actions: list[ScriptAction] = []
        for item in raw:
            if not isinstance(item, Mapping):
                raise ValueError("plugin action must be an object")
            action = action_from_dict(item)
            if isinstance(action, (ReplyAction, SendTextAction, SendChannelAction)):
                text = action.text
                size = len(text.encode("utf-8"))
                if not text.strip() or size > self._config.max_action_text_bytes:
                    raise ValueError("plugin text action is empty or too large")
                if not isinstance(action, ReplyAction) or not action.long:
                    if size > self._config.chat_max_bytes:
                        raise ValueError("plugin text action exceeds the chat byte limit")
            if isinstance(action, SendTextAction):
                destination_id = action.destination_id.lower()
                if (
                    _NODE_ID_RE.fullmatch(destination_id) is None
                    or destination_id in _RESERVED_NODE_IDS
                ):
                    raise ValueError(
                        "plugin send destination must be a direct canonical node ID"
                    )
                if action.channel_index is not None and not 0 <= action.channel_index <= 7:
                    raise ValueError("plugin channel index is out of range")
            if isinstance(action, SendChannelAction) and not 0 <= action.channel_index <= 7:
                raise ValueError("plugin channel index is out of range")
            if isinstance(action, SendFileAction):
                destination_id = action.destination_id.lower()
                if (
                    _NODE_ID_RE.fullmatch(destination_id) is None
                    or destination_id in _RESERVED_NODE_IDS
                ):
                    raise ValueError(
                        "plugin file destination must be a direct canonical node ID"
                    )
            actions.append(action)
        return tuple(actions)

    def _validated_debug(self, raw: object) -> tuple[list[JsonValue], ...]:
        if raw is None:
            return ()
        if not isinstance(raw, list) or len(raw) > 16:
            raise ValueError("plugin result has an invalid debug list")
        entries: list[list[JsonValue]] = []
        for item in raw:
            clean = to_jsonable(item)
            if not isinstance(clean, list):
                raise ValueError("plugin debug entry must be an array")
            size = len(json.dumps(clean, separators=(",", ":")).encode("utf-8"))
            if size > 16 * 1024:
                raise ValueError("plugin debug entry is too large")
            entries.append(clean)
        return tuple(entries)

    def _validated_ticker_definitions(
        self,
        raw: object,
    ) -> tuple[dict[str, object], ...]:
        if raw is None:
            return ()
        if not isinstance(raw, list) or len(raw) > 8:
            raise ValueError("plugin registry has an invalid ticker list")
        definitions: list[dict[str, object]] = []
        seen: set[str] = set()
        expected = {"id", "label", "metric", "default_enabled"}
        for item in raw:
            if not isinstance(item, Mapping) or set(item) != expected:
                raise ValueError("plugin ticker definition has invalid fields")
            ticker_id = str(item.get("id") or "")
            label = str(item.get("label") or "")
            if _TICKER_ID_RE.fullmatch(ticker_id) is None or ticker_id in seen:
                raise ValueError("plugin ticker definition has an invalid or duplicate ID")
            if not label or label != label.strip() or len(label) > 26:
                raise ValueError("plugin ticker definition has an invalid label")
            metric = item.get("metric")
            default_enabled = item.get("default_enabled")
            if not isinstance(metric, bool) or not isinstance(default_enabled, bool):
                raise ValueError("plugin ticker definition flags must be booleans")
            seen.add(ticker_id)
            definitions.append(
                {
                    "id": ticker_id,
                    "label": label,
                    "metric": metric,
                    "default_enabled": default_enabled,
                }
            )
        return tuple(definitions)

    def _validated_view_definitions(
        self,
        raw: object,
    ) -> tuple[dict[str, object], ...]:
        if raw is None:
            return ()
        if not isinstance(raw, list) or len(raw) > 8:
            raise ValueError("plugin registry has an invalid view list")
        definitions: list[dict[str, object]] = []
        seen: set[str] = set()
        expected = {"id", "label", "icon", "description", "content"}
        for item in raw:
            if not isinstance(item, Mapping) or set(item) != expected:
                raise ValueError("plugin view definition has invalid fields")
            view_id = str(item.get("id") or "")
            label = str(item.get("label") or "")
            icon = str(item.get("icon") or "")
            description = str(item.get("description") or "")
            content = str(item.get("content") or "")
            if _VIEW_ID_RE.fullmatch(view_id) is None or view_id in seen:
                raise ValueError("plugin view definition has an invalid or duplicate ID")
            if not label or label != label.strip() or len(label) > 32:
                raise ValueError("plugin view definition has an invalid label")
            if _VIEW_ICON_RE.fullmatch(icon) is None:
                raise ValueError("plugin view definition has an invalid icon")
            if description != description.strip() or len(description) > 120:
                raise ValueError("plugin view definition has an invalid description")
            if len(content) > 16 * 1024:
                raise ValueError("plugin view definition content is too large")
            seen.add(view_id)
            definitions.append(
                {
                    "id": view_id,
                    "label": label,
                    "icon": icon,
                    "description": description,
                    "content": content,
                }
            )
        return tuple(definitions)

    def _validated_node_field_definitions(
        self,
        raw: object,
    ) -> tuple[dict[str, object], ...]:
        if raw is None:
            return ()
        if not isinstance(raw, list) or len(raw) > 32:
            raise ValueError("plugin registry has an invalid node field list")
        definitions: list[dict[str, object]] = []
        seen: set[str] = set()
        expected = {
            "id",
            "label",
            "group",
            "value_type",
            "render_kinds",
            "default_render_kind",
            "default_visible",
            "sortable",
        }
        for item in raw:
            if not isinstance(item, Mapping) or set(item) != expected:
                raise ValueError("plugin node field definition has invalid fields")
            field_id = str(item.get("id") or "")
            label = str(item.get("label") or "")
            group = str(item.get("group") or "")
            value_type = str(item.get("value_type") or "")
            render_kinds_raw = item.get("render_kinds")
            render_kinds = (
                [str(kind) for kind in render_kinds_raw]
                if isinstance(render_kinds_raw, list)
                else []
            )
            default_render_kind = str(item.get("default_render_kind") or "")
            default_visible = item.get("default_visible")
            sortable = item.get("sortable")
            if _NODE_FIELD_ID_RE.fullmatch(field_id) is None or field_id in seen:
                raise ValueError("plugin node field definition has an invalid or duplicate ID")
            if not label or label != label.strip() or len(label) > 32:
                raise ValueError("plugin node field definition has an invalid label")
            if not group or group != group.strip() or len(group) > 24:
                raise ValueError("plugin node field definition has an invalid group")
            if value_type not in _NODE_FIELD_VALUE_TYPES:
                raise ValueError("plugin node field definition has an invalid value type")
            if (
                not render_kinds
                or len(render_kinds) > 8
                or any(kind not in _NODE_FIELD_RENDER_KINDS for kind in render_kinds)
            ):
                raise ValueError("plugin node field definition has invalid render kinds")
            if default_render_kind not in render_kinds:
                raise ValueError("plugin node field default render kind is invalid")
            if not isinstance(default_visible, bool) or not isinstance(sortable, bool):
                raise ValueError("plugin node field definition flags must be booleans")
            seen.add(field_id)
            definitions.append(
                {
                    "id": field_id,
                    "label": label,
                    "group": group,
                    "value_type": value_type,
                    "render_kinds": render_kinds,
                    "default_render_kind": default_render_kind,
                    "default_visible": default_visible,
                    "sortable": sortable,
                }
            )
        return tuple(definitions)

    def _validated_ticker_updates(
        self,
        plugin_id: str,
        raw: object,
    ) -> tuple[dict[str, object], ...]:
        if raw is None:
            return ()
        if not isinstance(raw, list) or len(raw) > 8:
            raise ValueError("plugin result has an invalid ticker update list")
        registration = self._registry.get(plugin_id, {})
        definitions = registration.get("tickers")
        definition_rows = definitions if isinstance(definitions, list) else []
        declared_ids = {
            str(item.get("id") or "")
            for item in definition_rows
            if isinstance(item, Mapping)
        }
        expected = {"id", "value", "rows", "state", "detail", "metric_value"}
        updates: list[dict[str, object]] = []
        seen: set[str] = set()
        for item in raw:
            if not isinstance(item, Mapping) or set(item) != expected:
                raise ValueError("plugin ticker update has invalid fields")
            ticker_id = str(item.get("id") or "").strip().lower()
            if ticker_id not in declared_ids or ticker_id in seen:
                raise ValueError("plugin ticker update references an undeclared or duplicate ID")
            value = self._validated_ticker_scalar(item.get("value"), maximum=96)
            state = str(item.get("state") or "neutral")
            if state not in {"neutral", "good", "warn", "bad"}:
                raise ValueError("plugin ticker update has an invalid state")
            detail = item.get("detail")
            if not isinstance(detail, str) or len(detail) > 256:
                raise ValueError("plugin ticker update has invalid detail")
            metric_value = item.get("metric_value")
            if metric_value is not None:
                if isinstance(metric_value, bool) or not isinstance(metric_value, (int, float)):
                    raise ValueError("plugin ticker update has invalid metric_value")
                if not math.isfinite(float(metric_value)):
                    raise ValueError("plugin ticker update metric_value must be finite")
            raw_rows = item.get("rows")
            if not isinstance(raw_rows, list) or len(raw_rows) > 8:
                raise ValueError("plugin ticker update has invalid rows")
            rows: list[dict[str, object]] = []
            for row in raw_rows:
                if not isinstance(row, Mapping) or set(row) != {"key", "value"}:
                    raise ValueError("plugin ticker row has invalid fields")
                key = row.get("key")
                if not isinstance(key, str) or not key or len(key) > 20:
                    raise ValueError("plugin ticker row has an invalid label")
                rows.append(
                    {
                        "key": key,
                        "value": self._validated_ticker_scalar(
                            row.get("value"),
                            maximum=96,
                        ),
                    }
                )
            seen.add(ticker_id)
            updates.append(
                {
                    "id": ticker_id,
                    "value": value,
                    "rows": rows,
                    "state": state,
                    "detail": detail,
                    "metric_value": metric_value,
                }
            )
        return tuple(updates)

    @staticmethod
    def _validated_ticker_scalar(value: object, *, maximum: int) -> object:
        if value is None or isinstance(value, (bool, int)):
            return value
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("plugin ticker value must be finite")
            return value
        if isinstance(value, str) and len(value) <= maximum:
            return value
        raise ValueError("plugin ticker value must be a bounded JSON scalar")

    def _publish_ticker_updates(
        self,
        plugin_id: str,
        updates: Sequence[Mapping[str, object]],
    ) -> None:
        updated_at = time.time()
        with self._status_lock:
            for update in updates:
                ticker_id = str(update.get("id") or "")
                self._ticker_values[(plugin_id, ticker_id)] = {
                    "value": update.get("value"),
                    "rows": list(update.get("rows", [])),
                    "state": str(update.get("state") or "neutral"),
                    "detail": str(update.get("detail") or ""),
                    "metric_value": update.get("metric_value"),
                    "updated_at": updated_at,
                }
        self._notify_state_changed()

    def _notify_state_changed(self) -> None:
        callback = self._state_changed_fn
        if callback is None:
            return
        try:
            callback()
        except Exception:
            pass

    def _publish_debug(
        self,
        plugin_id: str,
        entries: Sequence[list[JsonValue]],
    ) -> None:
        for values in entries:
            rendered = " ".join(
                value
                if isinstance(value, str)
                else json.dumps(value, separators=(",", ":"), sort_keys=True)
                for value in values
            )
            print(
                f"[script:{_terminal_safe_text(plugin_id)}] "
                f"{_terminal_safe_text(rendered)}",
                flush=True,
            )
            with self._status_lock:
                self._debug_sequence += 1
                self._debug_records.append(
                    {
                        "seq": self._debug_sequence,
                        "timestamp": time.time(),
                        "plugin_id": plugin_id,
                        "values": list(values),
                    }
                )

    def _apply_session_action_unlocked(
        self,
        invocation: _Invocation,
        action: SessionAction,
    ) -> None:
        if not invocation.event.is_direct:
            raise ValueError("sessions may only be changed by direct messages")
        session_key = (
            invocation.event.local_node_id,
            invocation.event.sender_id,
            invocation.event.channel_index,
        )
        if action.operation == "start":
            self._sessions[session_key] = invocation.plugin_id
        else:
            self._sessions.pop(session_key, None)

    def _action_loop(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._action_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if item is _QUEUE_STOP:
                return
            if not isinstance(item, _QueuedActionBatch):
                continue
            while not item.ready.wait(timeout=0.1):
                if self._stop.is_set() or self._closing.is_set():
                    return
            if self._stop.is_set() or self._closing.is_set():
                return
            if item.canceled:
                continue
            try:
                for action in item.actions:
                    if self._stop.is_set() or self._closing.is_set():
                        return
                    if action.plugin_id != "host" and action.plugin_id not in self._manifest_by_id:
                        continue
                    if action.plugin_id != "host" and not self._mesh_route_enabled(
                        action.plugin_id
                    ):
                        continue
                    self._execute_action(action)
            except Exception as exc:
                with self._status_lock:
                    self._last_error = f"action failed: {exc}"

    def _queued_external_action(
        self,
        plugin_id: str,
        event: MessageEvent,
        action: ScriptAction,
    ) -> _QueuedAction:
        frames, radio_bytes = self._action_radio_cost(action)
        return _QueuedAction(
            plugin_id,
            event,
            action,
            radio_frames=frames,
            radio_bytes=radio_bytes,
        )

    def _action_radio_cost(self, action: ScriptAction) -> tuple[int, int]:
        if isinstance(action, ReplyAction):
            segments = (
                _numbered_utf8_segments(action.text, self._config.chat_max_bytes)
                if action.long
                else [action.text]
            )
            retry_multiplier = (
                max(0, int(self._config.long_reply_retry_limit)) + 1
                if action.long
                else 1
            )
            return (
                len(segments) * retry_multiplier,
                sum(len(part.encode("utf-8")) for part in segments)
                * retry_multiplier,
            )
        if isinstance(action, (SendTextAction, SendChannelAction)):
            return 1, len(action.text.encode("utf-8"))
        if isinstance(action, SendFileAction):
            estimator_owner = getattr(self._submit_file_fn, "__self__", None)
            estimator = getattr(estimator_owner, "estimate_transfer_cost", None)
            if callable(estimator):
                estimate = estimator(action.path_or_file_id)
                if not isinstance(estimate, Mapping):
                    raise ValueError("file transfer estimator returned an invalid result")
                frames = self._positive_radio_cost(estimate.get("frames"), "frames")
                radio_bytes = self._positive_radio_cost(estimate.get("bytes"), "bytes")
            else:
                # Custom submitters without a preflight API are charged the
                # protocol maximum so they can never understate radio use.
                frames = 4 * (FILE_TRANSFER_MAX_CHUNKS + 1)
                radio_bytes = frames * FILE_TRANSFER_MAX_WIRE_BYTES
            if frames > 4 * (FILE_TRANSFER_MAX_CHUNKS + 1):
                raise ValueError("file transfer estimator exceeds the protocol frame limit")
            if radio_bytes > frames * FILE_TRANSFER_MAX_WIRE_BYTES:
                raise ValueError("file transfer estimator exceeds the protocol byte limit")
            return frames, radio_bytes
        if isinstance(action, AcceptFileOfferAction):
            configured_chunks = max(
                1,
                (
                    max(1, int(self._config.max_inbound_file_bytes))
                    + FILE_TRANSFER_CHUNK_BYTES
                    - 1
                )
                // FILE_TRANSFER_CHUNK_BYTES,
            )
            ack_frames = min(FILE_TRANSFER_MAX_CHUNKS, configured_chunks) + 1
            return ack_frames, ack_frames * FILE_TRANSFER_MAX_WIRE_BYTES
        return 0, 0

    @staticmethod
    def _positive_radio_cost(value: object, label: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"file transfer estimator returned invalid {label}")
        try:
            parsed = int(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(
                f"file transfer estimator returned invalid {label}"
            ) from exc
        if parsed <= 0:
            raise ValueError(f"file transfer estimator returned invalid {label}")
        return parsed

    def _admit_action_batch(
        self,
        plugin_id: str,
        actions: Sequence[_QueuedAction],
    ) -> bool:
        action_count = len(actions)
        frame_count = sum(max(0, action.radio_frames) for action in actions)
        synchronous_frame_count = sum(
            max(0, action.radio_frames)
            for action in actions
            if not isinstance(
                action.action,
                (SendFileAction, AcceptFileOfferAction),
            )
        )
        radio_bytes = sum(max(0, action.radio_bytes) for action in actions)
        now = self._monotonic_fn()
        with self._admission_lock:
            times = self._action_times.setdefault(plugin_id, deque())
            while times and now - times[0] >= 60.0:
                times.popleft()
            usage = self._radio_usage.setdefault(plugin_id, deque())
            while usage and now - usage[0][0] >= 60.0:
                usage.popleft()
            while (
                self._global_radio_usage
                and now - self._global_radio_usage[0][0] >= 60.0
            ):
                self._global_radio_usage.popleft()
            used_frames = sum(row[1] for row in usage)
            used_bytes = sum(row[2] for row in usage)
            global_frames = sum(row[1] for row in self._global_radio_usage)
            global_bytes = sum(row[2] for row in self._global_radio_usage)
            denied = (
                len(times) + action_count
                > max(1, self._config.max_actions_per_minute)
                or synchronous_frame_count
                > max(1, self._config.max_synchronous_radio_frames_per_batch)
                or used_frames + frame_count
                > max(1, self._config.max_radio_frames_per_minute)
                or used_bytes + radio_bytes
                > max(1, self._config.max_radio_bytes_per_minute)
                or global_frames + frame_count
                > max(1, self._config.max_global_radio_frames_per_minute)
                or global_bytes + radio_bytes
                > max(1, self._config.max_global_radio_bytes_per_minute)
            )
            if not denied:
                times.extend(now for _ in range(action_count))
                usage.append((now, frame_count, radio_bytes))
                self._global_radio_usage.append((now, frame_count, radio_bytes))
        if denied:
            with self._status_lock:
                self._dropped_actions += action_count
            return False
        return True

    def _execute_action(self, queued: _QueuedAction) -> None:
        event = queued.event
        action = queued.action
        if isinstance(action, ReplyAction):
            segments = (
                _numbered_utf8_segments(action.text, self._config.chat_max_bytes)
                if action.long
                else [action.text]
            )
            for index, segment in enumerate(segments):
                reply_id = event.packet_id if index == 0 and event.packet_id > 0 else None
                if action.long:
                    delivered = self._send_long_reply_segment_until_acked(
                        text=segment,
                        destination=event.sender_id,
                        channel_index=event.channel_index,
                        reply_id=reply_id,
                    )
                    if not delivered:
                        return
                else:
                    self._send_chat_fn(
                        text=segment,
                        destination=event.sender_id,
                        channel_index=event.channel_index,
                        reply_id=reply_id,
                    )
                if index + 1 < len(segments):
                    if self._closing.wait(max(0.0, self._config.long_reply_pace_seconds)):
                        return
            return
        if isinstance(action, SendTextAction):
            self._send_chat_fn(
                text=action.text,
                destination=action.destination_id,
                channel_index=action.channel_index,
            )
            return
        if isinstance(action, SendChannelAction):
            self._send_chat_fn(
                text=action.text,
                destination="^all",
                channel_index=action.channel_index,
            )
            return
        if isinstance(action, SendFileAction):
            if self._submit_file_fn is None:
                raise RuntimeError("host-managed file sending is unavailable")
            response = self._submit_file_fn(
                destination_id=action.destination_id,
                path_or_file_id=action.path_or_file_id,
                channel_index=event.channel_index,
                local_node_id=event.local_node_id,
                admitted_frames=queued.radio_frames,
            )
            if isinstance(response, Mapping) and response.get("ok") is False:
                raise RuntimeError(str(response.get("error") or "file job was rejected"))
            return
        if isinstance(action, AcceptFileOfferAction):
            if self._accept_file_offer_fn is None:
                raise RuntimeError("host-managed inbound file acceptance is unavailable")
            if event.packet is None:
                raise ValueError("accept_file() requires the current packet to contain a file offer")
            response = self._accept_file_offer_fn(event.packet)
            if isinstance(response, Mapping) and response.get("ok") is False:
                raise ValueError(str(response.get("error") or "file offer was rejected"))

    def _send_long_reply_segment_until_acked(
        self,
        *,
        text: str,
        destination: str,
        channel_index: int,
        reply_id: int | None,
    ) -> bool:
        attempt_message_ids: list[int] = []
        original_message_id: int | None = None
        retry_limit = max(0, int(self._config.long_reply_retry_limit))
        for attempt_index in range(retry_limit + 1):
            send_result = self._send_chat_fn(
                text=text,
                destination=destination,
                channel_index=channel_index,
                reply_id=reply_id,
                retry_of=original_message_id if attempt_index > 0 else None,
                retry_unacked=False,
            )
            message_id = _sent_message_id(send_result)
            if message_id is None or self._get_delivery_state_fn is None:
                return True
            if original_message_id is None:
                original_message_id = message_id
            attempt_message_ids.append(message_id)
            if self._wait_for_long_reply_ack(attempt_message_ids):
                return True
        return False

    def _wait_for_long_reply_ack(self, message_ids: Sequence[int]) -> bool:
        if self._any_delivery_is_acked(message_ids):
            return True
        wait_seconds = max(0.0, float(self._config.long_reply_ack_wait_seconds))
        if wait_seconds <= 0:
            return False
        poll_seconds = max(0.05, float(self._config.long_reply_ack_poll_seconds))
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            if self._closing.wait(min(poll_seconds, remaining)):
                return False
            if self._any_delivery_is_acked(message_ids):
                return True
        return self._any_delivery_is_acked(message_ids)

    def _any_delivery_is_acked(self, message_ids: Sequence[int]) -> bool:
        return any(self._delivery_is_acked(message_id) for message_id in message_ids)

    def _delivery_is_acked(self, message_id: object) -> bool:
        getter = self._get_delivery_state_fn
        if getter is None:
            return False
        try:
            state = getter(message_id)
        except Exception:
            return False
        if isinstance(state, Mapping):
            raw_state = state.get("delivery_state") or state.get("state")
        else:
            raw_state = state
        return str(raw_state or "").strip().lower() in _ACKED_DELIVERY_STATES

    def _startup_identity_is_quarantined(self, plugin_id: str) -> bool:
        manifest = self._manifest_by_id.get(plugin_id)
        quarantined_digest = self._startup_quarantined_identities.get(plugin_id)
        return bool(
            manifest is not None
            and quarantined_digest
            and manifest.package_digest == quarantined_digest
        )

    def _is_quarantined(self, plugin_id: str) -> bool:
        if self._startup_identity_is_quarantined(plugin_id):
            return True
        return self._plugin_quarantined_until.get(plugin_id, 0.0) > self._monotonic_fn()

    def _quarantine_error(self, plugin_id: str) -> str:
        if self._startup_identity_is_quarantined(plugin_id):
            return (
                "quarantined after fatal startup failure; disable and re-enable "
                "the plugin or restart Meshyface to retry"
            )
        return "temporarily quarantined after repeated handler failures"

    def _record_plugin_failure(self, plugin_id: str, error: str) -> None:
        failures = self._plugin_failures.get(plugin_id, 0) + 1
        self._plugin_failures[plugin_id] = failures
        self._plugin_last_errors[plugin_id] = error
        if failures >= 3:
            delay = min(60.0, float(2 ** min(6, failures - 3)))
            self._plugin_quarantined_until[plugin_id] = self._monotonic_fn() + delay
        with self._status_lock:
            self._last_error = f"{plugin_id}: {error}"
            registration = self._registry.get(plugin_id)
            if registration is not None:
                registration["failures"] = failures
                registration["last_error"] = error

    def _record_worker_failure(self, error: str) -> None:
        with self._status_lock:
            self._crashes += 1
            self._last_error = error

    def _stop_worker(self, *, force: bool = False) -> None:
        connection = self._connection
        process = self._process
        self._connection = None
        self._process = None
        self._worker_plugin_ids = frozenset()
        with self._status_lock:
            self._worker_ready = False
            self._registry = {}
        if connection is not None and not force:
            try:
                connection.send_bytes(encode_message({"type": "shutdown"}))
                if connection.poll(0.25):
                    connection.recv_bytes(MAX_PROTOCOL_FRAME_BYTES)
            except Exception:
                pass
        if process is not None:
            alive_fn = getattr(process, "is_alive", None)
            join = getattr(process, "join", None)
            if not force and callable(join):
                join(timeout=0.5)
            if callable(alive_fn) and alive_fn():
                terminate = getattr(process, "terminate", None)
                if callable(terminate):
                    terminate()
            if callable(join):
                join(timeout=1.0)
            if callable(alive_fn) and alive_fn():
                kill = getattr(process, "kill", None)
                if callable(kill):
                    kill()
                if callable(join):
                    join(timeout=1.0)
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


__all__ = [
    "PluginRuntime",
    "PluginRuntimeConfig",
    "_utf8_segments",
    "sanitize_plugin_status_error",
]
