"""Spawned child implementation for trusted Python plugins."""

from __future__ import annotations

import hmac
import importlib.util
import json
import logging
import math
import re
import sys
import dis
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import CodeType, FunctionType, MappingProxyType, ModuleType
from typing import cast

from .plugins import (
    AcceptFileOfferAction,
    Script,
    ScriptAction,
    PluginManifest,
    PluginSource,
    MessageEvent,
    ReplyAction,
    SendChannelAction,
    SendFileAction,
    SendTextAction,
    SessionAction,
    action_to_dict,
    compute_plugin_package_digest,
    validate_script_against_manifest,
    ViewDefinition,
)
from .helpers_json import JsonValue, to_jsonable
from .offline_atlas import nearest_city
from .plugin_protocol import MAX_PROTOCOL_FRAME_BYTES, decode_message, encode_message


MAX_HANDLER_ACTIONS = 16
MAX_HANDLER_DEBUG_CALLS = 16
MAX_HANDLER_DEBUG_BYTES = 16 * 1024
MAX_HANDLER_TICKER_UPDATES = 8
MAX_HANDLER_NODE_FIELD_UPDATES = 64
MAX_TICKER_ROWS = 8
MAX_NODE_FIELD_VALUE_BYTES = 96
MAX_NODE_FIELD_TITLE_BYTES = 160

_NODE_ID_RE = re.compile(r"![0-9a-f]{8}\Z")
_RESERVED_NODE_IDS = {"!00000000", "!ffffffff"}

_MESH_READ_CALLS = frozenset(
    {
        "get_node",
        "list_nodes",
        "get_node_location",
        "nearest_city",
    }
)
_MESH_WRITE_CALLS = frozenset(
    {
        "reply",
        "reply_long",
        "send_text",
        "send_channel",
        "send_file",
        "accept_file",
    }
)
_MESH_WRITE_ACTION_NAMES = frozenset(
    {
        "ReplyAction",
        "SendTextAction",
        "SendChannelAction",
        "SendFileAction",
        "AcceptFileOfferAction",
    }
)


def _handler_mesh_access(handler: object) -> tuple[bool, bool]:
    if not isinstance(handler, FunctionType):
        return False, False
    return _code_mesh_access(
        handler.__code__,
        globals_map=handler.__globals__,
        module_name=handler.__module__,
        seen_functions={id(handler)},
        seen_codes=set(),
    )


def _code_mesh_access(
    code: CodeType,
    *,
    globals_map: Mapping[str, object],
    module_name: str,
    seen_functions: set[int],
    seen_codes: set[int],
) -> tuple[bool, bool]:
    code_id = id(code)
    if code_id in seen_codes:
        return False, False
    seen_codes.add(code_id)
    reads = False
    writes = False
    referenced_names: set[str] = set()
    for instruction in dis.get_instructions(code):
        arg = str(instruction.argval or "")
        if instruction.opname in {"LOAD_METHOD", "LOAD_ATTR", "LOAD_GLOBAL", "LOAD_NAME"}:
            referenced_names.add(arg)
            if arg in _MESH_READ_CALLS:
                reads = True
            if arg in _MESH_WRITE_CALLS or arg in _MESH_WRITE_ACTION_NAMES:
                writes = True
    for const in code.co_consts:
        if isinstance(const, CodeType):
            const_reads, const_writes = _code_mesh_access(
                const,
                globals_map=globals_map,
                module_name=module_name,
                seen_functions=seen_functions,
                seen_codes=seen_codes,
            )
            reads = reads or const_reads
            writes = writes or const_writes
    for name in referenced_names:
        value = globals_map.get(name)
        if not isinstance(value, FunctionType):
            continue
        if value.__module__ != module_name:
            continue
        function_id = id(value)
        if function_id in seen_functions:
            continue
        seen_functions.add(function_id)
        nested_reads, nested_writes = _code_mesh_access(
            value.__code__,
            globals_map=value.__globals__,
            module_name=value.__module__,
            seen_functions=seen_functions,
            seen_codes=seen_codes,
        )
        reads = reads or nested_reads
        writes = writes or nested_writes
    return reads, writes


def _script_mesh_access(script: Script) -> str:
    handlers: list[object] = [
        script.message_handler,
        script.packet_handler,
        script.session_handler,
        script.start_handler,
        script.stop_handler,
        *script.commands.values(),
    ]
    active_handlers = [handler for handler in handlers if handler is not None]
    if not active_handlers:
        return "none"
    saw_read = False
    saw_write = False
    for handler in active_handlers:
        handler_reads, handler_writes = _handler_mesh_access(handler)
        saw_read = saw_read or handler_reads
        saw_write = saw_write or handler_writes
    if saw_write:
        return "read_write"
    if saw_read or active_handlers:
        return "read_only"
    return "none"


def _view_definitions_from_payload(raw: object) -> tuple[ViewDefinition, ...]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return ()
    definitions: list[ViewDefinition] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        definitions.append(
            ViewDefinition(
                id=str(item.get("id") or ""),
                label=str(item.get("label") or ""),
                icon=str(item.get("icon") or ""),
                description=str(item.get("description") or ""),
            )
        )
    return tuple(definitions)


def _manifest_from_payload(payload: Mapping[str, object]) -> PluginManifest:
    return PluginManifest(
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
        source=cast(PluginSource, str(payload["source"])),
        package_digest=str(payload["package_digest"]),
        views=_view_definitions_from_payload(payload.get("views")),
    )


def _load_plugin_module(manifest: PluginManifest) -> ModuleType:
    current_digest = compute_plugin_package_digest(manifest.plugin_directory)
    if not hmac.compare_digest(current_digest, manifest.package_digest):
        raise ImportError(
            f"plugin {manifest.id!r} package changed after discovery; "
            "restart Meshyface to load the current local revision"
        )
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


def _load_script(manifest: PluginManifest) -> Script:
    module = _load_plugin_module(manifest)
    script = getattr(module, manifest.entrypoint_object, None)
    return validate_script_against_manifest(manifest, script)


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
    config: Mapping[str, JsonValue]
    session: _WorkerSession
    mesh: _WorkerMesh
    log: logging.Logger
    debug_entries: list[list[JsonValue]]
    declared_ticker_ids: frozenset[str]
    ticker_updates: dict[str, dict[str, JsonValue]]
    declared_node_field_ids: frozenset[str]
    node_field_updates: dict[tuple[str, str], dict[str, JsonValue]]

    @property
    def packet(self) -> Mapping[str, JsonValue] | None:
        return self.message.packet

    def reply(self, text: str) -> ReplyAction:
        return self.mesh.reply(self.message, text)

    def reply_long(self, text: str) -> ReplyAction:
        return self.mesh.reply_long(self.message, text)

    def accept_file(self) -> AcceptFileOfferAction:
        return AcceptFileOfferAction()

    def set_ticker(
        self,
        ticker_id: str,
        *,
        value: JsonValue = "n/a",
        rows: Mapping[str, JsonValue] | None = None,
        state: str = "neutral",
        detail: str = "",
        metric_value: float | int | None = None,
    ) -> None:
        clean_id = str(ticker_id or "").strip().lower()
        if clean_id not in self.declared_ticker_ids:
            raise ValueError(f"ticker {clean_id!r} was not declared by this plugin")
        if clean_id not in self.ticker_updates and len(self.ticker_updates) >= MAX_HANDLER_TICKER_UPDATES:
            raise ValueError("plugin handler updated too many tickers")
        clean_value = _ticker_scalar(value, "ticker value", maximum=96)
        clean_state = str(state or "neutral").strip().lower()
        if clean_state not in {"neutral", "good", "warn", "bad"}:
            raise ValueError("ticker state must be neutral, good, warn, or bad")
        if not isinstance(detail, str):
            raise ValueError("ticker detail must be a string")
        clean_detail = " ".join(detail.split()).strip()
        if len(clean_detail) > 256:
            raise ValueError("ticker detail must be at most 256 characters")
        if metric_value is not None:
            if isinstance(metric_value, bool) or not isinstance(metric_value, (int, float)):
                raise ValueError("ticker metric_value must be a number or None")
            if not math.isfinite(float(metric_value)):
                raise ValueError("ticker metric_value must be finite")

        clean_rows: list[JsonValue] = []
        if rows is not None:
            if not isinstance(rows, Mapping):
                raise ValueError("ticker rows must be an object or None")
            if len(rows) > MAX_TICKER_ROWS:
                raise ValueError(f"ticker rows must contain at most {MAX_TICKER_ROWS} entries")
            for raw_key, raw_value in rows.items():
                if not isinstance(raw_key, str):
                    raise ValueError("ticker row labels must be strings")
                key = " ".join(raw_key.split()).strip()
                if not key or len(key) > 20:
                    raise ValueError("ticker row labels must be 1 to 20 characters")
                clean_rows.append(
                    {
                        "key": key,
                        "value": _ticker_scalar(raw_value, "ticker row value", maximum=96),
                    }
                )
        self.ticker_updates[clean_id] = {
            "id": clean_id,
            "value": clean_value,
            "rows": clean_rows,
            "state": clean_state,
            "detail": clean_detail,
            "metric_value": metric_value,
        }

    def set_node_field(
        self,
        node_id: str,
        field_id: str,
        *,
        value: JsonValue = "n/a",
        sort: JsonValue | None = None,
        title: str = "",
    ) -> None:
        clean_node_id = str(node_id or "").strip().lower()
        if _NODE_ID_RE.fullmatch(clean_node_id) is None or clean_node_id in _RESERVED_NODE_IDS:
            raise ValueError("node field node_id must be a canonical node ID")
        clean_field_id = str(field_id or "").strip().lower()
        if clean_field_id not in self.declared_node_field_ids:
            raise ValueError(f"node field {clean_field_id!r} was not declared by this plugin")
        key = (clean_node_id, clean_field_id)
        if (
            key not in self.node_field_updates
            and len(self.node_field_updates) >= MAX_HANDLER_NODE_FIELD_UPDATES
        ):
            raise ValueError("plugin handler updated too many node fields")
        clean_value = _ticker_scalar(
            value,
            "node field value",
            maximum=MAX_NODE_FIELD_VALUE_BYTES,
        )
        clean_sort = (
            None
            if sort is None
            else _ticker_scalar(
                sort,
                "node field sort",
                maximum=MAX_NODE_FIELD_VALUE_BYTES,
            )
        )
        if not isinstance(title, str):
            raise ValueError("node field title must be a string")
        clean_title = " ".join(title.split()).strip()
        if len(clean_title) > MAX_NODE_FIELD_TITLE_BYTES:
            raise ValueError(
                f"node field title must be at most {MAX_NODE_FIELD_TITLE_BYTES} characters"
            )
        self.node_field_updates[key] = {
            "node_id": clean_node_id,
            "field_id": clean_field_id,
            "value": clean_value,
            "sort": clean_sort,
            "title": clean_title,
        }

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


def _ticker_scalar(value: object, field: str, *, maximum: int) -> JsonValue:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field} must be finite")
        return value
    if isinstance(value, str):
        clean = " ".join(value.split()).strip()
        if len(clean) > maximum:
            raise ValueError(f"{field} must be at most {maximum} characters")
        return clean or "n/a"
    raise ValueError(f"{field} must be a JSON scalar")


def _normalize_handler_result(result: object) -> list[dict[str, JsonValue]]:
    if result is None:
        return []
    if isinstance(
        result,
        (
            ReplyAction,
            SendTextAction,
            SendChannelAction,
            SendFileAction,
            AcceptFileOfferAction,
            SessionAction,
        ),
    ):
        actions: Sequence[ScriptAction] = (result,)
    elif isinstance(result, (list, tuple)):
        actions = cast(Sequence[ScriptAction], result)
    else:
        raise TypeError("plugin handler must return an action, a sequence of actions, or None")
    if len(actions) > MAX_HANDLER_ACTIONS:
        raise ValueError(f"plugin handler returned more than {MAX_HANDLER_ACTIONS} actions")
    return [action_to_dict(action) for action in actions]


def _freeze_config_value(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_config_value(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_config_value(item) for item in value)
    return value


def _handle_invoke(scripts: Mapping[str, Script], message: Mapping[str, object]) -> dict[str, object]:
    request_id = str(message.get("request_id") or "")
    plugin_id = str(message.get("plugin_id") or "")
    handler_kind = str(message.get("handler") or "")
    script = scripts.get(plugin_id)
    if script is None:
        raise ValueError(f"unknown plugin {plugin_id!r}")
    event_raw = message.get("event")
    if not isinstance(event_raw, Mapping):
        raise ValueError("invoke event must be an object")
    event = MessageEvent.from_dict(event_raw)
    state_raw = message.get("state")
    peer_state_raw = message.get("peer_state")
    config_raw = message.get("config")
    if (
        not isinstance(state_raw, Mapping)
        or not isinstance(peer_state_raw, Mapping)
        or not isinstance(config_raw, Mapping)
    ):
        raise ValueError("invoke state must be JSON objects")
    nodes_raw = message.get("nodes", [])
    if not isinstance(nodes_raw, list) or not all(isinstance(row, Mapping) for row in nodes_raw):
        raise ValueError("invoke nodes must be an array of objects")
    state = cast(MutableMapping[str, JsonValue], dict(state_raw))
    peer_state = cast(MutableMapping[str, JsonValue], dict(peer_state_raw))
    config = cast(
        Mapping[str, JsonValue],
        _freeze_config_value(config_raw),
    )
    initial_session_active = bool(message.get("session_active", False))
    session = _WorkerSession(initial_session_active)
    debug_entries: list[list[JsonValue]] = []
    ticker_updates: dict[str, dict[str, JsonValue]] = {}
    node_field_updates: dict[tuple[str, str], dict[str, JsonValue]] = {}
    context = _WorkerContext(
        message=event,
        state=state,
        peer_state=peer_state,
        config=config,
        session=session,
        mesh=_WorkerMesh(event, cast(Sequence[Mapping[str, object]], nodes_raw)),
        log=logging.getLogger(f"meshdash.plugin.{plugin_id}"),
        debug_entries=debug_entries,
        declared_ticker_ids=frozenset(script.tickers),
        ticker_updates=ticker_updates,
        declared_node_field_ids=frozenset(script.node_fields),
        node_field_updates=node_field_updates,
    )
    if handler_kind == "command":
        command = str(message.get("command") or "")
        handler = script.commands.get(command)
    elif handler_kind == "message":
        handler = script.message_handler
    elif handler_kind == "packet":
        handler = script.packet_handler
    elif handler_kind == "session":
        handler = script.session_handler
    elif handler_kind == "start":
        handler = script.start_handler
    elif handler_kind == "stop":
        handler = script.stop_handler
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
        "tickers": list(ticker_updates.values()),
        "node_fields": list(node_field_updates.values()),
    }


def plugin_worker_main(connection: object) -> None:
    """Process entrypoint.  Only JSON bytes are read after spawn bootstrap."""

    # Package bytecode is part of the discovered revision. Do not mutate local
    # plugin directories merely by importing them in a fresh worker.
    sys.dont_write_bytecode = True
    recv_bytes = getattr(connection, "recv_bytes")
    send_bytes = getattr(connection, "send_bytes")
    close = getattr(connection, "close")
    scripts: dict[str, Script] = {}
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
                script = _load_script(manifest)
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
                        "mesh_access": "unknown",
                        "tickers": [],
                        "views": [definition.to_dict() for definition in manifest.views],
                        "node_fields": [],
                    }
                )
            else:
                scripts[manifest.id] = script
                registry.append(
                    {
                        "id": manifest.id,
                        "commands": list(script.commands),
                        "on_message": script.message_handler is not None,
                        "on_packet": script.packet_handler is not None,
                        "session": script.session_handler is not None,
                        "on_start": script.start_handler is not None,
                        "on_stop": script.stop_handler is not None,
                        "mesh_access": _script_mesh_access(script),
                        "tickers": [definition.to_dict() for definition in script.tickers.values()],
                        "views": [definition.to_dict() for definition in script.views.values()],
                        "node_fields": [
                            definition.to_dict() for definition in script.node_fields.values()
                        ],
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
                result = _handle_invoke(scripts, message)
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
