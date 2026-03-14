from typing import Optional

from .history_store_runtime_init import (
    initialize_history_store_runtime as _initialize_history_store_runtime_helper,
)
from .history_store_runtime_maintenance import (
    close_history_store as _close_history_store_helper,
    maybe_prune_history_store_unlocked as _maybe_prune_history_store_unlocked_helper,
    prune_history_store_unlocked as _prune_history_store_unlocked_helper,
    reset_history_store as _reset_history_store_helper,
)
from .history_store_chat import (
    load_recent_chat as _load_recent_chat_helper,
    save_chat as _save_chat_helper,
)
from .history_store_connections import (
    load_connections as _load_connections_helper,
    save_connection_event as _save_connection_event_wrapper_helper,
)
from .history_store_nodes import (
    load_node_capabilities as _load_node_capabilities_helper,
    load_node_history as _load_node_history_helper,
    load_node_saved_counts as _load_node_saved_counts_helper,
    load_online_activity as _load_online_activity_helper,
)
from .history_store_packets import (
    load_recent_packets as _load_recent_packets_helper,
    search_packets as _search_packets_helper,
    save_packet as _save_packet_helper,
)
from .history_store_summary import (
    load_summary_metrics as _load_summary_metrics_helper,
    save_summary_metrics as _save_summary_metrics_helper,
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
        _initialize_history_store_runtime_helper(
            self,
            db_path=db_path,
            max_rows=max_rows,
            retention_days=retention_days,
            event_max_rows=event_max_rows,
            event_retention_days=event_retention_days,
            rollup_retention_days=rollup_retention_days,
        )

    def close(self) -> None:
        _close_history_store_helper(self)

    def _prune_unlocked(self) -> None:
        _prune_history_store_unlocked_helper(
            self,
        )

    def _maybe_prune_unlocked(self) -> None:
        _maybe_prune_history_store_unlocked_helper(
            self,
            prune_unlocked_fn=self._prune_unlocked,
        )

    def reset(self) -> int:
        return _reset_history_store_helper(self)

    def load_recent_packets(self, limit: int) -> list[dict[str, object]]:
        return _load_recent_packets_helper(self, limit)

    def search_packets(
        self,
        needle: str,
        *,
        limit: int | None = None,
        before: int | None = None,
        after: int | None = None,
        scope: str | None = None,
        scan_limit: int | None = None,
    ) -> dict[str, object]:
        return _search_packets_helper(
            self,
            needle,
            limit=limit,
            before=before,
            after=after,
            scope=scope,
            scan_limit=scan_limit,
        )

    def load_recent_chat(self, limit: int) -> list[dict[str, object]]:
        return _load_recent_chat_helper(self, limit)

    def load_connections(self) -> list[dict[str, object]]:
        return _load_connections_helper(self)

    def load_node_history(self, node_id: str, window_hours: int, max_points: int) -> dict[str, object]:
        return _load_node_history_helper(self, node_id, window_hours, max_points)

    def load_online_activity(self, window_hours: int) -> dict[str, object]:
        return _load_online_activity_helper(self, window_hours)

    def load_node_saved_counts(self) -> dict[str, dict[str, object]]:
        return _load_node_saved_counts_helper(self)

    def load_node_capabilities(self) -> dict[str, dict[str, object]]:
        return _load_node_capabilities_helper(self)

    def load_summary_metrics(self, window_hours: int) -> dict[str, object]:
        return _load_summary_metrics_helper(self, window_hours)

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

    def save_packet(self, packet_entry: dict[str, object]) -> None:
        _save_packet_helper(self, packet_entry)

    def save_chat(self, chat_entry: dict[str, object]) -> None:
        _save_chat_helper(self, chat_entry)

    def save_summary_metrics(self, summary: dict[str, object]) -> None:
        _save_summary_metrics_helper(self, summary)
