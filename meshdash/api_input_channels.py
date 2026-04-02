import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ChannelSettingsRequest:
    """A request to update Meshtastic channel settings on the connected node.

    Supported actions:
      - "upsert": create/update a channel slot (PRIMARY/SECONDARY).
      - "disable": disable a SECONDARY channel slot (must be last active).
      - "export_url": return the sharable channel URL from the device.
      - "import_url": apply a Meshtastic channel URL (QR/share URL) to the device.

    Notes:
      - If channel_index is omitted for "upsert", the next available slot
        (first DISABLED after the last active channel) will be used.
      - "psk" can be provided as meshtastic.util.fromPSK-compatible strings
        such as: "default", "random", "none", "simple15", "base64:...".
      - If "psk" is omitted or set to "<redacted>", the existing PSK is preserved.
    """

    action: str = "upsert"
    channel_index: Optional[int] = None
    role: Optional[str] = None
    settings: dict[str, object] = field(default_factory=dict)
    include_all: bool = True
    url: Optional[str] = None
    add_only: bool = False
    allow_experimental: bool = False


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "y", "on"}:
            return True
        if v in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


def _coerce_int(value: object) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if not (value == value):
            return None
        return int(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return int(raw, 10)
        except Exception:
            return None
    return None


def _clean_settings(payload: object) -> dict[str, object]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("Expected 'settings' to be an object")

    clean: dict[str, object] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        k = key.strip()
        if k in {"name", "psk"}:
            if value is None:
                continue
            clean[k] = str(value)
            continue
        if k in {"uplink_enabled", "downlink_enabled"}:
            clean[k] = _coerce_bool(value)
            continue
        # module_settings passthrough (advanced) - must be an object
        if k == "module_settings":
            if isinstance(value, dict):
                clean[k] = dict(value)
            continue
    return clean


def parse_channel_settings_request(raw_body: bytes) -> ChannelSettingsRequest:
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Invalid JSON: {exc}")

    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object")

    action_raw = str(payload.get("action") or payload.get("op") or "upsert").strip().lower()
    action = {
        "seturl": "import_url",
        "set_url": "import_url",
        "importurl": "import_url",
        "import_url": "import_url",
    }.get(action_raw, action_raw)

    if action not in {"upsert", "disable", "export_url", "import_url"}:
        raise ValueError("Unsupported action")

    channel_index = _coerce_int(payload.get("channel_index"))
    if channel_index is None and "channel_index" in payload and payload.get("channel_index") is not None:
        raise ValueError("Invalid channel_index")

    role = payload.get("role")
    role_s: Optional[str]
    if role is None:
        role_s = None
    else:
        role_s = str(role).strip().upper() or None

    include_all = _coerce_bool(payload.get("include_all", True))

    settings = _clean_settings(payload.get("settings"))
    # Allow a flat payload style: { name: ..., psk: ..., uplink_enabled: ... }
    for flat_key in ("name", "psk", "uplink_enabled", "downlink_enabled"):
        if flat_key in payload and flat_key not in settings:
            val = payload.get(flat_key)
            if flat_key in {"uplink_enabled", "downlink_enabled"}:
                settings[flat_key] = _coerce_bool(val)
            elif val is not None:
                settings[flat_key] = str(val)

    url: Optional[str] = None
    add_only = False
    if action == "import_url":
        url_raw = (
            payload.get("url")
            or payload.get("channel_url")
            or payload.get("seturl")
            or payload.get("set_url")
            or payload.get("setURL")
            or payload.get("setUrl")
        )
        url = str(url_raw).strip() if url_raw is not None else None
        if not url:
            raise ValueError("Missing url")
        add_only = _coerce_bool(payload.get("add_only", payload.get("addOnly", False)))

    return ChannelSettingsRequest(
        action=action,
        channel_index=channel_index,
        role=role_s,
        settings=settings,
        include_all=include_all,
        url=url,
        add_only=add_only,
        allow_experimental=_coerce_bool(payload.get("allow_experimental", payload.get("experimental", False))),
    )
