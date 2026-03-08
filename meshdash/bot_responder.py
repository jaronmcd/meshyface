import json
import os
import threading
import time
from typing import Callable, Optional

from .bot_commands import (
    DEFAULT_ENABLED_MANAGED_BOT_COMMAND_NAMES,
    MANAGED_BOT_COMMAND_SPECS,
    STANDARD_BOT_COMMANDS as _STANDARD_BOT_COMMANDS,
    build_custom_bot_command_spec,
    normalize_bot_command_name,
)
from .bot_apps.base import BotApp
from .bot_apps.registry import build_builtin_bot_apps
from .helpers import to_int as _to_int

STANDARD_BOT_COMMANDS = _STANDARD_BOT_COMMANDS

_RECENT_PACKET_TTL_SECONDS = 180
_RECENT_PACKET_MAX = 1024


def _parse_bool_token(value: object, default: bool) -> bool:
    if value is None:
        return default
    text = str(value).strip().lower()
    if not text:
        return default
    if text in ("1", "true", "yes", "on", "enable", "enabled"):
        return True
    if text in ("0", "false", "no", "off", "disable", "disabled"):
        return False
    return default


def _is_hex_text(value: str) -> bool:
    return bool(value) and all(ch in "0123456789abcdefABCDEF" for ch in value)


def _normalize_node_id(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in ("^all", "all", "broadcast", "!ffffffff", "ffffffff", "0xffffffff", "4294967295"):
        return "^all"
    if text.startswith("!") and len(text) == 9 and _is_hex_text(text[1:]):
        return f"!{text[1:].lower()}"
    if len(text) == 8 and _is_hex_text(text):
        return f"!{text.lower()}"
    return text


def _node_suffix(node_id: object) -> str:
    clean = _normalize_node_id(node_id)
    if not clean.startswith("!") or len(clean) != 9:
        return ""
    return clean[1:][-4:]


def _normalize_command_name(value: object) -> str:
    return normalize_bot_command_name(value)


def _format_node_id_from_num(raw_num: object) -> str:
    number = _to_int(raw_num)
    if number is None:
        return ""
    if number < 0:
        return ""
    return f"!{number:08x}"


def _resolve_packet_node_id(raw_id: object, raw_num: object, interface: object) -> str:
    clean_id = _normalize_node_id(raw_id)
    if clean_id:
        return clean_id
    number = _to_int(raw_num)
    if number is None:
        return ""
    nodes_by_num = getattr(interface, "nodesByNum", None)
    if isinstance(nodes_by_num, dict):
        info = nodes_by_num.get(number)
        if isinstance(info, dict):
            user = info.get("user")
            if isinstance(user, dict):
                candidate = _normalize_node_id(user.get("id") or user.get("node_id"))
                if candidate:
                    return candidate
    return _format_node_id_from_num(number)


def _packet_hops(packet: dict[str, object]) -> Optional[int]:
    hop_start = _to_int(packet.get("hopStart"))
    hop_limit = _to_int(packet.get("hopLimit"))
    if hop_start is None or hop_limit is None:
        return None
    diff = hop_start - hop_limit
    if diff < 0:
        return None
    return diff


def _packet_text(decoded: object) -> str:
    if not isinstance(decoded, dict):
        return ""
    raw = decoded.get("text")
    if not isinstance(raw, str):
        return ""
    return raw.strip()


def _is_text_message_packet(packet: dict[str, object]) -> bool:
    decoded = packet.get("decoded")
    if not isinstance(decoded, dict):
        return False
    text = decoded.get("text")
    if isinstance(text, str) and text.strip():
        return True
    portnum = str(decoded.get("portnum") or "").strip().upper()
    return "TEXT_MESSAGE_APP" in portnum


def _iter_known_nodes(interface: object) -> list[dict[str, object]]:
    nodes_by_num = getattr(interface, "nodesByNum", None)
    if not isinstance(nodes_by_num, dict):
        return []
    rows: list[dict[str, object]] = []
    for raw_num, info in nodes_by_num.items():
        if not isinstance(info, dict):
            continue
        user = info.get("user")
        if not isinstance(user, dict):
            continue
        node_id = _normalize_node_id(user.get("id") or user.get("node_id"))
        if not node_id:
            node_id = _format_node_id_from_num(raw_num)
        if not node_id.startswith("!"):
            continue
        short_name = str(user.get("shortName") or user.get("short_name") or "").strip()
        long_name = str(user.get("longName") or user.get("long_name") or "").strip()
        last_heard = _to_int(info.get("lastHeard") or info.get("last_heard"))
        hops_away = _to_int(info.get("hopsAway") or info.get("hops_away"))
        rows.append(
            {
                "id": node_id,
                "short_name": short_name,
                "long_name": long_name,
                "last_heard": last_heard,
                "hops_away": hops_away,
            }
        )
    return rows


def _node_age_label(last_heard: object, now_unix: int) -> str:
    heard = _to_int(last_heard)
    if heard is None or heard <= 0:
        return "n/a"
    delta = max(0, now_unix - heard)
    if delta < 60:
        return f"{delta}s"
    if delta < 3600:
        return f"{delta // 60}m"
    if delta < 86400:
        return f"{delta // 3600}h"
    return f"{delta // 86400}d"


def _format_latency_label(latency_ms: int) -> str:
    value = max(0, int(latency_ms))
    if value < 1000:
        return f"{value}ms"
    if value < 10000:
        return f"{value / 1000:.1f}s"
    total_seconds = value // 1000
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts[:3])


def _format_short_node_label(node: dict[str, object], now_unix: int) -> str:
    node_id = str(node.get("id") or "").strip() or "unknown"
    short_name = str(node.get("short_name") or "").strip()
    long_name = str(node.get("long_name") or "").strip()
    hops = _to_int(node.get("hops_away"))
    age = _node_age_label(node.get("last_heard"), now_unix)
    id_tail = _node_suffix(node_id) or node_id
    name_text = long_name or short_name or id_tail
    if len(name_text) > 18:
        name_text = f"{name_text[:18].rstrip()}..."
    if hops is None:
        return f"{id_tail}:{name_text}/{age}"
    return f"{id_tail}:{name_text}/{hops}h/{age}"


def _find_node_for_query(query: str, nodes: list[dict[str, object]]) -> Optional[dict[str, object]]:
    raw = str(query or "").strip().lower()
    if not raw:
        return None
    normalized = _normalize_node_id(raw)
    if normalized.startswith("!"):
        for node in nodes:
            node_id = str(node.get("id") or "").strip().lower()
            if node_id == normalized:
                return node

    token = raw.lstrip("!")
    best_score = -1
    best_row: Optional[dict[str, object]] = None
    for node in nodes:
        node_id = str(node.get("id") or "").strip().lower()
        if not node_id.startswith("!"):
            continue
        short_name = str(node.get("short_name") or "").strip().lower()
        long_name = str(node.get("long_name") or "").strip().lower()
        score = -1
        if token and _is_hex_text(token):
            if node_id[1:] == token:
                score = 400
            elif node_id[1:].endswith(token):
                score = 300 + min(len(token), 8)
        if short_name and token and short_name == token:
            score = max(score, 240)
        if long_name and token and long_name == token:
            score = max(score, 240)
        if token and long_name and token in long_name:
            score = max(score, 180)
        if token and short_name and token in short_name:
            score = max(score, 170)
        if score > best_score:
            best_score = score
            best_row = node
        elif score >= 0 and score == best_score and best_row is not None:
            prev_heard = _to_int(best_row.get("last_heard")) or 0
            next_heard = _to_int(node.get("last_heard")) or 0
            if next_heard > prev_heard:
                best_row = node
    return best_row if best_score >= 0 else None


def _safe_strftime(unix_seconds: object) -> str:
    value = _to_int(unix_seconds)
    if value is None or value <= 0:
        return "n/a"
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(value))
    except Exception:
        return "n/a"


class MeshResponseBot:
    def __init__(
        self,
        *,
        send_chat_fn: Callable[..., dict[str, object]],
        get_local_node_id_fn: Callable[[object], str],
        custom_commands: Optional[dict[str, str]] = None,
        disabled_commands: Optional[list[str]] = None,
        enabled: bool = True,
        log_enabled: bool = True,
        game_enabled: bool = False,
        reply_broadcast: bool = False,
        now_unix_fn: Callable[[], float] = time.time,
    ) -> None:
        self._send_chat_fn = send_chat_fn
        self._get_local_node_id_fn = get_local_node_id_fn
        self._enabled = bool(enabled)
        self._log_enabled = bool(log_enabled)
        self._reply_broadcast = bool(reply_broadcast)
        self._now_unix_fn = now_unix_fn
        self._custom_commands = {
            _normalize_command_name(name): str(template or "").strip()
            for name, template in (custom_commands or {}).items()
            if _normalize_command_name(name) and str(template or "").strip()
        }
        bot_apps = []
        for app in build_builtin_bot_apps():
            app_name = _normalize_command_name(getattr(getattr(app, "SPEC", None), "name", ""))
            if not app_name:
                continue
            bot_apps.append((app_name, app))
        self._bot_apps_by_name: dict[str, BotApp] = {}
        self._bot_app_order: list[str] = []
        self._bot_app_enabled: dict[str, bool] = {}
        for app_name, app in bot_apps:
            if app_name in self._bot_apps_by_name:
                continue
            self._bot_apps_by_name[app_name] = app
            self._bot_app_order.append(app_name)
            self._bot_app_enabled[app_name] = True
        if "zork" in self._bot_app_enabled:
            self._bot_app_enabled["zork"] = bool(game_enabled)
        raw_disabled_commands = {
            _normalize_command_name(value) for value in (disabled_commands or [])
        }
        known_commands = {
            _normalize_command_name(getattr(spec, "name", ""))
            for spec in list(MANAGED_BOT_COMMAND_SPECS)
            + [
                getattr(app, "SPEC", None)
                for app in self._bot_apps_by_name.values()
            ]
            + [build_custom_bot_command_spec(name) for name in self._custom_commands.keys()]
            if _normalize_command_name(getattr(spec, "name", ""))
        }
        self._disabled_commands = {
            name
            for name in raw_disabled_commands
            if name and name not in self._bot_apps_by_name and name in known_commands
        }
        for name in raw_disabled_commands:
            if name in self._bot_app_enabled:
                self._set_bot_app_enabled_locked(name, False)
        self._recent_packet_ids: dict[str, int] = {}
        self._request_log: list[dict[str, object]] = []
        self._request_seq = 0
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def log_enabled(self) -> bool:
        return self._log_enabled

    @property
    def game_enabled(self) -> bool:
        return bool(self._bot_app_enabled.get("zork"))

    def _active_game_sessions_locked(self) -> int:
        total = 0
        for name in self._bot_app_order:
            app = self._bot_apps_by_name.get(name)
            spec = getattr(app, "SPEC", None)
            kind = str(getattr(spec, "kind", "") or "").strip().lower()
            if kind != "game":
                continue
            try:
                total += int(app.active_session_count())
            except Exception:
                continue
        return total

    def _set_bot_app_enabled_locked(self, name: str, enabled: bool) -> None:
        clean = _normalize_command_name(name)
        if clean not in self._bot_app_enabled:
            return
        self._bot_app_enabled[clean] = bool(enabled)
        if self._bot_app_enabled[clean]:
            return
        app = self._bot_apps_by_name.get(clean)
        if app is None:
            return
        try:
            app.clear_sessions()
        except Exception:
            return

    def _bot_app_specs_locked(self) -> list[object]:
        out: list[object] = []
        for name in self._bot_app_order:
            app = self._bot_apps_by_name.get(name)
            spec = getattr(app, "SPEC", None)
            if _normalize_command_name(getattr(spec, "name", "")):
                out.append(spec)
        return out

    def _managed_command_specs_locked(self) -> list[object]:
        specs = list(MANAGED_BOT_COMMAND_SPECS)
        seen = {
            _normalize_command_name(getattr(spec, "name", ""))
            for spec in specs
            if _normalize_command_name(getattr(spec, "name", ""))
        }
        for spec in self._bot_app_specs_locked():
            name = _normalize_command_name(getattr(spec, "name", ""))
            if not name or name in seen:
                continue
            specs.append(spec)
            seen.add(name)
        for name in sorted(self._custom_commands.keys()):
            specs.append(build_custom_bot_command_spec(name))
        return specs

    def _managed_command_names_locked(self) -> set[str]:
        return {
            _normalize_command_name(getattr(spec, "name", ""))
            for spec in self._managed_command_specs_locked()
            if _normalize_command_name(getattr(spec, "name", ""))
        }

    def _command_enabled_locked(self, command: str) -> bool:
        clean = _normalize_command_name(command)
        if not clean:
            return False
        if clean in self._bot_app_enabled:
            return bool(self._bot_app_enabled.get(clean))
        return clean not in self._disabled_commands

    def _managed_command_rows_locked(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for spec in self._managed_command_specs_locked():
            name = _normalize_command_name(getattr(spec, "name", ""))
            if not name:
                continue
            out.append(
                {
                    "name": name,
                    "usage": str(getattr(spec, "usage", "") or name).strip() or name,
                    "description": str(getattr(spec, "description", "") or "").strip(),
                    "kind": str(getattr(spec, "kind", "") or "builtin").strip().lower(),
                    "enabled": self._command_enabled_locked(name),
                }
            )
        return out

    def _enabled_command_usage_tokens(self) -> list[str]:
        with self._lock:
            rows = self._managed_command_rows_locked()
        return [
            str(row.get("usage") or "").strip()
            for row in rows
            if bool(row.get("enabled")) and str(row.get("usage") or "").strip()
        ]

    def _apply_command_settings_locked(self, command_settings: dict[str, bool]) -> None:
        known_commands = self._managed_command_names_locked()
        unknown_commands = sorted(
            name
            for name in (_normalize_command_name(key) for key in command_settings.keys())
            if name and name not in known_commands
        )
        if unknown_commands:
            raise ValueError(f"Unknown bot command: {unknown_commands[0]}")
        for raw_name, raw_enabled in command_settings.items():
            name = _normalize_command_name(raw_name)
            enabled = bool(raw_enabled)
            if not name:
                continue
            if name in self._bot_app_enabled:
                self._set_bot_app_enabled_locked(name, enabled)
                continue
            if enabled:
                self._disabled_commands.discard(name)
            else:
                self._disabled_commands.add(name)

    def _bot_settings_locked(self) -> dict[str, object]:
        return {
            "enabled": bool(self._enabled),
            "log_enabled": bool(self._log_enabled),
            "game_enabled": bool(self._bot_app_enabled.get("zork")),
            "active_game_sessions": self._active_game_sessions_locked(),
            "disabled_commands": sorted(self._disabled_commands),
            "commands": self._managed_command_rows_locked(),
        }

    def bot_settings(self) -> dict[str, object]:
        with self._lock:
            return dict(self._bot_settings_locked())

    def configure(
        self,
        *,
        enabled: Optional[bool] = None,
        log_enabled: Optional[bool] = None,
        game_enabled: Optional[bool] = None,
        command_settings: Optional[dict[str, bool]] = None,
    ) -> dict[str, object]:
        with self._lock:
            if enabled is not None:
                self._enabled = bool(enabled)
            if log_enabled is not None:
                self._log_enabled = bool(log_enabled)
            if game_enabled is not None:
                self._set_bot_app_enabled_locked("zork", bool(game_enabled))
            if command_settings:
                self._apply_command_settings_locked(command_settings)
            out = self._bot_settings_locked()
        out["ok"] = True
        return out

    def _remember_packet_id(self, from_id: str, packet_id: Optional[int]) -> bool:
        if packet_id is None or packet_id <= 0:
            return False
        key = f"{_normalize_node_id(from_id)}|{packet_id}"
        if not key.startswith("!"):
            key = f"unknown|{packet_id}"
        now_unix = int(self._now_unix_fn())
        seen_at = self._recent_packet_ids.get(key)
        if seen_at is not None and (now_unix - seen_at) <= _RECENT_PACKET_TTL_SECONDS:
            return True
        self._recent_packet_ids[key] = now_unix
        if len(self._recent_packet_ids) > _RECENT_PACKET_MAX:
            oldest = sorted(self._recent_packet_ids.items(), key=lambda item: item[1])[
                : max(1, len(self._recent_packet_ids) - _RECENT_PACKET_MAX)
            ]
            for stale_key, _stale_ts in oldest:
                self._recent_packet_ids.pop(stale_key, None)
        stale_before = now_unix - _RECENT_PACKET_TTL_SECONDS
        for stale_key, seen_unix in list(self._recent_packet_ids.items()):
            if seen_unix < stale_before:
                self._recent_packet_ids.pop(stale_key, None)
        return False

    def _record_request(self, entry: dict[str, object]) -> None:
        if not self._log_enabled:
            return
        with self._lock:
            self._request_seq += 1
            entry["_seq"] = self._request_seq
            self._request_log.append(dict(entry))
            if len(self._request_log) > _RECENT_PACKET_MAX:
                self._request_log = self._request_log[-_RECENT_PACKET_MAX:]

    def _update_request(self, request_id: str, **updates: object) -> None:
        if not self._log_enabled:
            return
        if not request_id:
            return
        with self._lock:
            for row in reversed(self._request_log):
                if str(row.get("id") or "") != request_id:
                    continue
                row.update(updates)
                break

    def recent_requests(self, limit: int = 200) -> list[dict[str, object]]:
        max_rows = max(1, min(1000, int(limit)))
        with self._lock:
            rows = list(self._request_log)
        rows.sort(
            key=lambda row: (
                _to_int(row.get("received_unix")) or 0,
                _to_int(row.get("_seq")) or 0,
            ),
            reverse=True,
        )
        out: list[dict[str, object]] = []
        for row in rows[:max_rows]:
            clean = {k: v for k, v in row.items() if not str(k).startswith("_")}
            out.append(clean)
        return out

    def _local_node_context(self, interface: object) -> tuple[str, set[str], list[dict[str, object]]]:
        local_node_id = ""
        try:
            local_node_id = _normalize_node_id(self._get_local_node_id_fn(interface))
        except Exception:
            local_node_id = ""
        nodes = _iter_known_nodes(interface)
        aliases: set[str] = set()
        if local_node_id:
            aliases.add(local_node_id.lower())
            suffix = _node_suffix(local_node_id)
            if suffix:
                aliases.add(suffix)
            if local_node_id.startswith("!"):
                aliases.add(local_node_id[1:].lower())
        for node in nodes:
            node_id = str(node.get("id") or "").strip().lower()
            if not local_node_id or node_id != local_node_id.lower():
                continue
            short_name = str(node.get("short_name") or "").strip().lower()
            long_name = str(node.get("long_name") or "").strip().lower()
            if short_name:
                aliases.add(short_name)
            if long_name:
                aliases.add(long_name)
            break
        return local_node_id, aliases, nodes

    def _parse_command(self, text: str) -> tuple[str, list[str]] | None:
        raw = str(text or "").strip()
        if not raw:
            return None
        parts = [part for part in raw.split() if part]
        if not parts:
            return None
        head = _normalize_command_name(parts[0])
        if not head:
            return None
        return head, parts[1:]

    def _build_standard_reply(
        self,
        *,
        command: str,
        args: list[str],
        local_node_id: str,
        local_aliases: set[str],
        nodes: list[dict[str, object]],
        packet: dict[str, object],
        received_ms: int,
    ) -> Optional[str]:
        now_unix = int(self._now_unix_fn())
        if command in ("cmd", "help"):
            tokens = self._enabled_command_usage_tokens()
            if not tokens:
                return "cmds: none enabled"
            return f"cmds: {' '.join(tokens)}"

        if command == "whoami":
            if not local_node_id:
                return "whoami: local id unavailable"
            local_node = _find_node_for_query(local_node_id, nodes)
            if local_node is None:
                return f"whoami: {local_node_id}"
            short_name = str(local_node.get("short_name") or "").strip()
            long_name = str(local_node.get("long_name") or "").strip()
            hops = _to_int(local_node.get("hops_away"))
            hops_text = f"{hops}" if hops is not None else "n/a"
            if long_name and short_name:
                return f"whoami: {local_node_id} short={short_name} long={long_name} hops={hops_text}"
            if long_name:
                return f"whoami: {local_node_id} name={long_name} hops={hops_text}"
            if short_name:
                return f"whoami: {local_node_id} short={short_name} hops={hops_text}"
            return f"whoami: {local_node_id} hops={hops_text}"

        if command in ("whois", "whohas"):
            if not args:
                return f"{command}: usage {command} <id|name>"
            query = str(args[0] or "").strip()
            if not query:
                return f"{command}: usage {command} <id|name>"
            match = _find_node_for_query(query, nodes)
            if match is None:
                return f"{command} {query}: unknown"
            node_id = str(match.get("id") or "unknown").strip()
            short_name = str(match.get("short_name") or "").strip()
            long_name = str(match.get("long_name") or "").strip()
            hops = _to_int(match.get("hops_away"))
            hops_text = f"{hops}" if hops is not None else "n/a"
            age = _node_age_label(match.get("last_heard"), now_unix)
            if long_name and short_name:
                return f"{command} {query}: {node_id} {short_name}/{long_name} hops={hops_text} seen={age}"
            if long_name:
                return f"{command} {query}: {node_id} {long_name} hops={hops_text} seen={age}"
            if short_name:
                return f"{command} {query}: {node_id} {short_name} hops={hops_text} seen={age}"
            return f"{command} {query}: {node_id} hops={hops_text} seen={age}"

        if command == "lheard":
            local_id_lower = local_node_id.lower() if local_node_id else ""
            heard = [
                node
                for node in nodes
                if str(node.get("id") or "").strip().lower() != local_id_lower
            ]
            heard.sort(key=lambda row: (_to_int(row.get("last_heard")) or 0), reverse=True)
            if not heard:
                return "lheard: no recent nodes"
            samples = [_format_short_node_label(row, now_unix) for row in heard[:5]]
            return f"lheard: {', '.join(samples)}"

        if command == "ping":
            target = str(args[0] or "").strip().lower() if args else ""
            if target and target not in local_aliases:
                return None
            tx_ms = int(self._now_unix_fn() * 1000)
            latency_ms = max(0, tx_ms - int(received_ms))
            latency_text = _format_latency_label(latency_ms)
            hops = _packet_hops(packet)
            hop_text = f"hop {hops}" if hops is not None else "hop n/a"
            return f"pong {latency_text} {hop_text}"

        return None

    def _build_custom_reply(
        self,
        *,
        command: str,
        args: list[str],
        from_id: str,
        to_id: str,
        local_node_id: str,
        packet: dict[str, object],
    ) -> Optional[str]:
        template = self._custom_commands.get(command)
        if not template:
            return None
        hops = _packet_hops(packet)
        rx_unix = _to_int(packet.get("rxTime"))
        values = {
            "command": command,
            "args": " ".join(args),
            "from_id": from_id,
            "to_id": to_id,
            "local_id": local_node_id,
            "hops": "n/a" if hops is None else str(hops),
            "rx_time": _safe_strftime(rx_unix),
        }
        try:
            rendered = template.format(**values)
        except Exception:
            rendered = template
        text = str(rendered or "").strip()
        return text or None

    def _build_reply(
        self,
        *,
        command: str,
        args: list[str],
        from_id: str,
        to_id: str,
        local_node_id: str,
        local_aliases: set[str],
        nodes: list[dict[str, object]],
        packet: dict[str, object],
        received_ms: int,
    ) -> Optional[str]:
        standard_reply = self._build_standard_reply(
            command=command,
            args=args,
            local_node_id=local_node_id,
            local_aliases=local_aliases,
            nodes=nodes,
            packet=packet,
            received_ms=received_ms,
        )
        if standard_reply is not None:
            return standard_reply[:200]
        custom_reply = self._build_custom_reply(
            command=command,
            args=args,
            from_id=from_id,
            to_id=to_id,
            local_node_id=local_node_id,
            packet=packet,
        )
        if custom_reply is not None:
            return custom_reply[:200]
        return None

    def _prioritized_bot_apps_locked(self, from_id: str) -> list[tuple[str, BotApp]]:
        clean_from_id = _normalize_node_id(from_id)
        active: list[tuple[str, BotApp]] = []
        inactive: list[tuple[str, BotApp]] = []
        for name in self._bot_app_order:
            app = self._bot_apps_by_name.get(name)
            if app is None:
                continue
            try:
                has_session = app.has_active_session(clean_from_id)
            except Exception:
                has_session = False
            if has_session:
                active.append((name, app))
            else:
                inactive.append((name, app))
        return active + inactive

    def on_receive(self, packet: object, interface: object = None, **_kwargs: object) -> None:
        if not self._enabled and not self._log_enabled:
            return
        if not isinstance(packet, dict):
            return
        if not _is_text_message_packet(packet):
            return
        if interface is None:
            return

        decoded = packet.get("decoded")
        text = _packet_text(decoded)
        if not text:
            return

        from_id = _resolve_packet_node_id(packet.get("fromId"), packet.get("from"), interface)
        if not from_id or from_id == "^all":
            return
        packet_id = _to_int(packet.get("id"))
        if self._remember_packet_id(from_id, packet_id):
            return
        to_id = _resolve_packet_node_id(packet.get("toId"), packet.get("to"), interface) or "^all"
        local_node_id, local_aliases, nodes = self._local_node_context(interface)
        if local_node_id and _normalize_node_id(from_id).lower() == local_node_id.lower():
            return

        rx_unix = _to_int(packet.get("rxTime"))
        now_unix = int(self._now_unix_fn())
        received_unix = rx_unix if rx_unix is not None and rx_unix > 0 else now_unix
        received_ms = received_unix * 1000
        channel_index = _to_int(packet.get("channel"))
        if channel_index is None or channel_index < 0:
            channel_index = 0
        app_result = None
        with self._lock:
            for app_name, app in self._prioritized_bot_apps_locked(from_id):
                result = app.try_handle_message(
                    text=text,
                    from_id=from_id,
                    to_id=to_id,
                    local_node_id=local_node_id,
                    now_unix=now_unix,
                    enabled=bool(self._bot_app_enabled.get(app_name)),
                )
                if not getattr(result, "handled", False):
                    continue
                app_result = (app_name, result)
                break
        if app_result is not None:
            app_name, result = app_result
            command = _normalize_command_name(result.command_name or app_name) or app_name
            raw_args = result.command_args if getattr(result, "command_args", None) else None
            if raw_args is None:
                args = [part for part in str(text or "").split()[1:] if part]
            else:
                args = [str(part) for part in raw_args if str(part)]
            command_enabled = bool(self._command_enabled_locked(command))
            reply_text = getattr(result, "reply_text", None)
        else:
            parsed = self._parse_command(text)
            if parsed is None:
                return
            command, args = parsed
            if command not in STANDARD_BOT_COMMANDS and command not in self._custom_commands:
                return
            with self._lock:
                command_enabled = self._command_enabled_locked(command)
            reply_text = None
            if command_enabled:
                reply_text = self._build_reply(
                    command=command,
                    args=args,
                    from_id=from_id,
                    to_id=to_id,
                    local_node_id=local_node_id,
                    local_aliases=local_aliases,
                    nodes=nodes,
                    packet=packet,
                    received_ms=received_ms,
                )
        request_id = f"mesh-{_normalize_node_id(from_id) or 'unknown'}-{packet_id if packet_id is not None else received_unix}-{command}"
        request_entry = {
            "id": request_id,
            "source": "mesh",
            "command": text,
            "command_head": command,
            "command_args": " ".join(args),
            "command_enabled": bool(command_enabled),
            "from_id": _normalize_node_id(from_id),
            "to_id": _normalize_node_id(to_id) or "^all",
            "channel_index": channel_index,
            "message_id": packet_id,
            "reply_id": None,
            "received_unix": received_unix,
            "received_at": _safe_strftime(received_unix),
            "hops": _packet_hops(packet),
            "respond_enabled": bool(self._enabled),
            "responded": False,
            "response_message_id": None,
            "response_unix": None,
            "response_hops": None,
            "response_from": "",
            "response_to": "",
            "response_text": "",
            "response_error": "",
        }
        self._record_request(request_entry)

        if not self._enabled:
            return

        if to_id.startswith("!") and local_node_id.startswith("!") and to_id.lower() != local_node_id.lower():
            return

        if not reply_text:
            return

        reply_id = packet_id if packet_id is not None and packet_id > 0 else None
        if command in self._bot_apps_by_name:
            destination = from_id
        else:
            destination = "^all" if self._reply_broadcast or to_id == "^all" else from_id
        if destination != "^all" and not destination.startswith("!"):
            return
        try:
            response_payload = self._send_chat_fn(
                text=reply_text,
                destination=destination,
                channel_index=channel_index,
                reply_id=reply_id,
            )
            response_message_id = _to_int(
                response_payload.get("message_id") if isinstance(response_payload, dict) else None
            )
            response_unix = _to_int(
                response_payload.get("sent_at")
                if isinstance(response_payload, dict)
                else None
            )
            response_from = local_node_id or ""
            response_to = _normalize_node_id(destination) or destination
            self._update_request(
                request_id,
                responded=True,
                response_message_id=response_message_id,
                response_unix=response_unix if response_unix and response_unix > 0 else int(self._now_unix_fn()),
                response_hops=_packet_hops(packet),
                response_from=response_from,
                response_to=response_to,
                response_text=reply_text,
                response_error="",
            )
        except Exception as exc:
            self._update_request(
                request_id,
                responded=False,
                response_error=str(exc),
            )


def _load_custom_commands_from_env(env: dict[str, str]) -> dict[str, str]:
    raw = str(env.get("MESH_DASH_BOT_CUSTOM_COMMANDS") or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in parsed.items():
        name = _normalize_command_name(key)
        if not name:
            continue
        text = str(value or "").strip()
        if not text:
            continue
        out[name] = text
    return out


def _load_disabled_commands_from_env(env: dict[str, str]) -> list[str]:
    raw = str(env.get("MESH_DASH_BOT_DISABLED_COMMANDS") or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None
        if isinstance(parsed, list):
            return [
                name
                for name in (_normalize_command_name(value) for value in parsed)
                if name
            ]
    return [
        name
        for name in (_normalize_command_name(value) for value in raw.replace(";", ",").split(","))
        if name
    ]


def _default_disabled_commands() -> list[str]:
    default_enabled = {
        _normalize_command_name(name) for name in DEFAULT_ENABLED_MANAGED_BOT_COMMAND_NAMES
    }
    return [
        name
        for name in (
            _normalize_command_name(getattr(spec, "name", ""))
            for spec in MANAGED_BOT_COMMAND_SPECS
        )
        if name and name not in default_enabled
    ]


def build_mesh_response_bot_from_env(
    *,
    send_chat_fn: Callable[..., dict[str, object]],
    get_local_node_id_fn: Callable[[object], str],
    env: Optional[dict[str, str]] = None,
    now_unix_fn: Callable[[], float] = time.time,
) -> Optional[MeshResponseBot]:
    env_map = env if isinstance(env, dict) else dict(os.environ)
    respond_enabled = _parse_bool_token(env_map.get("MESH_DASH_BOT_ENABLED"), False)
    log_enabled = _parse_bool_token(env_map.get("MESH_DASH_BOT_LOG_ENABLED"), True)
    game_enabled = _parse_bool_token(env_map.get("MESH_DASH_BOT_GAME_ENABLED"), True)
    if not respond_enabled and not log_enabled:
        return None
    reply_broadcast = _parse_bool_token(env_map.get("MESH_DASH_BOT_REPLY_BROADCAST"), False)
    custom_commands = _load_custom_commands_from_env(env_map)
    if "MESH_DASH_BOT_DISABLED_COMMANDS" in env_map:
        disabled_commands = _load_disabled_commands_from_env(env_map)
    else:
        disabled_commands = _default_disabled_commands()
    return MeshResponseBot(
        send_chat_fn=send_chat_fn,
        get_local_node_id_fn=get_local_node_id_fn,
        custom_commands=custom_commands,
        disabled_commands=disabled_commands,
        enabled=respond_enabled,
        log_enabled=log_enabled,
        game_enabled=game_enabled,
        reply_broadcast=reply_broadcast,
        now_unix_fn=now_unix_fn,
    )


__all__ = [
    "MeshResponseBot",
    "STANDARD_BOT_COMMANDS",
    "build_mesh_response_bot_from_env",
]
