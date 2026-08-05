"""Host-owned durable JSON state and conversational session routing."""

from __future__ import annotations

import hmac
import json
import os
import re
import sqlite3
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass

from .plugin_protocol import PluginProtocolError, _validate_json_value


MAX_STATE_JSON_BYTES = 256 * 1024
MAX_PEER_STATE_ROWS_PER_PLUGIN = 512
MAX_PEER_STATE_BYTES_PER_PLUGIN = 8 * 1024 * 1024
MAX_SESSIONS_PER_PLUGIN = 256
_GLOBAL_STATE_CHANNEL = -1
_RUNTIME_ENABLED_KEY = "runtime_enabled"
_PACKAGE_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")


class PluginStateConflict(RuntimeError):
    """Raised when a stale handler result attempts to replace newer state."""


class PluginStateQuotaExceeded(PluginProtocolError):
    """Raised when a plugin attempts to exceed a durable-state quota."""


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


def _canonical_package_digest(value: object) -> str:
    digest = str(value or "").strip().lower()
    if _PACKAGE_DIGEST_RE.fullmatch(digest) is None:
        raise ValueError("plugin package digest must be a SHA-256 identity")
    return digest


def _canonical_channel(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("channel index must be an integer from 0 through 7")
    try:
        channel = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("channel index must be an integer from 0 through 7") from exc
    if not 0 <= channel <= 7:
        raise ValueError("channel index must be an integer from 0 through 7")
    return channel


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

    def __init__(
        self,
        path: str,
        *,
        now_fn=time.time,
        max_peer_state_rows_per_plugin: int = MAX_PEER_STATE_ROWS_PER_PLUGIN,
        max_peer_state_bytes_per_plugin: int = MAX_PEER_STATE_BYTES_PER_PLUGIN,
        max_sessions_per_plugin: int = MAX_SESSIONS_PER_PLUGIN,
    ) -> None:
        self.path = os.path.abspath(os.path.expanduser(str(path)))
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, mode=0o700, exist_ok=True)
        self._now_fn = now_fn
        self._max_peer_state_rows_per_plugin = max(
            1,
            int(max_peer_state_rows_per_plugin),
        )
        self._max_peer_state_bytes_per_plugin = max(
            2,
            int(max_peer_state_bytes_per_plugin),
        )
        self._max_sessions_per_plugin = max(1, int(max_sessions_per_plugin))
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
                channel_index INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 0,
                updated_unix INTEGER NOT NULL,
                PRIMARY KEY (plugin_id, peer_id, channel_index),
                CHECK (channel_index BETWEEN -1 AND 7)
            );
            CREATE TABLE IF NOT EXISTS plugin_sessions (
                local_node_id TEXT NOT NULL,
                peer_id TEXT NOT NULL,
                channel_index INTEGER NOT NULL,
                plugin_id TEXT NOT NULL,
                updated_unix INTEGER NOT NULL,
                PRIMARY KEY (local_node_id, peer_id, channel_index),
                CHECK (channel_index BETWEEN 0 AND 7)
            );
            CREATE TABLE IF NOT EXISTS plugin_peer_revision_counters (
                plugin_id TEXT PRIMARY KEY,
                revision INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS plugin_enablement (
                plugin_id TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL,
                package_digest TEXT,
                updated_unix INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS plugin_settings (
                plugin_id TEXT PRIMARY KEY,
                settings_json TEXT NOT NULL,
                package_digest TEXT,
                updated_unix INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS plugin_route_policy (
                plugin_id TEXT PRIMARY KEY,
                mesh_enabled INTEGER NOT NULL,
                console_enabled INTEGER NOT NULL,
                ticker_enabled INTEGER NOT NULL DEFAULT 1,
                view_enabled INTEGER NOT NULL DEFAULT 1,
                updated_unix INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS plugin_runtime_settings (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_unix INTEGER NOT NULL
            );
            """
        )
        self._migrate_channel_scopes()
        self._connection.execute(
            """
            INSERT INTO plugin_peer_revision_counters(plugin_id, revision)
            SELECT plugin_id, MAX(revision)
            FROM plugin_state
            WHERE peer_id <> ''
            GROUP BY plugin_id
            ON CONFLICT(plugin_id) DO UPDATE SET
                revision=MAX(
                    plugin_peer_revision_counters.revision,
                    excluded.revision
                )
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS plugin_sessions_plugin_id_idx
            ON plugin_sessions(plugin_id)
            """
        )
        enablement_columns = {
            str(row[1])
            for row in self._connection.execute(
                "PRAGMA table_info(plugin_enablement)"
            ).fetchall()
        }
        if "package_digest" not in enablement_columns:
            # A legacy row has no known package revision. Keep it nullable
            # until startup reconciles the known plugin ID to local files.
            self._connection.execute(
                "ALTER TABLE plugin_enablement ADD COLUMN package_digest TEXT"
            )
        settings_columns = {
            str(row[1])
            for row in self._connection.execute(
                "PRAGMA table_info(plugin_settings)"
            ).fetchall()
        }
        if "package_digest" not in settings_columns:
            # Keep legacy settings unbound until startup validates them against
            # the current known plugin schema and reconciles the local revision.
            self._connection.execute(
                "ALTER TABLE plugin_settings ADD COLUMN package_digest TEXT"
            )
        route_policy_columns = {
            str(row[1])
            for row in self._connection.execute(
                "PRAGMA table_info(plugin_route_policy)"
            ).fetchall()
        }
        if "ticker_enabled" not in route_policy_columns:
            self._connection.execute(
                "ALTER TABLE plugin_route_policy "
                "ADD COLUMN ticker_enabled INTEGER NOT NULL DEFAULT 1"
            )
        if "view_enabled" not in route_policy_columns:
            self._connection.execute(
                "ALTER TABLE plugin_route_policy "
                "ADD COLUMN view_enabled INTEGER NOT NULL DEFAULT 1"
            )
        self._connection.commit()

    def _migrate_channel_scopes(self) -> None:
        state_columns = {
            str(row[1])
            for row in self._connection.execute(
                "PRAGMA table_info(plugin_state)"
            ).fetchall()
        }
        session_columns = {
            str(row[1])
            for row in self._connection.execute(
                "PRAGMA table_info(plugin_sessions)"
            ).fetchall()
        }
        migrate_state = "channel_index" not in state_columns
        migrate_sessions = "channel_index" not in session_columns
        if not migrate_state and not migrate_sessions:
            return
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            if migrate_state:
                self._connection.execute(
                    "ALTER TABLE plugin_state RENAME TO plugin_state_legacy_scope"
                )
                self._connection.execute(
                    """
                    CREATE TABLE plugin_state (
                        plugin_id TEXT NOT NULL,
                        peer_id TEXT NOT NULL,
                        channel_index INTEGER NOT NULL,
                        state_json TEXT NOT NULL,
                        revision INTEGER NOT NULL DEFAULT 0,
                        updated_unix INTEGER NOT NULL,
                        PRIMARY KEY (plugin_id, peer_id, channel_index),
                        CHECK (channel_index BETWEEN -1 AND 7)
                    )
                    """
                )
                self._connection.execute(
                    """
                    INSERT INTO plugin_state(
                        plugin_id,
                        peer_id,
                        channel_index,
                        state_json,
                        revision,
                        updated_unix
                    )
                    SELECT
                        plugin_id,
                        peer_id,
                        CASE WHEN peer_id = '' THEN ? ELSE 0 END,
                        state_json,
                        revision,
                        updated_unix
                    FROM plugin_state_legacy_scope
                    """,
                    (_GLOBAL_STATE_CHANNEL,),
                )
                self._connection.execute("DROP TABLE plugin_state_legacy_scope")
            if migrate_sessions:
                self._connection.execute(
                    "ALTER TABLE plugin_sessions RENAME TO plugin_sessions_legacy_scope"
                )
                self._connection.execute(
                    """
                    CREATE TABLE plugin_sessions (
                        local_node_id TEXT NOT NULL,
                        peer_id TEXT NOT NULL,
                        channel_index INTEGER NOT NULL,
                        plugin_id TEXT NOT NULL,
                        updated_unix INTEGER NOT NULL,
                        PRIMARY KEY (local_node_id, peer_id, channel_index),
                        CHECK (channel_index BETWEEN 0 AND 7)
                    )
                    """
                )
                self._connection.execute(
                    """
                    INSERT INTO plugin_sessions(
                        local_node_id,
                        peer_id,
                        channel_index,
                        plugin_id,
                        updated_unix
                    )
                    SELECT local_node_id, peer_id, 0, plugin_id, updated_unix
                    FROM plugin_sessions_legacy_scope
                    """
                )
                self._connection.execute("DROP TABLE plugin_sessions_legacy_scope")
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def runtime_enabled(self, *, default: bool = True) -> bool:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT value_json
                FROM plugin_runtime_settings
                WHERE key=?
                """,
                (_RUNTIME_ENABLED_KEY,),
            ).fetchone()
        if row is None:
            return bool(default)
        try:
            value = json.loads(str(row[0] or ""))
        except json.JSONDecodeError:
            return bool(default)
        if isinstance(value, bool):
            return value
        return bool(default)

    def set_runtime_enabled(self, enabled: bool) -> bool:
        clean_enabled = bool(enabled)
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO plugin_runtime_settings(key, value_json, updated_unix)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json=excluded.value_json,
                    updated_unix=excluded.updated_unix
                """,
                (
                    _RUNTIME_ENABLED_KEY,
                    json.dumps(clean_enabled),
                    max(0, int(self._now_fn())),
                ),
            )
            self._connection.commit()
        return clean_enabled

    def _load_row_locked(
        self,
        plugin_id: str,
        peer_id: str,
        channel_index: int,
    ) -> tuple[dict[str, object], int, str | None]:
        row = self._connection.execute(
            """
            SELECT state_json, revision
            FROM plugin_state
            WHERE plugin_id=? AND peer_id=? AND channel_index=?
            """,
            (plugin_id, peer_id, channel_index),
        ).fetchone()
        if row is None:
            revision = 0
            if peer_id:
                revision_row = self._connection.execute(
                    """
                    SELECT revision
                    FROM plugin_peer_revision_counters
                    WHERE plugin_id=?
                    """,
                    (plugin_id,),
                ).fetchone()
                if revision_row is not None:
                    revision = max(0, int(revision_row[0] or 0))
            return {}, revision, None
        encoded = str(row[0] or "{}")
        return _decode_state(encoded), max(0, int(row[1] or 0)), encoded

    def _next_peer_revision_locked(self, plugin_id: str) -> int:
        row = self._connection.execute(
            """
            SELECT revision
            FROM plugin_peer_revision_counters
            WHERE plugin_id=?
            """,
            (plugin_id,),
        ).fetchone()
        revision = max(0, int(row[0] or 0)) + 1 if row is not None else 1
        self._connection.execute(
            """
            INSERT INTO plugin_peer_revision_counters(plugin_id, revision)
            VALUES (?, ?)
            ON CONFLICT(plugin_id) DO UPDATE SET revision=excluded.revision
            """,
            (plugin_id, revision),
        )
        return revision

    def snapshot(
        self,
        plugin_id: object,
        peer_id: object,
        channel_index: object = 0,
    ) -> PluginStateSnapshot:
        clean_plugin = _canonical_id(plugin_id, label="plugin id")
        clean_peer = _canonical_id(peer_id, label="peer id")
        clean_channel = _canonical_channel(channel_index)
        with self._lock:
            state, revision, _state_json = self._load_row_locked(
                clean_plugin,
                "",
                _GLOBAL_STATE_CHANNEL,
            )
            peer_state, peer_revision, _peer_json = self._load_row_locked(
                clean_plugin,
                clean_peer,
                clean_channel,
            )
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
        channel_index: object = 0,
        session_local_node_id: object | None = None,
        session_operation: str | None = None,
    ) -> PluginStateSnapshot:
        clean_plugin = _canonical_id(plugin_id, label="plugin id")
        clean_peer = _canonical_id(peer_id, label="peer id")
        clean_channel = _canonical_channel(channel_index)
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
                (
                    _current_state,
                    state_revision,
                    current_state_json,
                ) = self._load_row_locked(
                    clean_plugin,
                    "",
                    _GLOBAL_STATE_CHANNEL,
                )
                (
                    _current_peer,
                    peer_revision,
                    current_peer_json,
                ) = self._load_row_locked(
                    clean_plugin,
                    clean_peer,
                    clean_channel,
                )
                if state_revision != int(expected_state_revision) or peer_revision != int(
                    expected_peer_state_revision
                ):
                    raise PluginStateConflict("plugin state changed during handler execution")
                next_state_revision = state_revision
                if state_json != (current_state_json or "{}"):
                    next_state_revision += 1
                    self._connection.execute(
                        """
                        INSERT INTO plugin_state(
                            plugin_id,
                            peer_id,
                            channel_index,
                            state_json,
                            revision,
                            updated_unix
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(plugin_id, peer_id, channel_index) DO UPDATE SET
                            state_json=excluded.state_json,
                            revision=excluded.revision,
                            updated_unix=excluded.updated_unix
                        """,
                        (
                            clean_plugin,
                            "",
                            _GLOBAL_STATE_CHANNEL,
                            state_json,
                            next_state_revision,
                            now_unix,
                        ),
                    )
                next_peer_revision = peer_revision
                if peer_json == "{}":
                    if current_peer_json not in (None, "{}"):
                        next_peer_revision = self._next_peer_revision_locked(
                            clean_plugin
                        )
                        self._connection.execute(
                            """
                            DELETE FROM plugin_state
                            WHERE plugin_id=? AND peer_id=? AND channel_index=?
                            """,
                            (
                                clean_plugin,
                                clean_peer,
                                clean_channel,
                            ),
                        )
                elif peer_json != (current_peer_json or "{}"):
                    self._enforce_peer_state_quota_locked(
                        clean_plugin,
                        current_peer_json=current_peer_json,
                        next_peer_json=peer_json,
                    )
                    next_peer_revision = self._next_peer_revision_locked(
                        clean_plugin
                    )
                    self._connection.execute(
                        """
                        INSERT INTO plugin_state(
                            plugin_id,
                            peer_id,
                            channel_index,
                            state_json,
                            revision,
                            updated_unix
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(plugin_id, peer_id, channel_index) DO UPDATE SET
                            state_json=excluded.state_json,
                            revision=excluded.revision,
                            updated_unix=excluded.updated_unix
                        """,
                        (
                            clean_plugin,
                            clean_peer,
                            clean_channel,
                            peer_json,
                            next_peer_revision,
                            now_unix,
                        ),
                    )
                if session_operation == "start":
                    self._start_session_locked(
                        clean_local,
                        clean_peer,
                        clean_channel,
                        clean_plugin,
                        now_unix,
                    )
                elif session_operation == "end":
                    self._connection.execute(
                        """
                        DELETE FROM plugin_sessions
                        WHERE local_node_id=? AND peer_id=? AND channel_index=?
                        """,
                        (clean_local, clean_peer, clean_channel),
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

    def _enforce_peer_state_quota_locked(
        self,
        plugin_id: str,
        *,
        current_peer_json: str | None,
        next_peer_json: str,
    ) -> None:
        row = self._connection.execute(
            """
            SELECT
                COUNT(*),
                COALESCE(SUM(LENGTH(CAST(state_json AS BLOB))), 0)
            FROM plugin_state
            WHERE plugin_id=? AND peer_id <> ''
            """,
            (plugin_id,),
        ).fetchone()
        row_count = max(0, int(row[0] or 0)) if row else 0
        byte_count = max(0, int(row[1] or 0)) if row else 0
        next_rows = row_count + (1 if current_peer_json is None else 0)
        previous_bytes = (
            len(current_peer_json.encode("utf-8"))
            if current_peer_json is not None
            else 0
        )
        next_bytes = (
            byte_count
            - previous_bytes
            + len(next_peer_json.encode("utf-8"))
        )
        if next_rows > self._max_peer_state_rows_per_plugin:
            raise PluginStateQuotaExceeded(
                "plugin peer state exceeds the per-plugin row quota"
            )
        if next_bytes > self._max_peer_state_bytes_per_plugin:
            raise PluginStateQuotaExceeded(
                "plugin peer state exceeds the per-plugin byte quota"
            )

    def active_session(
        self,
        local_node_id: object,
        peer_id: object,
        channel_index: object = 0,
    ) -> str | None:
        local_id = _canonical_id(local_node_id, label="local node id")
        clean_peer = _canonical_id(peer_id, label="peer id")
        clean_channel = _canonical_channel(channel_index)
        with self._lock:
            row = self._connection.execute(
                """
                SELECT plugin_id
                FROM plugin_sessions
                WHERE local_node_id=? AND peer_id=? AND channel_index=?
                """,
                (local_id, clean_peer, clean_channel),
            ).fetchone()
        return str(row[0]) if row else None

    def list_sessions(self) -> tuple[tuple[str, str, int, str], ...]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT local_node_id, peer_id, channel_index, plugin_id
                FROM plugin_sessions
                """
            ).fetchall()
        return tuple(
            (
                str(local_id),
                str(peer_id),
                int(channel_index),
                str(plugin_id),
            )
            for local_id, peer_id, channel_index, plugin_id in rows
        )

    def _start_session_locked(
        self,
        local_node_id: str,
        peer_id: str,
        channel_index: int,
        plugin_id: str,
        now_unix: int,
    ) -> None:
        current = self._connection.execute(
            """
            SELECT plugin_id
            FROM plugin_sessions
            WHERE local_node_id=? AND peer_id=? AND channel_index=?
            """,
            (local_node_id, peer_id, channel_index),
        ).fetchone()
        if current is None or str(current[0]) != plugin_id:
            count_row = self._connection.execute(
                "SELECT COUNT(*) FROM plugin_sessions WHERE plugin_id=?",
                (plugin_id,),
            ).fetchone()
            count = max(0, int(count_row[0] or 0)) if count_row else 0
            if count >= self._max_sessions_per_plugin:
                raise PluginStateQuotaExceeded(
                    "plugin sessions exceed the per-plugin quota"
                )
        self._connection.execute(
            """
            INSERT INTO plugin_sessions(
                local_node_id,
                peer_id,
                channel_index,
                plugin_id,
                updated_unix
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(local_node_id, peer_id, channel_index) DO UPDATE SET
                plugin_id=excluded.plugin_id,
                updated_unix=excluded.updated_unix
            """,
            (local_node_id, peer_id, channel_index, plugin_id, now_unix),
        )

    def start_session(
        self,
        local_node_id: object,
        peer_id: object,
        plugin_id: object,
        channel_index: object = 0,
    ) -> None:
        local_id = _canonical_id(local_node_id, label="local node id")
        clean_peer = _canonical_id(peer_id, label="peer id")
        clean_plugin = _canonical_id(plugin_id, label="plugin id")
        clean_channel = _canonical_channel(channel_index)
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._start_session_locked(
                    local_id,
                    clean_peer,
                    clean_channel,
                    clean_plugin,
                    max(0, int(self._now_fn())),
                )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise

    def end_session(
        self,
        local_node_id: object,
        peer_id: object,
        channel_index: object = 0,
    ) -> bool:
        local_id = _canonical_id(local_node_id, label="local node id")
        clean_peer = _canonical_id(peer_id, label="peer id")
        clean_channel = _canonical_channel(channel_index)
        with self._lock:
            cursor = self._connection.execute(
                """
                DELETE FROM plugin_sessions
                WHERE local_node_id=? AND peer_id=? AND channel_index=?
                """,
                (local_id, clean_peer, clean_channel),
            )
            self._connection.commit()
        return int(cursor.rowcount or 0) > 0

    def clear_sessions_for_plugin(self, plugin_id: object) -> int:
        clean_plugin = _canonical_id(plugin_id, label="plugin id")
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM plugin_sessions WHERE plugin_id=?",
                (clean_plugin,),
            )
            self._connection.commit()
        return max(0, int(cursor.rowcount or 0))

    def plugin_enablement_record(
        self,
        plugin_id: object,
    ) -> tuple[bool, str | None] | None:
        clean_plugin = _canonical_id(plugin_id, label="plugin id")
        with self._lock:
            row = self._connection.execute(
                """
                SELECT enabled, package_digest
                FROM plugin_enablement
                WHERE plugin_id=?
                """,
                (clean_plugin,),
            ).fetchone()
        if row is None:
            return None
        stored_digest = str(row[1] or "").strip().lower()
        return (
            bool(int(row[0])),
            (
                stored_digest
                if _PACKAGE_DIGEST_RE.fullmatch(stored_digest) is not None
                else None
            ),
        )

    def plugin_enabled(
        self,
        plugin_id: object,
        *,
        package_digest: object,
        default: bool,
    ) -> bool:
        clean_plugin = _canonical_id(plugin_id, label="plugin id")
        clean_digest = _canonical_package_digest(package_digest)
        with self._lock:
            row = self._connection.execute(
                "SELECT enabled, package_digest FROM plugin_enablement WHERE plugin_id=?",
                (clean_plugin,),
            ).fetchone()
        if row is None:
            return bool(default)
        stored_digest = str(row[1] or "").strip().lower()
        if _PACKAGE_DIGEST_RE.fullmatch(stored_digest) is None:
            return False
        if not hmac.compare_digest(stored_digest, clean_digest):
            return False
        return bool(int(row[0]))

    def set_plugin_enabled(
        self,
        plugin_id: object,
        enabled: bool,
        *,
        package_digest: object,
    ) -> None:
        clean_plugin = _canonical_id(plugin_id, label="plugin id")
        clean_digest = _canonical_package_digest(package_digest)
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO plugin_enablement(
                    plugin_id, enabled, package_digest, updated_unix
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(plugin_id) DO UPDATE SET
                    enabled=excluded.enabled,
                    package_digest=excluded.package_digest,
                    updated_unix=excluded.updated_unix
                """,
                (
                    clean_plugin,
                    1 if enabled else 0,
                    clean_digest,
                    max(0, int(self._now_fn())),
                ),
            )
            self._connection.commit()

    def set_plugin_enabled_if_identity_matches(
        self,
        plugin_id: object,
        enabled: bool,
        *,
        package_digest: object,
    ) -> bool:
        """Apply a startup override only to a new or matching local revision."""

        clean_plugin = _canonical_id(plugin_id, label="plugin id")
        clean_digest = _canonical_package_digest(package_digest)
        with self._lock:
            cursor = self._connection.execute(
                """
                INSERT INTO plugin_enablement(
                    plugin_id, enabled, package_digest, updated_unix
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(plugin_id) DO UPDATE SET
                    enabled=excluded.enabled,
                    package_digest=excluded.package_digest,
                    updated_unix=excluded.updated_unix
                WHERE lower(trim(plugin_enablement.package_digest))
                    = excluded.package_digest
                """,
                (
                    clean_plugin,
                    1 if enabled else 0,
                    clean_digest,
                    max(0, int(self._now_fn())),
                ),
            )
            self._connection.commit()
        return int(cursor.rowcount or 0) > 0

    def reconcile_plugin_identity(
        self,
        plugin_id: object,
        *,
        package_digest: object,
        compatible_settings: Mapping[str, object] | None = None,
        rebind_settings: bool = False,
    ) -> bool:
        """Bind a known plugin record to a trusted local package edit."""

        clean_plugin = _canonical_id(plugin_id, label="plugin id")
        clean_digest = _canonical_package_digest(package_digest)
        if rebind_settings and compatible_settings is None:
            raise ValueError("compatible settings are required for rebinding")
        settings_json = (
            _encode_state(compatible_settings or {}) if rebind_settings else ""
        )
        now_unix = max(0, int(self._now_fn()))
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    """
                    SELECT package_digest
                    FROM plugin_enablement
                    WHERE plugin_id=?
                    """,
                    (clean_plugin,),
                ).fetchone()
                if row is None:
                    self._connection.commit()
                    return False
                stored_digest = str(row[0] or "").strip().lower()
                if (
                    _PACKAGE_DIGEST_RE.fullmatch(stored_digest) is not None
                    and hmac.compare_digest(stored_digest, clean_digest)
                ):
                    self._connection.commit()
                    return False
                self._connection.execute(
                    """
                    UPDATE plugin_enablement
                    SET package_digest=?, updated_unix=?
                    WHERE plugin_id=?
                    """,
                    (clean_digest, now_unix, clean_plugin),
                )
                if rebind_settings:
                    self._connection.execute(
                        """
                        UPDATE plugin_settings
                        SET settings_json=?, package_digest=?, updated_unix=?
                        WHERE plugin_id=?
                        """,
                        (
                            settings_json,
                            clean_digest,
                            now_unix,
                            clean_plugin,
                        ),
                    )
                self._connection.execute(
                    "DELETE FROM plugin_sessions WHERE plugin_id=?",
                    (clean_plugin,),
                )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
        return True

    def plugin_settings(
        self,
        plugin_id: object,
        *,
        package_digest: object,
    ) -> dict[str, object]:
        clean_plugin = _canonical_id(plugin_id, label="plugin id")
        clean_digest = _canonical_package_digest(package_digest)
        with self._lock:
            row = self._connection.execute(
                """
                SELECT settings_json, package_digest
                FROM plugin_settings
                WHERE plugin_id=?
                """,
                (clean_plugin,),
            ).fetchone()
        if row is None:
            return {}
        stored_digest = str(row[1] or "").strip().lower()
        if _PACKAGE_DIGEST_RE.fullmatch(stored_digest) is None:
            return {}
        if not hmac.compare_digest(stored_digest, clean_digest):
            return {}
        return _decode_state(row[0])

    def plugin_settings_record(
        self,
        plugin_id: object,
    ) -> tuple[dict[str, object], str | None] | None:
        """Return host-only settings and their bound package revision."""

        clean_plugin = _canonical_id(plugin_id, label="plugin id")
        with self._lock:
            row = self._connection.execute(
                """
                SELECT settings_json, package_digest
                FROM plugin_settings
                WHERE plugin_id=?
                """,
                (clean_plugin,),
            ).fetchone()
        if row is None:
            return None
        stored_digest = str(row[1] or "").strip().lower()
        return (
            _decode_state(row[0]),
            (
                stored_digest
                if _PACKAGE_DIGEST_RE.fullmatch(stored_digest) is not None
                else None
            ),
        )

    def set_plugin_settings(
        self,
        plugin_id: object,
        settings: Mapping[str, object],
        *,
        package_digest: object,
    ) -> dict[str, object]:
        clean_plugin = _canonical_id(plugin_id, label="plugin id")
        clean_digest = _canonical_package_digest(package_digest)
        settings_json = _encode_state(settings)
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO plugin_settings(
                    plugin_id, settings_json, package_digest, updated_unix
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(plugin_id) DO UPDATE SET
                    settings_json=excluded.settings_json,
                    package_digest=excluded.package_digest,
                    updated_unix=excluded.updated_unix
                """,
                (
                    clean_plugin,
                    settings_json,
                    clean_digest,
                    max(0, int(self._now_fn())),
                ),
            )
            self._connection.commit()
        return dict(settings)

    def plugin_route_policy(self, plugin_id: object) -> dict[str, bool]:
        clean_plugin = _canonical_id(plugin_id, label="plugin id")
        with self._lock:
            row = self._connection.execute(
                """
                SELECT mesh_enabled, console_enabled, ticker_enabled, view_enabled
                FROM plugin_route_policy
                WHERE plugin_id=?
                """,
                (clean_plugin,),
            ).fetchone()
        if row is None:
            return {
                "mesh_enabled": True,
                "console_enabled": True,
                "ticker_enabled": True,
                "view_enabled": True,
            }
        return {
            "mesh_enabled": bool(int(row[0])),
            "console_enabled": bool(int(row[1])),
            "ticker_enabled": bool(int(row[2])),
            "view_enabled": bool(int(row[3])),
        }

    def set_plugin_route_policy(
        self,
        plugin_id: object,
        *,
        mesh_enabled: bool,
        console_enabled: bool,
        ticker_enabled: bool | None = None,
        view_enabled: bool | None = None,
    ) -> dict[str, bool]:
        clean_plugin = _canonical_id(plugin_id, label="plugin id")
        existing_policy = self.plugin_route_policy(clean_plugin)
        clean_ticker_enabled = (
            bool(ticker_enabled)
            if ticker_enabled is not None
            else existing_policy["ticker_enabled"]
        )
        clean_view_enabled = (
            bool(view_enabled)
            if view_enabled is not None
            else existing_policy["view_enabled"]
        )
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO plugin_route_policy(
                    plugin_id,
                    mesh_enabled,
                    console_enabled,
                    ticker_enabled,
                    view_enabled,
                    updated_unix
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(plugin_id) DO UPDATE SET
                    mesh_enabled=excluded.mesh_enabled,
                    console_enabled=excluded.console_enabled,
                    ticker_enabled=excluded.ticker_enabled,
                    view_enabled=excluded.view_enabled,
                    updated_unix=excluded.updated_unix
                """,
                (
                    clean_plugin,
                    1 if mesh_enabled else 0,
                    1 if console_enabled else 0,
                    1 if clean_ticker_enabled else 0,
                    1 if clean_view_enabled else 0,
                    max(0, int(self._now_fn())),
                ),
            )
            self._connection.commit()
        return {
            "mesh_enabled": bool(mesh_enabled),
            "console_enabled": bool(console_enabled),
            "ticker_enabled": clean_ticker_enabled,
            "view_enabled": clean_view_enabled,
        }


__all__ = [
    "MAX_PEER_STATE_BYTES_PER_PLUGIN",
    "MAX_PEER_STATE_ROWS_PER_PLUGIN",
    "MAX_SESSIONS_PER_PLUGIN",
    "MAX_STATE_JSON_BYTES",
    "PluginStateConflict",
    "PluginStateQuotaExceeded",
    "PluginStateSnapshot",
    "PluginStateStore",
]
