from __future__ import annotations

import threading
import time

from .api_input_network_tools import NetworkToolRequest
from .helpers import to_int


def _load_meshtastic_modules():
    try:
        from meshtastic.protobuf import channel_pb2, mesh_pb2, portnums_pb2  # type: ignore
        try:
            from meshtastic.protobuf import telemetry_pb2  # type: ignore
        except Exception:
            telemetry_pb2 = None
    except Exception as exc:
        raise RuntimeError("Meshtastic protobuf support is unavailable") from exc
    return channel_pb2, mesh_pb2, portnums_pb2, telemetry_pb2


def _channel_is_enabled(iface: object, channel_index: int, channel_pb2_module: object) -> bool:
    local_node = getattr(iface, "localNode", None)
    get_channel = getattr(local_node, "getChannelByChannelIndex", None)
    if not callable(get_channel):
        return True
    try:
        channel = get_channel(channel_index)
    except Exception:
        return False
    if channel is None:
        return False
    disabled_role = getattr(getattr(channel_pb2_module, "Channel", None).Role, "DISABLED", None)
    if disabled_role is None:
        return True
    return getattr(channel, "role", None) != disabled_role


def _portnum_matches(value: object, expected_name: str) -> bool:
    text = str(value or "").strip().upper()
    return text == expected_name or text.endswith(f".{expected_name}")


def _routing_error_reason(packet: object) -> str:
    decoded = packet.get("decoded") if isinstance(packet, dict) else None
    routing = decoded.get("routing") if isinstance(decoded, dict) else None
    if not isinstance(routing, dict):
        return ""
    reason = str(routing.get("errorReason") or "").strip().upper()
    if not reason or reason == "NONE":
        return ""
    return reason


def _send_mesh_request(
    *,
    iface: object,
    send_lock,
    message: object,
    destination: str,
    port_num: object,
    channel_index: int,
    timeout_ms: int,
    hop_limit: int | None = None,
    to_int_fn=to_int,
) -> tuple[int | None, object | None]:
    send_data = getattr(iface, "sendData", None)
    if not callable(send_data):
        raise ValueError("Connected interface does not support sendData()")

    done = threading.Event()
    response_box: dict[str, object] = {"packet": None}

    def _on_response(packet: object) -> None:
        response_box["packet"] = packet
        done.set()

    kwargs: dict[str, object] = {
        "destinationId": destination,
        "portNum": port_num,
        "wantResponse": True,
        "onResponse": _on_response,
        "channelIndex": channel_index,
    }
    if hop_limit is not None:
        kwargs["hopLimit"] = hop_limit

    with send_lock:
        sent_packet = send_data(message, **kwargs)

    sent_packet_id = to_int_fn(getattr(sent_packet, "id", None))
    if not done.wait(max(0.1, float(timeout_ms) / 1000.0)):
        return sent_packet_id, None
    return sent_packet_id, response_box.get("packet")


def _send_mesh_packet(
    *,
    iface: object,
    send_lock,
    message: object,
    destination: str,
    port_num: object,
    channel_index: int,
    hop_limit: int | None = None,
    to_int_fn=to_int,
) -> int | None:
    send_data = getattr(iface, "sendData", None)
    if not callable(send_data):
        raise ValueError("Connected interface does not support sendData()")

    kwargs: dict[str, object] = {
        "destinationId": destination,
        "portNum": port_num,
        "wantResponse": False,
        "channelIndex": channel_index,
    }
    if hop_limit is not None:
        kwargs["hopLimit"] = hop_limit

    with send_lock:
        sent_packet = send_data(message, **kwargs)
    return to_int_fn(getattr(sent_packet, "id", None))


def _error_response(
    request: NetworkToolRequest,
    *,
    summary_label: str,
    detail: str,
) -> dict[str, object]:
    payload = _not_implemented_response(request, summary_label=summary_label, detail=detail)
    payload["console_lines"] = [f"[{summary_label}] {detail}"]
    return payload


def _not_implemented_response(
    request: NetworkToolRequest,
    *,
    summary_label: str,
    detail: str,
) -> dict[str, object]:
    destination = str(request.destination or "").strip() or None
    payload: dict[str, object] = {
        "ok": False,
        "command": request.command,
        "error": detail,
        "console_lines": [f"[{summary_label}] {detail}"],
    }
    if destination:
        payload["destination"] = destination
    if request.channel_index is not None:
        payload["channel_index"] = request.channel_index
    if request.timeout_ms is not None:
        payload["timeout_ms"] = request.timeout_ms
    if request.hop_limit is not None:
        payload["hop_limit"] = request.hop_limit
    if request.telemetry_type is not None:
        payload["telemetry_type"] = request.telemetry_type
    if request.text is not None:
        payload["text"] = request.text
    if request.delay_seconds is not None:
        payload["delay_seconds"] = request.delay_seconds
    if request.time_sec is not None:
        payload["time_sec"] = request.time_sec
    if request.config_type is not None:
        payload["config_type"] = request.config_type
    if request.starting_index is not None:
        payload["starting_index"] = request.starting_index
    if request.confirm is not None:
        payload["confirm"] = request.confirm
    return payload


def _nodeinfo_field(user: object, field_name: str) -> object:
    if isinstance(user, dict):
        value = user.get(field_name)
        if value is not None:
            return value
        pieces = field_name.split("_")
        camel_name = pieces[0] + "".join(piece[:1].upper() + piece[1:] for piece in pieces[1:])
        return user.get(camel_name)
    return getattr(user, field_name, None)


def _find_local_user_record(iface: object, *, to_int_fn=to_int) -> object | None:
    local_node = getattr(iface, "localNode", None)
    local_num = to_int_fn(getattr(local_node, "nodeNum", None))

    nodes_by_num = getattr(iface, "nodesByNum", None)
    if isinstance(nodes_by_num, dict):
        lookup_keys: list[object] = []
        if local_num is not None:
            lookup_keys.extend((local_num, str(local_num)))
        for key in lookup_keys:
            candidate = nodes_by_num.get(key)
            if not candidate:
                continue
            user_obj = _nodeinfo_field(candidate, "user")
            if user_obj:
                return user_obj
            return candidate

    local_user = _nodeinfo_field(local_node, "user")
    if local_user:
        return local_user
    return local_node


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        clean = value.strip().lower()
        if clean in {"1", "true", "yes", "y", "on"}:
            return True
        if clean in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


_TELEMETRY_TYPE_ALIASES = {
    "device": "device_metrics",
    "device_metrics": "device_metrics",
    "environment": "environment_metrics",
    "environment_metrics": "environment_metrics",
    "air_quality": "air_quality_metrics",
    "airquality": "air_quality_metrics",
    "air_quality_metrics": "air_quality_metrics",
    "power": "power_metrics",
    "power_metrics": "power_metrics",
    "localstats": "local_stats",
    "local_stats": "local_stats",
}

_REQUEST_CONFIG_TYPE_ALIASES = {
    "device": "DEVICE_CONFIG",
    "device_config": "DEVICE_CONFIG",
    "position": "POSITION_CONFIG",
    "position_config": "POSITION_CONFIG",
    "power": "POWER_CONFIG",
    "power_config": "POWER_CONFIG",
    "network": "NETWORK_CONFIG",
    "network_config": "NETWORK_CONFIG",
    "display": "DISPLAY_CONFIG",
    "display_config": "DISPLAY_CONFIG",
    "lora": "LORA_CONFIG",
    "lora_config": "LORA_CONFIG",
    "bluetooth": "BLUETOOTH_CONFIG",
    "bluetooth_config": "BLUETOOTH_CONFIG",
    "security": "SECURITY_CONFIG",
    "security_config": "SECURITY_CONFIG",
    "sessionkey": "SESSIONKEY_CONFIG",
    "session_key": "SESSIONKEY_CONFIG",
    "sessionkey_config": "SESSIONKEY_CONFIG",
    "deviceui": "DEVICEUI_CONFIG",
    "device_ui": "DEVICEUI_CONFIG",
    "deviceui_config": "DEVICEUI_CONFIG",
    "ui": "DEVICEUI_CONFIG",
}

_REQUEST_CONFIG_TYPE_ENUM_VALUES = {
    "DEVICE_CONFIG": 0,
    "POSITION_CONFIG": 1,
    "POWER_CONFIG": 2,
    "NETWORK_CONFIG": 3,
    "DISPLAY_CONFIG": 4,
    "LORA_CONFIG": 5,
    "BLUETOOTH_CONFIG": 6,
    "SECURITY_CONFIG": 7,
    "SESSIONKEY_CONFIG": 8,
    "DEVICEUI_CONFIG": 9,
}


def _normalize_telemetry_type(value: object) -> str:
    clean = str(value or "").strip().lower()
    if not clean:
        return "device_metrics"
    normalized = _TELEMETRY_TYPE_ALIASES.get(clean)
    if not normalized:
        raise ValueError(f"Unsupported telemetry type: {clean}")
    return normalized


def _normalize_request_config_type(value: object) -> str:
    clean = str(value or "").strip().lower().replace("-", "_")
    if not clean:
        return "DEVICE_CONFIG"
    normalized = _REQUEST_CONFIG_TYPE_ALIASES.get(clean)
    if normalized:
        return normalized
    if clean.endswith("_config"):
        candidate = clean.upper()
    else:
        candidate = f"{clean.upper()}_CONFIG"
    if candidate in _REQUEST_CONFIG_TYPE_ALIASES.values():
        return candidate
    raise ValueError(f"Unsupported config type: {clean}")


def _build_telemetry_request_message(telemetry_pb2_module: object, telemetry_type: str) -> object:
    telemetry_request = telemetry_pb2_module.Telemetry()
    if telemetry_type == "environment_metrics":
        telemetry_request.environment_metrics.CopyFrom(telemetry_pb2_module.EnvironmentMetrics())
    elif telemetry_type == "air_quality_metrics":
        telemetry_request.air_quality_metrics.CopyFrom(telemetry_pb2_module.AirQualityMetrics())
    elif telemetry_type == "power_metrics":
        telemetry_request.power_metrics.CopyFrom(telemetry_pb2_module.PowerMetrics())
    elif telemetry_type == "local_stats":
        telemetry_request.local_stats.CopyFrom(telemetry_pb2_module.LocalStats())
    else:
        telemetry_request.device_metrics.CopyFrom(telemetry_pb2_module.DeviceMetrics())
    return telemetry_request


def _parse_telemetry_response_payload(payload: object, telemetry_pb2_module: object) -> dict[str, object]:
    if not isinstance(payload, (bytes, bytearray)):
        raise ValueError("Telemetry response payload missing")
    telemetry = telemetry_pb2_module.Telemetry()
    telemetry.ParseFromString(bytes(payload))
    try:
        from google.protobuf import json_format  # type: ignore
    except Exception:
        json_format = None
    if json_format is not None:
        try:
            as_dict = json_format.MessageToDict(telemetry, preserving_proto_field_name=True)
            if isinstance(as_dict, dict):
                return as_dict
        except Exception:
            pass
    fallback_to_dict = getattr(telemetry, "to_dict", None)
    if callable(fallback_to_dict):
        try:
            as_dict = fallback_to_dict()
        except Exception:
            as_dict = {}
        if isinstance(as_dict, dict):
            return as_dict
    return {}


def _build_local_nodeinfo_payload(
    iface: object,
    *,
    mesh_pb2_module: object,
    to_int_fn=to_int,
) -> object:
    user_message = mesh_pb2_module.User()
    source = _find_local_user_record(iface, to_int_fn=to_int_fn)

    node_id = str(_nodeinfo_field(source, "id") or "").strip()
    if not node_id:
        local_node = getattr(iface, "localNode", None)
        local_num = to_int_fn(getattr(local_node, "nodeNum", None))
        if local_num is not None and local_num >= 0:
            node_id = f"!{local_num & 0xFFFFFFFF:08x}"
    if not node_id:
        raise ValueError("Local node ID is unavailable; cannot send node info")
    user_message.id = node_id

    long_name = str(_nodeinfo_field(source, "long_name") or "").strip()
    if long_name:
        user_message.long_name = long_name
    short_name = str(_nodeinfo_field(source, "short_name") or "").strip()
    if short_name:
        user_message.short_name = short_name

    hw_model = to_int_fn(_nodeinfo_field(source, "hw_model"))
    if hw_model is not None and hw_model >= 0:
        user_message.hw_model = hw_model

    role = to_int_fn(_nodeinfo_field(source, "role"))
    if role is not None and role >= 0:
        user_message.role = role

    is_licensed_raw = _nodeinfo_field(source, "is_licensed")
    if is_licensed_raw is not None:
        user_message.is_licensed = _coerce_bool(is_licensed_raw)

    is_unmessagable_raw = _nodeinfo_field(source, "is_unmessagable")
    if is_unmessagable_raw is not None:
        user_message.is_unmessagable = _coerce_bool(is_unmessagable_raw)

    return user_message


def _run_ping(
    request: NetworkToolRequest,
    *,
    iface: object,
    send_lock,
    to_int_fn=to_int,
) -> dict[str, object]:
    destination = str(request.destination or "").strip()
    if not destination:
        raise ValueError("Missing destination")

    channel_pb2, mesh_pb2, portnums_pb2, _telemetry_pb2 = _load_meshtastic_modules()
    channel_index = request.channel_index if request.channel_index is not None else 0
    timeout_ms = request.timeout_ms if request.timeout_ms is not None else 8000
    if not _channel_is_enabled(iface, channel_index, channel_pb2):
        return _error_response(
            request,
            summary_label="ping",
            detail=f"Channel {channel_index} is not enabled on the local node",
        )

    nodeinfo_request = mesh_pb2.User()
    try:
        sent_packet_id, response_packet = _send_mesh_request(
            iface=iface,
            send_lock=send_lock,
            message=nodeinfo_request,
            destination=destination,
            port_num=portnums_pb2.PortNum.NODEINFO_APP,
            channel_index=channel_index,
            timeout_ms=timeout_ms,
            hop_limit=request.hop_limit,
            to_int_fn=to_int_fn,
        )
    except ValueError as exc:
        return _error_response(
            request,
            summary_label="ping",
            detail=str(exc),
        )
    except Exception as exc:
        return _error_response(
            request,
            summary_label="ping",
            detail=f"Ping failed: {exc}",
        )

    if response_packet is None:
        return {
            "ok": False,
            "command": "ping",
            "destination": destination,
            "channel_index": channel_index,
            "hop_limit": request.hop_limit,
            "sent_packet_id": sent_packet_id,
            "error": "Timed out waiting for ping response",
            "console_lines": [f"[ping] {destination} | timed out waiting for response"],
        }

    routing_error = _routing_error_reason(response_packet)
    if routing_error == "NO_RESPONSE":
        return {
            "ok": False,
            "command": "ping",
            "destination": destination,
            "channel_index": channel_index,
            "hop_limit": request.hop_limit,
            "sent_packet_id": sent_packet_id,
            "error": "Destination did not respond",
            "console_lines": [f"[ping] {destination} | destination did not respond"],
        }
    if routing_error:
        return {
            "ok": False,
            "command": "ping",
            "destination": destination,
            "channel_index": channel_index,
            "hop_limit": request.hop_limit,
            "sent_packet_id": sent_packet_id,
            "error": f"Ping failed: {routing_error}",
            "console_lines": [f"[ping] {destination} | error={routing_error}"],
        }

    decoded = response_packet.get("decoded") if isinstance(response_packet, dict) else None
    if not isinstance(decoded, dict) or not _portnum_matches(decoded.get("portnum"), "NODEINFO_APP"):
        return {
            "ok": False,
            "command": "ping",
            "destination": destination,
            "channel_index": channel_index,
            "hop_limit": request.hop_limit,
            "sent_packet_id": sent_packet_id,
            "error": "Invalid ping response payload",
            "console_lines": [f"[ping] {destination} | invalid response payload"],
        }

    nodeinfo: object = decoded.get("user")
    if not isinstance(nodeinfo, dict):
        payload = decoded.get("payload")
        if not isinstance(payload, (bytes, bytearray)):
            return {
                "ok": False,
                "command": "ping",
                "destination": destination,
                "channel_index": channel_index,
                "hop_limit": request.hop_limit,
                "sent_packet_id": sent_packet_id,
                "error": "Ping response payload missing",
                "console_lines": [f"[ping] {destination} | response payload missing"],
            }
        nodeinfo = mesh_pb2.User()
        try:
            nodeinfo.ParseFromString(bytes(payload))
        except Exception as exc:
            return {
                "ok": False,
                "command": "ping",
                "destination": destination,
                "channel_index": channel_index,
                "hop_limit": request.hop_limit,
                "sent_packet_id": sent_packet_id,
                "error": f"Malformed ping response: {exc}",
                "console_lines": [f"[ping] {destination} | malformed response payload"],
            }

    node_id = str(_nodeinfo_field(nodeinfo, "id") or "").strip()
    long_name = str(_nodeinfo_field(nodeinfo, "long_name") or "").strip()
    short_name = str(_nodeinfo_field(nodeinfo, "short_name") or "").strip()
    hw_model_raw = _nodeinfo_field(nodeinfo, "hw_model")
    role_raw = _nodeinfo_field(nodeinfo, "role")
    hw_model = to_int_fn(hw_model_raw)
    role = to_int_fn(role_raw)

    console_parts = [f"[ping] {destination}", "nodeinfo response"]
    if node_id:
        console_parts.append(f"id={node_id}")
    if long_name:
        console_parts.append(f"long={long_name}")
    if short_name:
        console_parts.append(f"short={short_name}")
    if hw_model not in (None, 0):
        console_parts.append(f"hw={hw_model}")
    if role not in (None, 0):
        console_parts.append(f"role={role}")

    return {
        "ok": True,
        "command": "ping",
        "destination": destination,
        "channel_index": channel_index,
        "hop_limit": request.hop_limit,
        "sent_packet_id": sent_packet_id,
        "result": {
            "id": node_id or None,
            "long_name": long_name or None,
            "short_name": short_name or None,
            "hw_model": hw_model,
            "role": role,
        },
        "console_lines": [" | ".join(console_parts)],
    }


def _run_send_node_info(
    request: NetworkToolRequest,
    *,
    iface: object,
    send_lock,
    to_int_fn=to_int,
) -> dict[str, object]:
    channel_pb2, mesh_pb2, portnums_pb2, _telemetry_pb2 = _load_meshtastic_modules()
    channel_index = request.channel_index if request.channel_index is not None else 0
    if not _channel_is_enabled(iface, channel_index, channel_pb2):
        return _error_response(
            request,
            summary_label="nodeinfo",
            detail=f"Channel {channel_index} is not enabled on the local node",
        )

    try:
        user_payload = _build_local_nodeinfo_payload(
            iface,
            mesh_pb2_module=mesh_pb2,
            to_int_fn=to_int_fn,
        )
        sent_packet_id = _send_mesh_packet(
            iface=iface,
            send_lock=send_lock,
            message=user_payload,
            destination="^all",
            port_num=portnums_pb2.PortNum.NODEINFO_APP,
            channel_index=channel_index,
            hop_limit=request.hop_limit,
            to_int_fn=to_int_fn,
        )
    except ValueError as exc:
        return _error_response(
            request,
            summary_label="nodeinfo",
            detail=str(exc),
        )
    except Exception as exc:
        return _error_response(
            request,
            summary_label="nodeinfo",
            detail=f"Node info broadcast failed: {exc}",
        )

    node_id = str(getattr(user_payload, "id", "") or "").strip()
    long_name = str(getattr(user_payload, "long_name", "") or "").strip()
    short_name = str(getattr(user_payload, "short_name", "") or "").strip()
    hw_model = to_int_fn(getattr(user_payload, "hw_model", None))
    role = to_int_fn(getattr(user_payload, "role", None))
    is_licensed = bool(getattr(user_payload, "is_licensed", False))
    is_unmessagable = bool(getattr(user_payload, "is_unmessagable", False))

    console_parts = [f"[nodeinfo] broadcast", f"id={node_id}"]
    if long_name:
        console_parts.append(f"long={long_name}")
    if short_name:
        console_parts.append(f"short={short_name}")
    if hw_model is not None:
        console_parts.append(f"hw={hw_model}")
    if role is not None:
        console_parts.append(f"role={role}")
    console_parts.append(f"ch={channel_index}")

    return {
        "ok": True,
        "command": "send_node_info",
        "destination": "^all",
        "channel_index": channel_index,
        "hop_limit": request.hop_limit,
        "sent_packet_id": sent_packet_id,
        "result": {
            "id": node_id,
            "long_name": long_name or None,
            "short_name": short_name or None,
            "hw_model": hw_model,
            "role": role,
            "is_licensed": is_licensed,
            "is_unmessagable": is_unmessagable,
        },
        "console_lines": [" | ".join(console_parts)],
    }


def _run_request_telemetry(
    request: NetworkToolRequest,
    *,
    iface: object,
    send_lock,
    to_int_fn=to_int,
) -> dict[str, object]:
    destination = str(request.destination or "").strip()
    if not destination:
        raise ValueError("Missing destination")

    channel_pb2, _mesh_pb2, portnums_pb2, telemetry_pb2 = _load_meshtastic_modules()
    if telemetry_pb2 is None:
        return _error_response(
            request,
            summary_label="telemetry",
            detail="Telemetry protobuf support is unavailable",
        )

    channel_index = request.channel_index if request.channel_index is not None else 0
    timeout_ms = request.timeout_ms if request.timeout_ms is not None else 12000
    if not _channel_is_enabled(iface, channel_index, channel_pb2):
        return _error_response(
            request,
            summary_label="telemetry",
            detail=f"Channel {channel_index} is not enabled on the local node",
        )

    try:
        telemetry_type = _normalize_telemetry_type(request.telemetry_type)
    except ValueError as exc:
        return _error_response(
            request,
            summary_label="telemetry",
            detail=str(exc),
        )

    telemetry_request = _build_telemetry_request_message(telemetry_pb2, telemetry_type)
    try:
        sent_packet_id, response_packet = _send_mesh_request(
            iface=iface,
            send_lock=send_lock,
            message=telemetry_request,
            destination=destination,
            port_num=portnums_pb2.PortNum.TELEMETRY_APP,
            channel_index=channel_index,
            timeout_ms=timeout_ms,
            hop_limit=request.hop_limit,
            to_int_fn=to_int_fn,
        )
    except ValueError as exc:
        return _error_response(
            request,
            summary_label="telemetry",
            detail=str(exc),
        )
    except Exception as exc:
        return _error_response(
            request,
            summary_label="telemetry",
            detail=f"Telemetry request failed: {exc}",
        )

    if response_packet is None:
        return {
            "ok": False,
            "command": "request_telemetry",
            "destination": destination,
            "channel_index": channel_index,
            "hop_limit": request.hop_limit,
            "sent_packet_id": sent_packet_id,
            "telemetry_type": telemetry_type,
            "error": "Timed out waiting for telemetry response",
            "console_lines": [f"[telemetry] {destination} | timed out waiting for response"],
        }

    routing_error = _routing_error_reason(response_packet)
    if routing_error == "NO_RESPONSE":
        return {
            "ok": False,
            "command": "request_telemetry",
            "destination": destination,
            "channel_index": channel_index,
            "hop_limit": request.hop_limit,
            "sent_packet_id": sent_packet_id,
            "telemetry_type": telemetry_type,
            "error": "Destination did not respond",
            "console_lines": [f"[telemetry] {destination} | destination did not respond"],
        }
    if routing_error:
        return {
            "ok": False,
            "command": "request_telemetry",
            "destination": destination,
            "channel_index": channel_index,
            "hop_limit": request.hop_limit,
            "sent_packet_id": sent_packet_id,
            "telemetry_type": telemetry_type,
            "error": f"Telemetry request failed: {routing_error}",
            "console_lines": [f"[telemetry] {destination} | error={routing_error}"],
        }

    decoded = response_packet.get("decoded") if isinstance(response_packet, dict) else None
    if not isinstance(decoded, dict) or not _portnum_matches(decoded.get("portnum"), "TELEMETRY_APP"):
        return {
            "ok": False,
            "command": "request_telemetry",
            "destination": destination,
            "channel_index": channel_index,
            "hop_limit": request.hop_limit,
            "sent_packet_id": sent_packet_id,
            "telemetry_type": telemetry_type,
            "error": "Invalid telemetry response payload",
            "console_lines": [f"[telemetry] {destination} | invalid response payload"],
        }

    try:
        telemetry_payload = _parse_telemetry_response_payload(decoded.get("payload"), telemetry_pb2)
    except Exception as exc:
        return {
            "ok": False,
            "command": "request_telemetry",
            "destination": destination,
            "channel_index": channel_index,
            "hop_limit": request.hop_limit,
            "sent_packet_id": sent_packet_id,
            "telemetry_type": telemetry_type,
            "error": f"Malformed telemetry response: {exc}",
            "console_lines": [f"[telemetry] {destination} | malformed response payload"],
        }

    response_type = ""
    response_metrics: object = {}
    if isinstance(telemetry_payload, dict):
        for key, value in telemetry_payload.items():
            if key == "time":
                continue
            response_type = str(key).strip()
            response_metrics = value
            break

    console_parts = [
        f"[telemetry] {destination}",
        f"type={telemetry_type}",
    ]
    if response_type:
        console_parts.append(f"response={response_type}")
    if isinstance(response_metrics, dict):
        preview = []
        for key, value in list(response_metrics.items())[:3]:
            preview.append(f"{key}={value}")
        if preview:
            console_parts.append(", ".join(preview))

    return {
        "ok": True,
        "command": "request_telemetry",
        "destination": destination,
        "channel_index": channel_index,
        "hop_limit": request.hop_limit,
        "sent_packet_id": sent_packet_id,
        "telemetry_type": telemetry_type,
        "result": {
            "requested_type": telemetry_type,
            "response_type": response_type or None,
            "response": telemetry_payload if telemetry_payload else {},
        },
        "console_lines": [" | ".join(console_parts)],
    }


def _preview_console_text(value: object, *, max_len: int = 80) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return f"{text[:max_len - 3]}..."


def _run_send_text(
    request: NetworkToolRequest,
    *,
    iface: object,
    send_lock,
    to_int_fn=to_int,
) -> dict[str, object]:
    destination = str(request.destination or "").strip()
    if not destination:
        raise ValueError("Missing destination")

    text = str(request.text or "").strip()
    if not text:
        return _error_response(
            request,
            summary_label="sendtext",
            detail="Missing message text",
        )

    channel_pb2, _mesh_pb2, portnums_pb2, _telemetry_pb2 = _load_meshtastic_modules()
    channel_index = request.channel_index if request.channel_index is not None else 0
    if not _channel_is_enabled(iface, channel_index, channel_pb2):
        return _error_response(
            request,
            summary_label="sendtext",
            detail=f"Channel {channel_index} is not enabled on the local node",
        )

    send_text = getattr(iface, "sendText", None)
    if not callable(send_text):
        return _error_response(
            request,
            summary_label="sendtext",
            detail="Connected interface does not support sendText()",
        )

    try:
        kwargs: dict[str, object] = {
            "destinationId": destination,
            "channelIndex": channel_index,
            "wantAck": False,
            "wantResponse": False,
        }
        if request.hop_limit is not None:
            kwargs["hopLimit"] = request.hop_limit
        with send_lock:
            sent_packet = send_text(text, **kwargs)
        sent_packet_id = to_int_fn(getattr(sent_packet, "id", None))
    except ValueError as exc:
        return _error_response(
            request,
            summary_label="sendtext",
            detail=str(exc),
        )
    except Exception as exc:
        return _error_response(
            request,
            summary_label="sendtext",
            detail=f"Text send failed: {exc}",
        )

    preview = _preview_console_text(text).replace('"', "'")
    console_parts = [
        f"[sendtext] {destination}",
        f'text="{preview}"',
        f"ch={channel_index}",
    ]
    if request.hop_limit is not None:
        console_parts.append(f"hop={request.hop_limit}")

    return {
        "ok": True,
        "command": "send_text",
        "destination": destination,
        "channel_index": channel_index,
        "hop_limit": request.hop_limit,
        "sent_packet_id": sent_packet_id,
        "result": {
            "text": text,
        },
        "console_lines": [" | ".join(console_parts)],
    }


def _resolve_remote_node(
    iface: object,
    destination: str,
) -> object:
    get_node = getattr(iface, "getNode", None)
    if not callable(get_node):
        raise ValueError("Connected interface does not support getNode()")
    try:
        return get_node(
            destination,
            requestChannels=False,
            requestChannelAttempts=0,
            timeout=15,
        )
    except TypeError:
        try:
            return get_node(destination, False, 0, 15)
        except TypeError:
            return get_node(destination)


def _run_request_config(
    request: NetworkToolRequest,
    *,
    iface: object,
    send_lock,
) -> dict[str, object]:
    destination = str(request.destination or "").strip()
    if not destination:
        raise ValueError("Missing destination")

    try:
        config_type_name = _normalize_request_config_type(request.config_type)
    except ValueError as exc:
        return _error_response(
            request,
            summary_label="config",
            detail=str(exc),
        )

    config_value = _REQUEST_CONFIG_TYPE_ENUM_VALUES.get(config_type_name)
    if config_value is None:
        return _error_response(
            request,
            summary_label="config",
            detail=f"Unsupported config type: {config_type_name}",
        )

    try:
        node = _resolve_remote_node(iface, destination)
        request_config = getattr(node, "requestConfig", None)
        if not callable(request_config):
            raise ValueError("Target node does not support requestConfig()")
        with send_lock:
            request_config(config_value)
    except ValueError as exc:
        return _error_response(
            request,
            summary_label="config",
            detail=str(exc),
        )
    except Exception as exc:
        return _error_response(
            request,
            summary_label="config",
            detail=f"Config request failed: {exc}",
        )

    return {
        "ok": True,
        "command": "request_config",
        "destination": destination,
        "config_type": config_type_name,
        "console_lines": [f"[config] {destination} | requested {config_type_name}"],
    }


def _run_request_channels(
    request: NetworkToolRequest,
    *,
    iface: object,
    send_lock,
) -> dict[str, object]:
    destination = str(request.destination or "").strip()
    if not destination:
        raise ValueError("Missing destination")

    starting_index = request.starting_index if request.starting_index is not None else 0

    try:
        node = _resolve_remote_node(iface, destination)
        request_channels = getattr(node, "requestChannels", None)
        if not callable(request_channels):
            raise ValueError("Target node does not support requestChannels()")
        with send_lock:
            try:
                request_channels(startingIndex=starting_index)
            except TypeError:
                request_channels(starting_index)
    except ValueError as exc:
        return _error_response(
            request,
            summary_label="channels",
            detail=str(exc),
        )
    except Exception as exc:
        return _error_response(
            request,
            summary_label="channels",
            detail=f"Channel request failed: {exc}",
        )

    return {
        "ok": True,
        "command": "request_channels",
        "destination": destination,
        "starting_index": starting_index,
        "console_lines": [f"[channels] {destination} | requested from index {starting_index}"],
    }


def _run_device_metadata(
    request: NetworkToolRequest,
    *,
    iface: object,
    send_lock,
) -> dict[str, object]:
    destination = str(request.destination or "").strip()
    if not destination:
        raise ValueError("Missing destination")

    try:
        node = _resolve_remote_node(iface, destination)
        get_metadata = getattr(node, "getMetadata", None)
        if not callable(get_metadata):
            raise ValueError("Target node does not support getMetadata()")
        with send_lock:
            get_metadata()
    except ValueError as exc:
        return _error_response(
            request,
            summary_label="metadata",
            detail=str(exc),
        )
    except Exception as exc:
        return _error_response(
            request,
            summary_label="metadata",
            detail=f"Metadata request failed: {exc}",
        )

    return {
        "ok": True,
        "command": "device_metadata",
        "destination": destination,
        "console_lines": [f"[device-metadata] {destination} | request sent"],
    }


def _require_dangerous_confirm(
    request: NetworkToolRequest,
    *,
    summary_label: str,
    command_name: str,
) -> dict[str, object] | None:
    if request.confirm is True:
        return None
    return _error_response(
        request,
        summary_label=summary_label,
        detail=f'Refusing to run dangerous command without confirmation (use "{command_name} ... --confirm")',
    )


def _run_reset_nodedb(
    request: NetworkToolRequest,
    *,
    iface: object,
    send_lock,
    to_int_fn=to_int,
) -> dict[str, object]:
    destination = str(request.destination or "").strip()
    if not destination:
        raise ValueError("Missing destination")

    confirm_error = _require_dangerous_confirm(
        request,
        summary_label="reset-nodedb",
        command_name="reset-nodedb",
    )
    if confirm_error is not None:
        return confirm_error

    try:
        node = _resolve_remote_node(iface, destination)
        reset_nodedb = getattr(node, "resetNodeDb", None)
        if not callable(reset_nodedb):
            raise ValueError("Target node does not support resetNodeDb()")
        with send_lock:
            sent_packet = reset_nodedb()
        sent_packet_id = to_int_fn(getattr(sent_packet, "id", None))
    except ValueError as exc:
        return _error_response(
            request,
            summary_label="reset-nodedb",
            detail=str(exc),
        )
    except Exception as exc:
        return _error_response(
            request,
            summary_label="reset-nodedb",
            detail=f"Reset NodeDB failed: {exc}",
        )

    return {
        "ok": True,
        "command": "reset_nodedb",
        "destination": destination,
        "confirm": True,
        "sent_packet_id": sent_packet_id,
        "console_lines": [f"[reset-nodedb] {destination} | request sent"],
    }


def _run_factory_reset_common(
    request: NetworkToolRequest,
    *,
    iface: object,
    send_lock,
    full_device: bool,
    to_int_fn=to_int,
) -> dict[str, object]:
    destination = str(request.destination or "").strip()
    if not destination:
        raise ValueError("Missing destination")

    command_label = "factory-reset-device" if full_device else "factory-reset"
    confirm_error = _require_dangerous_confirm(
        request,
        summary_label=command_label,
        command_name=command_label,
    )
    if confirm_error is not None:
        return confirm_error

    try:
        node = _resolve_remote_node(iface, destination)
        factory_reset = getattr(node, "factoryReset", None)
        if not callable(factory_reset):
            raise ValueError("Target node does not support factoryReset()")
        with send_lock:
            sent_packet = factory_reset(full=full_device)
        sent_packet_id = to_int_fn(getattr(sent_packet, "id", None))
    except ValueError as exc:
        return _error_response(
            request,
            summary_label=command_label,
            detail=str(exc),
        )
    except Exception as exc:
        return _error_response(
            request,
            summary_label=command_label,
            detail=f"Factory reset failed: {exc}",
        )

    command_name = "factory_reset_device" if full_device else "factory_reset"
    return {
        "ok": True,
        "command": command_name,
        "destination": destination,
        "confirm": True,
        "sent_packet_id": sent_packet_id,
        "result": {
            "full_device": bool(full_device),
        },
        "console_lines": [f"[{command_label}] {destination} | request sent"],
    }


def _run_factory_reset(
    request: NetworkToolRequest,
    *,
    iface: object,
    send_lock,
    to_int_fn=to_int,
) -> dict[str, object]:
    return _run_factory_reset_common(
        request,
        iface=iface,
        send_lock=send_lock,
        full_device=False,
        to_int_fn=to_int_fn,
    )


def _run_factory_reset_device(
    request: NetworkToolRequest,
    *,
    iface: object,
    send_lock,
    to_int_fn=to_int,
) -> dict[str, object]:
    return _run_factory_reset_common(
        request,
        iface=iface,
        send_lock=send_lock,
        full_device=True,
        to_int_fn=to_int_fn,
    )


def _run_send_alert(
    request: NetworkToolRequest,
    *,
    iface: object,
    send_lock,
    to_int_fn=to_int,
) -> dict[str, object]:
    destination = str(request.destination or "").strip()
    if not destination:
        raise ValueError("Missing destination")

    alert_text = str(request.text or "").strip()
    if not alert_text:
        return _error_response(
            request,
            summary_label="alert",
            detail="Missing alert text",
        )

    channel_pb2, _mesh_pb2, _portnums_pb2, _telemetry_pb2 = _load_meshtastic_modules()
    channel_index = request.channel_index if request.channel_index is not None else 0
    if not _channel_is_enabled(iface, channel_index, channel_pb2):
        return _error_response(
            request,
            summary_label="alert",
            detail=f"Channel {channel_index} is not enabled on the local node",
        )

    try:
        alert_port = getattr(getattr(_portnums_pb2, "PortNum", None), "ALERT_APP", None)
        if alert_port is not None:
            sent_packet_id = _send_mesh_packet(
                iface=iface,
                send_lock=send_lock,
                message=alert_text.encode("utf-8"),
                destination=destination,
                port_num=alert_port,
                channel_index=channel_index,
                hop_limit=request.hop_limit,
                to_int_fn=to_int_fn,
            )
        else:
            send_alert = getattr(iface, "sendAlert", None)
            if not callable(send_alert):
                return _error_response(
                    request,
                    summary_label="alert",
                    detail="Connected interface does not support ALERT_APP send",
                )
            kwargs: dict[str, object] = {
                "destinationId": destination,
                "channelIndex": channel_index,
            }
            if request.hop_limit is not None:
                kwargs["hopLimit"] = request.hop_limit
            with send_lock:
                sent_packet = send_alert(alert_text, **kwargs)
            sent_packet_id = to_int_fn(getattr(sent_packet, "id", None))
    except ValueError as exc:
        return _error_response(
            request,
            summary_label="alert",
            detail=str(exc),
        )
    except Exception as exc:
        return _error_response(
            request,
            summary_label="alert",
            detail=f"Alert send failed: {exc}",
        )

    preview = _preview_console_text(alert_text).replace('"', "'")
    console_parts = [
        f"[alert] {destination}",
        f'text="{preview}"',
        f"ch={channel_index}",
    ]
    if request.hop_limit is not None:
        console_parts.append(f"hop={request.hop_limit}")

    return {
        "ok": True,
        "command": "send_alert",
        "destination": destination,
        "channel_index": channel_index,
        "hop_limit": request.hop_limit,
        "sent_packet_id": sent_packet_id,
        "result": {
            "text": alert_text,
        },
        "console_lines": [" | ".join(console_parts)],
    }


def _run_reboot(
    request: NetworkToolRequest,
    *,
    iface: object,
    send_lock,
    to_int_fn=to_int,
) -> dict[str, object]:
    destination = str(request.destination or "").strip()
    if not destination:
        raise ValueError("Missing destination")

    delay_seconds = request.delay_seconds if request.delay_seconds is not None else 10
    if delay_seconds < 0:
        return _error_response(
            request,
            summary_label="reboot",
            detail="delay_seconds must be >= 0",
        )

    try:
        node = _resolve_remote_node(iface, destination)
        reboot_fn = getattr(node, "reboot", None)
        if not callable(reboot_fn):
            raise ValueError("Target node does not support reboot()")
        with send_lock:
            sent_packet = reboot_fn(secs=delay_seconds)
        sent_packet_id = to_int_fn(getattr(sent_packet, "id", None))
    except ValueError as exc:
        return _error_response(
            request,
            summary_label="reboot",
            detail=str(exc),
        )
    except Exception as exc:
        return _error_response(
            request,
            summary_label="reboot",
            detail=f"Reboot request failed: {exc}",
        )

    return {
        "ok": True,
        "command": "reboot",
        "destination": destination,
        "delay_seconds": delay_seconds,
        "sent_packet_id": sent_packet_id,
        "console_lines": [f"[reboot] {destination} | scheduled reboot in {delay_seconds}s"],
    }


def _run_shutdown(
    request: NetworkToolRequest,
    *,
    iface: object,
    send_lock,
    to_int_fn=to_int,
) -> dict[str, object]:
    destination = str(request.destination or "").strip()
    if not destination:
        raise ValueError("Missing destination")

    delay_seconds = request.delay_seconds if request.delay_seconds is not None else 10
    if delay_seconds < 0:
        return _error_response(
            request,
            summary_label="shutdown",
            detail="delay_seconds must be >= 0",
        )

    try:
        node = _resolve_remote_node(iface, destination)
        shutdown_fn = getattr(node, "shutdown", None)
        if not callable(shutdown_fn):
            raise ValueError("Target node does not support shutdown()")
        with send_lock:
            sent_packet = shutdown_fn(secs=delay_seconds)
        sent_packet_id = to_int_fn(getattr(sent_packet, "id", None))
    except ValueError as exc:
        return _error_response(
            request,
            summary_label="shutdown",
            detail=str(exc),
        )
    except Exception as exc:
        return _error_response(
            request,
            summary_label="shutdown",
            detail=f"Shutdown request failed: {exc}",
        )

    return {
        "ok": True,
        "command": "shutdown",
        "destination": destination,
        "delay_seconds": delay_seconds,
        "sent_packet_id": sent_packet_id,
        "console_lines": [f"[shutdown] {destination} | scheduled shutdown in {delay_seconds}s"],
    }


def _run_set_time(
    request: NetworkToolRequest,
    *,
    iface: object,
    send_lock,
    to_int_fn=to_int,
) -> dict[str, object]:
    destination = str(request.destination or "").strip()
    if not destination:
        raise ValueError("Missing destination")

    time_sec = request.time_sec if request.time_sec is not None else int(time.time())
    if time_sec < 1:
        return _error_response(
            request,
            summary_label="set-time",
            detail="time_sec must be >= 1",
        )

    try:
        node = _resolve_remote_node(iface, destination)
        set_time_fn = getattr(node, "setTime", None)
        if not callable(set_time_fn):
            raise ValueError("Target node does not support setTime()")
        with send_lock:
            sent_packet = set_time_fn(timeSec=time_sec)
        sent_packet_id = to_int_fn(getattr(sent_packet, "id", None))
    except ValueError as exc:
        return _error_response(
            request,
            summary_label="set-time",
            detail=str(exc),
        )
    except Exception as exc:
        return _error_response(
            request,
            summary_label="set-time",
            detail=f"Set-time request failed: {exc}",
        )

    return {
        "ok": True,
        "command": "set_time",
        "destination": destination,
        "time_sec": time_sec,
        "sent_packet_id": sent_packet_id,
        "console_lines": [f"[set-time] {destination} | epoch={time_sec}"],
    }


def _run_request_position(
    request: NetworkToolRequest,
    *,
    iface: object,
    send_lock,
    to_int_fn=to_int,
) -> dict[str, object]:
    destination = str(request.destination or "").strip()
    if not destination:
        raise ValueError("Missing destination")

    channel_pb2, mesh_pb2, portnums_pb2, _telemetry_pb2 = _load_meshtastic_modules()
    channel_index = request.channel_index if request.channel_index is not None else 0
    timeout_ms = request.timeout_ms if request.timeout_ms is not None else 8000
    if not _channel_is_enabled(iface, channel_index, channel_pb2):
        return _error_response(
            request,
            summary_label="position",
            detail=f"Channel {channel_index} is not enabled on the local node",
        )

    position_request = mesh_pb2.Position()
    try:
        sent_packet_id, response_packet = _send_mesh_request(
            iface=iface,
            send_lock=send_lock,
            message=position_request,
            destination=destination,
            port_num=portnums_pb2.PortNum.POSITION_APP,
            channel_index=channel_index,
            timeout_ms=timeout_ms,
            to_int_fn=to_int_fn,
        )
    except ValueError as exc:
        return _error_response(
            request,
            summary_label="position",
            detail=str(exc),
        )
    except Exception as exc:
        return _error_response(
            request,
            summary_label="position",
            detail=f"Position request failed: {exc}",
        )

    if response_packet is None:
        return {
            "ok": False,
            "command": "request_position",
            "destination": destination,
            "channel_index": channel_index,
            "sent_packet_id": sent_packet_id,
            "error": "Timed out waiting for position response",
            "console_lines": [f"[position] {destination} | timed out waiting for response"],
        }

    routing_error = _routing_error_reason(response_packet)
    if routing_error:
        return {
            "ok": False,
            "command": "request_position",
            "destination": destination,
            "channel_index": channel_index,
            "sent_packet_id": sent_packet_id,
            "error": f"Position request failed: {routing_error}",
            "console_lines": [f"[position] {destination} | error={routing_error}"],
        }

    decoded = response_packet.get("decoded") if isinstance(response_packet, dict) else None
    if not isinstance(decoded, dict) or not _portnum_matches(decoded.get("portnum"), "POSITION_APP"):
        return {
            "ok": False,
            "command": "request_position",
            "destination": destination,
            "channel_index": channel_index,
            "sent_packet_id": sent_packet_id,
            "error": "Invalid position response payload",
            "console_lines": [f"[position] {destination} | invalid response payload"],
        }

    payload = decoded.get("payload")
    if not isinstance(payload, (bytes, bytearray)):
        return {
            "ok": False,
            "command": "request_position",
            "destination": destination,
            "channel_index": channel_index,
            "sent_packet_id": sent_packet_id,
            "error": "Position response payload missing",
            "console_lines": [f"[position] {destination} | response payload missing"],
        }

    position = mesh_pb2.Position()
    position.ParseFromString(bytes(payload))
    latitude_i = to_int_fn(getattr(position, "latitude_i", None))
    longitude_i = to_int_fn(getattr(position, "longitude_i", None))
    altitude = to_int_fn(getattr(position, "altitude", None))
    precision_bits = to_int_fn(getattr(position, "precision_bits", None))
    lat = (latitude_i * 1e-7) if latitude_i not in (None, 0) else None
    lon = (longitude_i * 1e-7) if longitude_i not in (None, 0) else None
    position_disabled = precision_bits == 0

    console_parts = [f"[position] {destination}"]
    if lat is not None and lon is not None:
        console_parts.append(f"lat={lat:.6f} lon={lon:.6f}")
    else:
        console_parts.append("lat=n/a lon=n/a")
    if altitude not in (None, 0):
        console_parts.append(f"alt={altitude}m")
    if precision_bits is not None:
        console_parts.append(f"precision={precision_bits}")

    return {
        "ok": True,
        "command": "request_position",
        "destination": destination,
        "channel_index": channel_index,
        "sent_packet_id": sent_packet_id,
        "result": {
            "lat": lat,
            "lon": lon,
            "altitude": altitude if altitude not in (None, 0) else None,
            "precision_bits": precision_bits,
            "position_disabled": position_disabled,
        },
        "console_lines": [" | ".join(console_parts)],
    }


def _resolve_iface_node_id(
    iface: object,
    node_num: object,
    *,
    prefer_local_alias: bool = False,
    to_int_fn=to_int,
) -> str:
    numeric = to_int_fn(node_num)
    if numeric is None or numeric < 0:
        return "unknown"
    if prefer_local_alias:
        return "!local"

    node_num_to_id = getattr(iface, "_nodeNumToId", None)
    if callable(node_num_to_id):
        try:
            resolved = node_num_to_id(numeric, False)
        except TypeError:
            resolved = node_num_to_id(numeric)
        except Exception:
            resolved = None
        clean = str(resolved or "").strip()
        if clean and clean.lower() != "unknown":
            return clean

    return f"!{numeric & 0xFFFFFFFF:08x}"


def _traceroute_default_hop_limit(iface: object, *, to_int_fn=to_int) -> int:
    local_node = getattr(iface, "localNode", None)
    local_config = getattr(local_node, "localConfig", None)
    lora = getattr(local_config, "lora", None)
    hop_limit = to_int_fn(getattr(lora, "hop_limit", None))
    if hop_limit is None or hop_limit < 1:
        return 3
    return hop_limit


def _traceroute_default_timeout_ms(hop_limit: int) -> int:
    return max(12000, 2000 + (max(1, hop_limit) * 2000))


def _normalize_traceroute_snr(raw_value: object, *, to_int_fn=to_int) -> float | None:
    numeric = to_int_fn(raw_value)
    if numeric is None or numeric == -128:
        return None
    return float(numeric) / 4.0


def _build_traceroute_path(
    iface: object,
    *,
    route_nodes: object,
    snr_values: object,
    final_node_num: object,
    final_prefer_local_alias: bool = False,
    to_int_fn=to_int,
) -> list[dict[str, object]]:
    route_list = list(route_nodes or [])
    snr_list = list(snr_values or [])
    nodes = route_list + [final_node_num]
    path: list[dict[str, object]] = []
    for index, node_num in enumerate(nodes):
        prefer_local_alias = final_prefer_local_alias and index == (len(nodes) - 1)
        path.append(
            {
                "node": _resolve_iface_node_id(
                    iface,
                    node_num,
                    prefer_local_alias=prefer_local_alias,
                    to_int_fn=to_int_fn,
                ),
                "snr_db": _normalize_traceroute_snr(
                    snr_list[index] if index < len(snr_list) else None,
                    to_int_fn=to_int_fn,
                ),
            }
        )
    return path


def _format_traceroute_path_line(
    *,
    label: str,
    start_node: str,
    hops: list[dict[str, object]],
) -> str:
    parts = [f"[traceroute] {label}: {start_node}"]
    for hop in hops:
        node = str(hop.get("node") or "unknown").strip() or "unknown"
        snr_db = hop.get("snr_db")
        if isinstance(snr_db, (int, float)):
            parts.append(f"{node} ({float(snr_db):.1f}dB)")
        else:
            parts.append(f"{node} (?)")
    return " -> ".join(parts)


def _run_traceroute(
    request: NetworkToolRequest,
    *,
    iface: object,
    send_lock,
    to_int_fn=to_int,
) -> dict[str, object]:
    destination = str(request.destination or "").strip()
    if not destination:
        raise ValueError("Missing destination")

    channel_pb2, mesh_pb2, portnums_pb2, _telemetry_pb2 = _load_meshtastic_modules()
    channel_index = request.channel_index if request.channel_index is not None else 0
    hop_limit = request.hop_limit if request.hop_limit is not None else _traceroute_default_hop_limit(
        iface,
        to_int_fn=to_int_fn,
    )
    timeout_ms = request.timeout_ms if request.timeout_ms is not None else _traceroute_default_timeout_ms(
        hop_limit
    )

    if not _channel_is_enabled(iface, channel_index, channel_pb2):
        return _error_response(
            request,
            summary_label="traceroute",
            detail=f"Channel {channel_index} is not enabled on the local node",
        )

    route_request = mesh_pb2.RouteDiscovery()
    try:
        sent_packet_id, response_packet = _send_mesh_request(
            iface=iface,
            send_lock=send_lock,
            message=route_request,
            destination=destination,
            port_num=portnums_pb2.PortNum.TRACEROUTE_APP,
            channel_index=channel_index,
            timeout_ms=timeout_ms,
            hop_limit=hop_limit,
            to_int_fn=to_int_fn,
        )
    except ValueError as exc:
        return _error_response(
            request,
            summary_label="traceroute",
            detail=str(exc),
        )
    except Exception as exc:
        return _error_response(
            request,
            summary_label="traceroute",
            detail=f"Traceroute failed: {exc}",
        )

    if response_packet is None:
        return {
            "ok": False,
            "command": "traceroute",
            "destination": destination,
            "channel_index": channel_index,
            "hop_limit": hop_limit,
            "sent_packet_id": sent_packet_id,
            "error": "Timed out waiting for traceroute response",
            "console_lines": [f"[traceroute] {destination} | timed out waiting for response"],
        }

    routing_error = _routing_error_reason(response_packet)
    if routing_error == "NO_RESPONSE":
        return {
            "ok": False,
            "command": "traceroute",
            "destination": destination,
            "channel_index": channel_index,
            "hop_limit": hop_limit,
            "sent_packet_id": sent_packet_id,
            "error": "Destination did not respond",
            "console_lines": [f"[traceroute] {destination} | destination did not respond"],
        }
    if routing_error:
        return {
            "ok": False,
            "command": "traceroute",
            "destination": destination,
            "channel_index": channel_index,
            "hop_limit": hop_limit,
            "sent_packet_id": sent_packet_id,
            "error": f"Traceroute failed: {routing_error}",
            "console_lines": [f"[traceroute] {destination} | error={routing_error}"],
        }

    decoded = response_packet.get("decoded") if isinstance(response_packet, dict) else None
    if not isinstance(decoded, dict) or not _portnum_matches(decoded.get("portnum"), "TRACEROUTE_APP"):
        return {
            "ok": False,
            "command": "traceroute",
            "destination": destination,
            "channel_index": channel_index,
            "hop_limit": hop_limit,
            "sent_packet_id": sent_packet_id,
            "error": "Invalid traceroute response payload",
            "console_lines": [f"[traceroute] {destination} | invalid response payload"],
        }

    payload = decoded.get("payload")
    if not isinstance(payload, (bytes, bytearray)):
        return {
            "ok": False,
            "command": "traceroute",
            "destination": destination,
            "channel_index": channel_index,
            "hop_limit": hop_limit,
            "sent_packet_id": sent_packet_id,
            "error": "Traceroute response payload missing",
            "console_lines": [f"[traceroute] {destination} | response payload missing"],
        }

    route_response = mesh_pb2.RouteDiscovery()
    try:
        route_response.ParseFromString(bytes(payload))
    except Exception as exc:
        return {
            "ok": False,
            "command": "traceroute",
            "destination": destination,
            "channel_index": channel_index,
            "hop_limit": hop_limit,
            "sent_packet_id": sent_packet_id,
            "error": f"Malformed traceroute response: {exc}",
            "console_lines": [f"[traceroute] {destination} | malformed response payload"],
        }

    towards = _build_traceroute_path(
        iface,
        route_nodes=getattr(route_response, "route", []),
        snr_values=getattr(route_response, "snr_towards", []),
        final_node_num=response_packet.get("from") if isinstance(response_packet, dict) else None,
        to_int_fn=to_int_fn,
    )
    back_route_nodes = getattr(route_response, "route_back", [])
    back_snr_values = getattr(route_response, "snr_back", [])
    has_back_path = bool(back_route_nodes) or bool(back_snr_values) or (
        isinstance(response_packet, dict) and "hopStart" in response_packet
    )
    back = _build_traceroute_path(
        iface,
        route_nodes=back_route_nodes,
        snr_values=back_snr_values,
        final_node_num=response_packet.get("to") if isinstance(response_packet, dict) else None,
        final_prefer_local_alias=True,
        to_int_fn=to_int_fn,
    ) if has_back_path else []

    towards_start = _resolve_iface_node_id(
        iface,
        response_packet.get("to") if isinstance(response_packet, dict) else None,
        prefer_local_alias=True,
        to_int_fn=to_int_fn,
    )
    towards_line = _format_traceroute_path_line(
        label="towards",
        start_node=towards_start,
        hops=towards,
    )
    console_lines = [towards_line]

    if back:
        back_start = _resolve_iface_node_id(
            iface,
            response_packet.get("from") if isinstance(response_packet, dict) else None,
            to_int_fn=to_int_fn,
        )
        console_lines.append(
            _format_traceroute_path_line(
                label="back",
                start_node=back_start,
                hops=back,
            )
        )

    return {
        "ok": True,
        "command": "traceroute",
        "destination": destination,
        "channel_index": channel_index,
        "hop_limit": hop_limit,
        "sent_packet_id": sent_packet_id,
        "result": {
            "towards": towards,
            "back": back,
        },
        "console_lines": console_lines,
    }


def run_network_tool(
    request: NetworkToolRequest,
    *,
    iface: object,
    send_lock,
    to_int_fn=to_int,
) -> dict[str, object]:
    if request.command == "nodes":
        return {
            "ok": False,
            "command": "nodes",
            "error": "nodes is handled frontend-only in v1",
            "console_lines": [
                "[nodes] handled frontend-only in v1. Use the console nodes aliases instead.",
            ],
        }
    if request.command == "send_node_info":
        return _run_send_node_info(
            request,
            iface=iface,
            send_lock=send_lock,
            to_int_fn=to_int_fn,
        )
    if request.command == "send_text":
        return _run_send_text(
            request,
            iface=iface,
            send_lock=send_lock,
            to_int_fn=to_int_fn,
        )
    if request.command == "ping":
        return _run_ping(
            request,
            iface=iface,
            send_lock=send_lock,
            to_int_fn=to_int_fn,
        )
    if request.command == "request_position":
        return _run_request_position(
            request,
            iface=iface,
            send_lock=send_lock,
            to_int_fn=to_int_fn,
        )
    if request.command == "request_telemetry":
        return _run_request_telemetry(
            request,
            iface=iface,
            send_lock=send_lock,
            to_int_fn=to_int_fn,
        )
    if request.command == "send_alert":
        return _run_send_alert(
            request,
            iface=iface,
            send_lock=send_lock,
            to_int_fn=to_int_fn,
        )
    if request.command == "request_config":
        return _run_request_config(
            request,
            iface=iface,
            send_lock=send_lock,
        )
    if request.command == "request_channels":
        return _run_request_channels(
            request,
            iface=iface,
            send_lock=send_lock,
        )
    if request.command == "device_metadata":
        return _run_device_metadata(
            request,
            iface=iface,
            send_lock=send_lock,
        )
    if request.command == "reset_nodedb":
        return _run_reset_nodedb(
            request,
            iface=iface,
            send_lock=send_lock,
            to_int_fn=to_int_fn,
        )
    if request.command == "factory_reset":
        return _run_factory_reset(
            request,
            iface=iface,
            send_lock=send_lock,
            to_int_fn=to_int_fn,
        )
    if request.command == "factory_reset_device":
        return _run_factory_reset_device(
            request,
            iface=iface,
            send_lock=send_lock,
            to_int_fn=to_int_fn,
        )
    if request.command == "reboot":
        return _run_reboot(
            request,
            iface=iface,
            send_lock=send_lock,
            to_int_fn=to_int_fn,
        )
    if request.command == "shutdown":
        return _run_shutdown(
            request,
            iface=iface,
            send_lock=send_lock,
            to_int_fn=to_int_fn,
        )
    if request.command == "set_time":
        return _run_set_time(
            request,
            iface=iface,
            send_lock=send_lock,
            to_int_fn=to_int_fn,
        )
    if request.command == "traceroute":
        return _run_traceroute(
            request,
            iface=iface,
            send_lock=send_lock,
            to_int_fn=to_int_fn,
        )
    raise ValueError(f"Unsupported network tool command: {request.command}")


__all__ = ["run_network_tool"]
