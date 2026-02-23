import json
import os
import sqlite3
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

from .helpers import to_int as _to_int
from .history_readers import (
    decode_connections_rows as _decode_connections_rows_helper,
    decode_recent_chat_rows as _decode_recent_chat_rows_helper,
    decode_recent_packets_rows as _decode_recent_packets_rows_helper,
)
from .history_queries import (
    fetch_connection_rows as _fetch_connection_rows_helper,
    fetch_node_capability_rows as _fetch_node_capability_rows_helper,
    fetch_node_history_rows as _fetch_node_history_rows_helper,
    fetch_node_saved_count_rows as _fetch_node_saved_count_rows_helper,
    fetch_online_activity_rows as _fetch_online_activity_rows_helper,
    fetch_recent_chat_rows as _fetch_recent_chat_rows_helper,
    fetch_recent_packet_rows as _fetch_recent_packet_rows_helper,
)
from .history_analytics import (
    build_node_history_payload as _build_node_history_payload_helper,
    build_online_activity_payload as _build_online_activity_payload_helper,
)
from .history_capabilities import (
    decode_node_capabilities_rows as _decode_node_capabilities_rows_helper,
    decode_node_saved_counts_rows as _decode_node_saved_counts_rows_helper,
)
from .history_connection_writes import (
    save_connection_event as _save_connection_event_helper,
)
from .history_backfill import backfill_node_capabilities as _backfill_node_capabilities_helper
from .history_writes import (
    save_packet_event_and_rollups as _save_packet_event_and_rollups_helper,
)
from .history_prune import prune_history_tables as _prune_history_tables_helper
from .history_schema import initialize_history_schema as _initialize_history_schema_helper


class HistoryStore:
    def __init__(
        self,
        db_path: str,
        max_rows: int,
        retention_days: int,
        event_max_rows: int,
        event_retention_days: int,
        rollup_retention_days: int,
    ) -> None:
        self.db_path = db_path
        self.max_rows = max(100, int(max_rows))
        self.retention_seconds = max(0, int(retention_days)) * 86400
        self.event_max_rows = max(1000, int(event_max_rows))
        self.event_retention_seconds = max(0, int(event_retention_days)) * 86400
        self.rollup_retention_seconds = max(0, int(rollup_retention_days)) * 86400
        self._writes_since_prune = 0
        self._lock = threading.Lock()

        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=5000")

        with self._lock:
            self._init_schema_unlocked()
            self._prune_unlocked()
            self._maybe_backfill_node_capabilities_unlocked()
            self._conn.commit()

    def _init_schema_unlocked(self) -> None:
        _initialize_history_schema_helper(self._conn)

    def _maybe_backfill_node_capabilities_unlocked(self) -> None:
        _backfill_node_capabilities_helper(self._conn, to_int_fn=_to_int)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _prune_unlocked(self) -> None:
        _prune_history_tables_helper(
            self._conn,
            now_unix=int(time.time()),
            retention_seconds=self.retention_seconds,
            event_retention_seconds=self.event_retention_seconds,
            rollup_retention_seconds=self.rollup_retention_seconds,
            max_rows=self.max_rows,
            event_max_rows=self.event_max_rows,
        )

    def _maybe_prune_unlocked(self) -> None:
        self._writes_since_prune += 1
        if self._writes_since_prune < 50:
            return
        self._writes_since_prune = 0
        self._prune_unlocked()

    def load_recent_packets(self, limit: int) -> list[Dict[str, Any]]:
        with self._lock:
            rows = _fetch_recent_packet_rows_helper(self._conn, limit=limit)
        return _decode_recent_packets_rows_helper(rows)

    def load_recent_chat(self, limit: int) -> list[Dict[str, Any]]:
        with self._lock:
            rows = _fetch_recent_chat_rows_helper(self._conn, limit=limit)
        return _decode_recent_chat_rows_helper(rows)

    def load_connections(self) -> list[Dict[str, Any]]:
        with self._lock:
            rows = _fetch_connection_rows_helper(self._conn)
        return _decode_connections_rows_helper(rows)

    def load_node_history(self, node_id: str, window_hours: int, max_points: int) -> Dict[str, Any]:
        clean_node_id = str(node_id or "").strip()
        hours = max(1, int(window_hours))
        if not clean_node_id:
            return _build_node_history_payload_helper(
                node_id="",
                window_hours=hours,
                metric_rows=[],
                position_rows=[],
            )
        limit = max(20, min(10000, int(max_points)))
        cutoff = int(time.time()) - (hours * 3600)

        with self._lock:
            rows, position_rows = _fetch_node_history_rows_helper(
                self._conn,
                node_id=clean_node_id,
                cutoff=cutoff,
                limit=limit,
            )

        return _build_node_history_payload_helper(
            node_id=clean_node_id,
            window_hours=hours,
            metric_rows=rows,
            position_rows=position_rows,
        )

    def load_online_activity(self, window_hours: int) -> Dict[str, Any]:
        hours = max(1, min(24 * 365, int(window_hours)))
        cutoff = int(time.time()) - (hours * 3600)

        with self._lock:
            rows, distinct_nodes = _fetch_online_activity_rows_helper(
                self._conn,
                cutoff=cutoff,
            )

        return _build_online_activity_payload_helper(
            window_hours=hours,
            hour_rows=rows,
            distinct_nodes=distinct_nodes,
            timezone_label=datetime.now().astimezone().tzname() or "local",
        )

    def load_node_saved_counts(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            rows = _fetch_node_saved_count_rows_helper(self._conn)
        return _decode_node_saved_counts_rows_helper(rows)

    def load_node_capabilities(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            rows = _fetch_node_capability_rows_helper(self._conn)
        return _decode_node_capabilities_rows_helper(rows)

    def save_connection_event(
        self,
        from_id: str,
        to_id: str,
        rx_time: Optional[int],
        portnum: Optional[str],
        hops: Optional[int],
    ) -> None:
        with self._lock:
            _save_connection_event_helper(
                self._conn,
                from_id=from_id,
                to_id=to_id,
                rx_time=rx_time,
                portnum=portnum,
                hops=hops,
                now_unix_fn=time.time,
            )

            self._maybe_prune_unlocked()
            self._conn.commit()

    def save_packet(self, packet_entry: Dict[str, Any]) -> None:
        summary = packet_entry.get("summary")
        packet = packet_entry.get("packet")
        summary_json = json.dumps(summary, separators=(",", ":"))
        packet_json = json.dumps(packet, separators=(",", ":"))

        with self._lock:
            self._conn.execute(
                "INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(?, ?, ?)",
                (int(time.time()), summary_json, packet_json),
            )
            if isinstance(summary, dict):
                _save_packet_event_and_rollups_helper(self._conn, summary, now_unix_fn=time.time)
            self._maybe_prune_unlocked()
            self._conn.commit()

    def save_chat(self, chat_entry: Dict[str, Any]) -> None:
        message_json = json.dumps(chat_entry, separators=(",", ":"))

        with self._lock:
            self._conn.execute(
                "INSERT INTO chat(created_unix, message_json) VALUES(?, ?)",
                (int(time.time()), message_json),
            )
            self._maybe_prune_unlocked()
            self._conn.commit()
