from __future__ import annotations

from functools import lru_cache
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any, Optional
import json

_ASSETS_DIR = Path(__file__).with_name("assets")
_OFFLINE_ATLAS_PATH = _ASSETS_DIR / "offline_atlas_na.min.json"


@lru_cache(maxsize=1)
def load_offline_atlas_payload() -> dict[str, Any]:
    try:
        text = _OFFLINE_ATLAS_PATH.read_text(encoding="utf-8")
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except Exception as exc:
        return {
            "ok": False,
            "error": f"offline atlas unavailable: {exc}",
            "layers": {},
            "counts": {},
        }
    return {
        "ok": False,
        "error": "offline atlas payload invalid",
        "layers": {},
        "counts": {},
    }


def _to_float(value: object) -> Optional[float]:
    try:
        parsed = float(value)
    except Exception:
        return None
    if parsed != parsed:  # NaN guard
        return None
    return parsed


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


@lru_cache(maxsize=1)
def _offline_city_rows() -> tuple[dict[str, object], ...]:
    payload = load_offline_atlas_payload()
    if not isinstance(payload, dict):
        return ()
    layers = payload.get("layers")
    if not isinstance(layers, dict):
        return ()
    cities = layers.get("cities")
    if not isinstance(cities, dict):
        return ()
    features = cities.get("features")
    if not isinstance(features, list):
        return ()

    rows: list[dict[str, object]] = []
    for feature in features:
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties")
        if not isinstance(props, dict):
            props = {}
        geom = feature.get("geometry")
        if not isinstance(geom, dict):
            continue
        coords = geom.get("coordinates")
        if not isinstance(coords, (list, tuple)) or len(coords) < 2:
            continue
        lon = _to_float(coords[0])
        lat = _to_float(coords[1])
        if lat is None or lon is None:
            continue
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            continue
        name = str(props.get("name") or "").strip()
        if not name:
            continue
        state = str(props.get("adm1name") or "").strip()
        country = str(props.get("adm0name") or "").strip()
        population = _to_float(props.get("population")) or 0.0
        rank = _to_float(props.get("scalerank")) or 9.0
        rows.append(
            {
                "name": name,
                "state": state,
                "country": country,
                "lat": lat,
                "lon": lon,
                "population": population,
                "rank": rank,
            }
        )
    return tuple(rows)


def nearest_city(lat: object, lon: object) -> Optional[dict[str, object]]:
    lat_f = _to_float(lat)
    lon_f = _to_float(lon)
    if lat_f is None or lon_f is None:
        return None
    if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
        return None

    cities = _offline_city_rows()
    if not cities:
        return None

    best: Optional[dict[str, object]] = None
    best_distance_km: Optional[float] = None
    for city in cities:
        city_lat = _to_float(city.get("lat"))
        city_lon = _to_float(city.get("lon"))
        if city_lat is None or city_lon is None:
            continue
        distance_km = _haversine_km(lat_f, lon_f, city_lat, city_lon)
        if best_distance_km is None or distance_km < best_distance_km:
            best_distance_km = distance_km
            best = city
            continue
        if best_distance_km is not None and abs(distance_km - best_distance_km) < 0.01:
            current_pop = _to_float(city.get("population")) or 0.0
            best_pop = _to_float(best.get("population")) or 0.0
            if current_pop > best_pop:
                best = city
                best_distance_km = distance_km

    if best is None or best_distance_km is None:
        return None
    return {
        "name": str(best.get("name") or "").strip(),
        "state": str(best.get("state") or "").strip(),
        "country": str(best.get("country") or "").strip(),
        "distance_km": round(float(best_distance_km), 1),
        "population": int(_to_float(best.get("population")) or 0),
        "rank": int(_to_float(best.get("rank")) or 9),
    }
