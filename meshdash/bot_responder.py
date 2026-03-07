import json
import os
import time
from typing import Callable, Optional

from .helpers import to_int as _to_int

STANDARD_BOT_COMMANDS = (
    "cmd",
    "help",
    "whoami",
    "whois",
    "whohas",
    "ping",
    "lheard",
)

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
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if text.startswith("!") or text.startswith("#"):
        text = text[1:]
    if not text:
        return ""
    out = []
    for ch in text:
        if ("a" <= ch <= "z") or ("0" <= ch <= "9") or ch in ("_", "-"):
            out.append(ch)
    return "".join(out)


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
        enabled: bool = True,
        reply_broadcast: bool = False,
        now_unix_fn: Callable[[], float] = time.time,
    ) -> None:
        self._send_chat_fn = send_chat_fn
        self._get_local_node_id_fn = get_local_node_id_fn
        self._enabled = bool(enabled)
        self._reply_broadcast = bool(reply_broadcast)
        self._now_unix_fn = now_unix_fn
        self._custom_commands = {
            _normalize_command_name(name): str(template or "").strip()
            for name, template in (custom_commands or {}).items()
            if _normalize_command_name(name) and str(template or "").strip()
        }
        self._recent_packet_ids: dict[int, int] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _remember_packet_id(self, packet_id: Optional[int]) -> bool:
        if packet_id is None or packet_id <= 0:
            return False
        now_unix = int(self._now_unix_fn())
        seen_at = self._recent_packet_ids.get(packet_id)
        if seen_at is not None and (now_unix - seen_at) <= _RECENT_PACKET_TTL_SECONDS:
            return True
        self._recent_packet_ids[packet_id] = now_unix
        if len(self._recent_packet_ids) > _RECENT_PACKET_MAX:
            oldest = sorted(self._recent_packet_ids.items(), key=lambda item: item[1])[
                : max(1, len(self._recent_packet_ids) - _RECENT_PACKET_MAX)
            ]
            for stale_packet_id, _stale_ts in oldest:
                self._recent_packet_ids.pop(stale_packet_id, None)
        stale_before = now_unix - _RECENT_PACKET_TTL_SECONDS
        for stale_packet_id, seen_unix in list(self._recent_packet_ids.items()):
            if seen_unix < stale_before:
                self._recent_packet_ids.pop(stale_packet_id, None)
        return False

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
            custom_names = sorted(name for name in self._custom_commands.keys() if name)
            custom_tail = f" | custom: {', '.join(custom_names)}" if custom_names else ""
            return f"cmds: help whoami whois <id> whohas <name> ping [target] lheard{custom_tail}"

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
            hops = _packet_hops(packet)
            hops_text = f"{hops}" if hops is not None else "n/a"
            rx_unix = _to_int(packet.get("rxTime"))
            tx_unix = int(tx_ms / 1000)
            rx_text = _safe_strftime(rx_unix if rx_unix is not None else tx_unix)
            tx_text = _safe_strftime(tx_unix)
            return f"pong {latency_ms}ms hops={hops_text} rx={rx_text} tx={tx_text}"

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

    def on_receive(self, packet: object, interface: object = None, **_kwargs: object) -> None:
        if not self._enabled:
            return
        if not isinstance(packet, dict):
            return
        if not _is_text_message_packet(packet):
            return
        if interface is None:
            return

        packet_id = _to_int(packet.get("id"))
        if self._remember_packet_id(packet_id):
            return

        decoded = packet.get("decoded")
        text = _packet_text(decoded)
        if not text:
            return

        parsed = self._parse_command(text)
        if parsed is None:
            return
        command, args = parsed
        if command not in STANDARD_BOT_COMMANDS and command not in self._custom_commands:
            return

        from_id = _resolve_packet_node_id(packet.get("fromId"), packet.get("from"), interface)
        if not from_id or from_id == "^all":
            return
        to_id = _resolve_packet_node_id(packet.get("toId"), packet.get("to"), interface) or "^all"
        local_node_id, local_aliases, nodes = self._local_node_context(interface)
        if local_node_id and from_id.lower() == local_node_id.lower():
            return
        if to_id.startswith("!") and local_node_id.startswith("!") and to_id.lower() != local_node_id.lower():
            return

        received_ms = int(self._now_unix_fn() * 1000)
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
        if not reply_text:
            return

        channel_index = _to_int(packet.get("channel"))
        if channel_index is None or channel_index < 0:
            channel_index = 0
        reply_id = packet_id if packet_id is not None and packet_id > 0 else None
        destination = "^all" if self._reply_broadcast or to_id == "^all" else from_id
        if destination != "^all" and not destination.startswith("!"):
            return
        self._send_chat_fn(
            text=reply_text,
            destination=destination,
            channel_index=channel_index,
            reply_id=reply_id,
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


def build_mesh_response_bot_from_env(
    *,
    send_chat_fn: Callable[..., dict[str, object]],
    get_local_node_id_fn: Callable[[object], str],
    env: Optional[dict[str, str]] = None,
    now_unix_fn: Callable[[], float] = time.time,
) -> Optional[MeshResponseBot]:
    env_map = env if isinstance(env, dict) else dict(os.environ)
    enabled = _parse_bool_token(env_map.get("MESH_DASH_BOT_ENABLED"), True)
    if not enabled:
        return None
    reply_broadcast = _parse_bool_token(env_map.get("MESH_DASH_BOT_REPLY_BROADCAST"), False)
    custom_commands = _load_custom_commands_from_env(env_map)
    return MeshResponseBot(
        send_chat_fn=send_chat_fn,
        get_local_node_id_fn=get_local_node_id_fn,
        custom_commands=custom_commands,
        enabled=True,
        reply_broadcast=reply_broadcast,
        now_unix_fn=now_unix_fn,
    )


__all__ = [
    "MeshResponseBot",
    "STANDARD_BOT_COMMANDS",
    "build_mesh_response_bot_from_env",
]
