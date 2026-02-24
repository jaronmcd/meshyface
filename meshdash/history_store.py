import threading
import time
from typing import Any, Dict, Optional

from .history_maintenance import (
    next_prune_counter as _next_prune_counter_helper,
)
from .history_store_connection import (
    open_and_initialize_history_connection as _open_and_initialize_history_connection_helper,
    prune_history_connection as _prune_history_connection_helper,
)
from .history_store_reads import (
    load_connections as _load_connections_helper,
    load_node_capabilities as _load_node_capabilities_helper,
    load_node_history as _load_node_history_helper,
    load_node_saved_counts as _load_node_saved_counts_helper,
    load_online_activity as _load_online_activity_helper,
    load_recent_chat as _load_recent_chat_helper,
    load_recent_packets as _load_recent_packets_helper,
)
from .history_store_writes import (
    save_chat as _save_chat_helper,
    save_connection_event as _save_connection_event_wrapper_helper,
    save_packet as _save_packet_helper,
)


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
        self._conn = _open_and_initialize_history_connection_helper(
            db_path=self.db_path,
            retention_seconds=self.retention_seconds,
            event_retention_seconds=self.event_retention_seconds,
            rollup_retention_seconds=self.rollup_retention_seconds,
            max_rows=self.max_rows,
            event_max_rows=self.event_max_rows,
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _prune_unlocked(self) -> None:
        _prune_history_connection_helper(
            self._conn,
            retention_seconds=self.retention_seconds,
            event_retention_seconds=self.event_retention_seconds,
            rollup_retention_seconds=self.rollup_retention_seconds,
            max_rows=self.max_rows,
            event_max_rows=self.event_max_rows,
        )

    def _maybe_prune_unlocked(self) -> None:
        self._writes_since_prune, should_prune = _next_prune_counter_helper(
            self._writes_since_prune
        )
        if not should_prune:
            return
        self._prune_unlocked()

    def load_recent_packets(self, limit: int) -> list[Dict[str, Any]]:
        return _load_recent_packets_helper(self, limit)

    def load_recent_chat(self, limit: int) -> list[Dict[str, Any]]:
        return _load_recent_chat_helper(self, limit)

    def load_connections(self) -> list[Dict[str, Any]]:
        return _load_connections_helper(self)

    def load_node_history(self, node_id: str, window_hours: int, max_points: int) -> Dict[str, Any]:
        return _load_node_history_helper(self, node_id, window_hours, max_points)

    def load_online_activity(self, window_hours: int) -> Dict[str, Any]:
        return _load_online_activity_helper(self, window_hours)

    def load_node_saved_counts(self) -> Dict[str, Dict[str, Any]]:
        return _load_node_saved_counts_helper(self)

    def load_node_capabilities(self) -> Dict[str, Dict[str, Any]]:
        return _load_node_capabilities_helper(self)

    def save_connection_event(
        self,
        from_id: str,
        to_id: str,
        rx_time: Optional[int],
        portnum: Optional[str],
        hops: Optional[int],
    ) -> None:
        _save_connection_event_wrapper_helper(
            self,
            from_id=from_id,
            to_id=to_id,
            rx_time=rx_time,
            portnum=portnum,
            hops=hops,
        )

    def save_packet(self, packet_entry: Dict[str, Any]) -> None:
        _save_packet_helper(self, packet_entry)

    def save_chat(self, chat_entry: Dict[str, Any]) -> None:
        _save_chat_helper(self, chat_entry)
