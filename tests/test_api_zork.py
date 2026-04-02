import io

from meshdash.api_input_zork import StandaloneZorkRequest
from meshdash.api_zork import handle_standalone_zork_post


def _handler(body=b"{}"):
    class _H:
        def __init__(self):
            self.rfile = io.BytesIO(body)
            self.headers = {"Content-Length": str(len(body))}

    return _H()


def test_handle_standalone_zork_post_returns_503_when_disabled():
    calls = {}

    handle_standalone_zork_post(
        _handler(),
        play_standalone_zork_fn=None,
        to_int_fn=lambda value: int(value) if value not in (None, "") else None,
        validate_content_length_fn=lambda *_args, **_kwargs: 2,
        parse_standalone_zork_request_fn=None,
        write_json_response_fn=lambda _handler, **kwargs: calls.update(kwargs),
    )

    assert calls["status_code"] == 503
    assert "Standalone Zork is not enabled" in calls["payload_obj"]["error"]


def test_handle_standalone_zork_post_returns_400_on_invalid_request_size():
    calls = {}

    def _raise_size(*_args, **_kwargs):
        raise ValueError("bad size")

    handle_standalone_zork_post(
        _handler(),
        play_standalone_zork_fn=lambda **_kwargs: {"ok": True},
        to_int_fn=lambda value: int(value) if value not in (None, "") else None,
        validate_content_length_fn=_raise_size,
        parse_standalone_zork_request_fn=lambda _raw: StandaloneZorkRequest(text="look", session_id="s1"),
        write_json_response_fn=lambda _handler, **kwargs: calls.update(kwargs),
    )

    assert calls["status_code"] == 400
    assert calls["payload_obj"]["error"] == "Invalid request size"


def test_handle_standalone_zork_post_returns_400_on_value_error():
    calls = {}

    def _play(**_kwargs):
        raise ValueError("invalid zork input")

    handle_standalone_zork_post(
        _handler(body=b'{"text":"look"}'),
        play_standalone_zork_fn=_play,
        to_int_fn=lambda value: int(value) if value not in (None, "") else None,
        validate_content_length_fn=lambda *_args, **_kwargs: len(b'{"text":"look"}'),
        parse_standalone_zork_request_fn=lambda _raw: StandaloneZorkRequest(text="look", session_id="s1"),
        write_json_response_fn=lambda _handler, **kwargs: calls.update(kwargs),
    )

    assert calls["status_code"] == 400
    assert calls["payload_obj"]["error"] == "invalid zork input"


def test_handle_standalone_zork_post_returns_500_on_unexpected_exception():
    calls = {}

    def _play(**_kwargs):
        raise RuntimeError("zork blew up")

    handle_standalone_zork_post(
        _handler(body=b'{"text":"look"}'),
        play_standalone_zork_fn=_play,
        to_int_fn=lambda value: int(value) if value not in (None, "") else None,
        validate_content_length_fn=lambda *_args, **_kwargs: len(b'{"text":"look"}'),
        parse_standalone_zork_request_fn=lambda _raw: StandaloneZorkRequest(text="look", session_id="s1"),
        write_json_response_fn=lambda _handler, **kwargs: calls.update(kwargs),
    )

    assert calls["status_code"] == 500
    assert calls["payload_obj"]["error"] == "Standalone Zork failed"


def test_handle_standalone_zork_post_returns_200_and_passes_request_fields():
    calls = {}
    captured = {}

    def _play(*, text, session_id):
        captured["text"] = text
        captured["session_id"] = session_id
        return {"ok": True, "reply": "West of House"}

    handle_standalone_zork_post(
        _handler(body=b'{"text":"look","session_id":"abc"}'),
        play_standalone_zork_fn=_play,
        to_int_fn=lambda value: int(value) if value not in (None, "") else None,
        validate_content_length_fn=lambda *_args, **_kwargs: len(b'{"text":"look","session_id":"abc"}'),
        parse_standalone_zork_request_fn=lambda _raw: StandaloneZorkRequest(text="look", session_id="abc"),
        write_json_response_fn=lambda _handler, **kwargs: calls.update(kwargs),
    )

    assert captured == {"text": "look", "session_id": "abc"}
    assert calls["status_code"] == 200
    assert calls["payload_obj"]["reply"] == "West of House"
    assert calls["no_store"] is True


def test_handle_standalone_zork_post_returns_400_when_response_not_ok():
    calls = {}

    handle_standalone_zork_post(
        _handler(body=b'{"text":"x nonsense"}'),
        play_standalone_zork_fn=lambda **_kwargs: {"ok": False, "error": "no session"},
        to_int_fn=lambda value: int(value) if value not in (None, "") else None,
        validate_content_length_fn=lambda *_args, **_kwargs: len(b'{"text":"x nonsense"}'),
        parse_standalone_zork_request_fn=lambda _raw: StandaloneZorkRequest(text="x nonsense", session_id=None),
        write_json_response_fn=lambda _handler, **kwargs: calls.update(kwargs),
    )

    assert calls["status_code"] == 400
    assert calls["payload_obj"]["error"] == "no session"
    assert calls["no_store"] is True
