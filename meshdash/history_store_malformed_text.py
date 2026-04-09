import time

from .history_store_runtime_contracts import HistoryStoreReadState


def _is_hex_text(value: str) -> bool:
    return bool(value) and all(ch in "0123456789abcdefABCDEF" for ch in value)


def _canonical_node_id(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("!") and len(text) == 9 and _is_hex_text(text[1:]):
        return f"!{text[1:].lower()}"
    if len(text) == 8 and _is_hex_text(text):
        return f"!{text.lower()}"
    return text


def _positive_int(value: object) -> int | None:
    try:
        number = int(value)  # type: ignore[arg-type]
    except Exception:
        return None
    return number if number > 0 else None


def _preview_payload(value: object, limit: int = 48) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return f"{text[:max(8, limit - 3)]}..."


def load_malformed_text_history(
    store: HistoryStoreReadState,
    *,
    window_hours: int | None = None,
    node_id: str | None = None,
    limit: int | None = None,
) -> dict[str, object]:
    clean_hours = max(1, min(24 * 365, int(window_hours) if isinstance(window_hours, int) else 72))
    clean_limit = max(1, min(500, int(limit) if isinstance(limit, int) else 100))
    clean_node_id = _canonical_node_id(node_id or "")
    cutoff_unix = int(time.time()) - (clean_hours * 3600)

    read_conn = getattr(store, "_read_conn", None)
    if read_conn is None or read_conn is store._conn:
        read_conn = store._conn
        read_lock = store._lock
    else:
        read_lock = getattr(store, "_read_lock", None) or store._lock

    all_rows_query = """
        SELECT
          id,
          created_unix,
          packet_row_id,
          from_id,
          from_label,
          portnum,
          packet_id,
          rx_time_unix,
          payload_text
        FROM malformed_text_payloads
        WHERE COALESCE(rx_time_unix, created_unix) >= ?
          AND (? = '' OR from_id = ?)
        ORDER BY COALESCE(rx_time_unix, created_unix) DESC, id DESC
    """
    params = (cutoff_unix, clean_node_id, clean_node_id)

    with read_lock:
        rows = list(read_conn.execute(all_rows_query, params))

    entries: list[dict[str, object]] = []
    senders_by_id: dict[str, dict[str, object]] = {}
    first_seen_unix: int | None = None
    last_seen_unix: int | None = None

    for idx, row in enumerate(rows):
        row_id, created_unix, packet_row_id, from_id, from_label, portnum, packet_id, rx_time_unix, payload_text = row
        packet_unix = _positive_int(rx_time_unix) or _positive_int(created_unix)
        if packet_unix is not None:
            if first_seen_unix is None or packet_unix < first_seen_unix:
                first_seen_unix = packet_unix
            if last_seen_unix is None or packet_unix > last_seen_unix:
                last_seen_unix = packet_unix

        clean_from_id = _canonical_node_id(from_id)
        clean_from_label = str(from_label or clean_from_id or "Unknown node").strip() or (clean_from_id or "Unknown node")
        payload_text_value = str(payload_text or "").strip()

        sender_bucket = senders_by_id.get(clean_from_id)
        if sender_bucket is None:
            sender_bucket = {
                "from_id": clean_from_id,
                "from_label": clean_from_label,
                "count": 0,
                "first_seen_unix": packet_unix,
                "last_seen_unix": packet_unix,
                "last_packet_id": _positive_int(packet_id),
                "last_payload_preview": _preview_payload(payload_text_value),
            }
            senders_by_id[clean_from_id] = sender_bucket
        sender_bucket["count"] = int(sender_bucket.get("count") or 0) + 1
        if isinstance(packet_unix, int) and packet_unix > 0:
            first_sender_seen = _positive_int(sender_bucket.get("first_seen_unix"))
            last_sender_seen = _positive_int(sender_bucket.get("last_seen_unix"))
            if first_sender_seen is None or packet_unix < first_sender_seen:
                sender_bucket["first_seen_unix"] = packet_unix
            if last_sender_seen is None or packet_unix >= last_sender_seen:
                sender_bucket["last_seen_unix"] = packet_unix
                sender_bucket["last_packet_id"] = _positive_int(packet_id)
                sender_bucket["last_payload_preview"] = _preview_payload(payload_text_value)

        if idx < clean_limit:
            entries.append(
                {
                    "id": _positive_int(row_id),
                    "created_unix": _positive_int(created_unix),
                    "packet_row_id": _positive_int(packet_row_id),
                    "from_id": clean_from_id,
                    "from_label": clean_from_label,
                    "portnum": str(portnum or "").strip(),
                    "packet_id": _positive_int(packet_id),
                    "rx_time_unix": _positive_int(rx_time_unix),
                    "payload_text": payload_text_value,
                    "payload_preview": _preview_payload(payload_text_value, 72),
                }
            )

    senders = sorted(
        senders_by_id.values(),
        key=lambda item: (
            -int(item.get("count") or 0),
            -int(_positive_int(item.get("last_seen_unix")) or 0),
            str(item.get("from_label") or ""),
        ),
    )

    return {
        "ok": True,
        "window_hours": clean_hours,
        "limit": clean_limit,
        "node_id": clean_node_id,
        "summary": {
            "total_packets": len(rows),
            "distinct_senders": len(senders),
            "first_seen_unix": first_seen_unix,
            "last_seen_unix": last_seen_unix,
        },
        "senders": senders,
        "entries": entries,
    }
