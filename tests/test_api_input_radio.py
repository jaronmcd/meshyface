import pytest

from meshdash.api_input_radio import parse_radio_settings_request


def test_parse_radio_settings_request_defaults_to_empty_objects():
    request = parse_radio_settings_request(b"{}")
    assert request.lora == {}
    assert request.local == {}
    assert request.module == {}
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
          "actions": {
            "reset_nodedb": "yes",
            "reset_dashboard_db": 1,
            "set_time": "on",
            "unknown": true
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
    assert request.actions == {"reset_nodedb": True, "reset_dashboard_db": True, "set_time": True}


def test_parse_radio_settings_request_supports_top_level_reset_alias():
    request = parse_radio_settings_request(b'{"reset_nodedb": "1", "reset_dashboard_db": "true", "set_time": "yes"}')
    assert request.actions == {"reset_nodedb": True, "reset_dashboard_db": True, "set_time": True}


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
