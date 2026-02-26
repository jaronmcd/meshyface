from typing import Optional

from .helpers_core import to_float as _to_float
from .helpers_core import to_int as _to_int


def extract_position_fields(position: object) -> Optional[tuple[float, float]]:
    if not isinstance(position, dict):
        return None

    lat = position.get("latitude")
    lon = position.get("longitude")
    if lat is None:
        lat = position.get("lat")
    if lon is None:
        lon = position.get("lon")

    if lat is None and position.get("latitudeI") is not None:
        lat = _to_float(position.get("latitudeI"))
        lat = lat * 1e-7 if lat is not None else None
    if lon is None and position.get("longitudeI") is not None:
        lon = _to_float(position.get("longitudeI"))
        lon = lon * 1e-7 if lon is not None else None

    if lat is None and position.get("latitude_i") is not None:
        lat = _to_float(position.get("latitude_i"))
        lat = lat * 1e-7 if lat is not None else None
    if lon is None and position.get("longitude_i") is not None:
        lon = _to_float(position.get("longitude_i"))
        lon = lon * 1e-7 if lon is not None else None

    lat_f = _to_float(lat)
    lon_f = _to_float(lon)
    if lat_f is None or lon_f is None:
        return None
    if lat_f == 0.0 and lon_f == 0.0:
        return None
    if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
        return None
    return lat_f, lon_f


def extract_packet_position(packet: dict[str, object]) -> Optional[dict[str, object]]:
    if not isinstance(packet, dict):
        return None

    candidates: list[dict[str, object]] = []
    decoded = packet.get("decoded")
    if isinstance(decoded, dict):
        for key in ("position", "gps", "location"):
            candidate = decoded.get(key)
            if isinstance(candidate, dict):
                candidates.append(candidate)
        candidates.append(decoded)

    for key in ("position", "gps", "location"):
        candidate = packet.get(key)
        if isinstance(candidate, dict):
            candidates.append(candidate)
    candidates.append(packet)

    for candidate in candidates:
        coords = extract_position_fields(candidate)
        if coords is None:
            continue

        altitude = _to_float(candidate.get("altitude"))
        if altitude is None:
            altitude = _to_float(candidate.get("altitude_m"))
        if altitude is None:
            altitude = _to_float(candidate.get("altitudeM"))

        sats = _to_int(candidate.get("satsInView"))
        if sats is None:
            sats = _to_int(candidate.get("sats_in_view"))
        if sats is None:
            sats = _to_int(candidate.get("satellites"))

        out: dict[str, object] = {
            "lat": coords[0],
            "lon": coords[1],
        }
        if altitude is not None:
            out["altitude"] = altitude
        if sats is not None and sats >= 0:
            out["sats_in_view"] = sats
        return out
    return None
