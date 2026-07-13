"""Host-owned durable JSON state and conversational session routing."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass

from .plugin_protocol import PluginProtocolError, _validate_json_value


MAX_STATE_JSON_BYTES = 256 * 1024


class PluginStateConflict(RuntimeError):
    """Raised when a stale handler result attempts to replace newer state."""


@dataclass(frozen=True)
class PluginStateSnapshot:
    state: dict[str, object]
    state_revision: int
    peer_state: dict[str, object]
    peer_state_revision: int


def _canonical_id(value: object, *, label: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        raise ValueError(f"{label} is required")
    if len(text) > 128:
        raise ValueError(f"{label} is too long")
    return text


def _encode_state(value: Mapping[str, object]) -> str:
    state = dict(value)
    _validate_json_value(state)
    encoded = json.dumps(
        state,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if len(encoded.encode("utf-8")) > MAX_STATE_JSON_BYTES:
        raise PluginProtocolError("plugin state exceeds the maximum size")
    return encoded


def _decode_state(value: object) -> dict[str, object]:
    try:
        decoded = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return dict(decoded) if isinstance(decoded, dict) else {}


class PluginStateStore:
    """Small independent SQLite store; never passed to plugin workers."""

    def __init__(self, path: str, *, now_fn=time.time) -> None:
        self.path = os.path.abspath(os.path.expanduser(str(path)))
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, mode=0o700, exist_ok=True)
        self._now_fn = now_fn
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS plugin_state (
                plugin_id TEXT NOT NULL,
                peer_id TEXT NOT NULL,
                state_json TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 0,
                updated_unix INTEGER NOT NULL,
                PRIMARY KEY (plugin_id, peer_id)
            );
            CREATE TABLE IF NOT EXISTS plugin_sessions (
                local_node_id TEXT NOT NULL,
                peer_id TEXT NOT NULL,
                plugin_id TEXT NOT NULL,
                updated_unix INTEGER NOT NULL,
                PRIMARY KEY (local_node_id, peer_id)
            );
            CREATE TABLE IF NOT EXISTS plugin_enablement (
                plugin_id TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL,
                updated_unix INTEGER NOT NULL
            );
            """
        )
        self._connection.commit()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _load_row_locked(self, plugin_id: str, peer_id: str) -> tuple[dict[str, object], int]:
        row = self._connection.execute(
            "SELECT state_json, revision FROM plugin_state WHERE plugin_id=? AND peer_id=?",
            (plugin_id, peer_id),
        ).fetchone()
        if row is None:
            return {}, 0
        return _decode_state(row[0]), max(0, int(row[1] or 0))

    def snapshot(self, plugin_id: object, peer_id: object) -> PluginStateSnapshot:
        clean_plugin = _canonical_id(plugin_id, label="plugin id")
        clean_peer = _canonical_id(peer_id, label="peer id")
        with self._lock:
            state, revision = self._load_row_locked(clean_plugin, "")
            peer_state, peer_revision = self._load_row_locked(clean_plugin, clean_peer)
        return PluginStateSnapshot(state, revision, peer_state, peer_revision)

    def commit(
        self,
        plugin_id: object,
        peer_id: object,
        *,
        state: Mapping[str, object],
        peer_state: Mapping[str, object],
        expected_state_revision: int,
        expected_peer_state_revision: int,
        session_local_node_id: object | None = None,
        session_operation: str | None = None,
    ) -> PluginStateSnapshot:
        clean_plugin = _canonical_id(plugin_id, label="plugin id")
        clean_peer = _canonical_id(peer_id, label="peer id")
        state_json = _encode_state(state)
        peer_json = _encode_state(peer_state)
        clean_local = (
            _canonical_id(session_local_node_id, label="local node id")
            if session_operation is not None
            else ""
        )
        if session_operation not in (None, "start", "end"):
            raise ValueError("session operation must be start or end")
        now_unix = max(0, int(self._now_fn()))
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                _current_state, state_revision = self._load_row_locked(clean_plugin, "")
                _current_peer, peer_revision = self._load_row_locked(clean_plugin, clean_peer)
                if state_revision != int(expected_state_revision) or peer_revision != int(
                    expected_peer_state_revision
                ):
                    raise PluginStateConflict("plugin state changed during handler execution")
                next_state_revision = state_revision + 1
                next_peer_revision = peer_revision + 1
                self._connection.execute(
                    """
                    INSERT INTO plugin_state(plugin_id, peer_id, state_json, revision, updated_unix)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(plugin_id, peer_id) DO UPDATE SET
                        state_json=excluded.state_json,
                        revision=excluded.revision,
                        updated_unix=excluded.updated_unix
                    """,
                    (clean_plugin, "", state_json, next_state_revision, now_unix),
                )
                self._connection.execute(
                    """
                    INSERT INTO plugin_state(plugin_id, peer_id, state_json, revision, updated_unix)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(plugin_id, peer_id) DO UPDATE SET
                        state_json=excluded.state_json,
                        revision=excluded.revision,
                        updated_unix=excluded.updated_unix
                    """,
                    (clean_plugin, clean_peer, peer_json, next_peer_revision, now_unix),
                )
                if session_operation == "start":
                    self._connection.execute(
                        """
                        INSERT INTO plugin_sessions(local_node_id, peer_id, plugin_id, updated_unix)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(local_node_id, peer_id) DO UPDATE SET
                            plugin_id=excluded.plugin_id,
                            updated_unix=excluded.updated_unix
                        """,
                        (clean_local, clean_peer, clean_plugin, now_unix),
                    )
                elif session_operation == "end":
                    self._connection.execute(
                        "DELETE FROM plugin_sessions WHERE local_node_id=? AND peer_id=?",
                        (clean_local, clean_peer),
                    )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        return PluginStateSnapshot(
            dict(state),
            next_state_revision,
            dict(peer_state),
            next_peer_revision,
        )

    def active_session(self, local_node_id: object, peer_id: object) -> str | None:
        local_id = _canonical_id(local_node_id, label="local node id")
        clean_peer = _canonical_id(peer_id, label="peer id")
        with self._lock:
            row = self._connection.execute(
                "SELECT plugin_id FROM plugin_sessions WHERE local_node_id=? AND peer_id=?",
                (local_id, clean_peer),
            ).fetchone()
        return str(row[0]) if row else None

    def list_sessions(self) -> tuple[tuple[str, str, str], ...]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT local_node_id, peer_id, plugin_id FROM plugin_sessions"
            ).fetchall()
        return tuple((str(local_id), str(peer_id), str(plugin_id)) for local_id, peer_id, plugin_id in rows)

    def start_session(self, local_node_id: object, peer_id: object, plugin_id: object) -> None:
        local_id = _canonical_id(local_node_id, label="local node id")
        clean_peer = _canonical_id(peer_id, label="peer id")
        clean_plugin = _canonical_id(plugin_id, label="plugin id")
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO plugin_sessions(local_node_id, peer_id, plugin_id, updated_unix)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(local_node_id, peer_id) DO UPDATE SET
                    plugin_id=excluded.plugin_id,
                    updated_unix=excluded.updated_unix
                """,
                (local_id, clean_peer, clean_plugin, max(0, int(self._now_fn()))),
            )
            self._connection.commit()

    def end_session(self, local_node_id: object, peer_id: object) -> bool:
        local_id = _canonical_id(local_node_id, label="local node id")
        clean_peer = _canonical_id(peer_id, label="peer id")
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM plugin_sessions WHERE local_node_id=? AND peer_id=?",
                (local_id, clean_peer),
            )
            self._connection.commit()
        return int(cursor.rowcount or 0) > 0

    def plugin_enabled(self, plugin_id: object, *, default: bool) -> bool:
        clean_plugin = _canonical_id(plugin_id, label="plugin id")
        with self._lock:
            row = self._connection.execute(
                "SELECT enabled FROM plugin_enablement WHERE plugin_id=?",
                (clean_plugin,),
            ).fetchone()
        return bool(int(row[0])) if row else bool(default)

    def set_plugin_enabled(self, plugin_id: object, enabled: bool) -> None:
        clean_plugin = _canonical_id(plugin_id, label="plugin id")
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO plugin_enablement(plugin_id, enabled, updated_unix)
                VALUES (?, ?, ?)
                ON CONFLICT(plugin_id) DO UPDATE SET
                    enabled=excluded.enabled,
                    updated_unix=excluded.updated_unix
                """,
                (clean_plugin, 1 if enabled else 0, max(0, int(self._now_fn()))),
            )
            self._connection.commit()


__all__ = [
    "MAX_STATE_JSON_BYTES",
    "PluginStateConflict",
    "PluginStateSnapshot",
    "PluginStateStore",
]
