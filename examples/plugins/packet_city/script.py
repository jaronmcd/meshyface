"""Print accepted packets and their sender's nearest known city."""

import time
from collections.abc import Mapping

from meshdash.plugins import Script


script = Script(id="packet_city", name="Packet & City Debug", version="1.0.0")
script.ticker("scoreboard", label="Packet City", default_enabled=True)
_SECRET_KEYS = {"adminkey", "password", "pin", "privatekey", "psk", "sessionpasskey"}
_city_counts = {}
_unknown_count = 0
_last_seen_unix = 0


def _redact(value):
    if isinstance(value, Mapping):
        return {
            key: (
                "<redacted>"
                if "".join(char for char in str(key).lower() if char.isalnum())
                in _SECRET_KEYS
                else _redact(child)
            )
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_redact(child) for child in value]
    return value


def _sender_city(ctx, packet):
    position = ctx.mesh.get_node_location(ctx.message.sender_id)
    decoded = packet.get("decoded")
    if position is None and isinstance(decoded, Mapping):
        candidate = decoded.get("position")
        if isinstance(candidate, Mapping):
            position = candidate
    if not isinstance(position, Mapping):
        return None
    latitude = position.get("latitude")
    longitude = position.get("longitude")
    if latitude is None or longitude is None:
        return None
    city = ctx.mesh.nearest_city(latitude, longitude)
    if not city:
        return None
    return city


def _city_label(city):
    if not isinstance(city, Mapping):
        return "unknown"
    name = ", ".join(part for part in (city.get("name"), city.get("state")) if part)
    return f"{name} ({city.get('distance_km')} km)"


def _city_name(city):
    if not isinstance(city, Mapping):
        return None
    return " ".join(str(city.get("name") or "").split()) or None


def _leaders():
    return sorted(_city_counts.items(), key=lambda item: (-item[1], item[0].casefold()))[:3]


def _publish_scoreboard(ctx):
    leaders = _leaders()
    counted = sum(_city_counts.values())
    rows = {f"{rank}. {name}": count for rank, (name, count) in enumerate(leaders, 1)}
    if not rows:
        rows["Leaders"] = "Waiting for city packets"
    rows["Counted"] = counted
    rows["Unknown"] = _unknown_count
    rows["Last seen"] = (
        time.strftime("%H:%M:%S", time.localtime(_last_seen_unix))
        if _last_seen_unix
        else "none"
    )
    leader_value = f"{leaders[0][0]} · {leaders[0][1]}" if leaders else "waiting"
    leader_detail = " · ".join(f"{name} {count}" for name, count in leaders) or "none yet"
    ctx.set_ticker(
        "scoreboard",
        value=leader_value,
        rows=rows,
        state="neutral",
        detail=f"Packet City top 3 · {leader_detail} · {_unknown_count} unknown",
    )


@script.on_start
def start_scoreboard(ctx):
    _publish_scoreboard(ctx)


@script.on_packet
def print_packet_and_city(ctx):
    global _last_seen_unix, _unknown_count

    packet = ctx.packet or {}
    city = _sender_city(ctx, packet)
    city_name = _city_name(city)
    if city_name is None:
        _unknown_count += 1
    else:
        _city_counts[city_name] = _city_counts.get(city_name, 0) + 1
    _last_seen_unix = int(time.time())
    _publish_scoreboard(ctx)
    ctx.debug("packet&city:", {"city": _city_label(city), "packet": _redact(packet)})
