import argparse
import json
import os
import sqlite3
import threading
import time
from collections import Counter, deque
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple

try:
    import meshtastic
except Exception:
    meshtastic = None
from mesh_connection import add_mesh_connection_args, mesh_target_label, open_mesh_interface
try:
    from meshdash import __version__ as _package_version
except Exception:
    _package_version = "0.0.0"
from meshdash.helpers import (
    calculate_hops as _calculate_hops,
    emoji_from_codepoint as _emoji_from_codepoint,
    extract_packet_battery_level as _extract_packet_battery_level,
    extract_packet_position as _extract_packet_position,
    extract_emoji_codepoint as _extract_emoji_codepoint,
    extract_position_fields as _extract_position_fields,
    extract_reply_id as _extract_reply_id,
    format_epoch as _format_epoch,
    is_sensitive_key as _is_sensitive_key_helper,
    message_to_dict as _message_to_dict_helper,
    normalize_single_emoji as _normalize_single_emoji,
    redact_secrets as _redact_secrets_helper,
    safe_json_loads as _safe_json_loads,
    to_jsonable as _to_jsonable_helper,
    to_float as _to_float,
    to_int as _to_int,
)
from meshdash.chat import (
    build_local_chat_entry as _build_local_chat_entry,
    chat_message_id as _chat_message_id_helper,
    expire_pending_deliveries as _expire_pending_deliveries_helper,
    extract_routing_delivery_update as _extract_routing_delivery_update_helper,
    set_delivery_state as _set_delivery_state_helper,
)
from meshdash.revision import (
    detect_git_commit as _detect_git_commit_helper,
    revision_info as _build_revision_info,
    sanitize_revision_token as _sanitize_revision_token_helper,
)
from meshdash.nodes import (
    extract_position as _extract_position_helper,
    get_local_node_id as _get_local_node_id_helper,
    get_local_node_num as _get_local_node_num_helper,
    get_node_id_from_num as _get_node_id_from_num_helper,
    parse_utc_text_to_unix as _parse_utc_text_to_unix_helper,
    safe_nodes_items as _safe_nodes_items_helper,
    utc_now as _utc_now_helper,
)
from meshdash.runtime import (
    apply_default_gateway as _apply_default_gateway_helper,
    guess_lan_ipv4 as _guess_lan_ipv4_helper,
)
from meshdash.state import (
    build_state as _build_state_helper,
    collect_local_state as _collect_local_state_helper,
    collect_nodes as _collect_nodes_helper,
)
from meshdash.services import (
    build_node_history_loader as _build_node_history_loader,
    build_online_activity_loader as _build_online_activity_loader,
    send_chat_message as _send_chat_message_helper,
)
from meshdash.html import render_html as _render_html_helper
from meshdash.http_api import make_http_handler as _make_http_handler_helper
try:
    from pubsub import pub
except Exception:
    pub = None

try:
    from meshtastic.protobuf import mesh_pb2, portnums_pb2
except Exception:
    mesh_pb2 = None
    portnums_pb2 = None


DEFAULT_MESH_PORT = "/dev/ttyACM0"
DEFAULT_GATEWAY_HOST = "192.168.1.241"
DEFAULT_GATEWAY_PORT = 4403
DEFAULT_HTTP_HOST = "0.0.0.0"
DEFAULT_HTTP_PORT = 8877
DEFAULT_REFRESH_MS = 3000
DEFAULT_PACKET_LIMIT = 250
DEFAULT_HISTORY_DB = "mesh_dashboard_history.sqlite3"
DEFAULT_HISTORY_MAX_ROWS = 5000
DEFAULT_HISTORY_RETENTION_DAYS = 7
DEFAULT_HISTORY_EVENT_MAX_ROWS = 200000
DEFAULT_HISTORY_EVENT_RETENTION_DAYS = 30
DEFAULT_HISTORY_ROLLUP_RETENTION_DAYS = 365
DEFAULT_NODE_HISTORY_HOURS = 72
DEFAULT_NODE_HISTORY_MAX_POINTS = 1440
DEFAULT_CHAT_MAX_BYTES = 220
DEFAULT_CHAT_DELIVERY_TIMEOUT_SECONDS = 90
MIN_REAL_LINK_COUNT = 2
DEFAULT_APP_VERSION = _package_version or "0.1.0"
UNKNOWN_GIT_COMMIT = "nogit"

SENSITIVE_FIELD_NAMES = {
    "private_key",
    "wifi_psk",
    "password",
    "psk",
    "session_passkey",
    "admin_key",
}


def _utc_now() -> str:
    return _utc_now_helper()


def _parse_utc_text_to_unix(value: Any) -> Optional[int]:
    return _parse_utc_text_to_unix_helper(value)


def _sanitize_revision_token(raw: Any, fallback: str) -> str:
    return _sanitize_revision_token_helper(raw, fallback)


def _detect_git_commit() -> Optional[str]:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cwd = os.getcwd()
    explicit = os.environ.get("MESH_DASH_GIT_COMMIT", "")
    return _detect_git_commit_helper(
        explicit_commit=explicit,
        script_dir=script_dir,
        cwd=cwd,
        unknown_git_commit=UNKNOWN_GIT_COMMIT,
        sanitize_token=_sanitize_revision_token,
    )


def _revision_info() -> Dict[str, str]:
    version_raw = os.environ.get("MESH_DASH_VERSION", DEFAULT_APP_VERSION)
    return _build_revision_info(
        version_raw=version_raw,
        default_version=DEFAULT_APP_VERSION,
        unknown_git_commit=UNKNOWN_GIT_COMMIT,
        detect_commit=_detect_git_commit,
        sanitize_token=_sanitize_revision_token,
    )


def _send_emoji_reaction_packet(
    iface: Any,
    destination_id: str,
    channel_index: int,
    reply_id: int,
    emoji_codepoint: int,
    emoji_text: str,
    want_ack: bool = False,
) -> Any:
    if mesh_pb2 is None or portnums_pb2 is None:
        raise RuntimeError("Meshtastic protobuf modules are unavailable for emoji reactions")
    if not hasattr(iface, "_sendPacket"):
        raise RuntimeError("Meshtastic interface does not support low-level packet send")

    packet = mesh_pb2.MeshPacket()
    packet.channel = int(channel_index)
    packet.decoded.portnum = portnums_pb2.PortNum.TEXT_MESSAGE_APP
    packet.decoded.reply_id = int(reply_id)
    packet.decoded.emoji = int(emoji_codepoint)
    packet.decoded.payload = str(emoji_text or "").encode("utf-8")
    return iface._sendPacket(packet, destinationId=destination_id, wantAck=bool(want_ack))


def _guess_lan_ipv4() -> Optional[str]:
    return _guess_lan_ipv4_helper()


def _get_local_node_num(iface: Any) -> Optional[int]:
    return _get_local_node_num_helper(iface, to_jsonable_fn=_to_jsonable, to_int_fn=_to_int)


def _get_local_node_id(iface: Any) -> str:
    broadcast_num = getattr(meshtastic, "BROADCAST_NUM", None) if meshtastic is not None else None
    return _get_local_node_id_helper(
        iface,
        broadcast_num=broadcast_num,
        to_jsonable_fn=_to_jsonable,
        to_int_fn=_to_int,
    )


def _apply_default_gateway(args: argparse.Namespace) -> None:
    _apply_default_gateway_helper(args, default_mesh_port=DEFAULT_MESH_PORT)


def _message_to_dict(value: Any) -> Any:
    return _message_to_dict_helper(value)


def _to_jsonable(value: Any, depth: int = 0) -> Any:
    return _to_jsonable_helper(value, depth=depth)


def _is_sensitive_key(key: str) -> bool:
    return _is_sensitive_key_helper(key, SENSITIVE_FIELD_NAMES)


def _redact_secrets(value: Any, parent_key: Optional[str] = None) -> Any:
    return _redact_secrets_helper(value, SENSITIVE_FIELD_NAMES, parent_key=parent_key)


def _get_node_id_from_num(iface: Any, node_num: Any) -> Optional[str]:
    broadcast_num = getattr(meshtastic, "BROADCAST_NUM", None) if meshtastic is not None else None
    return _get_node_id_from_num_helper(
        iface,
        node_num,
        broadcast_num=broadcast_num,
        to_int_fn=_to_int,
    )


def _extract_position(node_info: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    return _extract_position_helper(node_info, extract_position_fields_fn=_extract_position_fields)


def _safe_nodes_items(iface: Any) -> list[Tuple[Any, Any]]:
    return _safe_nodes_items_helper(iface, retries=3, sleep_seconds=0.01)


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
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS packets (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              created_unix INTEGER NOT NULL,
              summary_json TEXT NOT NULL,
              packet_json TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              created_unix INTEGER NOT NULL,
              message_json TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS connections (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              from_id TEXT NOT NULL,
              to_id TEXT NOT NULL,
              first_seen_unix INTEGER NOT NULL,
              last_seen_unix INTEGER NOT NULL,
              seen_count INTEGER NOT NULL,
              portnums_json TEXT NOT NULL,
              last_hops INTEGER,
              hops_sum INTEGER NOT NULL DEFAULT 0,
              hops_count INTEGER NOT NULL DEFAULT 0,
              UNIQUE(from_id, to_id)
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS packet_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              created_unix INTEGER NOT NULL,
              from_id TEXT,
              to_id TEXT,
              portnum TEXT,
              rx_snr REAL,
              rx_rssi REAL,
              hops INTEGER,
              hop_start INTEGER,
              hop_limit INTEGER,
              channel TEXT,
              want_ack INTEGER,
              priority TEXT,
              summary_json TEXT
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS node_positions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              created_unix INTEGER NOT NULL,
              node_id TEXT NOT NULL,
              lat REAL NOT NULL,
              lon REAL NOT NULL,
              altitude REAL,
              sats_in_view INTEGER
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS node_capabilities (
              node_id TEXT PRIMARY KEY,
              last_seen_unix INTEGER NOT NULL,
              has_position INTEGER NOT NULL DEFAULT 0,
              last_position_unix INTEGER,
              last_hops INTEGER,
              battery_level INTEGER,
              battery_updated_unix INTEGER
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS node_metrics_1m (
              bucket_unix INTEGER NOT NULL,
              node_id TEXT NOT NULL,
              packet_count INTEGER NOT NULL,
              snr_sum REAL NOT NULL,
              snr_count INTEGER NOT NULL,
              snr_min REAL,
              snr_max REAL,
              rssi_sum REAL NOT NULL,
              rssi_count INTEGER NOT NULL,
              rssi_min REAL,
              rssi_max REAL,
              hops_sum INTEGER NOT NULL,
              hops_count INTEGER NOT NULL,
              hops_min INTEGER,
              hops_max INTEGER,
              last_seen_unix INTEGER NOT NULL,
              PRIMARY KEY(bucket_unix, node_id)
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS link_metrics_1m (
              bucket_unix INTEGER NOT NULL,
              from_id TEXT NOT NULL,
              to_id TEXT NOT NULL,
              packet_count INTEGER NOT NULL,
              snr_sum REAL NOT NULL,
              snr_count INTEGER NOT NULL,
              snr_min REAL,
              snr_max REAL,
              rssi_sum REAL NOT NULL,
              rssi_count INTEGER NOT NULL,
              rssi_min REAL,
              rssi_max REAL,
              hops_sum INTEGER NOT NULL,
              hops_count INTEGER NOT NULL,
              hops_min INTEGER,
              hops_max INTEGER,
              last_seen_unix INTEGER NOT NULL,
              PRIMARY KEY(bucket_unix, from_id, to_id)
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_packets_created_unix ON packets(created_unix)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_created_unix ON chat(created_unix)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_connections_last_seen_unix ON connections(last_seen_unix)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_packet_events_created_unix ON packet_events(created_unix)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_packet_events_from_id ON packet_events(from_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_packet_events_to_id ON packet_events(to_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_packet_events_portnum ON packet_events(portnum)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_node_positions_created_unix ON node_positions(created_unix)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_node_positions_node_id_created_unix ON node_positions(node_id, created_unix)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_node_capabilities_last_seen_unix ON node_capabilities(last_seen_unix)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_node_metrics_1m_last_seen_unix ON node_metrics_1m(last_seen_unix)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_link_metrics_1m_last_seen_unix ON link_metrics_1m(last_seen_unix)"
        )

    def _maybe_backfill_node_capabilities_unlocked(self) -> None:
        existing = self._conn.execute("SELECT COUNT(*) FROM node_capabilities").fetchone()
        if existing and int(existing[0] or 0) > 0:
            return

        merged: Dict[str, Dict[str, Any]] = {}

        metric_rows = self._conn.execute(
            """
            SELECT node_id, MAX(last_seen_unix)
            FROM node_metrics_1m
            GROUP BY node_id
            """
        ).fetchall()
        for node_id, last_seen_unix in metric_rows:
            clean_node_id = str(node_id or "").strip()
            seen = _to_int(last_seen_unix)
            if not clean_node_id or seen is None:
                continue
            merged.setdefault(clean_node_id, {})
            merged[clean_node_id]["last_seen_unix"] = seen

        position_rows = self._conn.execute(
            """
            SELECT node_id, MAX(created_unix)
            FROM node_positions
            GROUP BY node_id
            """
        ).fetchall()
        for node_id, last_position_unix in position_rows:
            clean_node_id = str(node_id or "").strip()
            pos_unix = _to_int(last_position_unix)
            if not clean_node_id or pos_unix is None:
                continue
            node = merged.setdefault(clean_node_id, {})
            node["has_position"] = True
            node["last_position_unix"] = pos_unix
            node["last_seen_unix"] = max(_to_int(node.get("last_seen_unix")) or pos_unix, pos_unix)

        hop_rows = self._conn.execute(
            """
            SELECT events.from_id, events.hops, events.created_unix
            FROM packet_events AS events
            JOIN (
              SELECT from_id, MAX(id) AS max_id
              FROM packet_events
              WHERE from_id IS NOT NULL AND hops IS NOT NULL
              GROUP BY from_id
            ) AS latest
              ON latest.from_id = events.from_id AND latest.max_id = events.id
            """
        ).fetchall()
        for node_id, last_hops, hop_seen_unix in hop_rows:
            clean_node_id = str(node_id or "").strip()
            hops = _to_int(last_hops)
            seen = _to_int(hop_seen_unix)
            if not clean_node_id:
                continue
            node = merged.setdefault(clean_node_id, {})
            if hops is not None and hops >= 0:
                node["last_hops"] = hops
            if seen is not None:
                node["last_seen_unix"] = max(_to_int(node.get("last_seen_unix")) or seen, seen)

        for node_id, values in merged.items():
            seen = _to_int(values.get("last_seen_unix"))
            if seen is None or seen <= 0:
                continue
            has_position = 1 if values.get("has_position") else 0
            self._conn.execute(
                """
                INSERT OR REPLACE INTO node_capabilities(
                  node_id, last_seen_unix, has_position, last_position_unix,
                  last_hops, battery_level, battery_updated_unix
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node_id,
                    seen,
                    has_position,
                    _to_int(values.get("last_position_unix")),
                    _to_int(values.get("last_hops")),
                    None,
                    None,
                ),
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _prune_unlocked(self) -> None:
        if self.retention_seconds > 0:
            cutoff = int(time.time()) - self.retention_seconds
            self._conn.execute("DELETE FROM packets WHERE created_unix < ?", (cutoff,))
            self._conn.execute("DELETE FROM chat WHERE created_unix < ?", (cutoff,))
            self._conn.execute("DELETE FROM connections WHERE last_seen_unix < ?", (cutoff,))
        if self.event_retention_seconds > 0:
            event_cutoff = int(time.time()) - self.event_retention_seconds
            self._conn.execute("DELETE FROM packet_events WHERE created_unix < ?", (event_cutoff,))
            self._conn.execute("DELETE FROM node_positions WHERE created_unix < ?", (event_cutoff,))
            self._conn.execute("DELETE FROM node_capabilities WHERE last_seen_unix < ?", (event_cutoff,))
        if self.rollup_retention_seconds > 0:
            rollup_cutoff = int(time.time()) - self.rollup_retention_seconds
            self._conn.execute("DELETE FROM node_metrics_1m WHERE last_seen_unix < ?", (rollup_cutoff,))
            self._conn.execute("DELETE FROM link_metrics_1m WHERE last_seen_unix < ?", (rollup_cutoff,))

        if self.max_rows > 0:
            self._conn.execute(
                """
                DELETE FROM packets
                WHERE id <= (SELECT COALESCE(MAX(id), 0) - ? FROM packets)
                """,
                (self.max_rows,),
            )
            self._conn.execute(
                """
                DELETE FROM chat
                WHERE id <= (SELECT COALESCE(MAX(id), 0) - ? FROM chat)
                """,
                (self.max_rows,),
            )
            self._conn.execute(
                """
                DELETE FROM connections
                WHERE id NOT IN (
                  SELECT id FROM connections
                  ORDER BY last_seen_unix DESC
                  LIMIT ?
                )
                """,
                (self.max_rows,),
            )
        if self.event_max_rows > 0:
            self._conn.execute(
                """
                DELETE FROM packet_events
                WHERE id <= (SELECT COALESCE(MAX(id), 0) - ? FROM packet_events)
                """,
                (self.event_max_rows,),
            )
            self._conn.execute(
                """
                DELETE FROM node_positions
                WHERE id <= (SELECT COALESCE(MAX(id), 0) - ? FROM node_positions)
                """,
                (self.event_max_rows,),
            )

    def _maybe_prune_unlocked(self) -> None:
        self._writes_since_prune += 1
        if self._writes_since_prune < 50:
            return
        self._writes_since_prune = 0
        self._prune_unlocked()

    def load_recent_packets(self, limit: int) -> list[Dict[str, Any]]:
        out: list[Dict[str, Any]] = []
        with self._lock:
            rows = self._conn.execute(
                "SELECT summary_json, packet_json FROM packets ORDER BY id DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()

        for summary_json, packet_json in reversed(rows):
            summary = _safe_json_loads(summary_json, {})
            if not isinstance(summary, dict):
                continue
            packet = _safe_json_loads(packet_json, {})
            out.append({"summary": summary, "packet": packet})
        return out

    def load_recent_chat(self, limit: int) -> list[Dict[str, Any]]:
        out: list[Dict[str, Any]] = []
        with self._lock:
            rows = self._conn.execute(
                "SELECT message_json FROM chat ORDER BY id DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()

        for (message_json,) in reversed(rows):
            entry = _safe_json_loads(message_json, {})
            if isinstance(entry, dict):
                out.append(entry)
        return out

    def load_connections(self) -> list[Dict[str, Any]]:
        out: list[Dict[str, Any]] = []
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT from_id, to_id, first_seen_unix, last_seen_unix, seen_count,
                       portnums_json, last_hops, hops_sum, hops_count
                FROM connections
                ORDER BY last_seen_unix DESC
                """
            ).fetchall()

        for row in rows:
            from_id, to_id, first_seen_unix, last_seen_unix, seen_count, portnums_json, last_hops, hops_sum, hops_count = row
            portnums = _safe_json_loads(portnums_json, [])
            if not isinstance(portnums, list):
                portnums = []
            out.append(
                {
                    "from": str(from_id),
                    "to": str(to_id),
                    "count": int(seen_count),
                    "first_rx_time": _to_int(first_seen_unix),
                    "last_rx_time": _to_int(last_seen_unix),
                    "portnums": [str(p) for p in portnums if p is not None],
                    "last_hops": _to_int(last_hops),
                    "hops_sum": _to_int(hops_sum) or 0,
                    "hops_count": _to_int(hops_count) or 0,
                }
            )
        return out

    def load_node_history(self, node_id: str, window_hours: int, max_points: int) -> Dict[str, Any]:
        clean_node_id = str(node_id or "").strip()
        if not clean_node_id:
            return {
                "node_id": "",
                "window_hours": max(1, int(window_hours)),
                "points": [],
                "positions": [],
                "summary": {},
            }

        hours = max(1, int(window_hours))
        limit = max(20, min(10000, int(max_points)))
        cutoff = int(time.time()) - (hours * 3600)

        with self._lock:
            rows = self._conn.execute(
                """
                SELECT bucket_unix, packet_count,
                       snr_sum, snr_count, snr_min, snr_max,
                       rssi_sum, rssi_count, rssi_min, rssi_max,
                       hops_sum, hops_count, hops_min, hops_max,
                       last_seen_unix
                FROM node_metrics_1m
                WHERE node_id = ? AND bucket_unix >= ?
                ORDER BY bucket_unix DESC
                LIMIT ?
                """,
                (clean_node_id, cutoff, limit),
            ).fetchall()
            position_rows = self._conn.execute(
                """
                SELECT created_unix, lat, lon, altitude, sats_in_view
                FROM node_positions
                WHERE node_id = ? AND created_unix >= ?
                ORDER BY created_unix DESC
                LIMIT ?
                """,
                (clean_node_id, cutoff, limit),
            ).fetchall()

        points: list[Dict[str, Any]] = []
        positions: list[Dict[str, Any]] = []
        total_packets = 0
        snr_min_all: Optional[float] = None
        snr_max_all: Optional[float] = None
        rssi_min_all: Optional[float] = None
        rssi_max_all: Optional[float] = None
        first_bucket: Optional[int] = None
        last_bucket: Optional[int] = None
        last_seen: Optional[int] = None
        trail_start: Optional[int] = None
        trail_end: Optional[int] = None

        for row in reversed(rows):
            (
                bucket_unix,
                packet_count,
                snr_sum,
                snr_count,
                snr_min,
                snr_max,
                rssi_sum,
                rssi_count,
                rssi_min,
                rssi_max,
                hops_sum,
                hops_count,
                hops_min,
                hops_max,
                last_seen_unix,
            ) = row

            bucket = _to_int(bucket_unix)
            if bucket is None:
                continue

            packets = _to_int(packet_count) or 0
            total_packets += packets
            first_bucket = bucket if first_bucket is None else min(first_bucket, bucket)
            last_bucket = bucket if last_bucket is None else max(last_bucket, bucket)
            seen_val = _to_int(last_seen_unix)
            if seen_val is not None:
                last_seen = seen_val if last_seen is None else max(last_seen, seen_val)

            snr_count_i = _to_int(snr_count) or 0
            rssi_count_i = _to_int(rssi_count) or 0
            hops_count_i = _to_int(hops_count) or 0
            snr_avg = (_to_float(snr_sum) or 0.0) / snr_count_i if snr_count_i > 0 else None
            rssi_avg = (_to_float(rssi_sum) or 0.0) / rssi_count_i if rssi_count_i > 0 else None
            hops_avg = (_to_float(hops_sum) or 0.0) / hops_count_i if hops_count_i > 0 else None

            snr_min_v = _to_float(snr_min)
            snr_max_v = _to_float(snr_max)
            rssi_min_v = _to_float(rssi_min)
            rssi_max_v = _to_float(rssi_max)

            if snr_min_v is not None:
                snr_min_all = snr_min_v if snr_min_all is None else min(snr_min_all, snr_min_v)
            if snr_max_v is not None:
                snr_max_all = snr_max_v if snr_max_all is None else max(snr_max_all, snr_max_v)
            if rssi_min_v is not None:
                rssi_min_all = rssi_min_v if rssi_min_all is None else min(rssi_min_all, rssi_min_v)
            if rssi_max_v is not None:
                rssi_max_all = rssi_max_v if rssi_max_all is None else max(rssi_max_all, rssi_max_v)

            points.append(
                {
                    "bucket_unix": bucket,
                    "bucket_time": _format_epoch(bucket),
                    "packet_count": packets,
                    "avg_snr": round(snr_avg, 2) if snr_avg is not None else None,
                    "min_snr": snr_min_v,
                    "max_snr": snr_max_v,
                    "avg_rssi": round(rssi_avg, 2) if rssi_avg is not None else None,
                    "min_rssi": rssi_min_v,
                    "max_rssi": rssi_max_v,
                    "avg_hops": round(hops_avg, 2) if hops_avg is not None else None,
                    "min_hops": _to_int(hops_min),
                    "max_hops": _to_int(hops_max),
                    "hops_samples": hops_count_i,
                    "last_seen": _format_epoch(last_seen_unix),
                }
            )

        for created_unix, lat, lon, altitude, sats_in_view in reversed(position_rows):
            point_unix = _to_int(created_unix)
            lat_f = _to_float(lat)
            lon_f = _to_float(lon)
            if point_unix is None or lat_f is None or lon_f is None:
                continue
            if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
                continue
            if lat_f == 0.0 and lon_f == 0.0:
                continue
            trail_start = point_unix if trail_start is None else min(trail_start, point_unix)
            trail_end = point_unix if trail_end is None else max(trail_end, point_unix)
            positions.append(
                {
                    "time_unix": point_unix,
                    "time": _format_epoch(point_unix),
                    "lat": lat_f,
                    "lon": lon_f,
                    "altitude": _to_float(altitude),
                    "sats_in_view": _to_int(sats_in_view),
                }
            )

        return {
            "node_id": clean_node_id,
            "window_hours": hours,
            "points": points,
            "positions": positions,
            "summary": {
                "total_packets": total_packets,
                "points": len(points),
                "first_bucket": _format_epoch(first_bucket),
                "last_bucket": _format_epoch(last_bucket),
                "last_seen": _format_epoch(last_seen),
                "snr_min": snr_min_all,
                "snr_max": snr_max_all,
                "rssi_min": rssi_min_all,
                "rssi_max": rssi_max_all,
                "trail_points": len(positions),
                "trail_start": _format_epoch(trail_start),
                "trail_end": _format_epoch(trail_end),
            },
        }

    def load_online_activity(self, window_hours: int) -> Dict[str, Any]:
        hours = max(1, min(24 * 365, int(window_hours)))
        cutoff = int(time.time()) - (hours * 3600)

        with self._lock:
            rows = self._conn.execute(
                """
                SELECT bucket_unix - (bucket_unix % 3600) AS hour_bucket,
                       COUNT(DISTINCT node_id) AS online_nodes
                FROM node_metrics_1m
                WHERE bucket_unix >= ?
                GROUP BY hour_bucket
                ORDER BY hour_bucket ASC
                """,
                (cutoff,),
            ).fetchall()
            distinct_row = self._conn.execute(
                "SELECT COUNT(DISTINCT node_id) FROM node_metrics_1m WHERE bucket_unix >= ?",
                (cutoff,),
            ).fetchone()

        timezone_label = datetime.now().astimezone().tzname() or "local"
        points: list[Dict[str, Any]] = []
        by_hour: Dict[int, list[int]] = {hour: [] for hour in range(24)}
        total_online = 0
        max_online = 0
        first_bucket: Optional[int] = None
        last_bucket: Optional[int] = None

        for raw_bucket, raw_online in rows:
            bucket = _to_int(raw_bucket)
            if bucket is None:
                continue
            online_nodes = max(0, _to_int(raw_online) or 0)
            local_dt = datetime.fromtimestamp(bucket)
            hour_local = local_dt.hour
            by_hour.setdefault(hour_local, []).append(online_nodes)
            total_online += online_nodes
            max_online = max(max_online, online_nodes)
            first_bucket = bucket if first_bucket is None else min(first_bucket, bucket)
            last_bucket = bucket if last_bucket is None else max(last_bucket, bucket)
            points.append(
                {
                    "bucket_unix": bucket,
                    "bucket_time": _format_epoch(bucket),
                    "bucket_local": local_dt.strftime("%Y-%m-%d %H:00"),
                    "hour_local": hour_local,
                    "hour_label": f"{hour_local:02d}:00",
                    "online_nodes": online_nodes,
                }
            )

        best_hour: Optional[int] = None
        best_avg: Optional[float] = None
        hourly_profile: list[Dict[str, Any]] = []
        for hour in range(24):
            samples = by_hour.get(hour, [])
            sample_count = len(samples)
            avg_online = (sum(samples) / sample_count) if sample_count > 0 else None
            peak_online = max(samples) if sample_count > 0 else 0
            if avg_online is not None:
                if best_avg is None or avg_online > best_avg + 1e-9:
                    best_hour = hour
                    best_avg = avg_online
                elif best_hour is not None and abs(avg_online - best_avg) <= 1e-9 and hour < best_hour:
                    best_hour = hour
            hourly_profile.append(
                {
                    "hour": hour,
                    "label": f"{hour:02d}:00",
                    "avg_online_nodes": round(avg_online, 2) if avg_online is not None else None,
                    "sample_hours": sample_count,
                    "peak_online_nodes": peak_online,
                }
            )

        sample_hours = len(points)
        avg_online_nodes = (total_online / sample_hours) if sample_hours > 0 else None
        distinct_nodes = int((distinct_row[0] if distinct_row else 0) or 0)

        return {
            "window_hours": hours,
            "timezone": "local",
            "timezone_label": timezone_label,
            "points": points,
            "hourly_profile": hourly_profile,
            "summary": {
                "sample_hours": sample_hours,
                "distinct_nodes": distinct_nodes,
                "max_online_nodes": max_online,
                "avg_online_nodes": round(avg_online_nodes, 2) if avg_online_nodes is not None else None,
                "best_hour": best_hour,
                "best_hour_label": f"{best_hour:02d}:00" if best_hour is not None else None,
                "best_hour_avg_online_nodes": round(best_avg, 2) if best_avg is not None else None,
                "window_start": _format_epoch(first_bucket),
                "window_end": _format_epoch(last_bucket),
            },
        }

    def load_node_saved_counts(self) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT node_id,
                       SUM(packet_count) AS saved_packets,
                       COUNT(*) AS saved_points,
                       MAX(last_seen_unix) AS saved_last_seen_unix
                FROM node_metrics_1m
                GROUP BY node_id
                """
            ).fetchall()

        for node_id, saved_packets, saved_points, saved_last_seen_unix in rows:
            clean_node_id = str(node_id or "").strip()
            if not clean_node_id:
                continue
            out[clean_node_id] = {
                "saved_packets": int(saved_packets or 0),
                "saved_points": int(saved_points or 0),
                "saved_last_seen": _format_epoch(saved_last_seen_unix),
            }
        return out

    def load_node_capabilities(self) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT node_id, last_seen_unix, has_position, last_position_unix,
                       last_hops, battery_level, battery_updated_unix
                FROM node_capabilities
                ORDER BY last_seen_unix DESC
                """
            ).fetchall()

        for (
            node_id,
            last_seen_unix,
            has_position,
            last_position_unix,
            last_hops,
            battery_level,
            battery_updated_unix,
        ) in rows:
            clean_node_id = str(node_id or "").strip()
            if not clean_node_id:
                continue
            out[clean_node_id] = {
                "last_seen_unix": _to_int(last_seen_unix),
                "last_seen": _format_epoch(last_seen_unix),
                "has_position": bool(_to_int(has_position)),
                "last_position_unix": _to_int(last_position_unix),
                "last_position_time": _format_epoch(last_position_unix),
                "last_hops": _to_int(last_hops),
                "battery_level": _to_int(battery_level),
                "battery_updated_unix": _to_int(battery_updated_unix),
                "battery_updated_time": _format_epoch(battery_updated_unix),
            }
        return out

    def save_connection_event(
        self,
        from_id: str,
        to_id: str,
        rx_time: Optional[int],
        portnum: Optional[str],
        hops: Optional[int],
    ) -> None:
        event_unix = rx_time if isinstance(rx_time, int) and rx_time > 0 else int(time.time())
        clean_port = str(portnum) if portnum is not None else None
        clean_hops = hops if isinstance(hops, int) and hops >= 0 else None

        with self._lock:
            row = self._conn.execute(
                """
                SELECT first_seen_unix, last_seen_unix, seen_count, portnums_json, last_hops, hops_sum, hops_count
                FROM connections
                WHERE from_id = ? AND to_id = ?
                """,
                (from_id, to_id),
            ).fetchone()

            if row is None:
                ports: set[str] = set()
                if clean_port:
                    ports.add(clean_port)
                self._conn.execute(
                    """
                    INSERT INTO connections(
                      from_id, to_id, first_seen_unix, last_seen_unix, seen_count,
                      portnums_json, last_hops, hops_sum, hops_count
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        from_id,
                        to_id,
                        event_unix,
                        event_unix,
                        1,
                        json.dumps(sorted(ports), separators=(",", ":")),
                        clean_hops,
                        clean_hops if clean_hops is not None else 0,
                        1 if clean_hops is not None else 0,
                    ),
                )
            else:
                first_seen_unix, last_seen_unix, seen_count, portnums_json, last_hops, hops_sum, hops_count = row
                ports = _safe_json_loads(portnums_json, [])
                if not isinstance(ports, list):
                    ports = []
                port_set = {str(p) for p in ports if p is not None}
                if clean_port:
                    port_set.add(clean_port)

                merged_first = min(_to_int(first_seen_unix) or event_unix, event_unix)
                merged_last = max(_to_int(last_seen_unix) or event_unix, event_unix)
                merged_count = (_to_int(seen_count) or 0) + 1

                merged_hops_sum = _to_int(hops_sum) or 0
                merged_hops_count = _to_int(hops_count) or 0
                merged_last_hops = _to_int(last_hops)
                if clean_hops is not None:
                    merged_hops_sum += clean_hops
                    merged_hops_count += 1
                    merged_last_hops = clean_hops

                self._conn.execute(
                    """
                    UPDATE connections
                    SET first_seen_unix = ?, last_seen_unix = ?, seen_count = ?,
                        portnums_json = ?, last_hops = ?, hops_sum = ?, hops_count = ?
                    WHERE from_id = ? AND to_id = ?
                    """,
                    (
                        merged_first,
                        merged_last,
                        merged_count,
                        json.dumps(sorted(port_set), separators=(",", ":")),
                        merged_last_hops,
                        merged_hops_sum,
                        merged_hops_count,
                        from_id,
                        to_id,
                    ),
                )

            self._maybe_prune_unlocked()
            self._conn.commit()

    @staticmethod
    def _merge_metric(
        sum_value: Any,
        count_value: Any,
        min_value: Any,
        max_value: Any,
        sample: Optional[float],
    ) -> Tuple[float, int, Optional[float], Optional[float]]:
        merged_sum = float(sum_value or 0.0)
        merged_count = int(count_value or 0)
        merged_min = _to_float(min_value)
        merged_max = _to_float(max_value)

        if sample is None:
            return merged_sum, merged_count, merged_min, merged_max

        merged_sum += sample
        merged_count += 1
        merged_min = sample if merged_min is None else min(merged_min, sample)
        merged_max = sample if merged_max is None else max(merged_max, sample)
        return merged_sum, merged_count, merged_min, merged_max

    @staticmethod
    def _bucket_minute(epoch_seconds: int) -> int:
        return int(epoch_seconds) - (int(epoch_seconds) % 60)

    @staticmethod
    def _clean_node_id(node_id: Any) -> Optional[str]:
        value = str(node_id or "").strip()
        if not value or value in ("Unknown", "n/a", "^all"):
            return None
        return value

    def _save_node_position_unlocked(self, node_id: str, event_unix: int, position_data: Any) -> None:
        coords = _extract_position_fields(position_data)
        if coords is None:
            return

        altitude: Optional[float] = None
        sats: Optional[int] = None
        if isinstance(position_data, dict):
            altitude = _to_float(position_data.get("altitude"))
            if altitude is None:
                altitude = _to_float(position_data.get("altitude_m"))
            if altitude is None:
                altitude = _to_float(position_data.get("altitudeM"))

            sats = _to_int(position_data.get("sats_in_view"))
            if sats is None:
                sats = _to_int(position_data.get("satsInView"))
            if sats is None:
                sats = _to_int(position_data.get("satellites"))

        latest = self._conn.execute(
            """
            SELECT created_unix, lat, lon
            FROM node_positions
            WHERE node_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (node_id,),
        ).fetchone()
        if latest is not None:
            latest_unix, latest_lat, latest_lon = latest
            latest_unix_i = _to_int(latest_unix)
            latest_lat_f = _to_float(latest_lat)
            latest_lon_f = _to_float(latest_lon)
            if (
                latest_unix_i is not None
                and latest_lat_f is not None
                and latest_lon_f is not None
                and abs(coords[0] - latest_lat_f) < 1e-7
                and abs(coords[1] - latest_lon_f) < 1e-7
                and abs(event_unix - latest_unix_i) < 30
            ):
                return

        self._conn.execute(
            """
            INSERT INTO node_positions(created_unix, node_id, lat, lon, altitude, sats_in_view)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                event_unix,
                node_id,
                coords[0],
                coords[1],
                altitude,
                sats if sats is not None and sats >= 0 else None,
            ),
        )

    def _upsert_node_capability_unlocked(
        self,
        node_id: str,
        event_unix: int,
        has_position: bool,
        last_hops: Optional[int],
        battery_level: Optional[int],
    ) -> None:
        clean_hops = last_hops if isinstance(last_hops, int) and last_hops >= 0 else None
        clean_battery = battery_level if isinstance(battery_level, int) and 0 <= battery_level <= 100 else None

        row = self._conn.execute(
            """
            SELECT last_seen_unix, has_position, last_position_unix,
                   last_hops, battery_level, battery_updated_unix
            FROM node_capabilities
            WHERE node_id = ?
            """,
            (node_id,),
        ).fetchone()

        if row is None:
            self._conn.execute(
                """
                INSERT INTO node_capabilities(
                  node_id, last_seen_unix, has_position, last_position_unix,
                  last_hops, battery_level, battery_updated_unix
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node_id,
                    event_unix,
                    1 if has_position else 0,
                    event_unix if has_position else None,
                    clean_hops,
                    clean_battery,
                    event_unix if clean_battery is not None else None,
                ),
            )
            return

        (
            last_seen_unix,
            row_has_position,
            row_last_position_unix,
            row_last_hops,
            row_battery_level,
            row_battery_updated_unix,
        ) = row
        merged_last_seen = max(_to_int(last_seen_unix) or event_unix, event_unix)
        merged_has_position = bool(_to_int(row_has_position)) or has_position
        merged_last_position_unix = _to_int(row_last_position_unix)
        if has_position:
            merged_last_position_unix = event_unix

        merged_last_hops = clean_hops if clean_hops is not None else _to_int(row_last_hops)
        merged_battery_level = _to_int(row_battery_level)
        merged_battery_updated_unix = _to_int(row_battery_updated_unix)
        if clean_battery is not None:
            merged_battery_level = clean_battery
            merged_battery_updated_unix = event_unix

        self._conn.execute(
            """
            UPDATE node_capabilities
            SET last_seen_unix = ?,
                has_position = ?,
                last_position_unix = ?,
                last_hops = ?,
                battery_level = ?,
                battery_updated_unix = ?
            WHERE node_id = ?
            """,
            (
                merged_last_seen,
                1 if merged_has_position else 0,
                merged_last_position_unix,
                merged_last_hops,
                merged_battery_level,
                merged_battery_updated_unix,
                node_id,
            ),
        )

    def _upsert_node_metric_unlocked(
        self,
        bucket_unix: int,
        node_id: str,
        event_unix: int,
        rx_snr: Optional[float],
        rx_rssi: Optional[float],
        hops: Optional[int],
    ) -> None:
        row = self._conn.execute(
            """
            SELECT packet_count,
                   snr_sum, snr_count, snr_min, snr_max,
                   rssi_sum, rssi_count, rssi_min, rssi_max,
                   hops_sum, hops_count, hops_min, hops_max,
                   last_seen_unix
            FROM node_metrics_1m
            WHERE bucket_unix = ? AND node_id = ?
            """,
            (bucket_unix, node_id),
        ).fetchone()

        if row is None:
            snr_sum, snr_count, snr_min, snr_max = self._merge_metric(0.0, 0, None, None, rx_snr)
            rssi_sum, rssi_count, rssi_min, rssi_max = self._merge_metric(0.0, 0, None, None, rx_rssi)
            hops_sum, hops_count, hops_min, hops_max = self._merge_metric(
                0.0,
                0,
                None,
                None,
                float(hops) if hops is not None else None,
            )
            self._conn.execute(
                """
                INSERT INTO node_metrics_1m(
                  bucket_unix, node_id, packet_count,
                  snr_sum, snr_count, snr_min, snr_max,
                  rssi_sum, rssi_count, rssi_min, rssi_max,
                  hops_sum, hops_count, hops_min, hops_max,
                  last_seen_unix
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bucket_unix,
                    node_id,
                    1,
                    snr_sum,
                    snr_count,
                    snr_min,
                    snr_max,
                    rssi_sum,
                    rssi_count,
                    rssi_min,
                    rssi_max,
                    int(hops_sum),
                    hops_count,
                    int(hops_min) if hops_min is not None else None,
                    int(hops_max) if hops_max is not None else None,
                    event_unix,
                ),
            )
            return

        (
            packet_count,
            snr_sum,
            snr_count,
            snr_min,
            snr_max,
            rssi_sum,
            rssi_count,
            rssi_min,
            rssi_max,
            hops_sum,
            hops_count,
            hops_min,
            hops_max,
            last_seen_unix,
        ) = row

        snr_sum, snr_count, snr_min, snr_max = self._merge_metric(snr_sum, snr_count, snr_min, snr_max, rx_snr)
        rssi_sum, rssi_count, rssi_min, rssi_max = self._merge_metric(
            rssi_sum,
            rssi_count,
            rssi_min,
            rssi_max,
            rx_rssi,
        )
        hops_sum_f, hops_count, hops_min_f, hops_max_f = self._merge_metric(
            hops_sum,
            hops_count,
            hops_min,
            hops_max,
            float(hops) if hops is not None else None,
        )

        self._conn.execute(
            """
            UPDATE node_metrics_1m
            SET packet_count = ?,
                snr_sum = ?, snr_count = ?, snr_min = ?, snr_max = ?,
                rssi_sum = ?, rssi_count = ?, rssi_min = ?, rssi_max = ?,
                hops_sum = ?, hops_count = ?, hops_min = ?, hops_max = ?,
                last_seen_unix = ?
            WHERE bucket_unix = ? AND node_id = ?
            """,
            (
                int(packet_count or 0) + 1,
                snr_sum,
                snr_count,
                snr_min,
                snr_max,
                rssi_sum,
                rssi_count,
                rssi_min,
                rssi_max,
                int(hops_sum_f),
                hops_count,
                int(hops_min_f) if hops_min_f is not None else None,
                int(hops_max_f) if hops_max_f is not None else None,
                max(_to_int(last_seen_unix) or event_unix, event_unix),
                bucket_unix,
                node_id,
            ),
        )

    def _upsert_link_metric_unlocked(
        self,
        bucket_unix: int,
        from_id: str,
        to_id: str,
        event_unix: int,
        rx_snr: Optional[float],
        rx_rssi: Optional[float],
        hops: Optional[int],
    ) -> None:
        row = self._conn.execute(
            """
            SELECT packet_count,
                   snr_sum, snr_count, snr_min, snr_max,
                   rssi_sum, rssi_count, rssi_min, rssi_max,
                   hops_sum, hops_count, hops_min, hops_max,
                   last_seen_unix
            FROM link_metrics_1m
            WHERE bucket_unix = ? AND from_id = ? AND to_id = ?
            """,
            (bucket_unix, from_id, to_id),
        ).fetchone()

        if row is None:
            snr_sum, snr_count, snr_min, snr_max = self._merge_metric(0.0, 0, None, None, rx_snr)
            rssi_sum, rssi_count, rssi_min, rssi_max = self._merge_metric(0.0, 0, None, None, rx_rssi)
            hops_sum, hops_count, hops_min, hops_max = self._merge_metric(
                0.0,
                0,
                None,
                None,
                float(hops) if hops is not None else None,
            )
            self._conn.execute(
                """
                INSERT INTO link_metrics_1m(
                  bucket_unix, from_id, to_id, packet_count,
                  snr_sum, snr_count, snr_min, snr_max,
                  rssi_sum, rssi_count, rssi_min, rssi_max,
                  hops_sum, hops_count, hops_min, hops_max,
                  last_seen_unix
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bucket_unix,
                    from_id,
                    to_id,
                    1,
                    snr_sum,
                    snr_count,
                    snr_min,
                    snr_max,
                    rssi_sum,
                    rssi_count,
                    rssi_min,
                    rssi_max,
                    int(hops_sum),
                    hops_count,
                    int(hops_min) if hops_min is not None else None,
                    int(hops_max) if hops_max is not None else None,
                    event_unix,
                ),
            )
            return

        (
            packet_count,
            snr_sum,
            snr_count,
            snr_min,
            snr_max,
            rssi_sum,
            rssi_count,
            rssi_min,
            rssi_max,
            hops_sum,
            hops_count,
            hops_min,
            hops_max,
            last_seen_unix,
        ) = row

        snr_sum, snr_count, snr_min, snr_max = self._merge_metric(snr_sum, snr_count, snr_min, snr_max, rx_snr)
        rssi_sum, rssi_count, rssi_min, rssi_max = self._merge_metric(
            rssi_sum,
            rssi_count,
            rssi_min,
            rssi_max,
            rx_rssi,
        )
        hops_sum_f, hops_count, hops_min_f, hops_max_f = self._merge_metric(
            hops_sum,
            hops_count,
            hops_min,
            hops_max,
            float(hops) if hops is not None else None,
        )

        self._conn.execute(
            """
            UPDATE link_metrics_1m
            SET packet_count = ?,
                snr_sum = ?, snr_count = ?, snr_min = ?, snr_max = ?,
                rssi_sum = ?, rssi_count = ?, rssi_min = ?, rssi_max = ?,
                hops_sum = ?, hops_count = ?, hops_min = ?, hops_max = ?,
                last_seen_unix = ?
            WHERE bucket_unix = ? AND from_id = ? AND to_id = ?
            """,
            (
                int(packet_count or 0) + 1,
                snr_sum,
                snr_count,
                snr_min,
                snr_max,
                rssi_sum,
                rssi_count,
                rssi_min,
                rssi_max,
                int(hops_sum_f),
                hops_count,
                int(hops_min_f) if hops_min_f is not None else None,
                int(hops_max_f) if hops_max_f is not None else None,
                max(_to_int(last_seen_unix) or event_unix, event_unix),
                bucket_unix,
                from_id,
                to_id,
            ),
        )

    def _save_packet_event_and_rollups_unlocked(self, summary: Dict[str, Any]) -> None:
        event_unix = _to_int(summary.get("rx_time_unix"))
        if event_unix is None or event_unix <= 0:
            event_unix = int(time.time())

        from_id = self._clean_node_id(summary.get("from"))
        to_id = self._clean_node_id(summary.get("to"))
        portnum_raw = summary.get("portnum")
        portnum = str(portnum_raw) if portnum_raw is not None else None
        rx_snr = _to_float(summary.get("rx_snr"))
        rx_rssi = _to_float(summary.get("rx_rssi"))
        hops = _to_int(summary.get("hops"))
        hop_start = _to_int(summary.get("hop_start"))
        hop_limit = _to_int(summary.get("hop_limit"))
        channel_raw = summary.get("channel")
        channel = str(channel_raw) if channel_raw is not None else None
        priority_raw = summary.get("priority")
        priority = str(priority_raw) if priority_raw is not None else None
        want_ack = 1 if summary.get("want_ack") else 0
        position_data = summary.get("position")
        battery_level = _to_int(summary.get("battery_level"))

        self._conn.execute(
            """
            INSERT INTO packet_events(
              created_unix, from_id, to_id, portnum,
              rx_snr, rx_rssi, hops, hop_start, hop_limit,
              channel, want_ack, priority, summary_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_unix,
                from_id,
                to_id,
                portnum,
                rx_snr,
                rx_rssi,
                hops,
                hop_start,
                hop_limit,
                channel,
                want_ack,
                priority,
                json.dumps(summary, separators=(",", ":")),
            ),
        )

        bucket_unix = self._bucket_minute(event_unix)
        if from_id:
            self._upsert_node_metric_unlocked(
                bucket_unix=bucket_unix,
                node_id=from_id,
                event_unix=event_unix,
                rx_snr=rx_snr,
                rx_rssi=rx_rssi,
                hops=hops,
            )
            self._save_node_position_unlocked(
                node_id=from_id,
                event_unix=event_unix,
                position_data=position_data,
            )
            self._upsert_node_capability_unlocked(
                node_id=from_id,
                event_unix=event_unix,
                has_position=_extract_position_fields(position_data) is not None,
                last_hops=hops,
                battery_level=battery_level,
            )
        if from_id and to_id and from_id != to_id:
            self._upsert_link_metric_unlocked(
                bucket_unix=bucket_unix,
                from_id=from_id,
                to_id=to_id,
                event_unix=event_unix,
                rx_snr=rx_snr,
                rx_rssi=rx_rssi,
                hops=hops,
            )

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
                self._save_packet_event_and_rollups_unlocked(summary)
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
            for edge in self._history_store.load_connections():
                key = (str(edge["from"]), str(edge["to"]))
                self._historical_edges[key] = {
                    "from": str(edge["from"]),
                    "to": str(edge["to"]),
                    "count": int(edge["count"]),
                    "first_rx_time": edge.get("first_rx_time"),
                    "last_rx_time": edge.get("last_rx_time"),
                    "portnums": set(edge.get("portnums") or []),
                    "last_hops": edge.get("last_hops"),
                    "hops_sum": int(edge.get("hops_sum") or 0),
                    "hops_count": int(edge.get("hops_count") or 0),
                }

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

        is_direct_link = (
            bool(from_id)
            and bool(to_id)
            and from_id not in ("Unknown",)
            and to_id not in ("^all", "Unknown")
            and str(from_id) != str(to_id)
        )
        if is_direct_link:
            key = (str(from_id), str(to_id))
            edge = self.edges.setdefault(
                key,
                {
                    "from": str(from_id),
                    "to": str(to_id),
                    "count": 0,
                    "first_rx_time": None,
                    "last_rx_time": None,
                    "portnums": set(),
                    "last_hops": None,
                    "hops_sum": 0,
                    "hops_count": 0,
                },
            )
            edge["count"] += 1
            if rx_time is not None and (edge["first_rx_time"] is None or rx_time < edge["first_rx_time"]):
                edge["first_rx_time"] = rx_time
            if rx_time is not None and (edge["last_rx_time"] is None or rx_time > edge["last_rx_time"]):
                edge["last_rx_time"] = rx_time

            if portnum is not None:
                edge["portnums"].add(str(portnum))
            if hops is not None:
                edge["last_hops"] = hops
                edge["hops_sum"] += hops
                edge["hops_count"] += 1

            if include_live_count:
                hist = self._historical_edges.setdefault(
                    key,
                    {
                        "from": str(from_id),
                        "to": str(to_id),
                        "count": 0,
                        "first_rx_time": None,
                        "last_rx_time": None,
                        "portnums": set(),
                        "last_hops": None,
                        "hops_sum": 0,
                        "hops_count": 0,
                    },
                )
                hist["count"] += 1
                if rx_time is not None and (hist["first_rx_time"] is None or rx_time < hist["first_rx_time"]):
                    hist["first_rx_time"] = rx_time
                if rx_time is not None and (hist["last_rx_time"] is None or rx_time > hist["last_rx_time"]):
                    hist["last_rx_time"] = rx_time
                if portnum is not None:
                    hist["portnums"].add(str(portnum))
                if hops is not None:
                    hist["last_hops"] = hops
                    hist["hops_sum"] += hops
                    hist["hops_count"] += 1

                if self._history_store is not None:
                    self._history_store.save_connection_event(
                        from_id=str(from_id),
                        to_id=str(to_id),
                        rx_time=rx_time,
                        portnum=str(portnum) if portnum is not None else None,
                        hops=hops,
                    )

        packet_summary = {
            "captured_at": _utc_now(),
            "live": include_live_count,
            "packet_id": packet_id,
            "from": from_id,
            "to": to_id,
            "from_num": _to_int(packet.get("from")),
            "to_num": _to_int(packet.get("to")),
            "portnum": str(portnum) if portnum is not None else None,
            "rx_time": _format_epoch(packet.get("rxTime")),
            "rx_time_unix": rx_time,
            "rx_rssi": packet.get("rxRssi"),
            "rx_snr": packet.get("rxSnr"),
            "hop_start": packet.get("hopStart"),
            "hop_limit": packet.get("hopLimit"),
            "hops": hops,
            "want_ack": packet.get("wantAck"),
            "priority": packet.get("priority"),
            "channel": packet.get("channel"),
            "decoded_text": decoded.get("text") if isinstance(decoded, dict) else None,
            "reply_id": reply_id,
            "emoji": emoji_glyph,
            "emoji_codepoint": emoji_codepoint,
            "is_reaction": is_reaction,
        }
        if packet_position is not None:
            packet_summary["position"] = packet_position
        if packet_battery is not None:
            packet_summary["battery_level"] = packet_battery

        packet_entry = {
            "summary": packet_summary,
            "packet": _to_jsonable(packet),
        }
        self.recent_packets.append(packet_entry)
        if self._history_store is not None and include_live_count:
            self._history_store.save_packet(packet_entry)

        decoded_text = decoded.get("text") if isinstance(decoded, dict) else None
        has_text = isinstance(decoded_text, str) and decoded_text.strip()
        if has_text or is_reaction:
            chat_entry = {
                "captured_at": _utc_now(),
                "from": from_id,
                "to": to_id,
                "portnum": str(portnum) if portnum is not None else None,
                "channel": packet.get("channel"),
                "rx_time": _format_epoch(packet.get("rxTime")),
                "text": decoded_text if isinstance(decoded_text, str) else "",
                "hops": hops,
                "hop_start": packet.get("hopStart"),
                "hop_limit": packet.get("hopLimit"),
            }
            if packet_id is not None and packet_id > 0:
                chat_entry["message_id"] = packet_id
            if reply_id is not None and reply_id > 0:
                chat_entry["reply_id"] = reply_id
            if emoji_glyph:
                chat_entry["emoji"] = emoji_glyph
            if emoji_codepoint is not None and emoji_codepoint > 0:
                chat_entry["emoji_codepoint"] = emoji_codepoint
            if is_reaction:
                chat_entry["is_reaction"] = True
            self.recent_chat.append(chat_entry)
            if self._history_store is not None and include_live_count:
                self._history_store.save_chat(chat_entry)

        self._expire_pending_deliveries_unlocked()

    def snapshot(self, nodes_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        with self._lock:
            self._expire_pending_deliveries_unlocked()
            edge_rows: list[Dict[str, Any]] = []
            real_edge_count = 0
            combined_keys = set(self.edges.keys()) | set(self._historical_edges.keys())
            for key in combined_keys:
                session_edge = self.edges.get(key)
                hist_edge = self._historical_edges.get(key)
                from_id, to_id = key

                session_count = int(session_edge["count"]) if session_edge else 0
                if hist_edge:
                    lifetime_count = int(hist_edge["count"])
                    first_seen = hist_edge.get("first_rx_time")
                    last_seen = hist_edge.get("last_rx_time")
                    last_hops = hist_edge.get("last_hops")
                    hops_sum = int(hist_edge.get("hops_sum") or 0)
                    hops_count = int(hist_edge.get("hops_count") or 0)
                    port_set = set(hist_edge.get("portnums") or set())
                else:
                    lifetime_count = session_count
                    first_seen = session_edge.get("first_rx_time") if session_edge else None
                    last_seen = session_edge.get("last_rx_time") if session_edge else None
                    last_hops = session_edge.get("last_hops") if session_edge else None
                    hops_sum = int(session_edge.get("hops_sum") or 0) if session_edge else 0
                    hops_count = int(session_edge.get("hops_count") or 0) if session_edge else 0
                    port_set = set(session_edge.get("portnums") or set()) if session_edge else set()

                if session_edge:
                    port_set |= set(session_edge.get("portnums") or set())
                    if first_seen is None:
                        first_seen = session_edge.get("first_rx_time")
                    session_last = session_edge.get("last_rx_time")
                    if session_last is not None and (last_seen is None or session_last > last_seen):
                        last_seen = session_last
                    if last_hops is None and session_edge.get("last_hops") is not None:
                        last_hops = session_edge.get("last_hops")

                avg_hops: Optional[float] = None
                if hops_count > 0:
                    avg_hops = round(hops_sum / hops_count, 2)
                is_real = lifetime_count >= MIN_REAL_LINK_COUNT
                if is_real:
                    real_edge_count += 1

                row = {
                    "from": from_id,
                    "to": to_id,
                    "count": lifetime_count,
                    "session_count": session_count,
                    "lifetime_count": lifetime_count,
                    "is_real": is_real,
                    "confidence": "confirmed" if is_real else "observed",
                    "first_rx_time": _format_epoch(first_seen),
                    "last_rx_time": _format_epoch(last_seen),
                    "last_hops": last_hops,
                    "avg_hops": avg_hops,
                    "hops_samples": hops_count,
                    "portnums": sorted(port_set),
                }
                src = nodes_by_id.get(from_id)
                dst = nodes_by_id.get(to_id)
                if src and dst and src.get("lat") is not None and dst.get("lat") is not None:
                    row["src_lat"] = src.get("lat")
                    row["src_lon"] = src.get("lon")
                    row["dst_lat"] = dst.get("lat")
                    row["dst_lon"] = dst.get("lon")
                edge_rows.append(row)

            edge_rows.sort(key=lambda item: (-item["lifetime_count"], item["from"], item["to"]))
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


def _seed_tracker_from_node_db(tracker: DashboardTracker, iface: Any) -> None:
    for _num, node in _safe_nodes_items(iface):
        if not isinstance(node, dict):
            continue
        last_packet = node.get("lastReceived")
        if isinstance(last_packet, dict):
            tracker.seed_packet(last_packet, iface)


def _collect_nodes(iface: Any) -> Dict[str, Any]:
    return _collect_nodes_helper(iface)


def _collect_local_state(iface: Any) -> Dict[str, Any]:
    return _collect_local_state_helper(iface)


def _build_state(
    iface: Any,
    tracker: DashboardTracker,
    started_at: float,
    target: str,
    show_secrets: bool,
    storage_probe_path: Optional[str],
    revision_info: Dict[str, str],
) -> Dict[str, Any]:
    return _build_state_helper(
        iface=iface,
        tracker=tracker,
        started_at=started_at,
        target=target,
        show_secrets=show_secrets,
        storage_probe_path=storage_probe_path,
        revision_info=revision_info,
        sensitive_field_names=SENSITIVE_FIELD_NAMES,
    )


def _render_html(
    refresh_ms: int,
    packet_limit: int,
    show_secrets: bool,
    history_enabled: bool,
    history_max_rows: int,
    history_retention_days: int,
    node_history_hours: int,
    node_history_max_points: int,
    revision_label: str,
    revision_title: str,
) -> str:
    return _render_html_helper(
        refresh_ms=refresh_ms,
        packet_limit=packet_limit,
        show_secrets=show_secrets,
        history_enabled=history_enabled,
        history_max_rows=history_max_rows,
        history_retention_days=history_retention_days,
        node_history_hours=node_history_hours,
        node_history_max_points=node_history_max_points,
        revision_label=revision_label,
        revision_title=revision_title,
    )


def _make_http_handler(
    html_text: str,
    state_fn,
    node_history_fn=None,
    online_activity_fn=None,
    send_chat_fn=None,
):
    return _make_http_handler_helper(
        html_text=html_text,
        state_fn=state_fn,
        node_history_fn=node_history_fn,
        online_activity_fn=online_activity_fn,
        send_chat_fn=send_chat_fn,
        default_node_history_hours=DEFAULT_NODE_HISTORY_HOURS,
        to_int_fn=_to_int,
    )


def run_dashboard(args: argparse.Namespace) -> None:
    if meshtastic is None:
        raise RuntimeError(
            "meshtastic Python package is required. Install with: pip install meshtastic"
        )
    if pub is None:
        raise RuntimeError(
            "pypubsub is required. Install with: pip install pypubsub"
        )
    target = mesh_target_label(args)
    print(f"Connecting to {target} ...")
    iface = open_mesh_interface(args)

    history_store: Optional[HistoryStore] = None
    history_db_path = os.path.abspath(os.path.expanduser(args.history_db))
    if not args.no_history:
        try:
            history_store = HistoryStore(
                db_path=history_db_path,
                max_rows=args.history_max_rows,
                retention_days=args.history_retention_days,
                event_max_rows=args.history_event_max_rows,
                event_retention_days=args.history_event_retention_days,
                rollup_retention_days=args.history_rollup_retention_days,
            )
        except Exception as exc:
            print(f"History disabled: cannot open {history_db_path}: {exc}")
            history_store = None

    tracker = DashboardTracker(packet_limit=args.packet_limit, history_store=history_store)
    send_lock = threading.Lock()
    pub.subscribe(tracker.on_receive, "meshtastic.receive")
    if not tracker.has_recent_packets():
        _seed_tracker_from_node_db(tracker, iface)
    started_at = time.time()
    revision_info = _revision_info()

    def state_fn() -> Dict[str, Any]:
        return _build_state(
            iface=iface,
            tracker=tracker,
            started_at=started_at,
            target=target,
            show_secrets=args.show_secrets,
            storage_probe_path=history_db_path,
            revision_info=revision_info,
        )

    node_history_fn = _build_node_history_loader(
        history_store=history_store,
        default_hours=args.node_history_hours,
        default_points=args.node_history_max_points,
    )
    online_activity_fn = _build_online_activity_loader(
        history_store=history_store,
        default_hours=args.node_history_hours,
    )

    def send_chat_fn(
        text: Any,
        destination: Any = None,
        channel_index: Optional[int] = None,
        reply_id: Optional[int] = None,
        retry_of: Optional[int] = None,
        emoji: Any = None,
    ) -> Dict[str, Any]:
        return _send_chat_message_helper(
            text=text,
            destination=destination,
            channel_index=channel_index,
            reply_id=reply_id,
            retry_of=retry_of,
            emoji=emoji,
            iface=iface,
            send_lock=send_lock,
            send_reaction_packet_fn=_send_emoji_reaction_packet,
            local_node_id_fn=lambda: _get_local_node_id(iface),
            record_local_chat_fn=tracker.record_local_chat,
            chat_max_bytes=DEFAULT_CHAT_MAX_BYTES,
            normalize_single_emoji_fn=_normalize_single_emoji,
            to_int_fn=_to_int,
            now_text_fn=_utc_now,
        )

    html = _render_html(
        refresh_ms=args.refresh_ms,
        packet_limit=args.packet_limit,
        show_secrets=args.show_secrets,
        history_enabled=history_store is not None,
        history_max_rows=args.history_max_rows,
        history_retention_days=args.history_retention_days,
        node_history_hours=args.node_history_hours,
        node_history_max_points=args.node_history_max_points,
        revision_label=revision_info["label"],
        revision_title=revision_info["title"],
    )
    handler_cls = _make_http_handler(
        html,
        state_fn,
        node_history_fn=node_history_fn,
        online_activity_fn=online_activity_fn,
        send_chat_fn=send_chat_fn,
    )
    server = ThreadingHTTPServer((args.http_host, args.http_port), handler_cls)
    bound_host, bound_port = server.server_address[:2]

    print("Dashboard server running.")
    print(f"Bound to: {bound_host}:{bound_port}")
    if args.http_host in ("0.0.0.0", "::"):
        print(f"Open from this computer: http://127.0.0.1:{bound_port}")
        lan_ip = _guess_lan_ipv4()
        if lan_ip:
            print(f"Open from Wi-Fi devices: http://{lan_ip}:{bound_port}")
        else:
            print(f"Open from Wi-Fi devices: http://<this-computer-ip>:{bound_port}")
    else:
        print(f"Open: http://{args.http_host}:{bound_port}")
    if not args.show_secrets:
        print("Secrets are redacted. Use --show-secrets to display full values.")
    print(f"Revision: v{revision_info['version']} ({revision_info['commit']})")
    if history_store is not None:
        print(
            f"History DB: {history_db_path} "
            f"(retention {args.history_retention_days}d, max {args.history_max_rows} rows; "
            f"events {args.history_event_retention_days}d/{args.history_event_max_rows} rows; "
            f"rollups {args.history_rollup_retention_days}d)"
        )
    else:
        print("History DB: disabled")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("Stopping dashboard...")
    finally:
        server.server_close()
        iface.close()
        if history_store is not None:
            history_store.close()


def main() -> None:
    env_gateway_host = os.environ.get("MESH_GATEWAY_HOST", DEFAULT_GATEWAY_HOST)
    env_gateway_port = os.environ.get("MESH_GATEWAY_PORT")
    try:
        resolved_gateway_port = int(env_gateway_port) if env_gateway_port else DEFAULT_GATEWAY_PORT
    except ValueError:
        resolved_gateway_port = DEFAULT_GATEWAY_PORT

    parser = argparse.ArgumentParser(
        description="Serve a high-detail Meshtastic dashboard with map, node tables, configs, and packet logs."
    )
    add_mesh_connection_args(parser, default_mesh_port=DEFAULT_MESH_PORT)
    parser.add_argument(
        "--default-gateway-host",
        default=env_gateway_host,
        help=(
            "Fallback TCP host for dashboard mode when --mesh-host is not provided "
            f"(default: {env_gateway_host})."
        ),
    )
    parser.add_argument(
        "--default-gateway-port",
        type=int,
        default=resolved_gateway_port,
        help=(
            "Fallback TCP port used with --default-gateway-host when --mesh-host is not provided "
            f"(default: {resolved_gateway_port})."
        ),
    )
    parser.add_argument(
        "--no-default-gateway",
        action="store_true",
        help="Disable default gateway fallback and use serial unless --mesh-host is set.",
    )
    parser.add_argument(
        "--http-host",
        default=DEFAULT_HTTP_HOST,
        help=f"HTTP bind host (default: {DEFAULT_HTTP_HOST})",
    )
    parser.add_argument(
        "--http-port",
        type=int,
        default=DEFAULT_HTTP_PORT,
        help=f"HTTP bind port (default: {DEFAULT_HTTP_PORT})",
    )
    parser.add_argument(
        "--refresh-ms",
        type=int,
        default=DEFAULT_REFRESH_MS,
        help=f"Browser polling interval in milliseconds (default: {DEFAULT_REFRESH_MS})",
    )
    parser.add_argument(
        "--packet-limit",
        type=int,
        default=DEFAULT_PACKET_LIMIT,
        help=f"Recent packet history buffer size (default: {DEFAULT_PACKET_LIMIT})",
    )
    parser.add_argument(
        "--show-secrets",
        action="store_true",
        help="Display sensitive config values (private keys/passwords/PSKs) in raw JSON panels.",
    )
    parser.add_argument(
        "--history-db",
        default=os.environ.get("MESH_DASH_HISTORY_DB", DEFAULT_HISTORY_DB),
        help=f"SQLite DB path for persisted chat/packet history and rollups (default: {DEFAULT_HISTORY_DB})",
    )
    parser.add_argument(
        "--history-max-rows",
        type=int,
        default=DEFAULT_HISTORY_MAX_ROWS,
        help=f"Max persisted rows per history table (default: {DEFAULT_HISTORY_MAX_ROWS})",
    )
    parser.add_argument(
        "--history-retention-days",
        type=int,
        default=DEFAULT_HISTORY_RETENTION_DAYS,
        help=(
            "Delete persisted rows older than this many days; "
            f"use 0 to disable age-based pruning (default: {DEFAULT_HISTORY_RETENTION_DAYS})"
        ),
    )
    parser.add_argument(
        "--history-event-max-rows",
        type=int,
        default=DEFAULT_HISTORY_EVENT_MAX_ROWS,
        help=(
            "Max rows for append-only packet event history "
            f"(default: {DEFAULT_HISTORY_EVENT_MAX_ROWS})"
        ),
    )
    parser.add_argument(
        "--history-event-retention-days",
        type=int,
        default=DEFAULT_HISTORY_EVENT_RETENTION_DAYS,
        help=(
            "Delete packet event rows older than this many days; "
            f"use 0 to disable age-based pruning (default: {DEFAULT_HISTORY_EVENT_RETENTION_DAYS})"
        ),
    )
    parser.add_argument(
        "--history-rollup-retention-days",
        type=int,
        default=DEFAULT_HISTORY_ROLLUP_RETENTION_DAYS,
        help=(
            "Delete rollup rows older than this many days; "
            f"use 0 to disable age-based pruning (default: {DEFAULT_HISTORY_ROLLUP_RETENTION_DAYS})"
        ),
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Disable persisted SQLite history (memory-only live buffers).",
    )
    parser.add_argument(
        "--node-history-hours",
        type=int,
        default=DEFAULT_NODE_HISTORY_HOURS,
        help=f"Default selected-node history window in hours (default: {DEFAULT_NODE_HISTORY_HOURS})",
    )
    parser.add_argument(
        "--node-history-max-points",
        type=int,
        default=DEFAULT_NODE_HISTORY_MAX_POINTS,
        help=(
            "Max selected-node history points returned by /api/history/node "
            f"(default: {DEFAULT_NODE_HISTORY_MAX_POINTS})"
        ),
    )
    args = parser.parse_args()
    _apply_default_gateway(args)
    run_dashboard(args)


if __name__ == "__main__":
    main()
