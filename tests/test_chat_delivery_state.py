from meshdash.chat_delivery_state import set_delivery_state


def _pending_direct_echo() -> dict[str, object]:
    return {
        "local_echo": True,
        "message_id": 1234,
        "from": "!3369d0b8",
        "to": "!02e5e3a4",
        "delivery_state": "pending",
        "delivery_updated_at": "2026-05-10 00:00:00Z",
        "delivery_updated_unix": 1778371200,
    }


def test_set_delivery_state_ignores_self_implicit_ack_for_direct_message() -> None:
    entry = _pending_direct_echo()

    changed = set_delivery_state(
        [entry],
        1234,
        "acked",
        ack_from_id="!3369d0b8",
        ack_to_id="!3369d0b8",
        now_text_fn=lambda: "2026-05-10 00:00:10Z",
        now_unix_fn=lambda: 1778371210,
    )

    assert changed is False
    assert entry["delivery_state"] == "pending"
    assert "delivery_ack_from" not in entry


def test_set_delivery_state_accepts_ack_from_original_destination() -> None:
    entry = _pending_direct_echo()

    changed = set_delivery_state(
        [entry],
        1234,
        "acked",
        ack_from_id="!02e5e3a4",
        ack_to_id="!3369d0b8",
        now_text_fn=lambda: "2026-05-10 00:00:10Z",
        now_unix_fn=lambda: 1778371210,
    )

    assert changed is True
    assert entry["delivery_state"] == "acked"
    assert entry["delivery_ack_from"] == "!02e5e3a4"
    assert entry["delivery_ack_to"] == "!3369d0b8"


def test_set_delivery_state_rejects_nak_when_not_from_destination() -> None:
    entry = _pending_direct_echo()

    changed = set_delivery_state(
        [entry],
        1234,
        "nak",
        "NO_CHANNEL",
        ack_from_id="!3369d0b8",
        ack_to_id="!3369d0b8",
        now_text_fn=lambda: "2026-05-10 00:00:10Z",
        now_unix_fn=lambda: 1778371210,
    )

    assert changed is False
    assert entry["delivery_state"] == "pending"
    assert "delivery_error" not in entry


def test_set_delivery_state_rejects_update_addressed_to_another_node() -> None:
    entry = _pending_direct_echo()

    changed = set_delivery_state(
        [entry],
        1234,
        "acked",
        ack_from_id="!02e5e3a4",
        ack_to_id="!ffffffff",
        now_text_fn=lambda: "2026-05-10 00:00:10Z",
        now_unix_fn=lambda: 1778371210,
    )

    assert changed is False
    assert entry["delivery_state"] == "pending"


def test_set_delivery_state_rejects_update_without_transport_endpoints() -> None:
    entry = _pending_direct_echo()

    changed = set_delivery_state(
        [entry],
        1234,
        "acked",
        now_text_fn=lambda: "2026-05-10 00:00:10Z",
        now_unix_fn=lambda: 1778371210,
    )

    assert changed is False
    assert entry["delivery_state"] == "pending"
