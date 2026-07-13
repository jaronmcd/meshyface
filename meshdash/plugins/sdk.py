"""Stable public SDK for trusted MeshyFace Python scripts.

This module intentionally contains no dashboard, radio, storage, or worker
objects.  A worker supplies implementations of the context protocols and the
host validates every action before executing it.
"""

from __future__ import annotations

from dataclasses import dataclass
from logging import Logger
import math
import re
from types import MappingProxyType
from typing import Callable, Literal, Mapping, MutableMapping, Protocol, TypeAlias, cast

from meshdash.helpers_json import JsonValue


_SCRIPT_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
_COMMAND_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
_TICKER_ID_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")


def _nonempty_string(value: object, field: str, *, maximum: int | None = None) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field} must be a non-empty, trimmed string")
    if maximum is not None and len(value) > maximum:
        raise ValueError(f"{field} must be at most {maximum} characters")
    return value


def _integer(value: object, field: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{field} must be at least {minimum}")
    return value


def _optional_integer(value: object, field: str, *, minimum: int | None = None) -> int | None:
    if value is None:
        return None
    return _integer(value, field, minimum=minimum)


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def _optional_number(value: object, field: str) -> float | None:
    if value is None:
        return None
    return _number(value, field)


@dataclass(frozen=True, slots=True)
class TickerDefinition:
    """One display-only dashboard ticker declared by a Script."""

    id: str
    label: str
    metric: bool = False
    default_enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or _TICKER_ID_RE.fullmatch(self.id) is None:
            raise ValueError("ticker id must match [a-z][a-z0-9_-]{0,31}")
        _nonempty_string(self.label, "ticker label", maximum=26)
        if not isinstance(self.metric, bool):
            raise ValueError("ticker metric must be a boolean")
        if not isinstance(self.default_enabled, bool):
            raise ValueError("ticker default_enabled must be a boolean")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "id": self.id,
            "label": self.label,
            "metric": self.metric,
            "default_enabled": self.default_enabled,
        }


@dataclass(frozen=True, slots=True)
class MessageEvent:
    """Normalized, immutable message information delivered to a script."""

    text: str
    sender_id: str
    destination_id: str
    local_node_id: str
    channel_index: int
    is_direct: bool
    is_broadcast: bool
    packet_id: int
    reply_packet_id: int | None
    received_at: float
    snr: float | None = None
    rssi: float | None = None
    hops: int | None = None
    packet: Mapping[str, JsonValue] | None = None
    portnum: str = ""

    def __post_init__(self) -> None:
        _nonempty_string(self.sender_id, "sender_id", maximum=64)
        _nonempty_string(self.destination_id, "destination_id", maximum=64)
        _nonempty_string(self.local_node_id, "local_node_id", maximum=64)
        if not isinstance(self.text, str):
            raise ValueError("text must be a string")
        _integer(self.channel_index, "channel_index", minimum=0)
        _integer(self.packet_id, "packet_id", minimum=0)
        _optional_integer(self.reply_packet_id, "reply_packet_id", minimum=0)
        _number(self.received_at, "received_at")
        _optional_number(self.snr, "snr")
        _optional_number(self.rssi, "rssi")
        _optional_integer(self.hops, "hops", minimum=0)
        if self.packet is not None and not isinstance(self.packet, Mapping):
            raise ValueError("packet must be an object or None")
        if not isinstance(self.portnum, str):
            raise ValueError("portnum must be a string")
        if not isinstance(self.is_direct, bool) or not isinstance(self.is_broadcast, bool):
            raise ValueError("is_direct and is_broadcast must be booleans")
        if self.is_direct and self.is_broadcast:
            raise ValueError("a message cannot be both direct and broadcast")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "text": self.text,
            "sender_id": self.sender_id,
            "destination_id": self.destination_id,
            "local_node_id": self.local_node_id,
            "channel_index": self.channel_index,
            "is_direct": self.is_direct,
            "is_broadcast": self.is_broadcast,
            "packet_id": self.packet_id,
            "reply_packet_id": self.reply_packet_id,
            "received_at": self.received_at,
            "snr": self.snr,
            "rssi": self.rssi,
            "hops": self.hops,
            "packet": dict(self.packet) if self.packet is not None else None,
            "portnum": self.portnum,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "MessageEvent":
        expected = {
            "text",
            "sender_id",
            "destination_id",
            "local_node_id",
            "channel_index",
            "is_direct",
            "is_broadcast",
            "packet_id",
            "reply_packet_id",
            "received_at",
            "snr",
            "rssi",
            "hops",
            "packet",
            "portnum",
        }
        missing = expected - payload.keys()
        unknown = payload.keys() - expected
        if missing:
            raise ValueError(f"message event is missing fields: {', '.join(sorted(missing))}")
        if unknown:
            raise ValueError(f"message event has unknown fields: {', '.join(sorted(unknown))}")
        return cls(
            text=cast(str, payload["text"]),
            sender_id=cast(str, payload["sender_id"]),
            destination_id=cast(str, payload["destination_id"]),
            local_node_id=cast(str, payload["local_node_id"]),
            channel_index=cast(int, payload["channel_index"]),
            is_direct=cast(bool, payload["is_direct"]),
            is_broadcast=cast(bool, payload["is_broadcast"]),
            packet_id=cast(int, payload["packet_id"]),
            reply_packet_id=cast(int | None, payload["reply_packet_id"]),
            received_at=cast(float, payload["received_at"]),
            snr=cast(float | None, payload["snr"]),
            rssi=cast(float | None, payload["rssi"]),
            hops=cast(int | None, payload["hops"]),
            packet=cast(Mapping[str, JsonValue] | None, payload["packet"]),
            portnum=cast(str, payload["portnum"]),
        )


@dataclass(frozen=True, slots=True)
class ReplyAction:
    text: str
    long: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise ValueError("text must be a string")
        if not isinstance(self.long, bool):
            raise ValueError("long must be a boolean")

    def to_dict(self) -> dict[str, JsonValue]:
        return {"type": "reply", "text": self.text, "long": self.long}


@dataclass(frozen=True, slots=True)
class SendTextAction:
    destination_id: str
    text: str
    channel_index: int | None = None

    def __post_init__(self) -> None:
        _nonempty_string(self.destination_id, "destination_id", maximum=64)
        if not isinstance(self.text, str):
            raise ValueError("text must be a string")
        _optional_integer(self.channel_index, "channel_index", minimum=0)

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "type": "send_text",
            "destination_id": self.destination_id,
            "text": self.text,
            "channel_index": self.channel_index,
        }


@dataclass(frozen=True, slots=True)
class SendChannelAction:
    channel_index: int
    text: str

    def __post_init__(self) -> None:
        _integer(self.channel_index, "channel_index", minimum=0)
        if not isinstance(self.text, str):
            raise ValueError("text must be a string")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "type": "send_channel",
            "channel_index": self.channel_index,
            "text": self.text,
        }


@dataclass(frozen=True, slots=True)
class SendFileAction:
    destination_id: str
    path_or_file_id: str

    def __post_init__(self) -> None:
        _nonempty_string(self.destination_id, "destination_id", maximum=64)
        _nonempty_string(self.path_or_file_id, "path_or_file_id")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "type": "send_file",
            "destination_id": self.destination_id,
            "path_or_file_id": self.path_or_file_id,
        }


@dataclass(frozen=True, slots=True)
class SessionAction:
    operation: Literal["start", "end"]

    def __post_init__(self) -> None:
        if self.operation not in ("start", "end"):
            raise ValueError("session operation must be 'start' or 'end'")

    def to_dict(self) -> dict[str, JsonValue]:
        return {"type": "session", "operation": self.operation}


ScriptAction: TypeAlias = (
    ReplyAction | SendTextAction | SendChannelAction | SendFileAction | SessionAction
)


def action_to_dict(action: ScriptAction) -> dict[str, JsonValue]:
    """Convert one immutable SDK action to a JSON-compatible dictionary."""

    if not isinstance(
        action,
        (ReplyAction, SendTextAction, SendChannelAction, SendFileAction, SessionAction),
    ):
        raise TypeError(f"unsupported script action: {type(action).__name__}")
    return action.to_dict()


def action_from_dict(payload: Mapping[str, object]) -> ScriptAction:
    """Strictly reconstruct an SDK action from a decoded JSON object."""

    action_type = payload.get("type")
    if action_type == "reply":
        _require_action_fields(payload, {"type", "text", "long"})
        return ReplyAction(text=cast(str, payload["text"]), long=cast(bool, payload["long"]))
    if action_type == "send_text":
        _require_action_fields(payload, {"type", "destination_id", "text", "channel_index"})
        return SendTextAction(
            destination_id=cast(str, payload["destination_id"]),
            text=cast(str, payload["text"]),
            channel_index=cast(int | None, payload["channel_index"]),
        )
    if action_type == "send_channel":
        _require_action_fields(payload, {"type", "channel_index", "text"})
        return SendChannelAction(
            channel_index=cast(int, payload["channel_index"]),
            text=cast(str, payload["text"]),
        )
    if action_type == "send_file":
        _require_action_fields(payload, {"type", "destination_id", "path_or_file_id"})
        return SendFileAction(
            destination_id=cast(str, payload["destination_id"]),
            path_or_file_id=cast(str, payload["path_or_file_id"]),
        )
    if action_type == "session":
        _require_action_fields(payload, {"type", "operation"})
        return SessionAction(operation=cast(Literal["start", "end"], payload["operation"]))
    raise ValueError("action type is missing or unsupported")


def _require_action_fields(payload: Mapping[str, object], expected: set[str]) -> None:
    missing = expected - payload.keys()
    unknown = payload.keys() - expected
    if missing:
        raise ValueError(f"action is missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise ValueError(f"action has unknown fields: {', '.join(sorted(unknown))}")


class SessionAPI(Protocol):
    @property
    def active(self) -> bool: ...

    def start(self) -> SessionAction: ...

    def end(self) -> SessionAction: ...


class MeshyFaceAPI(Protocol):
    """Facade implemented by the worker without exposing host internals."""

    def reply(self, message: MessageEvent, text: str) -> ReplyAction: ...

    def reply_long(self, message: MessageEvent, text: str) -> ReplyAction: ...

    def send_text(
        self,
        destination_id: str,
        text: str,
        channel_index: int | None = None,
    ) -> SendTextAction: ...

    def send_channel(self, channel_index: int, text: str) -> SendChannelAction: ...

    def get_node(self, node_id: str) -> Mapping[str, JsonValue] | None: ...

    def list_nodes(self) -> tuple[Mapping[str, JsonValue], ...]: ...

    def get_node_location(self, node_id: str) -> Mapping[str, JsonValue] | None: ...

    def nearest_city(self, latitude: float, longitude: float) -> Mapping[str, JsonValue] | None: ...

    def send_file(self, destination_id: str, path_or_file_id: str) -> SendFileAction: ...


class ScriptContext(Protocol):
    message: MessageEvent
    packet: Mapping[str, JsonValue] | None
    mesh: MeshyFaceAPI
    state: MutableMapping[str, JsonValue]
    peer_state: MutableMapping[str, JsonValue]
    session: SessionAPI
    log: Logger

    def reply(self, text: str) -> ReplyAction: ...

    def reply_long(self, text: str) -> ReplyAction: ...

    def set_ticker(
        self,
        ticker_id: str,
        *,
        value: JsonValue = "n/a",
        rows: Mapping[str, JsonValue] | None = None,
        state: Literal["neutral", "good", "warn", "bad"] = "neutral",
        detail: str = "",
        metric_value: float | int | None = None,
    ) -> None: ...

    def debug(self, *values: object) -> None: ...


ScriptHandler: TypeAlias = Callable[[ScriptContext], object]


class Script:
    """Declarative registration object exported to plugin authors.

    Manifest metadata is authoritative.  After importing an entrypoint in the
    worker, the runtime must call ``validate_script_against_manifest`` before
    invoking handlers.
    """

    def __init__(self, *, id: str, name: str, version: str) -> None:
        if not isinstance(id, str) or _SCRIPT_ID_RE.fullmatch(id) is None:
            raise ValueError("script id must match [a-z][a-z0-9_-]{0,63}")
        self._id = id
        self._name = _nonempty_string(name, "script name", maximum=128)
        self._version = _nonempty_string(version, "script version", maximum=64)
        self._commands: dict[str, ScriptHandler] = {}
        self._commands_view: Mapping[str, ScriptHandler] = MappingProxyType(self._commands)
        self._tickers: dict[str, TickerDefinition] = {}
        self._tickers_view: Mapping[str, TickerDefinition] = MappingProxyType(self._tickers)
        self._message_handler: ScriptHandler | None = None
        self._packet_handler: ScriptHandler | None = None
        self._session_handler: ScriptHandler | None = None
        self._start_handler: ScriptHandler | None = None
        self._stop_handler: ScriptHandler | None = None

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    @property
    def commands(self) -> Mapping[str, ScriptHandler]:
        """Live, read-only view of command handlers for the worker runtime."""

        return self._commands_view

    @property
    def tickers(self) -> Mapping[str, TickerDefinition]:
        """Live, read-only view of dashboard ticker declarations."""

        return self._tickers_view

    @property
    def message_handler(self) -> ScriptHandler | None:
        return self._message_handler

    @property
    def packet_handler(self) -> ScriptHandler | None:
        return self._packet_handler

    @property
    def session_handler(self) -> ScriptHandler | None:
        return self._session_handler

    @property
    def start_handler(self) -> ScriptHandler | None:
        return self._start_handler

    @property
    def stop_handler(self) -> ScriptHandler | None:
        return self._stop_handler

    def command(self, name: str) -> Callable[[ScriptHandler], ScriptHandler]:
        if not isinstance(name, str) or _COMMAND_RE.fullmatch(name) is None:
            raise ValueError("command name must match [a-z][a-z0-9_-]{0,31}")

        def register(handler: ScriptHandler) -> ScriptHandler:
            self._require_callable(handler, f"command {name!r}")
            if name in self._commands:
                raise ValueError(f"command {name!r} is already registered")
            self._commands[name] = handler
            return handler

        return register

    def ticker(
        self,
        ticker_id: str,
        *,
        label: str,
        metric: bool = False,
        default_enabled: bool = True,
    ) -> TickerDefinition:
        """Declare one optional dashboard ticker owned by this Script."""

        definition = TickerDefinition(
            id=ticker_id,
            label=label,
            metric=metric,
            default_enabled=default_enabled,
        )
        if definition.id in self._tickers:
            raise ValueError(f"ticker {definition.id!r} is already registered")
        self._tickers[definition.id] = definition
        return definition

    def on_message(self, handler: ScriptHandler) -> ScriptHandler:
        self._message_handler = self._register_single(
            "message handler", self._message_handler, handler
        )
        return handler

    def on_packet(self, handler: ScriptHandler) -> ScriptHandler:
        self._packet_handler = self._register_single(
            "packet handler", self._packet_handler, handler
        )
        return handler

    def session(self, handler: ScriptHandler) -> ScriptHandler:
        self._session_handler = self._register_single(
            "session handler", self._session_handler, handler
        )
        return handler

    def on_start(self, handler: ScriptHandler) -> ScriptHandler:
        self._start_handler = self._register_single(
            "start handler", self._start_handler, handler
        )
        return handler

    def on_stop(self, handler: ScriptHandler) -> ScriptHandler:
        self._stop_handler = self._register_single("stop handler", self._stop_handler, handler)
        return handler

    @classmethod
    def _register_single(
        cls,
        label: str,
        current: ScriptHandler | None,
        handler: ScriptHandler,
    ) -> ScriptHandler:
        cls._require_callable(handler, label)
        if current is not None:
            raise ValueError(f"{label} is already registered")
        return handler

    @staticmethod
    def _require_callable(handler: object, label: str) -> None:
        if not callable(handler):
            raise TypeError(f"{label} must be callable")
