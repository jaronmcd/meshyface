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
    NODEINFO_APP = 4
    POSITION_APP = 3
    TELEMETRY_APP = 67
    TRACEROUTE_APP = 70
    ALERT_APP = 89


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


class _FakeUser:
    def __init__(self) -> None:
        self.id = ""
        self.long_name = ""
        self.short_name = ""
        self.hw_model = 0
        self.role = 0

    def SerializeToString(self) -> bytes:
        return b"nodeinfo-request"

    def ParseFromString(self, payload: bytes) -> None:
        if payload == b"good-nodeinfo":
            self.id = "!abcd1234"
            self.long_name = "Alpha Ridge"
            self.short_name = "ALP"
            self.hw_model = 12
            self.role = 1
        elif payload == b"minimal-nodeinfo":
            self.id = "!abcd1234"


_FakeMeshPb2.User = _FakeUser


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


class _FakeTelemetryMetrics:
    def __init__(self) -> None:
        object.__setattr__(self, "_values", {})

    def CopyFrom(self, other) -> None:
        source = getattr(other, "_values", {})
        object.__setattr__(self, "_values", dict(source if isinstance(source, dict) else {}))

    def __getattr__(self, name: str):
        values = object.__getattribute__(self, "_values")
        return values.get(name)

    def __setattr__(self, name: str, value) -> None:
        values = object.__getattribute__(self, "_values")
        values[name] = value

    def to_dict(self) -> dict[str, object]:
        values = object.__getattribute__(self, "_values")
        return dict(values if isinstance(values, dict) else {})


class _FakeTelemetry:
    def __init__(self) -> None:
        self.device_metrics = _FakeTelemetryMetrics()
        self.environment_metrics = _FakeTelemetryMetrics()
        self.air_quality_metrics = _FakeTelemetryMetrics()
        self.power_metrics = _FakeTelemetryMetrics()
        self.local_stats = _FakeTelemetryMetrics()

    def SerializeToString(self) -> bytes:
        return b"telemetry-request"

    def ParseFromString(self, payload: bytes) -> None:
        self.device_metrics = _FakeTelemetryMetrics()
        self.environment_metrics = _FakeTelemetryMetrics()
        self.air_quality_metrics = _FakeTelemetryMetrics()
        self.power_metrics = _FakeTelemetryMetrics()
        self.local_stats = _FakeTelemetryMetrics()
        if payload == b"good-telemetry-device":
            self.device_metrics.battery_level = 88
            self.device_metrics.voltage = 4.21
            return
        if payload == b"good-telemetry-power":
            self.power_metrics.ch1_voltage = 12.3
            self.power_metrics.ch1_current = 1.1
            return
        if payload == b"bad-telemetry":
            raise ValueError("bad telemetry payload")

    def to_dict(self) -> dict[str, object]:
        for key in (
            "device_metrics",
            "environment_metrics",
            "air_quality_metrics",
            "power_metrics",
            "local_stats",
        ):
            metrics = getattr(self, key, None)
            if metrics is None or not hasattr(metrics, "to_dict"):
                continue
            values = metrics.to_dict()
            if values:
                return {key: values}
        return {}


class _FakeTelemetryPb2:
    Telemetry = _FakeTelemetry
    DeviceMetrics = _FakeTelemetryMetrics
    EnvironmentMetrics = _FakeTelemetryMetrics
    AirQualityMetrics = _FakeTelemetryMetrics
    PowerMetrics = _FakeTelemetryMetrics
    LocalStats = _FakeTelemetryMetrics


class _FakeSentPacket:
    def __init__(self, packet_id: int) -> None:
        self.id = packet_id


class _FakeRemoteNode:
    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        self.reboot_calls: list[int] = []
        self.shutdown_calls: list[int] = []
        self.set_time_calls: list[int] = []
        self.request_config_calls: list[int] = []
        self.request_channels_calls: list[int] = []
        self.get_metadata_calls: int = 0
        self.reset_nodedb_calls: int = 0
        self.factory_reset_calls: list[bool] = []

    def reboot(self, secs: int = 10):
        self.reboot_calls.append(secs)
        return _FakeSentPacket(5678)

    def shutdown(self, secs: int = 10):
        self.shutdown_calls.append(secs)
        return _FakeSentPacket(6789)

    def setTime(self, timeSec: int = 0):
        self.set_time_calls.append(timeSec)
        return _FakeSentPacket(7890)

    def requestConfig(self, configType):
        self.request_config_calls.append(int(configType))

    def requestChannels(self, startingIndex: int = 0):
        self.request_channels_calls.append(int(startingIndex))

    def getMetadata(self):
        self.get_metadata_calls += 1

    def resetNodeDb(self):
        self.reset_nodedb_calls += 1
        return _FakeSentPacket(8800)

    def factoryReset(self, full: bool = False):
        self.factory_reset_calls.append(bool(full))
        return _FakeSentPacket(8900 if full else 8890)


class _FakeChannel:
    def __init__(self, role: int) -> None:
        self.role = role


class _FakeLocalNode:
    def __init__(self, channel_role: int = 1, hop_limit: int = 4, node_num: int = 0x01020304) -> None:
        self._channel_role = channel_role
        self.nodeNum = node_num
        self.reboot_calls: list[int] = []
        self.shutdown_calls: list[int] = []
        self.set_time_calls: list[int] = []
        self.user = {
            "id": f"!{node_num:08x}",
            "longName": "Local Ridge",
            "shortName": "LCL",
            "hwModel": 9,
            "role": 1,
            "isLicensed": True,
            "isUnmessagable": False,
        }
        self.localConfig = type(
            "_FakeLocalConfig",
            (),
            {"lora": type("_FakeLoraConfig", (), {"hop_limit": hop_limit})()},
        )()

    def getChannelByChannelIndex(self, channel_index: int):
        if channel_index != 0:
            return None
        return _FakeChannel(self._channel_role)

    def reboot(self, secs: int = 10):
        self.reboot_calls.append(secs)
        return _FakeSentPacket(1111)

    def shutdown(self, secs: int = 10):
        self.shutdown_calls.append(secs)
        return _FakeSentPacket(2222)

    def setTime(self, timeSec: int = 0):
        self.set_time_calls.append(timeSec)
        return _FakeSentPacket(3333)


class _FakeIface:
    def __init__(
        self,
        response_packet: dict[str, object] | None,
        *,
        channel_role: int = 1,
        hop_limit: int = 4,
    ) -> None:
        self.response_packet = response_packet
        local_node_num = 0x01020304
        self.localNode = _FakeLocalNode(
            channel_role=channel_role,
            hop_limit=hop_limit,
            node_num=local_node_num,
        )
        self.send_calls: list[dict[str, object]] = []
        self.alert_calls: list[dict[str, object]] = []
        self.text_calls: list[dict[str, object]] = []
        self.nodes_by_num = {
            0x11223344: "!11223344",
            0x55667788: "!55667788",
            0xABCD1234: "!abcd1234",
            local_node_num: "!01020304",
        }
        self.nodesByNum = {
            local_node_num: {
                "num": local_node_num,
                "user": {
                    "id": "!01020304",
                    "longName": "Local Ridge",
                    "shortName": "LCL",
                    "hwModel": 9,
                    "role": 1,
                    "isLicensed": True,
                    "isUnmessagable": False,
                },
            },
        }
        self.remote_nodes = {
            "!abcd1234": _FakeRemoteNode("!abcd1234"),
            "!11223344": _FakeRemoteNode("!11223344"),
        }

    def sendData(self, message, **kwargs):
        self.send_calls.append({"message": message, **kwargs})
        callback = kwargs.get("onResponse")
        if callable(callback) and self.response_packet is not None:
            callback(self.response_packet)
        return _FakeSentPacket(1234)

    def _nodeNumToId(self, num: int, isDest: bool = True):
        return self.nodes_by_num.get(num)

    def sendAlert(self, text: str, **kwargs):
        self.alert_calls.append({"text": text, **kwargs})
        return _FakeSentPacket(4321)

    def sendText(self, text: str, **kwargs):
        self.text_calls.append({"text": text, **kwargs})
        return _FakeSentPacket(2468)

    def getNode(
        self,
        nodeId: str,
        requestChannels: bool = True,
        requestChannelAttempts: int = 3,
        timeout: int = 300,
    ):
        if nodeId == "!01020304":
            return self.localNode
        node = self.remote_nodes.get(nodeId)
        if node is None:
            raise ValueError(f"Unknown node: {nodeId}")
        return node


def test_run_network_tool_request_position_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
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


def test_run_network_tool_ping_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
    )
    iface = _FakeIface(
        {
            "decoded": {
                "portnum": "NODEINFO_APP",
                "payload": b"good-nodeinfo",
            }
        }
    )

    response = run_network_tool(
        NetworkToolRequest(command="ping", destination="!abcd1234", hop_limit=3),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is True
    assert response["command"] == "ping"
    assert response["destination"] == "!abcd1234"
    assert response["hop_limit"] == 3
    assert response["sent_packet_id"] == 1234
    assert response["result"]["id"] == "!abcd1234"
    assert response["result"]["long_name"] == "Alpha Ridge"
    assert response["result"]["short_name"] == "ALP"
    assert response["result"]["hw_model"] == 12
    assert response["result"]["role"] == 1
    assert response["console_lines"] == [
        "[ping] !abcd1234 | nodeinfo response | id=!abcd1234 | long=Alpha Ridge | short=ALP | hw=12 | role=1"
    ]
    assert iface.send_calls[0]["portNum"] == _FakePortNum.NODEINFO_APP
    assert iface.send_calls[0]["hopLimit"] == 3


def test_run_network_tool_send_node_info_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
    )
    iface = _FakeIface(None)

    response = run_network_tool(
        NetworkToolRequest(command="send_node_info", channel_index=0, hop_limit=2),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is True
    assert response["command"] == "send_node_info"
    assert response["destination"] == "^all"
    assert response["channel_index"] == 0
    assert response["hop_limit"] == 2
    assert response["sent_packet_id"] == 1234
    assert response["result"]["id"] == "!01020304"
    assert response["result"]["long_name"] == "Local Ridge"
    assert response["result"]["short_name"] == "LCL"
    assert response["result"]["hw_model"] == 9
    assert response["result"]["role"] == 1
    assert response["result"]["is_licensed"] is True
    assert response["result"]["is_unmessagable"] is False
    assert iface.send_calls[0]["destinationId"] == "^all"
    assert iface.send_calls[0]["portNum"] == _FakePortNum.NODEINFO_APP
    assert iface.send_calls[0]["wantResponse"] is False
    assert iface.send_calls[0]["hopLimit"] == 2


def test_run_network_tool_request_telemetry_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
    )
    iface = _FakeIface(
        {
            "decoded": {
                "portnum": "TELEMETRY_APP",
                "payload": b"good-telemetry-device",
            }
        }
    )

    response = run_network_tool(
        NetworkToolRequest(
            command="request_telemetry",
            destination="!abcd1234",
            telemetry_type="device_metrics",
            hop_limit=4,
        ),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is True
    assert response["command"] == "request_telemetry"
    assert response["destination"] == "!abcd1234"
    assert response["telemetry_type"] == "device_metrics"
    assert response["result"]["requested_type"] == "device_metrics"
    assert response["result"]["response_type"] == "device_metrics"
    assert response["result"]["response"]["device_metrics"]["battery_level"] == 88
    assert response["sent_packet_id"] == 1234
    assert iface.send_calls[0]["portNum"] == _FakePortNum.TELEMETRY_APP
    assert iface.send_calls[0]["wantResponse"] is True
    assert iface.send_calls[0]["hopLimit"] == 4


def test_run_network_tool_send_alert_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
    )
    iface = _FakeIface(None)

    response = run_network_tool(
        NetworkToolRequest(
            command="send_alert",
            destination="!abcd1234",
            text="Weather warning",
            channel_index=0,
            hop_limit=2,
        ),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is True
    assert response["command"] == "send_alert"
    assert response["destination"] == "!abcd1234"
    assert response["channel_index"] == 0
    assert response["hop_limit"] == 2
    assert response["sent_packet_id"] == 1234
    assert response["result"]["text"] == "Weather warning"
    assert response["console_lines"] == [
        '[alert] !abcd1234 | text="Weather warning" | ch=0 | hop=2'
    ]
    assert iface.send_calls[0]["destinationId"] == "!abcd1234"
    assert iface.send_calls[0]["channelIndex"] == 0
    assert iface.send_calls[0]["hopLimit"] == 2
    assert iface.send_calls[0]["portNum"] == _FakePortNum.ALERT_APP
    assert iface.send_calls[0]["message"] == b"Weather warning"
    assert iface.alert_calls == []


def test_run_network_tool_send_alert_falls_back_when_alert_port_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    class _PortNumNoAlert:
        NODEINFO_APP = 4
        POSITION_APP = 3
        TELEMETRY_APP = 67
        TRACEROUTE_APP = 70

    class _PortnumsNoAlert:
        PortNum = _PortNumNoAlert

    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _PortnumsNoAlert, _FakeTelemetryPb2),
    )
    iface = _FakeIface(None)

    response = run_network_tool(
        NetworkToolRequest(
            command="send_alert",
            destination="!abcd1234",
            text="Weather warning",
            channel_index=0,
            hop_limit=2,
        ),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is True
    assert response["sent_packet_id"] == 4321
    assert iface.send_calls == []
    assert iface.alert_calls[0]["destinationId"] == "!abcd1234"
    assert iface.alert_calls[0]["channelIndex"] == 0
    assert iface.alert_calls[0]["hopLimit"] == 2


def test_run_network_tool_send_text_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
    )
    iface = _FakeIface(None)

    response = run_network_tool(
        NetworkToolRequest(
            command="send_text",
            destination="!abcd1234",
            text="hello mesh",
            channel_index=0,
            hop_limit=3,
        ),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is True
    assert response["command"] == "send_text"
    assert response["destination"] == "!abcd1234"
    assert response["channel_index"] == 0
    assert response["hop_limit"] == 3
    assert response["sent_packet_id"] == 2468
    assert response["result"]["text"] == "hello mesh"
    assert response["console_lines"] == ['[sendtext] !abcd1234 | text="hello mesh" | ch=0 | hop=3']
    assert iface.text_calls[0]["destinationId"] == "!abcd1234"
    assert iface.text_calls[0]["channelIndex"] == 0
    assert iface.text_calls[0]["hopLimit"] == 3


def test_run_network_tool_request_config_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
    )
    iface = _FakeIface(None)

    response = run_network_tool(
        NetworkToolRequest(
            command="request_config",
            destination="!abcd1234",
            config_type="lora",
        ),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is True
    assert response["command"] == "request_config"
    assert response["destination"] == "!abcd1234"
    assert response["config_type"] == "LORA_CONFIG"
    assert response["console_lines"] == ["[config] !abcd1234 | requested LORA_CONFIG"]
    assert iface.remote_nodes["!abcd1234"].request_config_calls == [5]


def test_run_network_tool_request_channels_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
    )
    iface = _FakeIface(None)

    response = run_network_tool(
        NetworkToolRequest(
            command="request_channels",
            destination="!abcd1234",
            starting_index=2,
        ),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is True
    assert response["command"] == "request_channels"
    assert response["destination"] == "!abcd1234"
    assert response["starting_index"] == 2
    assert response["console_lines"] == ["[channels] !abcd1234 | requested from index 2"]
    assert iface.remote_nodes["!abcd1234"].request_channels_calls == [2]


def test_run_network_tool_device_metadata_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
    )
    iface = _FakeIface(None)

    response = run_network_tool(
        NetworkToolRequest(command="device_metadata", destination="!abcd1234"),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is True
    assert response["command"] == "device_metadata"
    assert response["destination"] == "!abcd1234"
    assert response["console_lines"] == ["[device-metadata] !abcd1234 | request sent"]
    assert iface.remote_nodes["!abcd1234"].get_metadata_calls == 1


def test_run_network_tool_reset_nodedb_requires_confirm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
    )
    iface = _FakeIface(None)

    response = run_network_tool(
        NetworkToolRequest(command="reset_nodedb", destination="!abcd1234"),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is False
    assert "without confirmation" in str(response.get("error") or "")
    assert iface.remote_nodes["!abcd1234"].reset_nodedb_calls == 0


def test_run_network_tool_reset_nodedb_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
    )
    iface = _FakeIface(None)

    response = run_network_tool(
        NetworkToolRequest(command="reset_nodedb", destination="!abcd1234", confirm=True),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is True
    assert response["command"] == "reset_nodedb"
    assert response["destination"] == "!abcd1234"
    assert response["sent_packet_id"] == 8800
    assert response["console_lines"] == ["[reset-nodedb] !abcd1234 | request sent"]
    assert iface.remote_nodes["!abcd1234"].reset_nodedb_calls == 1


def test_run_network_tool_factory_reset_requires_confirm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
    )
    iface = _FakeIface(None)

    response = run_network_tool(
        NetworkToolRequest(command="factory_reset", destination="!abcd1234"),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is False
    assert "without confirmation" in str(response.get("error") or "")
    assert iface.remote_nodes["!abcd1234"].factory_reset_calls == []


def test_run_network_tool_factory_reset_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
    )
    iface = _FakeIface(None)

    response = run_network_tool(
        NetworkToolRequest(command="factory_reset", destination="!abcd1234", confirm=True),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is True
    assert response["command"] == "factory_reset"
    assert response["destination"] == "!abcd1234"
    assert response["sent_packet_id"] == 8890
    assert response["result"]["full_device"] is False
    assert response["console_lines"] == ["[factory-reset] !abcd1234 | request sent"]
    assert iface.remote_nodes["!abcd1234"].factory_reset_calls == [False]


def test_run_network_tool_factory_reset_device_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
    )
    iface = _FakeIface(None)

    response = run_network_tool(
        NetworkToolRequest(command="factory_reset_device", destination="!abcd1234", confirm=True),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is True
    assert response["command"] == "factory_reset_device"
    assert response["destination"] == "!abcd1234"
    assert response["sent_packet_id"] == 8900
    assert response["result"]["full_device"] is True
    assert response["console_lines"] == ["[factory-reset-device] !abcd1234 | request sent"]
    assert iface.remote_nodes["!abcd1234"].factory_reset_calls == [True]


def test_run_network_tool_reboot_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
    )
    iface = _FakeIface(None)

    response = run_network_tool(
        NetworkToolRequest(command="reboot", destination="!abcd1234", delay_seconds=5),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is True
    assert response["command"] == "reboot"
    assert response["destination"] == "!abcd1234"
    assert response["delay_seconds"] == 5
    assert response["sent_packet_id"] == 5678
    assert response["console_lines"] == ["[reboot] !abcd1234 | scheduled reboot in 5s"]
    assert iface.remote_nodes["!abcd1234"].reboot_calls == [5]


def test_run_network_tool_shutdown_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
    )
    iface = _FakeIface(None)

    response = run_network_tool(
        NetworkToolRequest(command="shutdown", destination="!abcd1234", delay_seconds=7),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is True
    assert response["command"] == "shutdown"
    assert response["destination"] == "!abcd1234"
    assert response["delay_seconds"] == 7
    assert response["sent_packet_id"] == 6789
    assert response["console_lines"] == ["[shutdown] !abcd1234 | scheduled shutdown in 7s"]
    assert iface.remote_nodes["!abcd1234"].shutdown_calls == [7]


def test_run_network_tool_set_time_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
    )
    iface = _FakeIface(None)

    response = run_network_tool(
        NetworkToolRequest(command="set_time", destination="!abcd1234", time_sec=1715985600),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is True
    assert response["command"] == "set_time"
    assert response["destination"] == "!abcd1234"
    assert response["time_sec"] == 1715985600
    assert response["sent_packet_id"] == 7890
    assert response["console_lines"] == ["[set-time] !abcd1234 | epoch=1715985600"]
    assert iface.remote_nodes["!abcd1234"].set_time_calls == [1715985600]


def test_run_network_tool_request_telemetry_handles_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
    )
    iface = _FakeIface(None)

    response = run_network_tool(
        NetworkToolRequest(
            command="request_telemetry",
            destination="!abcd1234",
            timeout_ms=50,
            telemetry_type="power_metrics",
        ),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is False
    assert response["command"] == "request_telemetry"
    assert response["error"] == "Timed out waiting for telemetry response"
    assert response["console_lines"] == ["[telemetry] !abcd1234 | timed out waiting for response"]


def test_run_network_tool_ping_handles_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
    )
    iface = _FakeIface(None)

    response = run_network_tool(
        NetworkToolRequest(command="ping", destination="!abcd1234", timeout_ms=50),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is False
    assert response["error"] == "Timed out waiting for ping response"
    assert response["console_lines"] == ["[ping] !abcd1234 | timed out waiting for response"]


def test_run_network_tool_ping_handles_no_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
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
        NetworkToolRequest(command="ping", destination="!abcd1234"),
        iface=iface,
        send_lock=threading.Lock(),
    )

    assert response["ok"] is False
    assert response["error"] == "Destination did not respond"
    assert response["console_lines"] == ["[ping] !abcd1234 | destination did not respond"]


def test_run_network_tool_request_position_handles_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_network_tools._load_meshtastic_modules",
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
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
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
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
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
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
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
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
        lambda: (_FakeChannelPb2, _FakeMeshPb2, _FakePortnumsPb2, _FakeTelemetryPb2),
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
