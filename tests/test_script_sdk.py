from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from meshdash.plugins import (
    AcceptFileOfferAction,
    Script,
    MessageEvent,
    NodeFieldDefinition,
    ReplyAction,
    SendChannelAction,
    SendFileAction,
    SendTextAction,
    SessionAction,
    TickerDefinition,
    ViewDefinition,
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
    view = script.view(
        "reply_lab",
        label="Reply Lab",
        icon="RL",
        description="Reply matching workspace",
        content="# Reply Lab",
    )

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
    assert view == ViewDefinition(
        "reply_lab",
        "Reply Lab",
        "RL",
        "Reply matching workspace",
        "# Reply Lab",
    )
    assert view.to_dict() == {
        "id": "reply_lab",
        "label": "Reply Lab",
        "icon": "RL",
        "description": "Reply matching workspace",
        "content": "# Reply Lab",
    }
    assert view.to_dict(include_content=False) == {
        "id": "reply_lab",
        "label": "Reply Lab",
        "icon": "RL",
        "description": "Reply matching workspace",
    }
    assert script.views == {"reply_lab": view}
    with pytest.raises(TypeError):
        script.commands["other"] = hello  # type: ignore[index]
    with pytest.raises(TypeError):
        script.tickers["other"] = ticker  # type: ignore[index]
    with pytest.raises(TypeError):
        script.views["other"] = view  # type: ignore[index]


def test_script_validates_ticker_declarations() -> None:
    script = Script(id="example", name="Example", version="1")

    script.ticker("health", label="Health", metric=True, default_enabled=False)
    with pytest.raises(ValueError, match="already registered"):
        script.ticker("health", label="Duplicate")
    with pytest.raises(ValueError, match="ticker id"):
        script.ticker("Bad ticker", label="Bad")
    with pytest.raises(ValueError, match="ticker label"):
        script.ticker("other", label="x" * 27)


def test_script_validates_view_declarations() -> None:
    script = Script(id="example", name="Example", version="1")

    view = script.view("main", label="Main View")

    assert view.icon == "MV"
    with pytest.raises(ValueError, match="already registered"):
        script.view("main", label="Duplicate")
    with pytest.raises(ValueError, match="view id"):
        script.view("Bad View", label="Bad")
    with pytest.raises(ValueError, match="view label"):
        script.view("other", label="x" * 33)
    with pytest.raises(ValueError, match="view icon"):
        script.view("other", label="Other", icon="TOOLONG")
    with pytest.raises(ValueError, match="view content"):
        script.view("large", label="Large", content="x" * (16 * 1024 + 1))


def test_script_declares_node_field_roster_line() -> None:
    script = Script(id="example", name="Example", version="1")

    field = script.node_field(
        "quality",
        label="Quality",
        value_type="number",
        render_kinds=("metric", "text"),
        default_render_kind="metric",
        default_visible=True,
        sortable=True,
        roster_line=1,
    )

    assert field == NodeFieldDefinition(
        "quality",
        "Quality",
        value_type="number",
        render_kinds=("metric", "text"),
        default_render_kind="metric",
        default_visible=True,
        sortable=True,
        roster_line=1,
    )
    assert field.to_dict()["roster_line"] == 1
    with pytest.raises(ValueError, match="roster_line"):
        script.node_field("invalid", label="Invalid", roster_line=0)
    with pytest.raises(ValueError, match="roster_line"):
        script.node_field("too_low", label="Too Low", roster_line=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="roster_line"):
        script.node_field("too_high", label="Too High", roster_line=5)


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
        AcceptFileOfferAction(),
        SessionAction("start"),
        SessionAction("end"),
    ],
)
def test_actions_are_immutable_and_json_round_trip(action: object) -> None:
    payload = action_to_dict(action)  # type: ignore[arg-type]

    assert action_from_dict(payload) == action
    action_fields = fields(action)  # type: ignore[arg-type]
    if action_fields:
        with pytest.raises(FrozenInstanceError):
            setattr(action, action_fields[0].name, "changed")
    else:
        with pytest.raises((FrozenInstanceError, TypeError)):
            setattr(action, "changed", True)


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
    with pytest.raises(ValueError, match="unknown fields"):
        action_from_dict({"type": "accept_file_offer", "enabled": True})
