import io

from meshdash.api_bot import handle_bot_settings_post
from meshdash.api_input_bot import BotSettingsRequest


def _handler(body=b"{}"):
    class _H:
        def __init__(self):
            self.rfile = io.BytesIO(body)
            self.headers = {"Content-Length": str(len(body))}

    return _H()


def test_handle_bot_settings_post_returns_503_when_disabled():
    calls = {}
    handle_bot_settings_post(
        _handler(),
        apply_bot_settings_fn=None,
        to_int_fn=lambda value: int(value) if value not in (None, "") else None,
        validate_content_length_fn=lambda *_args, **_kwargs: 2,
        parse_bot_settings_request_fn=None,
        write_json_response_fn=lambda _handler, **kwargs: calls.update(kwargs),
    )
    assert calls["status_code"] == 503
    assert "Bot settings are not enabled" in calls["payload_obj"]["error"]


def test_handle_bot_settings_post_returns_400_on_empty_patch():
    calls = {}
    handle_bot_settings_post(
        _handler(),
        apply_bot_settings_fn=lambda _req: {"ok": True},
        to_int_fn=lambda value: int(value) if value not in (None, "") else None,
        validate_content_length_fn=lambda *_args, **_kwargs: 2,
        parse_bot_settings_request_fn=lambda _raw: BotSettingsRequest(),
        write_json_response_fn=lambda _handler, **kwargs: calls.update(kwargs),
    )
    assert calls["status_code"] == 400
    assert "No bot settings provided" in calls["payload_obj"]["error"]


def test_handle_bot_settings_post_returns_200_on_success():
    calls = {}
    captured = {}
    handle_bot_settings_post(
        _handler(body=b'{"game_enabled":true}'),
        apply_bot_settings_fn=lambda req: (
            captured.update({"request": req}) or {"ok": True, "game_enabled": True}
        ),
        to_int_fn=lambda value: int(value) if value not in (None, "") else None,
        validate_content_length_fn=lambda *_args, **_kwargs: len(b'{"game_enabled":true}'),
        parse_bot_settings_request_fn=lambda _raw: BotSettingsRequest(game_enabled=True),
        write_json_response_fn=lambda _handler, **kwargs: calls.update(kwargs),
    )
    assert calls["status_code"] == 200
    assert calls["no_store"] is True
    assert calls["payload_obj"]["game_enabled"] is True
    assert isinstance(captured["request"], BotSettingsRequest)


def test_handle_bot_settings_post_accepts_public_game_start_patch():
    calls = {}
    captured = {}
    body = b'{"game_public_start_enabled":true}'
    handle_bot_settings_post(
        _handler(body=body),
        apply_bot_settings_fn=lambda req: (
            captured.update({"request": req}) or {"ok": True, "game_public_start_enabled": True}
        ),
        to_int_fn=lambda value: int(value) if value not in (None, "") else None,
        validate_content_length_fn=lambda *_args, **_kwargs: len(body),
        parse_bot_settings_request_fn=lambda _raw: BotSettingsRequest(game_public_start_enabled=True),
        write_json_response_fn=lambda _handler, **kwargs: calls.update(kwargs),
    )
    assert calls["status_code"] == 200
    assert calls["payload_obj"]["game_public_start_enabled"] is True
    assert captured["request"].game_public_start_enabled is True


def test_handle_bot_settings_post_accepts_command_settings_patch():
    calls = {}
    captured = {}
    body = b'{"command_settings":{"ping":false}}'
    handle_bot_settings_post(
        _handler(body=body),
        apply_bot_settings_fn=lambda req: (
            captured.update({"request": req}) or {"ok": True, "commands": [{"name": "ping", "enabled": False}]}
        ),
        to_int_fn=lambda value: int(value) if value not in (None, "") else None,
        validate_content_length_fn=lambda *_args, **_kwargs: len(body),
        parse_bot_settings_request_fn=lambda _raw: BotSettingsRequest(command_settings={"ping": False}),
        write_json_response_fn=lambda _handler, **kwargs: calls.update(kwargs),
    )
    assert calls["status_code"] == 200
    assert calls["payload_obj"]["commands"][0]["name"] == "ping"
    assert calls["payload_obj"]["commands"][0]["enabled"] is False
    assert captured["request"].command_settings == {"ping": False}


def test_handle_bot_settings_post_accepts_joke_settings_patch():
    calls = {}
    captured = {}
    body = b'{"joke_triggers":["tell me a joke"],"joke_lines":["line one","line two"]}'
    handle_bot_settings_post(
        _handler(body=body),
        apply_bot_settings_fn=lambda req: (
            captured.update({"request": req})
            or {
                "ok": True,
                "joke_triggers": ["tell me a joke"],
                "joke_lines": ["line one", "line two"],
            }
        ),
        to_int_fn=lambda value: int(value) if value not in (None, "") else None,
        validate_content_length_fn=lambda *_args, **_kwargs: len(body),
        parse_bot_settings_request_fn=lambda _raw: BotSettingsRequest(
            joke_triggers=["tell me a joke"],
            joke_lines=["line one", "line two"],
        ),
        write_json_response_fn=lambda _handler, **kwargs: calls.update(kwargs),
    )
    assert calls["status_code"] == 200
    assert calls["payload_obj"]["joke_triggers"] == ["tell me a joke"]
    assert calls["payload_obj"]["joke_lines"] == ["line one", "line two"]
    assert captured["request"].joke_triggers == ["tell me a joke"]
    assert captured["request"].joke_lines == ["line one", "line two"]


def test_handle_bot_settings_post_accepts_joke_delay_toggle_patch():
    calls = {}
    captured = {}
    body = b'{"joke_delay_punchline_enabled":true}'
    handle_bot_settings_post(
        _handler(body=body),
        apply_bot_settings_fn=lambda req: (
            captured.update({"request": req})
            or {
                "ok": True,
                "joke_delay_punchline_enabled": True,
            }
        ),
        to_int_fn=lambda value: int(value) if value not in (None, "") else None,
        validate_content_length_fn=lambda *_args, **_kwargs: len(body),
        parse_bot_settings_request_fn=lambda _raw: BotSettingsRequest(
            joke_delay_punchline_enabled=True,
        ),
        write_json_response_fn=lambda _handler, **kwargs: calls.update(kwargs),
    )
    assert calls["status_code"] == 200
    assert calls["payload_obj"]["joke_delay_punchline_enabled"] is True
    assert captured["request"].joke_delay_punchline_enabled is True
