import json

import pytest

from meshdash.api_input_channels import parse_channel_settings_request


def _parse(payload: object):
    return parse_channel_settings_request(json.dumps(payload).encode("utf-8"))


def test_parse_channel_settings_request_supports_nested_and_flat_upsert_payloads() -> None:
    request = _parse(
        {
            "action": "upsert",
            "channel_index": "2",
            "role": "secondary",
            "include_all": "off",
            "settings": {
                "name": "mesh",
                "psk": None,
                "uplink_enabled": "yes",
                "downlink_enabled": "0",
                "module_settings": {
                    "is_muted": True,
                    "position_precision": 24,
                },
                "ignored": "value",
            },
            "psk": "default",
            "allow_experimental": "1",
        }
    )

    assert request.action == "upsert"
    assert request.channel_index == 2
    assert request.role == "SECONDARY"
    assert request.include_all is False
    assert request.settings == {
        "name": "mesh",
        "uplink_enabled": True,
        "downlink_enabled": False,
        "module_settings": {
            "is_muted": True,
            "position_precision": 24,
        },
        "psk": "default",
    }
    assert request.allow_experimental is True


@pytest.mark.parametrize(
    ("payload", "expected_action"),
    [
        ({"op": "seturl", "url": "https://meshtastic.org/e/#abc"}, "import_url"),
        ({"action": "set_url", "channel_url": "https://meshtastic.org/e/#abc"}, "import_url"),
        ({"action": "importurl", "setURL": "https://meshtastic.org/e/#abc"}, "import_url"),
        ({"action": "import_url", "setUrl": "https://meshtastic.org/e/#abc"}, "import_url"),
    ],
)
def test_parse_channel_settings_request_normalizes_import_url_aliases(
    payload: dict[str, object],
    expected_action: str,
) -> None:
    request = _parse({**payload, "addOnly": "yes", "experimental": True})

    assert request.action == expected_action
    assert request.url == "https://meshtastic.org/e/#abc"
    assert request.add_only is True
    assert request.allow_experimental is True


def test_parse_channel_settings_request_accepts_disable_and_export_url() -> None:
    disable = _parse({"action": "disable", "channel_index": 1})
    export = _parse({"action": "export_url", "include_all": False})

    assert disable.action == "disable"
    assert disable.channel_index == 1
    assert export.action == "export_url"
    assert export.include_all is False


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"{not-json", "Invalid JSON"),
        (json.dumps(["not", "object"]).encode("utf-8"), "Expected a JSON object"),
        (json.dumps({"action": "bogus"}).encode("utf-8"), "Unsupported action"),
        (json.dumps({"channel_index": "not-int"}).encode("utf-8"), "Invalid channel_index"),
        (json.dumps({"settings": []}).encode("utf-8"), "Expected 'settings' to be an object"),
        (json.dumps({"action": "import_url"}).encode("utf-8"), "Missing url"),
    ],
)
def test_parse_channel_settings_request_rejects_invalid_payloads(payload: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_channel_settings_request(payload)
