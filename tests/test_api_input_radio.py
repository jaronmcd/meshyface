import json

import pytest

from meshdash.api_input_radio import parse_radio_settings_request


def _parse(payload: object):
    return parse_radio_settings_request(json.dumps(payload).encode("utf-8"))


def test_parse_radio_settings_request_cleans_supported_update_sections() -> None:
    request = _parse(
        {
            "lora": {
                "region": "US",
                "hop_limit": 3,
                "psk": "<redacted>",
                "clear_me": None,
                "bad": [{"nested": "object"}],
            },
            "local": {
                "device": {
                    "role": "CLIENT",
                    "wifi_psk": "<redacted>",
                    "nested": {"ok": True, "password": "<redacted>", "keep_none": None},
                },
                "ignored": "not an object",
                7: {"ignored": True},
            },
            "module": {
                "mqtt": {
                    "enabled": "yes",
                    "address": "broker.local",
                    "list": ["a", 1, True, None],
                    "bad_list": [{"x": 1}],
                },
            },
        }
    )

    assert request.lora == {
        "region": "US",
        "hop_limit": 3,
        "clear_me": None,
    }
    assert request.local == {
        "7": {"ignored": True},
        "device": {
            "role": "CLIENT",
            "nested": {"ok": True, "keep_none": None},
        }
    }
    assert request.module == {
        "mqtt": {
            "enabled": "yes",
            "address": "broker.local",
            "list": ["a", 1, True, None],
        }
    }


def test_parse_radio_settings_request_normalizes_owner_position_time_and_actions() -> None:
    request = _parse(
        {
            "owner": {
                "short": 1234,
                "longname": "Long Node",
                "isLicensed": "yes",
                "isUnmessagable": "off",
            },
            "fixed_position": {
                "latitude": 44.9,
                "lng": -93.2,
                "altitude": 255,
                "ignored": {"bad": True},
            },
            "time_sync": {
                "use_server": "true",
                "host": "pool.ntp.org",
                "tz": "America/Chicago",
                "request_timeout_ms": 2500,
            },
            "actions": {
                "reset_nodedb": "yes",
                "clear_fixed_position": "0",
                "unknown": True,
            },
            "set_time": "on",
            "regenerate_node_id": "false",
        }
    )

    assert request.owner == {
        "short_name": "1234",
        "long_name": "Long Node",
        "is_licensed": True,
        "is_unmessagable": False,
    }
    assert request.fixed_position == {
        "lat": 44.9,
        "lon": -93.2,
        "alt": 255,
    }
    assert request.time_sync == {
        "enabled": True,
        "server": "pool.ntp.org",
        "timezone": "America/Chicago",
        "timeout_ms": 2500,
    }
    assert request.actions == {
        "reset_nodedb": True,
        "clear_fixed_position": False,
        "set_time": True,
        "regenerate_node_id": False,
    }


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"{not-json", "Invalid JSON"),
        (json.dumps(["not", "object"]).encode("utf-8"), "Expected a JSON object"),
        (json.dumps({"lora": []}).encode("utf-8"), "Expected 'lora' to be an object"),
        (json.dumps({"local": []}).encode("utf-8"), "Expected 'local' to be an object"),
        (json.dumps({"owner": []}).encode("utf-8"), "Expected 'owner' to be an object"),
        (
            json.dumps({"fixed_position": []}).encode("utf-8"),
            "Expected 'fixed_position' to be an object",
        ),
        (json.dumps({"time_sync": []}).encode("utf-8"), "Expected 'time_sync' to be an object"),
        (json.dumps({"actions": []}).encode("utf-8"), "Expected 'actions' to be an object"),
    ],
)
def test_parse_radio_settings_request_rejects_invalid_payload_shapes(payload: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_radio_settings_request(payload)
