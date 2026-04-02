import io

from meshdash.api_channels import handle_channel_settings_post
from meshdash.api_input_channels import ChannelSettingsRequest


def _fake_handler(payload: bytes = b"{}"):
    class _H:
        headers = {"Content-Length": str(len(payload))}
        rfile = io.BytesIO(payload)

    return _H()


def _to_int(value):
    if value in (None, ""):
        return None
    return int(value)


def test_handle_channel_settings_post_disabled_returns_503():
    calls = []
    handle_channel_settings_post(
        _fake_handler(),
        apply_channel_settings_fn=None,
        to_int_fn=_to_int,
        validate_content_length_fn=lambda *_args, **_kwargs: 2,
        parse_channel_settings_request_fn=None,
        write_json_response_fn=lambda *_args, **kwargs: calls.append(kwargs),
    )
    assert calls[0]["status_code"] == 503
    assert calls[0]["payload_obj"]["ok"] is False


def test_handle_channel_settings_post_handles_invalid_size_and_parse_errors():
    calls = []

    def _raise_size(*_args, **_kwargs):
        raise ValueError("bad")

    handle_channel_settings_post(
        _fake_handler(),
        apply_channel_settings_fn=lambda _request: {"ok": True},
        to_int_fn=_to_int,
        validate_content_length_fn=_raise_size,
        parse_channel_settings_request_fn=lambda _raw: ChannelSettingsRequest(),
        write_json_response_fn=lambda *_args, **kwargs: calls.append(kwargs),
    )
    assert calls[0]["status_code"] == 400
    assert calls[0]["payload_obj"]["error"] == "Invalid request size"

    calls.clear()
    handle_channel_settings_post(
        _fake_handler(b'{"action":"upsert"}'),
        apply_channel_settings_fn=lambda _request: {"ok": True},
        to_int_fn=_to_int,
        validate_content_length_fn=lambda *_args, **_kwargs: len(b'{"action":"upsert"}'),
        parse_channel_settings_request_fn=lambda _raw: (_ for _ in ()).throw(ValueError("invalid payload")),
        write_json_response_fn=lambda *_args, **kwargs: calls.append(kwargs),
    )
    assert calls[0]["status_code"] == 400
    assert calls[0]["payload_obj"]["error"] == "invalid payload"


def test_handle_channel_settings_post_handles_apply_errors_and_success():
    calls = []

    def _raise_apply(_request):
        raise RuntimeError("boom")

    handle_channel_settings_post(
        _fake_handler(b'{"action":"upsert"}'),
        apply_channel_settings_fn=_raise_apply,
        to_int_fn=_to_int,
        validate_content_length_fn=lambda *_args, **_kwargs: len(b'{"action":"upsert"}'),
        parse_channel_settings_request_fn=lambda _raw: ChannelSettingsRequest(action="upsert"),
        write_json_response_fn=lambda *_args, **kwargs: calls.append(kwargs),
    )
    assert calls[0]["status_code"] == 500
    assert "Channel settings update failed: boom" in calls[0]["payload_obj"]["error"]

    calls.clear()
    handle_channel_settings_post(
        _fake_handler(b'{"action":"upsert"}'),
        apply_channel_settings_fn=lambda _request: {"ok": False, "error": "No valid fields"},
        to_int_fn=_to_int,
        validate_content_length_fn=lambda *_args, **_kwargs: len(b'{"action":"upsert"}'),
        parse_channel_settings_request_fn=lambda _raw: ChannelSettingsRequest(action="upsert"),
        write_json_response_fn=lambda *_args, **kwargs: calls.append(kwargs),
    )
    assert calls[0]["status_code"] == 400
    assert calls[0]["no_store"] is True

    calls.clear()
    handle_channel_settings_post(
        _fake_handler(b'{"action":"export_url"}'),
        apply_channel_settings_fn=lambda _request: {"ok": True, "action": "export_url"},
        to_int_fn=_to_int,
        validate_content_length_fn=lambda *_args, **_kwargs: len(b'{"action":"export_url"}'),
        parse_channel_settings_request_fn=lambda _raw: ChannelSettingsRequest(action="export_url"),
        write_json_response_fn=lambda *_args, **kwargs: calls.append(kwargs),
    )
    assert calls[0]["status_code"] == 200
    assert calls[0]["payload_obj"]["ok"] is True
    assert calls[0]["no_store"] is True

