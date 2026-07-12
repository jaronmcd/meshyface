import time
from types import SimpleNamespace

from meshdash.services_ping_bot import build_ping_bot_service
from meshdash.tracker_runtime_impl import DashboardTracker


class _FakeInterface:
    def __init__(self) -> None:
        self.myInfo = {"my_node_num": 0x12345678}
        self.nodesByNum = {
            0x12345678: {"user": {"id": "!12345678", "shortName": "mesh"}},
            0x01020304: {"user": {"id": "!01020304"}, "hopsAway": 3},
        }
        self.sent: list[dict[str, object]] = []

    def sendText(self, text: str, **kwargs: object) -> object:
        packet = SimpleNamespace(id=1700 + len(self.sent))
        self.sent.append({"text": text, "kwargs": dict(kwargs), "packet": packet})
        return packet


class _FlakyInterface(_FakeInterface):
    def __init__(self, *, fail_call_indexes: set[int]) -> None:
        super().__init__()
        self._fail_call_indexes = set(int(value) for value in fail_call_indexes)
        self.call_count = 0

    def sendText(self, text: str, **kwargs: object) -> object:
        self.call_count += 1
        if self.call_count in self._fail_call_indexes:
            raise RuntimeError("radio busy")
        return super().sendText(text, **kwargs)


def _text_packet(
    text: str,
    *,
    to: int = 0x12345678,
    packet_id: int = 901,
    hop_start: int | None = None,
    hop_limit: int | None = None,
    rx_snr: float | None = None,
    rx_rssi: float | None = None,
) -> dict[str, object]:
    packet: dict[str, object] = {
        "from": 0x01020304,
        "to": to,
        "id": packet_id,
        "channel": 1,
        "decoded": {
            "portnum": "TEXT_MESSAGE_APP",
            "text": text,
        },
    }
    if hop_start is not None:
        packet["hopStart"] = hop_start
    if hop_limit is not None:
        packet["hopLimit"] = hop_limit
    if rx_snr is not None:
        packet["rxSnr"] = rx_snr
    if rx_rssi is not None:
        packet["rxRssi"] = rx_rssi
    return packet


def test_dashboard_tracker_does_not_answer_ping_when_bot_runtime_disabled() -> None:
    tracker = DashboardTracker(packet_limit=25)
    iface = _FakeInterface()

    tracker.on_receive(_text_packet("ping"), iface)

    assert iface.sent == []


def test_dashboard_tracker_answers_direct_ping_when_enabled() -> None:
    tracker = DashboardTracker(packet_limit=25)
    iface = _FakeInterface()
    runtime = tracker.set_ping_bot_enabled(True, send_lock=None)
    assert runtime["ok"] is True
    assert runtime["ping"]["enabled"] is True

    tracker.on_receive(_text_packet("ping", hop_start=7, hop_limit=4), iface)

    assert iface.sent
    assert iface.sent[0]["kwargs"]["destinationId"] == "!01020304"
    assert iface.sent[0]["kwargs"]["replyId"] == 901
    assert iface.sent[0]["kwargs"]["channelIndex"] == 1
    assert str(iface.sent[0]["text"]).strip() == "3 hops."


def test_ping_bot_uses_numeric_sender_as_security_identity() -> None:
    iface = _FakeInterface()
    service = build_ping_bot_service(repeat_send_retry_limit=0)
    packet = _text_packet("ping")
    packet["fromId"] = "!deadbeef"

    assert service.handle_packet(packet, iface) is True
    assert iface.sent[0]["kwargs"]["destinationId"] == "!01020304"


def test_dashboard_tracker_repeats_direct_ping_reply_when_count_is_requested() -> None:
    tracker = DashboardTracker(packet_limit=25)
    iface = _FakeInterface()
    runtime = tracker.set_ping_bot_enabled(True, send_lock=None)
    assert runtime["ok"] is True
    assert runtime["ping"]["enabled"] is True

    set_delivery_state_fn = getattr(tracker, "_set_delivery_state_fn", None)
    assert callable(set_delivery_state_fn)

    tracker.on_receive(_text_packet("ping 5", hop_start=7, hop_limit=4), iface)

    for index in range(1, 6):
        deadline = time.monotonic() + 1.0
        while len(iface.sent) < index and time.monotonic() < deadline:
            time.sleep(0.01)
        assert len(iface.sent) >= index
        sent_packet = iface.sent[index - 1].get("packet")
        sent_message_id = getattr(sent_packet, "id", None)
        applied = False
        apply_deadline = time.monotonic() + 1.0
        while not applied and time.monotonic() < apply_deadline:
            applied = bool(
                set_delivery_state_fn(
                    sent_message_id,
                    "ack",
                    ack_from_id="!01020304",
                    ack_to_id="!12345678",
                )
            )
            if not applied:
                time.sleep(0.01)
        assert applied is True

    assert len(iface.sent) == 5
    assert [str(item["text"]).strip() for item in iface.sent] == ["1/5", "2/5", "3/5", "4/5", "5/5"]
    for item in iface.sent:
        assert item["kwargs"]["destinationId"] == "!01020304"
        assert item["kwargs"]["replyId"] == 901
        assert item["kwargs"]["channelIndex"] == 1


def test_dashboard_tracker_caps_direct_ping_repeat_count() -> None:
    tracker = DashboardTracker(packet_limit=25)
    iface = _FakeInterface()
    runtime = tracker.set_ping_bot_enabled(True, send_lock=None)
    assert runtime["ok"] is True

    set_delivery_state_fn = getattr(tracker, "_set_delivery_state_fn", None)
    assert callable(set_delivery_state_fn)

    tracker.on_receive(_text_packet("ping 100"), iface)

    for index in range(1, 9):
        deadline = time.monotonic() + 1.0
        while len(iface.sent) < index and time.monotonic() < deadline:
            time.sleep(0.01)
        assert len(iface.sent) >= index
        sent_packet = iface.sent[index - 1].get("packet")
        sent_message_id = getattr(sent_packet, "id", None)
        applied = False
        apply_deadline = time.monotonic() + 1.0
        while not applied and time.monotonic() < apply_deadline:
            applied = bool(
                set_delivery_state_fn(
                    sent_message_id,
                    "ack",
                    ack_from_id="!01020304",
                    ack_to_id="!12345678",
                )
            )
            if not applied:
                time.sleep(0.01)
        assert applied is True

    assert len(iface.sent) == 8
    assert str(iface.sent[0]["text"]).strip() == "1/8"
    assert str(iface.sent[-1]["text"]).strip() == "8/8"


def test_dashboard_tracker_answers_public_ping_with_direct_reply() -> None:
    tracker = DashboardTracker(packet_limit=25)
    iface = _FakeInterface()
    runtime = tracker.set_ping_bot_enabled(True, send_lock=None)
    assert runtime["ok"] is True
    assert runtime["ping"]["enabled"] is True

    tracker.on_receive(_text_packet("test", to=0xFFFFFFFF), iface)

    assert iface.sent
    assert iface.sent[0]["kwargs"]["destinationId"] == "!01020304"
    assert str(iface.sent[0]["text"]).strip() == "3 hops."


def test_dashboard_tracker_reports_zero_hops_when_packet_hops_are_zero() -> None:
    tracker = DashboardTracker(packet_limit=25)
    iface = _FakeInterface()
    runtime = tracker.set_ping_bot_enabled(True, send_lock=None)
    assert runtime["ok"] is True
    assert runtime["ping"]["enabled"] is True

    tracker.on_receive(_text_packet("ping", hop_start=0, hop_limit=0), iface)

    assert iface.sent
    assert str(iface.sent[0]["text"]).strip() == "0 hops."


def test_dashboard_tracker_includes_signal_levels_in_ping_reply() -> None:
    tracker = DashboardTracker(packet_limit=25)
    iface = _FakeInterface()
    runtime = tracker.set_ping_bot_enabled(True, send_lock=None)
    assert runtime["ok"] is True
    assert runtime["ping"]["enabled"] is True

    tracker.on_receive(_text_packet("ping", hop_start=1, hop_limit=1, rx_snr=11.0, rx_rssi=-46), iface)

    assert iface.sent
    assert str(iface.sent[0]["text"]).strip() == "0 hops. SNR 11.00dB RSSI -46dBm"


def test_dashboard_tracker_ping_message_only_blocks_public_ping() -> None:
    tracker = DashboardTracker(packet_limit=25)
    iface = _FakeInterface()
    enabled = tracker.set_ping_bot_enabled(True, send_lock=None)
    assert enabled["ok"] is True
    mode = tracker.set_ping_bot_message_only(True)
    assert mode["ok"] is True
    assert mode["ping"]["message_only"] is True
    assert mode["ping"]["public_start_enabled"] is False

    tracker.on_receive(_text_packet("ping", to=0xFFFFFFFF), iface)

    assert iface.sent == []


def test_dashboard_tracker_ping_message_only_keeps_direct_ping_active() -> None:
    tracker = DashboardTracker(packet_limit=25)
    iface = _FakeInterface()
    enabled = tracker.set_ping_bot_enabled(True, send_lock=None)
    assert enabled["ok"] is True
    mode = tracker.set_ping_bot_message_only(True)
    assert mode["ok"] is True

    tracker.on_receive(_text_packet("ping", hop_start=7, hop_limit=4), iface)

    assert iface.sent
    assert str(iface.sent[0]["text"]).strip() == "3 hops."


def test_dashboard_tracker_accepts_nodename_prefixed_natural_ping_trigger() -> None:
    tracker = DashboardTracker(packet_limit=25)
    iface = _FakeInterface()
    runtime = tracker.set_ping_bot_enabled(True, send_lock=None)
    assert runtime["ok"] is True
    assert runtime["ping"]["enabled"] is True

    tracker.on_receive(_text_packet("mesh can you see this?"), iface)

    assert iface.sent
    assert iface.sent[0]["kwargs"]["destinationId"] == "!01020304"
    assert str(iface.sent[0]["text"]).strip() == "3 hops."


def test_dashboard_tracker_ignores_ping_targeted_to_different_suffix() -> None:
    tracker = DashboardTracker(packet_limit=25)
    iface = _FakeInterface()
    runtime = tracker.set_ping_bot_enabled(True, send_lock=None)
    assert runtime["ok"] is True
    assert runtime["ping"]["enabled"] is True

    tracker.on_receive(_text_packet("ping dead"), iface)

    assert iface.sent == []


def test_dashboard_tracker_keeps_ping_off_when_only_zork_enabled() -> None:
    tracker = DashboardTracker(packet_limit=25)
    runtime = tracker.set_zork_bot_enabled(True, send_lock=None)

    assert runtime["ok"] is True
    assert runtime["zork"]["enabled"] is True
    assert runtime["ping"]["enabled"] is False


def test_ping_bot_paces_small_repeat_bursts() -> None:
    iface = _FakeInterface()
    sleeps: list[float] = []
    service = build_ping_bot_service(
        repeat_delay_seconds=0.5,
        repeat_max_paced_count=8,
        repeat_send_retry_limit=0,
        repeat_send_retry_delay_seconds=0,
        sleep_fn=sleeps.append,
    )

    handled = service.handle_packet(_text_packet("ping 5"), iface)

    assert handled is True
    assert [str(item["text"]).strip() for item in iface.sent] == ["1/5", "2/5", "3/5", "4/5", "5/5"]
    assert sleeps == [0.5, 0.5, 0.5, 0.5]


def test_ping_bot_retries_repeat_send_when_radio_send_fails_once() -> None:
    iface = _FlakyInterface(fail_call_indexes={2})
    service = build_ping_bot_service(
        repeat_delay_seconds=0,
        repeat_max_paced_count=8,
        repeat_send_retry_limit=1,
        repeat_send_retry_delay_seconds=0,
        sleep_fn=lambda _seconds: None,
    )

    handled = service.handle_packet(_text_packet("ping 3"), iface)

    assert handled is True
    assert iface.call_count == 4
    assert [str(item["text"]).strip() for item in iface.sent] == ["1/3", "2/3", "3/3"]


def test_ping_bot_drops_excess_async_repeat_work() -> None:
    class _FullSlots:
        @staticmethod
        def acquire(*, blocking: bool) -> bool:
            assert blocking is False
            return False

    iface = _FakeInterface()
    service = build_ping_bot_service(
        repeat_async=True,
        get_delivery_state_fn=lambda _message_id: "pending",
    )
    service._async_reply_slots = _FullSlots()

    assert service.handle_packet(_text_packet("ping 3"), iface) is True
    assert iface.sent == []


def test_ping_bot_rate_limits_requests_and_close_stops_processing() -> None:
    iface = _FakeInterface()
    monotonic = [100.0]
    service = build_ping_bot_service(
        repeat_send_retry_limit=0,
        peer_request_cooldown_seconds=5,
        global_request_cooldown_seconds=1,
        monotonic_fn=lambda: monotonic[0],
    )

    assert service.handle_packet(_text_packet("ping"), iface) is True
    assert service.handle_packet(_text_packet("ping"), iface) is True
    assert len(iface.sent) == 1
    monotonic[0] = 106.0
    assert service.handle_packet(_text_packet("ping"), iface) is True
    assert len(iface.sent) == 2
    service.close()
    assert service.handle_packet(_text_packet("ping"), iface) is False
    assert len(iface.sent) == 2
