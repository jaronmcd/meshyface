import argparse
import json
import os
import socket
import sqlite3
import subprocess
import threading
import time
from collections import Counter, deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

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
    disk_space_info as _disk_space_info,
    emoji_from_codepoint as _emoji_from_codepoint,
    extract_emoji_codepoint as _extract_emoji_codepoint,
    extract_reply_id as _extract_reply_id,
    format_epoch as _format_epoch,
    normalize_single_emoji as _normalize_single_emoji,
    safe_json_loads as _safe_json_loads,
    to_float as _to_float,
    to_int as _to_int,
)
try:
    from pubsub import pub
except Exception:
    pub = None

try:
    from google.protobuf.json_format import MessageToDict
    from google.protobuf.message import Message
except Exception:
    Message = None
    MessageToDict = None

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
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def _sanitize_revision_token(raw: Any, fallback: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return fallback
    safe = "".join(ch for ch in text if ch.isalnum() or ch in ("-", "_", ".", "+"))
    return safe or fallback


def _detect_git_commit() -> Optional[str]:
    explicit = str(os.environ.get("MESH_DASH_GIT_COMMIT", "")).strip()
    if explicit:
        return _sanitize_revision_token(explicit, UNKNOWN_GIT_COMMIT)

    search_roots: list[str] = []
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cwd = os.getcwd()
    for root in (script_dir, cwd):
        if root and root not in search_roots:
            search_roots.append(root)

    for root in search_roots:
        try:
            proc = subprocess.run(
                ["git", "-C", root, "rev-parse", "--short=12", "HEAD"],
                check=False,
                capture_output=True,
                text=True,
                timeout=1.0,
            )
        except Exception:
            continue
        if proc.returncode == 0:
            commit = _sanitize_revision_token(proc.stdout, "")
            if commit:
                return commit
    return None


def _revision_info() -> Dict[str, str]:
    version_raw = os.environ.get("MESH_DASH_VERSION", DEFAULT_APP_VERSION)
    version = _sanitize_revision_token(version_raw, "0.0.0")
    if version.lower().startswith("v"):
        version = version[1:] or "0.0.0"

    commit = _detect_git_commit() or UNKNOWN_GIT_COMMIT
    label = f"Rev: v{version} ({commit})"
    title = f"Dashboard revision: version {version}, commit {commit}"

    return {
        "version": version,
        "commit": commit,
        "label": label,
        "title": title,
    }


def _send_emoji_reaction_packet(
    iface: Any,
    destination_id: str,
    channel_index: int,
    reply_id: int,
    emoji_codepoint: int,
    emoji_text: str,
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
    return iface._sendPacket(packet, destinationId=destination_id, wantAck=False)


def _guess_lan_ipv4() -> Optional[str]:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
    except OSError:
        pass

    try:
        addr_info = socket.getaddrinfo(socket.gethostname(), None, family=socket.AF_INET)
        for _family, _type, _proto, _canonname, sockaddr in addr_info:
            ip = sockaddr[0]
            if ip and not ip.startswith("127."):
                return ip
    except socket.gaierror:
        pass

    return None


def _get_local_node_num(iface: Any) -> Optional[int]:
    my_info = _to_jsonable(getattr(iface, "myInfo", None))
    if isinstance(my_info, dict):
        for key in ("my_node_num", "myNodeNum", "node_num", "nodeNum", "num"):
            value = _to_int(my_info.get(key))
            if value is not None:
                return value

    local = getattr(iface, "localNode", None)
    if local is not None:
        for key in ("nodeNum", "node_num", "num"):
            value = _to_int(getattr(local, key, None))
            if value is not None:
                return value
    return None


def _get_local_node_id(iface: Any) -> str:
    node_num = _get_local_node_num(iface)
    if node_num is None:
        return "local"
    node_id = _get_node_id_from_num(iface, node_num)
    if node_id:
        return node_id
    return f"!{node_num:08x}"


def _apply_default_gateway(args: argparse.Namespace) -> None:
    # If user did not provide --mesh-host and left serial at the default path,
    # prefer the shared TCP gateway for this dashboard.
    if args.no_default_gateway:
        return
    if args.mesh_host:
        return
    if args.mesh_port != DEFAULT_MESH_PORT:
        return
    if not args.default_gateway_host:
        return
    args.mesh_host = args.default_gateway_host
    args.mesh_tcp_port = args.default_gateway_port


def _message_to_dict(value: Any) -> Any:
    if Message is not None and MessageToDict is not None and isinstance(value, Message):
        return MessageToDict(value, preserving_proto_field_name=True)
    return None


def _to_jsonable(value: Any, depth: int = 0) -> Any:
    if depth > 12:
        return "<max-depth>"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return value.hex()
    as_message = _message_to_dict(value)
    if as_message is not None:
        return _to_jsonable(as_message, depth + 1)
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, val in value.items():
            out[str(key)] = _to_jsonable(val, depth + 1)
        return out
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item, depth + 1) for item in value]
    return str(value)


def _is_sensitive_key(key: str) -> bool:
    key_l = key.lower()
    if key_l in SENSITIVE_FIELD_NAMES:
        return True
    return key_l.endswith("_password") or key_l.endswith("_private_key")


def _redact_secrets(value: Any, parent_key: Optional[str] = None) -> Any:
    if parent_key and _is_sensitive_key(parent_key):
        return "<redacted>"
    if isinstance(value, dict):
        return {
            key: _redact_secrets(val, key)
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [_redact_secrets(item, parent_key) for item in value]
    return value


def _get_node_id_from_num(iface: Any, node_num: Any) -> Optional[str]:
    numeric = _to_int(node_num)
    if numeric is None:
        return None
    if numeric == meshtastic.BROADCAST_NUM:
        return "^all"

    info = (iface.nodesByNum or {}).get(numeric, {})
    user = info.get("user", {}) if isinstance(info, dict) else {}
    node_id = user.get("id") if isinstance(user, dict) else None
    if node_id:
        return str(node_id)
    return f"!{numeric:08x}"


def _extract_position(node_info: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    position = node_info.get("position")
    if not isinstance(position, dict):
        return None

    lat = position.get("latitude")
    lon = position.get("longitude")

    if lat is None and position.get("latitudeI") is not None:
        lat = _to_float(position.get("latitudeI"))
        lat = lat * 1e-7 if lat is not None else None
    if lon is None and position.get("longitudeI") is not None:
        lon = _to_float(position.get("longitudeI"))
        lon = lon * 1e-7 if lon is not None else None

    lat_f = _to_float(lat)
    lon_f = _to_float(lon)
    if lat_f is None or lon_f is None:
        return None
    if lat_f == 0.0 and lon_f == 0.0:
        return None
    return lat_f, lon_f


def _safe_nodes_items(iface: Any) -> list[Tuple[Any, Any]]:
    for _ in range(3):
        try:
            return list((iface.nodesByNum or {}).items())
        except RuntimeError:
            time.sleep(0.01)
    return []


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
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_node_metrics_1m_last_seen_unix ON node_metrics_1m(last_seen_unix)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_link_metrics_1m_last_seen_unix ON link_metrics_1m(last_seen_unix)"
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
            return {"node_id": "", "window_hours": max(1, int(window_hours)), "points": [], "summary": {}}

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

        points: list[Dict[str, Any]] = []
        total_packets = 0
        snr_min_all: Optional[float] = None
        snr_max_all: Optional[float] = None
        rssi_min_all: Optional[float] = None
        rssi_max_all: Optional[float] = None
        first_bucket: Optional[int] = None
        last_bucket: Optional[int] = None
        last_seen: Optional[int] = None

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

        return {
            "node_id": clean_node_id,
            "window_hours": hours,
            "points": points,
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
    ) -> None:
        clean_text = str(text or "").strip()
        clean_message_id = _to_int(message_id)
        clean_reply_id = _to_int(reply_id)
        clean_emoji_codepoint = _to_int(emoji_codepoint)
        clean_emoji = str(emoji or "").strip() or _emoji_from_codepoint(clean_emoji_codepoint)
        if clean_emoji and clean_emoji_codepoint is None:
            clean_emoji_codepoint = ord(clean_emoji[0])
        has_reaction = bool(
            is_reaction or (clean_reply_id is not None and clean_reply_id > 0 and clean_emoji)
        )
        if not clean_text and not has_reaction:
            return
        entry = {
            "captured_at": _utc_now(),
            "from": str(from_id or "local"),
            "to": str(to_id or "^all"),
            "portnum": "TEXT_MESSAGE_APP",
            "channel": int(channel_index) if isinstance(channel_index, int) else 0,
            "rx_time": _utc_now(),
            "text": clean_text,
        }
        if clean_message_id is not None and clean_message_id > 0:
            entry["message_id"] = clean_message_id
        if clean_reply_id is not None and clean_reply_id > 0:
            entry["reply_id"] = clean_reply_id
        if clean_emoji:
            entry["emoji"] = clean_emoji
        if clean_emoji_codepoint is not None and clean_emoji_codepoint > 0:
            entry["emoji_codepoint"] = clean_emoji_codepoint
        if has_reaction:
            entry["is_reaction"] = True
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
        reply_id = _extract_reply_id(decoded)
        emoji_codepoint = _extract_emoji_codepoint(decoded)
        emoji_glyph = _emoji_from_codepoint(emoji_codepoint)
        is_reaction = bool(reply_id is not None and reply_id > 0 and emoji_glyph)
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

    def snapshot(self, nodes_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        with self._lock:
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
    rows: list[Dict[str, Any]] = []
    full_nodes: list[Dict[str, Any]] = []
    nodes_by_id: Dict[str, Dict[str, Any]] = {}

    for node_num, raw_info in _safe_nodes_items(iface):
        if not isinstance(raw_info, dict):
            continue

        info = _to_jsonable(raw_info)
        if not isinstance(info, dict):
            continue

        node_num_int = _to_int(info.get("num", node_num))
        user = info.get("user", {}) if isinstance(info.get("user"), dict) else {}
        node_id = user.get("id")
        if not node_id and node_num_int is not None:
            node_id = f"!{node_num_int:08x}"

        if not node_id:
            continue

        metrics = info.get("deviceMetrics", {}) if isinstance(info.get("deviceMetrics"), dict) else {}
        position = _extract_position(info)
        last_heard_epoch = _to_int(info.get("lastHeard")) or 0

        row = {
            "id": str(node_id),
            "num": node_num_int,
            "short_name": user.get("shortName"),
            "long_name": user.get("longName"),
            "hardware_model": user.get("hwModel"),
            "role": user.get("role"),
            "is_licensed": user.get("isLicensed"),
            "last_heard": _format_epoch(last_heard_epoch),
            "last_heard_epoch": last_heard_epoch,
            "last_heard_unix": last_heard_epoch,
            "snr": info.get("snr"),
            "hops_away": info.get("hopsAway"),
            "battery_level": metrics.get("batteryLevel"),
            "voltage": metrics.get("voltage"),
            "channel_utilization": metrics.get("channelUtilization"),
            "air_util_tx": metrics.get("airUtilTx"),
            "lat": position[0] if position else None,
            "lon": position[1] if position else None,
        }
        rows.append(row)
        nodes_by_id[str(node_id)] = row
        full_nodes.append(
            {
                "id": str(node_id),
                "num": node_num_int,
                "info": info,
            }
        )

    rows.sort(key=lambda item: item.get("last_heard_epoch", 0), reverse=True)
    for row in rows:
        row.pop("last_heard_epoch", None)

    full_nodes.sort(key=lambda item: item.get("num") or 0)
    nodes_with_position = sum(
        1 for node in rows if node.get("lat") is not None and node.get("lon") is not None
    )

    return {
        "rows": rows,
        "full": full_nodes,
        "by_id": nodes_by_id,
        "with_position_count": nodes_with_position,
    }


def _collect_local_state(iface: Any) -> Dict[str, Any]:
    local = getattr(iface, "localNode", None)
    if local is None:
        local = iface.getNode("^local")

    state: Dict[str, Any] = {}

    state["local_config"] = _to_jsonable(getattr(local, "localConfig", None))
    state["module_config"] = _to_jsonable(getattr(local, "moduleConfig", None))
    channels = getattr(local, "channels", None)
    if channels is None:
        state["channels"] = []
    else:
        state["channels"] = [_to_jsonable(channel) for channel in channels]

    return state


def _build_state(
    iface: Any,
    tracker: DashboardTracker,
    started_at: float,
    target: str,
    show_secrets: bool,
    storage_probe_path: Optional[str],
    revision_info: Dict[str, str],
) -> Dict[str, Any]:
    nodes = _collect_nodes(iface)
    tracker_data = tracker.snapshot(nodes["by_id"])
    node_saved_counts = tracker.load_node_saved_counts()
    for row in nodes["rows"]:
        stats = node_saved_counts.get(str(row.get("id") or ""), {})
        row["saved_packets"] = int(stats.get("saved_packets") or 0)
        row["saved_points"] = int(stats.get("saved_points") or 0)
        row["saved_last_seen"] = stats.get("saved_last_seen")

    my_info = _to_jsonable(getattr(iface, "myInfo", None))
    metadata = _to_jsonable(getattr(iface, "metadata", None))

    local_state: Dict[str, Any]
    local_error: Optional[str] = None
    try:
        local_state = _collect_local_state(iface)
    except Exception as exc:
        local_state = {}
        local_error = str(exc)

    modem_preset = None
    try:
        modem_preset = (
            (local_state.get("local_config") or {})
            .get("lora", {})
            .get("modem_preset")
        )
    except Exception:
        modem_preset = None

    state = {
        "generated_at": _utc_now(),
        "summary": {
            "target": target,
            "uptime_seconds": int(max(0, time.time() - started_at)),
            "node_count": len(nodes["rows"]),
            "nodes_with_position": nodes["with_position_count"],
            "live_packet_count": tracker_data["live_packet_count"],
            "edge_count": len(tracker_data["edges"]),
            "real_edge_count": tracker_data["real_edge_count"],
            "recent_packet_buffer": len(tracker_data["recent_packets"]),
            "modem_preset": modem_preset,
            "disk": _disk_space_info(storage_probe_path),
            "revision": revision_info,
        },
        "my_info": my_info,
        "metadata": metadata,
        "local_state": local_state,
        "local_state_error": local_error,
        "nodes": nodes["rows"],
        "nodes_full": nodes["full"],
        "traffic": {
            "edges": tracker_data["edges"],
            "port_counts": tracker_data["port_counts"],
            "recent_packets": tracker_data["recent_packets"],
            "recent_chat": tracker_data["recent_chat"],
        },
    }

    if not show_secrets:
        state = _redact_secrets(state)

    return state


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
    safety_label = "Secrets visible" if show_secrets else "Secrets redacted"
    history_label = "History: off"
    if history_enabled:
        history_label = (
            f"History: on ({history_retention_days}d retention, {history_max_rows} rows max)"
        )
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Meshtastic Dashboard</title>
  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    crossorigin=""
  />
  <style>
    :root {{
      --bg: #f3f7f1;
      --ink: #112015;
      --panel: #ffffff;
      --line: #c6d6c0;
      --accent: #2f855a;
      --accent-2: #1f6f53;
      --danger: #c53030;
      --muted: #5e6e64;
      --shadow: 0 10px 24px rgba(18, 40, 20, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0;
      padding: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 20% -10%, #d7ead3 0, transparent 45%),
        radial-gradient(circle at 80% 0%, #d0e6d4 0, transparent 40%),
        var(--bg);
      min-height: 100%;
    }}
    .topbar {{
      padding: 10px 14px;
      background: linear-gradient(100deg, #173d2d, #2d6f50);
      color: #f4fff7;
      box-shadow: var(--shadow);
      position: sticky;
      top: 0;
      z-index: 100;
    }}
    .topbar h1 {{ margin: 0; font-size: 16px; letter-spacing: 0.1px; }}
    .topbar .sub {{
      margin-top: 2px;
      font-size: 11px;
      opacity: 0.95;
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 6px;
    }}
    .topbar .sub .sub-text {{
      margin-right: 2px;
    }}
    .workspace-shell {{
      --rail-width: 72px;
      --chat-panel-width: 250px;
      display: grid;
      grid-template-columns: var(--rail-width) 0 minmax(0, 1fr);
      gap: 8px;
      padding: 8px;
      align-items: start;
    }}
    .workspace-shell.chat-panel-open {{
      grid-template-columns: var(--rail-width) minmax(190px, var(--chat-panel-width)) minmax(0, 1fr);
    }}
    .workspace-main {{
      min-width: 0;
    }}
    .teams-rail {{
      position: sticky;
      top: 84px;
      height: calc(100vh - 96px);
      min-height: 420px;
      border: 1px solid #c6d6c0;
      border-radius: 10px;
      background: #eef6ee;
      box-shadow: var(--shadow);
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding: 8px 6px;
      overflow-y: auto;
    }}
    .teams-rail-title {{
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 0.35px;
      color: #355445;
      text-transform: uppercase;
      text-align: center;
      margin-bottom: 2px;
    }}
    .rail-btn {{
      border: 1px solid #c4d8c6;
      background: #f4faf3;
      color: #234735;
      border-radius: 8px;
      padding: 6px 4px;
      font-size: 10px;
      line-height: 1.2;
      text-align: center;
      cursor: pointer;
    }}
    .rail-btn:hover {{
      background: #e7f3eb;
    }}
    .rail-btn.active {{
      background: #2f855a;
      border-color: #256f4a;
      color: #effff4;
      font-weight: 700;
    }}
    .chat-left-panel {{
      position: sticky;
      top: 84px;
      height: calc(100vh - 96px);
      min-height: 420px;
      border: 1px solid #c6d6c0;
      border-radius: 10px;
      background: #f6fbf5;
      box-shadow: var(--shadow);
      display: flex;
      flex-direction: column;
      min-width: 0;
      overflow: hidden;
    }}
    .chat-left-panel[hidden] {{
      display: none !important;
    }}
    .chat-left-head {{
      border-bottom: 1px solid #d2e1d0;
      background: #edf6ec;
      padding: 8px 10px 7px 10px;
    }}
    .chat-left-title {{
      font-size: 11px;
      font-weight: 700;
      color: #274935;
      letter-spacing: 0.15px;
      text-transform: uppercase;
    }}
    .chat-left-sub {{
      font-size: 10px;
      color: #4a6958;
      margin-top: 3px;
    }}
    .chat-left-section {{
      border-bottom: 1px solid #d9e7d6;
      padding: 7px 6px 6px 6px;
      background: #f7fcf7;
    }}
    .chat-left-section:last-child {{
      border-bottom: none;
      flex: 1 1 auto;
      min-height: 0;
      display: flex;
      flex-direction: column;
    }}
    .chat-left-label {{
      font-size: 10px;
      color: #466656;
      text-transform: uppercase;
      letter-spacing: 0.2px;
      margin: 0 0 5px 2px;
      font-weight: 700;
    }}
    .chat-channel-list {{
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}
    .chat-channel-item {{
      border: 1px solid #c7dac5;
      background: #eef8ef;
      color: #214434;
      border-radius: 7px;
      padding: 6px 7px;
      font-size: 10px;
      line-height: 1.15;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 6px;
      min-width: 0;
      text-align: left;
    }}
    .chat-channel-item:hover {{
      background: #e4f2e7;
    }}
    .chat-channel-item.active {{
      background: #d8efe1;
      border-color: #99c5aa;
      color: #173e2b;
      font-weight: 700;
    }}
    .chat-channel-name {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .chat-channel-meta {{
      font-size: 9px;
      color: #5f7b6c;
      opacity: 0.92;
      white-space: nowrap;
      flex: 0 0 auto;
    }}
    .chat-left-panel .chat-member-list {{
      padding: 6px;
      flex: 1 1 auto;
    }}
    .layout {{
      --split-left-pct: 64%;
      --splitter-size: 8px;
      --split-top-px: 430px;
      --split-mid-px: 250px;
      --split-low-px: 240px;
      display: grid;
      gap: 8px;
      padding: 0;
      grid-template-columns: minmax(380px, var(--split-left-pct)) var(--splitter-size) minmax(320px, 1fr);
      grid-template-rows:
        auto
        minmax(240px, var(--split-top-px))
        var(--splitter-size)
        minmax(180px, var(--split-mid-px))
        var(--splitter-size)
        minmax(260px, 380px)
        auto
        minmax(160px, var(--split-low-px))
        var(--splitter-size)
        auto;
      align-items: stretch;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      box-shadow: var(--shadow);
      overflow: hidden;
      scroll-margin-top: 84px;
    }}
    .card h2 {{
      margin: 0;
      padding: 8px 10px;
      font-size: 13px;
      border-bottom: 1px solid var(--line);
      background: #f8fbf7;
    }}
    .card .body {{
      padding: 8px 10px;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(115px, 1fr));
      gap: 6px;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 6px 7px;
      background: #fcfffc;
    }}
    .metric .label {{ font-size: 10px; color: var(--muted); }}
    .metric .value {{ font-size: 15px; font-weight: 700; margin-top: 2px; line-height: 1.1; }}
    .summary {{ grid-column: 1 / span 3; grid-row: 1; }}
    .map {{
      grid-column: 1 / span 3;
      grid-row: 6;
      display: flex;
      flex-direction: column;
      min-height: 0;
    }}
    .map .body {{
      padding: 8px 10px;
      display: flex;
      flex: 1 1 auto;
      min-height: 0;
    }}
    .map-frame {{
      flex: 1 1 auto;
      width: 100%;
      max-width: none;
      margin: 0;
      min-height: 260px;
      border: 1px solid #d7e5d2;
      border-radius: 8px;
      overflow: hidden;
      background: #eef6ee;
    }}
    .map-frame.map-wheel-active {{
      border-color: #8ab79b;
      box-shadow: inset 0 0 0 2px rgba(138, 183, 155, 0.55);
    }}
    #map {{
      width: 100%;
      height: 100%;
      min-height: 0;
    }}
    .chat {{
      grid-column: 1 / span 3;
      grid-row: 2;
      display: flex;
      flex-direction: column;
      min-height: 0;
    }}
    .map-data {{
      grid-column: 1 / span 3;
      grid-row: 7;
      display: flex;
      flex-direction: column;
      min-height: 0;
    }}
    .map-data .body {{
      flex: 1 1 auto;
      min-height: 0;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}
    .map-data-live, .map-data-node {{
      min-height: 0;
      display: flex;
      flex-direction: column;
      gap: 8px;
      flex: 1 1 auto;
    }}
    .map-data-live[hidden], .map-data-node[hidden] {{
      display: none !important;
    }}
    .history-caption {{
      font-size: 12px;
      color: #3e5a46;
      line-height: 1.35;
    }}
    .history-tabs {{
      display: flex;
      gap: 6px;
      border-bottom: 1px solid #d7e5d2;
      padding-bottom: 6px;
    }}
    .history-tab-btn {{
      border: 1px solid #c2d8c7;
      background: #f3faf5;
      color: #1f5d40;
      border-radius: 999px;
      font-size: 11px;
      padding: 4px 10px;
      cursor: pointer;
    }}
    .history-tab-btn.active {{
      background: #dff1e6;
      border-color: #87b99a;
      color: #14442d;
      font-weight: 600;
    }}
    .history-panel[hidden] {{
      display: none !important;
    }}
    #signal-chart-wrap {{
      position: relative;
      width: 100%;
      min-height: 220px;
      height: 220px;
      border: 1px solid #d7e5d2;
      border-radius: 8px;
      background: linear-gradient(180deg, #fbfffc 0%, #eef8f1 100%);
      overflow: hidden;
    }}
    #signal-chart {{
      width: 100%;
      height: 100%;
      display: block;
    }}
    .signal-empty {{
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #5d7467;
      font-size: 12px;
      text-align: center;
      padding: 10px;
      background: rgba(250, 255, 251, 0.9);
    }}
    .signal-empty[hidden] {{
      display: none !important;
    }}
    .signal-legend {{
      margin-top: 6px;
      font-size: 11px;
      color: #284a37;
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }}
    .legend-chip {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }}
    .legend-chip::before {{
      content: "";
      width: 11px;
      height: 2px;
      border-radius: 1px;
      background: currentColor;
    }}
    .overview-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 6px;
    }}
    .overview-item {{
      border: 1px solid #d7e5d2;
      border-radius: 8px;
      background: #f9fdf9;
      padding: 6px 7px;
    }}
    .overview-item .k {{
      color: #5e6e64;
      font-size: 10px;
      text-transform: uppercase;
    }}
    .overview-item .v {{
      margin-top: 2px;
      font-size: 12px;
      font-weight: 600;
      color: #193a28;
      line-height: 1.2;
    }}
    .nodes {{
      grid-column: 1 / span 3;
      grid-row: 4;
      display: flex;
      flex-direction: column;
      min-height: 0;
    }}
    .nodes .body {{
      flex: 1 1 auto;
      min-height: 0;
    }}
    .nodes .scroll {{
      max-height: none;
      min-height: 0;
    }}
    .packets {{ grid-column: 1; grid-row: 8; }}
    .raw {{ grid-column: 3; grid-row: 8; }}
    .console {{ grid-column: 1 / span 3; grid-row: 10; }}
    .splitter {{
      grid-column: 2;
      position: relative;
      border-radius: 8px;
      border: 1px solid #d1e0cb;
      background: linear-gradient(180deg, #f4faf3, #edf5ea);
      cursor: col-resize;
      touch-action: none;
      user-select: none;
      min-width: 6px;
    }}
    .splitter[data-row="8"] {{ grid-row: 8; }}
    .splitter::before {{
      content: "";
      position: absolute;
      left: 50%;
      top: 8px;
      bottom: 8px;
      width: 2px;
      transform: translateX(-50%);
      background: #b8cab9;
      border-radius: 1px;
    }}
    .splitter:hover::before, .splitter.active::before {{
      background: #2f855a;
    }}
    .hsplitter {{
      grid-column: 1 / span 3;
      position: relative;
      border-radius: 8px;
      border: 1px solid #d1e0cb;
      background: linear-gradient(90deg, #f4faf3, #edf5ea);
      cursor: row-resize;
      touch-action: none;
      user-select: none;
      min-height: 6px;
    }}
    .hsplitter[data-target="top"] {{ grid-row: 3; }}
    .hsplitter[data-target="mid"] {{ grid-row: 5; }}
    .hsplitter[data-target="low"] {{ grid-row: 9; }}
    .hsplitter::before {{
      content: "";
      position: absolute;
      left: 8px;
      right: 8px;
      top: 50%;
      height: 2px;
      transform: translateY(-50%);
      background: #b8cab9;
      border-radius: 1px;
    }}
    .hsplitter:hover::before, .hsplitter.active::before {{
      background: #2f855a;
    }}
    body.resizing-panels-x, body.resizing-panels-x * {{
      cursor: col-resize !important;
      user-select: none !important;
    }}
    body.resizing-panels-y, body.resizing-panels-y * {{
      cursor: row-resize !important;
      user-select: none !important;
    }}
    .layout.view-chat {{
      grid-template-rows:
        auto
        minmax(240px, var(--split-top-px))
        var(--splitter-size)
        minmax(200px, var(--split-mid-px))
        var(--splitter-size)
        minmax(220px, var(--split-low-px));
    }}
    .layout.view-chat .chat {{ grid-row: 2; }}
    .layout.view-chat .map {{ grid-row: 4; }}
    .layout.view-chat .map-data {{ grid-row: 6; }}
    .layout.view-chat .nodes,
    .layout.view-chat .packets,
    .layout.view-chat .raw,
    .layout.view-chat .console,
    .layout.view-chat .splitter,
    .layout.view-chat .hsplitter[data-target="low"] {{
      display: none !important;
    }}
    .layout.view-chat .hsplitter[data-target="top"] {{ grid-row: 3; }}
    .layout.view-chat .hsplitter[data-target="mid"] {{ grid-row: 5; }}

    .layout.view-network {{
      grid-template-rows:
        auto
        minmax(220px, var(--split-top-px))
        var(--splitter-size)
        minmax(220px, var(--split-mid-px))
        var(--splitter-size)
        minmax(220px, var(--split-low-px));
    }}
    .layout.view-network .nodes {{ grid-row: 2; }}
    .layout.view-network .map {{ grid-row: 4; }}
    .layout.view-network .map-data {{ grid-row: 6; }}
    .layout.view-network .chat,
    .layout.view-network .packets,
    .layout.view-network .raw,
    .layout.view-network .console,
    .layout.view-network .splitter,
    .layout.view-network .hsplitter[data-target="low"] {{
      display: none !important;
    }}
    .layout.view-network .hsplitter[data-target="top"] {{ grid-row: 3; }}
    .layout.view-network .hsplitter[data-target="mid"] {{ grid-row: 5; }}

    .layout.view-packets {{
      grid-template-rows:
        auto
        minmax(240px, var(--split-top-px))
        var(--splitter-size)
        minmax(170px, var(--split-low-px));
    }}
    .layout.view-packets .packets {{
      grid-column: 1 / span 3;
      grid-row: 2;
    }}
    .layout.view-packets .console {{
      grid-column: 1 / span 3;
      grid-row: 4;
    }}
    .layout.view-packets .chat,
    .layout.view-packets .nodes,
    .layout.view-packets .map,
    .layout.view-packets .map-data,
    .layout.view-packets .raw,
    .layout.view-packets .splitter,
    .layout.view-packets .hsplitter[data-target="top"],
    .layout.view-packets .hsplitter[data-target="mid"] {{
      display: none !important;
    }}
    .layout.view-packets .hsplitter[data-target="low"] {{ grid-row: 3; }}

    .layout.view-data {{
      grid-template-rows:
        auto
        minmax(240px, var(--split-top-px))
        var(--splitter-size)
        minmax(170px, var(--split-low-px));
    }}
    .layout.view-data .raw {{
      grid-column: 1 / span 3;
      grid-row: 2;
    }}
    .layout.view-data .console {{
      grid-column: 1 / span 3;
      grid-row: 4;
    }}
    .layout.view-data .chat,
    .layout.view-data .nodes,
    .layout.view-data .map,
    .layout.view-data .map-data,
    .layout.view-data .packets,
    .layout.view-data .splitter,
    .layout.view-data .hsplitter[data-target="top"],
    .layout.view-data .hsplitter[data-target="mid"] {{
      display: none !important;
    }}
    .layout.view-data .hsplitter[data-target="low"] {{ grid-row: 3; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 11px;
    }}
    th, td {{
      text-align: left;
      border-bottom: 1px solid #e7efe4;
      padding: 4px 5px;
      vertical-align: middle;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    th {{
      position: sticky;
      top: 0;
      z-index: 2;
      background: #f4faf3;
      color: #204231;
      font-size: 10px;
      letter-spacing: 0.2px;
      text-transform: uppercase;
    }}
    th.sortable {{
      cursor: pointer;
      user-select: none;
    }}
    th.sortable::after {{
      content: " \2195";
      font-size: 9px;
      opacity: 0.35;
    }}
    th.sortable.sorted-asc::after {{
      content: " \25B2";
      opacity: 0.9;
    }}
    th.sortable.sorted-desc::after {{
      content: " \25BC";
      opacity: 0.9;
    }}
    #nodes-table tbody tr.node-selectable {{
      cursor: pointer;
    }}
    #nodes-table tbody tr.node-selectable:hover {{
      background: #edf8f1;
    }}
    #nodes-table tbody tr.selected-node {{
      background: #d8efe1;
    }}
    .mono {{ font-family: "IBM Plex Mono", "Consolas", "Menlo", monospace; }}
    #nodes-table th:nth-child(1), #nodes-table td:nth-child(1) {{ width: 14%; }}
    #nodes-table th:nth-child(2), #nodes-table td:nth-child(2) {{ width: 13%; }}
    #nodes-table th:nth-child(3), #nodes-table td:nth-child(3) {{ width: 18%; }}
    #nodes-table th:nth-child(4), #nodes-table td:nth-child(4) {{ width: 16%; }}
    #nodes-table th:nth-child(5), #nodes-table td:nth-child(5) {{ width: 6%; }}
    #nodes-table th:nth-child(6), #nodes-table td:nth-child(6) {{ width: 6%; }}
    #nodes-table th:nth-child(7), #nodes-table td:nth-child(7) {{ width: 7%; }}
    #nodes-table th:nth-child(8), #nodes-table td:nth-child(8) {{ width: 10%; }}
    #nodes-table th:nth-child(9), #nodes-table td:nth-child(9) {{ width: 10%; }}
    .chat .body {{
      display: flex;
      flex-direction: column;
      flex: 1;
      min-height: 0;
      gap: 7px;
    }}
    .chat-shell {{
      display: block;
      flex: 1 1 auto;
      min-height: 0;
      height: 100%;
    }}
    .chat-member-pane {{
      grid-area: members;
      grid-column: 2;
      border: 1px solid #d6e5d2;
      border-radius: 7px;
      background: #f8fcf8;
      min-height: 0;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }}
    .chat-member-list {{
      padding: 4px;
      overflow: auto;
      min-height: 0;
      display: flex;
      flex-direction: column;
      gap: 3px;
    }}
    .chat-member-item {{
      display: grid;
      grid-template-columns: 11px minmax(0, 1fr);
      gap: 6px;
      align-items: center;
      border: 1px solid #c7dac5;
      background: #ecf7ef;
      color: #204233;
      border-radius: 6px;
      padding: 3px 6px;
      font-size: 10px;
      line-height: 1.2;
      cursor: pointer;
    }}
    .chat-member-item:hover {{
      background: #e2f0e7;
    }}
    .chat-member-item.status-warn {{
      background: #fff9e7;
      color: #5d4a1b;
      border-color: #ecd89c;
    }}
    .chat-member-item.status-stale {{
      background: #fff0f0;
      color: #6a3333;
      border-color: #e6b5b5;
    }}
    .chat-member-item.status-unknown {{
      background: #f2f5f2;
      color: #607268;
      border-color: #d8e3d8;
    }}
    .chat-member-item.selected-node {{
      background: #d8efe1;
      border-color: #99c5aa;
      color: #16402c;
    }}
    .chat-member-status {{
      width: 10px;
      text-align: center;
      font-size: 10px;
      font-weight: 700;
      line-height: 1;
      color: #2aa85a;
    }}
    .chat-member-status.status-online {{
      color: #2aa85a;
    }}
    .chat-member-status.status-warn {{
      color: #d2a022;
    }}
    .chat-member-status.status-stale {{
      color: #d15757;
    }}
    .chat-member-status.status-unknown {{
      color: #99aaa0;
    }}
    .chat-member-main {{
      display: flex;
      flex-direction: column;
      min-width: 0;
      gap: 1px;
    }}
    .chat-member-name {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 100%;
      color: inherit;
    }}
    .chat-member-name.status-warn {{
      color: #6d541d;
    }}
    .chat-member-name.status-stale {{
      color: #7b3d3d;
    }}
    .chat-member-name.status-unknown {{
      color: #667a70;
      opacity: 0.8;
    }}
    .chat-member-id {{
      font-size: 9px;
      color: #6c8578;
      opacity: 0.46;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 100%;
    }}
    .chat-main-pane {{
      display: grid;
      grid-template-rows: minmax(0, 1fr) auto auto;
      row-gap: 6px;
      min-height: 0;
      overflow: hidden;
    }}
    .chat-log-scroll {{
      grid-row: 1;
      flex: 1 1 auto;
      max-height: none;
      min-height: 0;
      display: flex;
      flex-direction: column;
    }}
    .chat-feed {{
      display: flex;
      flex-direction: column;
      gap: 5px;
      width: 100%;
      min-height: 0;
      margin-top: auto;
    }}
    .chat-feed-item {{
      width: 100%;
      box-sizing: border-box;
      border: 1px solid #d7e6d6;
      border-radius: 8px;
      padding: 6px 8px;
      background: #fbfefb;
      color: #163523;
    }}
    .chat-feed-item.chat-selectable {{
      cursor: pointer;
    }}
    .chat-feed-item.chat-selectable:hover {{
      background: #eef8f0;
      border-color: #c2dbc7;
    }}
    .chat-feed-item.selected-node {{
      background: #d8efe1;
      border-color: #99c5aa;
    }}
    .chat-feed-meta {{
      display: flex;
      align-items: baseline;
      flex-wrap: wrap;
      gap: 6px;
      font-size: 10px;
      color: #5a7462;
      line-height: 1.2;
      margin-bottom: 3px;
    }}
    .chat-feed-arrow {{
      color: #6e8c78;
      opacity: 0.75;
    }}
    .chat-feed-time {{
      margin-left: auto;
      font-size: 10px;
      color: #6a8572;
      white-space: nowrap;
    }}
    .chat-feed-hops {{
      font-size: 10px;
      color: #3f6b52;
      background: #edf6ef;
      border: 1px solid #c9dece;
      border-radius: 999px;
      padding: 1px 7px;
      line-height: 1.3;
      white-space: nowrap;
    }}
    .chat-feed-actions {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      margin-left: 2px;
    }}
    .chat-react-btn {{
      border: 1px solid #bdd4c1;
      background: #f5fbf6;
      color: #26543a;
      border-radius: 999px;
      padding: 1px 7px;
      font-size: 11px;
      line-height: 1.4;
      cursor: pointer;
      white-space: nowrap;
    }}
    .chat-react-btn:hover {{
      background: #e8f4eb;
      border-color: #9ec2a8;
    }}
    .chat-feed-text {{
      font-size: 12px;
      color: #173827;
      line-height: 1.35;
      white-space: normal;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .chat-reaction-row {{
      margin-top: 5px;
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
      align-items: center;
    }}
    .chat-reaction-chip {{
      border: 1px solid #b9d2bf;
      background: #ecf7ef;
      color: #1f4e35;
      border-radius: 999px;
      padding: 1px 8px;
      font-size: 11px;
      line-height: 1.3;
      cursor: pointer;
      white-space: nowrap;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }}
    .chat-reaction-chip:hover {{
      background: #dff0e4;
      border-color: #94bd9f;
    }}
    .chat-reaction-count {{
      font-size: 10px;
      font-weight: 700;
      color: #355f48;
    }}
    .chat-feed-empty {{
      border: 1px dashed #d2e2d4;
      border-radius: 8px;
      padding: 10px;
      font-size: 12px;
      color: #5d7566;
      background: #f8fcf8;
    }}
    .chat-composer {{
      grid-row: 3;
      position: relative;
      display: flex;
      gap: 6px;
      align-items: center;
      border-top: 1px solid #d8e7d3;
      padding-top: 6px;
      min-height: 0;
    }}
    #chat-input {{
      flex: 1;
      min-width: 0;
      border: 1px solid #c2d8c7;
      border-radius: 7px;
      padding: 6px 8px;
      font-size: 12px;
      color: #183223;
      background: #f9fdf9;
    }}
    #chat-input:focus {{
      outline: 2px solid #9ac5aa;
      outline-offset: 0;
      background: #ffffff;
    }}
    #chat-send-btn {{
      border: 1px solid #9cc9ad;
      background: #e3f4ea;
      color: #184a32;
      border-radius: 8px;
      padding: 6px 12px;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
    }}
    #chat-send-btn:hover {{
      background: #d7ecdf;
    }}
    #chat-send-btn:disabled {{
      opacity: 0.6;
      cursor: default;
    }}
    #chat-emoji-btn {{
      border: 1px solid #9cc9ad;
      background: #f1f9f4;
      color: #184a32;
      border-radius: 8px;
      padding: 6px 8px;
      font-size: 13px;
      line-height: 1;
      cursor: pointer;
      white-space: nowrap;
    }}
    #chat-emoji-btn:hover {{
      background: #e6f2ea;
    }}
    #chat-emoji-btn:disabled {{
      opacity: 0.6;
      cursor: default;
    }}
    .chat-emoji-panel {{
      position: absolute;
      right: 58px;
      bottom: calc(100% + 6px);
      width: min(320px, 92%);
      border: 1px solid #c9dbcc;
      border-radius: 8px;
      background: #fbfefb;
      box-shadow: 0 8px 20px rgba(16, 36, 24, 0.18);
      padding: 6px;
      z-index: 9;
    }}
    .chat-emoji-panel[hidden] {{
      display: none !important;
    }}
    .chat-emoji-grid {{
      display: grid;
      grid-template-columns: repeat(8, minmax(0, 1fr));
      gap: 4px;
    }}
    .chat-emoji-item {{
      border: 1px solid #d9e7da;
      border-radius: 6px;
      background: #ffffff;
      padding: 5px 4px;
      font-size: 16px;
      line-height: 1;
      cursor: pointer;
    }}
    .chat-emoji-item:hover {{
      background: #ecf5ef;
      border-color: #b4d0bd;
    }}
    .chat-send-status {{
      grid-row: 2;
      min-height: 0;
      font-size: 10px;
      color: #446551;
      line-height: 1.25;
    }}
    .chat-send-status:empty {{
      display: none;
    }}
    .chat-send-status.error {{
      color: #b43b3b;
      font-weight: 600;
    }}
    .chat-endpoint {{
      display: inline-flex;
      align-items: baseline;
      gap: 5px;
      max-width: 100%;
      min-width: 0;
    }}
    .chat-name {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 100%;
    }}
    .chat-name.status-warn {{
      color: #7a6322;
    }}
    .chat-name.status-stale {{
      color: #8a4545;
      opacity: 0.9;
    }}
    .chat-name.status-unknown {{
      color: #667a70;
      opacity: 0.72;
    }}
    .chat-id-bg {{
      font-size: 9px;
      color: #6c8578;
      opacity: 0.5;
      letter-spacing: 0.12px;
      white-space: nowrap;
    }}
    .chat-id-bg.status-warn {{
      color: #7f6b2d;
      opacity: 0.45;
    }}
    .chat-id-bg.status-stale {{
      color: #875151;
      opacity: 0.4;
    }}
    .chat-id-bg.status-unknown {{
      opacity: 0.36;
    }}
    .scroll {{
      max-height: 300px;
      overflow: auto;
    }}
    .chat-log-scroll.scroll {{
      max-height: none;
      height: auto;
      overflow: auto;
    }}
    .scroll.wheel-scroll-active,
    #live-console.wheel-scroll-active,
    details pre.wheel-scroll-active {{
      outline: 2px solid #8ab79b;
      outline-offset: -2px;
    }}
    .pill {{
      display: inline-block;
      font-size: 10px;
      border-radius: 999px;
      padding: 2px 7px;
      border: 1px solid #c2d8c7;
      background: #f0f8f2;
      margin-left: 6px;
      color: #1e5e40;
    }}
    .pill.selection-pill {{
      border-color: #a8d2b6;
      background: #e7f6ec;
      color: #194c33;
    }}
    .selection-btn {{
      margin-left: 6px;
      font-size: 10px;
      line-height: 1.2;
      border: 1px solid #c2d8c7;
      color: #194c33;
      background: #f0f8f2;
      border-radius: 999px;
      padding: 3px 8px;
      cursor: pointer;
    }}
    .selection-btn:hover {{
      background: #e1f2e7;
    }}
    .selection-btn:disabled {{
      opacity: 0.55;
      cursor: default;
    }}
    .disk-meter {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin-left: auto;
      padding: 2px 7px;
      border-radius: 999px;
      border: 1px solid rgba(226, 248, 233, 0.35);
      background: rgba(8, 30, 18, 0.2);
    }}
    .disk-label {{
      font-size: 10px;
      color: #e7fff0;
      white-space: nowrap;
    }}
    .disk-track {{
      width: 118px;
      height: 8px;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(231, 255, 240, 0.28);
    }}
    .disk-fill {{
      width: 0%;
      height: 100%;
      border-radius: 999px;
      background: #66dc8a;
      transition: width 220ms ease, background-color 220ms ease;
    }}
    .disk-fill.warn {{
      background: #f4c652;
    }}
    .disk-fill.danger {{
      background: #ff7676;
    }}
    .topbar .sub .revision-text {{
      color: #e7fff0;
      font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
      letter-spacing: 0.1px;
    }}
    .warn {{ color: var(--danger); font-weight: 600; }}
    .console .body {{
      padding: 8px 10px;
    }}
    .console-controls {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 8px;
      font-size: 11px;
      color: #294735;
    }}
    .console-controls button {{
      border: 1px solid #c2d8c7;
      background: #f0f8f2;
      color: #1e5e40;
      border-radius: 6px;
      font-size: 11px;
      padding: 4px 8px;
      cursor: pointer;
    }}
    .console-controls button:hover {{
      background: #e1f2e7;
    }}
    #live-console {{
      margin: 0;
      background: #0e1f16;
      color: #cbffde;
      border-radius: 6px;
      padding: 8px;
      min-height: 180px;
      max-height: 280px;
      overflow: auto;
      font-size: 10px;
      line-height: 1.3;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    details {{
      border: 1px solid #d7e5d2;
      border-radius: 6px;
      padding: 6px 8px;
      margin-bottom: 6px;
      background: #fcfffc;
    }}
    summary {{ cursor: pointer; font-weight: 600; }}
    pre {{
      margin: 10px 0 0 0;
      background: #0e1f16;
      color: #cbffde;
      border-radius: 6px;
      padding: 8px;
      max-height: 200px;
      overflow: auto;
      font-size: 10px;
      line-height: 1.35;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    @media (max-width: 1100px) {{
      .workspace-shell {{
        grid-template-columns: 1fr;
        grid-template-rows: auto auto auto;
        gap: 6px;
        padding: 6px;
      }}
      .teams-rail {{
        position: static;
        height: auto;
        min-height: 0;
        flex-direction: row;
        align-items: center;
        overflow-x: auto;
        overflow-y: hidden;
        padding: 6px;
      }}
      .teams-rail-title {{
        display: none;
      }}
      .rail-btn {{
        min-width: 74px;
      }}
      .workspace-shell.chat-panel-open {{
        grid-template-columns: 1fr;
      }}
      .chat-left-panel {{
        position: static;
        height: auto;
        min-height: 0;
        max-height: 220px;
      }}
      .layout {{
        grid-template-columns: 1fr;
        grid-template-rows: auto;
      }}
      .splitter, .hsplitter {{ display: none; }}
      .summary, .map, .map-data, .nodes, .chat, .packets, .raw, .console {{ grid-column: 1; grid-row: auto; }}
      .map-frame {{ max-width: none; }}
      .nodes .scroll {{ max-height: 360px; }}
    }}
    @media (max-width: 760px) {{
      .chat-left-panel {{
        max-height: 180px;
      }}
      .rail-btn {{
        min-width: 68px;
        font-size: 9px;
      }}
    }}
  </style>
</head>
<body>
  <div class="topbar">
    <h1>Meshtastic Deep Dashboard</h1>
    <div class="sub">
      <span id="revision-text" class="sub-text revision-text" title="{revision_title}">{revision_label}</span>
      <span class="pill">{safety_label}</span>
      <span class="pill">Packet buffer: {packet_limit}</span>
      <span class="pill">{history_label}</span>
      <span class="pill">Refresh: {refresh_ms} ms</span>
      <span class="pill selection-pill" id="selected-node-pill">Selected: none</span>
      <button id="clear-selection-btn" class="selection-btn" type="button" disabled>Clear</button>
      <span id="disk-meter" class="disk-meter" title="Disk free on dashboard host">
        <span id="disk-label" class="disk-label">Disk free: n/a</span>
        <span class="disk-track"><span id="disk-fill" class="disk-fill"></span></span>
      </span>
    </div>
  </div>

  <div class="workspace-shell">
    <aside class="teams-rail" aria-label="Dashboard views">
      <div class="teams-rail-title">Views</div>
      <button class="rail-btn active" data-view="chat" type="button" title="Teams-style chat workspace">Chat</button>
      <button class="rail-btn" data-view="network" type="button" title="Topology, nodes, and links">Network</button>
      <button class="rail-btn" data-view="packets" type="button" title="Recent packet stream">Packets</button>
      <button class="rail-btn" data-view="data" type="button" title="Raw node/config views">Data</button>
      <button class="rail-btn" data-view="all" type="button" title="Show every panel">All</button>
    </aside>
    <aside id="chat-left-panel" class="chat-left-panel" hidden aria-label="Chat roster">
      <div class="chat-left-head">
        <div class="chat-left-title">Chat Navigator</div>
        <div id="chat-left-sub" class="chat-left-sub">Loading…</div>
      </div>
      <div class="chat-left-section">
        <div class="chat-left-label">Channels</div>
        <div id="chat-channel-list" class="chat-channel-list"></div>
      </div>
      <div class="chat-left-section">
        <div id="chat-users-title" class="chat-left-label">Users</div>
        <div id="chat-room-list" class="chat-member-list"></div>
      </div>
    </aside>
    <main class="workspace-main">
  <div id="dashboard-layout" class="layout view-chat">
    <section class="card summary">
      <h2>Summary</h2>
      <div class="body">
        <div class="metrics">
          <div class="metric"><div class="label">Target</div><div class="value" id="m-target">n/a</div></div>
          <div class="metric"><div class="label">Known Nodes</div><div class="value" id="m-nodes">0</div></div>
          <div class="metric"><div class="label">Nodes With Position</div><div class="value" id="m-pos-nodes">0</div></div>
          <div class="metric"><div class="label">Live Packets</div><div class="value" id="m-live-packets">0</div></div>
          <div class="metric"><div class="label">Directed Links</div><div class="value" id="m-links">0</div></div>
          <div class="metric"><div class="label">LoRa Preset</div><div class="value" id="m-modem-preset">n/a</div></div>
          <div class="metric"><div class="label">Uptime (s)</div><div class="value" id="m-uptime">0</div></div>
        </div>
        <div style="margin-top:10px; font-size:12px; color:#3e5a46;">
          Updated: <span id="updated-at">n/a</span>
          <span id="local-state-error" class="warn"></span>
        </div>
      </div>
    </section>

    <section class="card chat">
      <h2>MediumFast Chat</h2>
      <div class="body">
        <div id="chat-caption" style="font-size:12px;color:#3e5a46;margin-bottom:8px;">
          Showing decoded text messages from recent packets.
        </div>
        <div class="chat-shell">
          <div class="chat-main-pane">
            <div class="scroll chat-log-scroll">
              <div id="chat-feed" class="chat-feed"></div>
            </div>
            <div class="chat-composer">
              <input
                id="chat-input"
                type="text"
                maxlength="280"
                placeholder="Message the room (^all)..."
                autocomplete="off"
              />
              <button id="chat-emoji-btn" type="button" title="Insert emoji" aria-label="Insert emoji" aria-expanded="false">🙂</button>
              <button id="chat-send-btn" type="button">Send</button>
              <div id="chat-emoji-panel" class="chat-emoji-panel" hidden></div>
            </div>
            <div id="chat-send-status" class="chat-send-status"></div>
          </div>
        </div>
      </div>
    </section>

    <section class="card map">
      <h2 id="map-card-title">Network Map</h2>
      <div class="body">
        <div class="map-frame">
          <div id="map"></div>
        </div>
      </div>
    </section>

    <div class="hsplitter" data-target="top" title="Drag to resize top and middle panels"></div>

    <section class="card nodes">
      <h2>Nodes</h2>
      <div class="body scroll">
        <table id="nodes-table">
            <thead>
              <tr>
              <th>Last Heard</th><th>ID</th><th>Name</th><th>HW</th><th>SNR</th><th>Hops</th><th>Battery</th><th>Saved</th><th>Pos</th>
              </tr>
            </thead>
          <tbody></tbody>
        </table>
      </div>
    </section>

    <section class="card map-data">
      <h2 id="map-data-title">Map Data</h2>
      <div class="body">
        <div id="map-data-live" class="map-data-live">
          <h3 style="margin:0 0 2px 0;font-size:13px;">Top Ports</h3>
          <div class="scroll" style="max-height:150px;">
            <table id="ports-table">
              <thead><tr><th>Port</th><th>Count</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
          <h3 style="margin:2px 0 2px 0;font-size:13px;">Top Links</h3>
          <div class="scroll" style="max-height:170px;">
            <table id="links-table">
              <thead><tr><th>From</th><th>To</th><th>Count</th><th>Hops</th><th>Status</th><th>Last</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
        </div>

        <div id="map-data-node" class="map-data-node" hidden>
          <div id="node-history-caption" class="history-caption">Select a node to view historical data.</div>
          <div class="history-tabs">
            <button class="history-tab-btn active" id="tab-btn-signal" data-tab="signal" type="button">Signal</button>
            <button class="history-tab-btn" id="tab-btn-overview" data-tab="overview" type="button">Overview</button>
          </div>
          <div id="tab-panel-signal" class="history-panel">
            <div id="signal-chart-wrap">
              <svg id="signal-chart" viewBox="0 0 900 220" preserveAspectRatio="none" aria-label="Node signal history"></svg>
              <div id="signal-empty" class="signal-empty" hidden>No historical signal points yet for this node.</div>
            </div>
            <div class="signal-legend">
              <span class="legend-chip" style="color:#1f6f53;">Avg SNR (dB)</span>
              <span class="legend-chip" style="color:#265d7b;">Avg RSSI (dBm)</span>
            </div>
          </div>
          <div id="tab-panel-overview" class="history-panel" hidden>
            <div id="node-history-overview" class="overview-grid"></div>
          </div>
        </div>
      </div>
    </section>

    <div class="hsplitter" data-target="mid" title="Drag to resize middle and lower panels"></div>

    <section class="card packets">
      <h2>Recent Packets</h2>
      <div class="body scroll">
        <table id="packets-table">
          <thead>
            <tr>
              <th>Captured</th><th>From</th><th>To</th><th>Port</th><th>SNR</th><th>RSSI</th><th>Text</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </section>

    <div class="splitter" data-row="8" title="Drag to resize packet/raw columns"></div>

    <section class="card raw">
      <h2>Raw Data</h2>
      <div class="body">
        <details><summary>my_info</summary><pre id="raw-my-info"></pre></details>
        <details><summary>metadata</summary><pre id="raw-metadata"></pre></details>
        <details><summary>local_config</summary><pre id="raw-local-config"></pre></details>
        <details><summary>module_config</summary><pre id="raw-module-config"></pre></details>
        <details><summary>channels</summary><pre id="raw-channels"></pre></details>
        <details><summary>nodes_full</summary><pre id="raw-nodes-full"></pre></details>
      </div>
    </section>

    <div class="hsplitter" data-target="low" title="Drag to resize lower panels and console"></div>

    <section class="card console">
      <h2>Realtime Console</h2>
      <div class="body">
        <div class="console-controls">
          <button id="console-clear-btn" type="button">Clear</button>
          <label><input id="console-autoscroll" type="checkbox" checked /> Auto-scroll</label>
        </div>
        <pre id="live-console"></pre>
      </div>
    </section>
  </div>
    </main>
  </div>

  <script
    src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    crossorigin=""
  ></script>
  <script>
    const refreshMs = {refresh_ms};
    const nodeHistoryHours = {node_history_hours};
    const nodeHistoryMaxPoints = {node_history_max_points};
    const map = L.map("map", {{
      preferCanvas: true,
      zoomAnimation: false,
      fadeAnimation: false,
      markerZoomAnimation: false,
      inertia: false,
      scrollWheelZoom: false,
    }}).setView([39.5, -98.35], 4);
    L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors"
    }}).addTo(map);

    const mapElement = document.getElementById("map");
    const mapFrameElement = mapElement ? mapElement.closest(".map-frame") : null;
    const nodeLayer = L.layerGroup().addTo(map);
    const edgeLayer = L.layerGroup().addTo(map);
    const nodeMarkers = new Map();
    const selectionStorageKey = "meshDashboardSelectedNodeId";
    const nodeNameCacheStorageKey = "meshDashboardNodeNameCacheV1";
    const splitStorageKey = "meshDashboardLayoutSplitState";
    const layoutViewStorageKey = "meshDashboardLayoutView";
    const chatChannelStorageKey = "meshDashboardChatChannel";
    const chatBottomStickThresholdPx = 28;
    const chatWarnWindowSeconds = 10 * 60;
    const chatStaleWindowSeconds = 30 * 60;
    const chatRosterMaxEntries = 180;
    const chatEmojiChoices = [
      "😀", "😁", "😂", "🤣", "😊", "😉", "😎", "🤔",
      "👍", "👎", "👏", "🙏", "✅", "❌", "⚠️", "🔥",
      "❤️", "💯", "📡", "📶", "🛰️", "🏠", "🚗", "🎯",
    ];
    const consoleMaxLines = 1200;
    const tableSortState = {{
      "nodes-table": {{ index: 0, dir: "desc" }},
      "links-table": {{ index: 2, dir: "desc" }},
      "ports-table": {{ index: 1, dir: "desc" }},
      "packets-table": {{ index: 0, dir: "desc" }},
    }};
    const wheelActivationLeaseMs = 1400;
    const knownLayoutViews = new Set(["chat", "network", "packets", "data", "all"]);
    const knownChatChannels = new Set(["all", "direct"]);
    const sortableTables = new Set(Object.keys(tableSortState));
    const consoleLines = [];
    const consoleKeyQueue = [];
    const consoleSeen = new Set();
    const wheelPaneSelector = ".scroll, #live-console, details pre";
    let selectedNodeId = null;
    let activeHistoryTab = "signal";
    let pendingSelectionScroll = false;
    let latestState = null;
    let lastMapSignature = "";
    let mapResizeRaf = null;
    let splitPct = 64;
    let splitTopPx = 430;
    let splitMidPx = 250;
    let splitLowPx = 240;
    let consoleAutoscroll = true;
    let fitDone = false;
    let mapResizeObserver = null;
    let activeWheelPane = null;
    let activeWheelPaneLease = null;
    let mapWheelZoomActive = false;
    let mapWheelJustArmed = false;
    let mapWheelLease = null;
    let chatSendInFlight = false;
    let chatStickToBottom = true;
    let activeLayoutView = "chat";
    let activeChatChannel = "all";
    let chatEmojiMode = "compose";
    let chatReactionTargetId = null;
    const nodeHistoryCache = new Map();
    const nodeNameCache = new Map();

    function requestMapResize() {{
      if (mapResizeRaf !== null) {{
        cancelAnimationFrame(mapResizeRaf);
      }}
      mapResizeRaf = requestAnimationFrame(() => {{
        map.invalidateSize({{ pan: false, animate: false }});
        mapResizeRaf = null;
      }});
    }}

    function syncMapSize() {{
      splitTopPx = clampTopSplitPx(splitTopPx);
      splitMidPx = clampMidSplitPx(splitMidPx);
      splitLowPx = clampLowSplitPx(splitLowPx);
      applySplitState();
      requestMapResize();
    }}

    function bindMapContainerObserver() {{
      if (mapResizeObserver || !mapFrameElement || typeof ResizeObserver === "undefined") {{
        return;
      }}
      mapResizeObserver = new ResizeObserver(() => {{
        requestMapResize();
      }});
      mapResizeObserver.observe(mapFrameElement);
    }}

    function setMapWheelZoomActive(active) {{
      const next = !!active;
      if (mapWheelZoomActive === next) {{
        return;
      }}
      mapWheelZoomActive = next;
      if (!mapWheelZoomActive) {{
        mapWheelJustArmed = false;
        if (mapWheelLease !== null) {{
          clearTimeout(mapWheelLease);
          mapWheelLease = null;
        }}
      }}
      if (mapWheelZoomActive) {{
        map.scrollWheelZoom.enable();
      }} else {{
        map.scrollWheelZoom.disable();
      }}
      if (mapFrameElement) {{
        mapFrameElement.classList.toggle("map-wheel-active", mapWheelZoomActive);
        mapFrameElement.setAttribute(
          "title",
          mapWheelZoomActive
            ? "Map wheel zoom active. Click outside map (or press Esc) to return wheel scrolling to page."
            : "Click map to enable wheel zoom."
        );
      }}
    }}

    function touchMapWheelLease() {{
      if (!mapWheelZoomActive) {{
        return;
      }}
      if (mapWheelLease !== null) {{
        clearTimeout(mapWheelLease);
      }}
      mapWheelLease = window.setTimeout(() => {{
        setMapWheelZoomActive(false);
      }}, wheelActivationLeaseMs);
    }}

    function bindMapWheelActivation() {{
      if (!mapFrameElement || mapFrameElement.dataset.wheelMapBound === "1") {{
        return;
      }}
      mapFrameElement.dataset.wheelMapBound = "1";
      setMapWheelZoomActive(false);

      mapFrameElement.addEventListener("pointerdown", (ev) => {{
        if (!(ev.target instanceof Element)) {{
          return;
        }}
        if (ev.target.closest(".leaflet-control")) {{
          return;
        }}
        if (!mapWheelZoomActive) {{
          mapWheelJustArmed = true;
        }}
        setMapWheelZoomActive(true);
        touchMapWheelLease();
      }});

      mapFrameElement.addEventListener("wheel", () => {{
        touchMapWheelLease();
      }}, {{ passive: true }});

      document.addEventListener("pointerdown", (ev) => {{
        if (!(ev.target instanceof Element)) {{
          setMapWheelZoomActive(false);
          return;
        }}
        if (!mapFrameElement.contains(ev.target)) {{
          setMapWheelZoomActive(false);
        }}
      }});
      document.addEventListener("keydown", (ev) => {{
        if (ev.key === "Escape") {{
          setMapWheelZoomActive(false);
        }}
      }});
    }}

    function bindWheelPassthrough() {{
      const clearWheelPaneLease = () => {{
        if (activeWheelPaneLease !== null) {{
          clearTimeout(activeWheelPaneLease);
          activeWheelPaneLease = null;
        }}
      }};

      const touchWheelPaneLease = () => {{
        if (!(activeWheelPane instanceof HTMLElement)) {{
          clearWheelPaneLease();
          return;
        }}
        clearWheelPaneLease();
        activeWheelPaneLease = window.setTimeout(() => {{
          setActiveWheelPane(null);
        }}, wheelActivationLeaseMs);
      }};

      const setActiveWheelPane = (next) => {{
        if (activeWheelPane === next) {{
          if (activeWheelPane instanceof HTMLElement) {{
            touchWheelPaneLease();
          }}
          return;
        }}
        if (activeWheelPane instanceof HTMLElement) {{
          activeWheelPane.classList.remove("wheel-scroll-active");
        }}
        activeWheelPane = next instanceof HTMLElement ? next : null;
        if (activeWheelPane) {{
          activeWheelPane.classList.add("wheel-scroll-active");
          if (document.activeElement !== activeWheelPane) {{
            activeWheelPane.focus({{ preventScroll: true }});
          }}
          touchWheelPaneLease();
        }} else {{
          clearWheelPaneLease();
        }}
      }};

      const canScrollInDirection = (el, delta) => {{
        if (!(el instanceof HTMLElement)) {{
          return false;
        }}
        const max = el.scrollHeight - el.clientHeight;
        if (max <= 1) {{
          return false;
        }}
        if (delta > 0) {{
          return el.scrollTop < (max - 1);
        }}
        if (delta < 0) {{
          return el.scrollTop > 1;
        }}
        return false;
      }};

      const routeWheelToPage = (delta) => {{
        window.scrollBy({{ top: delta, behavior: "auto" }});
      }};

      for (const el of document.querySelectorAll(wheelPaneSelector)) {{
        if (!(el instanceof HTMLElement) || el.dataset.wheelPassBound === "1") {{
          continue;
        }}
        el.dataset.wheelPassBound = "1";
        if (!el.hasAttribute("tabindex")) {{
          el.tabIndex = 0;
        }}
        if (!el.getAttribute("title")) {{
          el.setAttribute("title", "Click panel to wheel-scroll inside it. Auto-releases after a brief pause.");
        }}
        el.addEventListener("pointerdown", () => {{
          setActiveWheelPane(el);
        }});
        el.addEventListener("focusin", () => {{
          setActiveWheelPane(el);
        }});
        el.addEventListener(
          "wheel",
          (ev) => {{
            if (ev.defaultPrevented || ev.ctrlKey || ev.metaKey) {{
              return;
            }}
            const delta = Math.abs(ev.deltaY) >= Math.abs(ev.deltaX) ? ev.deltaY : ev.deltaX;
            if (!Number.isFinite(delta) || delta === 0) {{
              return;
            }}

            const paneIsActive = activeWheelPane === el;
            if (!paneIsActive) {{
              ev.preventDefault();
              routeWheelToPage(delta);
              return;
            }}

            if (canScrollInDirection(el, delta)) {{
              touchWheelPaneLease();
              return;
            }}

            ev.preventDefault();
            routeWheelToPage(delta);
            setActiveWheelPane(null);
          }},
          {{ passive: false }}
        );
      }}

      if (document.body.dataset.wheelPassDocBound !== "1") {{
        document.body.dataset.wheelPassDocBound = "1";
        document.addEventListener("pointerdown", (ev) => {{
          if (!(ev.target instanceof Element)) {{
            setActiveWheelPane(null);
            return;
          }}
          if (!ev.target.closest(wheelPaneSelector)) {{
            setActiveWheelPane(null);
          }}
        }});
        document.addEventListener("keydown", (ev) => {{
          if (ev.key === "Escape") {{
            setActiveWheelPane(null);
          }}
        }});
      }}
    }}

    map.whenReady(() => {{
      requestMapResize();
      bindMapContainerObserver();
      bindMapWheelActivation();
    }});
    window.addEventListener("resize", () => {{
      setTimeout(syncMapSize, 120);
    }});

    function setText(id, value) {{
      const el = document.getElementById(id);
      if (!el) return;
      el.textContent = value == null ? "n/a" : String(value);
    }}

    function getChatScroller() {{
      const feed = document.getElementById("chat-feed");
      if (!(feed instanceof HTMLElement)) return null;
      const scroller = feed.closest(".scroll");
      return scroller instanceof HTMLElement ? scroller : null;
    }}

    function isNearBottom(scroller, thresholdPx = chatBottomStickThresholdPx) {{
      if (!(scroller instanceof HTMLElement)) return false;
      const remaining = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight;
      return remaining <= thresholdPx;
    }}

    function bindChatAutoScroll() {{
      const scroller = getChatScroller();
      if (!(scroller instanceof HTMLElement) || scroller.dataset.chatScrollBound === "1") return;
      scroller.dataset.chatScrollBound = "1";
      chatStickToBottom = true;
      scroller.addEventListener("scroll", () => {{
        chatStickToBottom = isNearBottom(scroller);
      }});
    }}

    function bytesToGiB(value) {{
      const num = Number(value);
      if (!Number.isFinite(num) || num < 0) return null;
      return num / (1024 ** 3);
    }}

    function parseDashboardTimeToUnix(value) {{
      const text = String(value == null ? "" : value).trim();
      if (!text) return null;
      const iso = text.includes("T") ? text : text.replace(" ", "T");
      const parsed = Date.parse(iso);
      if (!Number.isFinite(parsed)) return null;
      return Math.floor(parsed / 1000);
    }}

    function nodeLastHeardUnix(node) {{
      if (!node || typeof node !== "object") return null;
      const raw = Number(node.last_heard_unix);
      if (Number.isFinite(raw) && raw > 0) {{
        return Math.floor(raw);
      }}
      return parseDashboardTimeToUnix(node.last_heard);
    }}

    function freshnessStatus(lastSeenUnix, nowUnix = Math.floor(Date.now() / 1000)) {{
      const ts = Number(lastSeenUnix);
      if (!Number.isFinite(ts) || ts <= 0) return "unknown";
      const age = Math.max(0, nowUnix - ts);
      if (age <= chatWarnWindowSeconds) return "online";
      if (age <= chatStaleWindowSeconds) return "warn";
      return "stale";
    }}

    function statusRank(status) {{
      const key = String(status || "unknown");
      if (key === "online") return 0;
      if (key === "warn") return 1;
      if (key === "stale") return 2;
      return 3;
    }}

    function pickFresherStatus(currentStatus, nextStatus) {{
      return statusRank(nextStatus) < statusRank(currentStatus) ? nextStatus : currentStatus;
    }}

    function normalizeChatChannel(raw) {{
      const clean = String(raw || "").trim().toLowerCase();
      return knownChatChannels.has(clean) ? clean : "all";
    }}

    function channelLabel(key) {{
      return key === "direct" ? "Peer-to-peer" : "Everyone";
    }}

    function applyChatChannel(channelKey, persist = true) {{
      activeChatChannel = normalizeChatChannel(channelKey);
      if (persist) {{
        try {{
          window.localStorage.setItem(chatChannelStorageKey, activeChatChannel);
        }} catch (_err) {{
        }}
      }}
      const usersTitle = document.getElementById("chat-users-title");
      if (usersTitle) {{
        usersTitle.textContent = activeChatChannel === "direct" ? "Users (Peer-to-peer)" : "Users (Everyone)";
      }}
      const input = document.getElementById("chat-input");
      if (input instanceof HTMLInputElement) {{
        if (activeChatChannel === "direct") {{
          input.placeholder = isSelectableNodeId(selectedNodeId)
            ? `Direct message to ${{selectedNodeId}}...`
            : "Select a user to direct message...";
        }} else {{
          input.placeholder = "Message the room (^all)...";
        }}
      }}
      if (latestState) {{
        renderChat(latestState);
      }}
    }}

    function loadChatChannel() {{
      let preferred = "all";
      try {{
        preferred = normalizeChatChannel(window.localStorage.getItem(chatChannelStorageKey) || "all");
      }} catch (_err) {{
      }}
      applyChatChannel(preferred, false);
    }}

    function classifyMessageChannel(msg) {{
      if (!msg || typeof msg !== "object") return "all";
      const toId = normalizeNodeId(msg.to || msg.destination || "");
      if (!toId || toId === "^all" || toId === "all" || toId === "broadcast") {{
        return "all";
      }}
      return "direct";
    }}

    function setChatSendStatus(message, isError = false) {{
      const el = document.getElementById("chat-send-status");
      if (!(el instanceof HTMLElement)) return;
      el.textContent = message ? String(message) : "";
      el.classList.toggle("error", !!isError);
    }}

    function setChatSendBusy(isBusy) {{
      chatSendInFlight = !!isBusy;
      const btn = document.getElementById("chat-send-btn");
      const emojiBtn = document.getElementById("chat-emoji-btn");
      const input = document.getElementById("chat-input");
      if (btn instanceof HTMLButtonElement) {{
        btn.disabled = chatSendInFlight;
        btn.textContent = chatSendInFlight ? "Sending..." : "Send";
      }}
      if (emojiBtn instanceof HTMLButtonElement) {{
        emojiBtn.disabled = chatSendInFlight;
      }}
      if (input instanceof HTMLInputElement) {{
        input.disabled = chatSendInFlight;
      }}
      if (chatSendInFlight) {{
        closeChatEmojiPanel();
      }}
    }}

    async function sendChatPayload(body, successMessage) {{
      if (chatSendInFlight) return null;
      setChatSendBusy(true);
      setChatSendStatus("Sending...");
      try {{
        const resp = await fetch("/api/chat/send", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(body || {{}}),
        }});
        const payload = await resp.json().catch(() => ({{}}));
        if (!resp.ok || !payload.ok) {{
          const msg = payload && payload.error ? payload.error : `send failed (${{resp.status}})`;
          throw new Error(msg);
        }}
        setChatSendStatus(successMessage || `Sent at ${{payload.sent_at || "now"}}`);
        await poll();
        return payload;
      }} catch (err) {{
        setChatSendStatus(`Send error: ${{err.message || err}}`, true);
        return null;
      }} finally {{
        setChatSendBusy(false);
      }}
    }}

    async function sendChatMessage() {{
      const input = document.getElementById("chat-input");
      if (!(input instanceof HTMLInputElement)) return;
      const text = input.value.trim();
      if (!text) {{
        setChatSendStatus("Enter a message before sending.", true);
        return;
      }}
      let destination = "^all";
      if (activeChatChannel === "direct") {{
        if (!isSelectableNodeId(selectedNodeId)) {{
          setChatSendStatus("Select a user before sending a peer-to-peer message.", true);
          return;
        }}
        destination = selectedNodeId;
      }}
      const payload = await sendChatPayload(
        {{
          text,
          destination,
          channel_index: 0,
        }},
        null
      );
      if (payload && payload.ok) {{
        input.value = "";
        if (destination === "^all") {{
          setChatSendStatus(`Sent to Everyone at ${{payload.sent_at || "now"}}`);
        }} else {{
          setChatSendStatus(`Sent direct to ${{destination}} at ${{payload.sent_at || "now"}}`);
        }}
      }}
    }}

    async function sendChatReaction(replyId, emoji) {{
      const replyNum = Number(replyId);
      const cleanEmoji = String(emoji || "").trim();
      if (!Number.isInteger(replyNum) || replyNum <= 0) {{
        setChatSendStatus("Cannot react: target message id is missing.", true);
        return;
      }}
      if (!cleanEmoji) {{
        setChatSendStatus("Choose an emoji reaction.", true);
        return;
      }}
      let destination = "^all";
      if (activeChatChannel === "direct" && isSelectableNodeId(selectedNodeId)) {{
        destination = selectedNodeId;
      }}
      const payload = await sendChatPayload(
        {{
          destination,
          channel_index: 0,
          reply_id: replyNum,
          emoji: cleanEmoji,
        }},
        null
      );
      if (payload && payload.ok) {{
        setChatSendStatus(`Reacted ${{cleanEmoji}} at ${{payload.sent_at || "now"}}`);
      }}
    }}

    function openChatEmojiPanel(mode = "compose", reactionTargetId = null) {{
      const panel = document.getElementById("chat-emoji-panel");
      const btn = document.getElementById("chat-emoji-btn");
      if (!(panel instanceof HTMLElement)) return;
      chatEmojiMode = mode === "react" ? "react" : "compose";
      const parsedTarget = Number(reactionTargetId);
      chatReactionTargetId = (
        chatEmojiMode === "react" && Number.isInteger(parsedTarget) && parsedTarget > 0
      ) ? parsedTarget : null;
      panel.hidden = false;
      if (btn instanceof HTMLButtonElement) {{
        btn.setAttribute("aria-expanded", "true");
      }}
      if (chatEmojiMode === "react") {{
        setChatSendStatus("Pick a reaction emoji...");
      }}
    }}

    function closeChatEmojiPanel() {{
      const panel = document.getElementById("chat-emoji-panel");
      const btn = document.getElementById("chat-emoji-btn");
      chatEmojiMode = "compose";
      chatReactionTargetId = null;
      if (panel instanceof HTMLElement) {{
        panel.hidden = true;
      }}
      if (btn instanceof HTMLButtonElement) {{
        btn.setAttribute("aria-expanded", "false");
      }}
    }}

    function insertEmojiAtCursor(emoji) {{
      const input = document.getElementById("chat-input");
      if (!(input instanceof HTMLInputElement)) return;
      const value = input.value || "";
      const start = Number.isFinite(input.selectionStart) ? input.selectionStart : value.length;
      const end = Number.isFinite(input.selectionEnd) ? input.selectionEnd : value.length;
      input.value = value.slice(0, start) + emoji + value.slice(end);
      const next = start + emoji.length;
      input.focus({{ preventScroll: true }});
      input.setSelectionRange(next, next);
    }}

    function bindEmojiPicker() {{
      const panel = document.getElementById("chat-emoji-panel");
      const btn = document.getElementById("chat-emoji-btn");
      if (!(panel instanceof HTMLElement) || !(btn instanceof HTMLButtonElement)) return;

      if (panel.dataset.init !== "1") {{
        panel.innerHTML = `<div class="chat-emoji-grid">${{chatEmojiChoices.map((emoji) => (
          `<button type="button" class="chat-emoji-item" data-emoji="${{escAttr(emoji)}}" title="${{escAttr(emoji)}}">${{escAttr(emoji)}}</button>`
        )).join("")}}</div>`;
        panel.dataset.init = "1";
      }}

      if (btn.dataset.emojiBound !== "1") {{
        btn.dataset.emojiBound = "1";
        btn.addEventListener("click", (ev) => {{
          ev.preventDefault();
          if (chatSendInFlight) return;
          if (panel.hidden) {{
            openChatEmojiPanel("compose", null);
          }} else {{
            closeChatEmojiPanel();
          }}
        }});
      }}

      if (panel.dataset.bound !== "1") {{
        panel.dataset.bound = "1";
        panel.addEventListener("click", (ev) => {{
          const target = ev.target;
          if (!(target instanceof Element)) return;
          const emojiBtn = target.closest(".chat-emoji-item");
          if (!(emojiBtn instanceof HTMLButtonElement)) return;
          const emoji = String(emojiBtn.getAttribute("data-emoji") || emojiBtn.textContent || "").trim();
          if (!emoji) return;
          if (chatEmojiMode === "react" && Number.isInteger(chatReactionTargetId) && chatReactionTargetId > 0) {{
            sendChatReaction(chatReactionTargetId, emoji);
          }} else {{
            insertEmojiAtCursor(emoji);
          }}
          closeChatEmojiPanel();
        }});
      }}

      if (document.body.dataset.chatEmojiCloseBound !== "1") {{
        document.body.dataset.chatEmojiCloseBound = "1";
        document.addEventListener("pointerdown", (ev) => {{
          const target = ev.target;
          if (!(target instanceof Element)) return;
          if (!target.closest("#chat-emoji-panel") && !target.closest("#chat-emoji-btn")) {{
            closeChatEmojiPanel();
          }}
        }});
        document.addEventListener("keydown", (ev) => {{
          if (ev.key === "Escape") {{
            closeChatEmojiPanel();
          }}
        }});
      }}
    }}

    function bindChatComposer() {{
      const btn = document.getElementById("chat-send-btn");
      if (btn instanceof HTMLButtonElement && btn.dataset.bound !== "1") {{
        btn.dataset.bound = "1";
        btn.addEventListener("click", () => {{
          sendChatMessage();
        }});
      }}

      const input = document.getElementById("chat-input");
      if (input instanceof HTMLInputElement && input.dataset.bound !== "1") {{
        input.dataset.bound = "1";
        input.addEventListener("keydown", (ev) => {{
          if (ev.key === "Enter" && !ev.shiftKey) {{
            ev.preventDefault();
            sendChatMessage();
          }}
        }});
      }}

      bindEmojiPicker();
    }}

    function nodeLabel(node) {{
      return node.long_name || node.short_name || node.id || "unknown";
    }}

    function preferredNodeName(node) {{
      if (!node || typeof node !== "object") return "";
      const longName = String(node.long_name || "").trim();
      if (longName) return longName;
      const shortName = String(node.short_name || "").trim();
      if (shortName) return shortName;
      return "";
    }}

    function markerStyle(isSelected) {{
      if (isSelected) {{
        return {{
          radius: 8,
          color: "#7a0f20",
          fillColor: "#ffd24a",
          fillOpacity: 0.95,
          weight: 2,
          bubblingMouseEvents: false
        }};
      }}
      return {{
        radius: 6,
        color: "#143d2a",
        fillColor: "#34c27f",
        fillOpacity: 0.85,
        weight: 1,
        bubblingMouseEvents: false
      }};
    }}

    function normalizeNodeId(nodeId) {{
      const raw = String(nodeId == null ? "" : nodeId).trim();
      if (!raw) return "";
      const lower = raw.toLowerCase();
      if (lower === "^all" || lower === "all" || lower === "broadcast") return "^all";
      if (lower === "unknown") return "Unknown";
      if (lower === "n/a" || lower === "na") return "n/a";
      if (lower === "local") return "local";

      const hex = raw.startsWith("!") ? raw.slice(1) : raw;
      if (/^[0-9a-f]{8}$/i.test(hex)) {{
        return `!${{hex.toLowerCase()}}`;
      }}
      return raw;
    }}

    function isSelectableNodeId(nodeId) {{
      const normalized = normalizeNodeId(nodeId);
      return !!normalized && normalized !== "^all" && normalized !== "Unknown" && normalized !== "n/a";
    }}

    function loadStoredSelection() {{
      try {{
        const stored = window.localStorage.getItem(selectionStorageKey);
        const normalized = normalizeNodeId(stored);
        if (isSelectableNodeId(normalized)) {{
          selectedNodeId = normalized;
        }}
      }} catch (_err) {{
      }}
    }}

    function loadNodeNameCache() {{
      try {{
        const raw = window.localStorage.getItem(nodeNameCacheStorageKey);
        if (!raw) return;
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) return;
        for (const entry of parsed) {{
          if (!Array.isArray(entry) || entry.length < 2) continue;
          const nodeId = normalizeNodeId(entry[0]);
          const name = String(entry[1] || "").trim();
          if (!isSelectableNodeId(nodeId) || !name) continue;
          nodeNameCache.set(nodeId, name);
        }}
      }} catch (_err) {{
      }}
    }}

    function persistNodeNameCache() {{
      try {{
        const entries = Array.from(nodeNameCache.entries()).slice(-2000);
        window.localStorage.setItem(nodeNameCacheStorageKey, JSON.stringify(entries));
      }} catch (_err) {{
      }}
    }}

    function updateNodeNameCache(nodes) {{
      let changed = false;
      for (const node of (nodes || [])) {{
        const nodeId = normalizeNodeId(node.id || "");
        if (!isSelectableNodeId(nodeId)) continue;
        const name = preferredNodeName(node);
        if (!name) continue;
        if (nodeNameCache.get(nodeId) !== name) {{
          nodeNameCache.set(nodeId, name);
          changed = true;
        }}
      }}
      if (changed) {{
        persistNodeNameCache();
      }}
    }}

    function persistSelection() {{
      try {{
        if (isSelectableNodeId(selectedNodeId)) {{
          window.localStorage.setItem(selectionStorageKey, normalizeNodeId(selectedNodeId));
        }} else {{
          window.localStorage.removeItem(selectionStorageKey);
        }}
      }} catch (_err) {{
      }}
    }}

    function renderSelectionStatus() {{
      const pill = document.getElementById("selected-node-pill");
      if (pill) {{
        pill.textContent = selectedNodeId ? `Selected: ${{selectedNodeId}}` : "Selected: none";
      }}
      const btn = document.getElementById("clear-selection-btn");
      if (btn) {{
        btn.disabled = !selectedNodeId;
      }}
    }}

    function escAttr(value) {{
      return String(value)
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    }}

    function clampSplitPct(value) {{
      return Math.max(42, Math.min(78, value));
    }}

    function clampTopSplitPx(value) {{
      const max = Math.max(300, Math.min(760, window.innerHeight - 320));
      return Math.max(220, Math.min(max, value));
    }}

    function clampMidSplitPx(value) {{
      const max = Math.max(220, Math.min(620, window.innerHeight - 380));
      return Math.max(160, Math.min(max, value));
    }}

    function clampLowSplitPx(value) {{
      const max = Math.max(220, Math.min(560, window.innerHeight - 320));
      return Math.max(160, Math.min(max, value));
    }}

    function applySplitState() {{
      const layout = document.querySelector(".layout");
      if (!(layout instanceof HTMLElement)) return;
      layout.style.setProperty("--split-left-pct", `${{splitPct}}%`);
      layout.style.setProperty("--split-top-px", `${{splitTopPx}}px`);
      layout.style.setProperty("--split-mid-px", `${{splitMidPx}}px`);
      layout.style.setProperty("--split-low-px", `${{splitLowPx}}px`);
    }}

    function loadSplitState() {{
      try {{
        const raw = window.localStorage.getItem(splitStorageKey) || "";
        if (raw) {{
          const parsed = JSON.parse(raw);
          if (parsed && typeof parsed === "object") {{
            if (Number.isFinite(parsed.col_pct)) {{
              splitPct = clampSplitPct(Number(parsed.col_pct));
            }}
            if (Number.isFinite(parsed.top_px)) {{
              splitTopPx = clampTopSplitPx(Number(parsed.top_px));
            }}
            if (Number.isFinite(parsed.mid_px)) {{
              splitMidPx = clampMidSplitPx(Number(parsed.mid_px));
            }}
            if (Number.isFinite(parsed.low_px)) {{
              splitLowPx = clampLowSplitPx(Number(parsed.low_px));
            }}
          }} else if (Number.isFinite(parsed)) {{
            splitPct = clampSplitPct(Number(parsed));
          }}
        }}
      }} catch (_err) {{
      }}
      applySplitState();
    }}

    function persistSplitState() {{
      try {{
        window.localStorage.setItem(
          splitStorageKey,
          JSON.stringify({{
            col_pct: splitPct,
            top_px: splitTopPx,
            mid_px: splitMidPx,
            low_px: splitLowPx,
          }})
        );
      }} catch (_err) {{
      }}
    }}

    function normalizeLayoutView(raw) {{
      const clean = String(raw || "").trim().toLowerCase();
      return knownLayoutViews.has(clean) ? clean : "chat";
    }}

    function applyLayoutView(viewName, persist = true) {{
      const layout = document.getElementById("dashboard-layout");
      if (!(layout instanceof HTMLElement)) return;
      const shell = document.querySelector(".workspace-shell");
      const chatLeftPanel = document.getElementById("chat-left-panel");
      const next = normalizeLayoutView(viewName);
      activeLayoutView = next;
      for (const name of knownLayoutViews) {{
        layout.classList.remove(`view-${{name}}`);
      }}
      layout.classList.add(`view-${{next}}`);
      const chatPanelOpen = next === "chat";
      if (shell instanceof HTMLElement) {{
        shell.classList.toggle("chat-panel-open", chatPanelOpen);
      }}
      if (chatLeftPanel instanceof HTMLElement) {{
        chatLeftPanel.hidden = !chatPanelOpen;
      }}

      for (const btn of document.querySelectorAll(".teams-rail .rail-btn")) {{
        if (!(btn instanceof HTMLButtonElement)) continue;
        const isActive = normalizeLayoutView(btn.dataset.view || "") === next;
        btn.classList.toggle("active", isActive);
        btn.setAttribute("aria-current", isActive ? "page" : "false");
      }}

      if (persist) {{
        try {{
          window.localStorage.setItem(layoutViewStorageKey, next);
        }} catch (_err) {{
        }}
      }}

      if (latestState) {{
        renderTraffic(latestState.traffic || {{}}, latestState.nodes || [], null);
      }}
      requestMapResize();
    }}

    function loadLayoutView() {{
      let preferred = "chat";
      try {{
        preferred = normalizeLayoutView(window.localStorage.getItem(layoutViewStorageKey) || "chat");
      }} catch (_err) {{
      }}
      applyLayoutView(preferred, false);
    }}

    function bindLayoutNav() {{
      for (const btn of document.querySelectorAll(".teams-rail .rail-btn")) {{
        if (!(btn instanceof HTMLButtonElement) || btn.dataset.bound === "1") continue;
        btn.dataset.bound = "1";
        btn.addEventListener("click", () => {{
          applyLayoutView(btn.dataset.view || "chat", true);
        }});
      }}
    }}

    function bindSplitters() {{
      const layout = document.querySelector(".layout");
      if (!(layout instanceof HTMLElement)) return;

      for (const splitter of document.querySelectorAll(".splitter, .hsplitter")) {{
        if (!(splitter instanceof HTMLElement) || splitter.dataset.bound === "1") continue;
        splitter.dataset.bound = "1";

        splitter.addEventListener("pointerdown", (ev) => {{
          if (window.matchMedia("(max-width: 1100px)").matches) return;
          ev.preventDefault();
          splitter.classList.add("active");
          const isHorizontal = splitter.classList.contains("hsplitter");
          document.body.classList.add(isHorizontal ? "resizing-panels-y" : "resizing-panels-x");
          splitter.setPointerCapture(ev.pointerId);
          const rect = layout.getBoundingClientRect();
          const startY = ev.clientY;
          const target = splitter.dataset.target || "";
          const startTop = splitTopPx;
          const startMid = splitMidPx;
          const startLow = splitLowPx;

          const onMove = (moveEv) => {{
            if (isHorizontal) {{
              const deltaY = moveEv.clientY - startY;
              if (target === "top") {{
                splitTopPx = clampTopSplitPx(startTop + deltaY);
              }} else if (target === "mid") {{
                splitMidPx = clampMidSplitPx(startMid + deltaY);
              }} else if (target === "low") {{
                splitLowPx = clampLowSplitPx(startLow + deltaY);
              }}
            }} else {{
              const pct = clampSplitPct(((moveEv.clientX - rect.left) / rect.width) * 100);
              splitPct = pct;
            }}
            applySplitState();
            requestMapResize();
          }};

          const onUp = () => {{
            splitter.classList.remove("active");
            document.body.classList.remove("resizing-panels-x", "resizing-panels-y");
            persistSplitState();
            requestMapResize();
            splitter.removeEventListener("pointermove", onMove);
            splitter.removeEventListener("pointerup", onUp);
            splitter.removeEventListener("pointercancel", onUp);
          }};

          splitter.addEventListener("pointermove", onMove);
          splitter.addEventListener("pointerup", onUp);
          splitter.addEventListener("pointercancel", onUp);
        }});
      }}
    }}

    function normalizeSortValue(raw) {{
      const text = String(raw == null ? "" : raw).trim();
      if (!text) return {{ kind: "empty", value: "" }};

      const numericText = text.replace(/,/g, "");
      if (/^-?\\d+(\\.\\d+)?$/.test(numericText)) {{
        return {{ kind: "num", value: Number.parseFloat(numericText) }};
      }}

      const epoch = Date.parse(text);
      if (!Number.isNaN(epoch)) {{
        return {{ kind: "date", value: epoch }};
      }}

      return {{ kind: "str", value: text.toLowerCase() }};
    }}

    function compareSortValues(a, b) {{
      const priority = {{ empty: 0, num: 1, date: 2, str: 3 }};
      if (a.kind !== b.kind) {{
        return (priority[a.kind] ?? 99) - (priority[b.kind] ?? 99);
      }}
      if (a.value < b.value) return -1;
      if (a.value > b.value) return 1;
      return 0;
    }}

    function cellSortRaw(cell) {{
      if (!cell) return "";
      return cell.getAttribute("data-sort") || cell.textContent || "";
    }}

    function updateSortIndicators(tableId) {{
      const table = document.getElementById(tableId);
      if (!(table instanceof HTMLTableElement)) return;
      const headers = Array.from(table.querySelectorAll("thead th"));
      headers.forEach((th) => {{
        th.classList.remove("sorted-asc", "sorted-desc");
      }});

      const state = tableSortState[tableId];
      if (!state) return;
      const target = headers[state.index];
      if (!target) return;
      target.classList.add(state.dir === "asc" ? "sorted-asc" : "sorted-desc");
    }}

    function bindSortableHeader(tableId) {{
      const table = document.getElementById(tableId);
      if (!(table instanceof HTMLTableElement) || table.dataset.sortBound === "1") return;
      table.dataset.sortBound = "1";

      const headers = Array.from(table.querySelectorAll("thead th"));
      headers.forEach((th, index) => {{
        th.classList.add("sortable");
        th.addEventListener("click", () => {{
          const state = tableSortState[tableId] || {{ index, dir: "asc" }};
          if (state.index === index) {{
            state.dir = state.dir === "asc" ? "desc" : "asc";
          }} else {{
            state.index = index;
            state.dir = index === 0 ? "desc" : "asc";
          }}
          tableSortState[tableId] = state;
          sortTableRows(tableId);
        }});
      }});

      updateSortIndicators(tableId);
    }}

    function sortTableRows(tableId) {{
      const table = document.getElementById(tableId);
      if (!(table instanceof HTMLTableElement)) return;
      const tbody = table.tBodies[0];
      if (!tbody) return;
      const state = tableSortState[tableId];
      if (!state) return;

      const rows = Array.from(tbody.rows);
      rows.sort((aRow, bRow) => {{
        const aCell = aRow.cells[state.index];
        const bCell = bRow.cells[state.index];
        const aValue = normalizeSortValue(cellSortRaw(aCell));
        const bValue = normalizeSortValue(cellSortRaw(bCell));
        const cmp = compareSortValues(aValue, bValue);
        return state.dir === "asc" ? cmp : -cmp;
      }});

      rows.forEach((row) => tbody.appendChild(row));
      updateSortIndicators(tableId);
    }}

    function packetConsoleKey(entry) {{
      const summary = entry.summary || {{}};
      let packetPart = "";
      try {{
        packetPart = JSON.stringify(entry.packet || {{}});
      }} catch (_err) {{
        packetPart = "";
      }}
      return [
        summary.captured_at || "",
        summary.from || "",
        summary.to || "",
        summary.portnum || "",
        summary.rx_time || "",
        String(summary.rx_snr ?? ""),
        String(summary.rx_rssi ?? ""),
        packetPart,
      ].join("|");
    }}

    function formatConsoleLine(entry) {{
      const s = entry.summary || {{}};
      const hops = (s.hop_start != null && s.hop_limit != null)
        ? Number(s.hop_start) - Number(s.hop_limit)
        : "n/a";
      const packetJson = (() => {{
        try {{
          return JSON.stringify(entry.packet || {{}});
        }} catch (_err) {{
          return "{{}}";
        }}
      }})();
      return `[${{s.captured_at || s.rx_time || "n/a"}}] ${{s.from || "n/a"}} -> ${{s.to || "n/a"}} port=${{s.portnum || "n/a"}} snr=${{s.rx_snr ?? "n/a"}} rssi=${{s.rx_rssi ?? "n/a"}} hops=${{hops}} ${{packetJson}}`;
    }}

    function appendConsoleLine(key, line) {{
      if (!key || consoleSeen.has(key)) return;
      consoleSeen.add(key);
      consoleKeyQueue.push(key);
      consoleLines.push(line);

      while (consoleLines.length > consoleMaxLines) {{
        consoleLines.shift();
        const oldKey = consoleKeyQueue.shift();
        if (oldKey) {{
          consoleSeen.delete(oldKey);
        }}
      }}
    }}

    function bindConsoleControls() {{
      const clearBtn = document.getElementById("console-clear-btn");
      if (clearBtn instanceof HTMLButtonElement && clearBtn.dataset.bound !== "1") {{
        clearBtn.dataset.bound = "1";
        clearBtn.addEventListener("click", () => {{
          consoleLines.length = 0;
          consoleKeyQueue.length = 0;
          consoleSeen.clear();
          const pre = document.getElementById("live-console");
          if (pre) {{
            pre.textContent = "";
          }}
        }});
      }}

      const auto = document.getElementById("console-autoscroll");
      if (auto instanceof HTMLInputElement && auto.dataset.bound !== "1") {{
        auto.dataset.bound = "1";
        consoleAutoscroll = auto.checked;
        auto.addEventListener("change", () => {{
          consoleAutoscroll = auto.checked;
        }});
      }}
    }}

    function renderConsole(traffic) {{
      const packets = traffic.recent_packets || [];
      for (const entry of packets) {{
        const key = packetConsoleKey(entry);
        appendConsoleLine(key, formatConsoleLine(entry));
      }}

      const pre = document.getElementById("live-console");
      if (!pre) return;
      pre.textContent = consoleLines.join("\\n");
      if (consoleAutoscroll) {{
        pre.scrollTop = pre.scrollHeight;
      }}
    }}

    function highlightNodeSelection() {{
      for (const row of document.querySelectorAll("#nodes-table tbody tr")) {{
        const nodeId = normalizeNodeId(row.dataset.nodeId || "");
        row.classList.toggle("selected-node", !!selectedNodeId && nodeId === selectedNodeId);
      }}
      for (const item of document.querySelectorAll("#chat-feed .chat-feed-item")) {{
        const nodeId = normalizeNodeId(item.dataset.nodeId || "");
        item.classList.toggle("selected-node", !!selectedNodeId && nodeId === selectedNodeId);
      }}
      for (const member of document.querySelectorAll("#chat-room-list .chat-member-item")) {{
        const nodeId = normalizeNodeId(member.dataset.nodeId || "");
        member.classList.toggle("selected-node", !!selectedNodeId && nodeId === selectedNodeId);
      }}
    }}

    function scrollSelectionIntoView() {{
      if (!selectedNodeId) {{
        pendingSelectionScroll = false;
        return;
      }}

      let didScroll = false;
      // Keep chat stable; selection auto-scroll only applies to the node list.
      for (const tableId of ["nodes-table"]) {{
        let targetRow = null;
        for (const row of document.querySelectorAll(`#${{tableId}} tbody tr`)) {{
          if (normalizeNodeId(row.dataset.nodeId || "") === selectedNodeId) {{
            targetRow = row;
            break;
          }}
        }}
        if (!targetRow) continue;

        const table = document.getElementById(tableId);
        const scroller = table ? table.closest(".scroll") : null;
        if (!(scroller instanceof HTMLElement)) {{
          didScroll = true;
          continue;
        }}

        const header = table ? table.querySelector("thead") : null;
        const headerHeight = header ? header.getBoundingClientRect().height : 0;
        const scrollerRect = scroller.getBoundingClientRect();
        const rowRect = targetRow.getBoundingClientRect();
        const topSafe = scrollerRect.top + headerHeight + 3;
        const bottomSafe = scrollerRect.bottom - 3;

        if (rowRect.top < topSafe) {{
          const delta = rowRect.top - topSafe;
          scroller.scrollTo({{ top: scroller.scrollTop + delta, behavior: "smooth" }});
        }} else if (rowRect.bottom > bottomSafe) {{
          const delta = rowRect.bottom - bottomSafe;
          scroller.scrollTo({{ top: scroller.scrollTop + delta, behavior: "smooth" }});
        }}
        didScroll = true;
      }}

      pendingSelectionScroll = !didScroll;
    }}

    function updateMapSelection(shouldFocus = false) {{
      for (const [nodeId, marker] of nodeMarkers.entries()) {{
        marker.setStyle(markerStyle(!!selectedNodeId && nodeId === selectedNodeId));
      }}
      if (!shouldFocus || !selectedNodeId) return;
      const marker = nodeMarkers.get(selectedNodeId);
      if (!marker) return;
      map.panTo(marker.getLatLng(), {{ animate: true, duration: 0.35 }});
      marker.openPopup();
    }}

    function selectedNodeFrom(nodes) {{
      if (!selectedNodeId) return null;
      for (const node of (nodes || [])) {{
        if (normalizeNodeId(node.id || "") === selectedNodeId) {{
          return node;
        }}
      }}
      return null;
    }}

    function setMapDataMode(mode) {{
      const live = document.getElementById("map-data-live");
      const node = document.getElementById("map-data-node");
      const title = document.getElementById("map-data-title");
      const nodeMode = mode === "node";
      if (live) live.hidden = nodeMode;
      if (node) node.hidden = !nodeMode;
      if (title) title.textContent = nodeMode ? "Node History" : "Map Data";
    }}

    function setHistoryTab(tabName) {{
      activeHistoryTab = tabName === "overview" ? "overview" : "signal";
      for (const btn of document.querySelectorAll(".history-tab-btn")) {{
        const isActive = btn.dataset.tab === activeHistoryTab;
        btn.classList.toggle("active", isActive);
      }}
      const signalPanel = document.getElementById("tab-panel-signal");
      const overviewPanel = document.getElementById("tab-panel-overview");
      if (signalPanel) signalPanel.hidden = activeHistoryTab !== "signal";
      if (overviewPanel) overviewPanel.hidden = activeHistoryTab !== "overview";
    }}

    function bindHistoryTabs() {{
      for (const btn of document.querySelectorAll(".history-tab-btn")) {{
        if (!(btn instanceof HTMLButtonElement) || btn.dataset.bound === "1") continue;
        btn.dataset.bound = "1";
        btn.addEventListener("click", () => {{
          setHistoryTab(btn.dataset.tab || "signal");
        }});
      }}
      setHistoryTab(activeHistoryTab);
    }}

    function renderNodeHistoryLoading(nodeId) {{
      setMapDataMode("node");
      const caption = document.getElementById("node-history-caption");
      if (caption) {{
        caption.textContent = `Loading history for ${{nodeId}}...`;
      }}
      const overview = document.getElementById("node-history-overview");
      if (overview) {{
        overview.innerHTML = "";
      }}
      const svg = document.getElementById("signal-chart");
      if (svg) {{
        svg.innerHTML = "";
      }}
      const empty = document.getElementById("signal-empty");
      if (empty) {{
        empty.hidden = false;
        empty.textContent = "Loading historical signal points...";
      }}
    }}

    function selectNode(nodeId, shouldFocus = true) {{
      const normalized = normalizeNodeId(nodeId);
      if (!isSelectableNodeId(normalized)) return;
      selectedNodeId = normalized;
      pendingSelectionScroll = true;
      persistSelection();
      renderSelectionStatus();
      highlightNodeSelection();
      updateMapSelection(shouldFocus);
      scrollSelectionIntoView();
      renderNodeHistoryLoading(selectedNodeId);
      if (latestState) {{
        renderMap(latestState.nodes || [], (latestState.traffic || {{}}).edges || []);
      }}
      applyChatChannel(activeChatChannel, false);
    }}

    function clearNodeSelection() {{
      selectedNodeId = null;
      pendingSelectionScroll = false;
      persistSelection();
      renderSelectionStatus();
      highlightNodeSelection();
      updateMapSelection(false);
      map.closePopup();
      setMapDataMode("live");
      if (latestState) {{
        renderMap(latestState.nodes || [], (latestState.traffic || {{}}).edges || []);
        renderTraffic(latestState.traffic || {{}}, latestState.nodes || [], null);
      }}
      applyChatChannel(activeChatChannel, false);
    }}

    function bindNodeRowClicks() {{
      for (const row of document.querySelectorAll("#nodes-table tbody tr.node-selectable")) {{
        row.addEventListener("click", () => {{
          selectNode(row.dataset.nodeId || "", true);
        }});
      }}
    }}

    function bindChatFeedClicks() {{
      for (const item of document.querySelectorAll("#chat-feed .chat-feed-item.chat-selectable")) {{
        item.addEventListener("click", () => {{
          selectNode(item.dataset.nodeId || "", true);
        }});
      }}
    }}

    function bindChatReactionControls() {{
      for (const btn of document.querySelectorAll("#chat-feed .chat-react-btn")) {{
        if (!(btn instanceof HTMLButtonElement)) continue;
        btn.addEventListener("click", (ev) => {{
          ev.preventDefault();
          ev.stopPropagation();
          if (chatSendInFlight) return;
          const replyId = Number(btn.dataset.replyId || "");
          if (!Number.isInteger(replyId) || replyId <= 0) {{
            setChatSendStatus("Cannot react: target message id is missing.", true);
            return;
          }}
          openChatEmojiPanel("react", replyId);
        }});
      }}

      for (const chip of document.querySelectorAll("#chat-feed .chat-reaction-chip")) {{
        if (!(chip instanceof HTMLButtonElement)) continue;
        chip.addEventListener("click", (ev) => {{
          ev.preventDefault();
          ev.stopPropagation();
          if (chatSendInFlight) return;
          const replyId = Number(chip.dataset.replyId || "");
          const emoji = String(chip.dataset.emoji || "").trim();
          if (!Number.isInteger(replyId) || replyId <= 0 || !emoji) return;
          sendChatReaction(replyId, emoji);
        }});
      }}
    }}

    function bindSelectionControls() {{
      const btn = document.getElementById("clear-selection-btn");
      if (!btn || btn.dataset.bound === "1") return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", () => {{
        clearNodeSelection();
      }});
    }}

    map.on("click", () => {{
      if (mapWheelJustArmed) {{
        mapWheelJustArmed = false;
        return;
      }}
      clearNodeSelection();
    }});

    function renderSummary(state) {{
      const s = state.summary || {{}};
      setText("m-target", s.target || "n/a");
      setText("m-nodes", s.node_count ?? 0);
      setText("m-pos-nodes", s.nodes_with_position ?? 0);
      setText("m-live-packets", s.live_packet_count ?? 0);
      const realLinks = s.real_edge_count ?? s.edge_count ?? 0;
      setText("m-links", realLinks);
      setText("m-modem-preset", s.modem_preset || "n/a");
      setText("m-uptime", s.uptime_seconds ?? 0);
      setText("updated-at", state.generated_at || "n/a");
      const err = document.getElementById("local-state-error");
      if (err) {{
        err.textContent = state.local_state_error ? `  Local state error: ${{state.local_state_error}}` : "";
      }}

      const revision = s.revision || {{}};
      const revisionText = document.getElementById("revision-text");
      if (revisionText) {{
        const fallbackLabel = String(revision.label || "").trim();
        const version = String(revision.version || "").trim();
        const commit = String(revision.commit || "").trim();
        if (fallbackLabel) {{
          revisionText.textContent = fallbackLabel;
        }} else if (version || commit) {{
          const versionText = version ? `v${{version}}` : "unknown";
          const commitText = commit || "nogit";
          revisionText.textContent = `Rev: ${{versionText}} (${{commitText}})`;
        }}
        const title = String(revision.title || "").trim();
        if (title) {{
          revisionText.title = title;
        }}
      }}

      const disk = s.disk || {{}};
      const diskLabel = document.getElementById("disk-label");
      const diskFill = document.getElementById("disk-fill");
      const diskMeter = document.getElementById("disk-meter");
      const freePctRaw = Number(disk.free_pct);
      if (!Number.isFinite(freePctRaw)) {{
        if (diskLabel) {{
          diskLabel.textContent = "Disk free: n/a";
        }}
        if (diskFill) {{
          diskFill.style.width = "0%";
          diskFill.classList.remove("warn", "danger");
        }}
        if (diskMeter) {{
          const detail = disk.error ? ` (${{disk.error}})` : "";
          diskMeter.title = `Disk free on dashboard host${{detail}}`;
        }}
        return;
      }}

      const freePct = Math.max(0, Math.min(100, freePctRaw));
      if (diskLabel) {{
        diskLabel.textContent = `Disk free: ${{freePct.toFixed(1)}}%`;
      }}
      if (diskFill) {{
        diskFill.style.width = `${{freePct.toFixed(1)}}%`;
        diskFill.classList.remove("warn", "danger");
        if (freePct < 15) {{
          diskFill.classList.add("danger");
        }} else if (freePct < 30) {{
          diskFill.classList.add("warn");
        }}
      }}
      if (diskMeter) {{
        const freeGiB = bytesToGiB(disk.free_bytes);
        const totalGiB = bytesToGiB(disk.total_bytes);
        const freeText = freeGiB == null ? "n/a" : freeGiB.toFixed(1);
        const totalText = totalGiB == null ? "n/a" : totalGiB.toFixed(1);
        diskMeter.title = `Disk free on dashboard host (${{freeText}} GiB / ${{totalText}} GiB, path: ${{disk.path || "n/a"}})`;
      }}
    }}

    function buildMapSignature(nodes, edges) {{
      const selection = isSelectableNodeId(selectedNodeId) ? normalizeNodeId(selectedNodeId) : "";
      if (selection) {{
        const selectedNode = selectedNodeFrom(nodes);
        if (
          selectedNode &&
          typeof selectedNode.lat === "number" &&
          typeof selectedNode.lon === "number"
        ) {{
          return `sel:${{selection}}:${{selectedNode.lat.toFixed(5)}},${{selectedNode.lon.toFixed(5)}}`;
        }}
        return `sel:${{selection}}:no-position`;
      }}
      const nodeSig = (nodes || [])
        .filter((node) => typeof node.lat === "number" && typeof node.lon === "number")
        .map((node) => `${{normalizeNodeId(node.id)}}:${{node.lat.toFixed(5)}},${{node.lon.toFixed(5)}}`)
        .join("|");
      const edgeSig = (edges || [])
        .map((edge) => `${{normalizeNodeId(edge.from)}}>${{normalizeNodeId(edge.to)}}:${{edge.lifetime_count ?? edge.count ?? 0}}:${{edge.last_rx_time || ""}}:${{edge.last_hops ?? ""}}`)
        .join("|");
      return `all#${{nodeSig}}#${{edgeSig}}`;
    }}

    function renderMap(nodes, edges) {{
      const signature = buildMapSignature(nodes, edges);
      if (signature === lastMapSignature) {{
        updateMapSelection(false);
        return;
      }}
      lastMapSignature = signature;

      nodeLayer.clearLayers();
      edgeLayer.clearLayers();
      nodeMarkers.clear();
      const features = [];
      const byId = Object.fromEntries(nodes.map((n) => [normalizeNodeId(n.id), n]));
      const selectionMode = isSelectableNodeId(selectedNodeId);
      const mapTitle = document.getElementById("map-card-title");
      if (mapTitle) {{
        mapTitle.textContent = selectionMode ? "Selected Node Map" : "Network Map";
      }}

      if (selectionMode) {{
        const selectedNode = selectedNodeFrom(nodes);
        if (
          selectedNode &&
          typeof selectedNode.lat === "number" &&
          typeof selectedNode.lon === "number"
        ) {{
          const marker = L.circleMarker(
            [selectedNode.lat, selectedNode.lon],
            markerStyle(true)
          );
          marker.bindPopup(`
            <b>${{nodeLabel(selectedNode)}}</b><br/>
            ${{normalizeNodeId(selectedNode.id) || selectedNode.id}}<br/>
            Num: ${{selectedNode.num ?? "n/a"}}<br/>
            SNR: ${{selectedNode.snr ?? "n/a"}}<br/>
            Last: ${{selectedNode.last_heard || "n/a"}}
          `);
          marker.on("click", () => {{
            selectNode(normalizeNodeId(selectedNode.id || ""), false);
          }});
          marker.addTo(nodeLayer);
          nodeMarkers.set(normalizeNodeId(selectedNode.id || ""), marker);
          features.push(marker);
          map.setView([selectedNode.lat, selectedNode.lon], Math.max(map.getZoom(), 11), {{ animate: false }});
          marker.openPopup();
        }} else {{
          map.closePopup();
        }}
        requestMapResize();
        return;
      }}

      for (const node of nodes) {{
        if (typeof node.lat !== "number" || typeof node.lon !== "number") continue;
        const normalizedId = normalizeNodeId(node.id || "");
        const isSelected = !!selectedNodeId && normalizedId === selectedNodeId;
        const marker = L.circleMarker([node.lat, node.lon], markerStyle(isSelected));
        marker.bindPopup(`
          <b>${{nodeLabel(node)}}</b><br/>
          ${{normalizedId || node.id}}<br/>
          Num: ${{node.num ?? "n/a"}}<br/>
          SNR: ${{node.snr ?? "n/a"}}<br/>
          Last: ${{node.last_heard || "n/a"}}
        `);
        marker.on("click", () => {{
          selectNode(normalizedId, false);
        }});
        marker.addTo(nodeLayer);
        nodeMarkers.set(normalizedId, marker);
        features.push(marker);
      }}

      for (const edge of edges) {{
        const src = byId[normalizeNodeId(edge.from)];
        const dst = byId[normalizeNodeId(edge.to)];
        if (!src || !dst) continue;
        if (typeof src.lat !== "number" || typeof src.lon !== "number") continue;
        if (typeof dst.lat !== "number" || typeof dst.lon !== "number") continue;
        const lifetimeCount = edge.lifetime_count ?? edge.count ?? 0;
        const sessionCount = edge.session_count ?? edge.count ?? 0;
        const isReal = !!edge.is_real;
        const hopsLabel = edge.avg_hops == null
          ? "n/a"
          : `avg ${{edge.avg_hops}}${{edge.last_hops == null ? "" : ` (last ${{edge.last_hops}})`}}`;
        const line = L.polyline([[src.lat, src.lon], [dst.lat, dst.lon]], {{
          color: isReal ? "#bf1f43" : "#b7791f",
          dashArray: isReal ? null : "6 6",
          opacity: isReal ? 0.74 : 0.52,
          weight: Math.min(8, 2 + lifetimeCount),
          bubblingMouseEvents: false,
        }});
        line.bindTooltip(`
          <b>${{edge.from}} -> ${{edge.to}}</b><br/>
          Status: ${{edge.confidence || (isReal ? "confirmed" : "observed")}}<br/>
          Packets: ${{lifetimeCount}}<br/>
          Hops: ${{hopsLabel}}
        `, {{ sticky: true, opacity: 0.92 }});
        line.bindPopup(`
          <b>${{edge.from}} -> ${{edge.to}}</b><br/>
          Status: ${{edge.confidence || (isReal ? "confirmed" : "observed")}}<br/>
          Session packets: ${{sessionCount}}<br/>
          Lifetime packets: ${{lifetimeCount}}<br/>
          First: ${{edge.first_rx_time || "n/a"}}<br/>
          Last: ${{edge.last_rx_time || "n/a"}}<br/>
          Hops: ${{hopsLabel}}<br/>
          Ports: ${{(edge.portnums || []).join(", ") || "n/a"}}
        `);
        line.addTo(edgeLayer);
        features.push(line);
      }}

      if (!fitDone && features.length > 0) {{
        map.fitBounds(L.featureGroup(features).getBounds().pad(0.2));
        fitDone = true;
        requestMapResize();
      }}
      updateMapSelection(false);
    }}

    function fillTable(tableId, rowsHtml) {{
      const tbody = document.querySelector(`#${{tableId}} tbody`);
      if (!tbody) return;
      tbody.innerHTML = rowsHtml.join("");
      if (sortableTables.has(tableId)) {{
        bindSortableHeader(tableId);
        sortTableRows(tableId);
      }}
    }}

    function renderNodes(nodes) {{
        const rows = nodes.map((node) => {{
          const nodeId = normalizeNodeId(node.id || "");
          const selectable = isSelectableNodeId(nodeId);
          const pos = (typeof node.lat === "number" && typeof node.lon === "number")
            ? `${{node.lat.toFixed(5)}}, ${{node.lon.toFixed(5)}}`
            : "n/a";
          const name = nodeLabel(node);
          const savedPackets = Number.isFinite(Number(node.saved_packets))
            ? Number(node.saved_packets)
            : 0;
          const savedPoints = Number.isFinite(Number(node.saved_points))
            ? Number(node.saved_points)
            : 0;
          const savedTitle = savedPoints > 0
            ? `${{savedPackets}} packets across ${{savedPoints}} minute buckets`
            : "No saved history yet";
          return `<tr data-node-id="${{escAttr(nodeId)}}" class="${{selectable ? "node-selectable" : ""}}">
          <td data-sort="${{escAttr(node.last_heard ?? "")}}">${{node.last_heard ?? "n/a"}}</td>
          <td class="mono" data-sort="${{escAttr(nodeId)}}" title="${{escAttr(String(node.id || nodeId || ""))}}">${{nodeId || "n/a"}}</td>
          <td data-sort="${{escAttr(name)}}">${{name}}</td>
          <td data-sort="${{escAttr(node.hardware_model ?? "")}}">${{node.hardware_model ?? "n/a"}}</td>
          <td data-sort="${{escAttr(node.snr ?? "")}}">${{node.snr ?? "n/a"}}</td>
          <td data-sort="${{escAttr(node.hops_away ?? "")}}">${{node.hops_away ?? "n/a"}}</td>
          <td data-sort="${{escAttr(node.battery_level ?? "")}}">${{node.battery_level ?? "n/a"}}</td>
          <td data-sort="${{escAttr(savedPackets)}}" title="${{escAttr(savedTitle)}}">${{savedPackets}}</td>
          <td data-sort="${{escAttr(pos)}}">${{pos}}</td>
        </tr>`;
      }});
      fillTable("nodes-table", rows);
      bindNodeRowClicks();
      highlightNodeSelection();
      if (pendingSelectionScroll) {{
        scrollSelectionIntoView();
      }}
    }}

    function formatMetricValue(value, decimals = 2, suffix = "") {{
      const num = Number(value);
      if (!Number.isFinite(num)) return "n/a";
      return `${{num.toFixed(decimals)}}${{suffix}}`;
    }}

    function renderSignalChart(points) {{
      const svg = document.getElementById("signal-chart");
      const empty = document.getElementById("signal-empty");
      if (!(svg instanceof SVGElement) || !(empty instanceof HTMLElement)) return;

      const rows = Array.isArray(points) ? points : [];
      const width = 900;
      const height = 220;
      const padLeft = 44;
      const padRight = 44;
      const padTop = 12;
      const padBottom = 24;
      const plotW = width - padLeft - padRight;
      const plotH = height - padTop - padBottom;

      const snrVals = rows.map((p) => Number(p.avg_snr)).filter((v) => Number.isFinite(v));
      const rssiVals = rows.map((p) => Number(p.avg_rssi)).filter((v) => Number.isFinite(v));
      if (snrVals.length === 0 && rssiVals.length === 0) {{
        svg.innerHTML = "";
        empty.hidden = false;
        empty.textContent = "No historical signal points yet for this node.";
        return;
      }}
      empty.hidden = true;

      const withSpread = (vals, fallbackMin, fallbackMax) => {{
        if (!vals.length) return [fallbackMin, fallbackMax];
        let lo = Math.min(...vals);
        let hi = Math.max(...vals);
        if (Math.abs(hi - lo) < 0.001) {{
          lo -= 1;
          hi += 1;
        }}
        return [lo, hi];
      }};

      const [snrMin, snrMax] = withSpread(snrVals, -20, 20);
      const [rssiMin, rssiMax] = withSpread(rssiVals, -130, -60);
      const xAt = (idx, total) => (
        padLeft + ((Math.max(0, idx) / Math.max(1, total - 1)) * plotW)
      );
      const yFrom = (value, minVal, maxVal) => (
        padTop + ((maxVal - value) / (maxVal - minVal)) * plotH
      );

      const buildPath = (metricKey, minVal, maxVal) => {{
        const n = rows.length;
        let d = "";
        let started = false;
        for (let i = 0; i < n; i += 1) {{
          const raw = Number(rows[i][metricKey]);
          if (!Number.isFinite(raw)) continue;
          const x = xAt(i, n);
          const y = yFrom(raw, minVal, maxVal);
          d += `${{started ? " L " : "M "}}${{x.toFixed(2)}} ${{y.toFixed(2)}}`;
          started = true;
        }}
        return d;
      }};

      const snrPath = buildPath("avg_snr", snrMin, snrMax);
      const rssiPath = buildPath("avg_rssi", rssiMin, rssiMax);
      const midY = padTop + (plotH / 2);

      svg.setAttribute("viewBox", `0 0 ${{width}} ${{height}}`);
      svg.innerHTML = `
        <rect x="0" y="0" width="${{width}}" height="${{height}}" fill="none"></rect>
        <line x1="${{padLeft}}" y1="${{midY.toFixed(2)}}" x2="${{width - padRight}}" y2="${{midY.toFixed(2)}}" stroke="#dce8df" stroke-width="1"></line>
        <line x1="${{padLeft}}" y1="${{padTop}}" x2="${{padLeft}}" y2="${{height - padBottom}}" stroke="#dce8df" stroke-width="1"></line>
        <line x1="${{width - padRight}}" y1="${{padTop}}" x2="${{width - padRight}}" y2="${{height - padBottom}}" stroke="#dce8df" stroke-width="1"></line>
        ${{snrPath ? `<path d="${{snrPath}}" fill="none" stroke="#1f6f53" stroke-width="2"></path>` : ""}}
        ${{rssiPath ? `<path d="${{rssiPath}}" fill="none" stroke="#265d7b" stroke-width="2"></path>` : ""}}
        <text x="${{padLeft - 4}}" y="${{padTop + 10}}" font-size="10" text-anchor="end" fill="#1f6f53">${{formatMetricValue(snrMax, 1)}}</text>
        <text x="${{padLeft - 4}}" y="${{height - padBottom}}" font-size="10" text-anchor="end" fill="#1f6f53">${{formatMetricValue(snrMin, 1)}}</text>
        <text x="${{width - padRight + 4}}" y="${{padTop + 10}}" font-size="10" text-anchor="start" fill="#265d7b">${{formatMetricValue(rssiMax, 0)}}</text>
        <text x="${{width - padRight + 4}}" y="${{height - padBottom}}" font-size="10" text-anchor="start" fill="#265d7b">${{formatMetricValue(rssiMin, 0)}}</text>
      `;
    }}

    function renderNodeHistoryOverview(history, node) {{
      const summary = history.summary || {{}};
      const target = document.getElementById("node-history-overview");
      if (!target) return;
      const historyNodeId = normalizeNodeId(history.node_id || "");
      const label = node ? nodeLabel(node) : (historyNodeId || selectedNodeId || "node");
      const items = [
        ["Node", `${{label}}`],
        ["Node ID", `${{historyNodeId || selectedNodeId || "n/a"}}`],
        ["Points", `${{summary.points ?? (history.points || []).length ?? 0}}`],
        ["Packets", `${{summary.total_packets ?? 0}}`],
        ["Window", `${{history.window_hours ?? nodeHistoryHours}}h`],
        ["Last Seen", `${{summary.last_seen || "n/a"}}`],
        ["SNR Range", `${{formatMetricValue(summary.snr_min, 1)}} to ${{formatMetricValue(summary.snr_max, 1)}} dB`],
        ["RSSI Range", `${{formatMetricValue(summary.rssi_min, 0)}} to ${{formatMetricValue(summary.rssi_max, 0)}} dBm`],
      ];
      target.innerHTML = items.map(([k, v]) => (
        `<div class="overview-item"><div class="k">${{k}}</div><div class="v">${{v}}</div></div>`
      )).join("");
    }}

    function renderNodeHistory(history, nodes) {{
      setMapDataMode("node");
      const node = selectedNodeFrom(nodes);
      const historyNodeId = normalizeNodeId(history.node_id || "");
      const caption = document.getElementById("node-history-caption");
      if (caption) {{
        const name = node ? nodeLabel(node) : (historyNodeId || selectedNodeId || "node");
        const span = history.summary || {{}};
        const loc = (node && typeof node.lat === "number" && typeof node.lon === "number")
          ? `Current location: ${{node.lat.toFixed(5)}}, ${{node.lon.toFixed(5)}}.`
          : "No current location available from live node state.";
        caption.textContent = `${{name}} (${{historyNodeId || selectedNodeId || "n/a"}}). ${{loc}} History window: ${{history.window_hours || nodeHistoryHours}}h, packets: ${{span.total_packets ?? 0}}.`;
      }}
      renderSignalChart(history.points || []);
      renderNodeHistoryOverview(history, node);
      setHistoryTab(activeHistoryTab);
    }}

    async function fetchNodeHistory(nodeId) {{
      if (!isSelectableNodeId(nodeId)) return null;
      const cached = nodeHistoryCache.get(nodeId);
      const nowMs = Date.now();
      if (cached && (nowMs - (cached.fetchedAt || 0)) < Math.max(refreshMs, 2500)) {{
        return cached.data;
      }}
      const url = `/api/history/node?node_id=${{encodeURIComponent(nodeId)}}&hours=${{nodeHistoryHours}}&points=${{nodeHistoryMaxPoints}}`;
      const resp = await fetch(url, {{ cache: "no-store" }});
      if (!resp.ok) throw new Error(`history API ${{resp.status}}`);
      const data = await resp.json();
      nodeHistoryCache.set(nodeId, {{ fetchedAt: nowMs, data }});
      return data;
    }}

    function renderTraffic(traffic, nodes, nodeHistory) {{
      if (isSelectableNodeId(selectedNodeId)) {{
        if (nodeHistory && normalizeNodeId(nodeHistory.node_id) === selectedNodeId) {{
          renderNodeHistory(nodeHistory, nodes);
        }} else {{
          renderNodeHistoryLoading(selectedNodeId);
        }}
        return;
      }}

      setMapDataMode("live");
      const ports = (traffic.port_counts || []).slice(0, 30).map((item) => (
        `<tr><td data-sort="${{escAttr(item.portnum ?? "")}}">${{item.portnum}}</td><td data-sort="${{escAttr(item.count ?? "")}}">${{item.count}}</td></tr>`
      ));
      fillTable("ports-table", ports);

      const links = (traffic.edges || []).slice(0, 60).map((edge) => (
        `<tr>
          <td data-sort="${{escAttr(edge.from ?? "")}}">${{edge.from}}</td>
          <td data-sort="${{escAttr(edge.to ?? "")}}">${{edge.to}}</td>
          <td data-sort="${{escAttr(edge.lifetime_count ?? edge.count ?? 0)}}">${{edge.lifetime_count ?? edge.count ?? 0}}</td>
          <td data-sort="${{escAttr(edge.avg_hops ?? "")}}">${{edge.avg_hops == null ? "n/a" : edge.avg_hops}}</td>
          <td data-sort="${{escAttr(edge.confidence || (edge.is_real ? "confirmed" : "observed"))}}">${{edge.confidence || (edge.is_real ? "confirmed" : "observed")}}</td>
          <td data-sort="${{escAttr(edge.last_rx_time ?? "")}}">${{edge.last_rx_time || "n/a"}}</td>
        </tr>`
      ));
      fillTable("links-table", links);
    }}

    function renderChat(state) {{
      const traffic = state.traffic || {{}};
      const s = state.summary || {{}};
      const chatScroller = getChatScroller();
      const shouldStickBottom = !!(chatScroller && (chatStickToBottom || isNearBottom(chatScroller)));
      updateNodeNameCache(state.nodes || []);
      const nowUnix = Math.floor(Date.now() / 1000);
      const nodesById = new Map(
        (state.nodes || []).map((node) => [normalizeNodeId(node.id || ""), node])
      );

      const chatEndpointParts = (nodeId) => {{
        const clean = normalizeNodeId(nodeId);
        if (!clean) {{
          return {{ label: "n/a", idTag: "", title: "n/a", status: "unknown" }};
        }}
        if (clean === "^all") {{
          return {{ label: "All", idTag: "", title: "^all", status: "unknown" }};
        }}
        if (clean === "local") {{
          return {{ label: "Local", idTag: "", title: "local", status: "online" }};
        }}
        const node = nodesById.get(clean);
        const name = preferredNodeName(node) || nodeNameCache.get(clean) || "Unknown node";
        const lastHeard = nodeLastHeardUnix(node);
        const status = freshnessStatus(lastHeard, nowUnix);
        return {{
          label: name,
          idTag: clean,
          title: `${{name}} (${{clean}})`,
          status,
        }};
      }};

      const participants = new Map();
      const channelCounts = {{ all: 0, direct: 0 }};
      const touchParticipant = (meta, msgTimeUnix) => {{
        if (!meta || !meta.idTag || !isSelectableNodeId(meta.idTag)) return;
        const existing = participants.get(meta.idTag);
        if (!existing) {{
          participants.set(meta.idTag, {{
            id: meta.idTag,
            name: meta.label || meta.idTag,
            status: String(meta.status || "unknown"),
            lastMessageUnix: msgTimeUnix || null,
          }});
          return;
        }}
        if (meta.label && meta.label !== "Unknown node") {{
          existing.name = meta.label;
        }}
        existing.status = pickFresherStatus(existing.status, String(meta.status || "unknown"));
        if (msgTimeUnix && (!existing.lastMessageUnix || msgTimeUnix > existing.lastMessageUnix)) {{
          existing.lastMessageUnix = msgTimeUnix;
        }}
      }};

      const touchNodeById = (nodeId, msgTimeUnix = null) => {{
        const clean = normalizeNodeId(nodeId);
        if (!isSelectableNodeId(clean)) return;
        const node = nodesById.get(clean);
        const name = preferredNodeName(node) || nodeNameCache.get(clean) || clean;
        const lastHeard = nodeLastHeardUnix(node);
        const status = freshnessStatus(lastHeard, nowUnix);
        const existing = participants.get(clean);
        if (!existing) {{
          participants.set(clean, {{
            id: clean,
            name,
            status,
            lastMessageUnix: msgTimeUnix || lastHeard || null,
          }});
          return;
        }}
        if (name && name !== "Unknown node") {{
          existing.name = name;
        }}
        existing.status = pickFresherStatus(existing.status, status);
        const recent = msgTimeUnix || lastHeard || null;
        if (recent && (!existing.lastMessageUnix || recent > existing.lastMessageUnix)) {{
          existing.lastMessageUnix = recent;
        }}
      }};

      const escapeChatText = (value) => {{
        const clean = String(value == null ? "" : value);
        const escaped = escAttr(clean);
        return escaped.replace(/\\n/g, "<br/>");
      }};

      const parseMessageId = (value) => {{
        const num = Number(value);
        if (!Number.isFinite(num) || num <= 0) return null;
        return Math.trunc(num);
      }};

      const messageIdOf = (msg) => {{
        if (!msg || typeof msg !== "object") return null;
        return parseMessageId(msg.message_id ?? msg.messageId ?? msg.packet_id ?? msg.packetId);
      }};

      const replyIdOf = (msg) => {{
        if (!msg || typeof msg !== "object") return null;
        return parseMessageId(msg.reply_id ?? msg.replyId);
      }};

      const emojiOf = (msg) => {{
        if (!msg || typeof msg !== "object") return "";
        const direct = String(msg.emoji || "").trim();
        if (direct) return direct;
        const codepoint = Number(msg.emoji_codepoint ?? msg.emojiCodepoint);
        if (Number.isInteger(codepoint) && codepoint > 0) {{
          try {{
            return String.fromCodePoint(codepoint);
          }} catch (_err) {{
            return "";
          }}
        }}
        return "";
      }};

      const isReactionMessage = (msg) => {{
        if (!msg || typeof msg !== "object") return false;
        if (msg.is_reaction === true) return true;
        const replyId = replyIdOf(msg);
        const emoji = emojiOf(msg);
        return !!(replyId && emoji);
      }};

      const rawMessages = traffic.recent_chat || [];
      const reactionBuckets = new Map();
      for (const msg of rawMessages) {{
        if (!isReactionMessage(msg)) continue;
        const replyId = replyIdOf(msg);
        const emoji = emojiOf(msg);
        if (!replyId || !emoji) continue;

        const key = String(replyId);
        let perMessage = reactionBuckets.get(key);
        if (!(perMessage instanceof Map)) {{
          perMessage = new Map();
          reactionBuckets.set(key, perMessage);
        }}

        let bucket = perMessage.get(emoji);
        if (!bucket) {{
          bucket = {{
            emoji,
            count: 0,
            reactors: new Set(),
            names: [],
            lastUnix: 0,
          }};
          perMessage.set(emoji, bucket);
        }}

        const reactorId = normalizeNodeId(msg.from || "");
        const reactorMeta = chatEndpointParts(reactorId);
        const reactorName = reactorMeta.label || reactorId || "Unknown node";
        const dedupeKey = reactorId || `${{reactorName}}:${{msg.rx_time || msg.captured_at || bucket.count}}`;
        if (!bucket.reactors.has(dedupeKey)) {{
          bucket.reactors.add(dedupeKey);
          bucket.count += 1;
          bucket.names.push(reactorName);
        }}
        const reactionTime = parseDashboardTimeToUnix(msg.rx_time || msg.captured_at || "");
        if (reactionTime && reactionTime > bucket.lastUnix) {{
          bucket.lastUnix = reactionTime;
        }}
      }}

      const baseMessages = rawMessages.filter((msg) => !isReactionMessage(msg));
      for (const msg of baseMessages) {{
        const key = classifyMessageChannel(msg);
        if (key === "direct") {{
          channelCounts.direct += 1;
        }} else {{
          channelCounts.all += 1;
        }}
      }}

      const channelList = document.getElementById("chat-channel-list");
      if (channelList) {{
        channelList.innerHTML = [
          {{ key: "all", label: "Everyone", count: channelCounts.all }},
          {{ key: "direct", label: "Peer-to-peer", count: channelCounts.direct }},
        ].map((entry) => (
          `<button type="button" class="chat-channel-item${{activeChatChannel === entry.key ? " active" : ""}}" data-channel="${{entry.key}}">
            <span class="chat-channel-name">${{entry.label}}</span>
            <span class="chat-channel-meta">${{entry.count}}</span>
          </button>`
        )).join("");
        for (const btn of channelList.querySelectorAll(".chat-channel-item")) {{
          if (!(btn instanceof HTMLButtonElement)) continue;
          btn.addEventListener("click", () => {{
            applyChatChannel(btn.dataset.channel || "all", true);
          }});
        }}
      }}

      const messages = baseMessages.filter((msg) => classifyMessageChannel(msg) === activeChatChannel);
      const feedItems = messages.map((msg) => {{
        const sourceNode = normalizeNodeId(msg.from);
        const fallbackNode = normalizeNodeId(msg.to);
        const primarySelectable = isSelectableNodeId(sourceNode) ? sourceNode : "";
        const fallbackSelectable = isSelectableNodeId(fallbackNode) ? fallbackNode : "";
        const nodeId = primarySelectable || fallbackSelectable;
        const selectableClass = nodeId ? "chat-selectable" : "";
        const fromMeta = chatEndpointParts(sourceNode);
        const toMeta = chatEndpointParts(fallbackNode);
        const msgTimeUnix = parseDashboardTimeToUnix(msg.rx_time || msg.captured_at || "");
        touchParticipant(fromMeta, msgTimeUnix);
        if (activeChatChannel === "direct") {{
          touchParticipant(toMeta, msgTimeUnix);
          touchNodeById(sourceNode, msgTimeUnix);
          touchNodeById(fallbackNode, msgTimeUnix);
        }}
        const timeText = msg.rx_time || msg.captured_at || "n/a";
        const textHtml = escapeChatText(msg.text || "");
        const hopNum = Number(msg.hops);
        const hasHop = Number.isFinite(hopNum) && hopNum >= 0;
        const hopStart = Number(msg.hop_start ?? msg.hopStart);
        const hopLimit = Number(msg.hop_limit ?? msg.hopLimit);
        const hopLabel = hasHop
          ? `${{Math.trunc(hopNum)}} hop${{Math.trunc(hopNum) === 1 ? "" : "s"}}`
          : "";
        const hopTitle = (
          Number.isFinite(hopStart) && Number.isFinite(hopLimit)
            ? `hopStart=${{Math.trunc(hopStart)}}, hopLimit=${{Math.trunc(hopLimit)}}`
            : "Hop count"
        );
        const messageId = messageIdOf(msg);
        const messageReactions = messageId ? reactionBuckets.get(String(messageId)) : null;
        const reactionChips = messageReactions
          ? Array.from(messageReactions.values())
              .sort((a, b) => (b.count - a.count) || String(a.emoji).localeCompare(String(b.emoji)))
              .map((bucket) => {{
                const tooltipNames = Array.from(new Set(bucket.names)).slice(0, 8);
                const tooltip = tooltipNames.length > 0
                  ? `${{bucket.emoji}}: ${{tooltipNames.join(", ")}}`
                  : `${{bucket.emoji}} reaction`;
                return `<button type="button" class="chat-reaction-chip" data-reply-id="${{escAttr(messageId)}}" data-emoji="${{escAttr(bucket.emoji)}}" title="${{escAttr(tooltip)}}">
                  <span>${{escAttr(bucket.emoji)}}</span><span class="chat-reaction-count">${{bucket.count}}</span>
                </button>`;
              }})
              .join("")
          : "";
        const reactButton = messageId
          ? `<button type="button" class="chat-react-btn" data-reply-id="${{escAttr(messageId)}}" title="React to this message">😊+</button>`
          : "";
        const reactionRow = reactionChips
          ? `<div class="chat-reaction-row">${{reactionChips}}</div>`
          : "";
        return `<div data-node-id="${{escAttr(nodeId)}}" class="chat-feed-item ${{selectableClass}}">
          <div class="chat-feed-meta">
            <span class="chat-endpoint" title="${{escAttr(fromMeta.title)}}">
              <span class="chat-name status-${{fromMeta.status}}">${{escAttr(fromMeta.label)}}</span>
              ${{fromMeta.idTag ? `<span class="chat-id-bg status-${{fromMeta.status}}">${{escAttr(fromMeta.idTag)}}</span>` : ""}}
            </span>
            <span class="chat-feed-arrow">&rarr;</span>
            <span class="chat-endpoint" title="${{escAttr(toMeta.title)}}">
              <span class="chat-name status-${{toMeta.status}}">${{escAttr(toMeta.label)}}</span>
              ${{toMeta.idTag ? `<span class="chat-id-bg status-${{toMeta.status}}">${{escAttr(toMeta.idTag)}}</span>` : ""}}
            </span>
            ${{hasHop ? `<span class="chat-feed-hops" title="${{escAttr(hopTitle)}}">${{escAttr(hopLabel)}}</span>` : ""}}
            <span class="chat-feed-actions">${{reactButton}}</span>
            <span class="chat-feed-time">${{escAttr(timeText)}}</span>
          </div>
          <div class="chat-feed-text">${{textHtml || "&nbsp;"}}</div>
          ${{reactionRow}}
        </div>`;
      }});
      if (activeChatChannel === "all" && participants.size === 0) {{
        for (const msg of baseMessages) {{
          if (classifyMessageChannel(msg) !== "all") continue;
          touchNodeById(msg.from, parseDashboardTimeToUnix(msg.rx_time || msg.captured_at || ""));
        }}
      }}
      if (activeChatChannel === "direct" && isSelectableNodeId(selectedNodeId)) {{
        touchNodeById(selectedNodeId);
      }}
      const feed = document.getElementById("chat-feed");
      if (feed) {{
        feed.innerHTML = feedItems.length > 0
          ? feedItems.join("")
          : `<div class="chat-feed-empty">No ${{channelLabel(activeChatChannel).toLowerCase()}} messages yet.</div>`;
      }}

      const roomList = document.getElementById("chat-room-list");
      const roster = Array.from(participants.values())
        .sort((a, b) => {{
          const rankDiff = statusRank(a.status) - statusRank(b.status);
          if (rankDiff !== 0) return rankDiff;
          const aTime = a.lastMessageUnix || 0;
          const bTime = b.lastMessageUnix || 0;
          if (aTime !== bTime) return bTime - aTime;
          return String(a.name || a.id).localeCompare(String(b.name || b.id));
        }})
        .slice(0, chatRosterMaxEntries);
      const onlineCount = roster.filter((item) => item.status === "online").length;
      const warnCount = roster.filter((item) => item.status === "warn").length;
      const staleCount = roster.filter((item) => item.status === "stale").length;
      if (roomList) {{
        roomList.innerHTML = roster.map((item) => (
          `<div class="chat-member-item status-${{item.status}}${{selectedNodeId === item.id ? " selected-node" : ""}}" data-node-id="${{escAttr(item.id)}}" title="${{escAttr(`${{item.name}} (${{item.id}})`)}}">
            <span class="chat-member-status status-${{item.status}}">●</span>
            <span class="chat-member-main">
              <span class="chat-member-name status-${{item.status}}">${{escAttr(item.name)}}</span>
              <span class="chat-member-id">${{escAttr(item.id)}}</span>
            </span>
          </div>`
        )).join("");
        for (const member of roomList.querySelectorAll(".chat-member-item")) {{
          member.addEventListener("click", () => {{
            selectNode(member.dataset.nodeId || "", true);
          }});
        }}
      }}
      const leftSub = document.getElementById("chat-left-sub");
      if (leftSub) {{
        leftSub.textContent = `${{channelLabel(activeChatChannel)}}: ${{onlineCount}} online, ${{warnCount}} aging, ${{staleCount}} stale`;
      }}

      bindChatAutoScroll();
      bindChatFeedClicks();
      bindChatReactionControls();
      highlightNodeSelection();
      if (pendingSelectionScroll) {{
        scrollSelectionIntoView();
      }} else if (chatScroller instanceof HTMLElement && shouldStickBottom) {{
        requestAnimationFrame(() => {{
          chatScroller.scrollTop = chatScroller.scrollHeight;
          chatStickToBottom = true;
        }});
      }}

      const caption = document.getElementById("chat-caption");
      if (caption) {{
        const preset = s.modem_preset || "unknown";
        caption.textContent = `LoRa preset: ${{preset}}. Channel: ${{channelLabel(activeChatChannel)}}. ${{onlineCount}} online, ${{warnCount}} aging, ${{staleCount}} stale.`;
      }}
    }}

    function renderPackets(traffic) {{
      const packets = (traffic.recent_packets || []).slice().reverse().slice(0, 120);
      const rows = packets.map((entry) => {{
        const s = entry.summary || {{}};
        const text = s.decoded_text == null ? "" : String(s.decoded_text);
        return `<tr>
          <td data-sort="${{escAttr(s.captured_at || "")}}">${{s.captured_at || "n/a"}}</td>
          <td data-sort="${{escAttr(s.from || "")}}">${{s.from || "n/a"}}</td>
          <td data-sort="${{escAttr(s.to || "")}}">${{s.to || "n/a"}}</td>
          <td data-sort="${{escAttr(s.portnum || "")}}">${{s.portnum || "n/a"}}</td>
          <td data-sort="${{escAttr(s.rx_snr ?? "")}}">${{s.rx_snr ?? "n/a"}}</td>
          <td data-sort="${{escAttr(s.rx_rssi ?? "")}}">${{s.rx_rssi ?? "n/a"}}</td>
          <td data-sort="${{escAttr(text)}}">${{text}}</td>
        </tr>`;
      }});
      fillTable("packets-table", rows);
    }}

    function setRaw(id, value) {{
      const el = document.getElementById(id);
      if (!el) return;
      el.textContent = JSON.stringify(value, null, 2);
    }}

    function renderRaw(state) {{
      setRaw("raw-my-info", state.my_info);
      setRaw("raw-metadata", state.metadata);
      setRaw("raw-local-config", (state.local_state || {{}}).local_config);
      setRaw("raw-module-config", (state.local_state || {{}}).module_config);
      setRaw("raw-channels", (state.local_state || {{}}).channels);
      setRaw("raw-nodes-full", state.nodes_full);
    }}

    async function poll() {{
      try {{
        const resp = await fetch("/api/state", {{ cache: "no-store" }});
        if (!resp.ok) throw new Error(`API ${{resp.status}}`);
        const state = await resp.json();
        latestState = state;
        let nodeHistory = null;
        if (isSelectableNodeId(selectedNodeId)) {{
          try {{
            nodeHistory = await fetchNodeHistory(selectedNodeId);
          }} catch (historyErr) {{
            renderNodeHistoryLoading(selectedNodeId);
            const caption = document.getElementById("node-history-caption");
            if (caption) {{
              caption.textContent = `History error for ${{selectedNodeId}}: ${{historyErr.message}}`;
            }}
          }}
        }}
        renderSummary(state);
        renderMap(state.nodes || [], (state.traffic || {{}}).edges || []);
        renderNodes(state.nodes || []);
        renderTraffic(state.traffic || {{}}, state.nodes || [], nodeHistory);
        renderChat(state);
        renderPackets(state.traffic || {{}});
        renderConsole(state.traffic || {{}});
        renderRaw(state);
      }} catch (err) {{
        setText("updated-at", `error: ${{err.message}}`);
        appendConsoleLine(`error|${{Date.now()}}|${{err.message}}`, `[poll error] ${{err.message}}`);
      }}
    }}

    loadStoredSelection();
    loadNodeNameCache();
    loadSplitState();
    loadLayoutView();
    loadChatChannel();
    bindLayoutNav();
    bindSplitters();
    bindSelectionControls();
    bindConsoleControls();
    bindChatComposer();
    bindChatAutoScroll();
    bindHistoryTabs();
    bindWheelPassthrough();
    renderSelectionStatus();
    if (isSelectableNodeId(selectedNodeId)) {{
      renderNodeHistoryLoading(selectedNodeId);
    }} else {{
      setMapDataMode("live");
    }}
    requestMapResize();

    poll();
    setInterval(poll, refreshMs);
  </script>
</body>
</html>
"""


def _make_http_handler(html_text: str, state_fn, node_history_fn=None, send_chat_fn=None):
    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            try:
                parsed = urlparse(self.path)
                path = parsed.path

                if path in ("/", "/index.html"):
                    body = html_text.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

                if path == "/api/state":
                    payload = json.dumps(state_fn(), separators=(",", ":")).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return

                if path == "/api/history/node":
                    query = parse_qs(parsed.query)
                    node_id = (query.get("node_id", [""])[0] or "").strip()
                    hours_override = _to_int(query.get("hours", [""])[0])
                    points_override = _to_int(query.get("points", [""])[0])
                    if node_history_fn is None:
                        response_obj = {"node_id": node_id, "points": [], "summary": {}}
                    else:
                        response_obj = node_history_fn(node_id, hours_override, points_override)
                    payload = json.dumps(response_obj, separators=(",", ":")).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return

                self.send_response(404)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Not Found")
            except (BrokenPipeError, ConnectionResetError):
                return

        def do_POST(self) -> None:
            try:
                parsed = urlparse(self.path)
                path = parsed.path
                if path != "/api/chat/send":
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b'{"ok":false,"error":"Not Found"}')
                    return

                if send_chat_fn is None:
                    payload = json.dumps(
                        {"ok": False, "error": "Chat send is not enabled on this dashboard instance"},
                        separators=(",", ":"),
                    ).encode("utf-8")
                    self.send_response(503)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return

                content_length = _to_int(self.headers.get("Content-Length")) or 0
                if content_length <= 0 or content_length > 8192:
                    payload = json.dumps(
                        {"ok": False, "error": "Invalid request size"},
                        separators=(",", ":"),
                    ).encode("utf-8")
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return

                raw = self.rfile.read(content_length)
                try:
                    body = json.loads(raw.decode("utf-8"))
                except Exception:
                    body = {}

                text = body.get("text") if isinstance(body, dict) else None
                destination = body.get("destination") if isinstance(body, dict) else None
                channel_index = _to_int(body.get("channel_index")) if isinstance(body, dict) else None
                reply_id = _to_int(body.get("reply_id")) if isinstance(body, dict) else None
                emoji = body.get("emoji") if isinstance(body, dict) else None

                try:
                    response_obj = send_chat_fn(
                        text=text,
                        destination=destination,
                        channel_index=channel_index,
                        reply_id=reply_id,
                        emoji=emoji,
                    )
                except ValueError as exc:
                    payload = json.dumps(
                        {"ok": False, "error": str(exc)},
                        separators=(",", ":"),
                    ).encode("utf-8")
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                except Exception as exc:
                    payload = json.dumps(
                        {"ok": False, "error": f"Send failed: {exc}"},
                        separators=(",", ":"),
                    ).encode("utf-8")
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return

                payload = json.dumps(response_obj, separators=(",", ":")).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                return

        def log_message(self, format: str, *args: Any) -> None:
            return

    return DashboardHandler


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

    def node_history_fn(
        node_id: str,
        hours_override: Optional[int] = None,
        points_override: Optional[int] = None,
    ) -> Dict[str, Any]:
        clean_node_id = str(node_id or "").strip()
        if history_store is None:
            return {"node_id": clean_node_id, "points": [], "summary": {}}
        hours = hours_override if isinstance(hours_override, int) and hours_override > 0 else args.node_history_hours
        points = (
            points_override
            if isinstance(points_override, int) and points_override > 0
            else args.node_history_max_points
        )
        return history_store.load_node_history(
            node_id=clean_node_id,
            window_hours=hours,
            max_points=points,
        )

    def send_chat_fn(
        text: Any,
        destination: Any = None,
        channel_index: Optional[int] = None,
        reply_id: Optional[int] = None,
        emoji: Any = None,
    ) -> Dict[str, Any]:
        clean_text = str(text or "").strip()
        clean_reply_id = _to_int(reply_id)
        clean_emoji, clean_emoji_codepoint = _normalize_single_emoji(emoji)

        has_reaction = bool(
            clean_reply_id is not None and clean_reply_id > 0 and clean_emoji and clean_emoji_codepoint
        )
        if clean_emoji and not has_reaction:
            raise ValueError("Emoji reactions require a valid reply_id")
        if clean_reply_id is not None and clean_reply_id <= 0:
            raise ValueError("reply_id must be a positive packet id")
        if has_reaction and clean_text:
            raise ValueError("Emoji reactions must not include text")
        if not clean_text and not has_reaction:
            raise ValueError("Message cannot be empty")

        if clean_text:
            payload_bytes = clean_text.encode("utf-8")
            if len(payload_bytes) > DEFAULT_CHAT_MAX_BYTES:
                raise ValueError(
                    f"Message is too long ({len(payload_bytes)} bytes). Limit is {DEFAULT_CHAT_MAX_BYTES} bytes."
                )

        dest = str(destination or "^all").strip() or "^all"
        if dest.lower() in ("all", "broadcast"):
            dest = "^all"
        if not (dest == "^all" or dest.startswith("!")):
            raise ValueError("Destination must be '^all' or a node id like !abcdef12")

        chan = channel_index if isinstance(channel_index, int) and channel_index >= 0 else 0
        sent_packet: Any
        with send_lock:
            if has_reaction:
                sent_packet = _send_emoji_reaction_packet(
                    iface=iface,
                    destination_id=dest,
                    channel_index=chan,
                    reply_id=clean_reply_id,
                    emoji_codepoint=clean_emoji_codepoint,
                    emoji_text=clean_emoji,
                )
            else:
                sent_packet = iface.sendText(
                    clean_text,
                    destinationId=dest,
                    channelIndex=chan,
                    replyId=clean_reply_id if clean_reply_id and clean_reply_id > 0 else None,
                )

        local_id = _get_local_node_id(iface)
        sent_packet_id = _to_int(getattr(sent_packet, "id", None))
        tracker.record_local_chat(
            text=clean_text if clean_text else "",
            from_id=local_id,
            to_id=dest,
            channel_index=chan,
            message_id=sent_packet_id,
            reply_id=clean_reply_id,
            emoji=clean_emoji,
            emoji_codepoint=clean_emoji_codepoint,
            is_reaction=has_reaction,
        )
        response = {
            "ok": True,
            "sent_at": _utc_now(),
            "from": local_id,
            "to": dest,
            "channel_index": chan,
            "message_id": sent_packet_id,
            "reply_id": clean_reply_id,
        }
        if has_reaction:
            response["reaction"] = clean_emoji
            response["reaction_codepoint"] = clean_emoji_codepoint
            response["text"] = ""
        else:
            response["text"] = clean_text
        return response

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
