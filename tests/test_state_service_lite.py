import meshdash.state_service as state_service
from meshdash.state_payload_contracts import DashboardStatePayload, StateTrafficPayload
from meshdash.state_service import (
    _slim_edges_for_network,
    _slim_history_caps,
    _slim_nodes_for_chat,
    _slim_recent_chat_for_chat_profile,
    _slim_recent_packets,
    _slim_recent_packets_for_activity,
    _slim_recent_packets_for_network_graph,
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


def test_slim_recent_packets_for_activity_drops_packet_body() -> None:
    recent_packets = [
        {
            "summary": {
                "packet_id": 123,
                "from": "!from",
                "to": "!to",
                "portnum": "POSITION_APP",
                "rx_time": "2026-06-03 00:00:01Z",
            },
            "packet": {
                "id": 123,
                "fromId": "!from",
                "toId": "!to",
                "decoded": {"payload": "drop-me"},
                "raw": {"drop": True},
            },
            "captured_at": "2026-06-03 00:00:01Z",
        }
    ]

    slimmed = _slim_recent_packets_for_activity(recent_packets)

    assert slimmed == [
            {
                "summary": {
                    "packet_id": 123,
                    "from": "!from",
                    "to": "!to",
                "portnum": "POSITION_APP",
                "rx_time": "2026-06-03 00:00:01Z",
            },
            "captured_at": "2026-06-03 00:00:01Z",
        }
    ]


def test_slim_recent_packets_for_network_graph_promotes_routing_fields() -> None:
    slimmed = _slim_recent_packets_for_network_graph(
        [
            {
                "summary": {
                    "packet_id": 123,
                    "from": "!from",
                    "to": "^all",
                    "portnum": "ROUTING_APP",
                    "decoded_text": "drop",
                },
                "packet": {
                    "fromId": "!packet-from",
                    "toId": "!packet-to",
                    "raw": {"drop": True},
                },
                "captured_at": "2026-06-05T00:00:00Z",
            }
        ]
    )

    assert slimmed == [
        {
            "from": "!from",
            "to": "^all",
            "portnum": "ROUTING_APP",
            "packet_id": 123,
            "captured_at": "2026-06-05T00:00:00Z",
        }
    ]


def test_slim_recent_chat_for_chat_profile_drops_duplicate_timestamps() -> None:
    slimmed = _slim_recent_chat_for_chat_profile(
        [
            {
                "message_id": 123,
                "from": "!node-a",
                "to": "^all",
                "scope": "all",
                "portnum": "TEXT_MESSAGE_APP",
                "rx_time": "2026-06-03 00:00:01Z",
                "captured_at": "2026-06-03 00:00:02Z",
                "delivery_updated_unix": 1780444801,
                "delivery_updated_at": "2026-06-03 00:00:01Z",
                "text": "hello",
            },
            {
                "message_id": 124,
                "from": "!node-b",
                "to": "^all",
                "scope": "direct",
                "portnum": "ALERT_APP",
                "captured_at": "2026-06-03 00:00:03Z",
                "delivery_updated_at": "2026-06-03 00:00:03Z",
                "text": "fallback",
            },
            {
                "message_id": 125,
                "from": "!node-c",
                "to": "!node-a",
                "scope": "direct",
                "portnum": "TEXT_MESSAGE_APP",
                "rx_time": "2026-06-03 00:00:04Z",
                "text": "dm",
            },
        ]
    )

    assert slimmed[0] == {
        "message_id": 123,
        "from": "!node-a",
        "to": "^all",
        "rx_time": "2026-06-03 00:00:01Z",
        "delivery_updated_unix": 1780444801,
        "text": "hello",
    }
    assert slimmed[1]["captured_at"] == "2026-06-03 00:00:03Z"
    assert slimmed[1]["delivery_updated_at"] == "2026-06-03 00:00:03Z"
    assert slimmed[1]["scope"] == "direct"
    assert slimmed[1]["portnum"] == "ALERT_APP"
    assert "scope" not in slimmed[2]
    assert "portnum" not in slimmed[2]


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


def test_lite_network_profile_omits_recent_chat_rows(monkeypatch) -> None:
    payload = DashboardStatePayload(
        generated_at="2026-06-03T00:00:00Z",
        summary={},
        summary_error=None,
        my_info={},
        my_info_error=None,
        metadata={},
        metadata_error=None,
        local_state={},
        local_state_error=None,
        nodes_error=None,
        tracker_error=None,
        tracker_saved_counts_error=None,
        tracker_capabilities_error=None,
        nodes=[{"id": "!node-a", "short_name": "A", "long_name": "Alpha"}],
        history_caps={},
        nodes_full=[],
        traffic=StateTrafficPayload(
            edges=[{"from": "!node-a", "to": "!node-b", "count": 1}],
            port_counts=[],
            recent_packets=[],
            recent_chat=[{"from": "!node-a", "to": "^all", "text": "chat row"}],
            node_packet_trends={},
        ),
        local_node_id="!local",
    )

    monkeypatch.setattr(
        state_service,
        "build_dashboard_state_typed",
        lambda **_kwargs: payload,
    )

    state = state_service.build_dashboard_state_lite(
        iface=object(),
        tracker=object(),
        started_at=0,
        target="",
        show_secrets=True,
        storage_probe_path=None,
        revision_info={},
        sensitive_field_names=set(),
        profile="network",
    )

    traffic = state["traffic"]
    assert isinstance(traffic, dict)
    assert traffic["recent_chat"] == []
    assert traffic["edges"]


def test_lite_network_map_profile_keeps_activity_packets_only(monkeypatch) -> None:
    payload = DashboardStatePayload(
        generated_at="2026-06-03T00:00:00Z",
        summary={},
        summary_error=None,
        my_info={},
        my_info_error=None,
        metadata={},
        metadata_error=None,
        local_state={},
        local_state_error=None,
        nodes_error=None,
        tracker_error=None,
        tracker_saved_counts_error=None,
        tracker_capabilities_error=None,
        nodes=[{"id": "!node-a", "short_name": "A", "long_name": "Alpha"}],
        history_caps={},
        nodes_full=[],
        traffic=StateTrafficPayload(
            edges=[{"from": "!node-a", "to": "!node-b", "count": 1}],
            port_counts=[{"portnum": "TEXT_MESSAGE_APP", "count": 2}],
            recent_packets=[
                {
                    "summary": {"packet_id": 1, "from": "!node-a", "to": "^all"},
                    "packet": {"id": 1, "raw": {"drop": True}},
                }
            ],
            recent_chat=[{"from": "!node-a", "to": "^all", "text": "chat row"}],
            node_packet_trends={"!node-a": {"recent": 2}},
        ),
        local_node_id="!local",
    )

    monkeypatch.setattr(
        state_service,
        "build_dashboard_state_typed",
        lambda **_kwargs: payload,
    )

    state = state_service.build_dashboard_state_lite(
        iface=object(),
        tracker=object(),
        started_at=0,
        target="",
        show_secrets=True,
        storage_probe_path=None,
        revision_info={},
        sensitive_field_names=set(),
        profile="network-map",
    )

    traffic = state["traffic"]
    assert isinstance(traffic, dict)
    assert traffic["recent_chat"] == []
    assert traffic["edges"]
    assert traffic["port_counts"] == []
    assert traffic["node_packet_trends"] == {}
    assert traffic["recent_packets"] == [{"summary": {"packet_id": 1, "from": "!node-a", "to": "^all"}}]


def test_lite_network_graph_profile_keeps_edges_and_graph_packets(monkeypatch) -> None:
    payload = DashboardStatePayload(
        generated_at="2026-06-03T00:00:00Z",
        summary={},
        summary_error=None,
        my_info={},
        my_info_error=None,
        metadata={},
        metadata_error=None,
        local_state={},
        local_state_error=None,
        nodes_error=None,
        tracker_error=None,
        tracker_saved_counts_error=None,
        tracker_capabilities_error=None,
        nodes=[{"id": "!node-a", "short_name": "A", "long_name": "Alpha"}],
        history_caps={},
        nodes_full=[],
        traffic=StateTrafficPayload(
            edges=[{"from": "!node-a", "to": "!node-b", "count": 1}],
            port_counts=[{"portnum": "TEXT_MESSAGE_APP", "count": 2}],
            recent_packets=[
                {
                    "summary": {"packet_id": 1, "from": "!node-a", "to": "^all", "portnum": "ROUTING_APP"},
                    "packet": {"id": 1, "raw": {"drop": True}},
                }
            ],
            recent_chat=[{"from": "!node-a", "to": "^all", "text": "chat row"}],
            node_packet_trends={"!node-a": {"recent": 2}},
        ),
        local_node_id="!local",
    )

    monkeypatch.setattr(
        state_service,
        "build_dashboard_state_typed",
        lambda **_kwargs: payload,
    )

    state = state_service.build_dashboard_state_lite(
        iface=object(),
        tracker=object(),
        started_at=0,
        target="",
        show_secrets=True,
        storage_probe_path=None,
        revision_info={},
        sensitive_field_names=set(),
        profile="network-graph",
    )

    traffic = state["traffic"]
    assert isinstance(traffic, dict)
    assert traffic["recent_chat"] == []
    assert traffic["edges"]
    assert traffic["port_counts"] == []
    assert traffic["node_packet_trends"] == {}
    assert traffic["recent_packets"] == [
        {"from": "!node-a", "to": "^all", "portnum": "ROUTING_APP", "packet_id": 1}
    ]


def test_lite_status_profile_omits_live_traffic_rows(monkeypatch) -> None:
    payload = DashboardStatePayload(
        generated_at="2026-06-03T00:00:00Z",
        summary={},
        summary_error=None,
        my_info={},
        my_info_error=None,
        metadata={},
        metadata_error=None,
        local_state={},
        local_state_error=None,
        nodes_error=None,
        tracker_error=None,
        tracker_saved_counts_error=None,
        tracker_capabilities_error=None,
        nodes=[{"id": "!node-a", "short_name": "A", "long_name": "Alpha", "last_heard": "drop"}],
        history_caps={
            "!node-a": {
                "last_seen_unix": 10,
                "last_seen": "2026-06-03 00:00:10Z",
                "last_short_name": "A",
            }
        },
        nodes_full=[],
        traffic=StateTrafficPayload(
            edges=[{"from": "!node-a", "to": "!node-b", "count": 1}],
            port_counts=[{"portnum": "TEXT_MESSAGE_APP", "count": 2}],
            recent_packets=[{"summary": {"packet_id": 1, "from": "!node-a", "to": "^all"}}],
            recent_chat=[{"from": "!node-a", "to": "^all", "text": "chat row"}],
            node_packet_trends={"!node-a": {"recent": 2}},
        ),
        local_node_id="!local",
    )

    monkeypatch.setattr(
        state_service,
        "build_dashboard_state_typed",
        lambda **_kwargs: payload,
    )

    state = state_service.build_dashboard_state_lite(
        iface=object(),
        tracker=object(),
        started_at=0,
        target="",
        show_secrets=True,
        storage_probe_path=None,
        revision_info={},
        sensitive_field_names=set(),
        profile="status",
    )

    traffic = state["traffic"]
    assert isinstance(traffic, dict)
    assert traffic["recent_chat"] == []
    assert traffic["recent_packets"] == []
    assert traffic["edges"] == []
    assert traffic["port_counts"] == []
    assert traffic["node_packet_trends"] == {}
    assert state["nodes"] == [{"id": "!node-a", "short_name": "A", "long_name": "Alpha"}]
    assert state["history_caps"]["!node-a"]["last_seen_unix"] == 10
    assert "last_seen" not in state["history_caps"]["!node-a"]


def test_lite_console_profile_keeps_packet_feed_without_chat_or_edges(monkeypatch) -> None:
    payload = DashboardStatePayload(
        generated_at="2026-06-03T00:00:00Z",
        summary={},
        summary_error=None,
        my_info={},
        my_info_error=None,
        metadata={},
        metadata_error=None,
        local_state={},
        local_state_error=None,
        nodes_error=None,
        tracker_error=None,
        tracker_saved_counts_error=None,
        tracker_capabilities_error=None,
        nodes=[{"id": "!node-a", "short_name": "A", "long_name": "Alpha"}],
        history_caps={},
        nodes_full=[],
        traffic=StateTrafficPayload(
            edges=[{"from": "!node-a", "to": "!node-b", "count": 1}],
            port_counts=[{"portnum": "TEXT_MESSAGE_APP", "count": 2}],
            recent_packets=[
                {
                    "summary": {"packet_id": 1, "from": "!node-a", "to": "^all"},
                    "packet": {"id": 1, "raw": {"drop": True}},
                }
            ],
            recent_chat=[{"from": "!node-a", "to": "^all", "text": "chat row"}],
            node_packet_trends={"!node-a": {"recent": 2}},
        ),
        local_node_id="!local",
    )

    monkeypatch.setattr(
        state_service,
        "build_dashboard_state_typed",
        lambda **_kwargs: payload,
    )

    state = state_service.build_dashboard_state_lite(
        iface=object(),
        tracker=object(),
        started_at=0,
        target="",
        show_secrets=True,
        storage_probe_path=None,
        revision_info={},
        sensitive_field_names=set(),
        profile="console",
    )

    traffic = state["traffic"]
    assert isinstance(traffic, dict)
    assert traffic["recent_chat"] == []
    assert traffic["edges"] == []
    assert traffic["port_counts"] == []
    assert traffic["node_packet_trends"] == {}
    assert len(traffic["recent_packets"]) == 1
    assert traffic["recent_packets"][0]["packet"]["id"] == 1
    assert "raw" not in traffic["recent_packets"][0]["packet"]


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
