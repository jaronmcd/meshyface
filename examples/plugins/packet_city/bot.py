"""Print accepted packets and their sender's nearest known city."""

from collections.abc import Mapping

from meshdash.bots import Bot


bot = Bot(id="packet_city", name="Packet & City Debug", version="1.0.0")
_SECRET_KEYS = {"adminkey", "password", "pin", "privatekey", "psk", "sessionpasskey"}


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
        return "unknown"
    latitude = position.get("latitude")
    longitude = position.get("longitude")
    if latitude is None or longitude is None:
        return "unknown"
    city = ctx.mesh.nearest_city(latitude, longitude)
    if not city:
        return "unknown"
    name = ", ".join(part for part in (city.get("name"), city.get("state")) if part)
    return f"{name} ({city.get('distance_km')} km)"


@bot.on_packet
def print_packet_and_city(ctx):
    packet = ctx.packet or {}
    ctx.debug("packet&city:", {"city": _sender_city(ctx, packet), "packet": _redact(packet)})
