from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional

import pytest

from meshdash import offline_atlas
from meshdash.offline_atlas import load_offline_atlas_payload, nearest_city


ATLAS_PATH = Path(__file__).resolve().parents[1] / "meshdash" / "assets" / "offline_atlas_na.min.json"


def _reference_nearest_city(lat: float, lon: float) -> Optional[dict[str, object]]:
    """The original linear scan over every city, kept as the behavioral oracle."""
    best: Optional[dict[str, object]] = None
    best_distance_km: Optional[float] = None
    for city in offline_atlas._offline_city_rows():
        distance_km = offline_atlas._haversine_km(lat, lon, float(city["lat"]), float(city["lon"]))
        if best_distance_km is None or distance_km < best_distance_km:
            best_distance_km = distance_km
            best = city
            continue
        if abs(distance_km - best_distance_km) < 0.01:
            if float(city["population"]) > float(best["population"]):
                best = city
                best_distance_km = distance_km
    if best is None or best_distance_km is None:
        return None
    return {
        "name": best["name"],
        "state": best["state"],
        "country": best["country"],
        "distance_km": round(float(best_distance_km), 1),
        "population": int(float(best["population"])),
        "rank": int(float(best["rank"])),
    }


def _clear_nearest_city_caches() -> None:
    offline_atlas._offline_city_rows.cache_clear()
    offline_atlas._offline_city_tree.cache_clear()
    offline_atlas._nearest_city_match.cache_clear()


@pytest.fixture
def synthetic_cities(monkeypatch: pytest.MonkeyPatch):
    def install(rows: list[dict[str, object]]) -> None:
        frozen = tuple(rows)
        _clear_nearest_city_caches()
        monkeypatch.setattr(offline_atlas, "_offline_city_rows", lambda: frozen)

    yield install
    monkeypatch.undo()
    _clear_nearest_city_caches()


def _city(name: str, lat: float, lon: float, population: float) -> dict[str, object]:
    return {"name": name, "state": "", "country": "", "lat": lat, "lon": lon, "population": population, "rank": 5.0}


def test_offline_atlas_has_global_basemap_inside_size_budget() -> None:
    payload = json.loads(ATLAS_PATH.read_text(encoding="utf-8"))
    counts = payload.get("counts") or {}

    assert ATLAS_PATH.stat().st_size < 5 * 1024 * 1024
    assert payload.get("bbox") == {"west": -180.0, "south": -90.0, "east": 180.0, "north": 90.0}
    assert counts.get("countries", 0) >= 170
    assert counts.get("coastline", 0) >= 100
    assert counts.get("borders", 0) >= 300
    assert counts.get("cities", 0) >= 4200
    assert counts.get("lakes", 0) >= 130
    assert counts.get("rivers", 0) >= 60


def test_nearest_city_uses_global_offline_city_rows() -> None:
    load_offline_atlas_payload.cache_clear()

    london = nearest_city(51.5072, -0.1276)
    tokyo = nearest_city(35.6762, 139.6503)

    assert london is not None
    assert london["name"] == "London"
    assert london["country"] == "United Kingdom"
    assert london["rank"] == 1
    assert tokyo is not None
    assert tokyo["name"] == "Tokyo"
    assert tokyo["country"] == "Japan"
    assert tokyo["rank"] == 0


def test_nearest_city_index_matches_linear_scan_across_the_globe() -> None:
    _clear_nearest_city_caches()
    cities = offline_atlas._offline_city_rows()
    rng = random.Random(20260916)
    points: list[tuple[float, float]] = [
        (90.0, 0.0),
        (-90.0, 0.0),
        (0.0, 180.0),
        (0.0, -180.0),
        (64.8378, -147.7164),
        (-54.8019, -68.3030),
        (44.9778, -93.2650),
    ]
    points.extend((rng.uniform(-90.0, 90.0), rng.uniform(-180.0, 180.0)) for _ in range(250))
    for city in rng.sample(cities, 250):
        lat, lon = float(city["lat"]), float(city["lon"])
        points.append((lat, lon))
        points.append((max(-90.0, min(90.0, lat + rng.uniform(-0.2, 0.2))), max(-180.0, min(180.0, lon + rng.uniform(-0.2, 0.2)))))

    for lat, lon in points:
        assert nearest_city(lat, lon) == _reference_nearest_city(lat, lon), (lat, lon)


def test_nearest_city_keeps_population_tie_break_and_scan_order(synthetic_cities) -> None:
    # Distances from the origin chain within 0.01 km of each other, so the winner depends on
    # the original atlas order and population rule, not only on the closest distance.
    km_per_deg = 111.19492664455873
    synthetic_cities(
        [
            _city("far-big", 5.0, 0.0, 9_000_000.0),
            _city("chain-c", 0.0, 1.0145 / km_per_deg, 300.0),
            _city("closest", 0.0, 1.0 / km_per_deg, 100.0),
            _city("chain-a", 1.0055 / km_per_deg, 0.0, 200.0),
            _city("chain-b", 0.0, -1.011 / km_per_deg, 250.0),
            _city("outside", 0.0, -1.03 / km_per_deg, 1_000_000.0),
            _city("same-spot-small", 0.0, 1.0 / km_per_deg, 50.0),
        ]
    )

    rng = random.Random(7)
    probes = [(0.0, 0.0)] + [(rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05)) for _ in range(300)]
    for lat, lon in probes:
        assert nearest_city(lat, lon) == _reference_nearest_city(lat, lon), (lat, lon)
    assert nearest_city(0.0, 0.0) == _reference_nearest_city(0.0, 0.0)


def test_nearest_city_scans_a_small_fraction_of_the_atlas(monkeypatch: pytest.MonkeyPatch) -> None:
    # Guard for the live dashboard: state builds and plugins look up every positioned node,
    # so a lookup must not degrade back to a scan of all 4,000+ cities.
    _clear_nearest_city_caches()
    city_count = len(offline_atlas._offline_city_rows())
    offline_atlas._offline_city_tree()
    calls = 0
    haversine = offline_atlas._haversine_km

    def counting_haversine(*args: float) -> float:
        nonlocal calls
        calls += 1
        return haversine(*args)

    monkeypatch.setattr(offline_atlas, "_haversine_km", counting_haversine)
    rng = random.Random(11)
    lookups = [(rng.uniform(25.0, 60.0), rng.uniform(-125.0, -65.0)) for _ in range(500)]
    for lat, lon in lookups:
        assert nearest_city(lat, lon) is not None

    assert calls / len(lookups) < city_count / 10
    for lat, lon in lookups:
        nearest_city(lat, lon)
    assert calls / len(lookups) < city_count / 10, "repeat lookups must be served from the bounded cache"
    _clear_nearest_city_caches()


def test_nearest_city_returns_independent_dicts() -> None:
    first = nearest_city(44.9778, -93.2650)
    assert first is not None
    first["name"] = "mutated by a plugin"
    second = nearest_city(44.9778, -93.2650)
    assert second is not None
    assert second["name"] != "mutated by a plugin"
