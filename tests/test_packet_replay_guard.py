from meshdash.packet_replay_guard import PacketReplayGuard


def _packet(packet_id: int, *, sender: int = 1, channel: int = 0) -> dict[str, object]:
    return {
        "from": sender,
        "id": packet_id,
        "channel": channel,
        "decoded": {"portnum": "TEXT_MESSAGE_APP"},
    }


def test_packet_replay_guard_rejects_recent_duplicates_and_allows_expired_keys() -> None:
    guard = PacketReplayGuard(ttl_seconds=10, max_entries=4)
    packet = _packet(7)

    assert guard.accept(packet, now_monotonic=100) is True
    assert guard.accept(packet, now_monotonic=105) is False
    assert guard.accept(packet, now_monotonic=116) is True


def test_packet_replay_guard_is_bounded_and_uses_full_envelope_key() -> None:
    guard = PacketReplayGuard(ttl_seconds=100, max_entries=2)

    assert guard.accept(_packet(1), now_monotonic=1) is True
    assert guard.accept(_packet(1, channel=1), now_monotonic=2) is True
    assert guard.accept(_packet(2), now_monotonic=3) is True
    assert len(guard) == 2
    assert guard.accept(_packet(1), now_monotonic=4) is True

    guard.clear()
    assert len(guard) == 0


def test_packet_replay_guard_rejects_packets_without_a_valid_numeric_sender() -> None:
    guard = PacketReplayGuard()

    assert guard.accept({"decoded": {}}, now_monotonic=1) is False
    assert guard.accept({"from": 1, "to": 2, "id": 0}, now_monotonic=1) is True
    assert guard.accept({"from": True, "id": 1}, now_monotonic=1) is False
    assert guard.accept({"from": 1.5, "id": 1}, now_monotonic=1) is False
    assert guard.accept({"from": 0xFFFFFFFF, "id": 1}, now_monotonic=1) is False


def test_packet_replay_guard_rejects_malformed_key_envelope_values() -> None:
    guard = PacketReplayGuard()

    assert guard.accept({"from": 1, "id": 1, "channel": True}, now_monotonic=1) is False
    assert guard.accept({"from": 1, "id": 0, "channel": 0}, now_monotonic=1) is False
    assert (
        guard.accept(
            {"from": 1, "to": True, "id": 0, "channel": 0},
            now_monotonic=1,
        )
        is False
    )


def test_packet_replay_guard_fingerprints_text_when_packet_id_is_missing() -> None:
    guard = PacketReplayGuard()
    packet = {
        "from": 1,
        "to": 2,
        "id": 0,
        "channel": 0,
        "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "status"},
    }

    assert guard.accept(packet, now_monotonic=1) is True
    assert guard.accept(packet, now_monotonic=2) is False


def test_packet_replay_guard_ignores_mutable_receive_time_in_fallback_key() -> None:
    guard = PacketReplayGuard()
    packet = {
        "from": 1,
        "to": 2,
        "id": 0,
        "channel": 0,
        "rxTime": 100,
        "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "status"},
    }

    assert guard.accept(packet, now_monotonic=1) is True
    assert guard.accept({**packet, "rxTime": 101}, now_monotonic=2) is False


def test_packet_replay_guard_fingerprints_non_text_updates_without_packet_id() -> None:
    guard = PacketReplayGuard()
    packet = {
        "from": 1,
        "to": 2,
        "channel": 0,
        "decoded": {
            "portnum": "NEIGHBORINFO_APP",
            "neighborinfo": {"node_id": 1, "neighbors": [{"node_id": 3}]},
        },
    }

    assert guard.accept(packet, now_monotonic=1) is True
    assert guard.accept(packet, now_monotonic=2) is False
