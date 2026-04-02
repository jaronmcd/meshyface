from collections import deque

from meshdash.tracker_local_chat import append_local_chat_entry


class _FakeHistoryStore:
    def __init__(self):
        self.saved = []

    def save_chat(self, entry):
        self.saved.append(entry)


def test_append_local_chat_entry_appends_and_writes_history_when_available():
    recent = deque(maxlen=4)
    history = _FakeHistoryStore()
    entry = {"text": "hello"}

    ok = append_local_chat_entry(
        recent_chat=recent,
        history_store=history,
        entry=entry,
    )

    assert ok is True
    assert list(recent) == [entry]
    assert history.saved == [entry]


def test_append_local_chat_entry_returns_false_for_none_entry():
    recent = deque(maxlen=4)
    history = _FakeHistoryStore()

    ok = append_local_chat_entry(
        recent_chat=recent,
        history_store=history,
        entry=None,
    )

    assert ok is False
    assert list(recent) == []
    assert history.saved == []


def test_append_local_chat_entry_skips_file_transfer_protocol_entries():
    recent = deque(maxlen=4)
    history = _FakeHistoryStore()
    entry = {"text": "MF_FILE_V1|C|mtest123|0|QUJD"}

    ok = append_local_chat_entry(
        recent_chat=recent,
        history_store=history,
        entry=entry,
    )

    assert ok is False
    assert list(recent) == []
    assert history.saved == []
