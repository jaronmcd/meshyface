import time

from .history_queries import (
    fetch_packet_search_rows as _fetch_packet_search_rows_helper,
    fetch_recent_packet_rows as _fetch_recent_packet_rows_helper,
)
from .history_raw_writes import (
    save_packet_record as _save_packet_record_helper,
)
from .helpers import safe_json_loads as _safe_json_loads
from .history_read_api import (
    load_recent_packets_data as _load_recent_packets_data_helper,
)
from .history_readers import (
    decode_recent_packets_rows as _decode_recent_packets_rows_helper,
)
from .history_store_runtime_contracts import (
    HistoryStoreReadState,
    HistoryStoreWriteState,
)
from .history_writes import (
    save_packet_event_and_rollups as _save_packet_event_and_rollups_helper,
)


def load_recent_packets(store: HistoryStoreReadState, limit: int) -> list[dict[str, object]]:
    read_conn = getattr(store, "_read_conn", None)
    if read_conn is None or read_conn is store._conn:
        read_conn = store._conn
        read_lock = store._lock
    else:
        read_lock = getattr(store, "_read_lock", None) or store._lock
    with read_lock:
        return _load_recent_packets_data_helper(
            read_conn,
            limit=limit,
            fetch_recent_packet_rows_fn=_fetch_recent_packet_rows_helper,
            decode_recent_packets_rows_fn=_decode_recent_packets_rows_helper,
        )


def search_packets(
    store: HistoryStoreReadState,
    needle: str,
    *,
    limit: int | None = None,
    before: int | None = None,
    after: int | None = None,
    scope: str | None = None,
    scan_limit: int | None = None,
) -> dict[str, object]:
    clean_needle = str(needle or "").strip()
    clean_scope = str(scope or "both").strip().lower()
    if clean_scope not in {"both", "summary", "packet"}:
        clean_scope = "both"

    clean_limit = max(1, min(500, int(limit) if isinstance(limit, int) else 120))
    clean_before = max(0, min(30, int(before) if isinstance(before, int) else 0))
    clean_after = max(0, min(30, int(after) if isinstance(after, int) else 0))
    clean_scan_limit = (
        max(1, min(50000, int(scan_limit)))
        if isinstance(scan_limit, int) and scan_limit > 0
        else 0
    )

    read_conn = getattr(store, "_read_conn", None)
    if read_conn is None or read_conn is store._conn:
        read_conn = store._conn
        read_lock = store._lock
    else:
        read_lock = getattr(store, "_read_lock", None) or store._lock

    with read_lock:
        rows = list(
            _fetch_packet_search_rows_helper(
                read_conn,
                clean_scan_limit,
            )
        )

    scanned_packets = len(rows)
    if not clean_needle:
        return {
            "ok": True,
            "query": "",
            "scope": clean_scope,
            "limit": clean_limit,
            "before": clean_before,
            "after": clean_after,
            "scan_limit": clean_scan_limit,
            "scanned_packets": scanned_packets,
            "matches": 0,
            "returned_matches": 0,
            "entries": [],
        }

    needle_lower = clean_needle.lower()
    match_indexes: list[int] = []
    for idx, row in enumerate(rows):
        _packet_id, _created_unix, summary_json, packet_json = row
        summary_text = str(summary_json or "")
        packet_text = str(packet_json or "")
        if clean_scope == "summary":
            haystack = summary_text
        elif clean_scope == "packet":
            haystack = packet_text
        else:
            haystack = f"{summary_text}\n{packet_text}"
        if needle_lower in haystack.lower():
            match_indexes.append(idx)

    total_matches = len(match_indexes)
    selected_match_indexes = match_indexes[-clean_limit:]
    selected_match_set = set(selected_match_indexes)

    if not selected_match_indexes:
        return {
            "ok": True,
            "query": clean_needle,
            "scope": clean_scope,
            "limit": clean_limit,
            "before": clean_before,
            "after": clean_after,
            "scan_limit": clean_scan_limit,
            "scanned_packets": scanned_packets,
            "matches": 0,
            "returned_matches": 0,
            "entries": [],
        }

    ranges: list[tuple[int, int]] = []
    for idx in selected_match_indexes:
        start = max(0, idx - clean_before)
        end = min(scanned_packets - 1, idx + clean_after)
        if not ranges or start > (ranges[-1][1] + 1):
            ranges.append((start, end))
        else:
            ranges[-1] = (ranges[-1][0], max(ranges[-1][1], end))

    entries: list[dict[str, object]] = []
    for range_idx, (start, end) in enumerate(ranges):
        if range_idx > 0:
            entries.append({"separator": True})
        for idx in range(start, end + 1):
            packet_id, created_unix, summary_json, packet_json = rows[idx]
            summary = _safe_json_loads(summary_json, {})
            if not isinstance(summary, dict):
                summary = {}
            packet = _safe_json_loads(packet_json, {})
            if not isinstance(packet, dict):
                packet = {}
            entries.append(
                {
                    "separator": False,
                    "match": idx in selected_match_set,
                    "packet_row_id": int(packet_id) if packet_id is not None else None,
                    "created_unix": int(created_unix) if created_unix is not None else None,
                    "summary": summary,
                    "packet": packet,
                }
            )

    return {
        "ok": True,
        "query": clean_needle,
        "scope": clean_scope,
        "limit": clean_limit,
        "before": clean_before,
        "after": clean_after,
        "scan_limit": clean_scan_limit,
        "scanned_packets": scanned_packets,
        "matches": total_matches,
        "returned_matches": len(selected_match_indexes),
        "entries": entries,
    }


def save_packet(store: HistoryStoreWriteState, packet_entry: dict[str, object]) -> None:
    with store._lock:
        _save_packet_record_helper(
            store._conn,
            packet_entry,
            now_unix_fn=time.time,
            save_packet_event_and_rollups_fn=_save_packet_event_and_rollups_helper,
        )
        store._maybe_prune_unlocked()
        store._conn.commit()
