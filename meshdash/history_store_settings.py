import json
import re
import time

from .config import DEFAULT_CHAT_MAX_BYTES
from .helpers_node_names import normalize_node_id_text as _normalize_node_id_text
from .history_env_metrics import (
    normalize_custom_telemetry_rules as _normalize_custom_telemetry_rules,
)
from .history_store_runtime_contracts import HistoryStoreReadState, HistoryStoreWriteState

_CUSTOM_TELEMETRY_RULES_KEY = "custom_telemetry_rules_v1"
_BBS_HOST_SETTINGS_KEY = "bbs_host_settings_v1"
_BBS_HOST_POSTS_KEY = "bbs_host_posts_v1"
_BOT_RUNTIME_SETTINGS_KEY = "bot_runtime_settings_v1"
_MESHYFACE_PROFILE_PROCESSING_SETTINGS_KEY = "meshyface_profile_processing_settings_v1"
_BBS_HOST_MAX_POSTS = 260
_BBS_MAX_POST_CHARS = DEFAULT_CHAT_MAX_BYTES


def _sanitize_bbs_text(value: object, max_chars: int) -> str:
    limit = max(1, int(max_chars))
    return (
        " ".join(str(value if value is not None else "").replace("|", " ").split())
        .strip()
        [:limit]
    )


def _normalize_bbs_board_id(value: object, fallback: object = "") -> str:
    text = str(value or fallback or "").strip().lower()
    text = re.sub(r"[^a-z0-9_-]+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = re.sub(r"^[-_]+|[-_]+$", "", text)
    return text[:24]


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


def _normalize_bbs_channel_index(value: object, *, fallback: int = 0) -> int:
    try:
        candidate = int(value)
    except Exception:
        return max(0, int(fallback))
    if candidate < 0:
        return max(0, int(fallback))
    return candidate


def _normalize_bbs_host_settings(
    payload: object,
    *,
    previous: object = None,
) -> dict[str, object]:
    source = payload if isinstance(payload, dict) else {}
    previous_source = previous if isinstance(previous, dict) else {}
    title = _sanitize_bbs_text(source.get("title"), 42) or "Packet Exchange"
    board_id = _normalize_bbs_board_id(
        source.get("board_id", source.get("boardId")),
        title,
    )
    motd = _sanitize_bbs_text(source.get("motd"), 120) or "2400 baud online."
    enabled_raw = source.get(
        "enabled",
        source.get("host_enabled", source.get("hostEnabled")),
    )
    channel_raw = source.get("channel_index", source.get("channelIndex"))
    started_raw = source.get("started_unix", source.get("startedUnix"))
    enabled = _coerce_bool(
        enabled_raw,
        fallback=_coerce_bool(previous_source.get("enabled"), fallback=False),
    )
    channel_index = _normalize_bbs_channel_index(
        channel_raw,
        fallback=_normalize_bbs_channel_index(previous_source.get("channel_index"), fallback=0),
    )
    try:
        started_unix = max(0, int(started_raw if started_raw is not None else previous_source.get("started_unix") or 0))
    except Exception:
        started_unix = max(0, int(previous_source.get("started_unix") or 0))
    return {
        "title": title,
        "board_id": board_id,
        "motd": motd,
        "enabled": enabled,
        "channel_index": channel_index,
        "started_unix": started_unix if enabled else 0,
    }


def _is_canonical_node_id(value: object) -> bool:
    text = _normalize_node_id_text(value)
    return bool(text.startswith("!") and len(text) == 9)


def _normalize_bbs_post(payload: object) -> dict[str, object] | None:
    source = payload if isinstance(payload, dict) else {}
    entry_id = _sanitize_bbs_text(
        source.get("entry_id", source.get("entryId")),
        60,
    )
    author_id = _normalize_node_id_text(
        source.get("author_id", source.get("authorId")),
    )
    if not _is_canonical_node_id(author_id):
        author_id = ""
    author_name = _sanitize_bbs_text(
        source.get("author_name", source.get("authorName")),
        48,
    )
    text = _sanitize_bbs_text(source.get("text"), _BBS_MAX_POST_CHARS)
    try:
        unix_value = int(source.get("unix") or 0)
    except Exception:
        unix_value = 0
    unix_value = max(0, unix_value)
    if not text:
        return None
    if not entry_id:
        entry_id = f"bbs-{unix_value:x}-{abs(hash((author_id, author_name, text))) & 0xFFFFFFFF:08x}"
    return {
        "entry_id": entry_id,
        "author_id": author_id,
        "author_name": author_name or author_id or "anon",
        "text": text,
        "unix": unix_value,
    }


def _normalize_bbs_posts(payload: object) -> list[dict[str, object]]:
    source_rows = payload if isinstance(payload, list) else []
    normalized_rows: list[dict[str, object]] = []
    seen_entry_ids: set[str] = set()
    for row in source_rows:
        normalized = _normalize_bbs_post(row)
        if not normalized:
            continue
        entry_id = str(normalized.get("entry_id") or "").strip()
        if not entry_id or entry_id in seen_entry_ids:
            continue
        seen_entry_ids.add(entry_id)
        normalized_rows.append(normalized)
    normalized_rows.sort(
        key=lambda row: (
            int(row.get("unix") or 0),
            str(row.get("entry_id") or ""),
        )
    )
    if len(normalized_rows) > _BBS_HOST_MAX_POSTS:
        normalized_rows = normalized_rows[-_BBS_HOST_MAX_POSTS:]
    return normalized_rows


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


def load_bbs_settings(
    store: HistoryStoreReadState,
) -> dict[str, object]:
    default_settings = _normalize_bbs_host_settings({})
    with store._lock:
        row = store._conn.execute(
            """
            SELECT value_json, updated_unix
            FROM dashboard_settings
            WHERE key = ?
            """,
            (_BBS_HOST_SETTINGS_KEY,),
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
            settings = _normalize_bbs_host_settings(parsed)
        setattr(store, "_bbs_host_settings", dict(settings))
        setattr(store, "_bbs_host_settings_updated_unix", int(updated_unix))
    return {
        "ok": True,
        "settings": settings,
        "updated_unix": int(updated_unix),
    }


def load_bbs_posts(
    store: HistoryStoreReadState,
) -> dict[str, object]:
    with store._lock:
        row = store._conn.execute(
            """
            SELECT value_json, updated_unix
            FROM dashboard_settings
            WHERE key = ?
            """,
            (_BBS_HOST_POSTS_KEY,),
        ).fetchone()
        if not row:
            posts: list[dict[str, object]] = []
            updated_unix = 0
        else:
            value_json = row[0] if len(row) > 0 else "[]"
            updated_unix = int(row[1] if len(row) > 1 and row[1] is not None else 0)
            try:
                parsed = json.loads(str(value_json or "[]"))
            except Exception:
                parsed = []
            posts = _normalize_bbs_posts(parsed)
        setattr(store, "_bbs_host_posts", list(posts))
        setattr(store, "_bbs_host_posts_updated_unix", int(updated_unix))
    return {
        "ok": True,
        "posts": posts,
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


def save_bbs_settings(
    store: HistoryStoreWriteState,
    *,
    settings: object,
) -> dict[str, object]:
    payload = settings
    if hasattr(payload, "title") or hasattr(payload, "board_id") or hasattr(payload, "motd"):
        payload = {
            "title": getattr(payload, "title", None),
            "board_id": getattr(payload, "board_id", None),
            "motd": getattr(payload, "motd", None),
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
            (_BBS_HOST_SETTINGS_KEY,),
        ).fetchone()
        try:
            existing_parsed = json.loads(str(existing_row[0] or "{}")) if existing_row else {}
        except Exception:
            existing_parsed = {}
        previous_settings = _normalize_bbs_host_settings(existing_parsed)
        normalized_settings = _normalize_bbs_host_settings(
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
            (_BBS_HOST_SETTINGS_KEY, value_json, updated_unix),
        )
        setattr(store, "_bbs_host_settings", dict(normalized_settings))
        setattr(store, "_bbs_host_settings_updated_unix", int(updated_unix))
        store._conn.commit()
    return {
        "ok": True,
        "settings": normalized_settings,
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


def append_bbs_post(
    store: HistoryStoreWriteState,
    *,
    post: object,
) -> dict[str, object]:
    payload = post
    if hasattr(payload, "text") or hasattr(payload, "author_name") or hasattr(payload, "entry_id"):
        payload = {
            "entry_id": getattr(payload, "entry_id", None),
            "author_id": getattr(payload, "author_id", None),
            "author_name": getattr(payload, "author_name", None),
            "text": getattr(payload, "text", None),
            "unix": getattr(payload, "unix", None),
        }
    if isinstance(payload, dict) and "post" in payload and isinstance(payload.get("post"), dict):
        payload = payload.get("post")
    normalized_post = _normalize_bbs_post(payload)
    if normalized_post is None:
        raise ValueError("BBS post text is required")
    updated_unix = max(int(time.time()), int(normalized_post.get("unix") or 0))
    with store._lock:
        existing_row = store._conn.execute(
            """
            SELECT value_json
            FROM dashboard_settings
            WHERE key = ?
            """,
            (_BBS_HOST_POSTS_KEY,),
        ).fetchone()
        try:
            existing_parsed = json.loads(str(existing_row[0] or "[]")) if existing_row else []
        except Exception:
            existing_parsed = []
        rows = _normalize_bbs_posts(existing_parsed)
        entry_id = str(normalized_post.get("entry_id") or "").strip()
        if not any(str(row.get("entry_id") or "").strip() == entry_id for row in rows):
            rows.append(normalized_post)
        rows = _normalize_bbs_posts(rows)
        value_json = json.dumps(rows, separators=(",", ":"))
        store._conn.execute(
            """
            INSERT INTO dashboard_settings(key, value_json, updated_unix)
            VALUES(?, ?, ?)
            ON CONFLICT(key) DO UPDATE
            SET value_json = excluded.value_json,
                updated_unix = excluded.updated_unix
            """,
            (_BBS_HOST_POSTS_KEY, value_json, updated_unix),
        )
        setattr(store, "_bbs_host_posts", list(rows))
        setattr(store, "_bbs_host_posts_updated_unix", int(updated_unix))
        store._conn.commit()
    return {
        "ok": True,
        "post": normalized_post,
        "posts": rows,
        "updated_unix": int(updated_unix),
    }
