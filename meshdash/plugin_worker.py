"""Spawned child implementation for trusted Python plugins."""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import cast

from .bots import (
    Bot,
    BotAction,
    BotManifest,
    BotSource,
    MessageEvent,
    ReplyAction,
    SendChannelAction,
    SendFileAction,
    SendTextAction,
    SessionAction,
    action_to_dict,
    validate_bot_against_manifest,
)
from .helpers_json import JsonValue, to_jsonable
from .offline_atlas import nearest_city
from .plugin_protocol import MAX_PROTOCOL_FRAME_BYTES, decode_message, encode_message


MAX_HANDLER_ACTIONS = 16
MAX_HANDLER_DEBUG_CALLS = 16
MAX_HANDLER_DEBUG_BYTES = 16 * 1024


def _manifest_from_payload(payload: Mapping[str, object]) -> BotManifest:
    return BotManifest(
        api_version=int(payload["api_version"]),
        id=str(payload["id"]),
        name=str(payload["name"]),
        version=str(payload["version"]),
        entrypoint=str(payload["entrypoint"]),
        commands=tuple(str(value) for value in cast(Sequence[object], payload["commands"])),
        default_enabled=bool(payload["default_enabled"]),
        manifest_path=Path(str(payload["manifest_path"])),
        plugin_directory=Path(str(payload["plugin_directory"])),
        entrypoint_path=Path(str(payload["entrypoint_path"])),
        entrypoint_object=str(payload["entrypoint_object"]),
        source=cast(BotSource, str(payload["source"])),
    )


def _load_plugin_module(manifest: BotManifest) -> ModuleType:
    package_name = f"_meshyface_plugin_{manifest.id}"
    package = ModuleType(package_name)
    package.__path__ = [str(manifest.plugin_directory)]  # type: ignore[attr-defined]
    package.__package__ = package_name
    sys.modules[package_name] = package
    module_name = f"{package_name}.__entrypoint__"
    spec = importlib.util.spec_from_file_location(module_name, manifest.entrypoint_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load plugin entrypoint {manifest.entrypoint_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_bot(manifest: BotManifest) -> Bot:
    module = _load_plugin_module(manifest)
    bot = getattr(module, manifest.entrypoint_object, None)
    return validate_bot_against_manifest(manifest, bot)


@dataclass
class _WorkerSession:
    active: bool

    def start(self) -> SessionAction:
        self.active = True
        return SessionAction("start")

    def end(self) -> SessionAction:
        self.active = False
        return SessionAction("end")


class _WorkerMesh:
    def __init__(self, message: MessageEvent, nodes: Sequence[Mapping[str, object]]) -> None:
        self._message = message
        self._nodes = tuple(dict(node) for node in nodes)

    def reply(self, message: MessageEvent, text: str) -> ReplyAction:
        del message
        return ReplyAction(text)

    def reply_long(self, message: MessageEvent, text: str) -> ReplyAction:
        del message
        return ReplyAction(text, long=True)

    def send_text(
        self,
        destination_id: str,
        text: str,
        channel_index: int | None = None,
    ) -> SendTextAction:
        return SendTextAction(destination_id, text, channel_index)

    def send_channel(self, channel_index: int, text: str) -> SendChannelAction:
        return SendChannelAction(channel_index, text)

    def get_node(self, node_id: str) -> Mapping[str, JsonValue] | None:
        clean = str(node_id or "").strip().lower()
        for node in self._nodes:
            candidate = str(node.get("id") or node.get("node_id") or "").strip().lower()
            if candidate == clean:
                return cast(Mapping[str, JsonValue], dict(node))
        return None

    def list_nodes(self) -> tuple[Mapping[str, JsonValue], ...]:
        return cast(tuple[Mapping[str, JsonValue], ...], self._nodes)

    def get_node_location(self, node_id: str) -> Mapping[str, JsonValue] | None:
        node = self.get_node(node_id)
        if node is None:
            return None
        position = node.get("position")
        if isinstance(position, Mapping):
            return cast(Mapping[str, JsonValue], dict(position))
        latitude = node.get("latitude") or node.get("lat")
        longitude = node.get("longitude") or node.get("lon")
        if latitude is None or longitude is None:
            return None
        return cast(
            Mapping[str, JsonValue],
            {"latitude": latitude, "longitude": longitude},
        )

    def nearest_city(self, latitude: float, longitude: float) -> Mapping[str, JsonValue] | None:
        result = nearest_city(latitude, longitude)
        return cast(Mapping[str, JsonValue] | None, result)

    def send_file(self, destination_id: str, path_or_file_id: str) -> SendFileAction:
        return SendFileAction(destination_id, path_or_file_id)


@dataclass
class _WorkerContext:
    message: MessageEvent
    state: MutableMapping[str, JsonValue]
    peer_state: MutableMapping[str, JsonValue]
    session: _WorkerSession
    mesh: _WorkerMesh
    log: logging.Logger
    debug_entries: list[list[JsonValue]]

    @property
    def packet(self) -> Mapping[str, JsonValue] | None:
        return self.message.packet

    def reply(self, text: str) -> ReplyAction:
        return self.mesh.reply(self.message, text)

    def reply_long(self, text: str) -> ReplyAction:
        return self.mesh.reply_long(self.message, text)

    def debug(self, *values: object) -> None:
        if len(self.debug_entries) >= MAX_HANDLER_DEBUG_CALLS:
            raise ValueError("plugin handler emitted too many debug entries")
        clean = to_jsonable(list(values))
        if not isinstance(clean, list):
            raise ValueError("plugin debug entry must be an array")
        size = len(json.dumps(clean, separators=(",", ":")).encode("utf-8"))
        if size > MAX_HANDLER_DEBUG_BYTES:
            raise ValueError("plugin debug entry is too large")
        self.debug_entries.append(clean)


def _normalize_handler_result(result: object) -> list[dict[str, JsonValue]]:
    if result is None:
        return []
    if isinstance(
        result,
        (ReplyAction, SendTextAction, SendChannelAction, SendFileAction, SessionAction),
    ):
        actions: Sequence[BotAction] = (result,)
    elif isinstance(result, (list, tuple)):
        actions = cast(Sequence[BotAction], result)
    else:
        raise TypeError("plugin handler must return an action, a sequence of actions, or None")
    if len(actions) > MAX_HANDLER_ACTIONS:
        raise ValueError(f"plugin handler returned more than {MAX_HANDLER_ACTIONS} actions")
    return [action_to_dict(action) for action in actions]


def _handle_invoke(bots: Mapping[str, Bot], message: Mapping[str, object]) -> dict[str, object]:
    request_id = str(message.get("request_id") or "")
    plugin_id = str(message.get("plugin_id") or "")
    handler_kind = str(message.get("handler") or "")
    bot = bots.get(plugin_id)
    if bot is None:
        raise ValueError(f"unknown plugin {plugin_id!r}")
    event_raw = message.get("event")
    if not isinstance(event_raw, Mapping):
        raise ValueError("invoke event must be an object")
    event = MessageEvent.from_dict(event_raw)
    state_raw = message.get("state")
    peer_state_raw = message.get("peer_state")
    if not isinstance(state_raw, Mapping) or not isinstance(peer_state_raw, Mapping):
        raise ValueError("invoke state must be JSON objects")
    nodes_raw = message.get("nodes", [])
    if not isinstance(nodes_raw, list) or not all(isinstance(row, Mapping) for row in nodes_raw):
        raise ValueError("invoke nodes must be an array of objects")
    state = cast(MutableMapping[str, JsonValue], dict(state_raw))
    peer_state = cast(MutableMapping[str, JsonValue], dict(peer_state_raw))
    initial_session_active = bool(message.get("session_active", False))
    session = _WorkerSession(initial_session_active)
    debug_entries: list[list[JsonValue]] = []
    context = _WorkerContext(
        message=event,
        state=state,
        peer_state=peer_state,
        session=session,
        mesh=_WorkerMesh(event, cast(Sequence[Mapping[str, object]], nodes_raw)),
        log=logging.getLogger(f"meshdash.plugin.{plugin_id}"),
        debug_entries=debug_entries,
    )
    if handler_kind == "command":
        command = str(message.get("command") or "")
        handler = bot.commands.get(command)
    elif handler_kind == "message":
        handler = bot.message_handler
    elif handler_kind == "packet":
        handler = bot.packet_handler
    elif handler_kind == "session":
        handler = bot.session_handler
    elif handler_kind == "start":
        handler = bot.start_handler
    elif handler_kind == "stop":
        handler = bot.stop_handler
    else:
        raise ValueError(f"unsupported handler kind {handler_kind!r}")
    if handler is None:
        raise ValueError(f"plugin {plugin_id!r} has no {handler_kind} handler")
    actions = _normalize_handler_result(handler(context))
    if session.active != initial_session_active and not any(
        action.get("type") == "session" for action in actions
    ):
        actions.append(SessionAction("start" if session.active else "end").to_dict())
    if len(actions) > MAX_HANDLER_ACTIONS:
        raise ValueError(f"plugin handler returned more than {MAX_HANDLER_ACTIONS} actions")
    return {
        "type": "result",
        "generation": int(message.get("generation") or 0),
        "request_id": request_id,
        "plugin_id": plugin_id,
        "state": dict(state),
        "peer_state": dict(peer_state),
        "actions": actions,
        "debug": debug_entries,
    }


def plugin_worker_main(connection: object) -> None:
    """Process entrypoint.  Only JSON bytes are read after spawn bootstrap."""

    recv_bytes = getattr(connection, "recv_bytes")
    send_bytes = getattr(connection, "send_bytes")
    close = getattr(connection, "close")
    bots: dict[str, Bot] = {}
    try:
        init_message = decode_message(recv_bytes(MAX_PROTOCOL_FRAME_BYTES))
        if init_message.get("type") != "init":
            raise ValueError("first worker message must be init")
        manifests_raw = init_message.get("manifests")
        if not isinstance(manifests_raw, list):
            raise ValueError("init manifests must be an array")
        registry: list[dict[str, object]] = []
        for raw in manifests_raw:
            if not isinstance(raw, Mapping):
                raise ValueError("manifest payload must be an object")
            manifest = _manifest_from_payload(raw)
            send_bytes(
                encode_message(
                    {"type": "loading", "plugin_id": manifest.id}
                )
            )
            try:
                bot = _load_bot(manifest)
            except BaseException as exc:
                registry.append(
                    {
                        "id": manifest.id,
                        "error": f"{type(exc).__name__}: {exc}",
                        "commands": [],
                        "on_message": False,
                        "on_packet": False,
                        "session": False,
                        "on_start": False,
                        "on_stop": False,
                    }
                )
            else:
                bots[manifest.id] = bot
                registry.append(
                    {
                        "id": manifest.id,
                        "commands": list(bot.commands),
                        "on_message": bot.message_handler is not None,
                        "on_packet": bot.packet_handler is not None,
                        "session": bot.session_handler is not None,
                        "on_start": bot.start_handler is not None,
                        "on_stop": bot.stop_handler is not None,
                    }
                )
        send_bytes(encode_message({"type": "ready", "registry": registry}))
        while True:
            message = decode_message(recv_bytes(MAX_PROTOCOL_FRAME_BYTES))
            message_type = message.get("type")
            if message_type == "shutdown":
                send_bytes(encode_message({"type": "stopped"}))
                return
            if message_type != "invoke":
                raise ValueError(f"unsupported worker message {message_type!r}")
            try:
                result = _handle_invoke(bots, message)
            except BaseException as exc:
                result = {
                    "type": "handler_error",
                    "generation": int(message.get("generation") or 0),
                    "request_id": str(message.get("request_id") or ""),
                    "plugin_id": str(message.get("plugin_id") or ""),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            send_bytes(encode_message(result))
    except BaseException as exc:
        try:
            send_bytes(
                encode_message(
                    {"type": "worker_error", "error": f"{type(exc).__name__}: {exc}"}
                )
            )
        except BaseException:
            pass
    finally:
        try:
            close()
        except BaseException:
            pass


__all__ = ["MAX_HANDLER_ACTIONS", "plugin_worker_main"]
