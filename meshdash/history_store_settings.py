import json
import time

from .history_env_metrics import (
    normalize_custom_telemetry_rules as _normalize_custom_telemetry_rules,
)
from .history_store_runtime_contracts import HistoryStoreReadState, HistoryStoreWriteState

_CUSTOM_TELEMETRY_RULES_KEY = "custom_telemetry_rules_v1"
_BOT_RUNTIME_SETTINGS_KEY = "bot_runtime_settings_v1"
_MESHYFACE_PROFILE_PROCESSING_SETTINGS_KEY = "meshyface_profile_processing_settings_v1"


def _coerce_bool(value: object, *, fallback: bool = False) -> bool:
    if value is None:
        return bool(fallback)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "enabled", "online"}:
        return True
    if text in {"0", "false", "no", "off", "disabled", "offline"}:
        return False
    return bool(fallback)


def _default_bot_runtime_settings() -> dict[str, object]:
    return {
        "zork_enabled": False,
        "ping_enabled": False,
        "ping_message_only": False,
    }


def _normalize_bot_runtime_settings(
    payload: object,
    *,
    previous: object = None,
) -> dict[str, object]:
    source = payload if isinstance(payload, dict) else {}
    previous_source = previous if isinstance(previous, dict) else {}
    zork_enabled_raw = source.get("zork_enabled", source.get("zorkEnabled"))
    ping_enabled_raw = source.get("ping_enabled", source.get("pingEnabled"))
    ping_message_only_raw = source.get(
        "ping_message_only",
        source.get("pingMessageOnly"),
    )
    return {
        "zork_enabled": _coerce_bool(
            zork_enabled_raw,
            fallback=_coerce_bool(previous_source.get("zork_enabled"), fallback=False),
        ),
        "ping_enabled": _coerce_bool(
            ping_enabled_raw,
            fallback=_coerce_bool(previous_source.get("ping_enabled"), fallback=False),
        ),
        "ping_message_only": _coerce_bool(
            ping_message_only_raw,
            fallback=_coerce_bool(previous_source.get("ping_message_only"), fallback=False),
        ),
    }


def _load_custom_telemetry_rules_unlocked(
    store: HistoryStoreReadState,
) -> tuple[list[dict[str, object]], int]:
    row = store._conn.execute(
        """
        SELECT value_json, updated_unix
        FROM dashboard_settings
        WHERE key = ?
        """,
        (_CUSTOM_TELEMETRY_RULES_KEY,),
    ).fetchone()
    if not row:
        return [], 0
    value_json = row[0] if len(row) > 0 else "[]"
    updated_unix = int(row[1] if len(row) > 1 and row[1] is not None else 0)
    try:
        parsed = json.loads(str(value_json or "[]"))
    except Exception:
        parsed = []
    rules = _normalize_custom_telemetry_rules(parsed)
    return rules, updated_unix


def load_custom_telemetry_settings(
    store: HistoryStoreReadState,
) -> dict[str, object]:
    with store._lock:
        rules, updated_unix = _load_custom_telemetry_rules_unlocked(store)
        setattr(store, "_custom_telemetry_rules", list(rules))
        setattr(store, "_custom_telemetry_updated_unix", int(updated_unix))
    return {
        "ok": True,
        "rules": rules,
        "updated_unix": int(updated_unix),
    }


def load_bot_runtime_settings(
    store: HistoryStoreReadState,
) -> dict[str, object]:
    default_settings = _default_bot_runtime_settings()
    with store._lock:
        row = store._conn.execute(
            """
            SELECT value_json, updated_unix
            FROM dashboard_settings
            WHERE key = ?
            """,
            (_BOT_RUNTIME_SETTINGS_KEY,),
        ).fetchone()
        if not row:
            settings = default_settings
            updated_unix = 0
        else:
            value_json = row[0] if len(row) > 0 else "{}"
            updated_unix = int(row[1] if len(row) > 1 and row[1] is not None else 0)
            try:
                parsed = json.loads(str(value_json or "{}"))
            except Exception:
                parsed = {}
            settings = _normalize_bot_runtime_settings(parsed)
        setattr(store, "_bot_runtime_settings", dict(settings))
        setattr(store, "_bot_runtime_settings_updated_unix", int(updated_unix))
    return {
        "ok": True,
        "settings": settings,
        "updated_unix": int(updated_unix),
    }


def load_meshyface_profile_processing_settings(
    store: HistoryStoreReadState,
) -> dict[str, object]:
    with store._lock:
        row = store._conn.execute(
            """
            SELECT value_json, updated_unix
            FROM dashboard_settings
            WHERE key = ?
            """,
            (_MESHYFACE_PROFILE_PROCESSING_SETTINGS_KEY,),
        ).fetchone()
        if not row:
            enabled = False
            updated_unix = 0
        else:
            value_json = row[0] if len(row) > 0 else "{}"
            updated_unix = int(row[1] if len(row) > 1 and row[1] is not None else 0)
            try:
                parsed = json.loads(str(value_json or "{}"))
            except Exception:
                parsed = {}
            source = parsed if isinstance(parsed, dict) else {}
            enabled = _coerce_bool(source.get("enabled"), fallback=False)
        setattr(store, "_meshyface_profile_processing_enabled", bool(enabled))
        setattr(store, "_meshyface_profile_processing_updated_unix", int(updated_unix))
    return {
        "ok": True,
        "enabled": bool(enabled),
        "updated_unix": int(updated_unix),
    }


def save_custom_telemetry_settings(
    store: HistoryStoreWriteState,
    *,
    rules: object,
) -> dict[str, object]:
    payload = rules
    if isinstance(payload, dict) and "rules" in payload:
        payload = payload.get("rules")
    if payload is None:
        raise ValueError("Custom telemetry rules payload is required")
    if not isinstance(payload, list):
        raise ValueError("Custom telemetry rules must be a JSON array")

    normalized_rules = _normalize_custom_telemetry_rules(payload)
    updated_unix = int(time.time())
    value_json = json.dumps(normalized_rules, separators=(",", ":"))
    with store._lock:
        store._conn.execute(
            """
            INSERT INTO dashboard_settings(key, value_json, updated_unix)
            VALUES(?, ?, ?)
            ON CONFLICT(key) DO UPDATE
            SET value_json = excluded.value_json,
                updated_unix = excluded.updated_unix
            """,
            (_CUSTOM_TELEMETRY_RULES_KEY, value_json, updated_unix),
        )
        setattr(store, "_custom_telemetry_rules", list(normalized_rules))
        setattr(store, "_custom_telemetry_updated_unix", int(updated_unix))
        store._conn.commit()
    return {
        "ok": True,
        "rules": normalized_rules,
        "updated_unix": int(updated_unix),
    }


def save_bot_runtime_settings(
    store: HistoryStoreWriteState,
    *,
    settings: object,
) -> dict[str, object]:
    payload = settings
    if (
        hasattr(payload, "zork_enabled")
        or hasattr(payload, "ping_enabled")
        or hasattr(payload, "ping_message_only")
    ):
        payload = {
            "zork_enabled": getattr(payload, "zork_enabled", None),
            "ping_enabled": getattr(payload, "ping_enabled", None),
            "ping_message_only": getattr(payload, "ping_message_only", None),
        }
    if isinstance(payload, dict) and "settings" in payload and isinstance(payload.get("settings"), dict):
        payload = payload.get("settings")
    updated_unix = int(time.time())
    with store._lock:
        existing_row = store._conn.execute(
            """
            SELECT value_json
            FROM dashboard_settings
            WHERE key = ?
            """,
            (_BOT_RUNTIME_SETTINGS_KEY,),
        ).fetchone()
        try:
            existing_parsed = json.loads(str(existing_row[0] or "{}")) if existing_row else {}
        except Exception:
            existing_parsed = {}
        previous_settings = _normalize_bot_runtime_settings(existing_parsed)
        normalized_settings = _normalize_bot_runtime_settings(
            payload,
            previous=previous_settings,
        )
        value_json = json.dumps(normalized_settings, separators=(",", ":"))
        store._conn.execute(
            """
            INSERT INTO dashboard_settings(key, value_json, updated_unix)
            VALUES(?, ?, ?)
            ON CONFLICT(key) DO UPDATE
            SET value_json = excluded.value_json,
                updated_unix = excluded.updated_unix
            """,
            (_BOT_RUNTIME_SETTINGS_KEY, value_json, updated_unix),
        )
        setattr(store, "_bot_runtime_settings", dict(normalized_settings))
        setattr(store, "_bot_runtime_settings_updated_unix", int(updated_unix))
        store._conn.commit()
    return {
        "ok": True,
        "settings": normalized_settings,
        "updated_unix": int(updated_unix),
    }


def save_meshyface_profile_processing_settings(
    store: HistoryStoreWriteState,
    *,
    enabled: object,
) -> dict[str, object]:
    next_enabled = _coerce_bool(enabled, fallback=False)
    updated_unix = int(time.time())
    value_json = json.dumps({"enabled": next_enabled}, separators=(",", ":"))
    with store._lock:
        store._conn.execute(
            """
            INSERT INTO dashboard_settings(key, value_json, updated_unix)
            VALUES(?, ?, ?)
            ON CONFLICT(key) DO UPDATE
            SET value_json = excluded.value_json,
                updated_unix = excluded.updated_unix
            """,
            (_MESHYFACE_PROFILE_PROCESSING_SETTINGS_KEY, value_json, updated_unix),
        )
        setattr(store, "_meshyface_profile_processing_enabled", bool(next_enabled))
        setattr(store, "_meshyface_profile_processing_updated_unix", int(updated_unix))
        store._conn.commit()
    return {
        "ok": True,
        "enabled": bool(next_enabled),
        "updated_unix": int(updated_unix),
    }
