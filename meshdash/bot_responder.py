import json
import os
import random
import threading
import time
from typing import Callable, Optional

from . import bot_responder_nodes as _bot_nodes
from .bot_commands import (
    DEFAULT_ENABLED_MANAGED_BOT_COMMAND_NAMES,
    MANAGED_BOT_COMMAND_SPECS,
    STANDARD_BOT_COMMANDS as _STANDARD_BOT_COMMANDS,
    build_custom_bot_command_spec,
    normalize_bot_command_name,
)
from .bot_apps.base import BotApp
from .bot_apps.registry import build_builtin_bot_apps
from .bot_responder_nodes import (
    _bot_to_requester_distance_hint,
    _effective_hops,
    _find_node_for_query,
    _format_hop_count_label,
    _format_latency_label,
    _iter_known_nodes,
    _is_text_message_packet,
    _node_suffix,
    _normalize_node_id,
    _packet_hops,
    _packet_link_signal_hint,
    _packet_text,
    _resolve_packet_node_id,
)
from .bot_responder_text import (
    _chat_limit_bytes_from_error,
    _safe_strftime,
    _segment_reply_text,
    _tag_zork_start_reply,
)
from .bot_settings_store import (
    DEFAULT_BOT_SETTINGS_FILE,
    load_persisted_bot_settings,
    save_persisted_bot_settings,
)
from .config import DEFAULT_CHAT_MAX_BYTES
from .helpers import to_int as _to_int
from .offline_atlas import nearest_city as _nearest_city_for_coords

STANDARD_BOT_COMMANDS = _STANDARD_BOT_COMMANDS

_RECENT_PACKET_TTL_SECONDS = 180
_RECENT_PACKET_MAX = 1024
_BOT_COMMAND_ALIASES = {
    "test": "ping",
}
_NATURAL_PING_PREFIXES = (
    "can you see this",
)
_DEFAULT_JOKE_TRIGGERS = (
    "tell me a joke",
)
_DEFAULT_JOKE_LINES = (
    "Why did the packet bring a map? It kept getting routed in circles.",
    "I told my node to stay positive. Now it only reports good SNR.",
    "My radio joined a band. It only plays LoRa classics.",
    "I asked the mesh for directions. It said, 'Take the shortest hop path.'",
    "Why was the telemetry calm? It had stable readings under pressure.",
    "I tried to hide from the network. The node list found me anyway.",
    "What do sleepy packets do? They take a little latency nap.",
    "The antenna got promoted. It really knows how to reach people.",
    "I told a bot to chill. It replied, 'Current temperature already sampled.'",
    "Why did the signal cross the hill? Better line of sight.",
)
_DEFAULT_JOKE_DELAY_PUNCHLINE_ENABLED = False
_DEFAULT_JOKE_PUNCHLINE_DELAY_SECONDS = 15.0
_REPLY_PACKET_TEXT_RESERVE_BYTES = 20
_DEFAULT_SEGMENT_DELAY_SECONDS = 1.5
_DEFAULT_SEGMENT_RETRY_COUNT = 0
_DEFAULT_SEGMENT_ACK_WAIT_SECONDS = 2.5
_SEGMENT_ACK_POLL_SECONDS = 0.2
_PUBLIC_PING_LIMIT = 3
_PUBLIC_PING_SUPPRESS_SECONDS = 3600
_PUBLIC_PING_LIMIT_REACTION = "❌"
_PUBLIC_PING_DIRECT_HANDOFF_TEXT = (
    "ping: public limit reached (3). Continue testing with direct peer-to-peer messages for 1 hour."
)


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


def _parse_nonnegative_float_token(value: object, default: float) -> float:
    fallback = max(0.0, float(default))
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    try:
        parsed = float(text)
    except Exception:
        return fallback
    if parsed < 0:
        return fallback
    return parsed


def _parse_nonnegative_int_token(value: object, default: int) -> int:
    fallback = max(0, int(default))
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    try:
        parsed = int(text)
    except Exception:
        return fallback
    if parsed < 0:
        return fallback
    return parsed


def _normalize_delivery_state(value: object) -> str:
    text = str(value or "").strip().lower()
    if text in ("sent", "pending", "acked", "nak", "timeout", "error"):
        return text
    return ""


def _normalize_command_name(value: object) -> str:
    return normalize_bot_command_name(value)


def _canonical_command_name(value: object) -> str:
    clean = _normalize_command_name(value)
    if not clean:
        return ""
    return _BOT_COMMAND_ALIASES.get(clean, clean)


def _parse_natural_ping_command(raw: str) -> tuple[str, list[str]] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    lowered = text.lower()
    for prefix in _NATURAL_PING_PREFIXES:
        if lowered == prefix:
            return ("ping", [])
        if lowered == f"{prefix}?":
            return ("ping", [])
    return None


def _parse_natural_joke_command(raw: str, triggers: list[str]) -> tuple[str, list[str]] | None:
    normalized = _normalize_trigger_phrase(raw)
    if not normalized:
        return None
    for trigger in triggers:
        if normalized == trigger:
            return ("joke", [])
    return None


def _normalize_trigger_phrase(value: object) -> str:
    text = " ".join(str(value or "").strip().lower().split())
    if not text:
        return ""
    text = text.rstrip("?.!;,")
    return text.strip()


def _parse_phrase_items(value: object, *, split_commas: bool) -> list[str]:
    if isinstance(value, list):
        return [str(item or "").strip() for item in value]
    text = str(value or "").strip()
    if not text:
        return []
    normalized = text.replace(";", "\n")
    if split_commas:
        normalized = normalized.replace(",", "\n")
    return [item.strip() for item in normalized.splitlines()]


def _normalize_joke_triggers(value: object) -> list[str]:
    raw_items = _parse_phrase_items(value, split_commas=True)
    out: list[str] = []
    seen: set[str] = set()
    for raw_item in raw_items:
        clean = _normalize_trigger_phrase(raw_item)
        if not clean or clean in seen:
            continue
        seen.add(clean)
        out.append(clean[:160])
        if len(out) >= 64:
            break
    if out:
        return out
    return [item for item in (_normalize_trigger_phrase(v) for v in _DEFAULT_JOKE_TRIGGERS) if item]


def _normalize_joke_lines(value: object) -> list[str]:
    if value is None:
        return [str(line).strip() for line in _DEFAULT_JOKE_LINES if str(line).strip()]
    raw_items = _parse_phrase_items(value, split_commas=False)
    out: list[str] = []
    seen: set[str] = set()
    for raw_item in raw_items:
        clean = str(raw_item or "").strip()
        if not clean:
            continue
        if len(clean) > 240:
            clean = clean[:240].rstrip()
        if not clean:
            continue
        dedupe_key = clean.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        out.append(clean)
        if len(out) >= 600:
            break
    if out:
        return out
    if isinstance(value, list):
        return []
    return [str(line).strip() for line in _DEFAULT_JOKE_LINES if str(line).strip()]


def _split_joke_prompt_and_punchline(text: object) -> tuple[str, str] | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    marker = raw.find("?")
    if marker < 0:
        return None
    prompt = raw[: marker + 1].strip()
    punchline = raw[marker + 1 :].strip()
    punchline = punchline.lstrip("-:;,.! ")
    if not prompt or not punchline:
        return None
    return prompt, punchline


def _bot_city_hint(local_node: Optional[dict[str, object]]) -> str:
    # Compatibility shim: tests monkeypatch bot_responder._nearest_city_for_coords.
    previous_lookup = _bot_nodes._nearest_city_for_coords
    _bot_nodes._nearest_city_for_coords = _nearest_city_for_coords
    try:
        return _bot_nodes._bot_city_hint(local_node)
    finally:
        _bot_nodes._nearest_city_for_coords = previous_lookup


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
        game_public_start_enabled: bool = False,
        joke_triggers: Optional[list[str]] = None,
        joke_lines: Optional[list[str]] = None,
        joke_delay_punchline_enabled: bool = _DEFAULT_JOKE_DELAY_PUNCHLINE_ENABLED,
        joke_punchline_delay_seconds: float = _DEFAULT_JOKE_PUNCHLINE_DELAY_SECONDS,
        reply_broadcast: bool = False,
        settings_path: Optional[str] = None,
        chat_max_bytes: int = DEFAULT_CHAT_MAX_BYTES,
        segment_delay_seconds: float = 0.0,
        segment_retry_count: int = 0,
        segment_ack_wait_seconds: float = 0.0,
        delivery_state_lookup_fn: Optional[Callable[[int], Optional[str]]] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        now_unix_fn: Callable[[], float] = time.time,
        timer_factory: Optional[Callable[[float, Callable[[], None]], object]] = None,
    ) -> None:
        self._send_chat_fn = send_chat_fn
        self._get_local_node_id_fn = get_local_node_id_fn
        self._enabled = bool(enabled)
        self._log_enabled = bool(log_enabled)
        self._reply_broadcast = bool(reply_broadcast)
        self._settings_path = str(settings_path).strip() if settings_path else None
        self._chat_max_bytes = max(1, int(chat_max_bytes))
        self._segment_delay_seconds = _parse_nonnegative_float_token(segment_delay_seconds, 0.0)
        self._segment_retry_count = _parse_nonnegative_int_token(segment_retry_count, 0)
        self._segment_ack_wait_seconds = _parse_nonnegative_float_token(segment_ack_wait_seconds, 0.0)
        self._delivery_state_lookup_fn = delivery_state_lookup_fn
        self._sleep_fn = sleep_fn
        self._now_unix_fn = now_unix_fn
        self._game_public_start_enabled = bool(game_public_start_enabled)
        self._joke_trigger_phrases = _normalize_joke_triggers(joke_triggers)
        self._joke_lines = _normalize_joke_lines(joke_lines)
        self._joke_delay_punchline_enabled = bool(joke_delay_punchline_enabled)
        self._joke_punchline_delay_seconds = _parse_nonnegative_float_token(
            joke_punchline_delay_seconds,
            _DEFAULT_JOKE_PUNCHLINE_DELAY_SECONDS,
        )
        self._joke_cycle: list[str] = []
        self._pending_joke_punchlines: dict[str, dict[str, object]] = {}
        self._pending_joke_seq = 0
        self._rng = random.Random()
        self._timer_factory = timer_factory
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
        self._public_ping_state: dict[str, dict[str, int]] = {}
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

    @property
    def game_public_start_enabled(self) -> bool:
        return bool(self._game_public_start_enabled)

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

    def _set_joke_settings_locked(
        self,
        *,
        triggers: Optional[list[str]] = None,
        lines: Optional[list[str]] = None,
        delay_punchline_enabled: Optional[bool] = None,
    ) -> None:
        clear_pending = False
        if triggers is not None:
            self._joke_trigger_phrases = _normalize_joke_triggers(triggers)
            self._joke_cycle = []
            clear_pending = True
        if lines is not None:
            self._joke_lines = _normalize_joke_lines(lines)
            self._joke_cycle = []
            clear_pending = True
        if delay_punchline_enabled is not None:
            self._joke_delay_punchline_enabled = bool(delay_punchline_enabled)
            clear_pending = True
        if clear_pending:
            self._clear_pending_joke_punchlines_locked()

    def _next_joke_line_locked(self) -> str:
        if not self._joke_cycle:
            refreshed = list(self._joke_lines)
            self._rng.shuffle(refreshed)
            self._joke_cycle = refreshed
        if not self._joke_cycle:
            return "I tried to tell a joke, but my punchline got dropped in transit."
        return self._joke_cycle.pop()

    def _clear_pending_joke_punchlines_locked(self) -> None:
        pending_rows = list(self._pending_joke_punchlines.values())
        self._pending_joke_punchlines.clear()
        for row in pending_rows:
            timer = row.get("timer")
            if timer is not None and hasattr(timer, "cancel"):
                try:
                    timer.cancel()
                except Exception:
                    continue

    def _build_timer(self, delay_seconds: float, callback: Callable[[], None]) -> object:
        if callable(self._timer_factory):
            timer = self._timer_factory(delay_seconds, callback)
        else:
            timer = threading.Timer(delay_seconds, callback)
        try:
            setattr(timer, "daemon", True)
        except Exception:
            pass
        return timer

    def _queue_delayed_joke_punchline(
        self,
        *,
        destination: str,
        channel_index: int,
        reply_id: Optional[int],
        punchline: str,
        request_id: str,
        from_id: str,
    ) -> None:
        clean_punchline = str(punchline or "").strip()
        delay_seconds = max(0.0, float(self._joke_punchline_delay_seconds))
        if not clean_punchline or delay_seconds <= 0:
            return
        entry_id = ""
        with self._lock:
            self._pending_joke_seq += 1
            entry_id = f"joke-{int(self._now_unix_fn())}-{self._pending_joke_seq}"
            self._pending_joke_punchlines[entry_id] = {
                "id": entry_id,
                "destination": _normalize_node_id(destination) or destination,
                "from_id": _normalize_node_id(from_id) or from_id,
                "channel_index": int(channel_index),
                "reply_id": _to_int(reply_id),
                "request_id": str(request_id or ""),
                "punchline": clean_punchline,
                "timer": None,
            }
        timer = self._build_timer(
            delay_seconds,
            lambda: self._deliver_pending_joke_punchline(
                entry_id=entry_id,
                reply_id=None,
                reason="timeout",
            ),
        )
        with self._lock:
            entry = self._pending_joke_punchlines.get(entry_id)
            if not isinstance(entry, dict):
                return
            entry["timer"] = timer
        if hasattr(timer, "start"):
            try:
                timer.start()
            except Exception:
                with self._lock:
                    self._pending_joke_punchlines.pop(entry_id, None)

    def _append_request_response(
        self,
        request_id: str,
        *,
        response_text: str = "",
        response_error: str = "",
        response_message_id: Optional[int] = None,
        response_unix: Optional[int] = None,
        response_from: str = "",
        response_to: str = "",
    ) -> None:
        if not self._log_enabled or not request_id:
            return
        with self._lock:
            for row in reversed(self._request_log):
                if str(row.get("id") or "") != request_id:
                    continue
                if response_text:
                    existing_text = str(row.get("response_text") or "").strip()
                    clean_text = str(response_text).strip()
                    if clean_text:
                        row["response_text"] = (
                            f"{existing_text}\n{clean_text}" if existing_text else clean_text
                        )
                        row["responded"] = True
                if response_error:
                    existing_error = str(row.get("response_error") or "").strip()
                    clean_error = str(response_error).strip()
                    if clean_error:
                        row["response_error"] = (
                            f"{existing_error}; {clean_error}" if existing_error else clean_error
                        )
                if response_message_id is not None:
                    row["response_message_id"] = response_message_id
                if response_unix is not None:
                    row["response_unix"] = response_unix
                if response_from:
                    row["response_from"] = response_from
                if response_to:
                    row["response_to"] = response_to
                break

    def _deliver_pending_joke_punchline(
        self,
        *,
        entry_id: str,
        reply_id: Optional[int],
        reason: str,
    ) -> bool:
        if not self._enabled:
            with self._lock:
                entry = self._pending_joke_punchlines.pop(entry_id, None)
            if isinstance(entry, dict):
                timer = entry.get("timer")
                if timer is not None and hasattr(timer, "cancel"):
                    try:
                        timer.cancel()
                    except Exception:
                        pass
            return False
        with self._lock:
            entry = self._pending_joke_punchlines.pop(entry_id, None)
        if not isinstance(entry, dict):
            return False
        timer = entry.get("timer")
        if timer is not None and hasattr(timer, "cancel"):
            try:
                timer.cancel()
            except Exception:
                pass
        destination = _normalize_node_id(entry.get("destination")) or str(entry.get("destination") or "")
        channel_index = _to_int(entry.get("channel_index"))
        channel_index = channel_index if channel_index is not None and channel_index >= 0 else 0
        fallback_reply_id = _to_int(entry.get("reply_id"))
        reply_id_to_use = _to_int(reply_id)
        if reply_id_to_use is None or reply_id_to_use <= 0:
            reply_id_to_use = fallback_reply_id if fallback_reply_id and fallback_reply_id > 0 else None
        punchline = str(entry.get("punchline") or "").strip()
        request_id = str(entry.get("request_id") or "").strip()
        try:
            response_segments, response_payloads = self._send_reply_text(
                text=punchline,
                destination=destination,
                channel_index=channel_index,
                reply_id=reply_id_to_use,
            )
            response_payload = response_payloads[-1] if response_payloads else {}
            response_message_id = _to_int(
                response_payload.get("message_id") if isinstance(response_payload, dict) else None
            )
            response_unix = _to_int(
                response_payload.get("sent_at") if isinstance(response_payload, dict) else None
            )
            self._append_request_response(
                request_id,
                response_text="\n".join(response_segments),
                response_message_id=response_message_id,
                response_unix=response_unix if response_unix and response_unix > 0 else int(self._now_unix_fn()),
                response_to=destination,
            )
            return True
        except Exception as exc:
            self._append_request_response(
                request_id,
                response_error=f"delayed joke {reason}: {exc}",
            )
            return False

    def _maybe_deliver_pending_joke_from_message(
        self,
        *,
        from_id: str,
        to_id: str,
        channel_index: int,
        packet_id: Optional[int],
    ) -> bool:
        clean_from_id = _normalize_node_id(from_id)
        clean_to_id = _normalize_node_id(to_id)
        pending_id = ""
        with self._lock:
            for entry_id, entry in self._pending_joke_punchlines.items():
                if not isinstance(entry, dict):
                    continue
                pending_destination = _normalize_node_id(entry.get("destination"))
                pending_channel = _to_int(entry.get("channel_index"))
                if pending_channel is None or pending_channel < 0:
                    pending_channel = 0
                if pending_channel != channel_index:
                    continue
                if pending_destination == "^all":
                    if clean_to_id != "^all":
                        continue
                    pending_id = str(entry_id)
                    break
                if pending_destination and pending_destination == clean_from_id:
                    pending_id = str(entry_id)
                    break
        if not pending_id:
            return False
        return self._deliver_pending_joke_punchline(
            entry_id=pending_id,
            reply_id=packet_id,
            reason="reply",
        )

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
            "game_public_start_enabled": bool(self._game_public_start_enabled),
            "joke_triggers": list(self._joke_trigger_phrases),
            "joke_lines": list(self._joke_lines),
            "joke_delay_punchline_enabled": bool(self._joke_delay_punchline_enabled),
            "active_game_sessions": self._active_game_sessions_locked(),
            "disabled_commands": sorted(self._disabled_commands),
            "commands": self._managed_command_rows_locked(),
        }

    def _persistable_bot_settings_locked(self) -> dict[str, object]:
        return {
            "enabled": bool(self._enabled),
            "log_enabled": bool(self._log_enabled),
            "game_enabled": bool(self._bot_app_enabled.get("zork")),
            "game_public_start_enabled": bool(self._game_public_start_enabled),
            "joke_triggers": list(self._joke_trigger_phrases),
            "joke_lines": list(self._joke_lines),
            "joke_delay_punchline_enabled": bool(self._joke_delay_punchline_enabled),
            "disabled_commands": sorted(self._disabled_commands),
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
        game_public_start_enabled: Optional[bool] = None,
        command_settings: Optional[dict[str, bool]] = None,
        joke_triggers: Optional[list[str]] = None,
        joke_lines: Optional[list[str]] = None,
        joke_delay_punchline_enabled: Optional[bool] = None,
    ) -> dict[str, object]:
        with self._lock:
            if enabled is not None:
                self._enabled = bool(enabled)
            if log_enabled is not None:
                self._log_enabled = bool(log_enabled)
            if game_enabled is not None:
                self._set_bot_app_enabled_locked("zork", bool(game_enabled))
            if game_public_start_enabled is not None:
                self._game_public_start_enabled = bool(game_public_start_enabled)
            if command_settings:
                self._apply_command_settings_locked(command_settings)
            if (
                joke_triggers is not None
                or joke_lines is not None
                or joke_delay_punchline_enabled is not None
            ):
                self._set_joke_settings_locked(
                    triggers=joke_triggers,
                    lines=joke_lines,
                    delay_punchline_enabled=joke_delay_punchline_enabled,
                )
            out = self._bot_settings_locked()
            persist_payload = self._persistable_bot_settings_locked()
        persist_error = save_persisted_bot_settings(self._settings_path, persist_payload)
        out["ok"] = True
        if persist_error:
            out["persist_error"] = persist_error
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
        natural_ping = _parse_natural_ping_command(raw)
        if natural_ping is not None:
            return natural_ping
        with self._lock:
            joke_triggers = list(self._joke_trigger_phrases)
        natural_joke = _parse_natural_joke_command(raw, joke_triggers)
        if natural_joke is not None:
            return natural_joke
        parts = [part for part in raw.split() if part]
        if not parts:
            return None
        head = _canonical_command_name(parts[0])
        if not head:
            return None
        return head, parts[1:]

    def _should_bootstrap_public_game_start(
        self,
        *,
        app_name: str,
        text: str,
        to_id: str,
        local_node_id: str,
    ) -> bool:
        if app_name != "zork" or not self._game_public_start_enabled:
            return False
        if _normalize_node_id(to_id) != "^all":
            return False
        if not _normalize_node_id(local_node_id).startswith("!"):
            return False
        # Avoid re-entering _parse_command while the main receive lock is held.
        raw = str(text or "").strip()
        if not raw:
            return False
        parts = [part for part in raw.split() if part]
        if not parts:
            return False
        command = _canonical_command_name(parts[0])
        return command == "zork"

    def _build_standard_reply(
        self,
        *,
        command: str,
        args: list[str],
        from_id: str,
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

        if command == "joke":
            with self._lock:
                return self._next_joke_line_locked()

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
            hops = _effective_hops(packet, from_id, nodes)
            hop_text = _format_hop_count_label(hops)
            requester = _find_node_for_query(from_id, nodes)
            local_node = _find_node_for_query(local_node_id, nodes) if local_node_id else None
            link_hint = _packet_link_signal_hint(packet)
            bot_city_hint = _bot_city_hint(local_node)
            distance_hint = _bot_to_requester_distance_hint(
                packet=packet,
                requester_node=requester,
                local_node=local_node,
                now_unix=now_unix,
            )
            details: list[str] = []
            if link_hint:
                details.append(link_hint)
            if bot_city_hint and distance_hint:
                details.append(f"bot near {bot_city_hint}, about {distance_hint} from you")
            elif bot_city_hint:
                details.append(f"bot near {bot_city_hint}")
            elif distance_hint:
                details.append(f"about {distance_hint} from you")
            if not details:
                return f"{latency_text} round trip, {hop_text}."
            return f"{latency_text} round trip, {hop_text}, {', '.join(details)}."

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
            from_id=from_id,
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

    def _send_reply_text(
        self,
        *,
        text: str,
        destination: str,
        channel_index: int,
        reply_id: Optional[int],
    ) -> tuple[list[str], list[dict[str, object]]]:
        clean_text = str(text or "").strip()
        if not clean_text:
            return ([], [])
        effective_limit = self._chat_max_bytes
        if reply_id is not None and reply_id > 0:
            effective_limit = max(1, effective_limit - _REPLY_PACKET_TEXT_RESERVE_BYTES)
        proactive_segments = _segment_reply_text(clean_text, effective_limit)
        if proactive_segments != [clean_text]:
            payloads: list[dict[str, object]] = []
            for index, segment in enumerate(proactive_segments):
                if index > 0 and self._segment_delay_seconds > 0:
                    self._sleep_fn(self._segment_delay_seconds)
                payload = self._send_segment_with_retry(
                    text=segment,
                    destination=destination,
                    channel_index=channel_index,
                    reply_id=reply_id if index == 0 else None,
                )
                payloads.append(payload)
            return (proactive_segments, payloads)
        try:
            payload = self._send_segment_with_retry(
                text=clean_text,
                destination=destination,
                channel_index=channel_index,
                reply_id=reply_id,
            )
            return ([clean_text], [payload])
        except Exception as exc:
            limit = _chat_limit_bytes_from_error(exc)
            if limit is None:
                raise
        segments = _segment_reply_text(clean_text, limit)
        if not segments:
            raise ValueError("Reply could not be segmented into non-empty messages")
        payloads: list[dict[str, object]] = []
        for index, segment in enumerate(segments):
            if index > 0 and self._segment_delay_seconds > 0:
                self._sleep_fn(self._segment_delay_seconds)
            payload = self._send_segment_with_retry(
                text=segment,
                destination=destination,
                channel_index=channel_index,
                reply_id=reply_id if index == 0 else None,
            )
            payloads.append(payload)
        return (segments, payloads)

    def _lookup_delivery_state(self, message_id: int) -> str:
        if message_id <= 0 or self._delivery_state_lookup_fn is None:
            return ""
        try:
            return _normalize_delivery_state(self._delivery_state_lookup_fn(message_id))
        except Exception:
            return ""

    def _wait_for_delivery_state(self, message_id: int) -> str:
        state = self._lookup_delivery_state(message_id)
        if state in ("acked", "sent", "nak", "timeout", "error"):
            return state
        timeout_seconds = max(0.0, float(self._segment_ack_wait_seconds))
        if timeout_seconds <= 0:
            return state
        remaining = timeout_seconds
        while remaining > 0:
            sleep_for = min(_SEGMENT_ACK_POLL_SECONDS, remaining)
            self._sleep_fn(sleep_for)
            remaining = max(0.0, remaining - sleep_for)
            current = self._lookup_delivery_state(message_id)
            if current:
                state = current
            if current in ("acked", "sent", "nak", "timeout", "error"):
                return current
        return state

    def _send_segment_with_retry(
        self,
        *,
        text: str,
        destination: str,
        channel_index: int,
        reply_id: Optional[int],
    ) -> dict[str, object]:
        should_track_delivery = bool(
            destination.startswith("!")
            and self._delivery_state_lookup_fn is not None
        )
        max_attempts = 1 + (self._segment_retry_count if should_track_delivery else 0)
        previous_message_id: Optional[int] = None
        payload: dict[str, object] = {}
        for attempt in range(max_attempts):
            send_kwargs: dict[str, object] = {
                "text": text,
                "destination": destination,
                "channel_index": channel_index,
                "reply_id": reply_id,
            }
            if attempt > 0 and previous_message_id is not None and previous_message_id > 0:
                send_kwargs["retry_of"] = previous_message_id
            payload_raw = self._send_chat_fn(**send_kwargs)
            payload = payload_raw if isinstance(payload_raw, dict) else {}
            if not should_track_delivery:
                return payload
            message_id = _to_int(payload.get("message_id"))
            if message_id is None or message_id <= 0:
                return payload
            previous_message_id = message_id
            state = self._wait_for_delivery_state(message_id)
            if state in ("acked", "sent"):
                return payload
            if attempt + 1 >= max_attempts:
                return payload
            if self._segment_delay_seconds > 0:
                self._sleep_fn(self._segment_delay_seconds)
        return payload

    def _public_ping_state_locked(self, from_id: str) -> dict[str, int]:
        key = _normalize_node_id(from_id) or "unknown"
        state = self._public_ping_state.get(key)
        if not isinstance(state, dict):
            state = {"public_count": 0, "suppress_until": 0}
            self._public_ping_state[key] = state
        return state

    def _public_ping_action(self, *, from_id: str, now_unix: int) -> str:
        with self._lock:
            state = self._public_ping_state_locked(from_id)
            suppress_until = int(state.get("suppress_until") or 0)
            if suppress_until > now_unix:
                return "suppress"
            if suppress_until and now_unix >= suppress_until:
                state["public_count"] = 0
                state["suppress_until"] = 0
            public_count = int(state.get("public_count") or 0)
            if public_count >= _PUBLIC_PING_LIMIT:
                state["public_count"] = 0
                state["suppress_until"] = now_unix + _PUBLIC_PING_SUPPRESS_SECONDS
                return "handoff"
        return "allow"

    def _mark_public_ping_reply_sent(self, *, from_id: str, now_unix: int) -> None:
        with self._lock:
            state = self._public_ping_state_locked(from_id)
            suppress_until = int(state.get("suppress_until") or 0)
            if suppress_until > now_unix:
                return
            if suppress_until and now_unix >= suppress_until:
                state["public_count"] = 0
                state["suppress_until"] = 0
            public_count = max(0, int(state.get("public_count") or 0))
            state["public_count"] = min(_PUBLIC_PING_LIMIT, public_count + 1)

    def _handle_public_ping_handoff(
        self,
        *,
        from_id: str,
        local_node_id: str,
        channel_index: int,
        reply_id: Optional[int],
        request_id: str,
    ) -> None:
        response_text_parts: list[str] = []
        response_error_parts: list[str] = []
        response_payload: dict[str, object] = {}

        direct_attempts: list[tuple[int, Optional[int], str]] = [
            # Primary path: match zork/game direct style.
            (channel_index, reply_id, "zork-style"),
            # Fallback 1: keep channel, drop thread metadata.
            (channel_index, None, "no-reply-id"),
            # Fallback 2: primary channel, plain direct.
            (0, None, "ch0-no-reply-id"),
        ]
        for attempt_channel, attempt_reply_id, attempt_label in direct_attempts:
            try:
                response_segments, response_payloads = self._send_reply_text(
                    text=_PUBLIC_PING_DIRECT_HANDOFF_TEXT,
                    destination=from_id,
                    channel_index=attempt_channel,
                    reply_id=attempt_reply_id,
                )
                if response_payloads:
                    response_payload = response_payloads[-1]
                if response_segments:
                    response_text_parts.append("\n".join(response_segments))
                break
            except Exception as exc:
                response_error_parts.append(f"direct[{attempt_label}]: {exc}")
                continue

        if reply_id is not None and reply_id > 0:
            try:
                reaction_payload_raw = self._send_chat_fn(
                    text="",
                    destination="^all",
                    channel_index=channel_index,
                    reply_id=reply_id,
                    emoji=_PUBLIC_PING_LIMIT_REACTION,
                )
                reaction_payload = reaction_payload_raw if isinstance(reaction_payload_raw, dict) else {}
                if not response_payload:
                    response_payload = reaction_payload
                response_text_parts.append(f"[reaction] {_PUBLIC_PING_LIMIT_REACTION}")
            except Exception as exc:
                response_error_parts.append(f"reaction: {exc}")

        response_message_id = _to_int(
            response_payload.get("message_id") if isinstance(response_payload, dict) else None
        )
        response_unix = _to_int(
            response_payload.get("sent_at") if isinstance(response_payload, dict) else None
        )
        self._update_request(
            request_id,
            responded=bool(response_text_parts),
            response_message_id=response_message_id,
            response_unix=response_unix if response_unix and response_unix > 0 else int(self._now_unix_fn()),
            response_hops=None,
            response_from=local_node_id or "",
            response_to=_normalize_node_id(from_id) or from_id,
            response_text="\n".join(response_text_parts),
            response_error="; ".join(response_error_parts),
        )

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
        self._maybe_deliver_pending_joke_from_message(
            from_id=from_id,
            to_id=to_id,
            channel_index=channel_index,
            packet_id=packet_id,
        )
        app_result = None
        with self._lock:
            for app_name, app in self._prioritized_bot_apps_locked(from_id):
                effective_to_id = to_id
                bootstrapped_public_start = self._should_bootstrap_public_game_start(
                    app_name=app_name,
                    text=text,
                    to_id=to_id,
                    local_node_id=local_node_id,
                )
                if bootstrapped_public_start:
                    effective_to_id = local_node_id
                result = app.try_handle_message(
                    text=text,
                    from_id=from_id,
                    to_id=effective_to_id,
                    local_node_id=local_node_id,
                    now_unix=now_unix,
                    enabled=bool(self._bot_app_enabled.get(app_name)),
                )
                if not getattr(result, "handled", False):
                    continue
                app_result = (app_name, result, bootstrapped_public_start)
                break
        if app_result is not None:
            app_name, result, _bootstrapped_public_start = app_result
            command = _normalize_command_name(result.command_name or app_name) or app_name
            raw_args = result.command_args if getattr(result, "command_args", None) else None
            if raw_args is None:
                args = [part for part in str(text or "").split()[1:] if part]
            else:
                args = [str(part) for part in raw_args if str(part)]
            command_enabled = bool(self._command_enabled_locked(command))
            reply_text = _tag_zork_start_reply(
                getattr(result, "reply_text", None),
                app_name=app_name,
            )
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
            "hops": _effective_hops(packet, from_id, nodes),
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
        delayed_joke_punchline = ""
        if command == "joke":
            with self._lock:
                delay_punchline_enabled = bool(self._joke_delay_punchline_enabled)
            if delay_punchline_enabled:
                split_joke = _split_joke_prompt_and_punchline(reply_text)
                if split_joke is not None:
                    reply_text, delayed_joke_punchline = split_joke
        is_public_ping = bool(command == "ping" and destination == "^all")
        if is_public_ping:
            ping_action = self._public_ping_action(from_id=from_id, now_unix=int(self._now_unix_fn()))
            if ping_action == "suppress":
                self._update_request(
                    request_id,
                    responded=False,
                    response_error="public ping suppressed (1h cooldown active)",
                )
                return
            if ping_action == "handoff":
                self._handle_public_ping_handoff(
                    from_id=from_id,
                    local_node_id=local_node_id,
                    channel_index=channel_index,
                    reply_id=reply_id,
                    request_id=request_id,
                )
                return
        if destination != "^all" and not destination.startswith("!"):
            return
        try:
            response_segments, response_payloads = self._send_reply_text(
                text=reply_text,
                destination=destination,
                channel_index=channel_index,
                reply_id=reply_id,
            )
            response_payload = response_payloads[-1] if response_payloads else {}
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
            if is_public_ping:
                self._mark_public_ping_reply_sent(from_id=from_id, now_unix=int(self._now_unix_fn()))
            if delayed_joke_punchline:
                self._queue_delayed_joke_punchline(
                    destination=destination,
                    channel_index=channel_index,
                    reply_id=reply_id,
                    punchline=delayed_joke_punchline,
                    request_id=request_id,
                    from_id=from_id,
                )
            self._update_request(
                request_id,
                responded=True,
                response_message_id=response_message_id,
                response_unix=response_unix if response_unix and response_unix > 0 else int(self._now_unix_fn()),
                response_hops=_effective_hops(packet, from_id, nodes),
                response_from=response_from,
                response_to=response_to,
                response_text="\n".join(response_segments),
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


def _resolve_bot_settings_path(env: Optional[dict[str, str]]) -> Optional[str]:
    if isinstance(env, dict):
        if "MESH_DASH_BOT_SETTINGS_FILE" in env:
            clean = str(env.get("MESH_DASH_BOT_SETTINGS_FILE") or "").strip()
            return clean or None
        return None
    raw = str(os.environ.get("MESH_DASH_BOT_SETTINGS_FILE") or "").strip()
    return raw or DEFAULT_BOT_SETTINGS_FILE


def build_mesh_response_bot_from_env(
    *,
    send_chat_fn: Callable[..., dict[str, object]],
    get_local_node_id_fn: Callable[[object], str],
    env: Optional[dict[str, str]] = None,
    chat_max_bytes: int = DEFAULT_CHAT_MAX_BYTES,
    delivery_state_lookup_fn: Optional[Callable[[int], Optional[str]]] = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    now_unix_fn: Callable[[], float] = time.time,
) -> Optional[MeshResponseBot]:
    env_map = env if isinstance(env, dict) else dict(os.environ)
    settings_path = _resolve_bot_settings_path(env)
    persisted = load_persisted_bot_settings(settings_path)
    respond_enabled = (
        _parse_bool_token(env_map.get("MESH_DASH_BOT_ENABLED"), False)
        if "MESH_DASH_BOT_ENABLED" in env_map
        else bool(persisted.get("enabled", False))
    )
    log_enabled = (
        _parse_bool_token(env_map.get("MESH_DASH_BOT_LOG_ENABLED"), True)
        if "MESH_DASH_BOT_LOG_ENABLED" in env_map
        else bool(persisted.get("log_enabled", True))
    )
    game_enabled = (
        _parse_bool_token(env_map.get("MESH_DASH_BOT_GAME_ENABLED"), True)
        if "MESH_DASH_BOT_GAME_ENABLED" in env_map
        else bool(persisted.get("game_enabled", True))
    )
    game_public_start_enabled = (
        _parse_bool_token(env_map.get("MESH_DASH_BOT_GAME_PUBLIC_START_ENABLED"), False)
        if "MESH_DASH_BOT_GAME_PUBLIC_START_ENABLED" in env_map
        else bool(persisted.get("game_public_start_enabled", False))
    )
    joke_delay_punchline_enabled = (
        _parse_bool_token(
            env_map.get("MESH_DASH_BOT_JOKE_DELAY_PUNCHLINE"),
            _DEFAULT_JOKE_DELAY_PUNCHLINE_ENABLED,
        )
        if "MESH_DASH_BOT_JOKE_DELAY_PUNCHLINE" in env_map
        else bool(
            persisted.get(
                "joke_delay_punchline_enabled",
                _DEFAULT_JOKE_DELAY_PUNCHLINE_ENABLED,
            )
        )
    )
    if not respond_enabled and not log_enabled:
        return None
    reply_broadcast = _parse_bool_token(env_map.get("MESH_DASH_BOT_REPLY_BROADCAST"), False)
    segment_delay_ms = _parse_nonnegative_float_token(
        env_map.get("MESH_DASH_BOT_SEGMENT_DELAY_MS"),
        _DEFAULT_SEGMENT_DELAY_SECONDS * 1000.0,
    )
    segment_retries = _parse_nonnegative_int_token(
        env_map.get("MESH_DASH_BOT_SEGMENT_RETRIES"),
        _DEFAULT_SEGMENT_RETRY_COUNT,
    )
    segment_ack_wait_ms = _parse_nonnegative_float_token(
        env_map.get("MESH_DASH_BOT_SEGMENT_ACK_WAIT_MS"),
        _DEFAULT_SEGMENT_ACK_WAIT_SECONDS * 1000.0,
    )
    custom_commands = _load_custom_commands_from_env(env_map)
    joke_triggers = _normalize_joke_triggers(persisted.get("joke_triggers"))
    if "MESH_DASH_BOT_JOKE_TRIGGERS" in env_map:
        joke_triggers = _normalize_joke_triggers(env_map.get("MESH_DASH_BOT_JOKE_TRIGGERS"))
    joke_lines = _normalize_joke_lines(persisted.get("joke_lines"))
    if "MESH_DASH_BOT_JOKE_LINES" in env_map:
        joke_lines = _normalize_joke_lines(env_map.get("MESH_DASH_BOT_JOKE_LINES"))
    if "MESH_DASH_BOT_DISABLED_COMMANDS" in env_map:
        disabled_commands = _load_disabled_commands_from_env(env_map)
    elif isinstance(persisted.get("disabled_commands"), list):
        disabled_commands = [
            name
            for name in (_normalize_command_name(value) for value in persisted.get("disabled_commands", []))
            if name
        ]
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
        game_public_start_enabled=game_public_start_enabled,
        joke_triggers=joke_triggers,
        joke_lines=joke_lines,
        joke_delay_punchline_enabled=joke_delay_punchline_enabled,
        reply_broadcast=reply_broadcast,
        settings_path=settings_path,
        chat_max_bytes=chat_max_bytes,
        segment_delay_seconds=segment_delay_ms / 1000.0,
        segment_retry_count=segment_retries,
        segment_ack_wait_seconds=segment_ack_wait_ms / 1000.0,
        delivery_state_lookup_fn=delivery_state_lookup_fn,
        sleep_fn=sleep_fn,
        now_unix_fn=now_unix_fn,
    )


__all__ = [
    "MeshResponseBot",
    "STANDARD_BOT_COMMANDS",
    "build_mesh_response_bot_from_env",
]
