from __future__ import annotations

import threading
from dataclasses import dataclass

from meshdash import services_chat
from meshdash.helpers import to_int
from meshdash.services_chat import send_chat_message


@dataclass
class _SentPacket:
    id: int


class _FakeIface:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    def sendText(self, text: str, **kwargs: object) -> _SentPacket:
        packet = _SentPacket(id=1000 + len(self.sent))
        self.sent.append({"id": packet.id, "text": text, **kwargs})
        return packet


def _send_reaction_packet_fn(**_kwargs: object) -> object:
    raise AssertionError("reaction sends are not used in these tests")


def _base_send_kwargs(iface: _FakeIface, records: list[dict[str, object]]) -> dict[str, object]:
    return {
        "text": "look",
        "destination": "!3369d0b8",
        "channel_index": 0,
        "reply_id": None,
        "retry_of": None,
        "emoji": None,
        "iface": iface,
        "send_lock": threading.Lock(),
        "send_reaction_packet_fn": _send_reaction_packet_fn,
        "local_node_id_fn": lambda: "!49b5dff0",
        "record_local_chat_fn": lambda **kwargs: records.append(kwargs),
        "chat_max_bytes": 200,
        "normalize_single_emoji_fn": lambda _value: (None, None),
        "to_int_fn": to_int,
        "now_text_fn": lambda: "2026-05-09 00:00:00Z",
        "outgoing_retry_wait_seconds": 0,
        "outgoing_retry_poll_seconds": 0.01,
        "outgoing_retry_limit": 1,
        "outgoing_retry_async": False,
        "sleep_fn": lambda _seconds: None,
    }


def test_send_chat_message_retries_unacked_direct_text_once() -> None:
    iface = _FakeIface()
    records: list[dict[str, object]] = []

    response = send_chat_message(
        **_base_send_kwargs(iface, records),
        get_delivery_state_fn=lambda _message_id: {"delivery_state": "pending"},
    )

    assert response["message_id"] == 1000
    assert [row["id"] for row in iface.sent] == [1000, 1001]
    assert len(records) == 2
    assert records[0]["message_id"] == 1000
    assert records[0]["retry_of"] is None
    assert records[1]["message_id"] == 1001
    assert records[1]["retry_of"] == 1000


def test_send_chat_message_does_not_retry_acked_direct_text() -> None:
    iface = _FakeIface()
    records: list[dict[str, object]] = []

    send_chat_message(
        **_base_send_kwargs(iface, records),
        get_delivery_state_fn=lambda _message_id: {"delivery_state": "acked"},
    )

    assert [row["id"] for row in iface.sent] == [1000]
    assert len(records) == 1
    assert records[0]["retry_of"] is None


def test_send_chat_message_skips_async_retry_when_worker_limit_is_full(
    monkeypatch,
) -> None:
    class _FullRetrySlots:
        @staticmethod
        def acquire(*, blocking: bool) -> bool:
            assert blocking is False
            return False

    iface = _FakeIface()
    records: list[dict[str, object]] = []
    kwargs = _base_send_kwargs(iface, records)
    kwargs["outgoing_retry_async"] = True
    monkeypatch.setattr(services_chat, "_OUTGOING_RETRY_SLOTS", _FullRetrySlots())

    send_chat_message(
        **kwargs,
        get_delivery_state_fn=lambda _message_id: {"delivery_state": "pending"},
    )

    assert [row["id"] for row in iface.sent] == [1000]
    assert len(records) == 1
