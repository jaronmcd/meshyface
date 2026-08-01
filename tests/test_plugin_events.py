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


def test_rejects_malformed_or_reserved_node_ids() -> None:
    packet = {
        "fromId": "!nothex!!",
        "toId": "!00000002",
        "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "hello"},
    }
    assert normalize_plugin_message_event(packet, local_node_id="!00000002") is None
    assert normalize_plugin_packet_event(packet, local_node_id="!00000002") is None

    packet["fromId"] = "!00000000"
    assert normalize_plugin_message_event(packet, local_node_id="!00000002") is None

    packet["fromId"] = "!ffffffff"
    assert normalize_plugin_packet_event(packet, local_node_id="!00000002") is None


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


def test_packet_hooks_reject_self_and_invalid_channels_but_preserve_transit() -> None:
    transit = {
        "from": 1,
        "to": 3,
        "channel": 7,
        "decoded": {"portnum": "POSITION_APP"},
    }
    event = normalize_plugin_packet_event(
        transit,
        local_node_id="!00000002",
    )
    assert event is not None
    assert event.is_direct is False
    assert event.is_broadcast is False
    assert normalize_plugin_packet_event(
        transit,
        local_node_id="!00000002",
        allow_transit=False,
    ) is None

    self_packet = dict(transit, **{"from": 2, "to": 0xFFFFFFFF})
    assert normalize_plugin_packet_event(
        self_packet,
        local_node_id="!00000002",
    ) is None
    assert normalize_plugin_packet_event(
        dict(transit, channel=8),
        local_node_id="!00000002",
    ) is None
    assert normalize_plugin_packet_event(
        dict(transit, channel=-1),
        local_node_id="!00000002",
    ) is None


def test_nonfinite_radio_metadata_is_safely_normalized() -> None:
    packet = {
        "from": 1,
        "to": 2,
        "channel": 0,
        "rxTime": float("nan"),
        "rxSnr": float("inf"),
        "rxRssi": float("-inf"),
        "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "!hello"},
    }

    message = normalize_plugin_message_event(
        packet,
        local_node_id="!00000002",
        now_fn=lambda: 123.5,
    )
    raw = normalize_plugin_packet_event(
        packet,
        local_node_id="!00000002",
        now_fn=lambda: 123.5,
    )

    assert message is not None
    assert message.received_at == 123.5
    assert message.snr is None
    assert message.rssi is None
    assert raw is not None
    assert raw.received_at == 123.5
