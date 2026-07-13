from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from meshdash.plugins import (
    Script,
    MessageEvent,
    ReplyAction,
    SendChannelAction,
    SendFileAction,
    SendTextAction,
    SessionAction,
    TickerDefinition,
    action_from_dict,
    action_to_dict,
)


def _message() -> MessageEvent:
    return MessageEvent(
        text="!hello",
        sender_id="!a1b2c3d4",
        destination_id="!01020304",
        local_node_id="!01020304",
        channel_index=2,
        is_direct=True,
        is_broadcast=False,
        packet_id=123,
        reply_packet_id=None,
        received_at=1234.5,
        snr=7.25,
        rssi=-91.0,
        hops=1,
    )


def test_script_registers_commands_and_handlers_with_read_only_registry() -> None:
    script = Script(id="example_script", name="Example Script", version="1.2.3")

    @script.command("hello")
    def hello(ctx: object) -> None:
        return None

    @script.on_message
    def message(ctx: object) -> None:
        return None

    @script.on_packet
    def packet(ctx: object) -> None:
        return None

    @script.session
    def session(ctx: object) -> None:
        return None

    @script.on_start
    def start(ctx: object) -> None:
        return None

    @script.on_stop
    def stop(ctx: object) -> None:
        return None

    ticker = script.ticker("activity", label="Activity", default_enabled=True)

    assert script.id == "example_script"
    assert script.name == "Example Script"
    assert script.version == "1.2.3"
    assert script.commands == {"hello": hello}
    assert script.message_handler is message
    assert script.packet_handler is packet
    assert script.session_handler is session
    assert script.start_handler is start
    assert script.stop_handler is stop
    assert ticker == TickerDefinition("activity", "Activity")
    assert script.tickers == {"activity": ticker}
    with pytest.raises(TypeError):
        script.commands["other"] = hello  # type: ignore[index]
    with pytest.raises(TypeError):
        script.tickers["other"] = ticker  # type: ignore[index]


def test_script_validates_ticker_declarations() -> None:
    script = Script(id="example", name="Example", version="1")

    script.ticker("health", label="Health", metric=True, default_enabled=False)
    with pytest.raises(ValueError, match="already registered"):
        script.ticker("health", label="Duplicate")
    with pytest.raises(ValueError, match="ticker id"):
        script.ticker("Bad ticker", label="Bad")
    with pytest.raises(ValueError, match="ticker label"):
        script.ticker("other", label="x" * 27)


@pytest.mark.parametrize("name", ["Hello", "two words", "!hello", "", "a" * 33])
def test_script_rejects_invalid_command_names(name: str) -> None:
    script = Script(id="example", name="Example", version="1")

    with pytest.raises(ValueError, match="command name"):
        script.command(name)


def test_script_rejects_duplicate_registrations() -> None:
    script = Script(id="example", name="Example", version="1")

    @script.command("hello")
    def hello(ctx: object) -> None:
        return None

    with pytest.raises(ValueError, match="already registered"):
        script.command("hello")(hello)

    script.on_message(hello)
    with pytest.raises(ValueError, match="already registered"):
        script.on_message(hello)

    script.on_packet(hello)
    with pytest.raises(ValueError, match="already registered"):
        script.on_packet(hello)


@pytest.mark.parametrize("plugin_id", ["Example", "two words", "-bad", "", "a" * 65])
def test_script_rejects_invalid_ids(plugin_id: str) -> None:
    with pytest.raises(ValueError, match="script id"):
        Script(id=plugin_id, name="Example", version="1")


def test_message_event_is_immutable_and_round_trips() -> None:
    event = MessageEvent.from_dict(
        {**_message().to_dict(), "packet": {"decoded": {"payload": "abcd"}}, "portnum": "POSITION_APP"}
    )

    assert MessageEvent.from_dict(event.to_dict()) == event
    assert event.packet == {"decoded": {"payload": "abcd"}}
    assert event.portnum == "POSITION_APP"
    with pytest.raises(FrozenInstanceError):
        event.text = "changed"  # type: ignore[misc]


def test_message_event_strictly_validates_decoded_payload() -> None:
    payload = _message().to_dict()
    payload["unexpected"] = True
    with pytest.raises(ValueError, match="unknown fields"):
        MessageEvent.from_dict(payload)

    payload = _message().to_dict()
    payload["is_direct"] = "yes"
    with pytest.raises(ValueError, match="must be booleans"):
        MessageEvent.from_dict(payload)

    payload = _message().to_dict()
    payload["received_at"] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        MessageEvent.from_dict(payload)


@pytest.mark.parametrize(
    "action",
    [
        ReplyAction("hello"),
        ReplyAction("long response", long=True),
        SendTextAction("!01020304", "hello", channel_index=2),
        SendChannelAction(1, "hello channel"),
        SendFileAction("!01020304", "daily-report"),
        SessionAction("start"),
        SessionAction("end"),
    ],
)
def test_actions_are_immutable_and_json_round_trip(action: object) -> None:
    payload = action_to_dict(action)  # type: ignore[arg-type]

    assert action_from_dict(payload) == action
    with pytest.raises(FrozenInstanceError):
        setattr(action, fields(action)[0].name, "changed")  # type: ignore[arg-type]


def test_action_decoder_rejects_unknown_types_fields_and_bad_values() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        action_from_dict({"type": "launch_rocket"})
    with pytest.raises(ValueError, match="unknown fields"):
        action_from_dict({"type": "reply", "text": "ok", "long": False, "extra": 1})
    with pytest.raises(ValueError, match="channel_index must be an integer"):
        action_from_dict(
            {
                "type": "send_text",
                "destination_id": "!01020304",
                "text": "hi",
                "channel_index": True,
            }
        )
