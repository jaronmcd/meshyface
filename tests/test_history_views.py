from meshdash.history_views import (
    build_node_history_loader,
    build_online_activity_loader,
    empty_node_history,
    empty_online_activity,
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


def test_empty_history_payload_shapes():
    node_empty = empty_node_history("!abc123")
    assert node_empty["node_id"] == "!abc123"
    assert node_empty["points"] == []
    assert node_empty["positions"] == []

    online_empty = empty_online_activity(12)
    assert online_empty["window_hours"] == 12
    assert len(online_empty["hourly_profile"]) == 24


def test_history_loaders_apply_defaults_and_overrides():
    store = _FakeHistoryStore()
    node_loader = build_node_history_loader(store, default_hours=72, default_points=1440)
    online_loader = build_online_activity_loader(store, default_hours=72)

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


def test_history_loaders_without_store_return_empty_payloads():
    node_loader = build_node_history_loader(None, default_hours=72, default_points=1440)
    online_loader = build_online_activity_loader(None, default_hours=72)

    node_payload = node_loader(" !xyz ", 5, 20)
    assert node_payload["node_id"] == "!xyz"
    assert node_payload["points"] == []

    online_payload = online_loader(None)
    assert online_payload["window_hours"] == 72
    assert len(online_payload["hourly_profile"]) == 24
