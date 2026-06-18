from types import SimpleNamespace

import pytest

import meshdash.radio_connection_status as radio_status


class _Clock:
    def __init__(self, value: float) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


class _FakeAdminMessage:
    def __init__(self) -> None:
        self.get_device_connection_status_request = False


class _FakeAdminPb2:
    AdminMessage = _FakeAdminMessage


class _FakeLocalNode:
    def __init__(self, response_packet: object | None, *, respond: bool = True, raise_error: Exception | None = None) -> None:
        self.response_packet = response_packet
        self.respond = respond
        self.raise_error = raise_error
        self.send_calls: list[dict[str, object]] = []

    def _sendAdmin(self, message: object, *, wantResponse: bool, onResponse: object) -> None:  # noqa: N802
        self.send_calls.append(
            {
                "message": message,
                "wantResponse": wantResponse,
                "onResponse": onResponse,
            }
        )
        if self.raise_error is not None:
            raise self.raise_error
        if self.respond:
            onResponse(self.response_packet)


@pytest.fixture(autouse=True)
def _reset_radio_status_cache(monkeypatch: pytest.MonkeyPatch):
    with radio_status._CACHE_LOCK:
        radio_status._CACHE.clear()
    monkeypatch.setattr(radio_status, "admin_pb2", _FakeAdminPb2)
    radio_status.set_radio_connection_status_enabled(True)
    yield
    radio_status.set_radio_connection_status_enabled(True)
    with radio_status._CACHE_LOCK:
        radio_status._CACHE.clear()


def _connection_status_packet() -> dict[str, object]:
    return {
        "decoded": {
            "admin": {
                "getDeviceConnectionStatusResponse": {
                    "wifi": {
                        "ssid": "MeshNet",
                        "rssi": 0xFFFFFFCE,
                        "status": {
                            "ipAddress": 0x0100A8C0,
                            "isConnected": "yes",
                            "isMqttConnected": "0",
                            "isSyslogConnected": 1,
                        },
                    },
                    "ethernet": {
                        "status": {
                            "ip_address": "10.0.0.2",
                            "is_connected": False,
                        }
                    },
                    "bluetooth": {
                        "pin": "123456",
                        "rssi": "-70",
                        "isConnected": 1,
                    },
                    "serial": {
                        "baud": "115200",
                        "is_connected": "true",
                    },
                }
            }
        }
    }


def test_get_radio_connection_status_requests_admin_and_parses_response() -> None:
    clock = _Clock(1000.0)
    local_node = _FakeLocalNode(_connection_status_packet())
    iface = SimpleNamespace(localNode=local_node)

    status = radio_status.get_radio_connection_status(iface, now_ts_fn=clock)

    assert status == {
        "source": "admin.get_device_connection_status",
        "captured_at_unix": 1000,
        "wifi": {
            "ip_address": "192.168.0.1",
            "is_connected": True,
            "is_mqtt_connected": False,
            "is_syslog_connected": True,
            "ssid": "MeshNet",
            "rssi_dbm": -50,
        },
        "ethernet": {
            "ip_address": "10.0.0.2",
            "is_connected": False,
        },
        "bluetooth": {
            "pin": 123456,
            "rssi_dbm": -70,
            "is_connected": True,
        },
        "serial": {
            "baud": 115200,
            "is_connected": True,
        },
        "age_seconds": 0,
    }
    assert len(local_node.send_calls) == 1
    assert local_node.send_calls[0]["wantResponse"] is True
    message = local_node.send_calls[0]["message"]
    assert message.get_device_connection_status_request is True


def test_get_radio_connection_status_returns_cached_status_until_refresh_interval() -> None:
    clock = _Clock(1000.0)
    local_node = _FakeLocalNode(_connection_status_packet())
    iface = SimpleNamespace(localNode=local_node)

    first = radio_status.get_radio_connection_status(iface, now_ts_fn=clock, refresh_seconds=20)
    clock.value = 1005.0
    second = radio_status.get_radio_connection_status(iface, now_ts_fn=clock, refresh_seconds=20)

    assert first is not None
    assert second is not None
    assert second["age_seconds"] == 5
    assert len(local_node.send_calls) == 1


def test_get_radio_connection_status_reports_invalid_response_and_send_errors() -> None:
    invalid_iface = SimpleNamespace(localNode=_FakeLocalNode({"decoded": {"admin": {}}}))
    invalid = radio_status.get_radio_connection_status(invalid_iface, now_ts_fn=lambda: 1000.0)

    error_iface = SimpleNamespace(localNode=_FakeLocalNode(None, raise_error=RuntimeError("send failed")))
    send_error = radio_status.get_radio_connection_status(error_iface, now_ts_fn=lambda: 1000.0)

    assert invalid == {"error": "Invalid connection status response"}
    assert send_error == {"error": "send failed"}


def test_get_radio_connection_status_handles_missing_protobuf_and_unsupported_node(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(radio_status, "admin_pb2", None)
    proto_iface = SimpleNamespace(localNode=_FakeLocalNode(None))
    proto_error = radio_status.get_radio_connection_status(
        proto_iface,
        now_ts_fn=lambda: 1000.0,
    )

    monkeypatch.setattr(radio_status, "admin_pb2", _FakeAdminPb2)
    unsupported_iface = SimpleNamespace(localNode=object())
    unsupported = radio_status.get_radio_connection_status(unsupported_iface, now_ts_fn=lambda: 1000.0)

    assert proto_error == {"error": "Connection status protobuf unavailable"}
    assert unsupported == {"error": "Admin connection status request unsupported"}


def test_get_radio_connection_status_times_out_in_flight_requests() -> None:
    clock = _Clock(1000.0)
    local_node = _FakeLocalNode(None, respond=False)
    iface = SimpleNamespace(localNode=local_node)

    first = radio_status.get_radio_connection_status(
        iface,
        now_ts_fn=clock,
        refresh_seconds=3,
        request_timeout_seconds=5,
    )
    clock.value = 1006.0
    second = radio_status.get_radio_connection_status(
        iface,
        now_ts_fn=clock,
        refresh_seconds=3,
        request_timeout_seconds=5,
    )

    assert first is None
    assert second == {"error": "Connection status request timed out"}
    assert len(local_node.send_calls) == 2


def test_radio_connection_status_enabled_toggle_suppresses_requests() -> None:
    local_node = _FakeLocalNode(_connection_status_packet())
    iface = SimpleNamespace(localNode=local_node)

    assert radio_status.set_radio_connection_status_enabled(False) is False
    assert radio_status.radio_connection_status_enabled() is False
    assert radio_status.get_radio_connection_status(iface, now_ts_fn=lambda: 1000.0) is None
    assert local_node.send_calls == []

    assert radio_status.set_radio_connection_status_enabled(True) is True
    assert radio_status.radio_connection_status_enabled() is True
