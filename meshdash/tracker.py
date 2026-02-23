import threading
import time
from collections import Counter, deque
from typing import Any, Dict, Optional, Tuple

try:
    import meshtastic
except Exception:
    meshtastic = None

from .chat import (
    build_local_chat_entry as _build_local_chat_entry,
    chat_message_id as _chat_message_id_helper,
    expire_pending_deliveries as _expire_pending_deliveries_helper,
    extract_routing_delivery_update as _extract_routing_delivery_update_helper,
    set_delivery_state as _set_delivery_state_helper,
)
from .helpers import (
    calculate_hops as _calculate_hops,
    emoji_from_codepoint as _emoji_from_codepoint,
    extract_emoji_codepoint as _extract_emoji_codepoint,
    extract_packet_battery_level as _extract_packet_battery_level,
    extract_packet_position as _extract_packet_position,
    extract_reply_id as _extract_reply_id,
    format_epoch as _format_epoch,
    safe_json_loads as _safe_json_loads,
    to_int as _to_int,
    to_jsonable as _to_jsonable,
)
from .history_store import HistoryStore
from .nodes import (
    get_node_id_from_num as _get_node_id_from_num_helper,
    parse_utc_text_to_unix as _parse_utc_text_to_unix,
    safe_nodes_items as _safe_nodes_items,
    utc_now as _utc_now,
)
from .tracker_snapshot import (
    build_edge_snapshot_rows as _build_edge_snapshot_rows_helper,
)
from .tracker_edges import (
    record_direct_edge_observation as _record_direct_edge_observation_helper,
)
from .tracker_history_edges import (
    build_historical_edges as _build_historical_edges_helper,
)
from .tracker_entries import (
    build_chat_entry_from_packet as _build_chat_entry_from_packet_helper,
    build_packet_summary as _build_packet_summary_helper,
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
        self.edges: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._historical_edges: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.port_counts: Counter[str] = Counter()
        self.recent_packets: deque[Dict[str, Any]] = deque(maxlen=packet_limit)
        self.recent_chat: deque[Dict[str, Any]] = deque(maxlen=packet_limit)

        if self._history_store is not None:
            for entry in self._history_store.load_recent_packets(packet_limit):
                self.recent_packets.append(entry)
            for entry in self._history_store.load_recent_chat(packet_limit):
                self.recent_chat.append(entry)
            self._historical_edges = _build_historical_edges_helper(
                self._history_store.load_connections()
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

    def _chat_message_id(self, entry: Any) -> Optional[int]:
        return _chat_message_id_helper(entry, to_int_fn=_to_int)

    def _set_delivery_state_unlocked(
        self,
        message_id: Any,
        state: str,
        error: Optional[str] = None,
    ) -> bool:
        return _set_delivery_state_helper(
            self.recent_chat,
            message_id=message_id,
            state=state,
            error=error,
            to_int_fn=_to_int,
            now_text_fn=_utc_now,
            now_unix_fn=lambda: int(time.time()),
        )

    def _extract_routing_delivery_update_unlocked(self, decoded: Any) -> Optional[Dict[str, Any]]:
        return _extract_routing_delivery_update_helper(decoded, to_int_fn=_to_int)

    def _expire_pending_deliveries_unlocked(self) -> None:
        _expire_pending_deliveries_helper(
            self.recent_chat,
            timeout_seconds=self._chat_delivery_timeout_seconds,
            to_int_fn=_to_int,
            parse_utc_text_to_unix_fn=_parse_utc_text_to_unix,
            now_unix_fn=lambda: int(time.time()),
            now_text_fn=_utc_now,
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
        now_text = _utc_now()
        now_unix = int(time.time())
        entry = _build_local_chat_entry(
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
            now_text=now_text,
            now_unix=now_unix,
            to_int_fn=_to_int,
            emoji_from_codepoint_fn=_emoji_from_codepoint,
        )
        if entry is None:
            return
        with self._lock:
            self.recent_chat.append(entry)
            if self._history_store is not None:
                self._history_store.save_chat(entry)

    def seed_packet(self, packet: Dict[str, Any], interface: Any) -> None:
        with self._lock:
            self._record_packet_unlocked(packet, interface, include_live_count=False)

    def _record_packet_unlocked(
        self, packet: Dict[str, Any], interface: Any, include_live_count: bool
    ) -> None:
        from_id = packet.get("fromId") or _get_node_id_from_num(interface, packet.get("from"))
        to_id = packet.get("toId") or _get_node_id_from_num(interface, packet.get("to"))
        rx_time = _to_int(packet.get("rxTime"))
        hops = _calculate_hops(packet.get("hopStart"), packet.get("hopLimit"))

        decoded = packet.get("decoded", {})
        portnum = decoded.get("portnum") if isinstance(decoded, dict) else None
        packet_id = _to_int(packet.get("id"))
        packet_position = _extract_packet_position(packet)
        packet_battery = _extract_packet_battery_level(packet)
        reply_id = _extract_reply_id(decoded)
        emoji_codepoint = _extract_emoji_codepoint(decoded)
        emoji_glyph = _emoji_from_codepoint(emoji_codepoint)
        is_reaction = bool(reply_id is not None and reply_id > 0 and emoji_glyph)
        delivery_update = self._extract_routing_delivery_update_unlocked(decoded)
        if delivery_update is not None:
            self._set_delivery_state_unlocked(
                delivery_update.get("request_id"),
                str(delivery_update.get("state") or "sent"),
                delivery_update.get("error"),
            )
        if portnum is not None:
            self.port_counts[str(portnum)] += 1

        direct_key = _record_direct_edge_observation_helper(
            session_edges=self.edges,
            historical_edges=self._historical_edges,
            from_id=from_id,
            to_id=to_id,
            rx_time=rx_time,
            portnum=portnum,
            hops=hops,
            include_live_count=include_live_count,
        )
        if direct_key is not None and include_live_count and self._history_store is not None:
            self._history_store.save_connection_event(
                from_id=direct_key[0],
                to_id=direct_key[1],
                rx_time=rx_time,
                portnum=str(portnum) if portnum is not None else None,
                hops=hops,
            )

        packet_summary = _build_packet_summary_helper(
            packet=packet,
            decoded=decoded,
            from_id=from_id,
            to_id=to_id,
            packet_id=packet_id,
            rx_time=rx_time,
            hops=hops,
            reply_id=reply_id,
            emoji_glyph=emoji_glyph,
            emoji_codepoint=emoji_codepoint,
            is_reaction=is_reaction,
            packet_position=packet_position,
            packet_battery=packet_battery,
            utc_now_fn=_utc_now,
            format_epoch_fn=_format_epoch,
            to_int_fn=_to_int,
        )
        packet_summary["live"] = include_live_count

        packet_entry = {
            "summary": packet_summary,
            "packet": _to_jsonable(packet),
        }
        self.recent_packets.append(packet_entry)
        if self._history_store is not None and include_live_count:
            self._history_store.save_packet(packet_entry)

        chat_entry = _build_chat_entry_from_packet_helper(
            packet=packet,
            decoded=decoded,
            from_id=from_id,
            to_id=to_id,
            packet_id=packet_id,
            hops=hops,
            reply_id=reply_id,
            emoji_glyph=emoji_glyph,
            emoji_codepoint=emoji_codepoint,
            is_reaction=is_reaction,
            utc_now_fn=_utc_now,
            format_epoch_fn=_format_epoch,
        )
        if chat_entry is not None:
            self.recent_chat.append(chat_entry)
            if self._history_store is not None and include_live_count:
                self._history_store.save_chat(chat_entry)

        self._expire_pending_deliveries_unlocked()

    def snapshot(self, nodes_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        with self._lock:
            self._expire_pending_deliveries_unlocked()
            edge_rows, real_edge_count = _build_edge_snapshot_rows_helper(
                session_edges=self.edges,
                historical_edges=self._historical_edges,
                nodes_by_id=nodes_by_id,
                min_real_link_count=MIN_REAL_LINK_COUNT,
                format_epoch_fn=_format_epoch,
            )
            port_rows = [
                {"portnum": portnum, "count": count}
                for portnum, count in self.port_counts.most_common()
            ]
            recent_packets = list(self.recent_packets)
            recent_chat = list(self.recent_chat)
            live_packet_count = self.live_packet_count

        return {
            "live_packet_count": live_packet_count,
            "real_edge_count": real_edge_count,
            "edges": edge_rows,
            "port_counts": port_rows,
            "recent_packets": recent_packets,
            "recent_chat": recent_chat,
        }


def seed_tracker_from_node_db(tracker: DashboardTracker, iface: Any) -> None:
    for _num, node in _safe_nodes_items(iface, retries=3, sleep_seconds=0.01):
        if not isinstance(node, dict):
            continue
        last_packet = node.get("lastReceived")
        if isinstance(last_packet, dict):
            tracker.seed_packet(last_packet, iface)
