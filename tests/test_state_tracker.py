from meshdash.state_tracker import (
    load_tracker_node_capabilities_safe,
    load_tracker_node_saved_counts_safe,
    load_tracker_snapshot_safe,
)
from meshdash.tracker_snapshot_contracts import TrackerSnapshot


class _OkTracker:
    def snapshot(self, by_id):
        return {
            "live_packet_count": 2,
            "real_edge_count": 1,
            "edges": [{"from": "!a", "to": "!b"}],
            "port_counts": [{"portnum": "TEXT_MESSAGE_APP", "count": 3}],
            "recent_packets": [{"summary": {"id": 1}}],
            "recent_chat": [{"text": "hello"}],
        }

    def load_node_saved_counts(self):
        return {"!a": {"saved_packets": 2}}

    def load_node_capabilities(self):
        return {"!a": {"gps_capable": True}}


class _FailTracker:
    def snapshot(self, by_id):
        raise RuntimeError("snapshot failed")

    def load_node_saved_counts(self):
        raise RuntimeError("saved failed")

    def load_node_capabilities(self):
        raise RuntimeError("caps failed")


class _TypedSnapshotTracker:
    def __init__(self):
        self.snapshot_calls = 0
        self.snapshot_typed_calls = 0

    def snapshot(self, by_id):
        self.snapshot_calls += 1
        return {}

    def snapshot_typed(self, by_id):
        self.snapshot_typed_calls += 1
        return TrackerSnapshot(
            live_packet_count=9,
            real_edge_count=4,
            edges=[{"from": "!a", "to": "!b"}],
            port_counts=[],
            recent_packets=[],
            recent_chat=[],
        )

    def load_node_saved_counts(self):
        return {}

    def load_node_capabilities(self):
        return {}


def test_load_tracker_snapshot_safe_success_path():
    out, error = load_tracker_snapshot_safe(_OkTracker(), {"!a": {"id": "!a"}})
    assert error is None
    assert out.live_packet_count == 2
    assert out.real_edge_count == 1
    assert out.edges[0]["from"] == "!a"


def test_load_tracker_snapshot_safe_failure_path_returns_empty_snapshot():
    out, error = load_tracker_snapshot_safe(_FailTracker(), {"!a": {"id": "!a"}})
    assert error == "snapshot failed"
    assert out.live_packet_count == 0
    assert out.real_edge_count == 0
    assert out.edges == []
    assert out.recent_chat == []


def test_load_tracker_snapshot_safe_prefers_snapshot_typed_when_available():
    tracker = _TypedSnapshotTracker()
    out, error = load_tracker_snapshot_safe(tracker, {"!a": {"id": "!a"}})
    assert error is None
    assert out.live_packet_count == 9
    assert out.real_edge_count == 4
    assert tracker.snapshot_typed_calls == 1
    assert tracker.snapshot_calls == 0


def test_load_tracker_node_saved_counts_safe_failure_path_returns_empty_mapping():
    out, error = load_tracker_node_saved_counts_safe(_FailTracker())
    assert error == "saved failed"
    assert out == {}


def test_load_tracker_node_capabilities_safe_failure_path_returns_empty_mapping():
    out, error = load_tracker_node_capabilities_safe(_FailTracker())
    assert error == "caps failed"
    assert out == {}
