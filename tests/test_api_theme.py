import io

from meshdash.api_input_theme import ThemeSettingsRequest
from meshdash.api_theme import handle_theme_settings_get, handle_theme_settings_post


def _fake_handler(payload: bytes = b"{}"):
    class _H:
        headers = {"Content-Length": str(len(payload))}
        rfile = io.BytesIO(payload)

    return _H()


def test_handle_theme_settings_get_disabled_returns_503():
    calls = []
    handle_theme_settings_get(
        _fake_handler(),
        get_theme_settings_fn=None,
        write_json_response_fn=lambda *_args, **kwargs: calls.append(kwargs),
    )
    assert calls[0]["status_code"] == 503
    assert calls[0]["payload_obj"]["ok"] is False


def test_handle_theme_settings_get_returns_payload():
    calls = []
    handle_theme_settings_get(
        _fake_handler(),
        get_theme_settings_fn=lambda: {"ok": True, "selected_preset": "default"},
        write_json_response_fn=lambda *_args, **kwargs: calls.append(kwargs),
    )
    assert calls[0]["status_code"] == 200
    assert calls[0]["no_store"] is True
    assert calls[0]["payload_obj"]["selected_preset"] == "default"


def test_handle_theme_settings_get_handles_service_exception():
    calls = []
    handle_theme_settings_get(
        _fake_handler(),
        get_theme_settings_fn=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        write_json_response_fn=lambda *_args, **kwargs: calls.append(kwargs),
    )
    assert calls[0]["status_code"] == 500
    assert "Theme settings failed: boom" in calls[0]["payload_obj"]["error"]


def test_handle_theme_settings_post_handles_invalid_size():
    calls = []
    def _raise_size(*_args, **_kwargs):
        raise ValueError("bad")

    handle_theme_settings_post(
        _fake_handler(),
        set_theme_preset_fn=lambda preset_name: {"ok": True, "selected_preset": str(preset_name)},
        to_int_fn=lambda value: int(value) if value else None,
        validate_content_length_fn=_raise_size,
        parse_theme_settings_request_fn=lambda _raw: ThemeSettingsRequest(preset_name="default"),
        write_json_response_fn=lambda *_args, **kwargs: calls.append(kwargs),
    )
    assert calls[0]["status_code"] == 400
    assert calls[0]["payload_obj"]["ok"] is False


def test_handle_theme_settings_post_disabled_returns_503():
    calls = []
    handle_theme_settings_post(
        _fake_handler(),
        set_theme_preset_fn=None,
        to_int_fn=lambda value: int(value) if value else None,
        validate_content_length_fn=lambda *_args, **_kwargs: 2,
        parse_theme_settings_request_fn=lambda _raw: ThemeSettingsRequest(preset_name="default"),
        write_json_response_fn=lambda *_args, **kwargs: calls.append(kwargs),
    )
    assert calls[0]["status_code"] == 503
    assert calls[0]["payload_obj"]["ok"] is False


def test_handle_theme_settings_post_rejects_unknown_preset():
    calls = []
    handler = _fake_handler(b'{"preset_name":"missing"}')
    handle_theme_settings_post(
        handler,
        set_theme_preset_fn=lambda _preset_name: {"ok": False, "error": "Unknown theme preset"},
        to_int_fn=lambda value: int(value) if value else None,
        validate_content_length_fn=lambda *_args, **_kwargs: len(b'{"preset_name":"missing"}'),
        parse_theme_settings_request_fn=lambda _raw: ThemeSettingsRequest(preset_name="missing"),
        write_json_response_fn=lambda *_args, **kwargs: calls.append(kwargs),
    )
    assert calls[0]["status_code"] == 400
    assert calls[0]["payload_obj"]["ok"] is False


def test_handle_theme_settings_post_updates_preset():
    calls = []
    handler = _fake_handler(b'{"preset_name":"forest"}')
    handle_theme_settings_post(
        handler,
        set_theme_preset_fn=lambda preset_name: {"ok": True, "selected_preset": str(preset_name)},
        to_int_fn=lambda value: int(value) if value else None,
        validate_content_length_fn=lambda *_args, **_kwargs: len(b'{"preset_name":"forest"}'),
        parse_theme_settings_request_fn=lambda _raw: ThemeSettingsRequest(preset_name="forest"),
        write_json_response_fn=lambda *_args, **kwargs: calls.append(kwargs),
    )
    assert calls[0]["status_code"] == 200
    assert calls[0]["no_store"] is True
    assert calls[0]["payload_obj"]["selected_preset"] == "forest"


def test_handle_theme_settings_post_handles_setter_exception():
    calls = []
    handler = _fake_handler(b'{"preset_name":"forest"}')
    handle_theme_settings_post(
        handler,
        set_theme_preset_fn=lambda _preset_name: (_ for _ in ()).throw(RuntimeError("save failed")),
        to_int_fn=lambda value: int(value) if value else None,
        validate_content_length_fn=lambda *_args, **_kwargs: len(b'{"preset_name":"forest"}'),
        parse_theme_settings_request_fn=lambda _raw: ThemeSettingsRequest(preset_name="forest"),
        write_json_response_fn=lambda *_args, **kwargs: calls.append(kwargs),
    )
    assert calls[0]["status_code"] == 500
    assert "Theme preset update failed: save failed" in calls[0]["payload_obj"]["error"]
