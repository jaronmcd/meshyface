from types import SimpleNamespace

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
    assert tracker.enable_zork_bot() is True

    tracker.on_receive(_direct_text_packet("zork"), iface)

    assert iface.sent
    combined_text = " ".join(str(row["text"]) for row in iface.sent)
    assert "zork: session started" in combined_text
    assert iface.sent[0]["kwargs"]["destinationId"] == "!01020304"
    assert iface.sent[0]["kwargs"]["channelIndex"] == 2
    assert iface.sent[0]["kwargs"]["replyId"] == 111


def test_dashboard_tracker_ignores_broadcast_zork_when_enabled() -> None:
    tracker = DashboardTracker(packet_limit=25)
    iface = _FakeInterface()
    assert tracker.enable_zork_bot() is True

    tracker.on_receive(_direct_text_packet("zork", to=0xFFFFFFFF), iface)

    assert iface.sent == []
