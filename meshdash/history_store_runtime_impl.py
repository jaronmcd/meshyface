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
    load_chat_page as _load_chat_page_helper,
    load_recent_chat as _load_recent_chat_helper,
    save_chat as _save_chat_helper,
    update_chat as _update_chat_helper,
)
from .history_store_connections import (
    load_connections as _load_connections_helper,
    save_connection_event as _save_connection_event_wrapper_helper,
)
from .history_store_link_edges import (
    load_link_edges as _load_link_edges_helper,
)
from .history_location_estimates import (
    load_location_estimates as _load_location_estimates_helper,
)
from .history_store_nodes import (
    load_node_capabilities as _load_node_capabilities_helper,
    load_node_history as _load_node_history_helper,
    load_node_position_counts as _load_node_position_counts_helper,
    load_node_saved_counts as _load_node_saved_counts_helper,
    load_online_activity as _load_online_activity_helper,
)
from .history_node_packet_trends import (
    load_node_packet_trends as _load_node_packet_trends_helper,
)
from .history_store_packets import (
    load_environment_metrics_history as _load_environment_metrics_history_helper,
    load_recent_packets as _load_recent_packets_helper,
    search_packets as _search_packets_helper,
    save_packet as _save_packet_helper,
)
from .history_store_malformed_text import (
    load_malformed_text_history as _load_malformed_text_history_helper,
)
from .history_store_summary import (
    load_summary_metrics as _load_summary_metrics_helper,
    save_summary_metrics as _save_summary_metrics_helper,
)
from .history_top_nodes import (
    load_top_nodes as _load_top_nodes_helper,
)
from .history_store_settings import (
    append_bbs_post as _append_bbs_post_helper,
    load_bbs_posts as _load_bbs_posts_helper,
    load_bbs_settings as _load_bbs_settings_helper,
    load_bot_runtime_settings as _load_bot_runtime_settings_helper,
    load_custom_telemetry_settings as _load_custom_telemetry_settings_helper,
    save_bbs_settings as _save_bbs_settings_helper,
    save_bot_runtime_settings as _save_bot_runtime_settings_helper,
    save_custom_telemetry_settings as _save_custom_telemetry_settings_helper,
)
from .history_store_database_stats import (
    load_database_stats as _load_database_stats_helper,
)
from .history_raw_packets import (
    build_raw_packet_database_download as _build_raw_packet_database_download_helper,
    load_raw_packet_stats as _load_raw_packet_stats_helper,
    save_raw_packet_capture as _save_raw_packet_capture_helper,
    save_raw_packet_settings as _save_raw_packet_settings_helper,
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
        source: str | None = None,
    ) -> dict[str, object]:
        return _search_packets_helper(
            self,
            needle,
            limit=limit,
            before=before,
            after=after,
            scope=scope,
            scan_limit=scan_limit,
            source=source,
        )

    def load_environment_metrics_history(
        self,
        *,
        window_hours: int | None = None,
        metric: str | None = None,
        node_id: str | None = None,
        limit: int | None = None,
        include_gap_scan: bool = True,
        catalog_only: bool = False,
    ) -> dict[str, object]:
        return _load_environment_metrics_history_helper(
            self,
            window_hours=window_hours,
            metric=metric,
            node_id=node_id,
            limit=limit,
            include_gap_scan=include_gap_scan,
            catalog_only=catalog_only,
        )

    def load_malformed_text_history(
        self,
        *,
        window_hours: int | None = None,
        node_id: str | None = None,
        limit: int | None = None,
    ) -> dict[str, object]:
        return _load_malformed_text_history_helper(
            self,
            window_hours=window_hours,
            node_id=node_id,
            limit=limit,
        )

    def load_recent_chat(self, limit: int) -> list[dict[str, object]]:
        return _load_recent_chat_helper(self, limit)

    def load_chat_page(
        self,
        *,
        limit: int,
        before_id: int | None = None,
        before_unix: int | None = None,
        scope: str | None = None,
        peer_id: str | None = None,
    ) -> list[dict[str, object]]:
        return _load_chat_page_helper(
            self,
            limit=limit,
            before_id=before_id,
            before_unix=before_unix,
            scope=scope,
            peer_id=peer_id,
        )

    def load_connections(self) -> list[dict[str, object]]:
        return _load_connections_helper(self)

    def load_link_edges(self, window: object = "7d", limit: object = 1200) -> dict[str, object]:
        return _load_link_edges_helper(self, window=window, limit=limit)

    def load_location_estimates(self, window: object = "72h", limit: object = 600) -> dict[str, object]:
        return _load_location_estimates_helper(self, window=window, limit=limit)

    def load_node_history(self, node_id: str, window_hours: int, max_points: int) -> dict[str, object]:
        return _load_node_history_helper(self, node_id, window_hours, max_points)

    def load_online_activity(self, window_hours: int) -> dict[str, object]:
        return _load_online_activity_helper(self, window_hours)

    def load_node_saved_counts(self) -> dict[str, dict[str, object]]:
        return _load_node_saved_counts_helper(self)

    def load_node_position_counts(self) -> dict[str, dict[str, object]]:
        return _load_node_position_counts_helper(self)

    def load_node_capabilities(self) -> dict[str, dict[str, object]]:
        return _load_node_capabilities_helper(self)

    def load_node_packet_trends(
        self,
        *,
        local_node_id: str = "",
        window_seconds: int = 3600,
        bucket_count: int = 24,
        recent_window_seconds: int = 300,
    ) -> dict[str, object]:
        return _load_node_packet_trends_helper(
            self,
            local_node_id=local_node_id,
            window_seconds=window_seconds,
            bucket_count=bucket_count,
            recent_window_seconds=recent_window_seconds,
        )

    def load_summary_metrics(self, window_hours: int) -> dict[str, object]:
        return _load_summary_metrics_helper(self, window_hours)

    def load_top_nodes(
        self,
        category: object = "saved_packets",
        limit: object = 10,
        exclude_node_ids: object = None,
    ) -> dict[str, object]:
        return _load_top_nodes_helper(
            self,
            category=category,
            limit=limit,
            exclude_node_ids=exclude_node_ids,
        )

    def database_stats(self) -> dict[str, object]:
        stats = _load_database_stats_helper(self)
        stats["raw_packet_store"] = _load_raw_packet_stats_helper(self)
        return stats

    def raw_packet_stats(self) -> dict[str, object]:
        return _load_raw_packet_stats_helper(self)

    def set_raw_packet_capture_settings(self, settings: object) -> dict[str, object]:
        return _save_raw_packet_settings_helper(self, settings=settings)

    def save_raw_packet(self, packet: object) -> bool:
        return _save_raw_packet_capture_helper(self, packet)

    def raw_packet_database_download(self) -> dict[str, object]:
        return _build_raw_packet_database_download_helper(self)

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

    def update_chat(self, chat_entry: dict[str, object]) -> bool:
        return _update_chat_helper(self, chat_entry)

    def save_summary_metrics(self, summary: dict[str, object]) -> None:
        _save_summary_metrics_helper(self, summary)

    def get_custom_telemetry_settings(self) -> dict[str, object]:
        return _load_custom_telemetry_settings_helper(self)

    def set_custom_telemetry_settings(self, rules: object) -> dict[str, object]:
        return _save_custom_telemetry_settings_helper(self, rules=rules)

    def get_bbs_settings(self) -> dict[str, object]:
        return _load_bbs_settings_helper(self)

    def get_bot_runtime_settings(self) -> dict[str, object]:
        return _load_bot_runtime_settings_helper(self)

    def get_bbs_posts(self) -> dict[str, object]:
        return _load_bbs_posts_helper(self)

    def set_bbs_settings(self, settings: object) -> dict[str, object]:
        return _save_bbs_settings_helper(self, settings=settings)

    def set_bot_runtime_settings(self, settings: object) -> dict[str, object]:
        return _save_bot_runtime_settings_helper(self, settings=settings)

    def append_bbs_post(self, post: object) -> dict[str, object]:
        return _append_bbs_post_helper(self, post=post)
