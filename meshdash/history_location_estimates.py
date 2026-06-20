import math
import time
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Optional

from .helpers import to_float as _to_float, to_int as _to_int
from .history_store_runtime_contracts import HistoryStoreReadState
from .offline_atlas import nearest_city as _nearest_city
from .sql_contracts import SqlConnection


_DEFAULT_LIMIT = 600
_MAX_LIMIT = 3000
_MIN_ANCHORS = 3
_MIN_SIGNAL_SAMPLES = 3
_MIN_CONFIDENCE = 0.42
_MIN_FIT = 0.36
_MAX_ANCHORS = 10
_MAX_CITY_DISTANCE_KM = 120.0
_WINDOW_SECONDS = {
    "6h": 6 * 60 * 60,
    "12h": 12 * 60 * 60,
    "24h": 24 * 60 * 60,
    "72h": 72 * 60 * 60,
    "7d": 7 * 24 * 60 * 60,
    "14d": 14 * 24 * 60 * 60,
    "30d": 30 * 24 * 60 * 60,
    "max": 0,
}


def _clamp(value: object, lower: float, upper: float) -> float:
    parsed = _to_float(value)
    if parsed is None:
        return lower
    return max(lower, min(upper, parsed))


def _normalize_window(raw_window: object) -> str:
    clean = str(raw_window or "").strip().lower().replace(" ", "")
    aliases = {
        "": "72h",
        "history": "72h",
        "3d": "72h",
        "week": "7d",
        "1w": "7d",
        "all": "max",
        "full": "max",
        "forever": "max",
    }
    clean = aliases.get(clean, clean)
    return clean if clean in _WINDOW_SECONDS else "72h"


def _clean_limit(raw_limit: object) -> int:
    parsed = _to_int(raw_limit)
    if parsed is None:
        parsed = _DEFAULT_LIMIT
    return max(1, min(_MAX_LIMIT, int(parsed)))


def _is_valid_coord(lat: object, lon: object) -> bool:
    lat_f = _to_float(lat)
    lon_f = _to_float(lon)
    return bool(
        lat_f is not None
        and lon_f is not None
        and -90.0 <= lat_f <= 90.0
        and -180.0 <= lon_f <= 180.0
        and not (lat_f == 0.0 and lon_f == 0.0)
    )


def _project_point(lat: float, lon: float, ref_lat: float, ref_lon: float) -> tuple[float, float]:
    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = max(1.0, math.cos(math.radians(ref_lat or 0.0)) * meters_per_deg_lat)
    return ((lon - ref_lon) * meters_per_deg_lon, (lat - ref_lat) * meters_per_deg_lat)


def _unproject_point(x: float, y: float, ref_lat: float, ref_lon: float) -> tuple[float, float]:
    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = max(1.0, math.cos(math.radians(ref_lat or 0.0)) * meters_per_deg_lat)
    return (ref_lat + (y / meters_per_deg_lat), ref_lon + (x / meters_per_deg_lon))


def _recency_score(last_seen_unix: object, now_unix: int) -> float:
    ts = _to_int(last_seen_unix)
    if ts is None or ts <= 0:
        return 0.72
    age_seconds = max(0, int(now_unix) - ts)
    if age_seconds <= 20 * 60:
        return 1.0
    if age_seconds >= 48 * 60 * 60:
        return 0.14
    span = (48 * 60 * 60) - (20 * 60)
    return _clamp(1 - ((age_seconds - (20 * 60)) / span), 0.14, 1.0)


def _edge_hop_metric(edge: Mapping[str, object]) -> float:
    avg_hops = _to_float(edge.get("avg_hops"))
    if avg_hops is not None:
        return avg_hops
    last_hops = _to_float(edge.get("last_hops"))
    if last_hops is not None:
        return last_hops
    return 1.0


def _edge_signal_score(edge: Mapping[str, object], *, now_unix: int) -> float:
    metrics: list[tuple[float, float]] = []
    avg_snr = _to_float(edge.get("avg_snr"))
    if avg_snr is not None:
        metrics.append((_clamp((avg_snr + 18) / 30, 0.0, 1.0), 0.42))
    avg_rssi = _to_float(edge.get("avg_rssi"))
    if avg_rssi is not None:
        metrics.append((_clamp((avg_rssi + 126) / 40, 0.0, 1.0), 0.28))
    hop_metric = _edge_hop_metric(edge)
    metrics.append((1 - _clamp((max(0.0, hop_metric) - 1) / 5, 0.0, 1.0), 0.18))
    count_metric = math.log10(max(1.0, _to_float(edge.get("count")) or 0.0) + 1)
    metrics.append((_clamp(count_metric / 2.5, 0.08, 1.0), 0.12))
    weighted = sum(value * weight for value, weight in metrics)
    total_weight = sum(weight for _value, weight in metrics)
    base_score = weighted / total_weight if total_weight > 0 else 0.42
    recency = _recency_score(edge.get("last_rx_unix"), now_unix)
    return _clamp((base_score * 0.84) + (recency * 0.16), 0.08, 0.98)


def _signal_sample_count(edge: Mapping[str, object]) -> int:
    return max(
        0,
        _to_int(edge.get("rssi_samples")) or 0,
        _to_int(edge.get("snr_samples")) or 0,
    )


def _range_from_signal(edge: Mapping[str, object]) -> Optional[dict[str, float]]:
    ranges: list[tuple[float, float]] = []
    samples = _signal_sample_count(edge)
    sample_damping = _clamp(math.log10(samples + 1) / 1.1, 0.35, 1.0)
    avg_rssi = _to_float(edge.get("avg_rssi"))
    if avg_rssi is not None:
        rssi_meters = 1000 * math.pow(10, ((-97 - avg_rssi) / (10 * 2.4)))
        ranges.append((_clamp(rssi_meters, 120.0, 65_000.0), 0.66 * sample_damping))
    avg_snr = _to_float(edge.get("avg_snr"))
    if avg_snr is not None:
        snr_meters = 900 * math.pow(2, ((10 - avg_snr) / 5))
        ranges.append((_clamp(snr_meters, 160.0, 70_000.0), 0.34 * sample_damping))
    if not ranges:
        return None
    log_total = 0.0
    total_weight = 0.0
    for value, weight in ranges:
        if weight <= 0:
            continue
        log_total += math.log(max(1.0, value)) * weight
        total_weight += weight
    if total_weight <= 0:
        return None
    meters = math.exp(log_total / total_weight)
    agreement = 0.68
    if len(ranges) >= 2:
        ratio = max(ranges[0][0], ranges[1][0]) / max(1.0, min(ranges[0][0], ranges[1][0]))
        agreement = _clamp(1 - (math.log(ratio) / math.log(10)), 0.28, 1.0)
    return {
        "meters": meters,
        "confidence": _clamp(agreement * sample_damping, 0.18, 1.0),
        "samples": float(samples),
    }


def _edge_location_weight(edge: Mapping[str, object], *, now_unix: int) -> float:
    signal_score = _edge_signal_score(edge, now_unix=now_unix)
    hop_overage = max(0.0, _edge_hop_metric(edge) - 1)
    hop_damping = 1.0 if hop_overage <= 0 else _clamp(1 / (1 + (hop_overage * 1.45)), 0.14, 1.0)
    sample_weight = max(1.0, _to_float(edge.get("count")) or 0.0)
    sample_damping = _clamp(math.log10(sample_weight + 1) / 2.2, 0.55, 1.0)
    return _clamp(signal_score * hop_damping * sample_damping, 0.04, 0.98)


def _fetch_latest_position_rows(conn: SqlConnection) -> list[tuple[object, ...]]:
    return conn.execute(
        """
        SELECT p.node_id, p.created_unix, p.lat, p.lon
        FROM node_positions AS p
        JOIN (
          SELECT node_id, MAX(created_unix) AS created_unix
          FROM node_positions
          GROUP BY node_id
        ) AS latest
          ON latest.node_id = p.node_id AND latest.created_unix = p.created_unix
        ORDER BY p.node_id ASC, p.id DESC
        """
    ).fetchall()


def _fetch_link_metric_rows(
    conn: SqlConnection,
    *,
    cutoff_unix: int,
    limit: int,
) -> list[tuple[object, ...]]:
    return conn.execute(
        """
        SELECT from_id,
               to_id,
               MIN(bucket_unix) AS first_seen_unix,
               MAX(last_seen_unix) AS last_seen_unix,
               COALESCE(SUM(packet_count), 0) AS packet_count,
               COALESCE(SUM(snr_sum), 0.0) AS snr_sum,
               COALESCE(SUM(snr_count), 0) AS snr_count,
               COALESCE(SUM(rssi_sum), 0.0) AS rssi_sum,
               COALESCE(SUM(rssi_count), 0) AS rssi_count,
               COALESCE(SUM(hops_sum), 0) AS hops_sum,
               COALESCE(SUM(hops_count), 0) AS hops_count,
               MAX(CASE WHEN hops_count > 0 THEN hops_max END) AS hops_max
        FROM link_metrics_1m
        WHERE (? <= 0 OR last_seen_unix >= ?)
          AND trim(COALESCE(from_id, '')) <> ''
          AND trim(COALESCE(to_id, '')) <> ''
          AND trim(COALESCE(from_id, '')) NOT IN ('Unknown', 'n/a', '^all')
          AND trim(COALESCE(to_id, '')) NOT IN ('Unknown', 'n/a', '^all')
          AND from_id <> to_id
        GROUP BY from_id, to_id
        HAVING SUM(packet_count) > 0
        ORDER BY packet_count DESC, last_seen_unix DESC, from_id ASC, to_id ASC
        LIMIT ?
        """,
        (int(cutoff_unix), int(cutoff_unix), max(1, int(limit))),
    ).fetchall()


def _decode_position_rows(rows: Iterable[tuple[object, ...]]) -> dict[str, dict[str, object]]:
    positions: dict[str, dict[str, object]] = {}
    for node_id, created_unix, lat, lon, *_rest in rows:
        clean_id = str(node_id or "").strip()
        lat_f = _to_float(lat)
        lon_f = _to_float(lon)
        if not clean_id or lat_f is None or lon_f is None or not _is_valid_coord(lat_f, lon_f):
            continue
        if clean_id in positions:
            continue
        positions[clean_id] = {
            "node_id": clean_id,
            "lat": lat_f,
            "lon": lon_f,
            "created_unix": _to_int(created_unix),
        }
    return positions


def _decode_link_rows(rows: Iterable[tuple[object, ...]]) -> list[dict[str, object]]:
    edges: list[dict[str, object]] = []
    for row in rows:
        if len(row) < 12:
            continue
        (
            from_id,
            to_id,
            first_seen_unix,
            last_seen_unix,
            packet_count,
            snr_sum,
            snr_count,
            rssi_sum,
            rssi_count,
            hops_sum,
            hops_count,
            hops_max,
        ) = row[:12]
        count = max(0, _to_int(packet_count) or 0)
        if count <= 0:
            continue
        from_clean = str(from_id or "").strip()
        to_clean = str(to_id or "").strip()
        if not from_clean or not to_clean or from_clean == to_clean:
            continue
        snr_samples = _to_int(snr_count) or 0
        rssi_samples = _to_int(rssi_count) or 0
        hops_samples = _to_int(hops_count) or 0
        edge: dict[str, object] = {
            "from": from_clean,
            "to": to_clean,
            "count": count,
            "first_rx_unix": _to_int(first_seen_unix),
            "last_rx_unix": _to_int(last_seen_unix),
            "snr_samples": snr_samples,
            "rssi_samples": rssi_samples,
            "hops_samples": hops_samples,
        }
        if snr_samples > 0:
            edge["avg_snr"] = (_to_float(snr_sum) or 0.0) / snr_samples
        if rssi_samples > 0:
            edge["avg_rssi"] = (_to_float(rssi_sum) or 0.0) / rssi_samples
        if hops_samples > 0:
            edge["avg_hops"] = (_to_float(hops_sum) or 0.0) / hops_samples
            edge["last_hops"] = _to_int(hops_max)
        edges.append(edge)
    return edges


def _build_anchor(
    *,
    target_id: str,
    edge: Mapping[str, object],
    positions_xy: Mapping[str, tuple[float, float]],
    now_unix: int,
) -> Optional[dict[str, object]]:
    from_id = str(edge.get("from") or "").strip()
    to_id = str(edge.get("to") or "").strip()
    peer_id = to_id if from_id == target_id else from_id if to_id == target_id else ""
    if not peer_id or peer_id not in positions_xy:
        return None
    signal_range = _range_from_signal(edge)
    if signal_range is None or int(signal_range["samples"]) < _MIN_SIGNAL_SAMPLES:
        return None
    location_weight = _edge_location_weight(edge, now_unix=now_unix)
    if location_weight <= 0:
        return None
    range_confidence = float(signal_range["confidence"])
    sample_weight = _clamp(math.log10(float(signal_range["samples"]) + 1), 0.35, 1.25)
    weight = _clamp(
        location_weight * range_confidence * _recency_score(edge.get("last_rx_unix"), now_unix) * sample_weight,
        0.02,
        2.5,
    )
    x, y = positions_xy[peer_id]
    return {
        "node_id": peer_id,
        "x": x,
        "y": y,
        "distance_meters": float(signal_range["meters"]),
        "weight": weight,
        "samples": int(signal_range["samples"]),
        "range_confidence": range_confidence,
        "avg_snr": _to_float(edge.get("avg_snr")),
        "avg_rssi": _to_float(edge.get("avg_rssi")),
        "avg_hops": _to_float(edge.get("avg_hops")),
        "last_seen_unix": _to_int(edge.get("last_rx_unix")),
    }


def _solve_trilateration(
    *,
    node_id: str,
    anchors: list[dict[str, object]],
) -> Optional[dict[str, object]]:
    usable = [
        anchor
        for anchor in anchors
        if _to_float(anchor.get("x")) is not None
        and _to_float(anchor.get("y")) is not None
        and (_to_float(anchor.get("distance_meters")) or 0.0) > 0
        and (_to_float(anchor.get("weight")) or 0.0) > 0
    ]
    if not node_id or len(usable) < _MIN_ANCHORS:
        return None

    total_seed_weight = sum(_to_float(anchor.get("weight")) or 0.0 for anchor in usable)
    if total_seed_weight <= 0:
        return None
    x = sum((_to_float(anchor.get("x")) or 0.0) * (_to_float(anchor.get("weight")) or 0.0) for anchor in usable)
    y = sum((_to_float(anchor.get("y")) or 0.0) * (_to_float(anchor.get("weight")) or 0.0) for anchor in usable)
    x /= total_seed_weight
    y /= total_seed_weight

    for iteration in range(22):
        a00 = a01 = a11 = b0 = b1 = 0.0
        for anchor in usable:
            ax = _to_float(anchor.get("x")) or 0.0
            ay = _to_float(anchor.get("y")) or 0.0
            dx = x - ax
            dy = y - ay
            distance = max(1.0, math.hypot(dx, dy))
            desired = max(1.0, _to_float(anchor.get("distance_meters")) or 1.0)
            residual = distance - desired
            jx = dx / distance
            jy = dy / distance
            weight = _clamp(anchor.get("weight"), 0.001, 8.0)
            a00 += weight * jx * jx
            a01 += weight * jx * jy
            a11 += weight * jy * jy
            b0 += weight * jx * residual
            b1 += weight * jy * residual
        det = (a00 * a11) - (a01 * a01)
        if not math.isfinite(det) or abs(det) < 1e-6:
            break
        step_x = ((b0 * a11) - (b1 * a01)) / det
        step_y = ((a00 * b1) - (a01 * b0)) / det
        step_meters = math.hypot(step_x, step_y)
        if not math.isfinite(step_meters) or step_meters <= 0.5:
            break
        max_step = max(420.0, 14_000.0 - (iteration * 520.0))
        if step_meters > max_step:
            ratio = max_step / step_meters
            step_x *= ratio
            step_y *= ratio
        x -= step_x
        y -= step_y
        if math.hypot(step_x, step_y) < 2:
            break

    weighted_error = 0.0
    weighted_distance = 0.0
    total_weight = 0.0
    total_samples = 0
    quality_sum = 0.0
    snr_sum = snr_weight = 0.0
    rssi_sum = rssi_weight = 0.0
    hops_sum = hops_weight = 0.0
    for anchor in usable:
        ax = _to_float(anchor.get("x")) or 0.0
        ay = _to_float(anchor.get("y")) or 0.0
        distance = math.hypot(x - ax, y - ay)
        desired = max(1.0, _to_float(anchor.get("distance_meters")) or 1.0)
        weight = _clamp(anchor.get("weight"), 0.001, 8.0)
        weighted_error += abs(distance - desired) * weight
        weighted_distance += desired * weight
        total_weight += weight
        total_samples += max(0, _to_int(anchor.get("samples")) or 0)
        quality_sum += _clamp(anchor.get("range_confidence"), 0.0, 1.0) * weight
        avg_snr = _to_float(anchor.get("avg_snr"))
        if avg_snr is not None:
            snr_sum += avg_snr * weight
            snr_weight += weight
        avg_rssi = _to_float(anchor.get("avg_rssi"))
        if avg_rssi is not None:
            rssi_sum += avg_rssi * weight
            rssi_weight += weight
        avg_hops = _to_float(anchor.get("avg_hops"))
        if avg_hops is not None:
            hops_sum += avg_hops * weight
            hops_weight += weight
    if total_weight <= 0:
        return None
    residual_meters = weighted_error / total_weight
    residual_ratio = residual_meters / max(900.0, weighted_distance / total_weight)
    fit_score = _clamp(1 - (residual_ratio / 0.82), 0.0, 1.0)
    quality_score = _clamp(quality_sum / total_weight, 0.0, 1.0)
    anchor_score = _clamp((len(usable) - 3) / 4, 0.0, 1.0)
    sample_score = _clamp(math.log10(total_samples + 1) / 1.35, 0.0, 1.0)
    confidence = _clamp(
        0.08 + (fit_score * 0.54) + (quality_score * 0.14) + (anchor_score * 0.14) + (sample_score * 0.10),
        0.04,
        0.92,
    )
    if confidence < _MIN_CONFIDENCE or fit_score < _MIN_FIT:
        return None
    return {
        "x": x,
        "y": y,
        "confidence": confidence,
        "fit_score": fit_score,
        "residual_km": round((residual_meters / 1000.0) * 10) / 10,
        "residual_ratio": round(residual_ratio * 1000) / 1000,
        "anchor_count": len(usable),
        "support_links": len(usable),
        "signal_samples": total_samples,
        "avg_link_quality": quality_score,
        "avg_snr": round(snr_sum / snr_weight, 2) if snr_weight > 0 else None,
        "avg_rssi": round(rssi_sum / rssi_weight, 2) if rssi_weight > 0 else None,
        "avg_hops": round(hops_sum / hops_weight, 2) if hops_weight > 0 else None,
    }


def build_location_estimates(
    *,
    edge_rows: Iterable[tuple[object, ...]],
    position_rows: Iterable[tuple[object, ...]],
    window: object = "72h",
    limit: object = _DEFAULT_LIMIT,
    now_unix: Optional[int] = None,
) -> dict[str, object]:
    clean_window = _normalize_window(window)
    clean_limit = _clean_limit(limit)
    now = int(now_unix if now_unix is not None else time.time())
    positions = _decode_position_rows(position_rows)
    edges = _decode_link_rows(edge_rows)

    if len(positions) < _MIN_ANCHORS:
        return {
            "ok": True,
            "window": clean_window,
            "limit": clean_limit,
            "estimate_count": 0,
            "estimates": [],
            "anchor_count": len(positions),
        }

    ref_lat = sum(float(pos["lat"]) for pos in positions.values()) / len(positions)
    ref_lon = sum(float(pos["lon"]) for pos in positions.values()) / len(positions)
    positions_xy = {
        node_id: _project_point(float(pos["lat"]), float(pos["lon"]), ref_lat, ref_lon)
        for node_id, pos in positions.items()
    }

    edges_by_node: dict[str, list[dict[str, object]]] = defaultdict(list)
    for edge in edges:
        edges_by_node[str(edge.get("from") or "")].append(edge)
        edges_by_node[str(edge.get("to") or "")].append(edge)

    candidate_ids = [
        node_id
        for node_id in edges_by_node
        if node_id and node_id not in positions
    ]
    estimates: list[dict[str, object]] = []
    for node_id in candidate_ids:
        anchors: list[dict[str, object]] = []
        for edge in edges_by_node.get(node_id, []):
            anchor = _build_anchor(
                target_id=node_id,
                edge=edge,
                positions_xy=positions_xy,
                now_unix=now,
            )
            if anchor is not None:
                anchors.append(anchor)
        if len(anchors) < _MIN_ANCHORS:
            continue
        anchors.sort(key=lambda item: _to_float(item.get("weight")) or 0.0, reverse=True)
        solution = _solve_trilateration(node_id=node_id, anchors=anchors[:_MAX_ANCHORS])
        if solution is None:
            continue
        lat, lon = _unproject_point(float(solution["x"]), float(solution["y"]), ref_lat, ref_lon)
        if not _is_valid_coord(lat, lon):
            continue
        city = _nearest_city(lat, lon)
        estimate: dict[str, object] = {
            "node_id": node_id,
            "lat": lat,
            "lon": lon,
            "estimated_lat": lat,
            "estimated_lon": lon,
            "source": "rssi_trilateration",
            "estimate_source": "rssi_trilateration",
            "confidence": round(float(solution["confidence"]), 3),
            "fit_score": round(float(solution["fit_score"]), 3),
            "residual_km": solution["residual_km"],
            "residual_ratio": solution["residual_ratio"],
            "anchor_count": solution["anchor_count"],
            "support_links": solution["support_links"],
            "signal_samples": solution["signal_samples"],
            "avg_link_quality": round(float(solution["avg_link_quality"]), 3),
            "avg_position_quality": round(float(solution["avg_link_quality"]), 3),
            "avg_snr": solution["avg_snr"],
            "avg_rssi": solution["avg_rssi"],
            "avg_hops": solution["avg_hops"],
            "window": clean_window,
        }
        city_distance = _to_float(city.get("distance_km")) if city else None
        if city and city_distance is not None and city_distance <= _MAX_CITY_DISTANCE_KM:
            city_name = str(city.get("name") or "").strip()
            city_state = str(city.get("state") or "").strip()
            city_country = str(city.get("country") or "").strip()
            city_label = city_name
            if city_state:
                city_label = f"{city_name}, {city_state}"
            elif city_country:
                city_label = f"{city_name}, {city_country}"
            estimate["city"] = city_label
            estimate["city_name"] = city_name
            estimate["city_state"] = city_state
            estimate["city_country"] = city_country
            estimate["city_distance_km"] = city.get("distance_km")
            estimate["city_population"] = city.get("population")
            estimate["city_rank"] = city.get("rank")
        estimates.append(estimate)

    estimates.sort(
        key=lambda item: (
            -float(item.get("confidence") or 0.0),
            -int(item.get("signal_samples") or 0),
            str(item.get("node_id") or ""),
        )
    )
    estimates = estimates[:clean_limit]
    return {
        "ok": True,
        "window": clean_window,
        "limit": clean_limit,
        "estimate_count": len(estimates),
        "estimates": estimates,
        "anchor_count": len(positions),
    }


def load_location_estimates(
    store: HistoryStoreReadState,
    *,
    window: object = "72h",
    limit: object = _DEFAULT_LIMIT,
) -> dict[str, object]:
    clean_window = _normalize_window(window)
    clean_limit = _clean_limit(limit)
    window_seconds = int(_WINDOW_SECONDS[clean_window])
    cutoff_unix = 0
    if window_seconds > 0:
        cutoff_unix = max(0, int(time.time()) - window_seconds)

    read_conn = getattr(store, "_read_conn", None)
    if read_conn is None or read_conn is store._conn:
        read_conn = store._conn
        read_lock = store._lock
    else:
        read_lock = getattr(store, "_read_lock", None) or store._lock

    # Fetch more edges than the returned estimate limit; each estimate needs
    # several anchored links and many high-volume edges may already have GPS.
    edge_limit = min(_MAX_LIMIT * 4, max(300, clean_limit * 12))
    with read_lock:
        position_rows = _fetch_latest_position_rows(read_conn)
        edge_rows = _fetch_link_metric_rows(
            read_conn,
            cutoff_unix=cutoff_unix,
            limit=edge_limit,
        )
    payload = build_location_estimates(
        edge_rows=edge_rows,
        position_rows=position_rows,
        window=clean_window,
        limit=clean_limit,
    )
    payload["window_seconds"] = window_seconds
    return payload
