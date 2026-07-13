"""Host-side supervision, routing, state, and action execution for plugins."""

from __future__ import annotations

import multiprocessing
import queue
import re
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from .bots import (
    BotAction,
    BotManifest,
    MessageEvent,
    ReplyAction,
    SendChannelAction,
    SendFileAction,
    SendTextAction,
    SessionAction,
    action_from_dict,
)
from .helpers_json import JsonValue, to_jsonable
from .plugin_protocol import MAX_PROTOCOL_FRAME_BYTES, decode_message, encode_message
from .plugin_state import PluginStateStore
from .plugin_worker import plugin_worker_main


_NODE_ID_RE = re.compile(r"![0-9a-f]{8}\Z")
_COMMAND_RE = re.compile(r"!([a-z][a-z0-9_-]{0,31})(?:\s|\Z)", re.IGNORECASE)
_QUIT_COMMANDS = {"!quit", "!exit"}
_QUEUE_STOP = object()
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
    max_action_text_bytes: int = 4096
    chat_max_bytes: int = 200
    long_reply_pace_seconds: float = 1.0
    max_actions_per_minute: int = 60


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
    action: BotAction


@dataclass
class _QueuedActionBatch:
    actions: tuple[_QueuedAction, ...]
    ready: threading.Event
    canceled: bool = False


def _manifest_payload(manifest: BotManifest) -> dict[str, JsonValue]:
    return {
        "api_version": manifest.api_version,
        "id": manifest.id,
        "name": manifest.name,
        "version": manifest.version,
        "entrypoint": manifest.entrypoint,
        "commands": list(manifest.commands),
        "default_enabled": manifest.default_enabled,
        "manifest_path": str(manifest.manifest_path),
        "plugin_directory": str(manifest.plugin_directory),
        "entrypoint_path": str(manifest.entrypoint_path),
        "entrypoint_object": manifest.entrypoint_object,
        "source": manifest.source,
    }


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


def sanitize_plugin_status_error(value: object) -> str:
    """Return a bounded single-line error that cannot expose an absolute path."""

    compact = " ".join(str(value or "").split()).strip()
    if not compact:
        return ""
    scrubbed = _ABSOLUTE_PATH_RE.sub("[path]", compact)
    if len(scrubbed) > 512:
        return f"{scrubbed[:509]}..."
    return scrubbed


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


class PluginRuntime:
    """Own one spawned worker and keep all host objects in the parent process."""

    def __init__(
        self,
        *,
        manifests: Sequence[BotManifest],
        state_store: PluginStateStore,
        send_chat_fn: Callable[..., object],
        node_snapshot_fn: Callable[[], Sequence[Mapping[str, object]]] = tuple,
        submit_file_fn: Callable[..., object] | None = None,
        config: PluginRuntimeConfig = PluginRuntimeConfig(),
        mp_context: object | None = None,
        monotonic_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        if not manifests:
            raise ValueError("at least one enabled plugin manifest is required")
        if len(manifests) > 64:
            raise ValueError("at most 64 plugins may be enabled")
        self._manifests = tuple(manifests)
        self._manifest_by_id = {manifest.id: manifest for manifest in manifests}
        if len(self._manifest_by_id) != len(self._manifests):
            raise ValueError("plugin IDs must be unique")
        self._command_plugins: dict[str, str] = {}
        for manifest in manifests:
            for command in manifest.commands:
                previous = self._command_plugins.get(command)
                if previous is not None:
                    raise ValueError(
                        f"command {command!r} is declared by both {previous!r} and {manifest.id!r}"
                    )
                self._command_plugins[command] = manifest.id
        self._state_store = state_store
        self._send_chat_fn = send_chat_fn
        self._node_snapshot_fn = node_snapshot_fn
        self._submit_file_fn = submit_file_fn
        self._config = config
        self._mp = mp_context or multiprocessing.get_context("spawn")
        self._monotonic_fn = monotonic_fn
        self._event_queue: queue.Queue[object] = queue.Queue(
            maxsize=max(1, int(config.event_queue_size))
        )
        self._control_queue: queue.Queue[object] = queue.Queue(
            maxsize=max(1, int(config.control_queue_size))
        )
        self._action_queue: queue.Queue[object] = queue.Queue(
            maxsize=max(1, int(config.action_queue_size))
        )
        self._stop = threading.Event()
        self._closing = threading.Event()
        self._status_lock = threading.Lock()
        self._registry: dict[str, dict[str, object]] = {}
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
        self._plugin_failures: dict[str, int] = {}
        self._plugin_quarantined_until: dict[str, float] = {}
        self._action_times: dict[str, deque[float]] = {}
        self._started_generation = 0
        self._session_lock = threading.Lock()
        self._sessions = {
            (local_node_id, peer_id): plugin_id
            for local_node_id, peer_id, plugin_id in state_store.list_sessions()
        }
        self._session_versions: dict[tuple[str, str], int] = {}
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

        if self._stop.is_set() or self._closing.is_set():
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

    def _route_event(self, event: MessageEvent) -> tuple[_Invocation, ...]:
        clean_text = event.text.strip()
        command_match = _COMMAND_RE.match(clean_text)
        invocations: list[_Invocation] = []
        if command_match:
            command = command_match.group(1).lower()
            plugin_id = self._command_plugins.get(command)
            if plugin_id:
                invocations.append(_Invocation(plugin_id, "command", event, command))
            else:
                return ()
        if not invocations and event.is_direct:
            with self._session_lock:
                session_plugin = self._sessions.get(
                    (event.local_node_id, event.sender_id)
                )
            registration = self._registry.get(session_plugin or "", {})
            if session_plugin and bool(registration.get("session")):
                invocations.append(_Invocation(session_plugin, "session", event))
        if not invocations:
            with self._status_lock:
                message_plugins = [
                    plugin_id
                    for plugin_id, registration in self._registry.items()
                    if bool(registration.get("on_message")) and not registration.get("error")
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
            elif alive and ready:
                runtime_status = "running"
            elif alive or (self._generation == 0 and not self._last_error):
                runtime_status = "starting"
            else:
                runtime_status = "error"
            plugins: dict[str, dict[str, object]] = {}
            for plugin_id, registration in self._registry.items():
                public_registration = dict(registration)
                registration_error = sanitize_plugin_status_error(
                    registration.get("error")
                )
                last_error = sanitize_plugin_status_error(
                    registration.get("last_error")
                )
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
                "current_plugin": self._current_plugin,
                "last_error": sanitize_plugin_status_error(self._last_error),
                "plugins": plugins,
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
            if not self._ensure_worker():
                if self._stop.wait(max(0.05, self._config.restart_backoff_seconds)):
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
        session_key = (event.local_node_id, event.sender_id)
        try:
            with self._session_lock:
                self._session_versions[session_key] = (
                    self._session_versions.get(session_key, 0) + 1
                )
                ended = self._state_store.end_session(
                    event.local_node_id,
                    event.sender_id,
                )
                ended = self._sessions.pop(session_key, None) is not None or ended
        except Exception as exc:
            with self._status_lock:
                self._last_error = f"host session end failed: {exc}"
            return
        if ended and not self._closing.is_set():
            self._queue_action(
                _QueuedAction("host", event, ReplyAction("Session ended."))
            )

    def _ensure_worker(self) -> bool:
        active_manifests = [
            manifest
            for manifest in self._manifests
            if not self._is_quarantined(manifest.id)
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
        loading_plugin = ""
        try:
            if not active_manifests:
                raise RuntimeError("all enabled plugins are temporarily quarantined")
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
                        "manifests": [
                            _manifest_payload(manifest) for manifest in active_manifests
                        ],
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
                response = decode_message(
                    parent_connection.recv_bytes(MAX_PROTOCOL_FRAME_BYTES)
                )
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
                registry[plugin_id] = dict(row)
            for manifest in self._manifests:
                if manifest.id not in registry:
                    registry[manifest.id] = {
                        "id": manifest.id,
                        "commands": [],
                        "on_message": False,
                        "session": False,
                        "on_start": False,
                        "on_stop": False,
                        "error": "temporarily quarantined after startup failure",
                    }
            with self._status_lock:
                self._registry = registry
                self._last_error = ""
                self._worker_ready = True
            self._worker_plugin_ids = active_plugin_ids
            return True
        except Exception as exc:
            if isinstance(exc, TimeoutError) and loading_plugin:
                self._record_plugin_failure(loading_plugin, str(exc))
                self._plugin_quarantined_until[loading_plugin] = (
                    self._monotonic_fn() + 60.0
                )
            self._record_worker_failure(str(exc))
            self._stop_worker()
            return False

    def _invoke(self, invocation: _Invocation) -> bool:
        connection = self._connection
        if connection is None:
            return False
        registration = self._registry.get(invocation.plugin_id, {})
        if registration.get("error"):
            return True
        state = self._state_store.snapshot(invocation.plugin_id, invocation.event.sender_id)
        with self._session_lock:
            session_key = (
                invocation.event.local_node_id,
                invocation.event.sender_id,
            )
            session_active = (
                self._sessions.get(session_key)
                == invocation.plugin_id
            )
            session_version = self._session_versions.get(session_key, 0)
        request_id = uuid.uuid4().hex
        try:
            raw_nodes = self._node_snapshot_fn()
            nodes = to_jsonable(list(raw_nodes))
            if not isinstance(nodes, list):
                nodes = []
        except Exception:
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
                return True
            if response.get("type") != "result":
                raise RuntimeError("plugin worker returned an invalid result")
            actions = self._validated_actions(response.get("actions"))
            session_actions = [
                action for action in actions if isinstance(action, SessionAction)
            ]
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
            external_actions = tuple(
                _QueuedAction(invocation.plugin_id, invocation.event, action)
                for action in actions
                if not isinstance(action, SessionAction)
            )
            action_batch: _QueuedActionBatch | None = None
            if external_actions:
                if not self._admit_action_batch(
                    invocation.plugin_id,
                    len(external_actions),
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
                        session_local_node_id=(
                            invocation.event.local_node_id
                            if effective_session_actions
                            else None
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
            self._plugin_failures[invocation.plugin_id] = 0
            with self._status_lock:
                self._last_error = ""
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

    def _validated_actions(self, raw: object) -> tuple[BotAction, ...]:
        if not isinstance(raw, list) or len(raw) > 16:
            raise ValueError("plugin result has an invalid action list")
        actions: list[BotAction] = []
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
                if _NODE_ID_RE.fullmatch(action.destination_id.lower()) is None:
                    raise ValueError("plugin send destination must be a canonical node ID")
                if action.channel_index is not None and not 0 <= action.channel_index <= 7:
                    raise ValueError("plugin channel index is out of range")
            if isinstance(action, SendChannelAction) and not 0 <= action.channel_index <= 7:
                raise ValueError("plugin channel index is out of range")
            if isinstance(action, SendFileAction):
                if _NODE_ID_RE.fullmatch(action.destination_id.lower()) is None:
                    raise ValueError("plugin file destination must be a canonical node ID")
            actions.append(action)
        return tuple(actions)

    def _apply_session_action_unlocked(
        self,
        invocation: _Invocation,
        action: SessionAction,
    ) -> None:
        if not invocation.event.is_direct:
            raise ValueError("sessions may only be changed by direct messages")
        if action.operation == "start":
            self._sessions[
                (invocation.event.local_node_id, invocation.event.sender_id)
            ] = invocation.plugin_id
        else:
            self._sessions.pop(
                (invocation.event.local_node_id, invocation.event.sender_id),
                None,
            )

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
                    self._execute_action(action)
            except Exception as exc:
                with self._status_lock:
                    self._last_error = f"action failed: {exc}"

    def _admit_action_batch(self, plugin_id: str, action_count: int) -> bool:
        now = self._monotonic_fn()
        times = self._action_times.setdefault(plugin_id, deque())
        while times and now - times[0] >= 60.0:
            times.popleft()
        if len(times) + action_count > max(1, self._config.max_actions_per_minute):
            with self._status_lock:
                self._dropped_actions += action_count
            return False
        times.extend(now for _ in range(action_count))
        return True

    def _execute_action(self, queued: _QueuedAction) -> None:
        event = queued.event
        action = queued.action
        if isinstance(action, ReplyAction):
            segments = (
                _utf8_segments(action.text, self._config.chat_max_bytes)
                if action.long
                else [action.text]
            )
            for index, segment in enumerate(segments):
                self._send_chat_fn(
                    text=segment,
                    destination=event.sender_id,
                    channel_index=event.channel_index,
                    reply_id=event.packet_id if index == 0 and event.packet_id > 0 else None,
                )
                if index + 1 < len(segments):
                    if self._closing.wait(
                        max(0.0, self._config.long_reply_pace_seconds)
                    ):
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
            )
            if isinstance(response, Mapping) and response.get("ok") is False:
                raise RuntimeError(str(response.get("error") or "file job was rejected"))

    def _is_quarantined(self, plugin_id: str) -> bool:
        return self._plugin_quarantined_until.get(plugin_id, 0.0) > self._monotonic_fn()

    def _record_plugin_failure(self, plugin_id: str, error: str) -> None:
        failures = self._plugin_failures.get(plugin_id, 0) + 1
        self._plugin_failures[plugin_id] = failures
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
