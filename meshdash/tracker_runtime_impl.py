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
from .packet_replay_guard import PacketReplayGuard
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
        self.meshyface_profile_processing_enabled = (
            self._load_meshyface_profile_processing_enabled()
        )
        self.meshyface_profiles_by_node_id: dict[str, dict[str, object]] = {}
        self._restore_meshyface_profiles_from_history_unlocked()
        self._packet_replay_guard = PacketReplayGuard()
        self.dropped_replay_packet_count = 0

    def _bump_state_revision_unlocked(self) -> None:
        self.state_revision = int(getattr(self, "state_revision", 0) or 0) + 1

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
        with self._lock:
            if not self._accept_packets:
                return
            if not self._packet_replay_guard.accept(packet):
                self.dropped_replay_packet_count += 1
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

    def _load_meshyface_profile_processing_enabled(self) -> bool:
        history_store = getattr(self, "_history_store", None)
        load_settings_fn = getattr(
            history_store,
            "get_meshyface_profile_processing_settings",
            None,
        )
        if not callable(load_settings_fn):
            return False
        try:
            response = load_settings_fn()
        except Exception:
            return False
        if not isinstance(response, Mapping):
            return False
        return bool(response.get("enabled"))

    def _persist_meshyface_profile_processing_enabled_unlocked(self, enabled: bool) -> None:
        history_store = getattr(self, "_history_store", None)
        save_settings_fn = getattr(
            history_store,
            "set_meshyface_profile_processing_settings",
            None,
        )
        if not callable(save_settings_fn):
            return
        try:
            save_settings_fn(bool(enabled))
        except Exception:
            pass

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
            self._persist_meshyface_profile_processing_enabled_unlocked(next_enabled)
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
