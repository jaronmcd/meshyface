import threading
import time
from typing import Optional

from .helpers import (
    to_int as _to_int,
)
from .history_store_runtime import HistoryStore
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
        self._accept_packets = True
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
        self.radio_link_connected: Optional[bool] = None
        self.radio_link_changed_unix: Optional[int] = None
        self.radio_link_error: Optional[str] = None
        self._zork_bot_service = None

    def _bump_state_revision_unlocked(self) -> None:
        self.state_revision = int(getattr(self, "state_revision", 0) or 0) + 1

    def enable_zork_bot(self, *, send_lock: object | None = None) -> bool:
        try:
            from .services_zork_bot import build_zork_bot_service
        except Exception:
            return False
        self._zork_bot_service = build_zork_bot_service(send_lock=send_lock)
        return True

    def on_receive(self, packet: dict[str, object], interface: object) -> None:
        zork_bot_service = None
        with self._lock:
            if not self._accept_packets:
                return
            self.live_packet_count += 1
            self._record_packet_unlocked(packet, interface, include_live_count=True)
            self._bump_state_revision_unlocked()
            zork_bot_service = self._zork_bot_service
        if zork_bot_service is not None:
            try:
                zork_bot_service.handle_packet(
                    packet,
                    interface,
                    record_local_chat_fn=self.record_local_chat,
                )
            except Exception:
                pass

    def stop_receiving(self) -> None:
        with self._lock:
            self._accept_packets = False

    def has_recent_packets(self) -> bool:
        with self._lock:
            return bool(self.recent_packets)

    def load_node_saved_counts(self) -> dict[str, dict[str, object]]:
        return _load_tracker_node_saved_counts_for_tracker_helper(self)

    def load_node_capabilities(self) -> dict[str, dict[str, object]]:
        return _load_tracker_node_capabilities_for_tracker_helper(self)

    def load_node_packet_trends(
        self,
        *,
        local_node_id: str = "",
        window_seconds: int = 3600,
        bucket_count: int = 24,
        recent_window_seconds: int = 300,
    ) -> dict[str, object]:
        history_store = getattr(self, "_history_store", None)
        load_fn = getattr(history_store, "load_node_packet_trends", None)
        if not callable(load_fn):
            return {}
        return load_fn(
            local_node_id=local_node_id,
            window_seconds=window_seconds,
            bucket_count=bucket_count,
            recent_window_seconds=recent_window_seconds,
        )

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
            changed = _record_tracker_local_chat_for_tracker_helper(
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
            if changed:
                self._bump_state_revision_unlocked()

    def seed_packet(self, packet: dict[str, object], interface: object) -> None:
        with self._lock:
            self._record_packet_unlocked(packet, interface, include_live_count=False)
            self._bump_state_revision_unlocked()

    def _record_packet_unlocked(
        self, packet: dict[str, object], interface: object, include_live_count: bool
    ) -> None:
        _record_tracker_receive_unlocked_for_tracker_helper(
            self,
            packet=packet,
            interface=interface,
            include_live_count=include_live_count,
        )

    def _set_radio_link_state_unlocked(
        self,
        *,
        connected: Optional[bool],
        error: Optional[str],
    ) -> None:
        self.radio_link_connected = connected
        self.radio_link_changed_unix = int(time.time())
        clean_error = str(error).strip() if error else ""
        self.radio_link_error = clean_error or None
        self._bump_state_revision_unlocked()

    def bootstrap_connection_state(self, iface: object) -> None:
        connected_attr = getattr(iface, "isConnected", None)
        connected: Optional[bool] = None
        if hasattr(connected_attr, "is_set"):
            try:
                connected = bool(connected_attr.is_set())
            except Exception:
                connected = None
        elif isinstance(connected_attr, bool):
            connected = connected_attr
        if connected is None:
            return
        with self._lock:
            self._set_radio_link_state_unlocked(
                connected=connected,
                error=None if connected else "link not established",
            )

    def on_connection_established(self, interface: object | None = None, **_kwargs: object) -> None:
        del interface
        with self._lock:
            self._set_radio_link_state_unlocked(connected=True, error=None)

    def on_connection_lost(self, interface: object | None = None, **kwargs: object) -> None:
        del interface
        raw_reason = kwargs.get("reason") or kwargs.get("error")
        reason = str(raw_reason).strip() if raw_reason is not None else ""
        with self._lock:
            self._set_radio_link_state_unlocked(
                connected=False,
                error=reason or "connection lost",
            )

    def radio_link_snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "connected": self.radio_link_connected,
                "changed_unix": self.radio_link_changed_unix,
                "error": self.radio_link_error,
            }

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
