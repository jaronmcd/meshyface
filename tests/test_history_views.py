from meshdash.history_views import (
    build_node_history_loader,
    build_online_activity_loader,
    build_summary_metrics_loader,
    empty_node_history,
    empty_online_activity,
    empty_summary_metrics,
)


class _FakeHistoryStore:
    def __init__(self):
        self.node_calls = []
        self.online_calls = []

    def load_node_history(self, *, node_id, window_hours, max_points):
        self.node_calls.append((node_id, window_hours, max_points))
        return {"node_id": node_id, "window_hours": window_hours, "max_points": max_points}

    def load_online_activity(self, *, window_hours):
        self.online_calls.append(window_hours)
        return {"window_hours": window_hours, "points": []}

    def load_summary_metrics(self, *, window_hours):
        self.online_calls.append(("summary", window_hours))
        return {"window_hours": window_hours, "points": [{"bucket_unix": 60}]}


def test_empty_history_payload_shapes():
    node_empty = empty_node_history("!abc123")
    assert node_empty["node_id"] == "!abc123"
    assert node_empty["points"] == []
    assert node_empty["positions"] == []

    online_empty = empty_online_activity(12)
    assert online_empty["window_hours"] == 12
    assert len(online_empty["hourly_profile"]) == 24

    online_invalid = empty_online_activity(0)
    assert online_invalid["window_hours"] == 72
    online_non_int = empty_online_activity("bad")  # type: ignore[arg-type]
    assert online_non_int["window_hours"] == 72

    summary_empty = empty_summary_metrics(6)
    assert summary_empty["window_hours"] == 6
    assert summary_empty["points"] == []

    summary_invalid = empty_summary_metrics(0)
    assert summary_invalid["window_hours"] == 72


def test_history_loaders_apply_defaults_and_overrides():
    store = _FakeHistoryStore()
    node_loader = build_node_history_loader(store, default_hours=72, default_points=1440)
    online_loader = build_online_activity_loader(store, default_hours=72)
    summary_loader = build_summary_metrics_loader(store, default_hours=72)

    node_payload = node_loader(" !node1 ", None, None)
    assert node_payload["node_id"] == "!node1"
    assert node_payload["window_hours"] == 72
    assert node_payload["max_points"] == 1440

    node_payload = node_loader("!node2", 6, 120)
    assert node_payload["window_hours"] == 6
    assert node_payload["max_points"] == 120

    online_payload = online_loader(None)
    assert online_payload["window_hours"] == 72
    online_payload = online_loader(24)
    assert online_payload["window_hours"] == 24

    node_payload = node_loader("!node3", 0, -1)
    assert node_payload["window_hours"] == 72
    assert node_payload["max_points"] == 1440

    online_payload = online_loader(0)
    assert online_payload["window_hours"] == 72

    summary_payload = summary_loader(None)
    assert summary_payload["window_hours"] == 72
    summary_payload = summary_loader(24)
    assert summary_payload["window_hours"] == 24


def test_history_loaders_without_store_return_empty_payloads():
    node_loader = build_node_history_loader(None, default_hours=72, default_points=1440)
    online_loader = build_online_activity_loader(None, default_hours=72)
    summary_loader = build_summary_metrics_loader(None, default_hours=72)

    node_payload = node_loader(" !xyz ", 5, 20)
    assert node_payload["node_id"] == "!xyz"
    assert node_payload["points"] == []

    online_payload = online_loader(None)
    assert online_payload["window_hours"] == 72
    assert len(online_payload["hourly_profile"]) == 24

    summary_payload = summary_loader(None)
    assert summary_payload["window_hours"] == 72
    assert summary_payload["points"] == []
