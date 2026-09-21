"""Bound routine state polls to recently heard nodes.

The radio interface keeps every node heard since the last radio connect, so on a busy
mesh with a long-lived link the node list (and every per-poll build, payload, and browser
render proportional to it) grows with uptime. Routine lite polls carry only nodes heard
within a window, plus nodes the payload still references. Older nodes stay in history and
are reachable through node search.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterable, Mapping

DEFAULT_STATE_NODE_WINDOW_DAYS = 14
STATE_NODE_WINDOW_DAYS_ENV = "MESH_DASH_STATE_NODE_WINDOW_DAYS"
_SECONDS_PER_DAY = 24 * 60 * 60


def state_node_window_seconds(environ: Mapping[str, str] | None = None) -> int:
    """Window for routine polls in seconds; ``0`` disables the window."""
    source = os.environ if environ is None else environ
    raw = str(source.get(STATE_NODE_WINDOW_DAYS_ENV, "") or "").strip()
    if not raw:
        return DEFAULT_STATE_NODE_WINDOW_DAYS * _SECONDS_PER_DAY
    try:
        days = float(raw)
    except ValueError:
        return DEFAULT_STATE_NODE_WINDOW_DAYS * _SECONDS_PER_DAY
    if days != days or days <= 0:
        return 0
    return int(days * _SECONDS_PER_DAY)


def normalize_node_id_text(value: object) -> str:
    return str(value or "").strip().lower()


def _add_node_id(node_ids: set[str], value: object) -> None:
    node_id = normalize_node_id_text(value)
    if node_id and not node_id.startswith("^"):
        node_ids.add(node_id)


def referenced_node_ids(
    *,
    recent_chat: Iterable[object],
    recent_packets: Iterable[object],
    edges: Iterable[object],
) -> set[str]:
    """Node ids that chat, packet, and edge rows in a state payload refer to."""
    node_ids: set[str] = set()
    for entry in recent_chat:
        if not isinstance(entry, Mapping):
            continue
        for key in (
            "from",
            "from_id",
            "fromId",
            "source",
            "source_id",
            "sourceId",
            "to",
            "to_id",
            "toId",
            "destination",
            "dest",
            "dest_id",
            "destId",
        ):
            _add_node_id(node_ids, entry.get(key))
    for entry in recent_packets:
        if not isinstance(entry, Mapping):
            continue
        summary = entry.get("summary")
        packet = entry.get("packet")
        if isinstance(summary, Mapping):
            for key in ("from", "from_id", "fromId", "to", "to_id", "toId"):
                _add_node_id(node_ids, summary.get(key))
        if isinstance(packet, Mapping):
            for key in ("fromId", "toId", "destination"):
                _add_node_id(node_ids, packet.get(key))
    for edge in edges:
        if not isinstance(edge, Mapping):
            continue
        _add_node_id(node_ids, edge.get("from"))
        _add_node_id(node_ids, edge.get("to"))
    return node_ids


def filter_node_rows_for_window(
    rows: list[dict[str, object]],
    *,
    window_seconds: int,
    keep_node_ids: set[str],
    now_unix: int | None = None,
) -> tuple[list[dict[str, object]], int]:
    """Keep rows heard within the window, favorites, and explicitly kept ids.

    Returns the kept rows (original order) and how many rows were omitted.
    """
    if window_seconds <= 0:
        return rows, 0
    now = int(time.time()) if now_unix is None else int(now_unix)
    cutoff = now - int(window_seconds)
    kept: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if row.get("is_favorite") is True or normalize_node_id_text(row.get("id")) in keep_node_ids:
            kept.append(row)
            continue
        try:
            last_heard = int(row.get("last_heard_unix") or 0)
        except (TypeError, ValueError, OverflowError):
            last_heard = 0
        if last_heard > 0 and last_heard >= cutoff:
            kept.append(row)
    return kept, len(rows) - len(kept)


def node_matches_search(query: str, *values: object) -> bool:
    needle = query.casefold()
    return any(needle in str(value).casefold() for value in values if value)
