import threading
import time
from typing import Optional

from .helpers import (
    to_int as _to_int,
)
from .history_store import HistoryStore
from .nodes import (
    parse_utc_text_to_unix as _parse_utc_text_to_unix,
    utc_now as _utc_now,
)
from .tracker_runtime_receive_bindings import (
    record_tracker_receive_unlocked_for_tracker as _record_tracker_receive_unlocked_for_tracker_helper,
)
from .tracker_runtime_init import (
    initialize_dashboard_tracker_runtime as _initialize_dashboard_tracker_runtime_helper,
)
from .tracker_runtime_chat import (
    record_tracker_local_chat_for_tracker as _record_tracker_local_chat_for_tracker_helper,
)
from .tracker_runtime_state import (
    build_tracker_snapshot_for_tracker_typed as _build_tracker_snapshot_for_tracker_typed_helper,
    load_tracker_node_capabilities_for_tracker as _load_tracker_node_capabilities_for_tracker_helper,
    load_tracker_node_saved_counts_for_tracker as _load_tracker_node_saved_counts_for_tracker_helper,
)
from .tracker_snapshot_contracts import TrackerSnapshot
from .tracker_seed import (
    seed_tracker_from_node_db as _seed_tracker_from_node_db_helper,
)
from .tracker_history_edges import (
    build_historical_edges as _build_historical_edges_helper,
)
from .tracker_bootstrap import (
    load_tracker_history_bootstrap as _load_tracker_history_bootstrap_helper,
)
from .tracker_callbacks import (
    build_tracker_delivery_callbacks as _build_tracker_delivery_callbacks_helper,
)
from .tracker_setup import (
    apply_tracker_history_bootstrap as _apply_tracker_history_bootstrap_helper,
    initialize_tracker_buffers as _initialize_tracker_buffers_helper,
)


DEFAULT_CHAT_DELIVERY_TIMEOUT_SECONDS = 90
MIN_REAL_LINK_COUNT = 2


class DashboardTracker:
    def __init__(self, packet_limit: int, history_store: Optional[HistoryStore] = None) -> None:
        self._lock = threading.Lock()
        _initialize_dashboard_tracker_runtime_helper(
            self,
            packet_limit=packet_limit,
            history_store=history_store,
            default_chat_delivery_timeout_seconds=DEFAULT_CHAT_DELIVERY_TIMEOUT_SECONDS,
            initialize_tracker_buffers_fn=_initialize_tracker_buffers_helper,
            build_tracker_delivery_callbacks_fn=_build_tracker_delivery_callbacks_helper,
            apply_tracker_history_bootstrap_fn=_apply_tracker_history_bootstrap_helper,
            load_tracker_history_bootstrap_fn=_load_tracker_history_bootstrap_helper,
            build_historical_edges_fn=_build_historical_edges_helper,
            parse_utc_text_to_unix_fn=_parse_utc_text_to_unix,
            utc_now_fn=_utc_now,
            to_int_fn=_to_int,
            now_unix_fn=time.time,
        )

    def on_receive(self, packet: dict[str, object], interface: object) -> None:
        with self._lock:
            self.live_packet_count += 1
            self._record_packet_unlocked(packet, interface, include_live_count=True)

    def has_recent_packets(self) -> bool:
        with self._lock:
            return bool(self.recent_packets)

    def load_node_saved_counts(self) -> dict[str, dict[str, object]]:
        return _load_tracker_node_saved_counts_for_tracker_helper(self)

    def load_node_capabilities(self) -> dict[str, dict[str, object]]:
        return _load_tracker_node_capabilities_for_tracker_helper(self)

    def record_local_chat(
        self,
        text: str,
        from_id: str = "local",
        to_id: str = "^all",
        channel_index: int = 0,
        message_id: Optional[int] = None,
        reply_id: Optional[int] = None,
        emoji: Optional[str] = None,
        emoji_codepoint: Optional[int] = None,
        is_reaction: bool = False,
        ack_requested: bool = False,
        retry_of: Optional[int] = None,
    ) -> None:
        with self._lock:
            _record_tracker_local_chat_for_tracker_helper(
                self,
                text=text,
                from_id=from_id,
                to_id=to_id,
                channel_index=channel_index,
                message_id=message_id,
                reply_id=reply_id,
                emoji=emoji,
                emoji_codepoint=emoji_codepoint,
                is_reaction=is_reaction,
                ack_requested=ack_requested,
                retry_of=retry_of,
                now_unix_fn=time.time,
            )

    def seed_packet(self, packet: dict[str, object], interface: object) -> None:
        with self._lock:
            self._record_packet_unlocked(packet, interface, include_live_count=False)

    def _record_packet_unlocked(
        self, packet: dict[str, object], interface: object, include_live_count: bool
    ) -> None:
        _record_tracker_receive_unlocked_for_tracker_helper(
            self,
            packet=packet,
            interface=interface,
            include_live_count=include_live_count,
        )

    def snapshot_typed(self, nodes_by_id: dict[str, dict[str, object]]) -> TrackerSnapshot:
        with self._lock:
            return _build_tracker_snapshot_for_tracker_typed_helper(
                self,
                nodes_by_id=nodes_by_id,
                min_real_link_count=MIN_REAL_LINK_COUNT,
            )

    def snapshot(self, nodes_by_id: dict[str, dict[str, object]]) -> dict[str, object]:
        return self.snapshot_typed(nodes_by_id).as_dict()


def seed_tracker_from_node_db(tracker: DashboardTracker, iface: object) -> None:
    _seed_tracker_from_node_db_helper(tracker, iface)
