import meshdash.fault_recorder as fault_recorder
from meshdash.fault_recorder import FaultRecorder, _safe_strftime
from meshdash.helpers_security import is_sensitive_key, redact_secrets


def test_fault_recorder_defaults_sorts_filters_and_trims_rows() -> None:
    clock = iter([100, 101, 102, 103])
    recorder = FaultRecorder(max_rows=2, now_unix_fn=lambda: next(clock))

    first = recorder.record_fault({})
    second = recorder.record_fault({"source": "radio", "created_unix": 105, "message": "kept"})
    third = recorder.record_fault({"source": "ui", "severity": "warn", "code": "bad", "message": "last"})

    assert first["source"] == "system"
    assert first["severity"] == "error"
    assert first["code"] == "UNKNOWN"
    assert first["id"] == "fault-100-1"
    assert "_seq" not in first
    assert recorder.record_fault("not a dict")["source"] == "system"  # type: ignore[arg-type]

    rows = recorder.recent_faults(limit=2)
    assert [row["message"] for row in rows] == ["", "last"]
    assert rows[0]["source"] == "system"
    assert rows[1]["source"] == "ui"
    assert "_seq" not in rows[0]

    radio_rows = recorder.recent_faults(source="radio")
    assert radio_rows == []
    assert second["created_unix"] == 105
    assert third["severity"] == "warn"


def test_fault_recorder_handles_bad_dates_and_limits() -> None:
    recorder = FaultRecorder(max_rows=5, now_unix_fn=lambda: 200)
    recorder.record_fault({"message": "one"})
    recorder.record_fault({"message": "two"})

    assert _safe_strftime(None) == "n/a"
    assert _safe_strftime(0) == "n/a"
    assert len(recorder.recent_faults(limit=0)) == 1
    assert len(recorder.recent_faults(limit=5000)) == 2


def test_safe_strftime_returns_na_when_localtime_fails(monkeypatch) -> None:
    def _raise_localtime(_value: object) -> object:
        raise OverflowError("bad time")

    monkeypatch.setattr(fault_recorder.time, "localtime", _raise_localtime)

    assert _safe_strftime(123) == "n/a"


def test_redact_secrets_walks_nested_dicts_and_lists() -> None:
    payload = {
        "name": "node",
        "api_token": "secret-token",
        "nested": {
            "wifi_password": "secret-password",
            "identity_private_key": "secret-key",
            "public": "value",
        },
        "items": [
            {"api_token": "list-secret", "public": "visible"},
            "plain",
        ],
    }

    redacted = redact_secrets(payload, {"api_token"})

    assert is_sensitive_key("api_token", {"api_token"}) is True
    assert is_sensitive_key("wifi_password", {"api_token"}) is True
    assert is_sensitive_key("identity_private_key", {"api_token"}) is True
    assert is_sensitive_key("name", {"api_token"}) is False
    assert redacted == {
        "name": "node",
        "api_token": "<redacted>",
        "nested": {
            "wifi_password": "<redacted>",
            "identity_private_key": "<redacted>",
            "public": "value",
        },
        "items": [
            {"api_token": "<redacted>", "public": "visible"},
            "plain",
        ],
    }
    assert redact_secrets(["secret"], {"api_token"}, parent_key="api_token") == "<redacted>"
