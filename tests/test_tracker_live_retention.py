from collections import deque

import meshdash.tracker_runtime_impl as tracker_runtime_impl
from meshdash.tracker_live_retention import DEFAULT_LIVE_STATE_RETENTION_SECONDS
from meshdash.tracker_runtime_impl import DashboardTracker


def _edge(last_rx_time: int) -> dict[str, object]:
    return {
        "from": "!from",
        "to": "!to",
        "count": 2,
        "first_rx_time": last_rx_time,
        "last_rx_time": last_rx_time,
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


def test_purge_live_state_removes_old_live_resources_only() -> None:
    tracker = DashboardTracker(packet_limit=8)
    now_unix = 10_000
    cutoff_unix = now_unix - DEFAULT_LIVE_STATE_RETENTION_SECONDS
    old_unix = cutoff_unix - 1
    recent_unix = cutoff_unix

    tracker.recent_packets = deque(
        [
            {"summary": {"packet_id": 1, "rx_time_unix": old_unix}},
            {"summary": {"packet_id": 2, "rx_time_unix": recent_unix}},
            {"summary": {"packet_id": 3}},
        ],
        maxlen=8,
    )
    tracker.recent_chat = deque(
        [
            {"text": "old", "rx_time_unix": old_unix},
            {"text": "recent", "rx_time_unix": recent_unix},
            {"text": "unknown"},
        ],
        maxlen=32,
    )
    tracker.edges = {
        ("!old", "!peer"): _edge(old_unix),
        ("!recent", "!peer"): _edge(recent_unix),
        ("!unknown", "!peer"): {"from": "!unknown", "to": "!peer", "count": 2},
    }
    tracker._historical_edges = {
        ("!oldhist", "!peer"): _edge(old_unix),
        ("!recenthist", "!peer"): _edge(recent_unix),
    }

    before_revision = tracker.state_revision
    result = tracker.purge_live_state(now_unix=now_unix)

    assert result == {
        "recent_packets": 1,
        "recent_chat": 1,
        "edges": 1,
        "historical_edges": 1,
        "total_removed": 4,
    }
    assert tracker.state_revision == before_revision + 1
    assert [entry["summary"].get("packet_id") for entry in tracker.recent_packets] == [2, 3]
    assert [entry["text"] for entry in tracker.recent_chat] == ["recent", "unknown"]
    assert set(tracker.edges) == {("!recent", "!peer"), ("!unknown", "!peer")}
    assert set(tracker._historical_edges) == {("!recenthist", "!peer")}


def test_purge_live_state_does_not_bump_revision_without_changes() -> None:
    tracker = DashboardTracker(packet_limit=8)
    tracker.recent_chat.append({"text": "recent", "rx_time_unix": 9_999})

    before_revision = tracker.state_revision
    result = tracker.purge_live_state(now_unix=10_000)

    assert result["total_removed"] == 0
    assert tracker.state_revision == before_revision


def test_snapshot_typed_purges_before_returning_live_payload(monkeypatch) -> None:
    monkeypatch.setattr(tracker_runtime_impl.time, "time", lambda: 10_000.0)
    tracker = DashboardTracker(packet_limit=8)
    cutoff_unix = 10_000 - DEFAULT_LIVE_STATE_RETENTION_SECONDS
    old_unix = cutoff_unix - 1
    recent_unix = cutoff_unix + 1

    tracker.recent_packets.extend(
        [
            {"summary": {"packet_id": 1, "rx_time_unix": old_unix}},
            {"summary": {"packet_id": 2, "rx_time_unix": recent_unix}},
        ]
    )
    tracker.recent_chat.extend(
        [
            {"text": "old", "rx_time_unix": old_unix},
            {"text": "recent", "rx_time_unix": recent_unix},
        ]
    )
    tracker.edges[("!old", "!peer")] = _edge(old_unix)
    tracker.edges[("!recent", "!peer")] = _edge(recent_unix)

    snapshot = tracker.snapshot_typed({})

    assert [entry["summary"]["packet_id"] for entry in snapshot.recent_packets] == [2]
    assert [entry["text"] for entry in snapshot.recent_chat] == ["recent"]
    assert {(edge["from"], edge["to"]) for edge in snapshot.edges} == {("!recent", "!peer")}
