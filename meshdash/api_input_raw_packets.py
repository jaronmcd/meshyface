import json
from dataclasses import dataclass


@dataclass(frozen=True)
class RawPacketCaptureSettingsRequest:
    settings: dict[str, object]


def _coerce_capture_enabled(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on", "enabled"}:
            return True
        if text in {"0", "false", "no", "off", "disabled"}:
            return False
    raise ValueError("capture_enabled must be boolean")


def parse_raw_packet_capture_settings_request(raw_body: bytes) -> RawPacketCaptureSettingsRequest:
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid JSON request body") from exc
    if not isinstance(body, dict):
        raise ValueError("request body must be an object")
    payload = body
    settings = payload.get("settings") if isinstance(payload.get("settings"), dict) else payload
    if not isinstance(settings, dict):
        raise ValueError("capture_enabled is required")
    if "capture_enabled" in settings:
        enabled = settings.get("capture_enabled")
    elif "enabled" in settings:
        enabled = settings.get("enabled")
    else:
        raise ValueError("capture_enabled is required")
    return RawPacketCaptureSettingsRequest(
        settings={
            "capture_enabled": _coerce_capture_enabled(enabled),
        }
    )
