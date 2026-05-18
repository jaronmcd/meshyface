import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.api_input_network_tools import parse_network_tool_request
from meshdash.helpers import to_int


def test_parse_network_tool_request_normalizes_position_command() -> None:
    raw = (
        b'{"command":"--request-position","destination":"!abcd1234",'
        b'"channel_index":"1","timeout_ms":"8000"}'
    )

    request = parse_network_tool_request(raw, to_int_fn=to_int)

    assert request.command == "request_position"
    assert request.destination == "!abcd1234"
    assert request.channel_index == 1
    assert request.timeout_ms == 8000
    assert request.hop_limit is None


def test_parse_network_tool_request_normalizes_traceroute_command() -> None:
    raw = (
        b'{"command":"--traceroute","destination":"!abcd1234",'
        b'"channel_index":"1","hop_limit":"5","timeout":"12000"}'
    )

    request = parse_network_tool_request(raw, to_int_fn=to_int)

    assert request.command == "traceroute"
    assert request.destination == "!abcd1234"
    assert request.channel_index == 1
    assert request.hop_limit == 5
    assert request.timeout_ms == 12000


def test_parse_network_tool_request_normalizes_ping_command() -> None:
    raw = (
        b'{"command":"--ping","destination":"!abcd1234",'
        b'"channel_index":"1","hop_limit":"4","timeout":"8000"}'
    )

    request = parse_network_tool_request(raw, to_int_fn=to_int)

    assert request.command == "ping"
    assert request.destination == "!abcd1234"
    assert request.channel_index == 1
    assert request.hop_limit == 4
    assert request.timeout_ms == 8000


def test_parse_network_tool_request_normalizes_telemetry_type_alias() -> None:
    raw = b'{"command":"request-telemetry","destination":"!abcd1234","type":"power"}'

    request = parse_network_tool_request(raw, to_int_fn=to_int)

    assert request.command == "request_telemetry"
    assert request.telemetry_type == "power_metrics"


def test_parse_network_tool_request_normalizes_telemetry_command_alias() -> None:
    raw = b'{"command":"--request-telemetry","destination":"!abcd1234"}'

    request = parse_network_tool_request(raw, to_int_fn=to_int)

    assert request.command == "request_telemetry"
    assert request.destination == "!abcd1234"


def test_parse_network_tool_request_allows_nodes_without_destination() -> None:
    request = parse_network_tool_request(b'{"command":"--nodes"}', to_int_fn=to_int)

    assert request.command == "nodes"
    assert request.destination is None


def test_parse_network_tool_request_allows_send_node_info_without_destination() -> None:
    request = parse_network_tool_request(
        b'{"command":"--send-node-info","channel_index":"2","hop_limit":"3"}',
        to_int_fn=to_int,
    )

    assert request.command == "send_node_info"
    assert request.destination is None
    assert request.channel_index == 2
    assert request.hop_limit == 3


def test_parse_network_tool_request_rejects_missing_destination_for_radio_commands() -> None:
    with pytest.raises(ValueError, match="Missing destination"):
        parse_network_tool_request(b'{"command":"traceroute"}', to_int_fn=to_int)


def test_parse_network_tool_request_normalizes_alert_and_text_aliases() -> None:
    raw = (
        b'{"command":"send-alert","destination":"!abcd1234","message":"Heads up",'
        b'"ch_index":"2","hop_limit":"3"}'
    )

    request = parse_network_tool_request(raw, to_int_fn=to_int)

    assert request.command == "send_alert"
    assert request.destination == "!abcd1234"
    assert request.text == "Heads up"
    assert request.channel_index == 2
    assert request.hop_limit == 3


def test_parse_network_tool_request_parses_admin_fields() -> None:
    raw = (
        b'{"command":"set-time","destination":"!abcd1234","time":"1715985600",'
        b'"delay":"5"}'
    )

    request = parse_network_tool_request(raw, to_int_fn=to_int)

    assert request.command == "set_time"
    assert request.destination == "!abcd1234"
    assert request.time_sec == 1715985600
    assert request.delay_seconds == 5


def test_parse_network_tool_request_parses_request_config_fields() -> None:
    raw = b'{"command":"request-config","destination":"!abcd1234","config":"lora"}'

    request = parse_network_tool_request(raw, to_int_fn=to_int)

    assert request.command == "request_config"
    assert request.destination == "!abcd1234"
    assert request.config_type == "lora"


def test_parse_network_tool_request_parses_request_channels_fields() -> None:
    raw = b'{"command":"request-channels","destination":"!abcd1234","start_index":"2"}'

    request = parse_network_tool_request(raw, to_int_fn=to_int)

    assert request.command == "request_channels"
    assert request.destination == "!abcd1234"
    assert request.starting_index == 2


def test_parse_network_tool_request_normalizes_official_sendtext_command() -> None:
    raw = b'{"command":"--sendtext","destination":"!abcd1234","text":"hello"}'

    request = parse_network_tool_request(raw, to_int_fn=to_int)

    assert request.command == "send_text"
    assert request.destination == "!abcd1234"
    assert request.text == "hello"


def test_parse_network_tool_request_normalizes_device_metadata_command() -> None:
    raw = b'{"command":"device-metadata","destination":"!abcd1234"}'

    request = parse_network_tool_request(raw, to_int_fn=to_int)

    assert request.command == "device_metadata"
    assert request.destination == "!abcd1234"


def test_parse_network_tool_request_parses_confirm_bool() -> None:
    raw = b'{"command":"factory-reset","destination":"!abcd1234","confirm":"true"}'

    request = parse_network_tool_request(raw, to_int_fn=to_int)

    assert request.command == "factory_reset"
    assert request.confirm is True
