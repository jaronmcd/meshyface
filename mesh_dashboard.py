import argparse
import json
import os
import socket
import sqlite3
import threading
import time
from collections import Counter, deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import meshtastic
from mesh_connection import add_mesh_connection_args, mesh_target_label, open_mesh_interface
from pubsub import pub

try:
    from google.protobuf.json_format import MessageToDict
    from google.protobuf.message import Message
except Exception:
    Message = None
    MessageToDict = None


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
MIN_REAL_LINK_COUNT = 2

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


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_epoch(epoch_value: Any) -> Optional[str]:
    epoch = _to_int(epoch_value)
    if epoch is None or epoch <= 0:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def _safe_json_loads(value: str, default: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _calculate_hops(hop_start: Any, hop_limit: Any) -> Optional[int]:
    start = _to_int(hop_start)
    limit = _to_int(hop_limit)
    if start is None or limit is None:
        return None
    hops = start - limit
    if hops < 0:
        return None
    return hops


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
    def __init__(self, db_path: str, max_rows: int, retention_days: int) -> None:
        self.db_path = db_path
        self.max_rows = max(100, int(max_rows))
        self.retention_seconds = max(0, int(retention_days)) * 86400
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
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_packets_created_unix ON packets(created_unix)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_created_unix ON chat(created_unix)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_connections_last_seen_unix ON connections(last_seen_unix)"
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
            "from": from_id,
            "to": to_id,
            "from_num": _to_int(packet.get("from")),
            "to_num": _to_int(packet.get("to")),
            "portnum": str(portnum) if portnum is not None else None,
            "rx_time": _format_epoch(packet.get("rxTime")),
            "rx_rssi": packet.get("rxRssi"),
            "rx_snr": packet.get("rxSnr"),
            "hop_start": packet.get("hopStart"),
            "hop_limit": packet.get("hopLimit"),
            "want_ack": packet.get("wantAck"),
            "priority": packet.get("priority"),
            "channel": packet.get("channel"),
            "decoded_text": decoded.get("text") if isinstance(decoded, dict) else None,
        }

        packet_entry = {
            "summary": packet_summary,
            "packet": _to_jsonable(packet),
        }
        self.recent_packets.append(packet_entry)
        if self._history_store is not None and include_live_count:
            self._history_store.save_packet(packet_entry)

        decoded_text = decoded.get("text") if isinstance(decoded, dict) else None
        if isinstance(decoded_text, str) and decoded_text.strip():
            chat_entry = {
                "captured_at": _utc_now(),
                "from": from_id,
                "to": to_id,
                "portnum": str(portnum) if portnum is not None else None,
                "channel": packet.get("channel"),
                "rx_time": _format_epoch(packet.get("rxTime")),
                "text": decoded_text,
            }
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
) -> Dict[str, Any]:
    nodes = _collect_nodes(iface)
    tracker_data = tracker.snapshot(nodes["by_id"])

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
    .topbar .sub {{ margin-top: 2px; font-size: 11px; opacity: 0.95; }}
    .layout {{
      --split-left-pct: 64%;
      --splitter-size: 8px;
      display: grid;
      gap: 8px;
      padding: 8px;
      grid-template-columns: minmax(380px, var(--split-left-pct)) var(--splitter-size) minmax(320px, 1fr);
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
      grid-column: 3;
      grid-row: 2;
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
      grid-column: 1;
      grid-row: 2;
      display: flex;
      flex-direction: column;
      min-height: 0;
    }}
    .map-data {{ grid-column: 3; grid-row: 3; }}
    .nodes {{ grid-column: 1; grid-row: 3; }}
    .nodes .scroll {{ max-height: 470px; }}
    .packets {{ grid-column: 1; grid-row: 4; }}
    .raw {{ grid-column: 3; grid-row: 4; }}
    .console {{ grid-column: 1 / span 3; grid-row: 5; }}
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
    .splitter[data-row="2"] {{ grid-row: 2; }}
    .splitter[data-row="3"] {{ grid-row: 3; }}
    .splitter[data-row="4"] {{ grid-row: 4; }}
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
    body.resizing-panels, body.resizing-panels * {{
      cursor: col-resize !important;
      user-select: none !important;
    }}
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
    #nodes-table tbody tr.node-selectable,
    #chat-table tbody tr.chat-selectable {{
      cursor: pointer;
    }}
    #nodes-table tbody tr.node-selectable:hover,
    #chat-table tbody tr.chat-selectable:hover {{
      background: #edf8f1;
    }}
    #nodes-table tbody tr.selected-node,
    #chat-table tbody tr.selected-node {{
      background: #d8efe1;
    }}
    .mono {{ font-family: "IBM Plex Mono", "Consolas", "Menlo", monospace; }}
    #nodes-table th:nth-child(1), #nodes-table td:nth-child(1) {{ width: 16%; }}
    #nodes-table th:nth-child(2), #nodes-table td:nth-child(2) {{ width: 16%; }}
    #nodes-table th:nth-child(3), #nodes-table td:nth-child(3) {{ width: 20%; }}
    #nodes-table th:nth-child(4), #nodes-table td:nth-child(4) {{ width: 19%; }}
    #nodes-table th:nth-child(5), #nodes-table td:nth-child(5) {{ width: 7%; }}
    #nodes-table th:nth-child(6), #nodes-table td:nth-child(6) {{ width: 6%; }}
    #nodes-table th:nth-child(7), #nodes-table td:nth-child(7) {{ width: 8%; }}
    #nodes-table th:nth-child(8), #nodes-table td:nth-child(8) {{ width: 8%; }}
    .chat .body {{
      display: flex;
      flex-direction: column;
      flex: 1;
      min-height: 0;
    }}
    .chat .scroll {{
      flex: 1;
      max-height: none;
      min-height: 220px;
    }}
    #chat-table {{
      table-layout: auto;
    }}
    #chat-table th:nth-child(1), #chat-table td:nth-child(1) {{ width: 20%; white-space: nowrap; }}
    #chat-table th:nth-child(2), #chat-table td:nth-child(2) {{ width: 16%; white-space: nowrap; }}
    #chat-table th:nth-child(3), #chat-table td:nth-child(3) {{ width: 10%; white-space: nowrap; }}
    #chat-table th:nth-child(4), #chat-table td:nth-child(4) {{
      width: 54%;
      white-space: normal;
      overflow: visible;
      text-overflow: clip;
      word-break: break-word;
      line-height: 1.25;
    }}
    #chat-table td {{ vertical-align: top; }}
    .scroll {{
      max-height: 300px;
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
      .layout {{ grid-template-columns: 1fr; }}
      .splitter {{ display: none; }}
      .summary, .map, .map-data, .nodes, .chat, .packets, .raw, .console {{ grid-column: 1; grid-row: auto; }}
      .map-frame {{ max-width: none; }}
      .nodes .scroll {{ max-height: 360px; }}
    }}
  </style>
</head>
<body>
  <div class="topbar">
    <h1>Meshtastic Deep Dashboard</h1>
    <div class="sub">
      Live node, traffic, config, and packet views.
      <span class="pill">{safety_label}</span>
      <span class="pill">Packet buffer: {packet_limit}</span>
      <span class="pill">{history_label}</span>
      <span class="pill">Refresh: {refresh_ms} ms</span>
      <span class="pill selection-pill" id="selected-node-pill">Selected: none</span>
      <button id="clear-selection-btn" class="selection-btn" type="button" disabled>Clear</button>
    </div>
  </div>

  <div class="layout">
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
        <div class="scroll">
          <table id="chat-table">
            <thead>
              <tr>
                <th>Time</th><th>From</th><th>To</th><th>Text</th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </section>

    <div class="splitter" data-row="2" title="Drag to resize columns"></div>

    <section class="card map">
      <h2>Network Map</h2>
      <div class="body">
        <div class="map-frame">
          <div id="map"></div>
        </div>
      </div>
    </section>

    <section class="card nodes">
      <h2>Nodes</h2>
      <div class="body scroll">
        <table id="nodes-table">
          <thead>
            <tr>
              <th>Last Heard</th><th>ID</th><th>Name</th><th>HW</th><th>SNR</th><th>Hops</th><th>Battery</th><th>Pos</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </section>

    <div class="splitter" data-row="3" title="Drag to resize columns"></div>

    <section class="card map-data">
      <h2>Map Data</h2>
      <div class="body">
        <h3 style="margin:0 0 8px 0;font-size:13px;">Top Ports</h3>
        <div class="scroll" style="max-height:150px;">
          <table id="ports-table">
            <thead><tr><th>Port</th><th>Count</th></tr></thead>
            <tbody></tbody>
          </table>
        </div>
        <h3 style="margin:10px 0 8px 0;font-size:13px;">Top Links</h3>
        <div class="scroll" style="max-height:170px;">
          <table id="links-table">
            <thead><tr><th>From</th><th>To</th><th>Count</th><th>Hops</th><th>Status</th><th>Last</th></tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </section>

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

    <div class="splitter" data-row="4" title="Drag to resize columns"></div>

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

  <script
    src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    crossorigin=""
  ></script>
  <script>
    const refreshMs = {refresh_ms};
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
    const splitStorageKey = "meshDashboardSplitPct";
    const consoleMaxLines = 1200;
    const tableSortState = {{
      "nodes-table": {{ index: 0, dir: "desc" }},
      "chat-table": {{ index: 0, dir: "desc" }},
      "links-table": {{ index: 2, dir: "desc" }},
      "ports-table": {{ index: 1, dir: "desc" }},
      "packets-table": {{ index: 0, dir: "desc" }},
    }};
    const wheelActivationLeaseMs = 1400;
    const sortableTables = new Set(Object.keys(tableSortState));
    const consoleLines = [];
    const consoleKeyQueue = [];
    const consoleSeen = new Set();
    const wheelPaneSelector = ".scroll, #live-console, details pre";
    let selectedNodeId = null;
    let pendingSelectionScroll = false;
    let lastMapSignature = "";
    let mapResizeRaf = null;
    let splitPct = 64;
    let consoleAutoscroll = true;
    let fitDone = false;
    let mapResizeObserver = null;
    let activeWheelPane = null;
    let activeWheelPaneLease = null;
    let mapWheelZoomActive = false;
    let mapWheelJustArmed = false;
    let mapWheelLease = null;

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

    function nodeLabel(node) {{
      return node.long_name || node.short_name || node.id || "unknown";
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

    function isSelectableNodeId(nodeId) {{
      return !!nodeId && nodeId !== "^all" && nodeId !== "Unknown" && nodeId !== "n/a";
    }}

    function loadStoredSelection() {{
      try {{
        const stored = window.localStorage.getItem(selectionStorageKey);
        if (isSelectableNodeId(stored)) {{
          selectedNodeId = String(stored);
        }}
      }} catch (_err) {{
      }}
    }}

    function persistSelection() {{
      try {{
        if (isSelectableNodeId(selectedNodeId)) {{
          window.localStorage.setItem(selectionStorageKey, String(selectedNodeId));
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

    function applySplitPct(value) {{
      const layout = document.querySelector(".layout");
      if (!layout) return;
      layout.style.setProperty("--split-left-pct", `${{value}}%`);
    }}

    function loadSplitState() {{
      try {{
        const stored = Number.parseFloat(window.localStorage.getItem(splitStorageKey) || "");
        if (Number.isFinite(stored)) {{
          splitPct = clampSplitPct(stored);
        }}
      }} catch (_err) {{
      }}
      applySplitPct(splitPct);
    }}

    function persistSplitState() {{
      try {{
        window.localStorage.setItem(splitStorageKey, String(splitPct));
      }} catch (_err) {{
      }}
    }}

    function bindSplitters() {{
      const layout = document.querySelector(".layout");
      if (!(layout instanceof HTMLElement)) return;

      for (const splitter of document.querySelectorAll(".splitter")) {{
        if (!(splitter instanceof HTMLElement) || splitter.dataset.bound === "1") continue;
        splitter.dataset.bound = "1";

        splitter.addEventListener("pointerdown", (ev) => {{
          if (window.matchMedia("(max-width: 1100px)").matches) return;
          ev.preventDefault();
          splitter.classList.add("active");
          document.body.classList.add("resizing-panels");
          splitter.setPointerCapture(ev.pointerId);

          const rect = layout.getBoundingClientRect();
          const onMove = (moveEv) => {{
            const pct = clampSplitPct(((moveEv.clientX - rect.left) / rect.width) * 100);
            splitPct = pct;
            applySplitPct(splitPct);
            requestMapResize();
          }};

          const onUp = () => {{
            splitter.classList.remove("active");
            document.body.classList.remove("resizing-panels");
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
        const nodeId = row.dataset.nodeId || "";
        row.classList.toggle("selected-node", !!selectedNodeId && nodeId === selectedNodeId);
      }}
      for (const row of document.querySelectorAll("#chat-table tbody tr")) {{
        const nodeId = row.dataset.nodeId || "";
        row.classList.toggle("selected-node", !!selectedNodeId && nodeId === selectedNodeId);
      }}
    }}

    function scrollSelectionIntoView() {{
      if (!selectedNodeId) {{
        pendingSelectionScroll = false;
        return;
      }}

      let didScroll = false;
      for (const tableId of ["nodes-table", "chat-table"]) {{
        let targetRow = null;
        for (const row of document.querySelectorAll(`#${{tableId}} tbody tr`)) {{
          if ((row.dataset.nodeId || "") === selectedNodeId) {{
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

    function selectNode(nodeId, shouldFocus = true) {{
      if (!isSelectableNodeId(nodeId)) return;
      selectedNodeId = String(nodeId);
      pendingSelectionScroll = true;
      persistSelection();
      renderSelectionStatus();
      highlightNodeSelection();
      updateMapSelection(shouldFocus);
      scrollSelectionIntoView();
    }}

    function clearNodeSelection() {{
      selectedNodeId = null;
      pendingSelectionScroll = false;
      persistSelection();
      renderSelectionStatus();
      highlightNodeSelection();
      updateMapSelection(false);
      map.closePopup();
    }}

    function bindNodeRowClicks() {{
      for (const row of document.querySelectorAll("#nodes-table tbody tr.node-selectable")) {{
        row.addEventListener("click", () => {{
          selectNode(row.dataset.nodeId || "", true);
        }});
      }}
    }}

    function bindChatRowClicks() {{
      for (const row of document.querySelectorAll("#chat-table tbody tr.chat-selectable")) {{
        row.addEventListener("click", () => {{
          selectNode(row.dataset.nodeId || "", true);
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
    }}

    function buildMapSignature(nodes, edges) {{
      const nodeSig = (nodes || [])
        .filter((node) => typeof node.lat === "number" && typeof node.lon === "number")
        .map((node) => `${{node.id}}:${{node.lat.toFixed(5)}},${{node.lon.toFixed(5)}}`)
        .join("|");
      const edgeSig = (edges || [])
        .map((edge) => `${{edge.from}}>${{edge.to}}:${{edge.lifetime_count ?? edge.count ?? 0}}:${{edge.last_rx_time || ""}}:${{edge.last_hops ?? ""}}`)
        .join("|");
      return `${{nodeSig}}#${{edgeSig}}`;
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
      const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));

      for (const node of nodes) {{
        if (typeof node.lat !== "number" || typeof node.lon !== "number") continue;
        const isSelected = !!selectedNodeId && node.id === selectedNodeId;
        const marker = L.circleMarker([node.lat, node.lon], markerStyle(isSelected));
        marker.bindPopup(`
          <b>${{nodeLabel(node)}}</b><br/>
          ${{node.id}}<br/>
          Num: ${{node.num ?? "n/a"}}<br/>
          SNR: ${{node.snr ?? "n/a"}}<br/>
          Last: ${{node.last_heard || "n/a"}}
        `);
        marker.on("click", () => {{
          selectNode(String(node.id || ""), false);
        }});
        marker.addTo(nodeLayer);
        nodeMarkers.set(String(node.id || ""), marker);
        features.push(marker);
      }}

      for (const edge of edges) {{
        const src = byId[edge.from];
        const dst = byId[edge.to];
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
          const nodeId = String(node.id || "");
          const selectable = isSelectableNodeId(nodeId);
          const pos = (typeof node.lat === "number" && typeof node.lon === "number")
            ? `${{node.lat.toFixed(5)}}, ${{node.lon.toFixed(5)}}`
            : "n/a";
          const name = nodeLabel(node);
          return `<tr data-node-id="${{escAttr(nodeId)}}" class="${{selectable ? "node-selectable" : ""}}">
          <td data-sort="${{escAttr(node.last_heard ?? "")}}">${{node.last_heard ?? "n/a"}}</td>
          <td class="mono" data-sort="${{escAttr(nodeId)}}">${{nodeId}}</td>
          <td data-sort="${{escAttr(name)}}">${{name}}</td>
          <td data-sort="${{escAttr(node.hardware_model ?? "")}}">${{node.hardware_model ?? "n/a"}}</td>
          <td data-sort="${{escAttr(node.snr ?? "")}}">${{node.snr ?? "n/a"}}</td>
          <td data-sort="${{escAttr(node.hops_away ?? "")}}">${{node.hops_away ?? "n/a"}}</td>
          <td data-sort="${{escAttr(node.battery_level ?? "")}}">${{node.battery_level ?? "n/a"}}</td>
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

    function renderTraffic(traffic) {{
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
      const rows = (traffic.recent_chat || []).slice().reverse().slice(0, 120).map((msg) => {{
        const sourceNode = isSelectableNodeId(msg.from) ? String(msg.from) : "";
        const fallbackNode = isSelectableNodeId(msg.to) ? String(msg.to) : "";
        const nodeId = sourceNode || fallbackNode;
        const selectableClass = nodeId ? "chat-selectable" : "";
        return `<tr data-node-id="${{escAttr(nodeId)}}" class="${{selectableClass}}">
          <td data-sort="${{escAttr(msg.rx_time || msg.captured_at || "")}}">${{msg.rx_time || msg.captured_at || "n/a"}}</td>
          <td data-sort="${{escAttr(msg.from || "")}}">${{msg.from || "n/a"}}</td>
          <td data-sort="${{escAttr(msg.to || "")}}">${{msg.to || "n/a"}}</td>
          <td data-sort="${{escAttr(msg.text || "")}}">${{msg.text || ""}}</td>
        </tr>`;
      }});
      fillTable("chat-table", rows);
      bindChatRowClicks();
      highlightNodeSelection();
      if (pendingSelectionScroll) {{
        scrollSelectionIntoView();
      }}

      const caption = document.getElementById("chat-caption");
      if (caption) {{
        const preset = s.modem_preset || "unknown";
        caption.textContent = `LoRa preset: ${{preset}}. Showing decoded text messages from recent packets.`;
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
        renderSummary(state);
        renderMap(state.nodes || [], (state.traffic || {{}}).edges || []);
        renderNodes(state.nodes || []);
        renderTraffic(state.traffic || {{}});
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
    loadSplitState();
    bindSplitters();
    bindSelectionControls();
    bindConsoleControls();
    bindWheelPassthrough();
    renderSelectionStatus();
    requestMapResize();

    poll();
    setInterval(poll, refreshMs);
  </script>
</body>
</html>
"""


def _make_http_handler(html_text: str, state_fn):
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

                self.send_response(404)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Not Found")
            except (BrokenPipeError, ConnectionResetError):
                return

        def log_message(self, format: str, *args: Any) -> None:
            return

    return DashboardHandler


def run_dashboard(args: argparse.Namespace) -> None:
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
            )
        except Exception as exc:
            print(f"History disabled: cannot open {history_db_path}: {exc}")
            history_store = None

    tracker = DashboardTracker(packet_limit=args.packet_limit, history_store=history_store)
    pub.subscribe(tracker.on_receive, "meshtastic.receive")
    if not tracker.has_recent_packets():
        _seed_tracker_from_node_db(tracker, iface)
    started_at = time.time()

    def state_fn() -> Dict[str, Any]:
        return _build_state(
            iface=iface,
            tracker=tracker,
            started_at=started_at,
            target=target,
            show_secrets=args.show_secrets,
        )

    html = _render_html(
        refresh_ms=args.refresh_ms,
        packet_limit=args.packet_limit,
        show_secrets=args.show_secrets,
        history_enabled=history_store is not None,
        history_max_rows=args.history_max_rows,
        history_retention_days=args.history_retention_days,
    )
    handler_cls = _make_http_handler(html, state_fn)
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
    if history_store is not None:
        print(
            f"History DB: {history_db_path} "
            f"(retention {args.history_retention_days}d, max {args.history_max_rows} rows)"
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
        help=f"SQLite DB path for persisted chat/packet history (default: {DEFAULT_HISTORY_DB})",
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
        "--no-history",
        action="store_true",
        help="Disable persisted SQLite history (memory-only live buffers).",
    )
    args = parser.parse_args()
    _apply_default_gateway(args)
    run_dashboard(args)


if __name__ == "__main__":
    main()
