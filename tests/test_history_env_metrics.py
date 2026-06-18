import json

from meshdash.history_env_metrics import (
    collect_environment_metric_containers,
    format_env_metric_label,
    metric_float,
    normalize_custom_telemetry_rules,
    normalize_env_metric_key,
)


def test_environment_metric_key_label_and_number_normalization() -> None:
    assert normalize_env_metric_key("Relative Humidity") == "relative_humidity"
    assert normalize_env_metric_key("barometric-pressure") == "barometric_pressure"
    assert normalize_env_metric_key("Air Util TX") == "air_util_tx"
    assert normalize_env_metric_key("  ") == ""

    assert format_env_metric_label("relative_humidity") == "Relative Humidity"
    assert format_env_metric_label("air-util-tx") == "Air Util Tx"
    assert format_env_metric_label("") == "Metric"

    assert metric_float("1,234.5") == 1234.5
    assert metric_float(12) == 12.0
    assert metric_float(True) is None
    assert metric_float(float("nan")) is None
    assert metric_float("not-a-number") is None


def test_normalize_custom_telemetry_rules_filters_dedupes_and_coerces_values() -> None:
    rules = normalize_custom_telemetry_rules(
        {
            "rules": [
                {
                    "name": "Sensor One",
                    "source": "decoded",
                    "path": "payload.value",
                    "port": "private_app",
                    "enabled": "yes",
                    "scale": "2.5",
                    "offset": "1",
                },
                {
                    "metric": "Sensor One",
                    "source": "decoded",
                    "path": "payload.value",
                    "portnum": "PRIVATE_APP",
                },
                {
                    "key": "Sensor Two",
                    "source": "bogus",
                    "json_path": "sensor.reading",
                    "enabled": "off",
                    "scale": "bad",
                    "offset": None,
                },
                {"name": ""},
                "bad",
            ]
        },
        max_rules=10,
    )

    assert rules == [
        {
            "enabled": True,
            "metric_key": "sensor_one",
            "source": "decoded",
            "path": "payload.value",
            "portnum": "PRIVATE_APP",
            "scale": 2.5,
            "offset": 1.0,
        },
        {
            "enabled": False,
            "metric_key": "sensor_two",
            "source": "payload_json",
            "path": "sensor.reading",
            "portnum": "",
            "scale": 1.0,
            "offset": 0.0,
        },
    ]
    assert normalize_custom_telemetry_rules("not-rules") == []


def test_collect_environment_metric_containers_finds_nested_and_custom_metrics() -> None:
    decoded = {
        "portnum": "PRIVATE_APP",
        "nested": [
            {
                "environmentMetrics": {
                    "temperature": 22.5,
                }
            },
            {
                "deviceMetrics": {
                    "batteryLevel": 87,
                }
            },
        ],
        "payload": json.dumps(
            {
                "sensor": {
                    "reading": "12.5",
                    "other": "not-number",
                }
            }
        ),
    }

    containers = collect_environment_metric_containers(
        decoded,
        summary={"portnum": "PRIVATE_APP"},
        custom_rules=[
            {
                "name": "Payload Sensor",
                "path": "sensor.reading",
                "scale": 2,
                "offset": -1,
                "portnum": "PRIVATE_APP",
            },
            {
                "name": "Wrong Port",
                "path": "sensor.reading",
                "portnum": "TEXT_MESSAGE_APP",
            },
            {
                "name": "Decoded Sensor",
                "source": "decoded",
                "path": "nested.0.environmentMetrics.temperature",
            },
        ],
    )

    assert {"temperature": 22.5} in containers
    assert {"batteryLevel": 87} in containers
    assert {"payload_sensor": 24.0, "decoded_sensor": 22.5} in containers


def test_collect_environment_metric_containers_parses_hex_payload_and_handles_missing_paths() -> None:
    payload_hex = json.dumps({"sensor": [{"reading": 7}]}).encode("utf-8").hex()

    containers = collect_environment_metric_containers(
        {"payload": payload_hex},
        packet={"summary": {"portnum": "PRIVATE_APP"}},
        custom_rules=[
            {"name": "Hex Sensor", "path": "sensor.0.reading"},
            {"name": "Out Of Range", "path": "sensor.9.reading"},
            {"name": "Bad List Path", "path": "sensor.nope"},
        ],
    )

    assert containers == [{"hex_sensor": 7.0}]
    assert collect_environment_metric_containers("not-a-map", custom_rules=[{"name": "x"}]) == []
