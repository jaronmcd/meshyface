import json
from types import SimpleNamespace

import meshdash.tracker_edges as tracker_edges
from meshdash.http_responses import json_bytes
from meshdash.history_rollups import merge_metric
from meshdash.nodes_identity import get_local_node_id
from meshdash.tracker_ingest import parse_tracker_packet
from meshdash.tracker_neighbor_info import MAX_NEIGHBOR_INFO_EDGES_PER_PACKET
from meshdash.tracker_runtime_impl import DashboardTracker
from meshdash.tracker_snapshot import build_edge_snapshot_rows


def _parse_packet(packet: dict[str, object]) -> dict[str, object]:
    return parse_tracker_packet(
        packet,
        object(),
        get_node_id_from_num_fn=lambda _interface, value: f"!{int(value):08x}",
        to_int_fn=lambda value: int(value) if value is not None else None,
        calculate_hops_fn=lambda _start, _limit: None,
        extract_packet_position_fn=lambda _packet: None,
        extract_packet_battery_level_fn=lambda _packet: None,
        extract_reply_id_fn=lambda _decoded: None,
        extract_emoji_codepoint_fn=lambda _decoded: None,
        emoji_from_codepoint_fn=lambda _codepoint: "",
    )


def test_neighbor_info_source_is_bound_to_canonical_packet_header_sender() -> None:
    parsed = _parse_packet(
        {
            "from": 101,
            "fromId": "!deadbeef",
            "to": 0xFFFFFFFF,
            "decoded": {
                "portnum": "NEIGHBORINFO_APP",
                "neighborinfo": {
                    "node_id": 202,
                    "neighbors": [{"node_id": 303, "snr": 4.0}],
                },
            },
        }
    )

    assert parsed["from_id"] == "!00000065"
    assert parsed["to_id"] == "^all"
    assert parsed["neighbor_info_edges"] == []


def test_invalid_numeric_header_does_not_fall_back_to_display_alias() -> None:
    parsed = _parse_packet(
        {
            "from": True,
            "fromId": "!deadbeef",
            "to": -1,
            "toId": "!cafebabe",
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "ignored"},
        }
    )

    assert parsed["from_id"] == ""
    assert parsed["to_id"] == ""


def test_missing_numeric_sender_does_not_fall_back_to_display_alias() -> None:
    parsed = _parse_packet(
        {
            "fromId": "!deadbeef",
            "to": 2,
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "ignored"},
        }
    )

    assert parsed["from_id"] == ""


def test_live_tracker_rejects_packet_with_only_display_sender() -> None:
    tracker = DashboardTracker(packet_limit=4)

    tracker.on_receive(
        {
            "fromId": "!deadbeef",
            "to": 2,
            "id": 3,
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "ignored"},
        },
        SimpleNamespace(nodesByNum={}),
    )

    assert tracker.live_packet_count == 0
    assert list(tracker.recent_packets) == []
    assert list(tracker.recent_chat) == []


def test_local_security_identity_ignores_mutable_nodedb_alias() -> None:
    interface = SimpleNamespace(
        myInfo={"my_node_num": 0x01020304},
        nodesByNum={0x01020304: {"user": {"id": "!deadbeef"}}},
    )

    assert get_local_node_id(interface, broadcast_num=0xFFFFFFFF) == "!01020304"


def test_omitted_protobuf_channel_is_recorded_as_primary_channel() -> None:
    tracker = DashboardTracker(packet_limit=4)
    tracker.on_receive(
        {
            "from": 1,
            "to": 2,
            "id": 3,
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "hello"},
        },
        SimpleNamespace(nodesByNum={}),
    )

    assert tracker.recent_chat[-1]["channel"] == 0


def test_neighbor_info_is_bounded_and_discards_nonfinite_signal_values() -> None:
    neighbors = [
        {"node_id": 1000 + index, "snr": float("inf") if index == 0 else 5.0}
        for index in range(MAX_NEIGHBOR_INFO_EDGES_PER_PACKET + 10)
    ]
    parsed = _parse_packet(
        {
            "from": 101,
            "to": 0xFFFFFFFF,
            "decoded": {
                "portnum": "NEIGHBORINFO_APP",
                "neighborinfo": {"node_id": 101, "neighbors": neighbors},
            },
        }
    )

    edges = parsed["neighbor_info_edges"]
    assert isinstance(edges, list)
    assert len(edges) == MAX_NEIGHBOR_INFO_EDGES_PER_PACKET
    assert edges[0]["from_id"] == "!00000065"
    assert edges[0]["to_id"] == "!000003e8"
    assert edges[0]["rx_snr"] is None
    assert edges[-1]["to_id"] == "!00000427"


def test_edge_ingestion_rejects_nonfinite_metrics_and_caps_new_keys(monkeypatch) -> None:
    monkeypatch.setattr(tracker_edges, "MAX_TRACKED_EDGE_KEYS", 1)
    session_edges: dict[tuple[str, str], dict[str, object]] = {}
    historical_edges: dict[tuple[str, str], dict[str, object]] = {}

    first_key = tracker_edges.record_direct_edge_observation(
        session_edges=session_edges,
        historical_edges=historical_edges,
        from_id="!00000001",
        to_id="!00000002",
        rx_time=100,
        portnum="NEIGHBORINFO_APP",
        hops=0,
        rx_snr=float("inf"),
        rx_rssi=float("nan"),
        include_live_count=True,
    )
    rejected_key = tracker_edges.record_direct_edge_observation(
        session_edges=session_edges,
        historical_edges=historical_edges,
        from_id="!00000001",
        to_id="!00000003",
        rx_time=101,
        portnum="NEIGHBORINFO_APP",
        hops=0,
        rx_snr=4.0,
        rx_rssi=-90,
        include_live_count=True,
    )

    assert first_key == ("!00000001", "!00000002")
    assert rejected_key == ("!00000001", "!00000003")
    assert len(session_edges) == len(historical_edges) == 1
    assert first_key not in session_edges
    assert session_edges[rejected_key]["snr_count"] == 1
    assert session_edges[rejected_key]["rssi_count"] == 1


def test_snapshot_drops_nonfinite_edge_rollups_and_coordinates() -> None:
    key = ("!00000001", "!00000002")
    edge = {
        "from": key[0],
        "to": key[1],
        "count": 1,
        "first_rx_time": 100,
        "last_rx_time": 100,
        "portnums": {"NEIGHBORINFO_APP"},
        "last_hops": float("inf"),
        "hops_sum": float("inf"),
        "hops_count": 1,
        "snr_sum": float("inf"),
        "snr_count": 1,
        "snr_min": float("-inf"),
        "snr_max": float("inf"),
        "rssi_sum": float("nan"),
        "rssi_count": 1,
        "rssi_min": float("nan"),
        "rssi_max": float("nan"),
    }

    rows, _real_count = build_edge_snapshot_rows(
        session_edges={key: edge},
        historical_edges={},
        nodes_by_id={
            key[0]: {"lat": float("inf"), "lon": 1.0},
            key[1]: {"lat": 2.0, "lon": 3.0},
        },
        min_real_link_count=1,
        format_epoch_fn=lambda value: value,
    )

    assert rows[0]["last_hops"] is None
    assert rows[0]["avg_hops"] is None
    assert rows[0]["snr_samples"] == 0
    assert rows[0]["avg_snr"] is None
    assert rows[0]["rssi_samples"] == 0
    assert rows[0]["avg_rssi"] is None
    assert "src_lat" not in rows[0]


def test_metric_rollup_resets_poisoned_state_and_ignores_nonfinite_samples() -> None:
    assert merge_metric(
        float("inf"),
        99,
        float("-inf"),
        float("inf"),
        float("nan"),
    ) == (0.0, 0, None, None)
    assert merge_metric(4.0, 1, 4.0, 4.0, float("inf")) == (4.0, 1, 4.0, 4.0)


def test_json_bytes_recursively_replaces_nonfinite_numbers_with_null() -> None:
    encoded = json_bytes(
        {
            "positive": float("inf"),
            "negative": float("-inf"),
            "nested": [float("nan"), {"finite": 1.5}],
        }
    )

    assert b"Infinity" not in encoded
    assert b"NaN" not in encoded
    assert json.loads(encoded) == {
        "positive": None,
        "negative": None,
        "nested": [None, {"finite": 1.5}],
    }
