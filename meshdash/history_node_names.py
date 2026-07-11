import time
from collections.abc import Iterable

from .helpers import format_epoch as _format_epoch
from .helpers import safe_json_loads as _safe_json_loads
from .helpers import to_int as _to_int
from .history_time import clamp_future_unix as _clamp_future_unix
from .nodes import parse_utc_text_to_unix as _parse_utc_text_to_unix


def _normalize_node_id(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in (
        "^all",
        "all",
        "broadcast",
        "!ffffffff",
        "ffffffff",
        "0xffffffff",
        "4294967295",
    ):
        return "^all"
    if text.startswith("!") and len(text) == 9:
        raw = text[1:]
        if all(ch in "0123456789abcdefABCDEF" for ch in raw):
            return f"!{raw.lower()}"
    if len(text) == 8 and all(ch in "0123456789abcdefABCDEF" for ch in text):
        return f"!{text.lower()}"
    return text


def _clean_name(value: object) -> str:
    return str(value or "").replace("\x00", "").strip()


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _extract_user_candidates(
    packet: dict[str, object],
    decoded: dict[str, object],
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for value in (
        packet.get("user"),
        decoded.get("user"),
        decoded.get("nodeinfo"),
        decoded.get("nodeInfo"),
        decoded.get("payload"),
        decoded.get("admin"),
    ):
        item = _as_dict(value)
        if not item:
            continue
        nested_user = _as_dict(item.get("user"))
        if nested_user:
            candidates.append(nested_user)
        candidates.append(item)
    return candidates


def _preferred_display_name(
    *,
    short_name: object,
    long_name: object,
    fallback: object = "",
) -> str:
    clean_long = _clean_name(long_name)
    if clean_long:
        return clean_long
    clean_short = _clean_name(short_name)
    if clean_short:
        return clean_short
    return _clean_name(fallback)


def _extract_time_unix(
    *values: object,
    now_unix: int,
) -> int | None:
    for value in values:
        unix_value = _to_int(value)
        if unix_value is not None and unix_value > 0:
            clamped = _clamp_future_unix(
                unix_value,
                now_unix=now_unix,
                default_to_now=False,
            )
            if clamped > 0:
                return int(clamped)
            continue
        parsed_unix = _parse_utc_text_to_unix(value)
        if parsed_unix is not None and parsed_unix > 0:
            clamped = _clamp_future_unix(
                parsed_unix,
                now_unix=now_unix,
                default_to_now=False,
            )
            if clamped > 0:
                return int(clamped)
            continue
    return None


def build_name_history_points(
    *,
    node_id: str,
    packet_rows: Iterable[tuple[object, ...]],
) -> list[dict[str, object]]:
    target_node_id = _normalize_node_id(node_id)
    if not target_node_id:
        return []
    now_unix = int(time.time())

    raw_events: list[dict[str, object]] = []
    for order, row in enumerate(packet_rows):
        created_unix = row[0] if len(row) > 0 else None
        summary_json = row[1] if len(row) > 1 else None
        packet_json = row[2] if len(row) > 2 else None

        summary = _as_dict(_safe_json_loads(summary_json, {}))
        packet = _as_dict(_safe_json_loads(packet_json, {}))
        decoded = _as_dict(packet.get("decoded"))
        sender_id = _normalize_node_id(
            summary.get("from")
            or packet.get("fromId")
            or packet.get("from_id")
        )

        for user in _extract_user_candidates(packet, decoded):
            short_name = _clean_name(user.get("shortName") or user.get("short_name"))
            long_name = _clean_name(user.get("longName") or user.get("long_name"))
            if not short_name and not long_name:
                continue

            user_id = _normalize_node_id(user.get("id") or user.get("node_id"))
            if user_id:
                if user_id != target_node_id:
                    continue
            else:
                if sender_id != target_node_id:
                    continue
                user_id = sender_id or target_node_id

            time_unix = _extract_time_unix(
                summary.get("rx_time_unix"),
                packet.get("rxTime"),
                created_unix,
                now_unix=now_unix,
            )
            if time_unix is None or time_unix <= 0:
                continue

            portnum = _clean_name(summary.get("portnum") or decoded.get("portnum"))
            raw_events.append(
                {
                    "_order": order,
                    "node_id": user_id,
                    "time_unix": int(time_unix),
                    "short_name": short_name,
                    "long_name": long_name,
                    "source_portnum": portnum,
                }
            )

    if not raw_events:
        return []

    raw_events.sort(key=lambda item: (int(item["time_unix"]), int(item["_order"])))
    history: list[dict[str, object]] = []
    current_short = ""
    current_long = ""
    for raw in raw_events:
        short_name = _clean_name(raw.get("short_name")) or current_short
        long_name = _clean_name(raw.get("long_name")) or current_long
        if not short_name and not long_name:
            continue
        if short_name == current_short and long_name == current_long:
            continue
        current_short = short_name
        current_long = long_name
        history.append(
            {
                "node_id": raw.get("node_id") or target_node_id,
                "time_unix": int(raw["time_unix"]),
                "time": _format_epoch(raw.get("time_unix")),
                "short_name": short_name,
                "long_name": long_name,
                "source_portnum": _clean_name(raw.get("source_portnum")) or None,
            }
        )
    return history


def build_name_change_chat_entries(
    *,
    recent_packets: Iterable[dict[str, object]],
) -> list[dict[str, object]]:
    raw_events: list[dict[str, object]] = []
    now_unix = int(time.time())
    for order, entry in enumerate(recent_packets):
        if not isinstance(entry, dict):
            continue
        summary = _as_dict(entry.get("summary"))
        packet = _as_dict(entry.get("packet"))
        decoded = _as_dict(packet.get("decoded"))
        sender_id = _normalize_node_id(
            summary.get("from")
            or packet.get("fromId")
            or packet.get("from_id")
        )
        if not sender_id:
            continue

        time_unix = _extract_time_unix(
            summary.get("captured_at"),
            entry.get("captured_at"),
            summary.get("rx_time_unix"),
            packet.get("rxTime"),
            summary.get("rx_time"),
            entry.get("rx_time_unix"),
            entry.get("rx_time"),
            now_unix=now_unix,
        )
        if time_unix is None or time_unix <= 0:
            continue

        portnum = _clean_name(summary.get("portnum") or decoded.get("portnum") or "NODEINFO_APP")
        channel = _to_int(summary.get("channel"))
        if channel is None or channel < 0:
            channel = _to_int(packet.get("channel"))
        if channel is None or channel < 0:
            channel = 0

        for user in _extract_user_candidates(packet, decoded):
            short_name = _clean_name(user.get("shortName") or user.get("short_name"))
            long_name = _clean_name(user.get("longName") or user.get("long_name"))
            if not short_name and not long_name:
                continue

            user_id = _normalize_node_id(user.get("id") or user.get("node_id"))
            if not user_id:
                user_id = sender_id
            if not user_id:
                continue

            raw_events.append(
                {
                    "_order": order,
                    "node_id": user_id,
                    "time_unix": int(time_unix),
                    "short_name": short_name,
                    "long_name": long_name,
                    "portnum": portnum or "NODEINFO_APP",
                    "channel": int(channel),
                }
            )

    if not raw_events:
        return []

    raw_events.sort(key=lambda item: (int(item["time_unix"]), int(item["_order"])))
    current_names_by_node: dict[str, dict[str, str]] = {}
    chat_entries: list[dict[str, object]] = []
    for raw in raw_events:
        node_id = _normalize_node_id(raw.get("node_id"))
        if not node_id:
            continue

        current = current_names_by_node.get(node_id, {"short_name": "", "long_name": ""})
        next_short = _clean_name(raw.get("short_name")) or current["short_name"]
        next_long = _clean_name(raw.get("long_name")) or current["long_name"]
        if next_short == current["short_name"] and next_long == current["long_name"]:
            continue

        previous_display = _preferred_display_name(
            short_name=current["short_name"],
            long_name=current["long_name"],
            fallback="",
        )
        next_display = _preferred_display_name(
            short_name=next_short,
            long_name=next_long,
            fallback="",
        )
        current_names_by_node[node_id] = {
            "short_name": next_short,
            "long_name": next_long,
        }
        if not previous_display or not next_display or previous_display == next_display:
            continue

        rx_time = _format_epoch(raw.get("time_unix"))
        chat_entries.append(
            {
                "captured_at": rx_time,
                "from": node_id,
                "to": "^all",
                "scope": "all",
                "portnum": _clean_name(raw.get("portnum")) or "NODEINFO_APP",
                "channel": int(raw.get("channel") or 0),
                "rx_time": rx_time,
                "rx_time_unix": int(raw["time_unix"]),
                "text": f"{previous_display} changed their name to {next_display}",
                "kind": "status",
                "status_event": "name_change",
                "status_subject": node_id,
                "status_old_name": previous_display,
                "status_new_name": next_display,
            }
        )
    return chat_entries
