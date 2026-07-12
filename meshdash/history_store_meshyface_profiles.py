import json
from collections.abc import Mapping

from .helpers import safe_json_loads as _safe_json_loads
from .helpers import to_int as _to_int
from .history_store_runtime_contracts import (
    HistoryStoreReadState,
    HistoryStoreWriteState,
)
from .meshyface_profile import (
    MESHYFACE_PROFILE_CACHE_LIMIT,
    MESHYFACE_PROFILE_MAX_PAYLOAD_BYTES,
    normalize_meshyface_profile_node_id as _normalize_meshyface_profile_node_id,
    normalize_meshyface_profile_ghost as _normalize_meshyface_profile_ghost,
    normalize_meshyface_theme_recipe as _normalize_meshyface_theme_recipe,
    parse_meshyface_profile_packet as _parse_meshyface_profile_packet,
)


# This is deliberately a fixed, newest-first slice of raw packet history.  A
# profile broadcast is rare, but startup must never turn an upgrade into an
# unbounded JSON scan of a long-running dashboard database.
MESHYFACE_PROFILE_BACKFILL_PACKET_LIMIT = 4096


def _profile_cache_limit(value: object) -> int:
    limit = _to_int(value)
    if limit is None or limit <= 0:
        return MESHYFACE_PROFILE_CACHE_LIMIT
    return int(limit)


def _profile_backfill_packet_limit(value: object) -> int:
    limit = _to_int(value)
    if limit is None or limit <= 0:
        return MESHYFACE_PROFILE_BACKFILL_PACKET_LIMIT
    return min(int(limit), MESHYFACE_PROFILE_BACKFILL_PACKET_LIMIT)


def _normalize_profile(value: object) -> dict[str, object] | None:
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


def _profile_from_row(row: object) -> dict[str, object] | None:
    if not isinstance(row, tuple) or len(row) < 4:
        return None
    theme: object = None
    ghost: object = None
    raw_theme = row[3]
    if isinstance(raw_theme, str) and raw_theme:
        try:
            theme = json.loads(raw_theme)
        except (TypeError, ValueError):
            theme = None
    if isinstance(theme, Mapping) and ("theme" in theme or "ghost" in theme):
        ghost = theme.get("ghost")
        theme = theme.get("theme")
    profile: dict[str, object] = {
        "node_id": row[0],
        "updated_unix": row[1],
        "received_unix": row[2],
        "theme": theme,
    }
    if ghost:
        profile["ghost"] = ghost
    return _normalize_profile(profile)


def _profiles_from_rows(rows: object) -> list[dict[str, object]]:
    if not isinstance(rows, (list, tuple)):
        return []
    profiles: list[dict[str, object]] = []
    for row in rows:
        profile = _profile_from_row(row)
        if profile is not None:
            profiles.append(profile)
    return profiles


def _load_meshyface_profiles_from_connection_unlocked(
    conn: object,
    *,
    limit: int,
) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT node_id, updated_unix, received_unix, theme_json
        FROM meshyface_profiles
        ORDER BY received_unix DESC, node_id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return _profiles_from_rows(rows)


def _decode_persisted_profile_payload(value: object) -> object:
    """Restore a JSON-safe raw payload to the bytes expected by the parser.

    ``to_jsonable`` stores byte payloads as hex text in ``packet_json``.  Do
    not accept arbitrary strings here: this recovery path only decodes an
    even-length, strictly hexadecimal payload within the Meshtastic data
    payload limit.
    """
    if not isinstance(value, str):
        return value
    text = value.strip()
    if (
        not text
        or len(text) % 2
        or len(text) > (MESHYFACE_PROFILE_MAX_PAYLOAD_BYTES * 2)
        or any(char not in "0123456789abcdefABCDEF" for char in text)
    ):
        return value
    try:
        return bytes.fromhex(text)
    except ValueError:
        return value


def _normalize_persisted_profile_packet(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    decoded = value.get("decoded")
    if not isinstance(decoded, Mapping):
        return None
    packet = dict(value)
    normalized_decoded = dict(decoded)
    normalized_decoded["payload"] = _decode_persisted_profile_payload(
        normalized_decoded.get("payload")
    )
    packet["decoded"] = normalized_decoded
    return packet


def _profile_from_persisted_packet(
    *,
    created_unix: object,
    packet_json: object,
) -> dict[str, object] | None:
    received_unix = _to_int(created_unix)
    if received_unix is None or received_unix <= 0:
        return None
    packet = _normalize_persisted_profile_packet(_safe_json_loads(packet_json, {}))
    if packet is None:
        return None
    return _normalize_profile(
        _parse_meshyface_profile_packet(
            packet,
            now_unix_fn=lambda: float(received_unix),
        )
    )


def _read_connection_and_lock(store: HistoryStoreReadState) -> tuple[object, object]:
    read_conn = getattr(store, "_read_conn", None)
    if read_conn is None or read_conn is store._conn:
        return store._conn, store._lock
    return read_conn, getattr(store, "_read_lock", None) or store._lock


def load_meshyface_profiles(
    store: HistoryStoreReadState,
    *,
    limit: object = MESHYFACE_PROFILE_CACHE_LIMIT,
) -> list[dict[str, object]]:
    profile_limit = _profile_cache_limit(limit)
    read_conn, read_lock = _read_connection_and_lock(store)
    with read_lock:
        return _load_meshyface_profiles_from_connection_unlocked(
            read_conn,
            limit=profile_limit,
        )


def _prune_meshyface_profiles_unlocked(
    store: HistoryStoreWriteState,
    *,
    limit: int,
) -> None:
    count_row = store._conn.execute(
        "SELECT COUNT(*) FROM meshyface_profiles"
    ).fetchone()
    count = _to_int(count_row[0]) if count_row else 0
    excess = max(0, int(count or 0) - limit)
    if excess <= 0:
        return
    rows = store._conn.execute(
        """
        SELECT node_id
        FROM meshyface_profiles
        ORDER BY received_unix ASC, node_id ASC
        LIMIT ?
        """,
        (excess,),
    ).fetchall()
    store._conn.executemany(
        "DELETE FROM meshyface_profiles WHERE node_id = ?",
        [(row[0],) for row in rows if row],
    )


def _save_normalized_meshyface_profile_unlocked(
    store: HistoryStoreWriteState,
    normalized: dict[str, object],
) -> bool:
    theme = _normalize_meshyface_theme_recipe(normalized.get("theme"))
    if theme is None:
        return False
    # The existing table retains a non-null color column. It is storage-only:
    # v2 profiles derive it solely from the advertised theme, never from wire
    # or UI color state.
    storage_color = str(theme["line_color"])
    ghost = _normalize_meshyface_profile_ghost(normalized.get("ghost"))
    storage_payload: object = theme
    if ghost:
        storage_payload = {
            "theme": theme,
            "ghost": ghost,
        }
    theme_json = json.dumps(storage_payload, separators=(",", ":"), ensure_ascii=False)
    cursor = store._conn.execute(
        """
        INSERT INTO meshyface_profiles(
            node_id, color, updated_unix, received_unix, theme_json
        )
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(node_id) DO UPDATE
        SET color = excluded.color,
            updated_unix = excluded.updated_unix,
            received_unix = excluded.received_unix,
            theme_json = excluded.theme_json
        WHERE excluded.updated_unix > meshyface_profiles.updated_unix
        """,
        (
            normalized["node_id"],
            storage_color,
            normalized["updated_unix"],
            normalized["received_unix"],
            theme_json,
        ),
    )
    return cursor.rowcount > 0


def save_meshyface_profile(
    store: HistoryStoreWriteState,
    profile: object,
    *,
    limit: object = MESHYFACE_PROFILE_CACHE_LIMIT,
) -> bool:
    normalized = _normalize_profile(profile)
    if normalized is None:
        return False
    profile_limit = _profile_cache_limit(limit)
    with store._lock:
        changed = _save_normalized_meshyface_profile_unlocked(store, normalized)
        if changed:
            _prune_meshyface_profiles_unlocked(store, limit=profile_limit)
            store._conn.commit()
    return changed


def backfill_meshyface_profiles_from_packets(
    store: HistoryStoreWriteState,
    *,
    limit: object = MESHYFACE_PROFILE_CACHE_LIMIT,
    packet_limit: object = MESHYFACE_PROFILE_BACKFILL_PACKET_LIMIT,
) -> list[dict[str, object]]:
    """Recover profile rows from a bounded newest slice of legacy packets.

    This runs only while the dedicated profile table is empty.  It makes a
    schema upgrade/restart recover old broadcasts without allowing historical
    packets to replace any profile row already persisted by the live receiver.
    """
    profile_limit = _profile_cache_limit(limit)
    raw_packet_limit = _profile_backfill_packet_limit(packet_limit)
    with store._lock:
        existing = store._conn.execute(
            "SELECT 1 FROM meshyface_profiles LIMIT 1"
        ).fetchone()
        if existing is not None:
            return []

        # Query by the primary-key order first, then inspect only this bounded
        # set in Python.  A payload LIKE predicate here would cause SQLite to
        # search arbitrarily far back through a large packet table.
        rows = store._conn.execute(
            """
            SELECT created_unix, packet_json
            FROM packets
            ORDER BY id DESC
            LIMIT ?
            """,
            (raw_packet_limit,),
        ).fetchall()

        candidates_by_node: dict[str, dict[str, object]] = {}
        # Replay oldest-to-newest so equal advertised timestamps preserve the
        # same first-writer behavior as the live strict LWW cache.
        for row in reversed(rows):
            if not isinstance(row, tuple) or len(row) < 2:
                continue
            profile = _profile_from_persisted_packet(
                created_unix=row[0],
                packet_json=row[1],
            )
            if profile is None:
                continue
            node_id = str(profile["node_id"])
            existing_profile = candidates_by_node.get(node_id)
            existing_updated = (
                _to_int(existing_profile.get("updated_unix"))
                if existing_profile is not None
                else None
            )
            candidate_updated = _to_int(profile.get("updated_unix"))
            if candidate_updated is None:
                continue
            if existing_updated is None or candidate_updated > existing_updated:
                candidates_by_node[node_id] = profile

        if not candidates_by_node:
            return []

        changed = False
        for profile in candidates_by_node.values():
            changed = _save_normalized_meshyface_profile_unlocked(store, profile) or changed
        if changed:
            _prune_meshyface_profiles_unlocked(store, limit=profile_limit)
            store._conn.commit()
        return _load_meshyface_profiles_from_connection_unlocked(
            store._conn,
            limit=profile_limit,
        )
