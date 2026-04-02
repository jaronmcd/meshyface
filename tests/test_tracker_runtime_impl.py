import types

import meshdash.tracker_runtime_impl as tracker_runtime_impl


def _patch_runtime_init(monkeypatch):
    def _fake_init(
        self,
        *,
        packet_limit,
        history_store,
        default_chat_delivery_timeout_seconds,
        initialize_tracker_buffers_fn,
        build_tracker_delivery_callbacks_fn,
        apply_tracker_history_bootstrap_fn,
        load_tracker_history_bootstrap_fn,
        build_historical_edges_fn,
        parse_utc_text_to_unix_fn,
        utc_now_fn,
        to_int_fn,
        now_unix_fn,
    ):
        del history_store
        del default_chat_delivery_timeout_seconds
        del initialize_tracker_buffers_fn
        del build_tracker_delivery_callbacks_fn
        del apply_tracker_history_bootstrap_fn
        del load_tracker_history_bootstrap_fn
        del build_historical_edges_fn
        del parse_utc_text_to_unix_fn
        del utc_now_fn
        del to_int_fn
        del now_unix_fn
        self.packet_limit = packet_limit
        self.live_packet_count = 0
        self.recent_packets = []
        self.recent_chat = []

    monkeypatch.setattr(tracker_runtime_impl, "_initialize_dashboard_tracker_runtime_helper", _fake_init)


def test_on_receive_stop_receiving_and_seed_packet_delegate_include_live_count(monkeypatch):
    _patch_runtime_init(monkeypatch)
    calls = []

    def _record_helper(tracker, *, packet, interface, include_live_count):
        calls.append(
            {
                "tracker": tracker,
                "packet": packet,
                "interface": interface,
                "include_live_count": include_live_count,
            }
        )

    monkeypatch.setattr(tracker_runtime_impl, "_record_tracker_receive_unlocked_for_tracker_helper", _record_helper)

    tracker = tracker_runtime_impl.DashboardTracker(packet_limit=16, history_store=None)
    iface = object()

    tracker.on_receive({"id": 1}, iface)
    assert tracker.live_packet_count == 1
    assert calls[-1]["include_live_count"] is True

    tracker.stop_receiving()
    tracker.on_receive({"id": 2}, iface)
    assert tracker.live_packet_count == 1
    assert len(calls) == 1

    tracker.seed_packet({"id": 3}, iface)
    assert tracker.live_packet_count == 1
    assert calls[-1]["include_live_count"] is False


def test_has_recent_packets_and_loaders_delegate_to_helpers(monkeypatch):
    _patch_runtime_init(monkeypatch)
    monkeypatch.setattr(
        tracker_runtime_impl,
        "_load_tracker_node_saved_counts_for_tracker_helper",
        lambda _tracker: {"!a": {"saved_count": 3}},
    )
    monkeypatch.setattr(
        tracker_runtime_impl,
        "_load_tracker_node_capabilities_for_tracker_helper",
        lambda _tracker: {"!a": {"has_position": True}},
    )

    tracker = tracker_runtime_impl.DashboardTracker(packet_limit=4, history_store=None)
    assert tracker.has_recent_packets() is False
    tracker.recent_packets.append({"id": 1})
    assert tracker.has_recent_packets() is True
    assert tracker.load_node_saved_counts() == {"!a": {"saved_count": 3}}
    assert tracker.load_node_capabilities() == {"!a": {"has_position": True}}


def test_record_local_chat_passes_expected_arguments(monkeypatch):
    _patch_runtime_init(monkeypatch)
    captured = {}

    def _record_chat_helper(
        tracker,
        *,
        text,
        from_id,
        to_id,
        channel_index,
        message_id,
        reply_id,
        emoji,
        emoji_codepoint,
        is_reaction,
        ack_requested,
        retry_of,
        now_unix_fn,
    ):
        captured.update(
            {
                "tracker": tracker,
                "text": text,
                "from_id": from_id,
                "to_id": to_id,
                "channel_index": channel_index,
                "message_id": message_id,
                "reply_id": reply_id,
                "emoji": emoji,
                "emoji_codepoint": emoji_codepoint,
                "is_reaction": is_reaction,
                "ack_requested": ack_requested,
                "retry_of": retry_of,
                "now_unix": int(now_unix_fn()),
            }
        )

    monkeypatch.setattr(
        tracker_runtime_impl,
        "_record_tracker_local_chat_for_tracker_helper",
        _record_chat_helper,
    )
    monkeypatch.setattr(tracker_runtime_impl.time, "time", lambda: 1234)

    tracker = tracker_runtime_impl.DashboardTracker(packet_limit=8, history_store=None)
    tracker.record_local_chat(
        text="hello",
        from_id="!from",
        to_id="!to",
        channel_index=2,
        message_id=99,
        reply_id=88,
        emoji=":)",
        emoji_codepoint=0x1F642,
        is_reaction=True,
        ack_requested=True,
        retry_of=42,
    )

    assert captured["tracker"] is tracker
    assert captured["text"] == "hello"
    assert captured["from_id"] == "!from"
    assert captured["to_id"] == "!to"
    assert captured["channel_index"] == 2
    assert captured["message_id"] == 99
    assert captured["reply_id"] == 88
    assert captured["emoji"] == ":)"
    assert captured["emoji_codepoint"] == 0x1F642
    assert captured["is_reaction"] is True
    assert captured["ack_requested"] is True
    assert captured["retry_of"] == 42
    assert captured["now_unix"] == 1234


def test_bootstrap_connection_state_and_connection_callbacks(monkeypatch):
    _patch_runtime_init(monkeypatch)
    monkeypatch.setattr(tracker_runtime_impl.time, "time", lambda: 5555)
    tracker = tracker_runtime_impl.DashboardTracker(packet_limit=8, history_store=None)

    tracker.bootstrap_connection_state(types.SimpleNamespace(isConnected=True))
    assert tracker.radio_link_snapshot() == {
        "connected": True,
        "changed_unix": 5555,
        "error": None,
    }

    tracker.bootstrap_connection_state(types.SimpleNamespace(isConnected=False))
    assert tracker.radio_link_snapshot() == {
        "connected": False,
        "changed_unix": 5555,
        "error": "link not established",
    }

    class _IsSet:
        def is_set(self):
            return True

    tracker.bootstrap_connection_state(types.SimpleNamespace(isConnected=_IsSet()))
    assert tracker.radio_link_snapshot()["connected"] is True

    class _BrokenIsSet:
        def is_set(self):
            raise RuntimeError("boom")

    before = tracker.radio_link_snapshot().copy()
    tracker.bootstrap_connection_state(types.SimpleNamespace(isConnected=_BrokenIsSet()))
    tracker.bootstrap_connection_state(types.SimpleNamespace())
    assert tracker.radio_link_snapshot() == before

    tracker.on_connection_established()
    assert tracker.radio_link_snapshot()["connected"] is True
    assert tracker.radio_link_snapshot()["error"] is None

    tracker.on_connection_lost(reason=" link dropped ")
    assert tracker.radio_link_snapshot()["connected"] is False
    assert tracker.radio_link_snapshot()["error"] == "link dropped"

    tracker.on_connection_lost()
    assert tracker.radio_link_snapshot()["error"] == "connection lost"


def test_snapshot_typed_snapshot_and_seed_delegations(monkeypatch):
    _patch_runtime_init(monkeypatch)
    snapshot_calls = {}
    seed_calls = {}

    class _FakeSnapshot:
        def __init__(self):
            self.value = {"ok": True, "rows": 3}

        def as_dict(self):
            return dict(self.value)

    fake_snapshot = _FakeSnapshot()

    def _build_snapshot_helper(tracker, *, nodes_by_id, min_real_link_count):
        snapshot_calls.update(
            {
                "tracker": tracker,
                "nodes_by_id": nodes_by_id,
                "min_real_link_count": min_real_link_count,
            }
        )
        return fake_snapshot

    def _seed_helper(tracker, iface):
        seed_calls.update({"tracker": tracker, "iface": iface})

    monkeypatch.setattr(
        tracker_runtime_impl,
        "_build_tracker_snapshot_for_tracker_typed_helper",
        _build_snapshot_helper,
    )
    monkeypatch.setattr(tracker_runtime_impl, "_seed_tracker_from_node_db_helper", _seed_helper)

    tracker = tracker_runtime_impl.DashboardTracker(packet_limit=8, history_store=None)
    typed = tracker.snapshot_typed({"!a": {"name": "A"}})
    assert typed is fake_snapshot
    assert snapshot_calls["tracker"] is tracker
    assert snapshot_calls["nodes_by_id"] == {"!a": {"name": "A"}}
    assert snapshot_calls["min_real_link_count"] == tracker_runtime_impl.MIN_REAL_LINK_COUNT

    as_dict = tracker.snapshot({"!b": {"name": "B"}})
    assert as_dict == {"ok": True, "rows": 3}

    iface = object()
    tracker_runtime_impl.seed_tracker_from_node_db(tracker, iface)
    assert seed_calls["tracker"] is tracker
    assert seed_calls["iface"] is iface
