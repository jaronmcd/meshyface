from __future__ import annotations

from typing import Any, Optional

from .api_input_channels import ChannelSettingsRequest


def _get_local_node(iface: object) -> Any:
    node = getattr(iface, "localNode", None)
    if node is not None:
        return node
    get_node = getattr(iface, "getNode", None)
    if callable(get_node):
        return get_node("^local")
    raise RuntimeError("Interface has no local node")


def _ensure_channels_loaded(node: object) -> Any:
    channels = getattr(node, "channels", None)
    if channels is not None:
        return channels

    request_channels = getattr(node, "requestChannels", None)
    wait_for = getattr(node, "waitForConfig", None)
    if callable(request_channels):
        try:
            request_channels(0)
        except TypeError:
            request_channels()
        if callable(wait_for):
            try:
                wait_for("channels")
            except Exception:
                # Best effort; some interfaces don't support waitForConfig.
                pass
    channels = getattr(node, "channels", None)
    if channels is None:
        raise RuntimeError("Channels are not loaded")
    return channels


def _import_channel_pb2():
    try:
        from meshtastic.protobuf import channel_pb2  # type: ignore

        return channel_pb2
    except Exception:
        from meshtastic.protobuf import channel_pb2 as channel_pb2_alt  # type: ignore

        return channel_pb2_alt


def _role_value(channel_pb2: Any, role: str) -> int:
    role_u = (role or "").strip().upper()
    if not role_u:
        raise ValueError("role is empty")
    mapping = {
        "DISABLED": channel_pb2.Channel.Role.DISABLED,
        "PRIMARY": channel_pb2.Channel.Role.PRIMARY,
        "SECONDARY": channel_pb2.Channel.Role.SECONDARY,
    }
    if role_u not in mapping:
        raise ValueError("Invalid role")
    return int(mapping[role_u])


def _role_name(channel_pb2: Any, role_value: int) -> str:
    try:
        return channel_pb2.Channel.Role.Name(int(role_value))
    except Exception:
        return str(role_value)


def _compute_last_active_index(channel_pb2: Any, channels: Any) -> int:
    disabled = int(channel_pb2.Channel.Role.DISABLED)
    last = 0
    for ch in channels or []:
        try:
            idx = int(getattr(ch, "index", 0))
            role = int(getattr(ch, "role", disabled))
        except Exception:
            continue
        if role != disabled:
            if idx > last:
                last = idx
    return last


def _acquire_lock(lock: object) -> tuple[bool, Optional[callable]]:
    acquire = getattr(lock, "acquire", None)
    release = getattr(lock, "release", None)
    if callable(acquire) and callable(release):
        acquire()
        return True, release
    return False, None


def apply_channel_settings(
    request: ChannelSettingsRequest,
    *,
    iface: object,
    send_lock: object,
    show_secrets: bool,
) -> dict[str, object]:
    """Apply channel edits to the connected Meshtastic radio (local node)."""

    action = (request.action or "upsert").strip().lower()

    node = _get_local_node(iface)

    if action == "import_url":
        set_url = getattr(node, "setURL", None)
        if not callable(set_url):
            return {"ok": False, "error": "Meshtastic node does not support setURL()"}

        url = (request.url or "").strip()
        if not url:
            return {"ok": False, "error": "Missing url"}

        add_only = bool(request.add_only)

        # Meshtastic expects a special URL shape when addOnly=True: .../?add=true#...
        # Be forgiving and rewrite common share URLs into the expected form.
        normalized = url
        if add_only:
            if "/?add=true#" not in normalized and "/#" in normalized:
                normalized = normalized.replace("/#", "/?add=true#", 1)
        else:
            if "/?add=true#" in normalized:
                normalized = normalized.replace("/?add=true#", "/#", 1)

        # Ensure we have channels loaded before invoking setURL (it expects node.channels not None).
        try:
            _ensure_channels_loaded(node)
        except Exception:
            # Best-effort; setURL will emit a nicer error if it truly can't proceed.
            pass

        locked, release = _acquire_lock(send_lock)
        try:
            try:
                set_url(normalized, addOnly=add_only)
            except TypeError:
                # Older versions might use positional args.
                set_url(normalized, add_only)
        except SystemExit as exc:
            return {"ok": False, "error": f"Import failed: {exc}"}
        except Exception as exc:
            return {"ok": False, "error": f"Import failed: {exc}"}
        finally:
            if locked and release:
                release()

        return {
            "ok": True,
            "action": "import_url",
            "add_only": add_only,
            "reboot_expected": True,
        }

    if action == "export_url":
        if not show_secrets:
            return {
                "ok": False,
                "error": "Secrets are redacted. Restart with --show-secrets to export channel URLs.",
            }
        get_url = getattr(node, "getURL", None)
        if not callable(get_url):
            return {"ok": False, "error": "Meshtastic node does not support getURL()"}
        try:
            url = get_url(includeAll=bool(request.include_all))
        except Exception as exc:
            return {"ok": False, "error": f"Export failed: {exc}"}
        return {"ok": True, "action": "export_url", "include_all": bool(request.include_all), "url": url}

    # For upsert/disable we need channels and writeChannel.
    try:
        channel_pb2 = _import_channel_pb2()
    except Exception as exc:
        return {"ok": False, "error": f"Meshtastic channel protobuf unavailable: {exc}"}

    try:
        channels = _ensure_channels_loaded(node)
    except Exception as exc:
        return {"ok": False, "error": f"Channels unavailable: {exc}"}

    write_channel = getattr(node, "writeChannel", None)
    if not callable(write_channel):
        return {"ok": False, "error": "Meshtastic node does not support writeChannel()"}

    disabled_role = int(channel_pb2.Channel.Role.DISABLED)
    primary_role = int(channel_pb2.Channel.Role.PRIMARY)
    secondary_role = int(channel_pb2.Channel.Role.SECONDARY)

    last_active = _compute_last_active_index(channel_pb2, channels)
    next_available = last_active + 1

    idx: Optional[int] = request.channel_index
    if action == "disable":
        if idx is None:
            return {"ok": False, "error": "channel_index is required for disable"}
        if idx <= 0:
            return {"ok": False, "error": "Primary channel (index 0) cannot be disabled"}
        if idx != last_active:
            return {
                "ok": False,
                "error": "Disable channels from the end (highest active index) to avoid gaps",
                "last_active_index": last_active,
            }
        if idx >= len(channels):
            return {"ok": False, "error": "channel_index out of range"}

        ch = channels[idx]
        # Enforce the role is secondary before disabling.
        try:
            ch_role = int(getattr(ch, "role", disabled_role))
        except Exception:
            ch_role = disabled_role
        if ch_role == primary_role:
            return {"ok": False, "error": "Primary channel cannot be disabled"}

        # Reset fields to defaults as best-effort.
        try:
            ch.role = disabled_role
        except Exception:
            pass
        try:
            if getattr(ch, "settings", None) is not None:
                ch.settings.name = ""
                # Downlink/uplink default false
                if hasattr(ch.settings, "downlink_enabled"):
                    ch.settings.downlink_enabled = False
                if hasattr(ch.settings, "uplink_enabled"):
                    ch.settings.uplink_enabled = False
                # Reset PSK to default (public) key when possible.
                try:
                    from meshtastic.util import fromPSK  # type: ignore

                    ch.settings.psk = fromPSK("default")
                except Exception:
                    # If util isn't available, keep existing bytes.
                    pass
        except Exception:
            pass
        try:
            if getattr(ch, "module_settings", None) is not None:
                # Reset common module settings.
                if hasattr(ch.module_settings, "is_muted"):
                    ch.module_settings.is_muted = False
                if hasattr(ch.module_settings, "position_precision"):
                    ch.module_settings.position_precision = 0
        except Exception:
            pass

        # Write to radio with locking.
        locked, release = _acquire_lock(send_lock)
        try:
            write_channel(idx)
        except Exception as exc:
            return {"ok": False, "error": f"Write failed: {exc}"}
        finally:
            if locked and release:
                release()

        return {
            "ok": True,
            "action": "disable",
            "channel_index": idx,
            "reboot_expected": True,
        }

    # action == upsert
    if action != "upsert":
        return {"ok": False, "error": "Unsupported action"}

    if idx is None:
        idx = next_available

    if idx < 0 or idx >= len(channels):
        return {"ok": False, "error": "channel_index out of range", "max_index": len(channels) - 1}

    ch = channels[idx]

    try:
        existing_role = int(getattr(ch, "role", disabled_role))
    except Exception:
        existing_role = disabled_role

    is_creating = existing_role == disabled_role and idx > last_active

    # If we are creating a new channel, enforce consecutive slots.
    if is_creating and idx != next_available:
        return {
            "ok": False,
            "error": "Channels must be consecutive. Add the next available channel slot.",
            "next_available_index": next_available,
            "last_active_index": last_active,
        }

    # Role rules.
    requested_role_value: Optional[int] = None
    if request.role:
        try:
            requested_role_value = _role_value(channel_pb2, request.role)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

    if idx == 0:
        if requested_role_value is not None and requested_role_value != primary_role:
            return {"ok": False, "error": "Primary channel must remain PRIMARY"}
        # Ensure primary.
        try:
            ch.role = primary_role
        except Exception:
            pass
    else:
        if requested_role_value is not None:
            if requested_role_value == primary_role:
                return {"ok": False, "error": "Only index 0 can be PRIMARY"}
            if requested_role_value == disabled_role:
                return {"ok": False, "error": "Use action=disable to disable a channel"}
            try:
                ch.role = requested_role_value
            except Exception:
                pass
        else:
            # If creating, default to SECONDARY.
            if existing_role == disabled_role:
                try:
                    ch.role = secondary_role
                except Exception:
                    pass

    applied_fields: list[str] = []
    ignored_fields: list[str] = []

    settings = request.settings or {}

    # Ensure settings message exists.
    if getattr(ch, "settings", None) is None:
        return {"ok": False, "error": "Channel settings are unavailable on this node"}

    if "name" in settings:
        try:
            name = str(settings.get("name") or "").strip()
            if idx != 0 and existing_role == disabled_role and not name and not bool(request.allow_experimental):
                return {"ok": False, "error": "Channel name is required when adding a channel"}
            ch.settings.name = name
            applied_fields.append("settings.name")
        except Exception:
            ignored_fields.append("settings.name")

    if "uplink_enabled" in settings:
        try:
            ch.settings.uplink_enabled = bool(settings.get("uplink_enabled"))
            applied_fields.append("settings.uplink_enabled")
        except Exception:
            ignored_fields.append("settings.uplink_enabled")

    if "downlink_enabled" in settings:
        try:
            ch.settings.downlink_enabled = bool(settings.get("downlink_enabled"))
            applied_fields.append("settings.downlink_enabled")
        except Exception:
            ignored_fields.append("settings.downlink_enabled")

    if "psk" in settings:
        psk_raw = settings.get("psk")
        psk_s = "" if psk_raw is None else str(psk_raw).strip()
        if psk_s and psk_s != "<redacted>":
            try:
                from meshtastic.util import fromPSK  # type: ignore

                ch.settings.psk = fromPSK(psk_s)
                applied_fields.append("settings.psk")
            except Exception:
                ignored_fields.append("settings.psk")
        else:
            # Empty or redacted => preserve.
            ignored_fields.append("settings.psk")

    if "module_settings" in settings:
        ms = settings.get("module_settings")
        if isinstance(ms, dict):
            # Only apply a safe subset.
            if getattr(ch, "module_settings", None) is None:
                ignored_fields.append("module_settings")
            else:
                if "is_muted" in ms:
                    try:
                        ch.module_settings.is_muted = bool(ms.get("is_muted"))
                        applied_fields.append("module_settings.is_muted")
                    except Exception:
                        ignored_fields.append("module_settings.is_muted")
                if "position_precision" in ms:
                    try:
                        ch.module_settings.position_precision = int(ms.get("position_precision"))
                        applied_fields.append("module_settings.position_precision")
                    except Exception:
                        ignored_fields.append("module_settings.position_precision")

    if not applied_fields and not is_creating and requested_role_value is None:
        return {"ok": False, "error": "No valid fields to apply", "ignored_fields": ignored_fields}

    # Write to radio with locking.
    locked, release = _acquire_lock(send_lock)
    try:
        write_channel(int(idx))
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Write failed: {exc}",
            "applied_fields": applied_fields,
            "ignored_fields": ignored_fields,
        }
    finally:
        if locked and release:
            release()

    # Recompute active index post-write is expensive; return best-effort hints.
    return {
        "ok": True,
        "action": "upsert",
        "channel_index": int(idx),
        "role": _role_name(channel_pb2, int(getattr(ch, "role", 0))),
        "applied_fields": applied_fields,
        "ignored_fields": ignored_fields,
        "reboot_expected": True,
    }
