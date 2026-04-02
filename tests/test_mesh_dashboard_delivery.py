import time
import types

import mesh_dashboard as md


def _iface() -> types.SimpleNamespace:
    return types.SimpleNamespace(nodesByNum={})


def _routing_packet(request_id: int, error_reason: str = "NONE") -> dict:
    return {
        "id": int(request_id) + 1000,
        "from": 1,
        "to": 2,
        "fromId": "!00000001",
        "toId": "!00000002",
        "rxTime": int(time.time()),
        "decoded": {
            "portnum": "ROUTING_APP",
            "routing": {
                "requestId": int(request_id),
                "errorReason": str(error_reason),
            },
        },
    }


def test_direct_local_chat_starts_pending_and_moves_to_acked():
    tracker = md.DashboardTracker(packet_limit=16, history_store=None)
    tracker.record_local_chat(
        text="hello",
        from_id="!local000",
        to_id="!peer0001",
        message_id=12345,
        ack_requested=True,
    )

    first = tracker.recent_chat[-1]
    assert first["delivery_state"] == "pending"
    assert first["ack_requested"] is True

    tracker.on_receive(_routing_packet(12345, "NONE"), _iface())

    updated = tracker.recent_chat[-1]
    assert updated["delivery_state"] == "acked"
    assert "delivery_error" not in updated


def test_direct_local_chat_moves_to_nak_with_reason():
    tracker = md.DashboardTracker(packet_limit=16, history_store=None)
    tracker.record_local_chat(
        text="hello",
        from_id="!local000",
        to_id="!peer0002",
        message_id=12346,
        ack_requested=True,
    )

    tracker.on_receive(_routing_packet(12346, "NO_RESPONSE"), _iface())

    updated = tracker.recent_chat[-1]
    assert updated["delivery_state"] == "nak"
    assert updated["delivery_error"] == "NO_RESPONSE"


def test_pending_delivery_times_out_during_snapshot():
    tracker = md.DashboardTracker(packet_limit=16, history_store=None)
    tracker.record_local_chat(
        text="hello",
        from_id="!local000",
        to_id="!peer0003",
        message_id=12347,
        ack_requested=True,
    )
    tracker._chat_delivery_timeout_seconds = 5

    entry = tracker.recent_chat[-1]
    entry["delivery_updated_unix"] = int(time.time()) - 30

    snap = tracker.snapshot(nodes_by_id={})
    latest = snap["recent_chat"][-1]
    assert latest["delivery_state"] == "timeout"
    assert "No ACK received" in latest["delivery_error"]


def test_broadcast_local_chat_is_not_tracked_for_ack():
    tracker = md.DashboardTracker(packet_limit=16, history_store=None)
    tracker.record_local_chat(
        text="hello everyone",
        from_id="!local000",
        to_id="^all",
        message_id=12348,
        ack_requested=True,
    )

    entry = tracker.recent_chat[-1]
    assert entry["delivery_state"] == "sent"
    assert "ack_requested" not in entry


def test_tracker_ignores_packets_after_stop_receiving():
    tracker = md.DashboardTracker(packet_limit=16, history_store=None)
    tracker.stop_receiving()
    tracker.on_receive(_routing_packet(12349, "NONE"), _iface())

    assert tracker.live_packet_count == 0
    assert list(tracker.recent_packets) == []
