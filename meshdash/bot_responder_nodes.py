from math import asin, cos, radians, sin, sqrt
from typing import Optional

from .helpers import extract_packet_position as _extract_packet_position
from .helpers import extract_position_fields as _extract_position_fields
from .helpers import to_float as _to_float
from .helpers import to_int as _to_int
from .offline_atlas import nearest_city as _nearest_city_for_coords

_BOT_CITY_HINT_MAX_DISTANCE_KM = 120.0
_REQUESTER_POSITION_MAX_AGE_SECONDS = 24 * 3600


def _is_hex_text(value: str) -> bool:
    return bool(value) and all(ch in "0123456789abcdefABCDEF" for ch in value)


def _normalize_node_id(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in ("^all", "all", "broadcast", "!ffffffff", "ffffffff", "0xffffffff", "4294967295"):
        return "^all"
    if text.startswith("!") and len(text) == 9 and _is_hex_text(text[1:]):
        return f"!{text[1:].lower()}"
    if len(text) == 8 and _is_hex_text(text):
        return f"!{text.lower()}"
    return text


def _node_suffix(node_id: object) -> str:
    clean = _normalize_node_id(node_id)
    if not clean.startswith("!") or len(clean) != 9:
        return ""
    return clean[1:][-4:]


def _format_node_id_from_num(raw_num: object) -> str:
    number = _to_int(raw_num)
    if number is None:
        return ""
    if number < 0:
        return ""
    return f"!{number:08x}"


def _resolve_packet_node_id(raw_id: object, raw_num: object, interface: object) -> str:
    clean_id = _normalize_node_id(raw_id)
    if clean_id:
        return clean_id
    number = _to_int(raw_num)
    if number is None:
        return ""
    nodes_by_num = getattr(interface, "nodesByNum", None)
    if isinstance(nodes_by_num, dict):
        info = nodes_by_num.get(number)
        if isinstance(info, dict):
            user = info.get("user")
            if isinstance(user, dict):
                candidate = _normalize_node_id(user.get("id") or user.get("node_id"))
                if candidate:
                    return candidate
    return _format_node_id_from_num(number)


def _nonnegative_hops(value: object) -> Optional[int]:
    hops = _to_int(value)
    if hops is None or hops < 0:
        return None
    return hops


def _hops_from_start_limit(start_value: object, limit_value: object) -> Optional[int]:
    hop_start = _to_int(start_value)
    hop_limit = _to_int(limit_value)
    if hop_start is None or hop_limit is None:
        return None
    diff = hop_start - hop_limit
    if diff < 0:
        return None
    return diff


def _packet_hops_from_mapping(container: object, _seen: Optional[set[int]] = None) -> Optional[int]:
    if not isinstance(container, dict):
        return None
    seen = _seen if isinstance(_seen, set) else set()
    marker = id(container)
    if marker in seen:
        return None
    seen.add(marker)

    for key in (
        "hops",
        "hop_count",
        "hopCount",
        "hopsAway",
        "hops_away",
        "last_hops",
        "lastHops",
    ):
        direct = _nonnegative_hops(container.get(key))
        if direct is not None:
            return direct

    for start_key, limit_key in (
        ("hopStart", "hopLimit"),
        ("hop_start", "hop_limit"),
        ("hopstart", "hoplimit"),
    ):
        derived = _hops_from_start_limit(container.get(start_key), container.get(limit_key))
        if derived is not None:
            return derived

    for nested_key in (
        "routing",
        "route",
        "metadata",
        "meta",
        "rx_metadata",
        "rxMetadata",
        "summary",
        "packet",
        "payload",
        "raw",
    ):
        nested = container.get(nested_key)
        nested_hops = _packet_hops_from_mapping(nested, seen)
        if nested_hops is not None:
            return nested_hops

    return None


def _packet_hops(packet: dict[str, object]) -> Optional[int]:
    hops = _packet_hops_from_mapping(packet)
    if hops is not None:
        return hops
    decoded = packet.get("decoded")
    return _packet_hops_from_mapping(decoded)


def _node_hops_away(node: Optional[dict[str, object]]) -> Optional[int]:
    if not isinstance(node, dict):
        return None
    for key in ("hops_away", "hopsAway", "hops", "last_hops", "lastHops"):
        hops = _nonnegative_hops(node.get(key))
        if hops is not None:
            return hops
    return None


def _effective_hops(packet: dict[str, object], from_id: str, nodes: list[dict[str, object]]) -> Optional[int]:
    direct = _packet_hops(packet)
    if direct is not None:
        return direct
    requester = _find_node_for_query(from_id, nodes)
    return _node_hops_away(requester)


def _normalize_unix_seconds(value: object) -> Optional[int]:
    parsed = _to_int(value)
    if parsed is None or parsed <= 0:
        return None
    if parsed > 10**12:
        parsed = parsed // 1000
    if parsed <= 0:
        return None
    return parsed


def _position_timestamp_unix(position: object) -> Optional[int]:
    if not isinstance(position, dict):
        return None
    for key in (
        "time",
        "timestamp",
        "timeSec",
        "time_sec",
        "unix",
        "lastUpdated",
        "last_updated",
        "lastFixTime",
        "last_fix_time",
    ):
        parsed = _normalize_unix_seconds(position.get(key))
        if parsed is not None:
            return parsed
    return None


def _packet_text(decoded: object) -> str:
    if not isinstance(decoded, dict):
        return ""
    raw = decoded.get("text")
    if not isinstance(raw, str):
        return ""
    return raw.strip()


def _is_text_message_packet(packet: dict[str, object]) -> bool:
    decoded = packet.get("decoded")
    if not isinstance(decoded, dict):
        return False
    text = decoded.get("text")
    if isinstance(text, str) and text.strip():
        return True
    portnum = str(decoded.get("portnum") or "").strip().upper()
    return "TEXT_MESSAGE_APP" in portnum


def _iter_known_nodes(interface: object) -> list[dict[str, object]]:
    nodes_by_num = getattr(interface, "nodesByNum", None)
    if not isinstance(nodes_by_num, dict):
        return []
    rows: list[dict[str, object]] = []
    for raw_num, info in nodes_by_num.items():
        if not isinstance(info, dict):
            continue
        user = info.get("user")
        if not isinstance(user, dict):
            continue
        node_id = _normalize_node_id(user.get("id") or user.get("node_id"))
        if not node_id:
            node_id = _format_node_id_from_num(raw_num)
        if not node_id.startswith("!"):
            continue
        short_name = str(user.get("shortName") or user.get("short_name") or "").strip()
        long_name = str(user.get("longName") or user.get("long_name") or "").strip()
        last_heard = _to_int(info.get("lastHeard") or info.get("last_heard"))
        hops_away = _node_hops_away(info)
        lat = None
        lon = None
        position = info.get("position")
        coords = _extract_position_fields(position)
        position_unix = _position_timestamp_unix(position)
        if coords is not None:
            lat, lon = coords
        rows.append(
            {
                "id": node_id,
                "short_name": short_name,
                "long_name": long_name,
                "last_heard": last_heard,
                "hops_away": hops_away,
                "lat": lat,
                "lon": lon,
                "position_unix": position_unix,
            }
        )
    return rows


def _node_age_label(last_heard: object, now_unix: int) -> str:
    heard = _to_int(last_heard)
    if heard is None or heard <= 0:
        return "n/a"
    delta = max(0, now_unix - heard)
    if delta < 60:
        return f"{delta}s"
    if delta < 3600:
        return f"{delta // 60}m"
    if delta < 86400:
        return f"{delta // 3600}h"
    return f"{delta // 86400}d"


def _format_latency_label(latency_ms: int) -> str:
    value = max(0, int(latency_ms))
    if value < 1000:
        return f"{value}ms"
    if value < 10000:
        return f"{value / 1000:.1f}s"
    total_seconds = value // 1000
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts[:3])


def _format_hop_count_label(hops: Optional[int]) -> str:
    if hops is None:
        return "hop count n/a"
    if hops == 1:
        return "1 hop"
    return f"{hops} hops"


def _format_distance_mi_label(distance_km: object) -> str:
    value_km = _to_float(distance_km)
    if value_km is None or value_km < 0:
        return ""
    value_mi = value_km * 0.621371
    if value_mi < 1.0:
        return "<1mi"
    if value_mi < 10.0:
        return f"{value_mi:.1f}mi"
    return f"{int(round(value_mi))}mi"


def _format_signal_rssi_label(value: object) -> str:
    parsed = _to_float(value)
    if parsed is None:
        return ""
    return f"{int(round(parsed))}dBm"


def _format_signal_snr_label(value: object) -> str:
    parsed = _to_float(value)
    if parsed is None:
        return ""
    return f"{parsed:.1f}dB"


def _packet_link_signal_hint(packet: dict[str, object]) -> str:
    rx_rssi = _to_float(packet.get("rxRssi"))
    if rx_rssi is None:
        rx_rssi = _to_float(packet.get("rx_rssi"))
    rx_snr = _to_float(packet.get("rxSnr"))
    if rx_snr is None:
        rx_snr = _to_float(packet.get("rx_snr"))

    parts: list[str] = []
    rssi_label = _format_signal_rssi_label(rx_rssi)
    if rssi_label:
        parts.append(rssi_label)
    snr_label = _format_signal_snr_label(rx_snr)
    if snr_label:
        parts.append(snr_label)
    if not parts:
        return ""
    return f"link {' / '.join(parts)} (last-hop)"


def _nearest_city_hint_from_coords(lat: object, lon: object, *, max_distance_km: float) -> str:
    lat_f = _to_float(lat)
    lon_f = _to_float(lon)
    if lat_f is None or lon_f is None:
        return ""
    city = _nearest_city_for_coords(lat_f, lon_f)
    if not isinstance(city, dict):
        return ""
    distance_value = _to_float(city.get("distance_km"))
    if distance_value is None or distance_value < 0:
        return ""
    if distance_value > float(max_distance_km):
        return ""
    city_name = str(city.get("name") or "").strip()
    state_name = str(city.get("state") or "").strip()
    country_name = str(city.get("country") or "").strip()
    if not city_name:
        return ""
    place_parts = [city_name]
    if state_name:
        place_parts.append(state_name)
    elif country_name:
        place_parts.append(country_name)
    return ", ".join(place_parts)


def _node_coords(node: Optional[dict[str, object]]) -> Optional[tuple[float, float]]:
    if not isinstance(node, dict):
        return None
    lat = _to_float(node.get("lat"))
    lon = _to_float(node.get("lon"))
    if lat is None or lon is None:
        return None
    if lat == 0.0 and lon == 0.0:
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    return lat, lon


def _node_position_is_recent(node: Optional[dict[str, object]], *, now_unix: int) -> bool:
    if not isinstance(node, dict):
        return False
    position_unix = _normalize_unix_seconds(node.get("position_unix"))
    if position_unix is None:
        return False
    if position_unix > (now_unix + 3600):
        return False
    if (now_unix - position_unix) > _REQUESTER_POSITION_MAX_AGE_SECONDS:
        return False
    return True


def _requester_coords(
    *,
    packet: dict[str, object],
    node: Optional[dict[str, object]],
    now_unix: int,
) -> Optional[tuple[float, float]]:
    packet_pos = _extract_packet_position(packet)
    if isinstance(packet_pos, dict):
        packet_coords = _node_coords(packet_pos)
        if packet_coords is not None:
            return packet_coords
    if not _node_position_is_recent(node, now_unix=now_unix):
        return None
    return _node_coords(node)


def _haversine_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    earth_radius_km = 6371.0
    lat_a_rad = radians(lat_a)
    lon_a_rad = radians(lon_a)
    lat_b_rad = radians(lat_b)
    lon_b_rad = radians(lon_b)
    d_lat = lat_b_rad - lat_a_rad
    d_lon = lon_b_rad - lon_a_rad
    hav = sin(d_lat / 2.0) ** 2 + cos(lat_a_rad) * cos(lat_b_rad) * sin(d_lon / 2.0) ** 2
    return 2.0 * earth_radius_km * asin(sqrt(max(0.0, hav)))


def _bot_city_hint(local_node: Optional[dict[str, object]]) -> str:
    local_coords = _node_coords(local_node)
    if local_coords is None:
        return ""
    return _nearest_city_hint_from_coords(
        local_coords[0],
        local_coords[1],
        max_distance_km=_BOT_CITY_HINT_MAX_DISTANCE_KM,
    )


def _bot_to_requester_distance_hint(
    *,
    packet: dict[str, object],
    requester_node: Optional[dict[str, object]],
    local_node: Optional[dict[str, object]],
    now_unix: int,
) -> str:
    local_coords = _node_coords(local_node)
    if local_coords is None:
        return ""
    requester_coords = _requester_coords(packet=packet, node=requester_node, now_unix=now_unix)
    if requester_coords is None:
        return ""
    distance_km = _haversine_km(
        local_coords[0],
        local_coords[1],
        requester_coords[0],
        requester_coords[1],
    )
    return _format_distance_mi_label(distance_km)


def _format_short_node_label(node: dict[str, object], now_unix: int) -> str:
    node_id = str(node.get("id") or "").strip() or "unknown"
    short_name = str(node.get("short_name") or "").strip()
    long_name = str(node.get("long_name") or "").strip()
    hops = _to_int(node.get("hops_away"))
    age = _node_age_label(node.get("last_heard"), now_unix)
    id_tail = _node_suffix(node_id) or node_id
    name_text = long_name or short_name or id_tail
    if len(name_text) > 18:
        name_text = f"{name_text[:18].rstrip()}..."
    if hops is None:
        return f"{id_tail}:{name_text}/{age}"
    return f"{id_tail}:{name_text}/{hops}h/{age}"


def _preferred_node_label(node: dict[str, object]) -> str:
    node_id = str(node.get("id") or "").strip() or "unknown"
    short_name = str(node.get("short_name") or "").strip()
    long_name = str(node.get("long_name") or "").strip()
    return long_name or short_name or _node_suffix(node_id) or node_id


def _find_node_for_query(query: str, nodes: list[dict[str, object]]) -> Optional[dict[str, object]]:
    raw = str(query or "").strip().lower()
    if not raw:
        return None
    normalized = _normalize_node_id(raw)
    if normalized.startswith("!"):
        for node in nodes:
            node_id = str(node.get("id") or "").strip().lower()
            if node_id == normalized:
                return node

    token = raw.lstrip("!")
    best_score = -1
    best_row: Optional[dict[str, object]] = None
    for node in nodes:
        node_id = str(node.get("id") or "").strip().lower()
        if not node_id.startswith("!"):
            continue
        short_name = str(node.get("short_name") or "").strip().lower()
        long_name = str(node.get("long_name") or "").strip().lower()
        score = -1
        if token and _is_hex_text(token):
            if node_id[1:] == token:
                score = 400
            elif node_id[1:].endswith(token):
                score = 300 + min(len(token), 8)
        if short_name and token and short_name == token:
            score = max(score, 240)
        if long_name and token and long_name == token:
            score = max(score, 240)
        if token and long_name and token in long_name:
            score = max(score, 180)
        if token and short_name and token in short_name:
            score = max(score, 170)
        if score > best_score:
            best_score = score
            best_row = node
        elif score >= 0 and score == best_score and best_row is not None:
            prev_heard = _to_int(best_row.get("last_heard")) or 0
            next_heard = _to_int(node.get("last_heard")) or 0
            if next_heard > prev_heard:
                best_row = node
    return best_row if best_score >= 0 else None
