from collections import deque

from meshdash.tracker_live_retention import (
    DEFAULT_MAX_RETAINED_LIVE_CHAT_ROWS,
    DEFAULT_MAX_RETAINED_LIVE_EDGE_ROWS,
    DEFAULT_MAX_RETAINED_LIVE_PACKET_ROWS,
)
from meshdash.tracker_runtime_impl import DashboardTracker


def _edge(index: int) -> dict[str, object]:
    return {
        "from": f"!from{index}",
        "to": "!to",
        "count": 2,
        "first_rx_time": index,
        "last_rx_time": index,
        "portnums": set(),
        "last_hops": None,
        "hops_sum": 0,
        "hops_count": 0,
        "snr_sum": 0.0,
        "snr_count": 0,
        "snr_min": None,
        "snr_max": None,
        "rssi_sum": 0.0,
        "rssi_count": 0,
        "rssi_min": None,
        "rssi_max": None,
    }


def test_purge_live_state_keeps_under_cap_chat_regardless_of_age() -> None:
    tracker = DashboardTracker(packet_limit=8)
    tracker.recent_chat = deque(
        [
            {"text": "old 1", "rx_time_unix": 1_000},
            {"text": "old 2", "rx_time_unix": 1_001},
            {"text": "old 3", "rx_time_unix": 1_002},
            {"text": "old 4", "rx_time_unix": 1_003},
        ],
        maxlen=32,
    )

    result = tracker.purge_live_state(now_unix=10_000)

    assert result["recent_chat"] == 0
    assert [entry["text"] for entry in tracker.recent_chat] == [
        "old 1",
        "old 2",
        "old 3",
        "old 4",
    ]


def test_purge_live_state_does_not_bump_revision_without_changes() -> None:
    tracker = DashboardTracker(packet_limit=8)
    tracker.recent_chat.append({"text": "recent", "rx_time_unix": 9_999})

    before_revision = tracker.state_revision
    result = tracker.purge_live_state(now_unix=10_000)

    assert result["total_removed"] == 0
    assert tracker.state_revision == before_revision


def test_purge_live_state_trims_buffers_fifo_to_size_caps() -> None:
    tracker = DashboardTracker(packet_limit=8)
    tracker._max_retained_live_packet_rows = 3
    tracker._max_retained_live_chat_rows = 4
    tracker._max_retained_live_edge_rows = 2
    tracker.recent_packets = deque(
        ({"summary": {"packet_id": index}} for index in range(6)),
        maxlen=8,
    )
    tracker.recent_chat = deque(
        ({"text": f"msg {index}"} for index in range(7)),
        maxlen=16,
    )
    tracker.edges = {
        (f"!edge{index}", "!peer"): _edge(index)
        for index in range(5)
    }
    tracker._historical_edges = {
        (f"!hist{index}", "!peer"): _edge(index)
        for index in range(5)
    }

    before_revision = tracker.state_revision
    result = tracker.purge_live_state(now_unix=10_000)

    assert result == {
        "recent_packets": 3,
        "recent_chat": 3,
        "edges": 3,
        "historical_edges": 3,
        "total_removed": 12,
    }
    assert tracker.state_revision == before_revision + 1
    assert [entry["summary"]["packet_id"] for entry in tracker.recent_packets] == [3, 4, 5]
    assert [entry["text"] for entry in tracker.recent_chat] == ["msg 3", "msg 4", "msg 5", "msg 6"]
    assert list(tracker.edges) == [("!edge3", "!peer"), ("!edge4", "!peer")]
    assert list(tracker._historical_edges) == [("!hist3", "!peer"), ("!hist4", "!peer")]


def test_snapshot_typed_purges_before_returning_live_payload() -> None:
    tracker = DashboardTracker(packet_limit=8)
    tracker._max_retained_live_packet_rows = 1
    tracker._max_retained_live_chat_rows = 1
    tracker._max_retained_live_edge_rows = 1
    tracker.recent_packets.extend(
        [
            {"summary": {"packet_id": 1}},
            {"summary": {"packet_id": 2}},
        ]
    )
    tracker.recent_chat.extend(
        [
            {"text": "older"},
            {"text": "newer"},
        ]
    )
    tracker.edges[("!old", "!peer")] = _edge(1)
    tracker.edges[("!new", "!peer")] = _edge(2)

    snapshot = tracker.snapshot_typed({})

    assert [entry["summary"]["packet_id"] for entry in snapshot.recent_packets] == [2]
    assert [entry["text"] for entry in snapshot.recent_chat] == ["newer"]
    assert {(edge["from"], edge["to"]) for edge in snapshot.edges} == {("!new", "!peer")}


def test_default_caps_bound_day_long_live_state_without_time_checks() -> None:
    tracker = DashboardTracker(packet_limit=250)
    tracker.recent_chat.extend(
        {"text": f"old-{index}", "rx_time_unix": 1_000 + index}
        for index in range(1_000)
    )
    tracker.recent_packets.extend(
        {"summary": {"packet_id": index, "rx_time_unix": 1_000 + index}}
        for index in range(250)
    )
    tracker.edges.update(
        {
            (f"!edge{index:04x}", "!peer"): _edge(index)
            for index in range(802)
        }
    )

    snapshot = tracker.snapshot_typed({})

    assert len(snapshot.recent_chat) == DEFAULT_MAX_RETAINED_LIVE_CHAT_ROWS
    assert snapshot.recent_chat[0]["text"] == "old-820"
    assert snapshot.recent_chat[-1]["text"] == "old-999"
    assert len(snapshot.recent_packets) == DEFAULT_MAX_RETAINED_LIVE_PACKET_ROWS
    assert snapshot.recent_packets[0]["summary"]["packet_id"] == 130
    assert snapshot.recent_packets[-1]["summary"]["packet_id"] == 249
    assert len(snapshot.edges) == DEFAULT_MAX_RETAINED_LIVE_EDGE_ROWS
