from typing import Optional

from .helpers_core import to_float as _to_float


def extract_packet_battery_level(packet: dict[str, object]) -> Optional[int]:
    if not isinstance(packet, dict):
        return None

    candidates: list[dict[str, object]] = []
    decoded = packet.get("decoded")
    if isinstance(decoded, dict):
        telemetry = decoded.get("telemetry")
        if isinstance(telemetry, dict):
            candidates.append(telemetry)
            metrics = telemetry.get("deviceMetrics") or telemetry.get("device_metrics")
            if isinstance(metrics, dict):
                candidates.append(metrics)
        metrics = decoded.get("deviceMetrics") or decoded.get("device_metrics") or decoded.get("metrics")
        if isinstance(metrics, dict):
            candidates.append(metrics)
        candidates.append(decoded)

    telemetry = packet.get("telemetry")
    if isinstance(telemetry, dict):
        candidates.append(telemetry)
        metrics = telemetry.get("deviceMetrics") or telemetry.get("device_metrics")
        if isinstance(metrics, dict):
            candidates.append(metrics)
    metrics = packet.get("deviceMetrics") or packet.get("device_metrics") or packet.get("metrics")
    if isinstance(metrics, dict):
        candidates.append(metrics)
    candidates.append(packet)

    for candidate in candidates:
        for key in ("batteryLevel", "battery_level", "batteryPercent", "battery_percent", "battery"):
            raw = candidate.get(key)
            if raw is None:
                continue
            level_f = _to_float(raw)
            if level_f is None:
                continue
            level = int(round(level_f))
            if 0 <= level <= 100:
                return level
    return None
