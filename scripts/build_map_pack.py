#!/usr/bin/env python3
"""Build a local map expansion pack for Meshyface.

The pack bundles Natural Earth 10m vector layers plus GeoNames cities500
place labels, split into 15-degree grid chunks so the dashboard can load
only the chunks intersecting the current map viewport.

Output layout (inside the pack zip):
    manifest.json
    chunks/<layer>/<cell>.json

Line layers are clipped to cell rectangles (with a small overlap margin) so
each chunk renders independently. Polygon and point layers assign whole
features to the cell containing their bbox center; the client compensates by
fetching one cell of padding around the viewport.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import re
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable, Iterable

from build_offline_atlas import (
    _feature_bbox,
    _parse_dbf,
    _parse_shp,
    _zip_members,
)

PACK_FORMAT = "meshdash-map-pack/1"
PACK_ID = "mymesh"
PACK_LABEL = "My Mesh Detail"
PACK_DESCRIPTION = (
    "Natural Earth 1:10m global vector detail (coastline, borders, states, "
    "rivers, lakes, urban areas, roads, railroads, parks) plus GeoNames "
    "cities500 place labels, built as a local dashboard map expansion."
)
PACK_ATTRIBUTION = "Natural Earth (public domain) | GeoNames.org (CC BY 4.0)"
CELL_DEG = 15.0
CLIP_MARGIN_DEG = 0.05
GRID_COLS = int(360 / CELL_DEG)
GRID_ROWS = int(180 / CELL_DEG)

NATURAL_EARTH_SOURCES = {
    "coastline": (
        "ne_10m_coastline.zip",
        "https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_coastline.zip",
    ),
    "borders": (
        "ne_10m_admin_0_boundary_lines_land.zip",
        "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_0_boundary_lines_land.zip",
    ),
    "states": (
        "ne_10m_admin_1_states_provinces_lines.zip",
        "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_1_states_provinces_lines.zip",
    ),
    "rivers": (
        "ne_10m_rivers_lake_centerlines.zip",
        "https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_rivers_lake_centerlines.zip",
    ),
    "lakes": (
        "ne_10m_lakes.zip",
        "https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_lakes.zip",
    ),
    "urban": (
        "ne_10m_urban_areas.zip",
        "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_urban_areas.zip",
    ),
    "roads": (
        "ne_10m_roads.zip",
        "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_roads.zip",
    ),
    "railroads": (
        "ne_10m_railroads.zip",
        "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_railroads.zip",
    ),
    "places": (
        "ne_10m_populated_places_simple.zip",
        "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_populated_places_simple.zip",
    ),
    "parks": (
        "ne_10m_parks_and_protected_lands.zip",
        "https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_parks_and_protected_lands.zip",
    ),
}
GEONAMES_CITIES_SOURCE = (
    "cities500.zip",
    "https://download.geonames.org/export/dump/cities500.zip",
)
GEONAMES_ADMIN1_SOURCE = (
    "admin1CodesASCII.txt",
    "https://download.geonames.org/export/dump/admin1CodesASCII.txt",
)
GEONAMES_COUNTRY_SOURCE = (
    "countryInfo.txt",
    "https://download.geonames.org/export/dump/countryInfo.txt",
)
GEONAMES_COUNTRY_DUMP_URL = "https://download.geonames.org/export/dump/{cc}.zip"
# GeoNames feature codes treated as peaks (feature class T).
_PEAK_FEATURE_CODES = {"PK", "PKS", "MT"}

# kind: line layers are clipped to cells; polygon/point layers are assigned
# to the cell containing their bbox center.
LAYER_SPECS: dict[str, dict[str, Any]] = {
    "coastline": {"kind": "line", "min_zoom": 4},
    "borders": {"kind": "line", "min_zoom": 4},
    "states": {"kind": "line", "min_zoom": 4},
    "rivers": {"kind": "line", "min_zoom": 5},
    "lakes": {"kind": "polygon", "min_zoom": 5},
    "urban": {"kind": "polygon", "min_zoom": 6},
    "roads": {"kind": "line", "min_zoom": 6},
    "railroads": {"kind": "line", "min_zoom": 7},
    "parks": {"kind": "polygon", "min_zoom": 5},
    "peaks": {"kind": "point", "min_zoom": 6},
    "cities": {"kind": "point", "min_zoom": 4},
}


def _text(record: dict[str, Any], *names: str) -> str:
    for name in names:
        value = str(record.get(name) or "").strip()
        if value:
            return value
    return ""


def _number(record: dict[str, Any], *names: str, fallback: float = 0.0) -> float:
    for name in names:
        value = record.get(name)
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            return number
    return fallback


def _download_sources(source_dir: Path) -> None:
    source_dir.mkdir(parents=True, exist_ok=True)
    downloads = list(NATURAL_EARTH_SOURCES.values()) + [
        GEONAMES_CITIES_SOURCE,
        GEONAMES_ADMIN1_SOURCE,
        GEONAMES_COUNTRY_SOURCE,
    ]
    for filename, url in downloads:
        target = source_dir / filename
        if target.exists() and target.stat().st_size > 0:
            continue
        print(f"Downloading {url}")
        urllib.request.urlretrieve(url, target)


def _source_path(source_dir: Path, filename: str) -> Path:
    path = source_dir / filename
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def _load_source_features(
    source_dir: Path,
    key: str,
    property_builder: Callable[[dict[str, Any]], dict[str, Any] | None],
) -> list[dict[str, Any]]:
    filename, _url = NATURAL_EARTH_SOURCES[key]
    shp_raw, dbf_raw = _zip_members(_source_path(source_dir, filename))
    geometries = _parse_shp(shp_raw)
    records = _parse_dbf(dbf_raw)
    features: list[dict[str, Any]] = []
    for geometry, record in zip(geometries, records):
        props = property_builder(record)
        if props is None:
            continue
        features.append({"type": "Feature", "properties": props, "geometry": geometry})
    return features


def _natural_earth_place_rank(record: dict[str, Any]) -> int:
    population = _number(record, "pop_max", "POP_MAX")
    is_capital = _number(record, "adm0cap", "ADM0CAP") >= 1
    is_world_city = (
        _number(record, "worldcity", "WORLDCITY") >= 1
        or _number(record, "megacity", "MEGACITY") >= 1
    )
    if population >= 15_000_000:
        return 0
    if population >= 6_000_000 or is_world_city:
        return 1
    if population >= 1_000_000 or is_capital:
        return 2
    return 3


def _geonames_place_rank(population: float) -> int:
    if population >= 1_000_000:
        return 2
    if population >= 250_000:
        return 3
    if population >= 100_000:
        return 4
    if population >= 25_000:
        return 5
    if population >= 5_000:
        return 6
    return 7


def _city_dedupe_key(name: str, lon: float, lat: float) -> tuple[str, float, float]:
    return (name.strip().casefold(), round(lon, 2), round(lat, 2))


def _load_geonames_admin1_names(source_dir: Path) -> dict[str, str]:
    names: dict[str, str] = {}
    path = _source_path(source_dir, GEONAMES_ADMIN1_SOURCE[0])
    for line in path.read_text(encoding="utf-8").splitlines():
        columns = line.split("\t")
        if len(columns) < 3:
            continue
        code = columns[0].strip()
        name = (columns[2] or columns[1]).strip()
        if code and name:
            names[code] = name
    return names


def _load_geonames_country_names(source_dir: Path) -> dict[str, str]:
    names: dict[str, str] = {}
    path = _source_path(source_dir, GEONAMES_COUNTRY_SOURCE[0])
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) < 5:
            continue
        iso2 = columns[0].strip().upper()
        name = columns[4].strip()
        if iso2 and name:
            names[iso2] = name
    return names


def _iter_geonames_city_rows(source_dir: Path):
    """Yield (name, ascii_name, lat, lon, country_code, admin1_code, population)."""
    filename, _url = GEONAMES_CITIES_SOURCE
    with zipfile.ZipFile(_source_path(source_dir, filename)) as archive:
        member = next(
            name for name in archive.namelist() if name.lower().endswith(".txt")
        )
        with archive.open(member) as handle:
            for line in io.TextIOWrapper(handle, encoding="utf-8"):
                columns = line.rstrip("\n").split("\t")
                if len(columns) < 15:
                    continue
                try:
                    lat = float(columns[4])
                    lon = float(columns[5])
                except ValueError:
                    continue
                try:
                    population = float(columns[14] or 0)
                except ValueError:
                    population = 0.0
                yield (
                    columns[1].strip(),
                    columns[2].strip(),
                    lat,
                    lon,
                    columns[8].strip().upper(),
                    columns[10].strip(),
                    population,
                )


def _region_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return slug[:48] or "region"


def _bbox_of_points(points: list[tuple[float, float]], pad_deg: float):
    lons = [point[0] for point in points]
    lats = [point[1] for point in points]
    return (
        max(-180.0, min(lons) - pad_deg),
        max(-90.0, min(lats) - pad_deg),
        min(180.0, max(lons) + pad_deg),
        min(90.0, max(lats) + pad_deg),
    )


def resolve_region(source_dir: Path, region: str):
    """Resolve a region name to (slug, label, bbox=(west, south, east, north)).

    Matches, in order: a country name, a state/province name (or its
    GeoNames code like "US.MN"), then a city name (largest population
    wins). Bounding boxes are derived from GeoNames city points, so a
    region's edges beyond its outermost cities rely on the padding.
    """
    def norm(value: str) -> str:
        cleaned = value.strip().casefold()
        return cleaned[4:] if cleaned.startswith("the ") else cleaned

    query = region.strip()
    query_cf = norm(query)
    if not query:
        raise ValueError("region is empty")

    country_names = _load_geonames_country_names(source_dir)
    admin1_names = _load_geonames_admin1_names(source_dir)

    country_code = ""
    for code, name in country_names.items():
        if norm(name) == query_cf or code.casefold() == query_cf:
            country_code = code
            break
    if country_code:
        points = [
            (lon, lat)
            for _n, _a, lat, lon, cc, _a1, _p in _iter_geonames_city_rows(source_dir)
            if cc == country_code
        ]
        if not points:
            raise ValueError(f"no city data for country {country_code}")
        label = country_names[country_code]
        return f"region_{country_code.lower()}", label, _bbox_of_points(points, 1.0)

    admin1_matches = [
        code
        for code, name in admin1_names.items()
        if norm(name) == query_cf or code.casefold() == query_cf
    ]
    if len(admin1_matches) > 1:
        candidates = ", ".join(
            f"{code} ({admin1_names[code]}, "
            f"{country_names.get(code.split('.')[0], code.split('.')[0])})"
            for code in sorted(admin1_matches)
        )
        raise ValueError(
            f"region {query!r} is ambiguous; use one of the codes: {candidates}"
        )
    if admin1_matches:
        code = admin1_matches[0]
        cc, _sep, admin1 = code.partition(".")
        points = [
            (lon, lat)
            for _n, _a, lat, lon, row_cc, row_a1, _p in _iter_geonames_city_rows(source_dir)
            if row_cc == cc and row_a1 == admin1
        ]
        if not points:
            raise ValueError(f"no city data for region {code}")
        label = f"{admin1_names[code]}, {country_names.get(cc, cc)}"
        return (
            f"region_{_region_slug(cc)}_{_region_slug(admin1)}",
            label,
            _bbox_of_points(points, 1.0),
        )

    best = None
    for name, ascii_name, lat, lon, cc, admin1, population in _iter_geonames_city_rows(
        source_dir
    ):
        if norm(name) == query_cf or norm(ascii_name) == query_cf:
            if best is None or population > best[4]:
                best = (name or ascii_name, lat, lon, cc, population, admin1)
    if best is None:
        raise ValueError(
            f"no country, state/province, or city named {query!r} in GeoNames data"
        )
    city_name, lat, lon, cc, _population, admin1 = best
    admin1_label = admin1_names.get(f"{cc}.{admin1}", "")
    context = admin1_label or country_names.get(cc, cc)
    label = f"{city_name}, {context}" if context else city_name
    return (
        f"region_{_region_slug(city_name)}",
        label,
        _bbox_of_points([(lon, lat)], 2.5),
    )


def cells_for_bbox(bbox: tuple[float, float, float, float]) -> set[str]:
    west, south, east, north = bbox
    col_min, row_min = _cell_for_point(west, south)
    col_max, row_max = _cell_for_point(east, north)
    return {
        _cell_id(col, row)
        for col in range(col_min, col_max + 1)
        for row in range(row_min, row_max + 1)
    }


def parse_layer_selection(include_arg: str, exclude_arg: str) -> set[str] | None:
    """Return the selected layer names, or None when all layers are wanted."""
    include = [item.strip() for item in (include_arg or "").split(",") if item.strip()]
    exclude = [item.strip() for item in (exclude_arg or "").split(",") if item.strip()]
    if include and exclude:
        raise ValueError("use --layers or --exclude-layers, not both")
    valid = set(LAYER_SPECS)
    unknown = [name for name in include + exclude if name not in valid]
    if unknown:
        raise ValueError(
            f"unknown layers: {', '.join(unknown)} "
            f"(valid: {', '.join(LAYER_SPECS)})"
        )
    if include:
        return set(include)
    if exclude:
        selected = valid - set(exclude)
        if not selected:
            raise ValueError("cannot exclude every layer")
        return selected
    return None


def parse_country_codes(value: str) -> list[str]:
    codes: list[str] = []
    for item in (value or "").split(","):
        code = item.strip().upper()
        if not code:
            continue
        if not re.fullmatch(r"[A-Z]{2}", code):
            raise ValueError("--peaks-countries expects ISO-2 codes like US,CA")
        if code not in codes:
            codes.append(code)
    return codes


def _haversine_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    rad = math.radians
    d_lat = rad(lat_b - lat_a)
    d_lon = rad(lon_b - lon_a)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(rad(lat_a)) * math.cos(rad(lat_b)) * math.sin(d_lon / 2) ** 2
    )
    return 2 * 6371.0 * math.asin(min(1.0, math.sqrt(a)))


def parse_center(value: str) -> tuple[float, float]:
    parts = [part.strip() for part in str(value or "").split(",")]
    if len(parts) != 2:
        raise ValueError("--center expects LAT,LON (e.g. 44.8,-93.2)")
    try:
        lat = float(parts[0])
        lon = float(parts[1])
    except ValueError as exc:
        raise ValueError("--center expects numeric LAT,LON") from exc
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise ValueError("--center is out of range")
    return lat, lon


def bbox_for_center_radius(
    lat: float, lon: float, radius_km: float
) -> tuple[float, float, float, float]:
    d_lat = radius_km / 111.32
    # Clamp the cosine so polar centers do not explode the longitude span.
    d_lon = radius_km / (111.32 * max(0.2, math.cos(math.radians(lat))))
    return (
        max(-180.0, lon - d_lon),
        max(-90.0, lat - d_lat),
        min(180.0, lon + d_lon),
        min(90.0, lat + d_lat),
    )


def _nearest_city_label(
    source_dir: Path,
    lat: float,
    lon: float,
    min_population: float = 25000,
    nearby_km: float = 30.0,
) -> str:
    """Name the area: the biggest city within nearby_km, else the closest one."""
    best_nearby: tuple[float, str] | None = None
    best_distant: tuple[float, str] | None = None
    try:
        for name, ascii_name, row_lat, row_lon, _cc, _a1, population in (
            _iter_geonames_city_rows(source_dir)
        ):
            if population < min_population:
                continue
            distance = _haversine_km(lat, lon, row_lat, row_lon)
            label = (ascii_name or name).strip()
            if distance <= nearby_km:
                if best_nearby is None or population > best_nearby[0]:
                    best_nearby = (population, label)
            elif best_distant is None or distance < best_distant[0]:
                best_distant = (distance, label)
    except FileNotFoundError:
        return ""
    if best_nearby is not None:
        return best_nearby[1]
    if best_distant is not None:
        return best_distant[1]
    return ""


def resolve_center_region(
    source_dir: Path, lat: float, lon: float, radius_km: float
):
    """Resolve a lat/lon/radius geofence to (slug, label, bbox)."""
    if radius_km <= 0:
        raise ValueError("--radius-km must be positive")
    bbox = bbox_for_center_radius(lat, lon, radius_km)
    radius_text = f"{radius_km:.0f} km"
    city = _nearest_city_label(source_dir, lat, lon)
    if city:
        slug = f"region_{_region_slug(city)}_{int(round(radius_km))}km"
        label = f"{city} area ({radius_text})"
    else:
        lat_slug = _region_slug(f"{abs(lat):.1f}{'n' if lat >= 0 else 's'}")
        lon_slug = _region_slug(f"{abs(lon):.1f}{'e' if lon >= 0 else 'w'}")
        slug = f"region_{lat_slug}_{lon_slug}_{int(round(radius_km))}km"
        label = f"{abs(lat):.2f}{'N' if lat >= 0 else 'S'} "
        label += f"{abs(lon):.2f}{'E' if lon >= 0 else 'W'} ({radius_text})"
    return slug, label, bbox


def _history_position_points(history_db: Path) -> list[tuple[float, float]]:
    import sqlite3

    if not history_db.is_file():
        raise ValueError(f"history database not found: {history_db}")
    connection = sqlite3.connect(f"file:{history_db}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT node_id, lat, lon, MAX(created_unix) FROM node_positions "
            "WHERE lat IS NOT NULL AND lon IS NOT NULL GROUP BY node_id"
        ).fetchall()
    finally:
        connection.close()
    points: list[tuple[float, float]] = []
    for _node_id, lat, lon, _created in rows:
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (TypeError, ValueError):
            continue
        if -90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0:
            points.append((lat_f, lon_f))
    return points


def _count_points_within_radius(
    points: Iterable[tuple[float, float]],
    center_lat: float,
    center_lon: float,
    radius_km: float,
) -> int:
    return sum(
        1
        for lat, lon in points
        if _haversine_km(center_lat, center_lon, lat, lon) <= radius_km
    )


def resolve_history_center(history_db: Path) -> tuple[float, float, float, int, int]:
    """Derive (lat, lon, radius_km, node_count, covered_count) from node history.

    Uses the latest position per node, a median center, and a radius that
    covers 90% of nodes, so a few far-away MQTT-heard nodes do not balloon
    the region.
    """
    points = _history_position_points(history_db)
    if len(points) < 3:
        raise ValueError(
            f"not enough node positions in {history_db} "
            f"(found {len(points)}, need at least 3)"
        )
    lats = sorted(point[0] for point in points)
    lons = sorted(point[1] for point in points)
    center_lat = lats[len(lats) // 2]
    center_lon = lons[len(lons) // 2]
    distances = sorted(
        _haversine_km(center_lat, center_lon, lat, lon) for lat, lon in points
    )
    p90 = distances[int(0.9 * (len(distances) - 1))]
    radius_km = max(10.0, p90 * 1.15)
    covered = _count_points_within_radius(points, center_lat, center_lon, radius_km)
    return center_lat, center_lon, radius_km, len(points), covered


# Rough per-chunk byte averages and land-chunk counts measured from the v1
# global build; used only for --estimate.
_ESTIMATE_LAYER_STATS: dict[str, tuple[int, int]] = {
    "coastline": (39_000, 210),
    "borders": (20_000, 76),
    "states": (69_000, 125),
    "rivers": (45_000, 113),
    "lakes": (33_000, 99),
    "urban": (196_000, 112),
    "roads": (146_000, 124),
    "railroads": (258_000, 107),
    "parks": (15_000, 40),
    "peaks": (60_000, 150),
    "cities": (193_000, 181),
}


def estimate_pack_bytes(
    layers: set[str] | None, keep_cells: set[str] | None
) -> dict[str, int]:
    """Rough per-layer installed-size estimate in bytes."""
    estimates: dict[str, int] = {}
    for layer_name in LAYER_SPECS:
        if layers is not None and layer_name not in layers:
            continue
        avg_bytes, global_chunks = _ESTIMATE_LAYER_STATS.get(layer_name, (100_000, 150))
        chunk_count = (
            global_chunks
            if keep_cells is None
            else min(len(keep_cells), global_chunks)
        )
        estimates[layer_name] = avg_bytes * chunk_count
    return estimates


def _load_parks_features(source_dir: Path) -> list[dict[str, Any]]:
    """Load park/protected-land polygons, selecting the area shapefile
    explicitly because the source zip bundles area/line/point variants."""
    filename, _url = NATURAL_EARTH_SOURCES["parks"]
    with zipfile.ZipFile(_source_path(source_dir, filename)) as archive:
        shp_name = next(
            name for name in archive.namelist()
            if name.lower().endswith("_area.shp")
        )
        dbf_name = next(
            name for name in archive.namelist()
            if name.lower().endswith("_area.dbf")
        )
        shp_raw = archive.read(shp_name)
        dbf_raw = archive.read(dbf_name)
    geometries = _parse_shp(shp_raw)
    records = _parse_dbf(dbf_raw)
    features: list[dict[str, Any]] = []
    for geometry, record in zip(geometries, records):
        features.append({
            "type": "Feature",
            "properties": {
                "name": _text(record, "name", "NAME", "unit_name", "UNIT_NAME"),
                "scalerank": _number(record, "scalerank", "SCALERANK", fallback=9),
            },
            "geometry": geometry,
        })
    return features


def country_codes_for_bbox(
    source_dir: Path, bbox: tuple[float, float, float, float]
) -> list[str]:
    """Country codes with cities500 entries inside the bbox."""
    west, south, east, north = bbox
    codes: set[str] = set()
    for _n, _a, lat, lon, cc, _a1, _p in _iter_geonames_city_rows(source_dir):
        if cc and south <= lat <= north and west <= lon <= east:
            codes.add(cc)
    return sorted(codes)


def _peaks_dump_path(source_dir: Path, country_code: str) -> Path:
    return source_dir / f"geonames_{country_code.upper()}.zip"


def download_peaks_sources(source_dir: Path, country_codes: list[str]) -> None:
    for country_code in country_codes:
        target = _peaks_dump_path(source_dir, country_code)
        if target.exists() and target.stat().st_size > 0:
            continue
        url = GEONAMES_COUNTRY_DUMP_URL.format(cc=country_code.upper())
        print(f"Downloading {url}")
        urllib.request.urlretrieve(url, target)


def _load_peaks_features(
    source_dir: Path, country_codes: list[str]
) -> list[dict[str, Any]]:
    """Load named peaks with elevation from GeoNames per-country dumps."""
    features: list[dict[str, Any]] = []
    seen: set[tuple[str, float, float]] = set()
    for country_code in country_codes:
        path = _peaks_dump_path(source_dir, country_code)
        with zipfile.ZipFile(_source_path(source_dir, path.name)) as archive:
            member = f"{country_code.upper()}.txt"
            with archive.open(member) as handle:
                for line in io.TextIOWrapper(handle, encoding="utf-8"):
                    columns = line.rstrip("\n").split("\t")
                    if len(columns) < 17:
                        continue
                    if columns[6] != "T" or columns[7] not in _PEAK_FEATURE_CODES:
                        continue
                    name = (columns[2] or columns[1]).strip()
                    if not name:
                        continue
                    try:
                        lat = round(float(columns[4]), 4)
                        lon = round(float(columns[5]), 4)
                    except ValueError:
                        continue
                    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                        continue
                    elevation = 0
                    for column in (columns[15], columns[16]):
                        try:
                            elevation = int(float(column))
                            break
                        except (TypeError, ValueError):
                            continue
                    key = _city_dedupe_key(name, lon, lat)
                    if key in seen:
                        continue
                    seen.add(key)
                    props: dict[str, Any] = {"name": name}
                    if elevation > 0:
                        props["elevation"] = elevation
                    features.append(
                        {
                            "type": "Feature",
                            "properties": props,
                            "geometry": {"type": "Point", "coordinates": [lon, lat]},
                        }
                    )
    return features


def _load_city_features(source_dir: Path) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    seen: set[tuple[str, float, float]] = set()

    ne_places = _load_source_features(
        source_dir,
        "places",
        lambda row: {
            "name": _text(row, "nameascii", "name", "NAMEASCII", "NAME"),
            "scalerank": _natural_earth_place_rank(row),
            "population": _number(row, "pop_max", "POP_MAX"),
            "adm0name": _text(row, "adm0name", "ADM0NAME"),
            "adm1name": _text(row, "adm1name", "ADM1NAME"),
        },
    )
    for feature in ne_places:
        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "Point":
            continue
        props = feature["properties"]
        name = str(props.get("name") or "").strip()
        coords = geometry.get("coordinates") or []
        if not name or len(coords) < 2:
            continue
        key = _city_dedupe_key(name, float(coords[0]), float(coords[1]))
        if key in seen:
            continue
        seen.add(key)
        for admin_key in ("adm0name", "adm1name"):
            if not props.get(admin_key):
                props.pop(admin_key, None)
        features.append(feature)

    admin1_names = _load_geonames_admin1_names(source_dir)
    country_names = _load_geonames_country_names(source_dir)

    filename, _url = GEONAMES_CITIES_SOURCE
    with zipfile.ZipFile(_source_path(source_dir, filename)) as archive:
        member = next(
            name for name in archive.namelist() if name.lower().endswith(".txt")
        )
        with archive.open(member) as handle:
            for line in io.TextIOWrapper(handle, encoding="utf-8"):
                columns = line.rstrip("\n").split("\t")
                if len(columns) < 15:
                    continue
                name = (columns[2] or columns[1]).strip()
                if not name:
                    continue
                try:
                    lat = round(float(columns[4]), 4)
                    lon = round(float(columns[5]), 4)
                except ValueError:
                    continue
                if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                    continue
                try:
                    population = float(columns[14] or 0)
                except ValueError:
                    population = 0.0
                key = _city_dedupe_key(name, lon, lat)
                if key in seen:
                    continue
                seen.add(key)
                country_code = columns[8].strip().upper()
                admin1_code = columns[10].strip()
                props: dict[str, Any] = {
                    "name": name,
                    "scalerank": _geonames_place_rank(population),
                    "population": int(population),
                }
                country_name = country_names.get(country_code, "")
                if country_name:
                    props["adm0name"] = country_name
                if country_code and admin1_code:
                    admin1_name = admin1_names.get(
                        f"{country_code}.{admin1_code}", ""
                    )
                    if admin1_name:
                        props["adm1name"] = admin1_name
                features.append(
                    {
                        "type": "Feature",
                        "properties": props,
                        "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    }
                )
    return features


def _cell_id(col: int, row: int) -> str:
    return f"c{col}r{row}"


def _cell_for_point(lon: float, lat: float) -> tuple[int, int]:
    col = min(GRID_COLS - 1, max(0, int((lon + 180.0) // CELL_DEG)))
    row = min(GRID_ROWS - 1, max(0, int((lat + 90.0) // CELL_DEG)))
    return col, row


def _cell_rect(col: int, row: int) -> tuple[float, float, float, float]:
    west = -180.0 + (col * CELL_DEG)
    south = -90.0 + (row * CELL_DEG)
    return west, south, west + CELL_DEG, south + CELL_DEG


def _clip_segment(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    rect: tuple[float, float, float, float],
) -> tuple[float, float, float, float] | None:
    """Liang-Barsky segment clip. Returns the clipped segment or None."""
    west, south, east, north = rect
    dx = bx - ax
    dy = by - ay
    t0, t1 = 0.0, 1.0
    for p, q in (
        (-dx, ax - west),
        (dx, east - ax),
        (-dy, ay - south),
        (dy, north - ay),
    ):
        if p == 0.0:
            if q < 0.0:
                return None
            continue
        t = q / p
        if p < 0.0:
            if t > t1:
                return None
            if t > t0:
                t0 = t
        else:
            if t < t0:
                return None
            if t < t1:
                t1 = t
    return (ax + (t0 * dx), ay + (t0 * dy), ax + (t1 * dx), ay + (t1 * dy))


def _round6(value: float) -> float:
    rounded = round(value, 6)
    return 0.0 if rounded == 0 else rounded


def _clip_line_to_rect(
    points: list[list[float]],
    rect: tuple[float, float, float, float],
) -> list[list[list[float]]]:
    """Clip a polyline to a rectangle, returning continuous runs."""
    runs: list[list[list[float]]] = []
    current: list[list[float]] = []
    for i in range(len(points) - 1):
        ax, ay = float(points[i][0]), float(points[i][1])
        bx, by = float(points[i + 1][0]), float(points[i + 1][1])
        clipped = _clip_segment(ax, ay, bx, by, rect)
        if clipped is None:
            if len(current) >= 2:
                runs.append(current)
            current = []
            continue
        cax, cay, cbx, cby = clipped
        start = [_round6(cax), _round6(cay)]
        end = [_round6(cbx), _round6(cby)]
        if current and current[-1] == start:
            if end != start:
                current.append(end)
        else:
            if len(current) >= 2:
                runs.append(current)
            current = [start, end] if end != start else [start]
    if len(current) >= 2:
        runs.append(current)
    return runs


def _line_parts(geometry: dict[str, Any]) -> list[list[list[float]]]:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if gtype == "LineString":
        return [coords]
    if gtype == "MultiLineString":
        return list(coords)
    return []


def _chunk_line_features(
    features: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    chunks: dict[str, list[dict[str, Any]]] = {}
    for feature in features:
        bbox = _feature_bbox(feature)
        if bbox is None:
            continue
        parts = _line_parts(feature.get("geometry") or {})
        if not parts:
            continue
        col_min, row_min = _cell_for_point(bbox[0], bbox[1])
        col_max, row_max = _cell_for_point(bbox[2], bbox[3])
        props = feature.get("properties") or {}
        for col in range(col_min, col_max + 1):
            for row in range(row_min, row_max + 1):
                west, south, east, north = _cell_rect(col, row)
                rect = (
                    west - CLIP_MARGIN_DEG,
                    south - CLIP_MARGIN_DEG,
                    east + CLIP_MARGIN_DEG,
                    north + CLIP_MARGIN_DEG,
                )
                runs: list[list[list[float]]] = []
                for part in parts:
                    runs.extend(_clip_line_to_rect(part, rect))
                if not runs:
                    continue
                if len(runs) == 1:
                    geometry = {"type": "LineString", "coordinates": runs[0]}
                else:
                    geometry = {"type": "MultiLineString", "coordinates": runs}
                chunks.setdefault(_cell_id(col, row), []).append(
                    {"type": "Feature", "properties": props, "geometry": geometry}
                )
    return chunks


def _chunk_center_features(
    features: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    chunks: dict[str, list[dict[str, Any]]] = {}
    for feature in features:
        bbox = _feature_bbox(feature)
        if bbox is None:
            continue
        center_lon = (bbox[0] + bbox[2]) * 0.5
        center_lat = (bbox[1] + bbox[3]) * 0.5
        col, row = _cell_for_point(center_lon, center_lat)
        chunks.setdefault(_cell_id(col, row), []).append(feature)
    return chunks


def build_layer_features(
    source_dir: Path,
    layer_names: Iterable[str] | None = None,
    *,
    peaks_countries: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    def no_props(_row: dict[str, Any]) -> dict[str, Any]:
        return {}

    def named_ranked(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": _text(row, "name", "NAME"),
            "scalerank": _number(row, "scalerank", "SCALERANK", fallback=9),
        }

    def road_props(row: dict[str, Any]) -> dict[str, Any]:
        if _number(row, "expressway", "EXPRESSWAY") >= 1:
            return {"x": 1}
        return {}

    loaders: dict[str, Callable[[], list[dict[str, Any]]]] = {
        "coastline": lambda: _load_source_features(source_dir, "coastline", no_props),
        "borders": lambda: _load_source_features(source_dir, "borders", no_props),
        "states": lambda: _load_source_features(source_dir, "states", no_props),
        "rivers": lambda: _load_source_features(source_dir, "rivers", named_ranked),
        "lakes": lambda: _load_source_features(source_dir, "lakes", named_ranked),
        "urban": lambda: _load_source_features(source_dir, "urban", no_props),
        "roads": lambda: _load_source_features(source_dir, "roads", road_props),
        "railroads": lambda: _load_source_features(source_dir, "railroads", no_props),
        "parks": lambda: _load_parks_features(source_dir),
        "peaks": lambda: _load_peaks_features(source_dir, peaks_countries or []),
        "cities": lambda: _load_city_features(source_dir),
    }
    selected = set(loaders) if layer_names is None else set(layer_names)
    return {name: loaders[name]() for name in loaders if name in selected}


def build_pack(
    source_dir: Path,
    output_dir: Path,
    version: int,
    *,
    pack_id: str = PACK_ID,
    label: str = PACK_LABEL,
    description: str = PACK_DESCRIPTION,
    keep_cells: set[str] | None = None,
    layers: set[str] | None = None,
    peaks_countries: list[str] | None = None,
) -> dict[str, Any]:
    selected_specs = {
        name: spec
        for name, spec in LAYER_SPECS.items()
        if layers is None or name in layers
    }
    layer_features = build_layer_features(
        source_dir, selected_specs, peaks_countries=peaks_countries
    )
    chunks_root = output_dir / "chunks"
    if chunks_root.exists():
        shutil.rmtree(chunks_root)
    manifest_layers: dict[str, Any] = {}
    counts: dict[str, int] = {}
    total_bytes = 0

    for layer_name, spec in selected_specs.items():
        features = layer_features.get(layer_name, [])
        counts[layer_name] = len(features)
        if spec["kind"] == "line":
            chunk_map = _chunk_line_features(features)
        else:
            chunk_map = _chunk_center_features(features)
        if keep_cells is not None:
            chunk_map = {
                cell_id: cell_features
                for cell_id, cell_features in chunk_map.items()
                if cell_id in keep_cells
            }
            counts[layer_name] = sum(len(f) for f in chunk_map.values())

        layer_dir = chunks_root / layer_name
        layer_dir.mkdir(parents=True, exist_ok=True)
        chunk_entries: dict[str, Any] = {}
        for cell_id in sorted(chunk_map):
            cell_features = chunk_map[cell_id]
            payload = {"type": "FeatureCollection", "features": cell_features}
            encoded = json.dumps(
                payload, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
            chunk_path = layer_dir / f"{cell_id}.json"
            chunk_path.write_bytes(encoded)
            total_bytes += len(encoded)
            chunk_entries[cell_id] = {
                "path": f"chunks/{layer_name}/{cell_id}.json",
                "bytes": len(encoded),
                "sha256": hashlib.sha256(encoded).hexdigest(),
                "features": len(cell_features),
            }
        manifest_layers[layer_name] = {
            "kind": spec["kind"],
            "min_zoom": spec["min_zoom"],
            "chunks": chunk_entries,
        }
        print(
            f"layer {layer_name}: {len(features)} features, "
            f"{len(chunk_entries)} chunks"
        )

    manifest = {
        "format": PACK_FORMAT,
        "id": pack_id,
        "version": int(version),
        "label": label,
        "description": description,
        "attribution": PACK_ATTRIBUTION,
        "cell_deg": CELL_DEG,
        "grid": {"cols": GRID_COLS, "rows": GRID_ROWS},
        "layers": manifest_layers,
        "counts": counts,
        "total_bytes": total_bytes,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return manifest


def write_pack_zip(pack_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.write(pack_dir / "manifest.json", "manifest.json")
        for chunk_path in sorted((pack_dir / "chunks").rglob("*.json")):
            archive.write(chunk_path, chunk_path.relative_to(pack_dir).as_posix())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the offline map expansion pack.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "layers:\n"
            f"  {', '.join(LAYER_SPECS)}\n"
            "\n"
            "examples:\n"
            "  # preview size of a pack geofenced around your mesh (uses node history)\n"
            "  python scripts/build_map_pack.py --source-dir map_sources --download \\\n"
            "    --from-history --estimate\n"
            "\n"
            "  # build that pack\n"
            "  python scripts/build_map_pack.py --source-dir map_sources --download \\\n"
            "    --from-history --zip mymesh.zip\n"
            "\n"
            "  # region by name, selected layers only\n"
            "  python scripts/build_map_pack.py --source-dir map_sources --download \\\n"
            "    --region \"Minnesota\" --layers cities,roads --zip mn.zip\n"
            "\n"
            "  # explicit geofence: center lat,lon + radius\n"
            "  python scripts/build_map_pack.py --source-dir map_sources --download \\\n"
            "    --center 44.8,-93.2 --radius-km 100 --zip area.zip\n"
            "\n"
            "  # remote/rural geofence where peaks country inference is empty\n"
            "  python scripts/build_map_pack.py --source-dir map_sources --download \\\n"
            "    --center 48.7,-113.7 --radius-km 50 --peaks-countries US \\\n"
            "    --zip peaks-area.zip\n"
            "\n"
            "  # install the result (shows size + asks to confirm)\n"
            "  python scripts/install_map_pack.py --zip mymesh.zip\n"
        ),
    )
    parser.add_argument("--source-dir", type=Path, required=True,
                        help="Directory holding (or receiving) source data zips.")
    parser.add_argument("--download", action="store_true",
                        help="Download missing source zips into --source-dir.")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Directory to write the unpacked pack (manifest + chunks); "
                             "default: map_pack_build/<pack id>.")
    parser.add_argument("--zip", type=Path, default=None,
                        help="Also write the distributable pack zip to this path.")
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument("--region", default="",
                        help="Build a regional pack: a country, state/province "
                             "(name or GeoNames code like US.MN), or city name. "
                             "Only grid cells covering the region are included.")
    parser.add_argument("--center", default="",
                        help="Geofence center as LAT,LON (use with --radius-km).")
    parser.add_argument("--radius-km", type=float, default=0.0,
                        help="Geofence radius in km around --center or the "
                             "--from-history center (overrides its derived radius).")
    parser.add_argument("--from-history", action="store_true",
                        help="Geofence around your mesh: derive the region from "
                             "node positions in the dashboard history database.")
    parser.add_argument("--history-db", type=Path, default=None,
                        help="History database path for --from-history "
                             "(default: $MESH_DASH_HISTORY_DB or "
                             "mesh_dashboard_history.sqlite3).")
    parser.add_argument("--layers", default="",
                        help="Comma-separated layers to include "
                             f"(valid: {', '.join(LAYER_SPECS)}).")
    parser.add_argument("--exclude-layers", default="",
                        help="Comma-separated layers to leave out.")
    parser.add_argument("--peaks-countries", default="",
                        help="Comma-separated ISO-2 country codes for the peaks "
                             "layer when bbox inference is empty or too broad; "
                             "use --exclude-layers peaks to omit peaks instead.")
    parser.add_argument("--estimate", action="store_true",
                        help="Print a rough installed-size estimate and exit "
                             "without building.")
    parser.add_argument("--pack-id", default="",
                        help="Pack id override (lowercase letters, digits, underscores).")
    parser.add_argument("--label", default="",
                        help="Pack display label override.")
    args = parser.parse_args()

    geofence_flags = sum(
        1 for flag in (args.region, args.center, args.from_history) if flag
    )
    if geofence_flags > 1:
        print("use only one of --region, --center, or --from-history",
              file=sys.stderr)
        return 2
    if args.center and args.radius_km <= 0:
        print("--center requires a positive --radius-km", file=sys.stderr)
        return 2

    try:
        selected_layers = parse_layer_selection(args.layers, args.exclude_layers)
        peaks_country_override = parse_country_codes(args.peaks_countries)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    if peaks_country_override and selected_layers is not None and "peaks" not in selected_layers:
        print("--peaks-countries requires the peaks layer", file=sys.stderr)
        return 2

    if args.download:
        _download_sources(args.source_dir)

    pack_id = PACK_ID
    label = PACK_LABEL
    description = PACK_DESCRIPTION
    keep_cells: set[str] | None = None
    region_label = ""
    try:
        if args.region:
            region_slug, region_label, bbox = resolve_region(
                args.source_dir, args.region
            )
        elif args.center:
            center_lat, center_lon = parse_center(args.center)
            region_slug, region_label, bbox = resolve_center_region(
                args.source_dir, center_lat, center_lon, args.radius_km
            )
        elif args.from_history:
            history_db = args.history_db or Path(
                os.environ.get("MESH_DASH_HISTORY_DB")
                or "mesh_dashboard_history.sqlite3"
            )
            center_lat, center_lon, derived_radius, node_count, covered = (
                resolve_history_center(history_db)
            )
            radius_km = args.radius_km if args.radius_km > 0 else derived_radius
            if args.radius_km > 0:
                covered = _count_points_within_radius(
                    _history_position_points(history_db),
                    center_lat,
                    center_lon,
                    radius_km,
                )
            print(
                f"history {history_db}: {node_count} nodes with positions, "
                f"center ({center_lat:.4f}, {center_lon:.4f}), "
                f"radius {radius_km:.0f} km covers {covered} nodes"
            )
            region_slug, region_label, bbox = resolve_center_region(
                args.source_dir, center_lat, center_lon, radius_km
            )
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    if region_label:
        keep_cells = cells_for_bbox(bbox)
        pack_id = region_slug
        label = f"{region_label} Detail"
        description = (
            f"Regional Natural Earth 1:10m detail and GeoNames place labels "
            f"covering {region_label}."
        )
        print(
            f"region {region_label}: bbox "
            f"({bbox[0]:.2f}, {bbox[1]:.2f}) to ({bbox[2]:.2f}, {bbox[3]:.2f}), "
            f"{len(keep_cells)} grid cells"
        )

    peaks_countries: list[str] | None = None
    build_layers: set[str] | None = selected_layers
    peaks_selected = selected_layers is None or "peaks" in selected_layers
    if peaks_selected:
        if region_label:
            peaks_countries = peaks_country_override or country_codes_for_bbox(
                args.source_dir, bbox
            )
            print(f"peaks countries: {', '.join(peaks_countries) or 'none'}")
            if not peaks_countries:
                print(
                    "peaks layer could not infer country codes from cities inside "
                    "the geofence; pass --peaks-countries CC,... or "
                    "--exclude-layers peaks",
                    file=sys.stderr,
                )
                return 2
            if peaks_countries and not args.estimate:
                if args.download:
                    download_peaks_sources(args.source_dir, peaks_countries)
                else:
                    missing = [
                        cc for cc in peaks_countries
                        if not _peaks_dump_path(args.source_dir, cc).is_file()
                    ]
                    if missing:
                        print(
                            f"peaks layer needs GeoNames country dumps for: "
                            f"{', '.join(missing)}; rerun with --download",
                            file=sys.stderr,
                        )
                        return 2
        elif selected_layers is not None or peaks_country_override:
            print(
                "peaks layer requires a geofenced build "
                "(--region, --center, or --from-history)",
                file=sys.stderr,
            )
            return 2
        else:
            print("note: skipping peaks layer (requires a geofenced build)")
            build_layers = set(LAYER_SPECS) - {"peaks"}

    if selected_layers is not None:
        layer_list = ", ".join(
            name for name in LAYER_SPECS if name in selected_layers
        )
        description = f"{description} Layers: {layer_list}."
    if args.pack_id:
        pack_id = args.pack_id
    if args.label:
        label = args.label
    if not re.fullmatch(r"[a-z0-9_]{1,64}", pack_id):
        print(f"invalid pack id {pack_id!r}: use lowercase letters, digits, "
              f"underscores (max 64 chars)", file=sys.stderr)
        return 2

    if args.estimate:
        estimates = estimate_pack_bytes(build_layers, keep_cells)
        total = sum(estimates.values())
        print("estimated install size (rough, from global v1 build densities):")
        for layer_name, layer_bytes in estimates.items():
            print(f"  {layer_name:10s} ~{layer_bytes / 1e6:7.1f} MB")
        cell_note = "all land cells" if keep_cells is None else f"{len(keep_cells)} cells"
        print(f"  {'total':10s} ~{total / 1e6:7.1f} MB "
              f"({len(estimates)} layers, {cell_note})")
        return 0

    output_dir = args.output_dir or (Path("map_pack_build") / pack_id)
    print(f"output dir: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_pack(
        args.source_dir,
        output_dir,
        args.version,
        pack_id=pack_id,
        label=label,
        description=description,
        keep_cells=keep_cells,
        layers=build_layers,
        peaks_countries=peaks_countries,
    )
    print(f"pack total: {manifest['total_bytes']} bytes across "
          f"{sum(len(layer['chunks']) for layer in manifest['layers'].values())} chunks")
    if args.zip is not None:
        write_pack_zip(output_dir, args.zip)
        print(f"wrote {args.zip} ({args.zip.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
