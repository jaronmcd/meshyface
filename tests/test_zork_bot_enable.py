from types import SimpleNamespace

from meshdash.services_zork_bot import ZorkBotService
from meshdash.tracker_runtime_impl import DashboardTracker


class _FakeInterface:
    def __init__(self) -> None:
        self.myInfo = {"my_node_num": 0x12345678}
        self.nodesByNum = {
            0x12345678: {"user": {"id": "!12345678"}},
            0x01020304: {"user": {"id": "!01020304"}},
        }
        self.sent: list[dict[str, object]] = []

    def sendText(self, text: str, **kwargs: object) -> object:
        packet = SimpleNamespace(id=700 + len(self.sent))
        self.sent.append({"text": text, "kwargs": dict(kwargs), "packet": packet})
        return packet


class _FakeGame:
    def __init__(self, reply_text: str) -> None:
        self.reply_text = reply_text

    def try_handle_message(self, **_kwargs: object) -> object:
        return SimpleNamespace(handled=True, reply_text=self.reply_text)


def _direct_text_packet(text: str, *, to: int = 0x12345678, packet_id: int = 111) -> dict[str, object]:
    return {
        "from": 0x01020304,
        "to": to,
        "id": packet_id,
        "channel": 2,
        "decoded": {
            "portnum": "TEXT_MESSAGE_APP",
            "text": text,
        },
    }


def test_dashboard_tracker_does_not_answer_zork_when_disabled() -> None:
    tracker = DashboardTracker(packet_limit=25)
    iface = _FakeInterface()

    tracker.on_receive(_direct_text_packet("zork"), iface)

    assert iface.sent == []


def test_dashboard_tracker_answers_direct_zork_when_enabled() -> None:
    tracker = DashboardTracker(packet_limit=25)
    iface = _FakeInterface()
    assert tracker.enable_zork_bot(
        reply_segment_delay_seconds=0,
        reply_retry_limit=0,
        reply_async=False,
    ) is True

    tracker.on_receive(_direct_text_packet("zork"), iface)

    assert iface.sent
    combined_text = " ".join(str(row["text"]) for row in iface.sent)
    assert "zork: session started" in combined_text
    assert iface.sent[0]["kwargs"]["destinationId"] == "!01020304"
    assert iface.sent[0]["kwargs"]["wantAck"] is True
    assert iface.sent[0]["kwargs"]["channelIndex"] == 2
    assert iface.sent[0]["kwargs"]["replyId"] == 111
    replies = [
        row
        for row in tracker.recent_chat
        if isinstance(row, dict) and row.get("from") == "!12345678" and row.get("to") == "!01020304"
    ]
    assert replies
    assert replies[0].get("ack_requested") is True


def test_dashboard_tracker_answers_public_zork_trigger_with_direct_session() -> None:
    tracker = DashboardTracker(packet_limit=25)
    iface = _FakeInterface()
    assert tracker.enable_zork_bot(
        reply_segment_delay_seconds=0,
        reply_retry_limit=0,
        reply_async=False,
    ) is True

    tracker.on_receive(_direct_text_packet("zork", to=0xFFFFFFFF), iface)

    assert iface.sent
    combined_text = " ".join(str(row["text"]) for row in iface.sent)
    assert "zork: session started" in combined_text
    assert iface.sent[0]["kwargs"]["destinationId"] == "!01020304"
    assert iface.sent[0]["kwargs"]["wantAck"] is True
    assert iface.sent[0]["kwargs"]["channelIndex"] == 2
    assert iface.sent[0]["kwargs"]["replyId"] == 111


def test_dashboard_tracker_ignores_non_exact_public_zork_trigger() -> None:
    tracker = DashboardTracker(packet_limit=25)
    iface = _FakeInterface()
    assert tracker.enable_zork_bot(
        reply_segment_delay_seconds=0,
        reply_retry_limit=0,
        reply_async=False,
    ) is True

    tracker.on_receive(_direct_text_packet("zork please", to=0xFFFFFFFF), iface)
    tracker.on_receive(_direct_text_packet("zrok", to=0xFFFFFFFF, packet_id=112), iface)

    assert iface.sent == []


def test_dashboard_tracker_answers_local_direct_zork_without_radio_send() -> None:
    tracker = DashboardTracker(packet_limit=25)
    assert tracker.enable_zork_bot(
        reply_segment_delay_seconds=0,
        reply_retry_limit=0,
        reply_async=False,
    ) is True

    tracker.record_local_chat(
        text="zork",
        from_id="!12345678",
        to_id="!12345678",
        channel_index=0,
        message_id=222,
    )

    texts = [str(row.get("text") or "") for row in tracker.recent_chat if isinstance(row, dict)]
    assert any("zork: session started" in text for text in texts)


def test_dashboard_tracker_paces_multi_part_zork_replies() -> None:
    tracker = DashboardTracker(packet_limit=25)
    iface = _FakeInterface()
    sleeps: list[float] = []
    assert tracker.enable_zork_bot(
        reply_segment_delay_seconds=1.25,
        reply_retry_limit=0,
        reply_async=False,
        sleep_fn=sleeps.append,
    ) is True

    tracker.on_receive(_direct_text_packet("zork"), iface)

    assert len(iface.sent) == 2
    assert sleeps == [1.25]


def test_dashboard_tracker_retries_unacked_zork_reply_segments() -> None:
    tracker = DashboardTracker(packet_limit=25)
    iface = _FakeInterface()
    assert tracker.enable_zork_bot(
        reply_segment_delay_seconds=0,
        reply_ack_wait_seconds=0,
        reply_retry_limit=1,
        reply_async=False,
    ) is True

    tracker.on_receive(_direct_text_packet("zork"), iface)

    assert len(iface.sent) == 2
    assert iface.sent[0]["text"] == iface.sent[1]["text"]
    assert str(iface.sent[0]["text"]).startswith("[1/2]")
    original_id = iface.sent[0]["packet"].id
    retry_entries = [
        row
        for row in tracker.recent_chat
        if isinstance(row, dict) and row.get("retry_of") == original_id
    ]
    assert len(retry_entries) == 1


def test_zork_bot_waits_for_each_segment_ack_before_advancing() -> None:
    iface = _FakeInterface()
    delivery_states: dict[int, str] = {}
    records: list[dict[str, object]] = []
    service = ZorkBotService(
        game=_FakeGame("alpha " * 45),
        reply_segment_delay_seconds=0,
        reply_ack_wait_seconds=0,
        reply_retry_limit=1,
        reply_async=False,
        get_delivery_state_fn=lambda message_id: delivery_states.get(int(message_id)),
    )

    def record_local_chat_fn(**kwargs: object) -> None:
        records.append(dict(kwargs))
        message_id = kwargs.get("message_id")
        if not isinstance(message_id, int):
            return
        text = str(kwargs.get("text") or "")
        delivery_states[message_id] = "acked" if text.startswith("[1/") else "sent"

    handled = service.handle_packet(
        _direct_text_packet("zork"),
        iface,
        record_local_chat_fn=record_local_chat_fn,
    )

    assert handled is True
    assert len(iface.sent) == 3
    assert str(iface.sent[0]["text"]).startswith("[1/2]")
    assert str(iface.sent[1]["text"]).startswith("[2/2]")
    assert iface.sent[2]["text"] == iface.sent[1]["text"]
    assert records[2]["retry_of"] == iface.sent[1]["packet"].id


def test_zork_bot_default_retry_policy_sends_one_repeat_per_segment() -> None:
    iface = _FakeInterface()
    service = ZorkBotService(
        game=_FakeGame("alpha " * 45),
        reply_segment_delay_seconds=0,
        reply_ack_wait_seconds=0,
        reply_async=False,
        get_delivery_state_fn=lambda _message_id: "pending",
    )

    handled = service.handle_packet(_direct_text_packet("zork"), iface)

    assert handled is True
    assert len(iface.sent) == 2
    assert iface.sent[0]["text"] == iface.sent[1]["text"]
    assert str(iface.sent[0]["text"]).startswith("[1/2]")
