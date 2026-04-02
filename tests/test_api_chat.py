import io

from meshdash.api_inputs import ChatSendRequest
from meshdash.api_chat import handle_chat_send_post


def _fake_handler(body: bytes = b"{}"):
    class _Handler:
        def __init__(self):
            self.headers = {"Content-Length": str(len(body))}
            self.rfile = io.BytesIO(body)

    return _Handler()


def test_handle_chat_send_post_returns_503_when_disabled():
    calls = []

    handle_chat_send_post(
        _fake_handler(),
        send_chat_fn=None,
        to_int_fn=lambda value: int(value) if value else None,
        validate_content_length_fn=lambda *_args, **_kwargs: 2,
        parse_chat_send_request_fn=lambda *_args, **_kwargs: ChatSendRequest(
            text=None,
            destination=None,
            channel_index=None,
            reply_id=None,
            retry_of=None,
            emoji=None,
        ),
        write_json_response_fn=lambda *_args, **kwargs: calls.append(kwargs),
    )

    assert calls[0]["status_code"] == 503
    assert calls[0]["payload_obj"]["ok"] is False


def test_handle_chat_send_post_returns_400_on_invalid_content_length():
    calls = []

    handle_chat_send_post(
        _fake_handler(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        to_int_fn=lambda value: int(value) if value else None,
        validate_content_length_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad size")),
        parse_chat_send_request_fn=lambda *_args, **_kwargs: ChatSendRequest(
            text=None,
            destination=None,
            channel_index=None,
            reply_id=None,
            retry_of=None,
            emoji=None,
        ),
        write_json_response_fn=lambda *_args, **kwargs: calls.append(kwargs),
    )

    assert calls[0]["status_code"] == 400
    assert calls[0]["payload_obj"]["error"] == "Invalid request size"


def test_handle_chat_send_post_returns_400_for_value_errors():
    calls = []

    handle_chat_send_post(
        _fake_handler(),
        send_chat_fn=lambda **_kwargs: (_ for _ in ()).throw(ValueError("bad request")),
        to_int_fn=lambda value: int(value) if value else None,
        validate_content_length_fn=lambda *_args, **_kwargs: 2,
        parse_chat_send_request_fn=lambda *_args, **_kwargs: ChatSendRequest(
            text="x",
            destination="^all",
            channel_index=0,
            reply_id=None,
            retry_of=None,
            emoji=None,
        ),
        write_json_response_fn=lambda *_args, **kwargs: calls.append(kwargs),
    )

    assert calls[0]["status_code"] == 400
    assert calls[0]["payload_obj"]["error"] == "bad request"


def test_handle_chat_send_post_returns_200_on_success():
    calls = []

    handle_chat_send_post(
        _fake_handler(),
        send_chat_fn=lambda **_kwargs: {"ok": True, "message_id": 123},
        to_int_fn=lambda value: int(value) if value else None,
        validate_content_length_fn=lambda *_args, **_kwargs: 2,
        parse_chat_send_request_fn=lambda *_args, **_kwargs: ChatSendRequest(
            text="hello",
            destination="^all",
            channel_index=0,
            reply_id=None,
            retry_of=None,
            emoji=None,
        ),
        write_json_response_fn=lambda *_args, **kwargs: calls.append(kwargs),
    )

    assert calls[0]["status_code"] == 200
    assert calls[0]["payload_obj"]["ok"] is True
    assert calls[0]["payload_obj"]["message_id"] == 123
    assert calls[0]["no_store"] is True


def test_handle_chat_send_post_returns_500_for_unexpected_errors():
    calls = []

    handle_chat_send_post(
        _fake_handler(),
        send_chat_fn=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
        to_int_fn=lambda value: int(value) if value else None,
        validate_content_length_fn=lambda *_args, **_kwargs: 2,
        parse_chat_send_request_fn=lambda *_args, **_kwargs: ChatSendRequest(
            text="x",
            destination="^all",
            channel_index=0,
            reply_id=None,
            retry_of=None,
            emoji=None,
        ),
        write_json_response_fn=lambda *_args, **kwargs: calls.append(kwargs),
    )

    assert calls[0]["status_code"] == 500
    assert calls[0]["payload_obj"]["ok"] is False
    assert "Send failed: boom" in calls[0]["payload_obj"]["error"]
