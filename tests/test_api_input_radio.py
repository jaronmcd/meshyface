import pytest

from meshdash import api_input_radio as radio_input
from meshdash.api_input_radio import parse_radio_settings_request


def test_parse_radio_settings_request_defaults_to_empty_objects():
    request = parse_radio_settings_request(b"{}")
    assert request.lora == {}
    assert request.local == {}
    assert request.module == {}
    assert request.owner == {}
    assert request.fixed_position == {}
    assert request.time_sync == {}
    assert request.actions == {}


def test_parse_radio_settings_request_filters_to_supported_value_shapes():
    request = parse_radio_settings_request(
        b"""
        {
          "lora": {
            "region": "US",
            "tx_power": 17,
            "enabled": true,
            "channels": [1, "2", null],
            "none_field": null,
            "nested": {"sub": 1},
            "complex": [{"bad": 1}]
          },
          "local": {
            "device": {
              "role": "ROUTER",
              "is_router": "true"
            },
            "network": "bad-shape"
          },
          "module": {
            "mqtt": {
              "enabled": true,
              "address": "mqtt.example.net"
            }
          },
          "owner": {
            "short": "AB12",
            "long_name": "Alpha Bravo",
            "isLicensed": "yes",
            "is_unmessagable": 0,
            "drop": {"bad": true}
          },
          "actions": {
            "reset_nodedb": "yes",
            "reset_dashboard_db": 1,
            "set_time": "on",
            "regenerate_node_id": "true",
            "set_fixed_position": 1,
            "clear_fixed_position": "false",
            "unknown": true
          },
          "fixed_position": {
            "latitude": "44.98",
            "longitude": -93.26,
            "altitude": 260,
            "extra": {"bad": true}
          },
          "time_sync": {
            "enabled": "1",
            "ntp_server": "pool.ntp.org",
            "timezone": "America/Chicago",
            "timeout": 5000,
            "drop": {"bad": true}
          }
        }
        """
    )

    assert request.lora == {
        "region": "US",
        "tx_power": 17,
        "enabled": True,
        "channels": [1, "2", None],
        "none_field": None,
        "nested": {"sub": 1},
    }
    assert request.local == {"device": {"role": "ROUTER", "is_router": "true"}}
    assert request.module == {"mqtt": {"enabled": True, "address": "mqtt.example.net"}}
    assert request.owner == {
        "short_name": "AB12",
        "long_name": "Alpha Bravo",
        "is_licensed": True,
        "is_unmessagable": False,
    }
    assert request.fixed_position == {"lat": "44.98", "lon": -93.26, "alt": 260}
    assert request.time_sync == {
        "enabled": True,
        "server": "pool.ntp.org",
        "timezone": "America/Chicago",
        "timeout_ms": 5000,
    }
    assert request.actions == {
        "reset_nodedb": True,
        "reset_dashboard_db": True,
        "set_time": True,
        "regenerate_node_id": True,
        "set_fixed_position": True,
        "clear_fixed_position": False,
    }


def test_parse_radio_settings_request_supports_top_level_reset_alias():
    request = parse_radio_settings_request(
        b'{"reset_nodedb":"1","reset_dashboard_db":"true","set_time":"yes","regenerate_node_id":"1","set_fixed_position":"on","clear_fixed_position":"0"}'
    )
    assert request.actions == {
        "reset_nodedb": True,
        "reset_dashboard_db": True,
        "set_time": True,
        "regenerate_node_id": True,
        "set_fixed_position": True,
        "clear_fixed_position": False,
    }


def test_parse_radio_settings_request_ignores_redacted_secret_placeholders():
    request = parse_radio_settings_request(
        b"""
        {
          "local": {
            "network": {
              "wifi_enabled": true,
              "wifi_ssid": "The LAN Before Time",
              "wifi_psk": "<redacted>",
              "ntp_server": "meshtastic.pool.ntp.org"
            }
          },
          "module": {
            "mqtt": {
              "enabled": true,
              "username": "meshdev",
              "password": "<redacted>",
              "map_report_settings": {
                "proxy_password": "<redacted>",
                "position_precision": 0
              }
            }
          }
        }
        """
    )

    assert request.local == {
        "network": {
            "wifi_enabled": True,
            "wifi_ssid": "The LAN Before Time",
            "ntp_server": "meshtastic.pool.ntp.org",
        }
    }
    assert request.module == {
        "mqtt": {
            "enabled": True,
            "username": "meshdev",
            "map_report_settings": {
                "position_precision": 0,
            },
        }
    }


def test_parse_radio_settings_request_keeps_redacted_literal_for_non_secret_fields():
    request = parse_radio_settings_request(
        b'{"local":{"device":{"tzdef":"<redacted>"}}}'
    )
    assert request.local == {"device": {"tzdef": "<redacted>"}}


def test_parse_radio_settings_request_rejects_invalid_json():
    with pytest.raises(ValueError, match="Invalid JSON"):
        parse_radio_settings_request(b"{not-json}")


def test_parse_radio_settings_request_rejects_non_object_payload():
    with pytest.raises(ValueError, match="Expected a JSON object"):
        parse_radio_settings_request(b'["not", "an", "object"]')


def test_parse_radio_settings_request_rejects_non_object_lora():
    with pytest.raises(ValueError, match="Expected 'lora' to be an object"):
        parse_radio_settings_request(b'{"lora": ["not", "an", "object"]}')


def test_parse_radio_settings_request_rejects_non_object_local_module_and_actions():
    with pytest.raises(ValueError, match="Expected 'local' to be an object"):
        parse_radio_settings_request(b'{"local": ["not", "an", "object"]}')

    with pytest.raises(ValueError, match="Expected 'module' to be an object"):
        parse_radio_settings_request(b'{"module": ["not", "an", "object"]}')

    with pytest.raises(ValueError, match="Expected 'actions' to be an object"):
        parse_radio_settings_request(b'{"actions": ["not", "an", "object"]}')


def test_parse_radio_settings_request_rejects_non_object_owner():
    with pytest.raises(ValueError, match="Expected 'owner' to be an object"):
        parse_radio_settings_request(b'{"owner": ["not", "an", "object"]}')


def test_parse_radio_settings_request_rejects_non_object_fixed_position():
    with pytest.raises(ValueError, match="Expected 'fixed_position' to be an object"):
        parse_radio_settings_request(b'{"fixed_position": ["not", "an", "object"]}')

    with pytest.raises(ValueError, match="Expected 'time_sync' to be an object"):
        parse_radio_settings_request(b'{"time_sync": ["not", "an", "object"]}')


def test_radio_input_helper_branches_for_private_cleaners():
    class _Unsupported:
        pass

    assert radio_input._coerce_bool(True) is True
    assert radio_input._coerce_bool(False) is False
    assert radio_input._coerce_bool("off") is False

    clean_nested = radio_input._clean_update_value(
        {
            "ok": 1,
            1: "skip",
            "keep_none": None,
            "drop": _Unsupported(),
        }
    )
    assert clean_nested == {"ok": 1, "keep_none": None}
    assert radio_input._clean_update_value(_Unsupported()) is None

    clean_obj = radio_input._clean_update_object(
        {
            "good": 2,
            99: "skip",
            "none_field": None,
            "drop": _Unsupported(),
        },
        field_name="lora",
    )
    assert clean_obj == {"good": 2, "none_field": None}

    clean_sections = radio_input._clean_section_map(
        {
            "device": {"role": "ROUTER"},
            7: {"bad": True},
            "bad_shape": "skip",
        },
        field_name="local",
    )
    assert clean_sections == {"device": {"role": "ROUTER"}}

    clean_actions = radio_input._clean_actions({"set_time": "yes", 7: True})
    assert clean_actions == {"set_time": True}

    clean_owner = radio_input._clean_owner(
        {
            "shortName": "ABCD",
            "long": "Alpha Bravo",
            "isLicensed": "1",
            "is_unmessagable": "off",
            "drop": _Unsupported(),
        }
    )
    assert clean_owner == {
        "short_name": "ABCD",
        "long_name": "Alpha Bravo",
        "is_licensed": True,
        "is_unmessagable": False,
    }

    clean_fixed_position = radio_input._clean_fixed_position(
        {
            "lat": 44.98,
            8: "skip",
            "longitude": _Unsupported(),
        }
    )
    assert clean_fixed_position == {"lat": 44.98}

    clean_time_sync = radio_input._clean_time_sync(
        {
            "enabled": "yes",
            "server": "pool.ntp.org",
            "timezone": "UTC",
            "timeout": 2500,
            "drop": _Unsupported(),
        }
    )
    assert clean_time_sync == {
        "enabled": True,
        "server": "pool.ntp.org",
        "timezone": "UTC",
        "timeout_ms": 2500,
    }
