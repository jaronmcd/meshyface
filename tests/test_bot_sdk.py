from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from meshdash.bots import (
    Bot,
    MessageEvent,
    ReplyAction,
    SendChannelAction,
    SendFileAction,
    SendTextAction,
    SessionAction,
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


def test_bot_registers_commands_and_handlers_with_read_only_registry() -> None:
    bot = Bot(id="example_bot", name="Example Bot", version="1.2.3")

    @bot.command("hello")
    def hello(ctx: object) -> None:
        return None

    @bot.on_message
    def message(ctx: object) -> None:
        return None

    @bot.session
    def session(ctx: object) -> None:
        return None

    @bot.on_start
    def start(ctx: object) -> None:
        return None

    @bot.on_stop
    def stop(ctx: object) -> None:
        return None

    assert bot.id == "example_bot"
    assert bot.name == "Example Bot"
    assert bot.version == "1.2.3"
    assert bot.commands == {"hello": hello}
    assert bot.message_handler is message
    assert bot.session_handler is session
    assert bot.start_handler is start
    assert bot.stop_handler is stop
    with pytest.raises(TypeError):
        bot.commands["other"] = hello  # type: ignore[index]


@pytest.mark.parametrize("name", ["Hello", "two words", "!hello", "", "a" * 33])
def test_bot_rejects_invalid_command_names(name: str) -> None:
    bot = Bot(id="example", name="Example", version="1")

    with pytest.raises(ValueError, match="command name"):
        bot.command(name)


def test_bot_rejects_duplicate_registrations() -> None:
    bot = Bot(id="example", name="Example", version="1")

    @bot.command("hello")
    def hello(ctx: object) -> None:
        return None

    with pytest.raises(ValueError, match="already registered"):
        bot.command("hello")(hello)

    bot.on_message(hello)
    with pytest.raises(ValueError, match="already registered"):
        bot.on_message(hello)


@pytest.mark.parametrize("bot_id", ["Example", "two words", "-bad", "", "a" * 65])
def test_bot_rejects_invalid_ids(bot_id: str) -> None:
    with pytest.raises(ValueError, match="bot id"):
        Bot(id=bot_id, name="Example", version="1")


def test_message_event_is_immutable_and_round_trips() -> None:
    event = _message()

    assert MessageEvent.from_dict(event.to_dict()) == event
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
