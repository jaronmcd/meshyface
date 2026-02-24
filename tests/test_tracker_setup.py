from meshdash.tracker_setup import (
    apply_tracker_history_bootstrap,
    initialize_tracker_buffers,
)


def test_initialize_tracker_buffers_creates_expected_collections():
    buffers = initialize_tracker_buffers(5)
    assert buffers["edges"] == {}
    assert buffers["historical_edges"] == {}
    assert list(buffers["recent_packets"]) == []
    assert list(buffers["recent_chat"]) == []
    assert buffers["recent_packets"].maxlen == 5
    assert buffers["recent_chat"].maxlen == 5


def test_apply_tracker_history_bootstrap_handles_none_history_store():
    recent_packets = []
    recent_chat = []
    historical = apply_tracker_history_bootstrap(
        history_store=None,
        packet_limit=5,
        recent_packets=recent_packets,
        recent_chat=recent_chat,
        load_tracker_history_bootstrap_fn=lambda *_a, **_k: {"historical_edges": {"bad": "call"}},
        build_historical_edges_fn=lambda *_a, **_k: {},
    )
    assert historical == {}
    assert recent_packets == []
    assert recent_chat == []


def test_apply_tracker_history_bootstrap_extends_recent_buffers():
    recent_packets = []
    recent_chat = []
    bootstrap_calls = {}

    def _load_bootstrap(store, *, packet_limit, build_historical_edges_fn):
        bootstrap_calls["store"] = store
        bootstrap_calls["packet_limit"] = packet_limit
        bootstrap_calls["builder"] = build_historical_edges_fn
        return {
            "recent_packets": [{"id": 1}],
            "recent_chat": [{"message_id": 2}],
            "historical_edges": {("a", "b"): {"count": 3}},
        }

    historical = apply_tracker_history_bootstrap(
        history_store="history-store",
        packet_limit=9,
        recent_packets=recent_packets,
        recent_chat=recent_chat,
        load_tracker_history_bootstrap_fn=_load_bootstrap,
        build_historical_edges_fn="edge-builder",
    )
    assert bootstrap_calls["store"] == "history-store"
    assert bootstrap_calls["packet_limit"] == 9
    assert bootstrap_calls["builder"] == "edge-builder"
    assert recent_packets == [{"id": 1}]
    assert recent_chat == [{"message_id": 2}]
    assert historical == {("a", "b"): {"count": 3}}
