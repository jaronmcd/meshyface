import base64
import io
import json
import re
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest
from google.protobuf.json_format import MessageToDict
from meshtastic.protobuf import mesh_pb2, portnums_pb2

import meshdash.meshyface_profile as meshyface_profile_protocol
import meshdash.tracker_runtime_impl as tracker_runtime_impl
from meshdash.api_input_meshyface_profile import parse_meshyface_profile_theme_request
from meshdash.helpers import to_int
from meshdash.html_css import build_dashboard_css
from meshdash.html_js import build_dashboard_js
from meshdash.html_template import render_html
from meshdash.history_store_runtime import HistoryStore
from meshdash.http_api import make_http_handler
from meshdash.http_api_post import build_post_route_dependencies
from meshdash.http_routes_post import handle_dashboard_post
from meshdash.meshyface_profile import (
    DEFAULT_MESHYFACE_PROFILE_PORTNUM,
    MESHYFACE_PROFILE_GHOST_BLEND_MAX,
    MESHYFACE_PROFILE_GHOST_JUSTIFY_DEFAULT,
    MESHYFACE_PROFILE_GHOST_TILT_DEFAULT,
    MESHYFACE_PROFILE_GHOST_TEXT_MAX_BYTES,
    MESHYFACE_PROFILE_GHOST_TEXT_MAX_CHARS,
    MESHYFACE_PROFILE_MAX_PAYLOAD_BYTES,
    MESHYFACE_THEME_RECIPE_BYTES,
    MESHYFACE_THEME_RECIPE_ENCODED_LENGTH,
    build_meshyface_theme_render,
    build_meshyface_profile_payload,
    decode_meshyface_theme_recipe,
    encode_meshyface_theme_recipe,
    parse_meshyface_profile_packet,
)
from meshdash.revision import RevisionInfo
from meshdash.services_meshyface_profile import send_meshyface_profile_theme
from meshdash.state_node_contracts import CollectedNodes
from meshdash.state_service import build_dashboard_state_lite, build_dashboard_state_typed
from meshdash.tracker_runtime_impl import DashboardTracker
from meshdash.tracker_snapshot_contracts import empty_tracker_snapshot


class _FakeHandler:
    def __init__(self, body: bytes = b"", *, headers: dict[str, object] | None = None) -> None:
        self.path = "/api/meshyface/profile/theme"
        self.headers = headers or {}
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()

    def send_response(self, code: int) -> None:
        self._last_code = code

    def send_header(self, key: str, value: str) -> None:
        pass

    def end_headers(self) -> None:
        pass


class _SentPacket:
    id = 1234


class _SendDataIface:
    def __init__(self) -> None:
        self.calls: list[tuple[bytes, dict[str, object]]] = []

    def sendData(self, data: bytes, **kwargs: object) -> _SentPacket:
        self.calls.append((data, kwargs))
        return _SentPacket()


def _theme_recipe(**overrides: object) -> dict[str, object]:
    recipe: dict[str, object] = {
        "version": 1,
        "base_color": "#123456",
        "line_color": "#abcdef",
        "line_contrast_color": "#fedcba",
        "gradient_primary_start_color": "#010203",
        "gradient_primary_end_color": "#f0e0d0",
        "color_depth": 73,
        "foreground_transparency": 42,
        "foreground_blur": 17,
        "text_font": "mono",
        "gradient_primary_type": "radial",
        "gradient_primary_direction": "down-left",
        "mode": "dark",
    }
    recipe.update(overrides)
    return recipe


def test_theme_render_reuses_sender_workspace_surface() -> None:
    render = build_meshyface_theme_render(
        _theme_recipe(
            base_color="#007aff",
            line_color="#0a84ff",
            line_contrast_color="#d8ecff",
            gradient_primary_start_color="#000000",
            gradient_primary_end_color="#000000",
            color_depth=76,
            foreground_transparency=51,
            foreground_blur=0,
            gradient_primary_type="linear",
            gradient_primary_direction="right",
            mode="dark",
        )
    )

    assert render == {
        "background_start_color": "#000000",
        "background_end_color": "#000000",
        "surface_color": "#105382",
        "surface_opacity": 49,
        "surface_hover_color": "#224f8e",
        "surface_hover_opacity": 49,
        "border_color": "#1ca6f6",
        "border_muted_color": "#1b8ed5",
    }


def test_theme_render_rejects_invalid_recipe() -> None:
    assert build_meshyface_theme_render({}) is None


class _StateTracker:
    radio_link_connected = None
    radio_link_changed_unix = None
    radio_link_error = None

    def snapshot(self, by_id: dict[str, dict[str, object]]) -> object:
        return empty_tracker_snapshot()

    def load_node_saved_counts(self) -> dict[str, dict[str, object]]:
        return {}

    def load_node_position_counts(self) -> dict[str, dict[str, object]]:
        return {}

    def load_node_capabilities(self) -> dict[str, dict[str, object]]:
        return {}

    def meshyface_profiles_snapshot(self) -> dict[str, dict[str, object]]:
        return {
            "!335d8354": {
                "node_id": "!335d8354",
                "updated_unix": 1_788_300_000,
                "received_unix": 1_788_300_010,
                "source": "mesh",
                "theme": _theme_recipe(),
                "ghost": {
                    "text": "73",
                    "blend": 23,
                    "effect": "glow",
                    "tilt": MESHYFACE_PROFILE_GHOST_TILT_DEFAULT,
                    "justify": MESHYFACE_PROFILE_GHOST_JUSTIFY_DEFAULT,
                    "fx": 61,
                },
            },
            "!bad": {"updated_unix": 1_788_300_000, "theme": _theme_recipe()},
            "!11111111": {
                "updated_unix": 1_788_300_000,
                "theme": _theme_recipe(base_color="abcdef"),
            },
            "!22222222": {
                "updated_unix": 1_788_300_000,
                "theme": _theme_recipe(version=2),
            },
        }


def _profile_packet(
    *,
    node_id: str = "!335d8354",
    sender_id: str | None = "!335d8354",
    updated_unix: int = 1_770_000_000,
    portnum: object = DEFAULT_MESHYFACE_PROFILE_PORTNUM,
    theme: object = None,
    ghost: object = None,
) -> dict[str, object]:
    packet: dict[str, object] = {
        "decoded": {
            "portnum": portnum,
            "payload": build_meshyface_profile_payload(
                node_id=node_id,
                updated_unix=updated_unix,
                theme=_theme_recipe() if theme is None else theme,
                ghost=ghost,
            ),
        }
    }
    if sender_id is not None:
        packet["fromId"] = sender_id
    return packet


def _open_history_store(path: Path) -> HistoryStore:
    return HistoryStore(
        db_path=str(path),
        max_rows=100,
        retention_days=30,
        event_max_rows=100,
        event_retention_days=30,
        rollup_retention_days=30,
    )


def _save_hex_profile_packet(
    store: HistoryStore,
    *,
    created_unix: int,
    node_id: str = "!335d8354",
    updated_unix: int = 1_788_300_000,
    theme: object = None,
) -> None:
    packet = _profile_packet(
        node_id=node_id,
        sender_id=node_id,
        updated_unix=updated_unix,
        theme=theme,
    )
    decoded = packet["decoded"]
    assert isinstance(decoded, dict)
    payload = decoded["payload"]
    assert isinstance(payload, bytes)
    # ``to_jsonable`` converts bytes to this exact historical packet_json
    # shape, which predates the dedicated meshyface_profiles table.
    legacy_packet = {
        "fromId": node_id,
        "decoded": {
            "portnum": decoded["portnum"],
            "payload": payload.hex(),
        },
    }
    with store._lock:
        store._conn.execute(
            "INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(?, ?, ?)",
            (created_unix, "{}", json.dumps(legacy_packet, separators=(",", ":"))),
        )
        store._conn.commit()


def _revision() -> RevisionInfo:
    return RevisionInfo(version="0.0.0", commit="test", label="test", title="test")


def _state_kwargs(tracker: object) -> dict[str, object]:
    return {
        "iface": object(),
        "tracker": tracker,
        "target": "test",
        "started_at": 1_800_000_000,
        "storage_probe_path": None,
        "revision_info": _revision(),
        "collect_nodes_fn": lambda iface: CollectedNodes(
            rows=[],
            full=[],
            by_id={},
            with_position_count=0,
        ),
        "collect_local_state_safe_fn": lambda iface, *, collect_local_state_fn: ({}, None),
        "get_radio_connection_status_fn": lambda iface: None,
    }


def test_meshyface_profile_uses_exact_private_app_port() -> None:
    assert DEFAULT_MESHYFACE_PROFILE_PORTNUM == 256
    assert DEFAULT_MESHYFACE_PROFILE_PORTNUM == portnums_pb2.PortNum.PRIVATE_APP
    assert portnums_pb2.PortNum.ATAK_FORWARDER == 257


def test_build_and_parse_theme_only_meshyface_profile_packet() -> None:
    recipe = _theme_recipe()
    payload = build_meshyface_profile_payload(
        node_id="335D8354",
        updated_unix=1_788_300_000,
        theme=recipe,
    )

    assert json.loads(payload) == {
        "type": "meshyface.profile",
        "v": 2,
        "node": "!335d8354",
        "updated": 1_788_300_000,
        "theme": encode_meshyface_theme_recipe(recipe),
    }
    assert len(payload) == 113
    assert len(payload) <= mesh_pb2.Constants.DATA_PAYLOAD_LEN
    assert parse_meshyface_profile_packet(
        {
            "fromId": "!335d8354",
            "decoded": {"portnum": 256, "payload": payload},
        },
        now_unix_fn=lambda: 1_788_300_010,
    ) == {
        "node_id": "!335d8354",
        "updated_unix": 1_788_300_000,
        "received_unix": 1_788_300_010,
        "source": "mesh",
        "theme": recipe,
    }


def test_theme_recipe_codec_round_trip_matches_fixed_byte_layout() -> None:
    recipe = _theme_recipe()

    encoded = encode_meshyface_theme_recipe(recipe)
    raw = base64.urlsafe_b64decode(encoded)

    assert len(encoded) == MESHYFACE_THEME_RECIPE_ENCODED_LENGTH == 28
    assert re.fullmatch(r"[A-Za-z0-9_-]{28}", encoded)
    assert len(raw) == MESHYFACE_THEME_RECIPE_BYTES == 21
    assert raw == (
        b"\x01"
        b"\x12\x34\x56"
        b"\xab\xcd\xef"
        b"\xfe\xdc\xba"
        b"\x01\x02\x03"
        b"\xf0\xe0\xd0"
        + bytes((73, 42, 17, 0b01011011, 1))
    )
    assert decode_meshyface_theme_recipe(encoded) == recipe


def test_theme_recipe_codec_supports_every_enum_value() -> None:
    enum_values = {
        "text_font": ("system", "compact", "rounded", "mono", "serif"),
        "gradient_primary_type": ("linear", "radial"),
        "gradient_primary_direction": (
            "right",
            "left",
            "down",
            "up",
            "down-right",
            "down-left",
            "up-right",
            "up-left",
            "center",
        ),
        "mode": ("light", "dark"),
    }

    for key, values in enum_values.items():
        for value in values:
            recipe = _theme_recipe(**{key: value})
            assert decode_meshyface_theme_recipe(
                encode_meshyface_theme_recipe(recipe)
            ) == recipe


def test_profile_theme_round_trip_stays_within_single_packet_limit() -> None:
    recipe = _theme_recipe()
    payload = build_meshyface_profile_payload(
        node_id="!335d8354",
        updated_unix=1_788_300_000,
        theme=recipe,
    )

    body = json.loads(payload)
    assert body["v"] == 2
    assert "color" not in body
    assert isinstance(body["theme"], str)
    assert len(payload) == 113
    assert len(payload) <= MESHYFACE_PROFILE_MAX_PAYLOAD_BYTES
    assert MESHYFACE_PROFILE_MAX_PAYLOAD_BYTES == mesh_pb2.Constants.DATA_PAYLOAD_LEN
    assert parse_meshyface_profile_packet(
        {
            "fromId": "!335d8354",
            "decoded": {"portnum": 256, "payload": payload},
        },
        now_unix_fn=lambda: 1_788_300_010,
    ) == {
        "node_id": "!335d8354",
        "updated_unix": 1_788_300_000,
        "received_unix": 1_788_300_010,
        "source": "mesh",
        "theme": recipe,
    }


def test_profile_packet_can_carry_compact_ghost_text() -> None:
    recipe = _theme_recipe()
    payload = build_meshyface_profile_payload(
        node_id="!335d8354",
        updated_unix=1_788_300_000,
        theme=recipe,
        ghost={"text": "🔥🔥🔥🔥🔥🔥", "blend": 100, "effect": "glow"},
    )

    body = json.loads(payload)
    assert body["ghost"] == "🔥🔥🔥🔥🔥🔥"
    assert body["ghost_fx"] == 63
    assert "ghost_tilt" not in body
    assert "ghost_justify" not in body
    assert len(body["ghost"]) == MESHYFACE_PROFILE_GHOST_TEXT_MAX_CHARS
    assert len(body["ghost"].encode("utf-8")) <= MESHYFACE_PROFILE_GHOST_TEXT_MAX_BYTES
    assert MESHYFACE_PROFILE_MAX_PAYLOAD_BYTES - len(payload) >= 70
    assert parse_meshyface_profile_packet(
        {
            "fromId": "!335d8354",
            "decoded": {"portnum": 256, "payload": payload},
        },
        now_unix_fn=lambda: 1_788_300_010,
    ) == {
        "node_id": "!335d8354",
        "updated_unix": 1_788_300_000,
        "received_unix": 1_788_300_010,
        "source": "mesh",
            "theme": recipe,
            "ghost": {
                "text": "🔥🔥🔥🔥🔥🔥",
                "blend": MESHYFACE_PROFILE_GHOST_BLEND_MAX,
            "effect": "glow",
            "tilt": MESHYFACE_PROFILE_GHOST_TILT_DEFAULT,
            "justify": MESHYFACE_PROFILE_GHOST_JUSTIFY_DEFAULT,
            "fx": 63,
        },
    }


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("version", 2),
        ("base_color", "123456"),
        ("color_depth", 101),
        ("foreground_transparency", 91),
        ("foreground_blur", 41),
        ("text_font", "comic-sans"),
        ("gradient_primary_type", "conic"),
        ("gradient_primary_direction", "sideways"),
        ("mode", "auto"),
    ],
)
def test_invalid_outgoing_theme_recipe_raises(key: str, value: object) -> None:
    with pytest.raises(ValueError, match="complete valid Meshyface theme recipe"):
        build_meshyface_profile_payload(
            node_id="!335d8354",
            updated_unix=1_788_300_000,
            theme=_theme_recipe(**{key: value}),
        )


def test_outgoing_theme_recipe_rejects_extra_keys_and_boolean_numbers() -> None:
    extra = _theme_recipe()
    extra["background_image"] = "data:image/png;base64,nope"

    for recipe in (extra, _theme_recipe(color_depth=True)):
        with pytest.raises(ValueError, match="complete valid Meshyface theme recipe"):
            encode_meshyface_theme_recipe(recipe)


def test_profile_builder_enforces_final_meshtastic_payload_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = build_meshyface_profile_payload(
        node_id="!335d8354",
        updated_unix=1_788_300_000,
        theme=_theme_recipe(),
    )
    monkeypatch.setattr(
        meshyface_profile_protocol,
        "MESHYFACE_PROFILE_MAX_PAYLOAD_BYTES",
        len(payload) - 1,
    )

    with pytest.raises(ValueError, match="profile payload exceeds"):
        build_meshyface_profile_payload(
            node_id="!335d8354",
            updated_unix=1_788_300_000,
            theme=_theme_recipe(),
        )


def _wire_theme(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


@pytest.mark.parametrize(
    "wire_theme",
    [
        "short",
        "A" * 27 + "=",
        "A" * 27 + "+",
        _wire_theme(bytes((2,)) + (b"\x00" * 20)),
        _wire_theme(bytes((1,)) + (b"\x00" * 15) + bytes((101, 0, 0, 0, 0))),
        _wire_theme(bytes((1,)) + (b"\x00" * 15) + bytes((0, 91, 0, 0, 0))),
        _wire_theme(bytes((1,)) + (b"\x00" * 15) + bytes((0, 0, 41, 0, 0))),
        _wire_theme(bytes((1,)) + (b"\x00" * 15) + bytes((0, 0, 0, 0b111, 0))),
        _wire_theme(bytes((1,)) + (b"\x00" * 15) + bytes((0, 0, 0, 0b11110000, 0))),
        _wire_theme(bytes((1,)) + (b"\x00" * 15) + bytes((0, 0, 0, 0, 2))),
    ],
)
def test_malformed_or_unknown_received_theme_is_rejected(
    wire_theme: str,
) -> None:
    body = json.loads(
        build_meshyface_profile_payload(
            node_id="!335d8354",
            updated_unix=1_788_300_000,
            theme=_theme_recipe(),
        )
    )
    body["theme"] = wire_theme
    packet = {
        "fromId": "!335d8354",
        "decoded": {
            "portnum": "PRIVATE_APP",
            "payload": json.dumps(body, separators=(",", ":")).encode(),
        },
    }

    assert parse_meshyface_profile_packet(
        packet,
        now_unix_fn=lambda: 1_788_300_010,
    ) is None


def test_parse_accepts_real_meshtastic_message_to_dict_receive_shape() -> None:
    payload = build_meshyface_profile_payload(
        node_id="!335d8354",
        updated_unix=1_788_300_000,
        theme=_theme_recipe(),
    )
    mesh_packet = mesh_pb2.MeshPacket()
    setattr(mesh_packet, "from", 0x335D8354)
    mesh_packet.decoded.portnum = portnums_pb2.PortNum.PRIVATE_APP
    mesh_packet.decoded.payload = payload

    packet = MessageToDict(mesh_packet)

    assert packet["decoded"]["portnum"] == "PRIVATE_APP"
    assert isinstance(packet["decoded"]["payload"], str)
    # Meshtastic's receive path replaces MessageToDict's base64 value with the
    # original bytes before publishing the packet to subscribers.
    packet["decoded"]["payload"] = mesh_packet.decoded.payload
    packet["fromId"] = "!335d8354"

    parsed = parse_meshyface_profile_packet(packet, now_unix_fn=lambda: 1_788_300_010)

    assert parsed is not None
    assert parsed["node_id"] == "!335d8354"
    assert parsed["theme"] == _theme_recipe()


@pytest.mark.parametrize("portnum", [257, "ATAK_FORWARDER", 300, "PRIVATE_APP_300"])
def test_parse_rejects_every_port_except_private_app_256(portnum: object) -> None:
    assert parse_meshyface_profile_packet(_profile_packet(portnum=portnum)) is None


def test_parse_requires_sender_and_rejects_mismatched_sender() -> None:
    assert parse_meshyface_profile_packet(_profile_packet(sender_id=None)) is None
    assert (
        parse_meshyface_profile_packet(
            _profile_packet(sender_id="!11111111"),
        )
        is None
    )


def test_profile_validation_requires_theme_and_rejects_far_future_timestamp() -> None:
    with pytest.raises(ValueError, match="complete valid Meshyface theme recipe"):
        build_meshyface_profile_payload(
            node_id="!335d8354",
            updated_unix=1_788_300_000,
            theme=None,
        )

    now_unix = 1_800_000_000
    accepted_boundary = _profile_packet(updated_unix=now_unix + (24 * 60 * 60))
    rejected_future = _profile_packet(updated_unix=now_unix + (24 * 60 * 60) + 1)

    assert parse_meshyface_profile_packet(accepted_boundary, now_unix_fn=lambda: now_unix)
    assert parse_meshyface_profile_packet(rejected_future, now_unix_fn=lambda: now_unix) is None


def test_parse_rejects_legacy_and_color_bearing_wire_packets() -> None:
    legacy_payload = json.dumps(
        {
            "type": "meshyface.profile",
            "v": 1,
            "node": "!335d8354",
            "color": "#db2777",
            "updated": 1_770_000_000,
        }
    ).encode()
    legacy_packet = {
        "fromId": "!335d8354",
        "decoded": {"portnum": "PRIVATE_APP", "payload": legacy_payload},
    }
    assert parse_meshyface_profile_packet(legacy_packet) is None

    body = json.loads(
        build_meshyface_profile_payload(
            node_id="!335d8354",
            updated_unix=1_770_000_000,
            theme=_theme_recipe(),
        )
    )
    body["color"] = "#db2777"
    color_bearing_packet = {
        "fromId": "!335d8354",
        "decoded": {
            "portnum": "PRIVATE_APP",
            "payload": json.dumps(body, separators=(",", ":")).encode(),
        },
    }

    assert parse_meshyface_profile_packet(color_bearing_packet) is None

    ghost_fx_without_text = dict(body)
    ghost_fx_without_text["ghost_fx"] = 7
    ghost_fx_packet = {
        "fromId": "!335d8354",
        "decoded": {
            "portnum": "PRIVATE_APP",
            "payload": json.dumps(
                ghost_fx_without_text,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode(),
        },
    }

    assert parse_meshyface_profile_packet(ghost_fx_packet) is None


def test_parse_meshyface_profile_theme_request_validates_theme_and_channel() -> None:
    body = json.dumps(
        {
            "channel_index": 2,
            "theme": _theme_recipe(base_color="#ABCDEF"),
            "ghost": {
                "text": "AB🔥",
                "blend": 45,
                "effect": "stamp",
                "tilt": "right-upside-down",
                "justify": "left",
            },
        }
    ).encode("utf-8")

    request = parse_meshyface_profile_theme_request(body, to_int_fn=to_int)

    assert request.channel_index == 2
    assert request.theme == _theme_recipe(base_color="#abcdef")
    assert request.ghost == {
        "text": "AB🔥",
        "blend": MESHYFACE_PROFILE_GHOST_BLEND_MAX,
        "effect": "stamp",
        "tilt": "right-upside-down",
        "justify": "left",
        "fx": 255,
    }
    with pytest.raises(ValueError, match="no longer supported"):
        parse_meshyface_profile_theme_request(
            json.dumps({"color": "#db2777", "theme": _theme_recipe()}).encode(),
            to_int_fn=to_int,
        )
    with pytest.raises(ValueError, match="complete valid Meshyface theme recipe"):
        parse_meshyface_profile_theme_request(
            json.dumps(
                {
                    "theme": _theme_recipe(version=2),
                }
            ).encode(),
            to_int_fn=to_int,
        )


def test_send_meshyface_profile_theme_uses_public_send_data_api() -> None:
    iface = _SendDataIface()
    recipe = _theme_recipe()

    response = send_meshyface_profile_theme(
        theme=recipe,
        iface=iface,
        send_lock=threading.Lock(),
        local_node_id_fn=lambda: "!335d8354",
        channel_index=3,
        now_unix_fn=lambda: 1_788_300_000,
    )

    assert response == {
        "ok": True,
        "sent": True,
        "type": "meshyface.profile",
        "node": "!335d8354",
        "updated": 1_788_300_000,
        "theme": recipe,
        "destination": "^all",
        "channel_index": 3,
        "portnum": 256,
        "packet_id": 1234,
    }
    assert len(iface.calls) == 1
    payload, kwargs = iface.calls[0]
    body = json.loads(payload)
    assert "color" not in body
    assert decode_meshyface_theme_recipe(body["theme"]) == recipe
    assert kwargs == {
        "destinationId": "^all",
        "portNum": 256,
        "wantAck": False,
        "wantResponse": False,
        "channelIndex": 3,
    }


def test_send_meshyface_profile_theme_includes_optional_ghost() -> None:
    iface = _SendDataIface()
    recipe = _theme_recipe()

    response = send_meshyface_profile_theme(
        theme=recipe,
        ghost={
            "text": "HELLO",
            "blend": 35,
            "effect": "outline",
            "tilt": "right-upside-down",
            "justify": "right",
        },
        iface=iface,
        send_lock=threading.Lock(),
        local_node_id_fn=lambda: "!335d8354",
        channel_index=3,
        now_unix_fn=lambda: 1_788_300_000,
    )

    assert response["ghost"] == {
        "text": "HELLO",
        "blend": MESHYFACE_PROFILE_GHOST_BLEND_MAX,
        "effect": "outline",
        "tilt": "right-upside-down",
        "justify": "right",
        "fx": 223,
    }
    payload, _kwargs = iface.calls[0]
    body = json.loads(payload)
    assert body["ghost"] == "HELLO"
    assert body["ghost_fx"] == 223
    assert body["ghost_tilt"] == "right"
    assert body["ghost_justify"] == "right"
    assert decode_meshyface_theme_recipe(body["theme"]) == recipe


def test_send_meshyface_profile_theme_rejects_invalid_theme_before_radio_send() -> None:
    iface = _SendDataIface()

    with pytest.raises(ValueError, match="complete valid Meshyface theme recipe"):
        send_meshyface_profile_theme(
            theme=_theme_recipe(mode="auto"),
            iface=iface,
            send_lock=threading.Lock(),
            local_node_id_fn=lambda: "!335d8354",
        )

    assert iface.calls == []


def test_tracker_accepts_only_strictly_newer_profile_updates() -> None:
    tracker = DashboardTracker(packet_limit=8)
    updated = int(time.time()) - 10
    first_recipe = _theme_recipe(line_color="#db2777")
    equal_recipe = _theme_recipe(line_color="#22c55e")
    older_recipe = _theme_recipe(line_color="#0ea5e9")
    newer_recipe = _theme_recipe(line_color="#a855f7")

    tracker.seed_packet(
        _profile_packet(updated_unix=updated, theme=first_recipe),
        interface=object(),
    )
    tracker.seed_packet(
        _profile_packet(updated_unix=updated, theme=equal_recipe),
        interface=object(),
    )
    tracker.seed_packet(
        _profile_packet(updated_unix=updated - 1, theme=older_recipe),
        interface=object(),
    )

    assert tracker.meshyface_profiles_snapshot()["!335d8354"]["theme"] == first_recipe

    tracker.seed_packet(
        _profile_packet(updated_unix=updated + 1, theme=newer_recipe),
        interface=object(),
    )

    assert tracker.meshyface_profiles_snapshot()["!335d8354"]["theme"] == newer_recipe
    assert list(tracker.recent_chat) == []


def test_tracker_replaces_theme_atomically_and_snapshots_theme() -> None:
    tracker = DashboardTracker(packet_limit=8)
    updated = int(time.time()) - 10
    recipe = _theme_recipe()
    equal_recipe = _theme_recipe(base_color="#22c55e")
    replacement_recipe = _theme_recipe(base_color="#0ea5e9")

    tracker.seed_packet(
        _profile_packet(updated_unix=updated, theme=recipe),
        interface=object(),
    )
    first_snapshot = tracker.meshyface_profiles_snapshot()
    assert first_snapshot["!335d8354"]["theme"] == recipe
    first_theme = first_snapshot["!335d8354"]["theme"]
    assert isinstance(first_theme, dict)
    first_theme["base_color"] = "#000000"
    stored_theme = tracker.meshyface_profiles_snapshot()["!335d8354"]["theme"]
    assert isinstance(stored_theme, dict)
    assert stored_theme["base_color"] == "#123456"

    tracker.seed_packet(
        _profile_packet(updated_unix=updated, theme=equal_recipe),
        interface=object(),
    )
    assert tracker.meshyface_profiles_snapshot()["!335d8354"]["theme"] == recipe

    tracker.seed_packet(
        _profile_packet(updated_unix=updated + 1, theme=replacement_recipe),
        interface=object(),
    )
    replaced = tracker.meshyface_profiles_snapshot()["!335d8354"]
    assert "color" not in replaced
    assert replaced["theme"] == replacement_recipe


def test_tracker_profile_cache_is_bounded_and_evicts_oldest_received(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tracker_runtime_impl, "MESHYFACE_PROFILE_CACHE_LIMIT", 2)

    received_times = {
        "!00000001": 100,
        "!00000002": 200,
        "!00000003": 300,
    }

    def _parse(packet: object) -> dict[str, object] | None:
        if not isinstance(packet, dict):
            return None
        node_id = str(packet.get("fromId") or "")
        return {
            "node_id": node_id,
            "updated_unix": received_times[node_id],
            "received_unix": received_times[node_id],
            "source": "mesh",
            "theme": _theme_recipe(),
        }

    monkeypatch.setattr(tracker_runtime_impl, "_parse_meshyface_profile_packet", _parse)
    tracker = DashboardTracker(packet_limit=8)

    for node_id in received_times:
        tracker.seed_packet({"fromId": node_id}, interface=object())

    profiles = tracker.meshyface_profiles_snapshot()
    assert len(profiles) == 2
    assert set(profiles) == {"!00000002", "!00000003"}


def test_received_meshyface_profile_survives_history_store_restart(tmp_path: Path) -> None:
    history_path = tmp_path / "profile-history.sqlite3"
    updated = int(time.time()) - 10
    recipe = _theme_recipe()
    ghost = {
        "text": "73",
        "blend": 23,
        "effect": "glow",
        "tilt": MESHYFACE_PROFILE_GHOST_TILT_DEFAULT,
        "justify": MESHYFACE_PROFILE_GHOST_JUSTIFY_DEFAULT,
        "fx": 61,
    }

    first_store = _open_history_store(history_path)
    try:
        first_tracker = DashboardTracker(packet_limit=8, history_store=first_store)
        first_tracker.seed_packet(
            _profile_packet(updated_unix=updated, theme=recipe, ghost=ghost),
            interface=object(),
        )
        assert first_tracker.meshyface_profiles_snapshot()["!335d8354"]["theme"] == recipe
        assert first_tracker.meshyface_profiles_snapshot()["!335d8354"]["ghost"] == ghost
    finally:
        first_store.close()

    second_store = _open_history_store(history_path)
    try:
        second_tracker = DashboardTracker(packet_limit=8, history_store=second_store)
        restored = second_tracker.meshyface_profiles_snapshot()["!335d8354"]
        assert "color" not in restored
        assert restored["theme"] == recipe
        assert restored["ghost"] == ghost

        second_tracker.seed_packet(
            _profile_packet(
                updated_unix=updated - 1,
                theme=_theme_recipe(base_color="#22c55e"),
            ),
            interface=object(),
        )
        assert second_tracker.meshyface_profiles_snapshot()["!335d8354"]["theme"] == recipe
    finally:
        second_store.close()


def test_tracker_backfills_hex_theme_profile_packets_after_profile_cache_upgrade(
    tmp_path: Path,
) -> None:
    store = _open_history_store(tmp_path / "theme-profile-history.sqlite3")
    recipe = _theme_recipe()
    try:
        _save_hex_profile_packet(
            store,
            created_unix=1_788_300_010,
            updated_unix=1_788_300_000,
            theme=recipe,
        )

        tracker = DashboardTracker(packet_limit=8, history_store=store)

        assert tracker.meshyface_profiles_snapshot() == {
            "!335d8354": {
                "node_id": "!335d8354",
                "updated_unix": 1_788_300_000,
                "received_unix": 1_788_300_010,
                "source": "mesh",
                "theme": recipe,
            }
        }
        assert store.load_meshyface_profiles() == list(
            tracker.meshyface_profiles_snapshot().values()
        )
    finally:
        store.close()


def test_profile_packet_backfill_replays_hex_packets_with_strict_lww(tmp_path: Path) -> None:
    store = _open_history_store(tmp_path / "theme-profile-lww.sqlite3")
    winning_recipe = _theme_recipe(base_color="#0ea5e9")
    try:
        _save_hex_profile_packet(
            store,
            created_unix=1_788_300_010,
            updated_unix=1_788_300_000,
        )
        _save_hex_profile_packet(
            store,
            created_unix=1_788_300_020,
            updated_unix=1_788_300_001,
            theme=winning_recipe,
        )
        # An equal advertised timestamp arrives later.  Like live reception,
        # strict LWW keeps the first value for that timestamp.
        _save_hex_profile_packet(
            store,
            created_unix=1_788_300_030,
            updated_unix=1_788_300_001,
            theme=_theme_recipe(base_color="#22c55e"),
        )

        tracker = DashboardTracker(packet_limit=8, history_store=store)
        profile = tracker.meshyface_profiles_snapshot()["!335d8354"]

        assert "color" not in profile
        assert profile["updated_unix"] == 1_788_300_001
        assert profile["received_unix"] == 1_788_300_020
        assert profile["theme"] == winning_recipe
    finally:
        store.close()


def test_profile_packet_backfill_only_reads_bounded_newest_packet_window(
    tmp_path: Path,
) -> None:
    store = _open_history_store(tmp_path / "theme-profile-window.sqlite3")
    try:
        _save_hex_profile_packet(
            store,
            created_unix=1_788_300_010,
            updated_unix=1_788_300_000,
        )
        with store._lock:
            store._conn.executemany(
                "INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(?, ?, ?)",
                [
                    (1_788_300_020, "{}", "{}"),
                    (1_788_300_030, "{}", "{}"),
                ],
            )
            store._conn.commit()

        assert store.backfill_meshyface_profiles_from_packets(packet_limit=2) == []
        assert store.load_meshyface_profiles() == []
    finally:
        store.close()


def test_profile_packet_backfill_never_overwrites_existing_profile_rows(
    tmp_path: Path,
) -> None:
    store = _open_history_store(tmp_path / "existing-profile-history.sqlite3")
    try:
        assert store.save_meshyface_profile(
            {
                "node_id": "!335d8354",
                "updated_unix": 1_788_300_100,
                "received_unix": 1_788_300_100,
                "theme": _theme_recipe(line_color="#a855f7"),
            }
        )
        _save_hex_profile_packet(
            store,
            created_unix=1_788_300_200,
            updated_unix=1_788_300_200,
        )

        tracker = DashboardTracker(packet_limit=8, history_store=store)

        assert tracker.meshyface_profiles_snapshot()["!335d8354"]["theme"] == _theme_recipe(
            line_color="#a855f7"
        )
        assert store.load_meshyface_profiles()[0]["theme"] == _theme_recipe(
            line_color="#a855f7"
        )
    finally:
        store.close()


def test_history_store_profile_rows_are_lww_bounded_and_resettable(tmp_path: Path) -> None:
    store = _open_history_store(tmp_path / "profile-history.sqlite3")
    try:
        first = {
            "node_id": "!00000001",
            "updated_unix": 100,
            "received_unix": 100,
            "theme": _theme_recipe(),
        }
        assert store.save_meshyface_profile(first, limit=2) is True
        assert store.save_meshyface_profile(
            {
                **first,
                "theme": _theme_recipe(line_color="#22c55e"),
                "received_unix": 101,
            },
            limit=2,
        ) is False
        assert store.save_meshyface_profile(
            {
                **first,
                "theme": _theme_recipe(line_color="#0ea5e9"),
                "updated_unix": 99,
            },
            limit=2,
        ) is False
        assert store.save_meshyface_profile(
            {
                **first,
                "theme": _theme_recipe(line_color="#a855f7"),
                "updated_unix": 101,
            },
            limit=2,
        ) is True

        assert store.save_meshyface_profile(
            {
                "node_id": "!00000002",
                "updated_unix": 200,
                "received_unix": 200,
                "theme": _theme_recipe(line_color="#22c55e"),
            },
            limit=2,
        ) is True
        assert store.save_meshyface_profile(
            {
                "node_id": "!00000003",
                "updated_unix": 300,
                "received_unix": 300,
                "theme": _theme_recipe(line_color="#0ea5e9"),
            },
            limit=2,
        ) is True
        profiles = store.load_meshyface_profiles(limit=2)
        assert [profile["node_id"] for profile in profiles] == ["!00000003", "!00000002"]
        assert all("color" not in profile for profile in profiles)

        with store._lock:
            store._conn.execute(
                """
                INSERT INTO meshyface_profiles(
                    node_id, color, updated_unix, received_unix, theme_json
                )
                VALUES(?, ?, ?, ?, ?)
                """,
                ("!not-a-node", "#ffffff", 400, 400, json.dumps(_theme_recipe())),
            )
            store._conn.commit()
        profiles = store.load_meshyface_profiles(limit=3)
        assert {profile["node_id"] for profile in profiles} == {"!00000002", "!00000003"}

        assert store.reset() >= 2
        assert store.load_meshyface_profiles() == []
    finally:
        store.close()


def test_full_and_lite_state_include_sanitized_top_level_profiles() -> None:
    tracker = _StateTracker()
    expected = {
        "!335d8354": {
            "node_id": "!335d8354",
            "updated_unix": 1_788_300_000,
            "received_unix": 1_788_300_010,
            "source": "mesh",
            "theme": _theme_recipe(),
            "render": build_meshyface_theme_render(_theme_recipe()),
            "ghost": {
                "text": "73",
                "blend": 23,
                "effect": "glow",
                "tilt": MESHYFACE_PROFILE_GHOST_TILT_DEFAULT,
                "justify": MESHYFACE_PROFILE_GHOST_JUSTIFY_DEFAULT,
                "fx": 61,
            },
        },
    }

    full = build_dashboard_state_typed(**_state_kwargs(tracker))
    lite = build_dashboard_state_lite(
        **_state_kwargs(tracker),
        show_secrets=True,
        sensitive_field_names=set(),
        profile="chat",
    )

    assert full.as_dict()["meshyface_profiles"] == expected
    assert lite["meshyface_profiles"] == expected
    assert "meshyface_profiles" not in full.as_dict()["traffic"]


def test_handle_dashboard_post_dispatches_profile_theme() -> None:
    recipe = _theme_recipe()
    body = json.dumps({"channel_index": 4, "theme": recipe}).encode()
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Authorization": "Bearer secret",
        },
    )
    responses: list[tuple[int, object]] = []
    received: list[dict[str, object]] = []

    def _send_profile(**kwargs: object) -> dict[str, object]:
        received.append(kwargs)
        return {"ok": True, "sent": True, **kwargs}

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        send_meshyface_profile_fn=_send_profile,
        api_token="secret",
        to_int_fn=to_int,
    )
    deps = replace(
        deps,
        write_json_response_fn=lambda handler, *, status_code, payload_obj, **kwargs: responses.append(
            (status_code, payload_obj)
        ),
    )

    handle_dashboard_post(handler, path="/api/meshyface/profile/theme", deps=deps)

    assert received == [{"channel_index": 4, "theme": recipe}]
    assert responses == [
        (
            200,
            {
                "ok": True,
                "sent": True,
                "channel_index": 4,
                "theme": recipe,
            },
        )
    ]


def test_handle_dashboard_post_dispatches_profile_theme_ghost() -> None:
    recipe = _theme_recipe()
    ghost = {
        "text": "AB🔥",
        "blend": 45,
        "effect": "stamp",
        "tilt": "right-upside-down",
        "justify": "left",
    }
    body = json.dumps({"channel_index": 4, "theme": recipe, "ghost": ghost}).encode(
        "utf-8"
    )
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Authorization": "Bearer secret",
        },
    )
    responses: list[tuple[int, object]] = []
    received: list[dict[str, object]] = []

    def _send_profile(**kwargs: object) -> dict[str, object]:
        received.append(kwargs)
        return {"ok": True, "sent": True, **kwargs}

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        send_meshyface_profile_fn=_send_profile,
        api_token="secret",
        to_int_fn=to_int,
    )
    deps = replace(
        deps,
        write_json_response_fn=lambda handler, *, status_code, payload_obj, **kwargs: responses.append(
            (status_code, payload_obj)
        ),
    )

    handle_dashboard_post(handler, path="/api/meshyface/profile/theme", deps=deps)

    normalized_ghost = {
        "text": "AB🔥",
        "blend": MESHYFACE_PROFILE_GHOST_BLEND_MAX,
        "effect": "stamp",
        "tilt": "right-upside-down",
        "justify": "left",
        "fx": 255,
    }
    assert received == [{"channel_index": 4, "theme": recipe, "ghost": normalized_ghost}]
    assert responses == [
        (
            200,
            {
                "ok": True,
                "sent": True,
                "channel_index": 4,
                "theme": recipe,
                "ghost": normalized_ghost,
            },
        )
    ]


def test_handle_dashboard_post_rejects_legacy_profile_color() -> None:
    recipe = _theme_recipe()
    body = json.dumps(
        {"color": "#db2777", "channel_index": 4, "theme": recipe}
    ).encode()
    handler = _FakeHandler(
        body,
        headers={
            "Content-Length": str(len(body)),
            "Authorization": "Bearer secret",
        },
    )
    responses: list[tuple[int, object]] = []
    received: list[dict[str, object]] = []

    def _send_profile(**kwargs: object) -> dict[str, object]:
        received.append(kwargs)
        return {"ok": True, "sent": True, **kwargs}

    deps = build_post_route_dependencies(
        send_chat_fn=None,
        send_meshyface_profile_fn=_send_profile,
        api_token="secret",
        to_int_fn=to_int,
    )
    deps = replace(
        deps,
        write_json_response_fn=lambda handler, *, status_code, payload_obj, **kwargs: responses.append(
            (status_code, payload_obj)
        ),
    )

    handle_dashboard_post(handler, path="/api/meshyface/profile/theme", deps=deps)

    assert received == []
    assert responses == [
        (
            400,
            {
                "ok": False,
                "error": "color is no longer supported; provide a complete Meshyface theme",
            },
        )
    ]


def test_profile_post_is_blocked_in_private_mode() -> None:
    handler = _FakeHandler()
    responses: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(send_chat_fn=None, private_mode=True, to_int_fn=to_int)
    deps = replace(
        deps,
        write_json_response_fn=lambda handler, *, status_code, payload_obj, **kwargs: responses.append(
            (status_code, payload_obj)
        ),
    )

    handle_dashboard_post(handler, path="/api/meshyface/profile/theme", deps=deps)

    assert responses == [(403, {"ok": False, "error": "This endpoint is disabled in private mode"})]


def test_profile_post_requires_configured_api_token() -> None:
    handler = _FakeHandler()
    responses: list[tuple[int, object]] = []
    deps = build_post_route_dependencies(send_chat_fn=None, api_token="secret", to_int_fn=to_int)
    deps = replace(
        deps,
        write_json_response_fn=lambda handler, *, status_code, payload_obj, **kwargs: responses.append(
            (status_code, payload_obj)
        ),
    )

    handle_dashboard_post(handler, path="/api/meshyface/profile/theme", deps=deps)

    assert responses == [(401, {"ok": False, "error": "API token required for write endpoint"})]


def test_make_http_handler_passes_state_profile_send_hook(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr("meshdash.http_api.build_get_route_dependencies", lambda **kwargs: object())

    def _capture_post_dependencies(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("meshdash.http_api.build_post_route_dependencies", _capture_post_dependencies)
    monkeypatch.setattr(
        "meshdash.http_api.build_dashboard_handler_class",
        lambda **kwargs: {
            "dispatch_get_fn": kwargs["dispatch_get_fn"],
            "dispatch_post_fn": kwargs["dispatch_post_fn"],
        },
    )

    def _state_fn() -> dict[str, object]:
        return {}

    def _send_profile(**kwargs: object) -> dict[str, object]:
        return {"ok": True, **kwargs}

    setattr(_state_fn, "send_meshyface_profile_fn", _send_profile)

    make_http_handler("<html></html>", _state_fn)

    assert captured["send_meshyface_profile_fn"] is _send_profile


def test_render_html_includes_theme_only_profile_controls() -> None:
    html = render_html(3000, 250, False, True, 200000, 30, 72, 1440, "test", "test")

    assert 'id="settings-meshyface-profile-color"' not in html
    assert 'id="settings-meshyface-profile-accept-remote"' not in html
    assert 'id="settings-meshyface-theme-sharing"' in html
    assert 'id="settings-meshyface-node-theme-preview"' in html
    assert 'id="settings-meshyface-node-theme-preview-card"' in html
    assert 'id="settings-meshyface-node-theme-preview-member"' in html
    assert 'id="settings-meshyface-node-theme-select"' in html
    assert 'id="settings-meshyface-node-theme-reset"' in html
    assert 'id="settings-meshyface-node-theme-save"' in html
    assert 'id="settings-meshyface-node-theme-try-dashboard"' in html
    assert 'id="settings-meshyface-node-theme-save-dashboard"' in html
    assert 'id="settings-meshyface-node-theme-ghost-text"' in html
    assert 'id="settings-meshyface-node-theme-ghost-effect"' in html
    assert 'id="settings-meshyface-node-theme-ghost-justify"' in html
    assert 'id="settings-meshyface-node-theme-ghost-tilt"' in html
    assert 'id="settings-meshyface-node-theme-ghost-upside-down"' in html
    assert 'id="settings-meshyface-node-theme-ghost-blend"' in html
    assert 'id="settings-meshyface-node-theme-ghost-blend" class="settings-range-input" type="range" min="0" max="25"' in html
    assert "Watermark" in html
    assert "Watermark effect" in html
    assert "Watermark justify" in html
    assert "Watermark tilt" in html
    assert "Upside down" in html
    assert '<option value="center" selected>Center</option>' in html
    assert '<option value="upside-down">Upside down</option>' not in html
    assert "Watermark strength" in html
    assert "Ghost text" not in html
    assert 'id="settings-meshyface-profile-broadcast"' in html
    assert 'id="settings-meshyface-profile-status"' in html
    assert 'id="settings-meshyface-profile-sync-enabled"' not in html
    assert "My Meshyface color" not in html
    assert "Node Appearance" in html
    assert "Share node appearance" in html
    assert "Shared appearance preview" in html
    assert "Node appearance" in html
    assert "Broadcast appearance" in html
    assert "Theme Sharing" not in html
    assert "Share node theme" not in html
    assert "Use received Meshyface themes to style nodes" not in html


def test_dashboard_css_keeps_ghost_overlay_off_compact_node_rows() -> None:
    css = build_dashboard_css(theme_css="")

    assert "--node-profile-ghost-text" in css
    assert "--node-profile-ghost-font-size" in css
    assert "--node-profile-ghost-anchor-x" in css
    assert "transform: translate(-50%, -50%) var(--node-profile-ghost-transform" in css
    assert "--node-profile-ghost-justify" not in css
    assert "--node-profile-ghost-padding-x" not in css
    assert ".chat-feed-item.profiled-node::after" in css
    assert ".chat-member-item.profiled-node::after" not in css
    assert ".self-node-identity-slot.profiled-node::after" not in css


def test_dashboard_js_keeps_profiles_separate_from_manual_tags_and_auto_scheduling() -> None:
    js = build_dashboard_js(refresh_ms=3000, node_history_hours=72, node_history_max_points=1440)

    assert 'const meshyfaceProfileThemeEndpoint = "/api/meshyface/profile/theme";' in js
    assert "meshyfaceProfileColorEndpoint" not in js
    assert "settingsMeshyfaceProfileColor" not in js
    assert "settingsMeshyfaceProfileColorStorageKey" not in js
    assert "setMeshyfaceProfileColor" not in js
    assert "settingsMeshyfaceProfileAcceptRemoteEnabled" not in js
    assert "settingsMeshyfaceProfileAcceptRemoteStorageKey" not in js
    assert 'let settingsMeshyfaceThemeSharingEnabled = true;' in js
    assert 'let settingsMeshyfaceNodeThemeSettings = null;' in js
    assert 'let settingsMeshyfaceNodeThemeSelected = "custom";' in js
    assert 'const settingsMeshyfaceThemeSharingStorageKey = "meshDashboardMeshyfaceThemeSharingV1";' in js
    assert 'const settingsMeshyfaceNodeThemeStorageKey = "meshDashboardMeshyfaceNodeThemeV1";' in js
    assert (
        'const settingsMeshyfaceNodeThemeCatalogStorageKey = '
        '"meshDashboardMeshyfaceNodeThemeCatalogV1";'
    ) in js
    assert (
        'const settingsMeshyfaceNodeThemeSelectedStorageKey = '
        '"meshDashboardMeshyfaceNodeThemeSelectedV1";'
    ) in js
    assert (
        'const settingsMeshyfaceNodeThemePreviewRenderStorageKey = '
        '"meshDashboardMeshyfaceNodeThemePreviewRenderV1";'
    ) in js
    assert "let meshyfaceProfileThemeDashboardPreviewUndo = null;" in js
    assert 'document.getElementById("settings-meshyface-theme-sharing")' in js
    assert "function setMeshyfaceThemeSharingEnabled(enabled, options = null)" in js
    assert "function currentMeshyfaceNodeThemeSettings()" in js
    assert "function currentMeshyfaceProfileThemeRecipe()" in js
    assert "function currentMeshyfaceProfileGhost()" in js
    assert "function currentMeshyfaceProfileOutgoingPayload(extra = null)" in js
    assert "function normalizeMeshyfaceNodeThemePayload(rawPayload, fallbackSettings = null)" in js
    assert "function meshyfaceNodeThemeOutgoingPayloadFromSettings(rawSettings, extra = null)" in js
    assert "settingsMeshyfaceNodeThemeCatalog[name] = normalizeMeshyfaceNodeThemePayload(payload);" in js
    assert "currentMeshyfaceProfileOutgoingPayload({ channel_index: channelIndex })" in js
    assert "function normalizeMeshyfaceProfileGhostText(value)" in js
    assert "if (charCount >= 6) break;" in js
    assert "function meshyfaceProfileGhostVisualUnits(value)" in js
    assert "function meshyfaceProfileGhostAutoFontSize(value)" in js
    assert "function meshyfaceProfileGhostAnchorX(justify, value)" in js
    assert '"--node-profile-ghost-anchor-x"' in js
    assert "const meshyfaceProfileGhostBlendMax = 25;" in js
    assert 'const meshyfaceProfileGhostTiltDefault = "level";' in js
    assert 'const meshyfaceProfileGhostJustifyDefault = "center";' in js
    assert "function normalizeMeshyfaceProfileGhostTilt(value, fallback = meshyfaceProfileGhostTiltDefault)" in js
    assert "function normalizeMeshyfaceProfileGhostJustify(value, fallback = meshyfaceProfileGhostJustifyDefault)" in js
    assert "function meshyfaceProfileGhostTiltBase(value)" in js
    assert "function meshyfaceProfileGhostTiltUpsideDown(value)" in js
    assert "function composeMeshyfaceProfileGhostTilt(base, upsideDown)" in js
    assert "function meshyfaceProfileFallbackGhostForNode(nodeId, node = null)" in js
    assert "function meshyfaceProfileGhostForAppearance(appearanceEntry)" in js
    assert "function normalizeMeshyfaceProfileGhost(rawGhost)" in js
    assert "function meshyfaceProfileGhostStyleVars(rawGhost)" in js
    assert "const settings = currentMeshyfaceNodeThemeSettings();" in js
    assert "function syncMeshyfaceNodeThemeControls()" in js
    assert "function bindMeshyfaceNodeThemeControls()" in js
    assert "function resetMeshyfaceNodeThemeFromDashboard()" in js
    assert "function saveCurrentMeshyfaceNodeThemeAs()" in js
    assert "function meshyfaceProfileThemeDashboardSettings(rawTheme, baseSettings = null)" in js
    assert "function captureMeshyfaceProfileThemeDashboardPreviewUndo(rawTheme)" in js
    assert "function clearMeshyfaceProfileThemeDashboardPreviewUndo()" in js
    assert "function tryCurrentMeshyfaceNodeThemeOnDashboard()" in js
    assert "function saveCurrentMeshyfaceNodeThemeAsDashboardTheme()" in js
    assert "Previewing node appearance on the dashboard. Use Undo look to restore the previous theme." in js
    assert "renderMeshyfaceNodeThemePreview();" in js
    assert 'document.getElementById("settings-meshyface-node-theme-ghost-text")' in js
    assert 'document.getElementById("settings-meshyface-node-theme-ghost-justify")' in js
    assert 'document.getElementById("settings-meshyface-node-theme-ghost-upside-down")' in js
    assert 'bindSelect("settings-meshyface-node-theme-ghost-effect", "ghost_effect", normalizeMeshyfaceProfileGhostEffect);' in js
    assert 'bindSelect("settings-meshyface-node-theme-ghost-justify", "ghost_justify", normalizeMeshyfaceProfileGhostJustify);' in js
    assert 'bindSelect("settings-meshyface-node-theme-ghost-tilt", "ghost_tilt", normalizeMeshyfaceProfileGhostTilt);' not in js
    assert "composeMeshyfaceProfileGhostTilt(" in js
    assert 'bindRangeInput("settings-meshyface-node-theme-ghost-blend", "ghost_blend", normalizeMeshyfaceProfileGhostBlend);' in js
    assert "function estimateMeshyfaceNodeThemePreviewRender(rawTheme)" in js
    assert "function meshyfaceNodeThemePreviewRenderForTheme(rawTheme)" in js
    assert "function persistMeshyfaceNodeThemePreviewRenderCache(signature, rawRender)" in js
    assert "function loadMeshyfaceNodeThemePreviewRenderCacheFromStorage()" in js
    assert "return exactRender || estimateMeshyfaceNodeThemePreviewRender(theme);" in js
    assert "persistMeshyfaceNodeThemePreviewRenderCache(signature, render);" in js
    assert "loadMeshyfaceNodeThemePreviewRenderCacheFromStorage();" in js
    assert "window.localStorage.getItem(settingsMeshyfaceNodeThemePreviewRenderStorageKey)" in js
    assert "window.localStorage.setItem(\n          settingsMeshyfaceNodeThemePreviewRenderStorageKey," in js
    assert "if (typeof loadMeshyfaceNodeThemePreferencesFromStorage === \"function\") {" in js
    assert "persistMeshyfaceNodeThemePreferences();" not in js[
        js.index("function loadSettingsAppearancePreferences()")
        : js.index("function persistSettingsAppearancePreferences()")
    ]
    assert "profile.color" not in js
    assert "const remoteMeshyfaceProfilesByNodeId = new Map();" in js
    assert "function clearRemoteMeshyfaceProfilesCache()" in js
    assert "function syncMeshyfaceProfilesFromState(state = latestState)" in js
    assert "if (!settingsMeshyfaceThemeSharingEnabled) return clearRemoteMeshyfaceProfilesCache();" in js
    assert "function meshyfaceProfileAppearanceForNode(nodeId, state = latestState)" in js
    assert "if (!settingsMeshyfaceThemeSharingEnabled) return null;" in js
    assert "function effectiveNodeAppearanceForNode(nodeId, state = latestState)" in js
    assert re.search(
        r"function nodeTagEntryForNode\(nodeId\)\s*\{\s*"
        r"return manualNodeTagEntryForNode\(nodeId\);\s*\}",
        js,
    )
    assert "function nodeTagOverridesProfileAppearance(tagEntry)" in js
    assert "return false;" in js[js.index("function nodeTagOverridesProfileAppearance(tagEntry)"):js.index("function meshyfaceProfilesCacheSignature")]
    assert "if (nodeTagOverridesProfileAppearance(tagEntry)) return tagEntry;" not in js
    assert "return meshyfaceProfileAppearanceForNode(nodeId, state) || tagEntry;" not in js
    assert "return meshyfaceProfileAppearanceForNode(nodeId, state);" in js
    local_profile_start = js.index("if (localNodeId && cleanNodeId === localNodeId)")
    local_profile_source_start = js.index('source: "local-profile",', local_profile_start)
    local_profile_end = js.index('source: "remote-profile",', local_profile_source_start)
    local_profile_block = js[local_profile_start:local_profile_end]
    assert "profileAppearance: true," in local_profile_block
    assert "localProfile: true," in local_profile_block
    assert "color: render ? render.border_color : theme.line_color," in local_profile_block
    assert "theme," in local_profile_block
    assert "...(render ? { render } : {})," in local_profile_block
    assert "queueMeshyfaceNodeThemePreviewRenderRefresh(theme);" in local_profile_block
    assert "const render = meshyfaceNodeThemePreviewRenderForTheme(theme);" in local_profile_block
    sharing_gate_index = js.index(
        "if (!settingsMeshyfaceThemeSharingEnabled) return null;",
        local_profile_source_start,
    )
    assert sharing_gate_index < local_profile_end
    remote_profile_block = js[local_profile_end:js.index("function effectiveNodeAppearanceForNode", local_profile_end)]
    assert "profileAppearance: true," in remote_profile_block
    assert "remoteProfile: true," in remote_profile_block
    assert "const theme = normalizeMeshyfaceProfileTheme(profile.theme);" in js
    assert "if (!theme || !preset) return null;" in js
    assert "const render = normalizeMeshyfaceProfileThemeRender(profile.render);" in js
    assert "color: render ? render.border_color : theme.line_color," in remote_profile_block
    assert "render," in remote_profile_block
    assert "const previewRender = meshyfaceNodeThemePreviewRenderForTheme(theme);" in js
    assert 'nodeId: previewLocalNodeId || "local-preview",' in js
    assert "...(previewNode ? { node: previewNode } : {})," in js
    theme_preference_block = js[
        js.index("function applyThemePreference(mode, persist = true)")
        : js.index("function bindThemeToggle()", js.index("function applyThemePreference(mode, persist = true)"))
    ]
    assert 'if (typeof renderMeshyfaceNodeThemePreview === "function") {' in theme_preference_block
    assert "renderMeshyfaceNodeThemePreview();" in theme_preference_block
    assert 'if (typeof rerenderMeshyfaceProfileAppearance === "function") {' in theme_preference_block
    assert "rerenderMeshyfaceProfileAppearance();" in theme_preference_block
    assert 'const appearanceClass = appearanceEntry && appearanceEntry.profileAppearance' in js
    assert "--node-profile-color-wash" not in js
    assert "--node-profile-identity-color:${color};" in js
    assert "const surfaceColor = profileTheme ? profileTheme.base_color : color;" in js
    assert "const surfaceBackground = appearanceEntry.profileAppearance && profileTheme" in js
    assert "--node-profile-bg:${surfaceBackground};" in js
    assert "const profileGhost = appearanceEntry.profileAppearance" in js
    assert "meshyfaceProfileGhostForAppearance(appearanceEntry)" in js
    assert "meshyfaceProfileGhostStyleVars(profileGhost)" in js
    assert "var(--node-profile-theme-surface, var(--node-profile-theme-background" in js
    assert "const profileRender = typeof normalizeMeshyfaceProfileThemeRender" in js
    assert "--node-profile-theme-background" in js
    assert "--node-profile-theme-shell" in js
    assert "--node-profile-theme-border-muted" in js
    assert "const meshyfaceProfileThemeFontFamilies = Object.freeze" not in js
    assert "function meshyfaceProfileThemeFontFamily(rawTheme)" not in js
    assert "const meshyfaceProfileThemeFontFamilyCss = Object.freeze" in js
    assert "--node-profile-theme-font-family" in js
    assert (
        '["--node-profile-theme-font-family", '
        "meshyfaceProfileThemeFontFamilyCss[theme.text_font] || meshyfaceProfileThemeFontFamilyCss.system]"
    ) in js
    assert "--node-profile-theme-motif-gradient" not in js
    assert "--node-profile-theme-gradient" not in js
    assert "--node-profile-theme-wash" not in js
    assert '["--node-profile-theme-base", theme.base_color]' in js
    assert '["--node-profile-theme-line", theme.line_color]' in js
    assert '["--node-profile-theme-contrast", theme.line_contrast_color]' in js
    assert 'target.style.setProperty("--node-profile-identity-color", color);' in js
    assert "data-reply-node-id=\"${escAttr(replyParentNodeId)}\"" in js
    assert "peer-dm-popout-head${peerProfileClass}" in js
    assert "peer-dm-popout-msg${isOwn ? \" is-own\" : \"\"}${alertClass}${messageProfileClass}" in js
    assert 'meshChannelEffectiveSendIndexForApp("profiles")' in js
    assert "syncMeshyfaceProfilesFromState(state)" in js
    assert "async function broadcastMeshyfaceProfileTheme()" in js
    assert "Turn on sharing before broadcasting your node appearance." in js
    assert "body: JSON.stringify({" in js
    assert "theme," in js
    broadcast_call_index = js.index("void broadcastMeshyfaceProfileTheme();")
    broadcast_button_index = js.rfind(
        'document.getElementById("settings-meshyface-profile-broadcast")',
        0,
        broadcast_call_index,
    )
    broadcast_click_index = js.index('.addEventListener("click"', broadcast_button_index)
    assert broadcast_button_index >= 0
    assert broadcast_click_index < broadcast_call_index
    assert broadcast_call_index - broadcast_button_index < 500
    assert js.count("broadcastMeshyfaceProfileTheme();") == 1
    assert "maybeBroadcastMeshyfaceProfileThemeOnStartup" not in js
    assert "settingsMeshyfaceProfileSyncEnabled" not in js


def test_dashboard_js_invalidates_spatial_and_inspector_surfaces_when_profiles_change() -> None:
    js = build_dashboard_js(refresh_ms=3000, node_history_hours=72, node_history_max_points=1440)

    poll_sync_start = js.index("if (syncMeshyfaceProfilesFromState(state)) {")
    poll_sync_end = js.index("if (typeof refreshConsoleNodeRowsCache", poll_sync_start)
    poll_sync_block = js[poll_sync_start:poll_sync_end]
    assert 'chatPollStructuralSignature = "";' in poll_sync_block
    assert 'lastMapSignature = "";' in poll_sync_block
    assert 'lastMapGraphSignature = "";' in poll_sync_block
    assert 'lastMapRenderMode = "";' in poll_sync_block

    rerender_start = js.index("function rerenderMeshyfaceProfileAppearance() {")
    rerender_end = js.index("function setMeshyfaceThemeSharingEnabled", rerender_start)
    rerender_block = js[rerender_start:rerender_end]
    assert "const networkMapVisible = activeLayoutView === \"network\"" in rerender_block
    assert "const mapVisible = activeLayoutView === \"saved\" || networkMapVisible;" in rerender_block
    assert "renderMap(" in rerender_block
    assert "bypassNodeFade: true" in rerender_block
    assert "syncChatNodeDetailsDrawer(latestState, { fetchHistory: false });" in rerender_block
