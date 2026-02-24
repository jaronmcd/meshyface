import threading
import time
from typing import Any, Dict, Optional

try:
    import meshtastic
except Exception:
    meshtastic = None

from .chat import (
    build_local_chat_entry as _build_local_chat_entry,
)
from .helpers import (
    calculate_hops as _calculate_hops,
    emoji_from_codepoint as _emoji_from_codepoint,
    extract_emoji_codepoint as _extract_emoji_codepoint,
    extract_packet_battery_level as _extract_packet_battery_level,
    extract_packet_position as _extract_packet_position,
    extract_reply_id as _extract_reply_id,
    format_epoch as _format_epoch,
    to_int as _to_int,
    to_jsonable as _to_jsonable,
)
from .history_store import HistoryStore
from .nodes import (
    get_node_id_from_num as _get_node_id_from_num_helper,
    parse_utc_text_to_unix as _parse_utc_text_to_unix,
    utc_now as _utc_now,
)
from .tracker_snapshot import (
    build_edge_snapshot_rows as _build_edge_snapshot_rows_helper,
    build_tracker_snapshot_payload as _build_tracker_snapshot_payload_helper,
)
from .tracker_edges import (
    record_direct_edge_observation as _record_direct_edge_observation_helper,
)
from .tracker_history_edges import (
    build_historical_edges as _build_historical_edges_helper,
)
from .tracker_bootstrap import (
    load_tracker_history_bootstrap as _load_tracker_history_bootstrap_helper,
)
from .tracker_entries import (
    build_chat_entry_from_packet as _build_chat_entry_from_packet_helper,
    build_packet_summary as _build_packet_summary_helper,
)
from .tracker_ingest import (
    parse_tracker_packet as _parse_tracker_packet_helper,
)
from .tracker_storage import (
    apply_tracker_storage_updates as _apply_tracker_storage_updates_helper,
)
from .tracker_delivery import (
    apply_routing_delivery_update as _apply_routing_delivery_update_helper,
)
from .tracker_local_chat import (
    append_local_chat_entry as _append_local_chat_entry_helper,
)
from .tracker_seed import (
    seed_tracker_from_node_db as _seed_tracker_from_node_db_helper,
)
from .tracker_packet_artifacts import (
    build_tracker_packet_artifacts as _build_tracker_packet_artifacts_helper,
)
from .tracker_observation import (
    apply_tracker_observation as _apply_tracker_observation_helper,
)
from .tracker_receive import (
    process_parsed_tracker_packet as _process_parsed_tracker_packet_helper,
)
from .tracker_local_entry import (
    build_tracker_local_entry as _build_tracker_local_entry_helper,
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


def _get_node_id_from_num(iface: Any, node_num: Any) -> Optional[str]:
    broadcast_num = getattr(meshtastic, "BROADCAST_NUM", None) if meshtastic is not None else None
    return _get_node_id_from_num_helper(
        iface,
        node_num,
        broadcast_num=broadcast_num,
        to_int_fn=_to_int,
    )


class DashboardTracker:
    def __init__(self, packet_limit: int, history_store: Optional[HistoryStore] = None) -> None:
        self._lock = threading.Lock()
        self._history_store = history_store
        self._chat_delivery_timeout_seconds = DEFAULT_CHAT_DELIVERY_TIMEOUT_SECONDS
        self.live_packet_count = 0
        buffers = _initialize_tracker_buffers_helper(packet_limit)
        self.edges = buffers["edges"]
        self._historical_edges = buffers["historical_edges"]
        self.port_counts = buffers["port_counts"]
        self.recent_packets = buffers["recent_packets"]
        self.recent_chat = buffers["recent_chat"]
        delivery_callbacks = _build_tracker_delivery_callbacks_helper(
            self.recent_chat,
            get_timeout_seconds_fn=lambda: self._chat_delivery_timeout_seconds,
            to_int_fn=_to_int,
            parse_utc_text_to_unix_fn=_parse_utc_text_to_unix,
            utc_now_fn=_utc_now,
            now_unix_fn=time.time,
        )
        self._set_delivery_state_fn = delivery_callbacks["set_delivery_state"]
        self._extract_delivery_update_fn = delivery_callbacks["extract_delivery_update"]
        self._expire_pending_deliveries_fn = delivery_callbacks["expire_pending_deliveries"]

        self._historical_edges = _apply_tracker_history_bootstrap_helper(
            history_store=self._history_store,
            packet_limit=packet_limit,
            recent_packets=self.recent_packets,
            recent_chat=self.recent_chat,
            load_tracker_history_bootstrap_fn=_load_tracker_history_bootstrap_helper,
            build_historical_edges_fn=_build_historical_edges_helper,
        )

    def on_receive(self, packet: Dict[str, Any], interface: Any) -> None:
        with self._lock:
            self.live_packet_count += 1
            self._record_packet_unlocked(packet, interface, include_live_count=True)

    def has_recent_packets(self) -> bool:
        with self._lock:
            return bool(self.recent_packets)

    def load_node_saved_counts(self) -> Dict[str, Dict[str, Any]]:
        if self._history_store is None:
            return {}
        return self._history_store.load_node_saved_counts()

    def load_node_capabilities(self) -> Dict[str, Dict[str, Any]]:
        if self._history_store is None:
            return {}
        return self._history_store.load_node_capabilities()

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
        entry = _build_tracker_local_entry_helper(
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
            build_local_chat_entry_fn=_build_local_chat_entry,
            utc_now_fn=_utc_now,
            now_unix_fn=time.time,
            to_int_fn=_to_int,
            emoji_from_codepoint_fn=_emoji_from_codepoint,
        )
        if entry is None:
            return
        with self._lock:
            _append_local_chat_entry_helper(
                recent_chat=self.recent_chat,
                history_store=self._history_store,
                entry=entry,
            )

    def seed_packet(self, packet: Dict[str, Any], interface: Any) -> None:
        with self._lock:
            self._record_packet_unlocked(packet, interface, include_live_count=False)

    def _record_packet_unlocked(
        self, packet: Dict[str, Any], interface: Any, include_live_count: bool
    ) -> None:
        parsed = _parse_tracker_packet_helper(
            packet,
            interface,
            get_node_id_from_num_fn=_get_node_id_from_num,
            to_int_fn=_to_int,
            calculate_hops_fn=_calculate_hops,
            extract_packet_position_fn=_extract_packet_position,
            extract_packet_battery_level_fn=_extract_packet_battery_level,
            extract_reply_id_fn=_extract_reply_id,
            extract_emoji_codepoint_fn=_extract_emoji_codepoint,
            emoji_from_codepoint_fn=_emoji_from_codepoint,
        )
        _process_parsed_tracker_packet_helper(
            packet=packet,
            parsed=parsed,
            include_live_count=include_live_count,
            session_edges=self.edges,
            historical_edges=self._historical_edges,
            port_counts=self.port_counts,
            apply_tracker_observation_fn=_apply_tracker_observation_helper,
            apply_routing_delivery_update_fn=_apply_routing_delivery_update_helper,
            extract_update_fn=self._extract_delivery_update_fn,
            set_delivery_state_fn=self._set_delivery_state_fn,
            record_direct_edge_observation_fn=_record_direct_edge_observation_helper,
            build_tracker_packet_artifacts_fn=_build_tracker_packet_artifacts_helper,
            build_packet_summary_fn=_build_packet_summary_helper,
            build_chat_entry_from_packet_fn=_build_chat_entry_from_packet_helper,
            utc_now_fn=_utc_now,
            format_epoch_fn=_format_epoch,
            to_int_fn=_to_int,
            to_jsonable_fn=_to_jsonable,
            apply_tracker_storage_updates_fn=_apply_tracker_storage_updates_helper,
            recent_packets=self.recent_packets,
            recent_chat=self.recent_chat,
            history_store=self._history_store,
        )

        self._expire_pending_deliveries_fn()

    def snapshot(self, nodes_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        with self._lock:
            self._expire_pending_deliveries_fn()
            return _build_tracker_snapshot_payload_helper(
                session_edges=self.edges,
                historical_edges=self._historical_edges,
                nodes_by_id=nodes_by_id,
                port_counts=self.port_counts,
                recent_packets=self.recent_packets,
                recent_chat=self.recent_chat,
                live_packet_count=self.live_packet_count,
                min_real_link_count=MIN_REAL_LINK_COUNT,
                format_epoch_fn=_format_epoch,
                build_edge_snapshot_rows_fn=_build_edge_snapshot_rows_helper,
            )


def seed_tracker_from_node_db(tracker: DashboardTracker, iface: Any) -> None:
    _seed_tracker_from_node_db_helper(tracker, iface)
