from meshdash.plugin_events import (
    normalize_plugin_message_event,
    normalize_plugin_packet_event,
)


def test_normalizes_direct_and_broadcast_text_packets() -> None:
    direct = normalize_plugin_message_event(
        {
            "from": 1,
            "to": 2,
            "id": 42,
            "channel": 3,
            "rxTime": 100,
            "rxSnr": 4.5,
            "rxRssi": -90,
            "hopStart": 3,
            "hopLimit": 2,
            "decoded": {
                "portnum": "TEXT_MESSAGE_APP",
                "text": "!hello",
                "replyId": 10,
            },
        },
        local_node_id="!00000002",
    )
    assert direct is not None
    assert direct.sender_id == "!00000001"
    assert direct.is_direct is True
    assert direct.packet_id == 42
    assert direct.hops == 1

    broadcast = normalize_plugin_message_event(
        {
            "from": 1,
            "to": 0xFFFFFFFF,
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "hello"},
        },
        local_node_id="!00000002",
    )
    assert broadcast is not None
    assert broadcast.is_broadcast is True


def test_rejects_non_text_self_and_messages_not_for_local_node() -> None:
    base = {
        "from": 1,
        "to": 2,
        "decoded": {"portnum": "POSITION_APP", "text": "hello"},
    }
    assert normalize_plugin_message_event(base, local_node_id="!00000002") is None
    base["decoded"] = {"portnum": "TEXT_MESSAGE_APP", "text": "hello"}
    assert normalize_plugin_message_event(base, local_node_id="!00000001") is None
    assert normalize_plugin_message_event(base, local_node_id="!00000003") is None


def test_wraps_raw_packet_for_packet_handlers() -> None:
    event = normalize_plugin_packet_event(
        {
            "from": 1,
            "to": 0xFFFFFFFF,
            "id": 42,
            "channel": 3,
            "decoded": {"portnum": "POSITION_APP", "payload": b"raw"},
        },
        local_node_id="!00000002",
        now_fn=lambda: 123.5,
    )

    assert event is not None
    assert event.packet == {
        "from": 1,
        "to": 0xFFFFFFFF,
        "id": 42,
        "channel": 3,
        "decoded": {"portnum": "POSITION_APP", "payload": "726177"},
    }
    assert event.portnum == "POSITION_APP"
    assert event.is_broadcast is True
    assert event.received_at == 123.5
