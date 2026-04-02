from collections import deque

from meshdash.tracker_storage import apply_tracker_storage_updates


class _FakeHistoryStore:
    def __init__(self):
        self.connection_calls = []
        self.packet_calls = []
        self.chat_calls = []

    def save_connection_event(self, **kwargs):
        self.connection_calls.append(kwargs)

    def save_packet(self, entry):
        self.packet_calls.append(entry)

    def save_chat(self, entry):
        self.chat_calls.append(entry)


def test_apply_tracker_storage_updates_updates_deques_and_history_when_live():
    packets = deque(maxlen=4)
    chat = deque(maxlen=4)
    history = _FakeHistoryStore()

    packet_entry = {"summary": {"packet_id": 1}, "packet": {"id": 1}}
    chat_entry = {"message_id": 1, "text": "hello"}
    apply_tracker_storage_updates(
        recent_packets=packets,
        recent_chat=chat,
        history_store=history,
        include_live_count=True,
        direct_key=("!a", "!b"),
        rx_time=123,
        portnum="TEXT_MESSAGE_APP",
        hops=2,
        packet_entry=packet_entry,
        chat_entry=chat_entry,
    )

    assert list(packets) == [packet_entry]
    assert list(chat) == [chat_entry]
    assert history.connection_calls == [
        {
            "from_id": "!a",
            "to_id": "!b",
            "rx_time": 123,
            "portnum": "TEXT_MESSAGE_APP",
            "hops": 2,
        }
    ]
    assert history.packet_calls == [packet_entry]
    assert history.chat_calls == [chat_entry]


def test_apply_tracker_storage_updates_skips_history_writes_for_seeded_packets():
    packets = deque(maxlen=4)
    chat = deque(maxlen=4)
    history = _FakeHistoryStore()

    packet_entry = {"summary": {"packet_id": 2}, "packet": {"id": 2}}
    apply_tracker_storage_updates(
        recent_packets=packets,
        recent_chat=chat,
        history_store=history,
        include_live_count=False,
        direct_key=("!a", "!b"),
        rx_time=200,
        portnum="NODEINFO_APP",
        hops=1,
        packet_entry=packet_entry,
        chat_entry=None,
    )

    assert list(packets) == [packet_entry]
    assert list(chat) == []
    assert history.connection_calls == []
    assert history.packet_calls == []
    assert history.chat_calls == []


def test_apply_tracker_storage_updates_skips_file_transfer_protocol_chat_entries():
    packets = deque(maxlen=4)
    chat = deque(maxlen=4)
    history = _FakeHistoryStore()

    packet_entry = {"summary": {"packet_id": 3}, "packet": {"id": 3}}
    chat_entry = {"message_id": 3, "text": "MF_FILE_V1|A|mtest123|0|4|AA=="}
    apply_tracker_storage_updates(
        recent_packets=packets,
        recent_chat=chat,
        history_store=history,
        include_live_count=True,
        direct_key=("!a", "!b"),
        rx_time=300,
        portnum="TEXT_MESSAGE_APP",
        hops=1,
        packet_entry=packet_entry,
        chat_entry=chat_entry,
    )

    assert list(packets) == [packet_entry]
    assert list(chat) == []
    assert history.packet_calls == [packet_entry]
    assert history.chat_calls == []
