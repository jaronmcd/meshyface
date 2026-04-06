import threading
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.api_input_network_tools import NetworkToolRequest
from meshdash.services_network_tools import run_network_tool


class _FakeRole:
    DISABLED = 0


class _FakeChannelPb2:
    class Channel:
        Role = _FakeRole


class _FakePortNum:
    POSITION_APP = 3
    TRACEROUTE_APP = 70


class _FakePortnumsPb2:
    PortNum = _FakePortNum


class _FakePosition:
    def __init__(self) -> None:
        self.latitude_i = 0
        self.longitude_i = 0
        self.altitude = 0
        self.precision_bits = 0

    def SerializeToString(self) -> bytes:
        return b"position-request"

    def ParseFromString(self, payload: bytes) -> None:
        if payload == b"good-position":
            self.latitude_i = 449800000
            self.longitude_i = -932600000
            self.altitude = 251
            self.precision_bits = 32
        elif payload == b"disabled-position":
            self.latitude_i = 0
            self.longitude_i = 0
            self.altitude = 0
            self.precision_bits = 0


class _FakeMeshPb2:
    Position = _FakePosition


class _FakeRouteDiscovery:
    def __init__(self) -> None:
        self.route = []
        self.snr_towards = []
        self.route_back = []
        self.snr_back = []

    def SerializeToString(self) -> bytes:
        return b"traceroute-request"

    def ParseFromString(self, payload: bytes) -> None:
        self.route = []
        self.snr_towards = []
        self.route_back = []
        self.snr_back = []
        if payload == b"good-traceroute":
            self.route = [0x11223344, 0x55667788]
            self.snr_towards = [34, 24, 18]
            self.route_back = [0x55667788, 0x11223344]
            self.snr_back = [22, 28, 32]
            return
        if payload == b"direct-traceroute":
            self.snr_towards = [20]
            self.snr_back = [24]
            return
        if payload == b"bad-traceroute":
            raise ValueError("bad traceroute payload")


_FakeMeshPb2.RouteDiscovery = _FakeRouteDiscovery


class _FakeSentPacket:
    def __init__(self, packet_id: int) -> None:
        self.id = packet_id


class _FakeChannel:
    def __init__(self, role: int) -> None:
        self.role = role


class _FakeLocalNode:
    def __init__(self, channel_role: int = 1, hop_limit: int = 4) -> None:
        self._channel_role = channel_role
        self.localConfig = type(
            "_FakeLocalConfig",
            (),
            {"lora": type("_FakeLoraConfig", (), {"hop_limit": hop_limit})()},
        )()

    def getChannelByChannelIndex(self, channel_index: int):
        if channel_index != 0:
            return None
        return _FakeChannel(self._channel_role)


class _FakeIface:
    def __init__(
        self,
        response_packet: dict[str, object] | None,
        *,
        channel_role: int = 1,
        hop_limit: int = 4,
    ) -> None:
        self.response_packet = response_packet
        self.localNode = _FakeLocalNode(channel_role=channel_role, hop_limit=hop_limit)
        self.send_calls: list[dict[str, object]] = []
        self.nodes_by_num = {
            0x11223344: "!11223344",
            0x55667788: "!55667788",
            0xABCD1234: "!abcd1234",
            0x01020304: "!01020304",
        }

    def sendData(self, message, **kwargs):
        self.send_calls.append({"message": message, **kwargs})
        callback = kwargs.get("onResponse")
        if callable(callback) and self.response_packet is not None:
            callback(self.response_packet)
        return _FakeSentPacket(1234)

    def _nodeNumToId(self, num: int, isDest: bool = True):
        return self.nodes_by_num.get(num)


def test_run_network_tool_request_position_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2),
    )
    iface = _FakeIface(
        {
            "decoded": {
                "portnum": "POSITION_APP",
                "payload": b"good-position",
            }
        }
    )

    response = run_network_tool(
        NetworkToolRequest(command="request_position", destination="!abcd1234"),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is True
    assert response["command"] == "request_position"
    assert response["destination"] == "!abcd1234"
    assert response["sent_packet_id"] == 1234
    assert response["result"]["lat"] == pytest.approx(44.98)
    assert response["result"]["lon"] == pytest.approx(-93.26)
    assert response["result"]["altitude"] == 251
    assert response["result"]["precision_bits"] == 32
    assert "lat=44.980000 lon=-93.260000" in response["console_lines"][0]


def test_run_network_tool_request_position_handles_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2),
    )
    iface = _FakeIface(None)

    response = run_network_tool(
        NetworkToolRequest(
            command="request_position",
            destination="!abcd1234",
            timeout_ms=50,
        ),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is False
    assert response["error"] == "Timed out waiting for position response"


def test_run_network_tool_request_position_rejects_disabled_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2),
    )
    iface = _FakeIface(None, channel_role=0)

    response = run_network_tool(
        NetworkToolRequest(command="request_position", destination="!abcd1234"),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is False
    assert response["error"] == "Channel 0 is not enabled on the local node"


def test_run_network_tool_traceroute_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2),
    )
    iface = _FakeIface(
        {
            "to": 0x01020304,
            "from": 0xABCD1234,
            "hopStart": 4,
            "decoded": {
                "portnum": "TRACEROUTE_APP",
                "payload": b"good-traceroute",
            },
        }
    )

    response = run_network_tool(
        NetworkToolRequest(command="traceroute", destination="!abcd1234"),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is True
    assert response["command"] == "traceroute"
    assert response["destination"] == "!abcd1234"
    assert response["channel_index"] == 0
    assert response["hop_limit"] == 4
    assert response["sent_packet_id"] == 1234
    assert response["result"]["towards"] == [
        {"node": "!11223344", "snr_db": 8.5},
        {"node": "!55667788", "snr_db": 6.0},
        {"node": "!abcd1234", "snr_db": 4.5},
    ]
    assert response["result"]["back"] == [
        {"node": "!55667788", "snr_db": 5.5},
        {"node": "!11223344", "snr_db": 7.0},
        {"node": "!local", "snr_db": 8.0},
    ]
    assert response["console_lines"] == [
        "[traceroute] towards: !local -> !11223344 (8.5dB) -> !55667788 (6.0dB) -> !abcd1234 (4.5dB)",
        "[traceroute] back: !abcd1234 -> !55667788 (5.5dB) -> !11223344 (7.0dB) -> !local (8.0dB)",
    ]
    assert iface.send_calls[0]["portNum"] == _FakePortNum.TRACEROUTE_APP
    assert iface.send_calls[0]["hopLimit"] == 4


def test_run_network_tool_traceroute_handles_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2),
    )
    iface = _FakeIface(None)

    response = run_network_tool(
        NetworkToolRequest(
            command="traceroute",
            destination="!abcd1234",
            timeout_ms=50,
            hop_limit=5,
        ),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is False
    assert response["error"] == "Timed out waiting for traceroute response"
    assert response["console_lines"] == ["[traceroute] !abcd1234 | timed out waiting for response"]


def test_run_network_tool_traceroute_handles_no_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2),
    )
    iface = _FakeIface(
        {
            "decoded": {
                "routing": {
                    "errorReason": "NO_RESPONSE",
                }
            }
        }
    )

    response = run_network_tool(
        NetworkToolRequest(command="traceroute", destination="!abcd1234"),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is False
    assert response["error"] == "Destination did not respond"
    assert response["console_lines"] == ["[traceroute] !abcd1234 | destination did not respond"]
