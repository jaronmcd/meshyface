import threading
import time
from collections.abc import Mapping
from typing import Optional

from .helpers import (
    to_int as _to_int,
)
from .history_store_runtime import HistoryStore
from .meshyface_profile import (
    MESHYFACE_PROFILE_CACHE_LIMIT,
    normalize_meshyface_profile_ghost as _normalize_meshyface_profile_ghost,
    normalize_meshyface_profile_node_id as _normalize_meshyface_profile_node_id,
    normalize_meshyface_theme_recipe as _normalize_meshyface_theme_recipe,
    parse_meshyface_profile_packet as _parse_meshyface_profile_packet,
)
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
    load_tracker_node_position_counts_for_tracker as _load_tracker_node_position_counts_for_tracker_helper,
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


def _normalize_meshyface_profile_cache_entry(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    node_id = _normalize_meshyface_profile_node_id(value.get("node_id"))
    updated_unix = _to_int(value.get("updated_unix"))
    received_unix = _to_int(value.get("received_unix"))
    theme = _normalize_meshyface_theme_recipe(value.get("theme"))
    if not node_id or theme is None or updated_unix is None or updated_unix <= 0:
        return None
    ghost = _normalize_meshyface_profile_ghost(value.get("ghost"))
    profile = {
        "node_id": node_id,
        "updated_unix": int(updated_unix),
        "received_unix": max(0, int(received_unix or 0)),
        "source": "mesh",
        "theme": theme,
    }
    if ghost:
        profile["ghost"] = ghost
    return profile


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
        self.meshyface_profile_processing_enabled = False
        self.meshyface_profiles_by_node_id: dict[str, dict[str, object]] = {}
        self._restore_meshyface_profiles_from_history_unlocked()
        self._zork_bot_service = None
        self._ping_bot_service = None
        self._ping_public_start_enabled = True

    def _bump_state_revision_unlocked(self) -> None:
        self.state_revision = int(getattr(self, "state_revision", 0) or 0) + 1

    def enable_zork_bot(
        self,
        *,
        send_lock: object | None = None,
        reply_segment_delay_seconds: float | None = None,
        reply_ack_wait_seconds: float | None = None,
        reply_ack_poll_seconds: float | None = None,
        reply_retry_limit: int | None = None,
        reply_async: bool | None = None,
        sleep_fn: object | None = None,
    ) -> bool:
        try:
            from .services_zork_bot import build_zork_bot_service
        except Exception:
            return False
        kwargs = {"send_lock": send_lock, "get_delivery_state_fn": self.get_delivery_state}
        if reply_segment_delay_seconds is not None:
            kwargs["reply_segment_delay_seconds"] = reply_segment_delay_seconds
        if reply_ack_wait_seconds is not None:
            kwargs["reply_ack_wait_seconds"] = reply_ack_wait_seconds
        if reply_ack_poll_seconds is not None:
            kwargs["reply_ack_poll_seconds"] = reply_ack_poll_seconds
        if reply_retry_limit is not None:
            kwargs["reply_retry_limit"] = reply_retry_limit
        if reply_async is not None:
            kwargs["reply_async"] = reply_async
        if callable(sleep_fn):
            kwargs["sleep_fn"] = sleep_fn
        zork_service = build_zork_bot_service(**kwargs)
        with self._lock:
            self._zork_bot_service = zork_service
            self._bump_state_revision_unlocked()
        return True

    def disable_zork_bot(self) -> bool:
        with self._lock:
            if self._zork_bot_service is None:
                return True
            self._zork_bot_service = None
            self._bump_state_revision_unlocked()
        return True

    def enable_ping_bot(
        self,
        *,
        send_lock: object | None = None,
    ) -> bool:
        try:
            from .services_ping_bot import build_ping_bot_service
        except Exception:
            return False
        with self._lock:
            public_start_enabled = bool(self._ping_public_start_enabled)
        ping_service = build_ping_bot_service(
            send_lock=send_lock,
            public_start_enabled=public_start_enabled,
            get_delivery_state_fn=self.get_delivery_state,
        )
        with self._lock:
            self._ping_bot_service = ping_service
            self._bump_state_revision_unlocked()
        return True

    def disable_ping_bot(self) -> bool:
        with self._lock:
            if self._ping_bot_service is None:
                return True
            self._ping_bot_service = None
            self._bump_state_revision_unlocked()
        return True

    def set_zork_bot_enabled(
        self,
        enabled: object,
        *,
        send_lock: object | None = None,
    ) -> dict[str, object]:
        if bool(enabled):
            with self._lock:
                already_enabled = self._zork_bot_service is not None
            zork_ok = True if already_enabled else self.enable_zork_bot(send_lock=send_lock)
            ok = bool(zork_ok)
        else:
            zork_ok = self.disable_zork_bot()
            ok = bool(zork_ok)
        runtime = self.get_zork_bot_runtime()
        runtime["ok"] = bool(ok)
        return runtime

    def set_ping_bot_enabled(
        self,
        enabled: object,
        *,
        send_lock: object | None = None,
    ) -> dict[str, object]:
        if bool(enabled):
            with self._lock:
                already_enabled = self._ping_bot_service is not None
            ping_ok = True if already_enabled else self.enable_ping_bot(send_lock=send_lock)
            ok = bool(ping_ok)
        else:
            ping_ok = self.disable_ping_bot()
            ok = bool(ping_ok)
        runtime = self.get_zork_bot_runtime()
        runtime["ok"] = bool(ok)
        return runtime

    def set_ping_bot_message_only(self, message_only: object) -> dict[str, object]:
        # "message only" means direct peer-to-peer chats only (no public ^all replies).
        public_start_enabled = not bool(message_only)
        changed = False
        with self._lock:
            if self._ping_public_start_enabled != public_start_enabled:
                self._ping_public_start_enabled = public_start_enabled
                changed = True
            service = self._ping_bot_service
        if service is not None:
            set_public_start_enabled = getattr(service, "set_public_start_enabled", None)
            if callable(set_public_start_enabled):
                try:
                    changed = bool(set_public_start_enabled(public_start_enabled)) or changed
                except Exception:
                    pass
        if changed:
            with self._lock:
                self._bump_state_revision_unlocked()
        runtime = self.get_zork_bot_runtime()
        runtime["ok"] = True
        runtime["changed"] = changed
        return runtime

    def get_zork_bot_runtime(self) -> dict[str, object]:
        with self._lock:
            zork_service = self._zork_bot_service
            ping_service = self._ping_bot_service
        active_session_count = 0
        sessions: list[dict[str, object]] = []
        if zork_service is not None:
            active_session_count_fn = getattr(zork_service, "active_session_count", None)
            if callable(active_session_count_fn):
                try:
                    active_session_count = max(0, int(active_session_count_fn()))
                except Exception:
                    active_session_count = 0
            session_summaries_fn = getattr(zork_service, "session_summaries", None)
            if callable(session_summaries_fn):
                try:
                    session_summaries = session_summaries_fn()
                    if isinstance(session_summaries, list):
                        sessions = [
                            dict(row)
                            for row in session_summaries
                            if isinstance(row, dict)
                        ]
                except Exception:
                    sessions = []
        zork_enabled = zork_service is not None
        ping_enabled = ping_service is not None
        ping_public_start_enabled = bool(self._ping_public_start_enabled)
        if ping_service is not None:
            public_start_enabled_fn = getattr(ping_service, "public_start_enabled", None)
            if callable(public_start_enabled_fn):
                try:
                    ping_public_start_enabled = bool(public_start_enabled_fn())
                except Exception:
                    pass
        return {
            "available": True,
            "zork": {
                "enabled": zork_enabled,
                "active_session_count": active_session_count,
                "sessions": sessions,
                "public_start_enabled": zork_enabled,
                "direct_message_enabled": zork_enabled,
            },
            "ping": {
                "enabled": ping_enabled,
                "active_session_count": 0,
                "sessions": [],
                "public_start_enabled": ping_public_start_enabled,
                "direct_message_enabled": ping_enabled,
                "message_only": not ping_public_start_enabled,
            },
        }

    def manage_zork_bot(self, action: object, *, peer_id: object = None) -> dict[str, object]:
        clean_action = str(action or "").strip().lower().replace("-", "_")
        with self._lock:
            service = self._zork_bot_service
        if service is None:
            runtime = self.get_zork_bot_runtime()
            runtime.update({"ok": False, "error": "Zork bot is disabled"})
            return runtime

        changed = False
        if clean_action == "end_session":
            end_session_fn = getattr(service, "end_session", None)
            if not callable(end_session_fn):
                runtime = self.get_zork_bot_runtime()
                runtime.update({"ok": False, "error": "Zork session management is unavailable"})
                return runtime
            changed = bool(end_session_fn(peer_id))
        elif clean_action == "clear_sessions":
            clear_sessions_fn = getattr(service, "clear_sessions", None)
            if not callable(clear_sessions_fn):
                runtime = self.get_zork_bot_runtime()
                runtime.update({"ok": False, "error": "Zork session management is unavailable"})
                return runtime
            changed = bool(clear_sessions_fn())
        else:
            raise ValueError("Unsupported Zork bot action")

        if changed:
            with self._lock:
                self._bump_state_revision_unlocked()
        runtime = self.get_zork_bot_runtime()
        runtime.update({"ok": True, "changed": changed})
        return runtime

    def get_delivery_state(self, message_id: object) -> Optional[dict[str, object]]:
        clean_message_id = _to_int(message_id)
        if clean_message_id is None or clean_message_id <= 0:
            return None
        with self._lock:
            for entry in reversed(self.recent_chat):
                if not isinstance(entry, dict):
                    continue
                if entry.get("local_echo") is not True:
                    continue
                entry_message_id = _to_int(
                    entry.get("message_id")
                    or entry.get("messageId")
                    or entry.get("packet_id")
                    or entry.get("packetId")
                )
                if entry_message_id != clean_message_id:
                    continue
                return {
                    "delivery_state": str(entry.get("delivery_state") or "").strip().lower(),
                    "delivery_updated_unix": _to_int(
                        entry.get("delivery_updated_unix") or entry.get("deliveryUpdatedUnix")
                    )
                    or 0,
                }
        return None

    def on_receive(self, packet: dict[str, object], interface: object) -> None:
        bot_services: list[object] = []
        with self._lock:
            if not self._accept_packets:
                return
            self.live_packet_count += 1
            history_store = getattr(self, "_history_store", None)
            save_raw_packet_fn = getattr(history_store, "save_raw_packet", None)
            if callable(save_raw_packet_fn):
                try:
                    save_raw_packet_fn(packet)
                except Exception:
                    pass
            self._record_meshyface_profile_unlocked(packet)
            self._record_packet_unlocked(packet, interface, include_live_count=True)
            self._bump_state_revision_unlocked()
            bot_services = [
                service
                for service in (self._ping_bot_service, self._zork_bot_service)
                if service is not None
            ]
        for bot_service in bot_services:
            try:
                handled = bot_service.handle_packet(
                    packet,
                    interface,
                    record_local_chat_fn=self.record_local_chat,
                )
                if handled:
                    break
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

    def load_node_position_counts(self) -> dict[str, dict[str, object]]:
        return _load_tracker_node_position_counts_for_tracker_helper(self)

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
        bot_command: Optional[str] = None,
    ) -> None:
        bot_services: list[object] = []
        should_offer_to_zork = False
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
                bot_command=bot_command,
                now_unix_fn=time.time,
            )
            if changed:
                self._bump_state_revision_unlocked()
                bot_services = [
                    service
                    for service in (self._ping_bot_service, self._zork_bot_service)
                    if service is not None
                ]
                should_offer_to_zork = not bool(is_reaction)
        if should_offer_to_zork and bot_services:
            local_node_id = ""
            from_text = str(from_id or "").strip()
            to_text = str(to_id or "").strip()
            if from_text.startswith("!"):
                local_node_id = from_text
            elif to_text.startswith("!"):
                local_node_id = to_text
            for bot_service in bot_services:
                try:
                    handled = bot_service.handle_local_chat(
                        text=text,
                        from_id=from_id,
                        to_id=to_id,
                        local_node_id=local_node_id,
                        channel_index=channel_index,
                        reply_id=message_id,
                        record_local_chat_fn=self.record_local_chat,
                    )
                    if handled:
                        break
                except Exception:
                    pass

    def seed_packet(self, packet: dict[str, object], interface: object) -> None:
        with self._lock:
            self._record_meshyface_profile_unlocked(packet)
            self._record_packet_unlocked(packet, interface, include_live_count=False)
            self._bump_state_revision_unlocked()

    def _record_meshyface_profile_unlocked(self, packet: object) -> bool:
        if not bool(getattr(self, "meshyface_profile_processing_enabled", False)):
            return False
        profile = _parse_meshyface_profile_packet(packet)
        next_profile = _normalize_meshyface_profile_cache_entry(profile)
        if next_profile is None:
            return False

        if not self._cache_meshyface_profile_unlocked(next_profile):
            return False
        self._persist_meshyface_profile_unlocked(next_profile)
        return True

    def _restore_meshyface_profiles_from_history_unlocked(self) -> None:
        if not bool(getattr(self, "meshyface_profile_processing_enabled", False)):
            return
        history_store = getattr(self, "_history_store", None)
        load_profiles_fn = getattr(history_store, "load_meshyface_profiles", None)
        if not callable(load_profiles_fn):
            return
        try:
            raw_profiles = load_profiles_fn(limit=MESHYFACE_PROFILE_CACHE_LIMIT)
        except TypeError:
            try:
                raw_profiles = load_profiles_fn()
            except Exception:
                return
        except Exception:
            return
        # Dedicated profile persistence was added after raw packets had already
        # been stored by some dashboards.  Only when that dedicated cache has
        # no usable rows do a bounded legacy-packet recovery; existing live
        # rows must remain the source of truth.
        if not raw_profiles:
            backfill_profiles_fn = getattr(
                history_store,
                "backfill_meshyface_profiles_from_packets",
                None,
            )
            if callable(backfill_profiles_fn):
                try:
                    raw_profiles = backfill_profiles_fn(
                        limit=MESHYFACE_PROFILE_CACHE_LIMIT,
                    )
                except TypeError:
                    try:
                        raw_profiles = backfill_profiles_fn()
                    except Exception:
                        pass
                except Exception:
                    # A legacy recovery failure is never allowed to prevent
                    # dashboard startup or ordinary profile reception.
                    pass
        if isinstance(raw_profiles, Mapping):
            profile_rows = raw_profiles.values()
        elif isinstance(raw_profiles, (list, tuple)):
            profile_rows = raw_profiles
        else:
            return
        for raw_profile in profile_rows:
            profile = _normalize_meshyface_profile_cache_entry(raw_profile)
            if profile is not None:
                self._cache_meshyface_profile_unlocked(profile)

    def _persist_meshyface_profile_unlocked(self, profile: dict[str, object]) -> None:
        history_store = getattr(self, "_history_store", None)
        save_profile_fn = getattr(history_store, "save_meshyface_profile", None)
        if not callable(save_profile_fn):
            return
        try:
            save_profile_fn(profile, limit=MESHYFACE_PROFILE_CACHE_LIMIT)
        except TypeError:
            try:
                save_profile_fn(profile)
            except Exception:
                pass
        except Exception:
            # Profile identity is optional dashboard state. A storage failure
            # must not interrupt ordinary radio receive handling.
            pass

    def _cache_meshyface_profile_unlocked(self, profile: dict[str, object]) -> bool:
        node_id = str(profile["node_id"])
        updated_unix = _to_int(profile.get("updated_unix"))
        if updated_unix is None or updated_unix <= 0:
            return False

        existing = self.meshyface_profiles_by_node_id.get(node_id)
        existing_updated = (
            _to_int(existing.get("updated_unix")) if isinstance(existing, dict) else None
        )
        # Manual last-writer-wins: only a strictly newer advertised timestamp
        # may replace a cached profile. Equal timestamps are intentionally
        # ignored so packet arrival order cannot flip the chosen theme.
        if existing_updated is not None and existing_updated >= updated_unix:
            return False

        self.meshyface_profiles_by_node_id[node_id] = dict(profile)

        while len(self.meshyface_profiles_by_node_id) > MESHYFACE_PROFILE_CACHE_LIMIT:
            evicted_node_id = min(
                self.meshyface_profiles_by_node_id,
                key=lambda candidate: (
                    int(
                        _to_int(
                            self.meshyface_profiles_by_node_id[candidate].get(
                                "received_unix"
                            )
                        )
                        or 0
                    ),
                    candidate,
                ),
            )
            del self.meshyface_profiles_by_node_id[evicted_node_id]
        return node_id in self.meshyface_profiles_by_node_id

    def meshyface_profile_processing_status(self) -> dict[str, object]:
        with self._lock:
            return {
                "ok": True,
                "enabled": bool(
                    getattr(self, "meshyface_profile_processing_enabled", False)
                ),
                "cached_profiles": len(self.meshyface_profiles_by_node_id),
            }

    def set_meshyface_profile_processing_enabled(
        self, enabled: bool
    ) -> dict[str, object]:
        with self._lock:
            next_enabled = bool(enabled)
            previous_enabled = bool(
                getattr(self, "meshyface_profile_processing_enabled", False)
            )
            changed = previous_enabled != next_enabled
            self.meshyface_profile_processing_enabled = next_enabled
            cleared_profiles = 0
            if not next_enabled:
                cleared_profiles = len(self.meshyface_profiles_by_node_id)
                self.meshyface_profiles_by_node_id.clear()
            elif changed:
                self._restore_meshyface_profiles_from_history_unlocked()
            if changed or cleared_profiles:
                self._bump_state_revision_unlocked()
            return {
                "ok": True,
                "enabled": next_enabled,
                "changed": bool(changed or cleared_profiles),
                "cached_profiles": len(self.meshyface_profiles_by_node_id),
                "cleared_profiles": cleared_profiles,
            }

    def meshyface_profiles_snapshot(self) -> dict[str, dict[str, object]]:
        with self._lock:
            if not bool(getattr(self, "meshyface_profile_processing_enabled", False)):
                return {}
            profiles: dict[str, dict[str, object]] = {}
            for node_id, profile in self.meshyface_profiles_by_node_id.items():
                snapshot = _normalize_meshyface_profile_cache_entry(profile)
                if snapshot is not None:
                    profiles[str(node_id)] = snapshot
            return profiles

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
