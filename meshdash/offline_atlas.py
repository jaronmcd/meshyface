from __future__ import annotations

from functools import lru_cache
from math import asin, cos, pi, radians, sin, sqrt
from pathlib import Path
from typing import Any, Optional
import json

_ASSETS_DIR = Path(__file__).with_name("assets")
_OFFLINE_ATLAS_PATH = _ASSETS_DIR / "offline_atlas_na.min.json"
_EARTH_RADIUS_KM = 6371.0
_NEAREST_CITY_TIE_KM = 0.01
# Slack keeps the chord bound conservative against float rounding in haversine.
_NEAREST_CITY_CHORD_SLACK = 1e-9
# Bounded so long uptimes with many distinct positions cannot grow memory without limit.
_NEAREST_CITY_CACHE_SIZE = 8192


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
    earth_radius_km = _EARTH_RADIUS_KM
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
        rank_value = _to_float(props.get("scalerank"))
        rank = rank_value if rank_value is not None else 9.0
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


def _unit_vector(lat: float, lon: float) -> tuple[float, float, float]:
    lat_rad = radians(lat)
    lon_rad = radians(lon)
    cos_lat = cos(lat_rad)
    return cos_lat * cos(lon_rad), cos_lat * sin(lon_rad), sin(lat_rad)


def _chord_for_km(distance_km: float) -> float:
    return 2.0 * sin(min(distance_km / (2.0 * _EARTH_RADIUS_KM), pi / 2.0))


# k-d tree node: (unit vector, city index, split axis, left subtree, right subtree).
_CityTreeNode = tuple[tuple[float, float, float], int, int, Optional["_CityTreeNode"], Optional["_CityTreeNode"]]


@lru_cache(maxsize=1)
def _offline_city_tree() -> Optional[_CityTreeNode]:
    """Index city unit vectors so lookups cost O(log n) wherever the node sits on the globe."""
    points = [
        (_unit_vector(float(city["lat"]), float(city["lon"])), index)
        for index, city in enumerate(_offline_city_rows())
    ]

    def build(items: list[tuple[tuple[float, float, float], int]], depth: int) -> Optional[_CityTreeNode]:
        if not items:
            return None
        axis = depth % 3
        items.sort(key=lambda item: item[0][axis])
        middle = len(items) // 2
        vector, index = items[middle]
        return vector, index, axis, build(items[:middle], depth + 1), build(items[middle + 1 :], depth + 1)

    return build(points, 0)


def _squared_chord(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return dx * dx + dy * dy + dz * dz


def _tree_nearest(node: Optional[_CityTreeNode], query: tuple[float, float, float], best: list[float]) -> None:
    """Update ``best`` = [squared chord, city index] with the closest city under ``node``."""
    if node is None:
        return
    vector, index, axis, left, right = node
    squared = _squared_chord(vector, query)
    if squared < best[0]:
        best[0] = squared
        best[1] = index
    offset = query[axis] - vector[axis]
    near, far = (left, right) if offset < 0.0 else (right, left)
    _tree_nearest(near, query, best)
    if offset * offset < best[0]:
        _tree_nearest(far, query, best)


def _tree_within(
    node: Optional[_CityTreeNode],
    query: tuple[float, float, float],
    squared_radius: float,
    found: list[int],
) -> None:
    if node is None:
        return
    vector, index, axis, left, right = node
    if _squared_chord(vector, query) <= squared_radius:
        found.append(index)
    offset = query[axis] - vector[axis]
    if offset <= 0.0 or offset * offset <= squared_radius:
        _tree_within(left, query, squared_radius, found)
    if offset >= 0.0 or offset * offset <= squared_radius:
        _tree_within(right, query, squared_radius, found)


@lru_cache(maxsize=_NEAREST_CITY_CACHE_SIZE)
def _nearest_city_match(lat_f: float, lon_f: float) -> Optional[tuple[int, float]]:
    cities = _offline_city_rows()
    tree = _offline_city_tree()
    if not cities or tree is None:
        return None

    query = _unit_vector(lat_f, lon_f)
    nearest: list[float] = [float("inf"), -1]
    _tree_nearest(tree, query, nearest)
    nearest_city_row = cities[int(nearest[1])]
    closest_km = _haversine_km(lat_f, lon_f, float(nearest_city_row["lat"]), float(nearest_city_row["lon"]))

    # The tie rule below lets a more populous city win within 0.01 km of the current
    # best, so widen the candidate set until it is closed under that window. Cities
    # outside it can then never displace a candidate, and the linear loop over the
    # candidates in atlas order picks exactly what a scan of every city would.
    distances: dict[int, float] = {}
    limit_km = closest_km + _NEAREST_CITY_TIE_KM
    while True:
        radius = _chord_for_km(limit_km) + _NEAREST_CITY_CHORD_SLACK
        found: list[int] = []
        _tree_within(tree, query, radius * radius, found)
        for index in found:
            if index not in distances:
                city = cities[index]
                distances[index] = _haversine_km(lat_f, lon_f, float(city["lat"]), float(city["lon"]))
        farthest_candidate_km = max(distance for distance in distances.values() if distance < limit_km)
        next_limit_km = farthest_candidate_km + _NEAREST_CITY_TIE_KM
        if next_limit_km <= limit_km:
            break
        limit_km = next_limit_km

    best_index: Optional[int] = None
    best_distance_km: Optional[float] = None
    for index in sorted(index for index, distance in distances.items() if distance < limit_km):
        distance_km = distances[index]
        if best_distance_km is None or distance_km < best_distance_km:
            best_distance_km = distance_km
            best_index = index
            continue
        if best_index is not None and abs(distance_km - best_distance_km) < _NEAREST_CITY_TIE_KM:
            current_pop = _to_float(cities[index].get("population")) or 0.0
            best_pop = _to_float(cities[best_index].get("population")) or 0.0
            if current_pop > best_pop:
                best_index = index
                best_distance_km = distance_km

    if best_index is None or best_distance_km is None:
        return None
    return best_index, best_distance_km


def nearest_city(lat: object, lon: object) -> Optional[dict[str, object]]:
    lat_f = _to_float(lat)
    lon_f = _to_float(lon)
    if lat_f is None or lon_f is None:
        return None
    if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
        return None

    match = _nearest_city_match(lat_f, lon_f)
    if match is None:
        return None
    best = _offline_city_rows()[match[0]]
    best_distance_km = match[1]
    # Build a fresh dict per call: plugin scripts receive it and may mutate it.
    best_rank = _to_float(best.get("rank"))
    return {
        "name": str(best.get("name") or "").strip(),
        "state": str(best.get("state") or "").strip(),
        "country": str(best.get("country") or "").strip(),
        "distance_km": round(float(best_distance_km), 1),
        "population": int(_to_float(best.get("population")) or 0),
        "rank": int(best_rank if best_rank is not None else 9),
    }
