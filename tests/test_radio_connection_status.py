import meshdash.radio_connection_status as connection_status_mod


def _clear_connection_status_cache() -> None:
    with connection_status_mod._CACHE_LOCK:
        connection_status_mod._CACHE.clear()


def test_parse_device_connection_status_packet_reads_wifi_signal_and_network_state():
    packet = {
        "decoded": {
            "admin": {
                "getDeviceConnectionStatusResponse": {
                    "wifi": {
                        "status": {
                            "ipAddress": 3232235948,
                            "isConnected": True,
                            "isMqttConnected": False,
                            "isSyslogConnected": True,
                        },
                        "ssid": "The LAN Before Time",
                        "rssi": -67,
                    }
                }
            }
        }
    }

    parsed = connection_status_mod._parse_device_connection_status_packet(
        packet,
        now_ts_fn=lambda: 123.0,
    )

    assert parsed is not None
    assert parsed["captured_at_unix"] == 123
    assert parsed["source"] == "admin.get_device_connection_status"
    wifi = parsed["wifi"]
    assert wifi["ssid"] == "The LAN Before Time"
    assert wifi["rssi_dbm"] == -67
    assert wifi["ip_address"] == "192.168.1.172"
    assert wifi["is_connected"] is True
    assert wifi["is_mqtt_connected"] is False
    assert wifi["is_syslog_connected"] is True


def test_parse_device_connection_status_packet_supports_snake_case_shapes():
    packet = {
        "decoded": {
            "admin": {
                "get_device_connection_status_response": {
                    "wifi": {
                        "status": {
                            "ip_address": "192.168.1.172",
                            "is_connected": "true",
                        },
                        "ssid": "mesh",
                        "rssi": "-70",
                    }
                }
            }
        }
    }

    parsed = connection_status_mod._parse_device_connection_status_packet(packet)
    assert parsed is not None
    assert parsed["wifi"]["ip_address"] == "192.168.1.172"
    assert parsed["wifi"]["is_connected"] is True
    assert parsed["wifi"]["rssi_dbm"] == -70


def test_parse_device_connection_status_packet_decodes_little_endian_numeric_ipv4():
    packet = {
        "decoded": {
            "admin": {
                "getDeviceConnectionStatusResponse": {
                    "wifi": {
                        "status": {
                            # 192.168.1.69 represented as little-endian uint32.
                            "ipAddress": 0x4501A8C0,
                            "isConnected": True,
                        },
                        "ssid": "mesh",
                    }
                }
            }
        }
    }

    parsed = connection_status_mod._parse_device_connection_status_packet(packet)
    assert parsed is not None
    assert parsed["wifi"]["ip_address"] == "192.168.1.69"


def test_parse_device_connection_status_packet_ignores_zero_wifi_rssi():
    packet = {
        "decoded": {
            "admin": {
                "getDeviceConnectionStatusResponse": {
                    "wifi": {
                        "status": {
                            "isConnected": True,
                        },
                        "ssid": "mesh",
                        "rssi": 0,
                    }
                }
            }
        }
    }

    parsed = connection_status_mod._parse_device_connection_status_packet(packet)
    assert parsed is not None
    assert parsed["wifi"]["is_connected"] is True
    assert "rssi_dbm" not in parsed["wifi"]


def test_parse_device_connection_status_packet_reads_rssi_from_wifi_status_block():
    packet = {
        "decoded": {
            "admin": {
                "getDeviceConnectionStatusResponse": {
                    "wifi": {
                        "status": {
                            "isConnected": True,
                            "rssi": -64,
                        },
                        "ssid": "mesh",
                    }
                }
            }
        }
    }

    parsed = connection_status_mod._parse_device_connection_status_packet(packet)
    assert parsed is not None
    assert parsed["wifi"]["is_connected"] is True
    assert parsed["wifi"]["rssi_dbm"] == -64


def test_parse_device_connection_status_packet_supports_wrapped_uint32_rssi():
    packet = {
        "decoded": {
            "admin": {
                "getDeviceConnectionStatusResponse": {
                    "wifi": {
                        "status": {
                            "isConnected": True,
                        },
                        "ssid": "mesh",
                        "rssi": 4294967231,  # -65 encoded as uint32
                    }
                }
            }
        }
    }

    parsed = connection_status_mod._parse_device_connection_status_packet(packet)
    assert parsed is not None
    assert parsed["wifi"]["rssi_dbm"] == -65


def test_get_radio_connection_status_uses_cached_response_and_throttles_requests():
    _clear_connection_status_cache()
    original_enabled = connection_status_mod.radio_connection_status_enabled()
    connection_status_mod.set_radio_connection_status_enabled(True)

    class _AdminMessage:
        def __init__(self):
            self.get_device_connection_status_request = False

    class _AdminPb2:
        AdminMessage = _AdminMessage

    original_admin_pb2 = connection_status_mod.admin_pb2
    connection_status_mod.admin_pb2 = _AdminPb2()

    class _Clock:
        value = 100.0

        def __call__(self):
            return self.value

    class _LocalNode:
        def __init__(self):
            self.calls = 0

        def _sendAdmin(self, _message, *, wantResponse=True, onResponse=None):
            self.calls += 1
            if callable(onResponse):
                onResponse(
                    {
                        "decoded": {
                            "admin": {
                                "getDeviceConnectionStatusResponse": {
                                    "wifi": {
                                        "status": {
                                            "ipAddress": 3232235948,
                                            "isConnected": True,
                                        },
                                        "ssid": "The LAN Before Time",
                                        "rssi": -65,
                                    }
                                }
                            }
                        }
                    }
                )

    class _Iface:
        def __init__(self):
            self.localNode = _LocalNode()

    try:
        clock = _Clock()
        iface = _Iface()

        first = connection_status_mod.get_radio_connection_status(
            iface,
            now_ts_fn=clock,
            refresh_seconds=20,
            request_timeout_seconds=6,
        )
        assert first is not None
        assert first["wifi"]["rssi_dbm"] == -65
        assert first["age_seconds"] == 0
        assert iface.localNode.calls == 1

        clock.value = 101.0
        second = connection_status_mod.get_radio_connection_status(
            iface,
            now_ts_fn=clock,
            refresh_seconds=20,
            request_timeout_seconds=6,
        )
        assert second is not None
        assert second["wifi"]["ssid"] == "The LAN Before Time"
        assert second["age_seconds"] == 1
        assert iface.localNode.calls == 1
    finally:
        connection_status_mod.set_radio_connection_status_enabled(original_enabled)
        connection_status_mod.admin_pb2 = original_admin_pb2


def test_get_radio_connection_status_returns_none_when_disabled():
    _clear_connection_status_cache()
    original_enabled = connection_status_mod.radio_connection_status_enabled()
    connection_status_mod.set_radio_connection_status_enabled(False)

    class _LocalNode:
        def __init__(self):
            self.calls = 0

        def _sendAdmin(self, *_args, **_kwargs):
            self.calls += 1

    class _Iface:
        def __init__(self):
            self.localNode = _LocalNode()

    try:
        iface = _Iface()
        result = connection_status_mod.get_radio_connection_status(iface, now_ts_fn=lambda: 100.0)
        assert result is None
        assert iface.localNode.calls == 0
    finally:
        connection_status_mod.set_radio_connection_status_enabled(original_enabled)
