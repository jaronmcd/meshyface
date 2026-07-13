import json

import pytest

from meshdash.plugin_protocol import (
    PROTOCOL_VERSION,
    PluginProtocolError,
    decode_message,
    encode_message,
)
from meshdash.plugin_state import PluginStateConflict, PluginStateStore


def test_plugin_protocol_round_trip_and_strict_validation() -> None:
    payload = encode_message({"type": "event", "text": "hello 👋"})
    assert decode_message(payload) == {
        "protocol_version": PROTOCOL_VERSION,
        "type": "event",
        "text": "hello 👋",
    }

    with pytest.raises(PluginProtocolError):
        encode_message({"type": "event", "value": float("nan")})
    with pytest.raises(PluginProtocolError):
        decode_message(json.dumps({"type": "event"}).encode())
    with pytest.raises(PluginProtocolError):
        decode_message(b"[]")


def test_plugin_state_is_durable_peer_scoped_and_revision_guarded(tmp_path) -> None:
    path = tmp_path / "plugin-state.sqlite3"
    store = PluginStateStore(str(path), now_fn=lambda: 100)
    initial = store.snapshot("example", "!00000001")
    assert initial.state == {}
    assert initial.peer_state == {}

    committed = store.commit(
        "example",
        "!00000001",
        state={"total": 1},
        peer_state={"room": "west"},
        expected_state_revision=0,
        expected_peer_state_revision=0,
    )
    assert committed.state_revision == 1
    assert committed.peer_state_revision == 1
    with pytest.raises(PluginStateConflict):
        store.commit(
            "example",
            "!00000001",
            state={},
            peer_state={},
            expected_state_revision=0,
            expected_peer_state_revision=0,
        )
    store.close()

    reopened = PluginStateStore(str(path))
    assert reopened.snapshot("example", "!00000001").peer_state == {"room": "west"}
    assert reopened.snapshot("example", "!00000002").peer_state == {}
    assert reopened.snapshot("example", "!00000002").state == {"total": 1}
    reopened.close()


def test_plugin_sessions_and_enablement_are_host_owned(tmp_path) -> None:
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    assert store.active_session("!aaaaaaaa", "!bbbbbbbb") is None
    store.start_session("!aaaaaaaa", "!bbbbbbbb", "zork")
    assert store.active_session("!aaaaaaaa", "!bbbbbbbb") == "zork"
    assert store.end_session("!aaaaaaaa", "!bbbbbbbb") is True
    assert store.end_session("!aaaaaaaa", "!bbbbbbbb") is False

    assert store.plugin_enabled("example", default=False) is False
    store.set_plugin_enabled("example", True)
    assert store.plugin_enabled("example", default=False) is True
    store.close()
