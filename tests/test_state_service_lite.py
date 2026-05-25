from meshdash.state_service import (
    _slim_edges_for_network,
    _slim_history_caps,
    _slim_nodes_for_chat,
    _slim_recent_packets,
)
from meshdash.state_summary import apply_node_historical_names


def test_slim_recent_packets_drops_raw_packet_blob_but_keeps_ui_fields() -> None:
    recent_packets = [
        {
            "summary": {
                "packet_id": 123,
                "from": "!from",
                "to": "!to",
                "portnum": "ROUTING_APP",
            },
            "packet": {
                "id": 123,
                "from": 1,
                "to": 2,
                "fromId": "!from",
                "toId": "!to",
                "channel": 7,
                "encrypted": "abc",
                "raw": {
                    "huge": "drop-me",
                    "decoded": {
                        "payload": "drop-me-too",
                    },
                },
                "decoded": {
                    "portnum": "ROUTING_APP",
                    "payload": "keep-me",
                    "routing": {
                        "requestId": 456,
                    },
                },
            },
        }
    ]

    slimmed = _slim_recent_packets(recent_packets)

    assert len(slimmed) == 1
    packet = slimmed[0]["packet"]
    assert packet["encrypted"] == "abc"
    assert packet["decoded"]["payload"] == "keep-me"
    assert packet["decoded"]["routing"]["requestId"] == 456
    assert "raw" not in packet
    assert "from_num" not in slimmed[0]["summary"]


def test_slim_history_caps_keeps_only_relevant_nodes_and_fields() -> None:
    history_caps = {
        "!node-a": {
            "first_seen_unix": 5,
            "first_seen": "2026-04-15 00:00:05Z",
            "last_seen_unix": 10,
            "last_seen": "2026-04-15 00:00:10Z",
            "has_position": True,
            "last_position_unix": 8,
            "last_position_time": "2026-04-15 00:00:08Z",
            "last_hops": 2,
            "battery_level": 90,
            "battery_updated_unix": 9,
            "last_short_name": "ALFA",
            "last_long_name": "Alpha Prime",
        },
        "!node-b": {
            "last_seen_unix": 20,
            "battery_level": 40,
        },
    }

    slimmed = _slim_history_caps(
        history_caps,
        nodes=[{"id": "!node-a"}],
        recent_chat=[],
        recent_packets=[],
        edges=[],
        local_node_id="!local",
    )

    assert set(slimmed) == {"!node-a"}
    assert slimmed["!node-a"]["first_seen_unix"] == 5
    assert slimmed["!node-a"]["first_seen"] == "2026-04-15 00:00:05Z"
    assert slimmed["!node-a"]["battery_level"] == 90
    assert slimmed["!node-a"]["last_short_name"] == "ALFA"
    assert slimmed["!node-a"]["last_long_name"] == "Alpha Prime"
    assert "battery_updated_unix" not in slimmed["!node-a"]


def test_slim_history_caps_chat_profile_drops_duplicate_text_times() -> None:
    history_caps = {
        "!node-a": {
            "first_seen_unix": 5,
            "first_seen": "2026-04-15 00:00:05Z",
            "last_seen_unix": 10,
            "last_seen": "2026-04-15 00:00:10Z",
            "has_position": True,
            "last_position_unix": 8,
            "last_position_time": "2026-04-15 00:00:08Z",
            "last_hops": 2,
            "battery_level": 90,
            "last_short_name": "ALFA",
            "last_long_name": "Alpha Prime",
        },
    }

    slimmed = _slim_history_caps(
        history_caps,
        nodes=[{"id": "!node-a"}],
        recent_chat=[],
        recent_packets=[],
        edges=[],
        local_node_id="!local",
        include_text_times=False,
    )

    assert set(slimmed) == {"!node-a"}
    assert slimmed["!node-a"]["last_seen_unix"] == 10
    assert slimmed["!node-a"]["last_position_unix"] == 8
    assert slimmed["!node-a"]["last_short_name"] == "ALFA"
    assert slimmed["!node-a"]["last_long_name"] == "Alpha Prime"
    assert "last_seen" not in slimmed["!node-a"]
    assert "first_seen" not in slimmed["!node-a"]
    assert slimmed["!node-a"]["first_seen_unix"] == 5
    assert "last_position_time" not in slimmed["!node-a"]


def test_apply_node_historical_names_prefers_custom_history_over_generic_live_name() -> None:
    rows = [
        {
            "id": "!aa000001",
            "short_name": "0001",
            "long_name": "Meshtastic 0001",
        },
        {
            "id": "!12345678",
            "short_name": "KEEP",
            "long_name": "Current Custom Name",
        },
    ]

    apply_node_historical_names(
        rows,
        {
            "!aa000001": {
                "first_seen_unix": 1776514000,
                "first_seen": "2026-04-18 12:06:40Z",
                "last_short_name": "ALFA",
                "last_long_name": "Alpha Relay",
            },
            "!12345678": {
                "last_short_name": "OLD",
                "last_long_name": "Older Custom Name",
            },
        },
    )

    assert rows[0]["short_name"] == "ALFA"
    assert rows[0]["long_name"] == "Alpha Relay"
    assert rows[0]["first_seen_unix"] == 1776514000
    assert rows[0]["first_seen"] == "2026-04-18 12:06:40Z"
    assert rows[1]["short_name"] == "KEEP"
    assert rows[1]["long_name"] == "Current Custom Name"


def test_slim_recent_packets_caps_lite_buffer_length() -> None:
    recent_packets = [
        {
            "summary": {"packet_id": idx, "from": f"!{idx}", "to": "^all"},
            "packet": {"id": idx},
        }
        for idx in range(150)
    ]

    slimmed = _slim_recent_packets(recent_packets)

    assert len(slimmed) == 120
    assert slimmed[0]["summary"]["packet_id"] == 30
    assert slimmed[-1]["summary"]["packet_id"] == 149


def test_slim_nodes_for_chat_drops_unused_heavy_fields() -> None:
    slimmed = _slim_nodes_for_chat(
        [
            {
                "id": "!node-a",
                "short_name": "A",
                "long_name": "Alpha",
                "saved_last_seen": "2026-04-15 00:00:10Z",
                "is_licensed": True,
                "first_seen_unix": 5,
                "last_heard": "2026-04-15 00:00:10Z",
                "last_heard_unix": 10,
                "role": "CLIENT",
            }
        ]
    )

    assert slimmed == [
        {
            "id": "!node-a",
            "short_name": "A",
            "long_name": "Alpha",
            "first_seen_unix": 5,
            "last_heard_unix": 10,
            "role": "CLIENT",
        }
    ]


def test_slim_nodes_for_chat_keeps_meshtastic_favorite_flag() -> None:
    slimmed = _slim_nodes_for_chat(
        [
            {
                "id": "!node-a",
                "short_name": "A",
                "is_favorite": True,
            }
        ]
    )

    assert slimmed == [
        {
            "id": "!node-a",
            "short_name": "A",
            "is_favorite": True,
        }
    ]


def test_slim_edges_for_network_drops_duplicate_strings_and_counts() -> None:
    slimmed = _slim_edges_for_network(
        [
            {
                "from": "!a",
                "to": "!b",
                "count": 12,
                "session_count": 3,
                "lifetime_count": 12,
                "is_real": True,
                "confidence": "confirmed",
                "first_rx_time": "2026-04-15 00:00:01Z",
                "last_rx_time": "2026-04-15 00:00:05Z",
                "avg_hops": 1.5,
                "last_hops": 2,
                "portnums": ["TEXT_MESSAGE_APP"],
                "avg_snr": 9.5,
                "snr_samples": 7,
                "snr_min": 3.0,
                "snr_max": 12.0,
                "avg_rssi": -101.5,
                "rssi_samples": 7,
                "rssi_min": -110,
                "rssi_max": -95,
            }
        ]
    )

    assert slimmed == [
        {
            "from": "!a",
            "to": "!b",
            "session_count": 3,
            "lifetime_count": 12,
            "is_real": True,
            "first_rx_unix": 1776211201,
            "last_rx_unix": 1776211205,
            "avg_hops": 1.5,
            "last_hops": 2,
            "portnums": ["TEXT_MESSAGE_APP"],
            "avg_snr": 9.5,
            "snr_min": 3.0,
            "snr_max": 12.0,
            "avg_rssi": -101.5,
            "rssi_min": -110,
            "rssi_max": -95,
        }
    ]
