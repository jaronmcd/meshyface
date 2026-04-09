from .history_time import latest_unix as _latest_unix
from .sql_contracts import SqlConnection


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


def _first_text(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _as_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)  # type: ignore[arg-type]
    except Exception:
        return None
    return number if number > 0 else None


def malformed_text_payload_record(
    summary: dict[str, object] | None,
    packet: dict[str, object] | None,
) -> dict[str, object] | None:
    summary_map = summary if isinstance(summary, dict) else {}
    packet_map = packet if isinstance(packet, dict) else {}
    decoded = packet_map.get("decoded")
    decoded_map = decoded if isinstance(decoded, dict) else {}
    raw_packet = packet_map.get("raw")
    raw_packet_map = raw_packet if isinstance(raw_packet, dict) else {}
    raw_decoded = raw_packet_map.get("decoded")
    raw_decoded_map = raw_decoded if isinstance(raw_decoded, dict) else {}

    portnum = _first_text(
        summary_map.get("portnum"),
        decoded_map.get("portnum"),
        packet_map.get("portnum"),
    ).upper()
    if portnum != "TEXT_MESSAGE_APP":
        return None
    if summary_map.get("is_reaction") is True:
        return None

    decoded_text = _first_text(
        summary_map.get("decoded_text"),
        decoded_map.get("text"),
        raw_decoded_map.get("text"),
        packet_map.get("text"),
    )
    if decoded_text:
        return None

    payload_text = _first_text(
        decoded_map.get("payload"),
        raw_decoded_map.get("payload"),
    )
    if not payload_text:
        return None

    from_id = _canonical_node_id(
        summary_map.get("from")
        or summary_map.get("from_id")
        or packet_map.get("fromId")
        or packet_map.get("from")
    )
    if not from_id:
        return None

    from_label = _first_text(
        summary_map.get("from_long_name"),
        summary_map.get("from_short_name"),
        summary_map.get("from_name"),
        from_id,
    )
    rx_time_unix = int(
        _latest_unix(
            summary_map.get("rx_time_unix"),
            summary_map.get("rx_time"),
            summary_map.get("captured_at_unix"),
            summary_map.get("captured_at"),
            packet_map.get("rxTime"),
            packet_map.get("rx_time"),
            raw_packet_map.get("rx_time"),
        )
        or 0
    )
    packet_id = _as_positive_int(summary_map.get("packet_id") or packet_map.get("id"))
    return {
        "from_id": from_id,
        "from_label": from_label,
        "portnum": portnum,
        "packet_id": packet_id,
        "rx_time_unix": rx_time_unix if rx_time_unix > 0 else None,
        "payload_text": payload_text,
    }


def save_malformed_text_payload(
    conn: SqlConnection,
    *,
    created_unix: int,
    packet_row_id: int,
    summary: dict[str, object] | None,
    packet: dict[str, object] | None,
) -> bool:
    record = malformed_text_payload_record(summary, packet)
    if record is None:
        return False
    conn.execute(
        """
        INSERT INTO malformed_text_payloads(
          created_unix, packet_row_id, from_id, from_label, portnum, packet_id, rx_time_unix, payload_text
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(created_unix),
            int(packet_row_id),
            record["from_id"],
            record["from_label"],
            record["portnum"],
            record["packet_id"],
            record["rx_time_unix"],
            record["payload_text"],
        ),
    )
    return True
