import json
from dataclasses import dataclass


@dataclass(frozen=True)
class CustomTelemetrySettingsRequest:
    rules: object = None


def parse_custom_telemetry_settings_request(raw_body: bytes) -> CustomTelemetrySettingsRequest:
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except Exception:
        body = {}
    payload = body if isinstance(body, dict) else {}
    return CustomTelemetrySettingsRequest(
        rules=payload.get("rules"),
    )
