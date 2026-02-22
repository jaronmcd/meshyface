from meshdash.services import (
    build_node_history_loader,
    build_online_activity_loader,
    empty_node_history,
    empty_online_activity,
    send_chat_message,
)


class _FakeHistoryStore:
    def __init__(self):
        self.node_calls = []
        self.online_calls = []

    def load_node_history(self, *, node_id, window_hours, max_points):
        self.node_calls.append((node_id, window_hours, max_points))
        return {"node_id": node_id, "window_hours": window_hours, "max_points": max_points}

    def load_online_activity(self, *, window_hours):
        self.online_calls.append(window_hours)
        return {"window_hours": window_hours, "points": []}


def test_empty_payload_shapes():
    node_empty = empty_node_history("!abc123")
    assert node_empty["node_id"] == "!abc123"
    assert node_empty["points"] == []
    assert node_empty["positions"] == []

    online_empty = empty_online_activity(12)
    assert online_empty["window_hours"] == 12
    assert len(online_empty["hourly_profile"]) == 24
    assert online_empty["summary"]["sample_hours"] == 0


def test_build_node_history_loader_defaults_and_overrides():
    store = _FakeHistoryStore()
    loader = build_node_history_loader(store, default_hours=72, default_points=1440)

    payload = loader(" !node1 ", None, None)
    assert payload["node_id"] == "!node1"
    assert payload["window_hours"] == 72
    assert payload["max_points"] == 1440

    payload = loader("!node2", 6, 120)
    assert payload["node_id"] == "!node2"
    assert payload["window_hours"] == 6
    assert payload["max_points"] == 120


def test_build_node_history_loader_without_store():
    loader = build_node_history_loader(None, default_hours=72, default_points=1440)
    payload = loader(" !xyz ", 5, 20)
    assert payload["node_id"] == "!xyz"
    assert payload["points"] == []
    assert payload["positions"] == []


def test_build_online_activity_loader_defaults_and_overrides():
    store = _FakeHistoryStore()
    loader = build_online_activity_loader(store, default_hours=72)

    payload = loader(None)
    assert payload["window_hours"] == 72

    payload = loader(24)
    assert payload["window_hours"] == 24
    assert store.online_calls == [72, 24]


def test_build_online_activity_loader_without_store():
    loader = build_online_activity_loader(None, default_hours=72)
    payload = loader(None)
    assert payload["window_hours"] == 72
    assert len(payload["hourly_profile"]) == 24


class _FakePacket:
    def __init__(self, packet_id):
        self.id = packet_id


class _FakeIface:
    def __init__(self):
        self.sent = []

    def sendText(self, text, destinationId, wantAck, channelIndex, replyId):
        self.sent.append(
            {
                "text": text,
                "destinationId": destinationId,
                "wantAck": wantAck,
                "channelIndex": channelIndex,
                "replyId": replyId,
            }
        )
        return _FakePacket(123)


class _NoopLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


def test_send_chat_message_text_path():
    iface = _FakeIface()
    reactions = []
    records = []

    response = send_chat_message(
        text="hello",
        destination="!abcd1234",
        channel_index=2,
        reply_id=None,
        retry_of=111,
        emoji=None,
        iface=iface,
        send_lock=_NoopLock(),
        send_reaction_packet_fn=lambda **kwargs: reactions.append(kwargs),
        local_node_id_fn=lambda: "!me000001",
        record_local_chat_fn=lambda **kwargs: records.append(kwargs),
        chat_max_bytes=220,
        normalize_single_emoji_fn=lambda value: (None, None),
        to_int_fn=lambda value: int(value) if value is not None else None,
        now_text_fn=lambda: "2026-02-22T12:00:00Z",
    )

    assert response["ok"] is True
    assert response["text"] == "hello"
    assert response["message_id"] == 123
    assert response["ack_requested"] is True
    assert response["delivery_state"] == "pending"
    assert response["retry_of"] == 111
    assert iface.sent[0]["destinationId"] == "!abcd1234"
    assert iface.sent[0]["wantAck"] is True
    assert records[0]["text"] == "hello"
    assert records[0]["is_reaction"] is False
    assert reactions == []


def test_send_chat_message_reaction_path():
    iface = _FakeIface()
    reaction_calls = []
    records = []

    def _send_reaction(**kwargs):
        reaction_calls.append(kwargs)
        return _FakePacket(777)

    response = send_chat_message(
        text="",
        destination="!abcd1234",
        channel_index=1,
        reply_id=555,
        retry_of=None,
        emoji="😀",
        iface=iface,
        send_lock=_NoopLock(),
        send_reaction_packet_fn=_send_reaction,
        local_node_id_fn=lambda: "!me000001",
        record_local_chat_fn=lambda **kwargs: records.append(kwargs),
        chat_max_bytes=220,
        normalize_single_emoji_fn=lambda value: ("😀", ord("😀")),
        to_int_fn=lambda value: int(value) if value is not None else None,
        now_text_fn=lambda: "2026-02-22T12:00:00Z",
    )

    assert response["ok"] is True
    assert response["text"] == ""
    assert response["reaction"] == "😀"
    assert response["reaction_codepoint"] == ord("😀")
    assert response["ack_requested"] is False
    assert iface.sent == []
    assert reaction_calls[0]["reply_id"] == 555
    assert records[0]["is_reaction"] is True


def test_send_chat_message_validates_reaction_requires_reply_id():
    iface = _FakeIface()
    try:
        send_chat_message(
            text="",
            destination="!abcd1234",
            channel_index=1,
            reply_id=None,
            retry_of=None,
            emoji="😀",
            iface=iface,
            send_lock=_NoopLock(),
            send_reaction_packet_fn=lambda **kwargs: _FakePacket(1),
            local_node_id_fn=lambda: "!me000001",
            record_local_chat_fn=lambda **kwargs: None,
            chat_max_bytes=220,
            normalize_single_emoji_fn=lambda value: ("😀", ord("😀")),
            to_int_fn=lambda value: int(value) if value is not None else None,
            now_text_fn=lambda: "2026-02-22T12:00:00Z",
        )
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "valid reply_id" in str(exc)
