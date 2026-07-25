import json
import sqlite3

import pytest

from meshdash.plugin_protocol import (
    PROTOCOL_VERSION,
    PluginProtocolError,
    decode_message,
    encode_message,
)
from meshdash.plugin_state import (
    PluginStateConflict,
    PluginStateQuotaExceeded,
    PluginStateStore,
)


_DIGEST_A = f"sha256:{'a' * 64}"
_DIGEST_B = f"sha256:{'b' * 64}"


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
    channel_one_before = store.snapshot("example", "!00000001", 1)
    assert channel_one_before.state == {"total": 1}
    assert channel_one_before.peer_state == {}
    channel_one = store.commit(
        "example",
        "!00000001",
        channel_index=1,
        state={"total": 1},
        peer_state={"room": "east"},
        expected_state_revision=1,
        expected_peer_state_revision=channel_one_before.peer_state_revision,
    )
    assert channel_one.state_revision == 1
    assert (
        channel_one.peer_state_revision
        == channel_one_before.peer_state_revision + 1
    )
    assert store.snapshot("example", "!00000001", 0).peer_state == {"room": "west"}
    assert store.snapshot("example", "!00000001", 1).peer_state == {"room": "east"}
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
    assert store.runtime_enabled(default=True) is True
    assert store.set_runtime_enabled(False) is False
    assert store.runtime_enabled(default=True) is False
    assert store.set_runtime_enabled(True) is True
    assert store.runtime_enabled(default=False) is True

    assert store.active_session("!aaaaaaaa", "!bbbbbbbb") is None
    store.start_session("!aaaaaaaa", "!bbbbbbbb", "zork", 3)
    assert store.active_session("!aaaaaaaa", "!bbbbbbbb", 0) is None
    assert store.active_session("!aaaaaaaa", "!bbbbbbbb", 3) == "zork"
    assert store.end_session("!aaaaaaaa", "!bbbbbbbb", 0) is False
    assert store.end_session("!aaaaaaaa", "!bbbbbbbb", 3) is True
    assert store.end_session("!aaaaaaaa", "!bbbbbbbb", 3) is False

    assert (
        store.plugin_enabled(
            "example",
            package_digest=_DIGEST_A,
            default=False,
        )
        is False
    )
    store.set_plugin_enabled("example", True, package_digest=_DIGEST_A)
    assert (
        store.plugin_enabled(
            "example",
            package_digest=_DIGEST_A,
            default=False,
        )
        is True
    )
    assert (
        store.plugin_enabled(
            "example",
            package_digest=_DIGEST_B,
            default=True,
        )
        is False
    )
    assert (
        store.set_plugin_enabled_if_identity_matches(
            "example",
            False,
            package_digest=_DIGEST_A,
        )
        is True
    )
    assert (
        store.set_plugin_enabled_if_identity_matches(
            "example",
            True,
            package_digest=_DIGEST_B,
        )
        is False
    )
    assert (
        store.plugin_enabled(
            "example",
            package_digest=_DIGEST_A,
            default=True,
        )
        is False
    )
    assert store.plugin_route_policy("example") == {
        "mesh_enabled": True,
        "console_enabled": True,
    }
    assert store.set_plugin_route_policy(
        "example",
        mesh_enabled=False,
        console_enabled=True,
    ) == {
        "mesh_enabled": False,
        "console_enabled": True,
    }
    assert store.plugin_route_policy("example") == {
        "mesh_enabled": False,
        "console_enabled": True,
    }
    store.close()

    reopened = PluginStateStore(str(tmp_path / "state.sqlite3"))
    assert reopened.runtime_enabled(default=False) is True
    reopened.close()


def test_known_plugin_identity_reconciliation_preserves_choice_and_clears_sessions(
    tmp_path,
) -> None:
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    store.set_plugin_enabled("example", False, package_digest=_DIGEST_A)
    store.set_plugin_settings(
        "example",
        {"greeting": "kept"},
        package_digest=_DIGEST_A,
    )
    store.start_session("!aaaaaaaa", "!bbbbbbbb", "example", 4)

    assert store.reconcile_plugin_identity(
        "example",
        package_digest=_DIGEST_B,
        compatible_settings={"greeting": "kept"},
        rebind_settings=True,
    )
    assert (
        store.plugin_enabled(
            "example",
            package_digest=_DIGEST_B,
            default=True,
        )
        is False
    )
    assert store.plugin_settings("example", package_digest=_DIGEST_B) == {
        "greeting": "kept"
    }
    assert store.active_session("!aaaaaaaa", "!bbbbbbbb", 4) is None

    assert (
        store.reconcile_plugin_identity(
            "new-plugin",
            package_digest=_DIGEST_A,
        )
        is False
    )
    assert (
        store.plugin_enabled(
            "new-plugin",
            package_digest=_DIGEST_A,
            default=False,
        )
        is False
    )
    store.close()


def test_state_commit_suppresses_noop_and_empty_peer_rows(tmp_path) -> None:
    clock = [100]
    store = PluginStateStore(
        str(tmp_path / "state.sqlite3"),
        now_fn=lambda: clock[0],
    )
    initial = store.commit(
        "example",
        "!00000001",
        state={},
        peer_state={},
        expected_state_revision=0,
        expected_peer_state_revision=0,
    )
    assert initial.state_revision == 0
    assert initial.peer_state_revision == 0
    assert store._connection.execute("SELECT COUNT(*) FROM plugin_state").fetchone() == (0,)

    changed = store.commit(
        "example",
        "!00000001",
        state={"total": 1},
        peer_state={"room": "west"},
        expected_state_revision=0,
        expected_peer_state_revision=0,
    )
    assert changed.state_revision == 1
    assert changed.peer_state_revision == 1
    clock[0] = 200
    unchanged = store.commit(
        "example",
        "!00000001",
        state={"total": 1},
        peer_state={"room": "west"},
        expected_state_revision=1,
        expected_peer_state_revision=1,
    )
    assert unchanged.state_revision == 1
    assert unchanged.peer_state_revision == 1
    updated_values = store._connection.execute(
        """
        SELECT updated_unix
        FROM plugin_state
        WHERE plugin_id=?
        ORDER BY peer_id
        """,
        ("example",),
    ).fetchall()
    assert updated_values == [(100,), (100,)]

    cleared = store.commit(
        "example",
        "!00000001",
        state={"total": 1},
        peer_state={},
        expected_state_revision=1,
        expected_peer_state_revision=1,
    )
    assert cleared.peer_state_revision == 2
    assert store.snapshot("example", "!00000001").peer_state == {}
    assert store._connection.execute(
        "SELECT COUNT(*) FROM plugin_state WHERE peer_id <> ''"
    ).fetchone() == (0,)
    store.close()


def test_peer_state_and_session_quotas_are_per_plugin(tmp_path) -> None:
    store = PluginStateStore(
        str(tmp_path / "state.sqlite3"),
        max_peer_state_rows_per_plugin=2,
        max_peer_state_bytes_per_plugin=30,
        max_sessions_per_plugin=2,
    )
    for peer, value in (("!00000001", "a"), ("!00000002", "b")):
        snapshot = store.snapshot("limited", peer)
        store.commit(
            "limited",
            peer,
            state={},
            peer_state={"v": value},
            expected_state_revision=snapshot.state_revision,
            expected_peer_state_revision=snapshot.peer_state_revision,
        )
    third_snapshot = store.snapshot("limited", "!00000003")
    with pytest.raises(PluginStateQuotaExceeded, match="row quota"):
        store.commit(
            "limited",
            "!00000003",
            state={},
            peer_state={"v": "c"},
            expected_state_revision=third_snapshot.state_revision,
            expected_peer_state_revision=third_snapshot.peer_state_revision,
        )
    # A different plugin receives its own quota budget.
    store.commit(
        "other",
        "!00000003",
        state={},
        peer_state={"v": "c"},
        expected_state_revision=0,
        expected_peer_state_revision=0,
    )
    with pytest.raises(PluginStateQuotaExceeded, match="byte quota"):
        store.commit(
            "limited",
            "!00000001",
            state={},
            peer_state={"v": "x" * 25},
            expected_state_revision=0,
            expected_peer_state_revision=1,
        )

    store.start_session("!aaaaaaaa", "!00000001", "limited", 0)
    store.start_session("!aaaaaaaa", "!00000002", "limited", 1)
    with pytest.raises(PluginStateQuotaExceeded, match="sessions"):
        store.start_session("!aaaaaaaa", "!00000003", "limited", 2)
    store.start_session("!aaaaaaaa", "!00000003", "other", 2)
    assert len(store.list_sessions()) == 3
    store.close()


def test_legacy_state_and_sessions_migrate_to_default_channel_zero(tmp_path) -> None:
    path = tmp_path / "legacy-scopes.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE plugin_state (
            plugin_id TEXT NOT NULL,
            peer_id TEXT NOT NULL,
            state_json TEXT NOT NULL,
            revision INTEGER NOT NULL DEFAULT 0,
            updated_unix INTEGER NOT NULL,
            PRIMARY KEY (plugin_id, peer_id)
        );
        CREATE TABLE plugin_sessions (
            local_node_id TEXT NOT NULL,
            peer_id TEXT NOT NULL,
            plugin_id TEXT NOT NULL,
            updated_unix INTEGER NOT NULL,
            PRIMARY KEY (local_node_id, peer_id)
        );
        """
    )
    connection.execute(
        "INSERT INTO plugin_state VALUES (?, ?, ?, ?, ?)",
        ("example", "", '{"total":2}', 4, 100),
    )
    connection.execute(
        "INSERT INTO plugin_state VALUES (?, ?, ?, ?, ?)",
        ("example", "!00000001", '{"room":"legacy"}', 3, 100),
    )
    connection.execute(
        "INSERT INTO plugin_sessions VALUES (?, ?, ?, ?)",
        ("!00000002", "!00000001", "example", 100),
    )
    connection.commit()
    connection.close()

    store = PluginStateStore(str(path))
    default_channel = store.snapshot("example", "!00000001")
    assert default_channel.state == {"total": 2}
    assert default_channel.state_revision == 4
    assert default_channel.peer_state == {"room": "legacy"}
    assert default_channel.peer_state_revision == 3
    assert store.snapshot("example", "!00000001", 1).state == {"total": 2}
    assert store.snapshot("example", "!00000001", 1).peer_state == {}
    assert store.active_session("!00000002", "!00000001", 0) == "example"
    assert store.active_session("!00000002", "!00000001", 1) is None
    assert store.list_sessions() == (
        ("!00000002", "!00000001", 0, "example"),
    )
    state_columns = {
        row[1]
        for row in store._connection.execute("PRAGMA table_info(plugin_state)")
    }
    session_columns = {
        row[1]
        for row in store._connection.execute("PRAGMA table_info(plugin_sessions)")
    }
    assert "channel_index" in state_columns
    assert "channel_index" in session_columns
    store.close()


def test_legacy_id_only_enablement_remains_unbound_until_reconciled(
    tmp_path,
) -> None:
    path = tmp_path / "legacy-state.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE plugin_enablement (
            plugin_id TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL,
            updated_unix INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        "INSERT INTO plugin_enablement(plugin_id, enabled, updated_unix) VALUES (?, ?, ?)",
        ("example", 1, 100),
    )
    connection.commit()
    connection.close()

    store = PluginStateStore(str(path))
    assert (
        store.plugin_enabled(
            "example",
            package_digest=_DIGEST_A,
            default=True,
        )
        is False
    )
    assert (
        store.set_plugin_enabled_if_identity_matches(
            "example",
            True,
            package_digest=_DIGEST_A,
        )
        is False
    )
    assert store.reconcile_plugin_identity(
        "example",
        package_digest=_DIGEST_A,
    )
    assert (
        store.plugin_enabled(
            "example",
            package_digest=_DIGEST_A,
            default=False,
        )
        is True
    )
    store.close()


def test_plugin_settings_are_host_owned_and_durable(tmp_path) -> None:
    path = tmp_path / "state.sqlite3"
    store = PluginStateStore(str(path), now_fn=lambda: 123)
    assert store.plugin_settings("example", package_digest=_DIGEST_A) == {}
    assert store.set_plugin_settings(
        "example",
        {"label": "hello", "enabled": True, "node_ids": ["!01020304"]},
        package_digest=_DIGEST_A,
    ) == {"label": "hello", "enabled": True, "node_ids": ["!01020304"]}
    assert store.plugin_settings("example", package_digest=_DIGEST_B) == {}
    store.close()

    reopened = PluginStateStore(str(path))
    assert reopened.plugin_settings("example", package_digest=_DIGEST_A) == {
        "label": "hello",
        "enabled": True,
        "node_ids": ["!01020304"],
    }
    reopened.close()


def test_legacy_id_only_settings_migrate_fail_closed(tmp_path) -> None:
    path = tmp_path / "legacy-settings.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE plugin_settings (
            plugin_id TEXT PRIMARY KEY,
            settings_json TEXT NOT NULL,
            updated_unix INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO plugin_settings(plugin_id, settings_json, updated_unix)
        VALUES (?, ?, ?)
        """,
        ("example", '{"api_token":"legacy-secret"}', 100),
    )
    connection.commit()
    connection.close()

    store = PluginStateStore(str(path))
    assert store.plugin_settings("example", package_digest=_DIGEST_A) == {}
    store.set_plugin_settings(
        "example",
        {"api_token": "new-value"},
        package_digest=_DIGEST_A,
    )
    assert store.plugin_settings("example", package_digest=_DIGEST_A) == {
        "api_token": "new-value"
    }
    store.close()
