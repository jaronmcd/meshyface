import io
from types import SimpleNamespace

from meshdash.api_channels import handle_channel_settings_post
from meshdash.api_chat import handle_chat_send_post
from meshdash.api_custom_telemetry import (
    handle_custom_telemetry_settings_get,
    handle_custom_telemetry_settings_post,
)
from meshdash.api_radio import handle_radio_settings_post
from meshdash.api_theme import handle_theme_settings_get, handle_theme_settings_post
from meshdash.helpers import to_int


class _Handler:
    def __init__(self, body: bytes = b"payload") -> None:
        self.headers = {"Content-Length": str(len(body))}
        self.rfile = io.BytesIO(body)


def _validate_content_length(headers: object, *, to_int_fn, max_bytes: int = 65536) -> int:
    length = to_int_fn(headers.get("Content-Length"))  # type: ignore[attr-defined]
    if length is None:
        raise ValueError("bad length")
    if length < 0 or length > max_bytes:
        raise ValueError("bad length")
    return length


def _writer(calls: list[dict[str, object]]):
    def _write(handler, *, status_code, payload_obj, no_store=False, **kwargs):
        calls.append(
            {
                "status": status_code,
                "payload": payload_obj,
                "no_store": no_store,
            }
        )

    return _write


def _call_chat(
    calls: list[dict[str, object]],
    *,
    send_chat_fn,
    validate_content_length_fn=_validate_content_length,
    parse_chat_send_request_fn=lambda raw, *, to_int_fn: SimpleNamespace(
        text=raw.decode("utf-8"),
        destination="!node",
        channel_index=1,
        reply_id=2,
        retry_of=3,
        emoji=":wave:",
    ),
) -> None:
    handle_chat_send_post(
        _Handler(b"hello"),
        send_chat_fn=send_chat_fn,
        to_int_fn=to_int,
        validate_content_length_fn=validate_content_length_fn,
        parse_chat_send_request_fn=parse_chat_send_request_fn,
        write_json_response_fn=_writer(calls),
    )


def test_chat_send_handler_maps_disabled_success_and_errors() -> None:
    calls: list[dict[str, object]] = []
    sent: list[dict[str, object]] = []

    _call_chat(calls, send_chat_fn=None)
    _call_chat(
        calls,
        send_chat_fn=lambda **kwargs: sent.append(kwargs) or {"ok": True, "packet_id": 123},
    )
    _call_chat(calls, send_chat_fn=lambda **_kwargs: (_ for _ in ()).throw(ValueError("bad chat")))
    _call_chat(calls, send_chat_fn=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("radio down")))
    _call_chat(
        calls,
        send_chat_fn=lambda **_kwargs: {"ok": True},
        validate_content_length_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("too big")),
    )

    assert [call["status"] for call in calls] == [503, 200, 400, 500, 400]
    assert calls[1] == {"status": 200, "payload": {"ok": True, "packet_id": 123}, "no_store": True}
    assert sent == [
        {
            "text": "hello",
            "destination": "!node",
            "channel_index": 1,
            "reply_id": 2,
            "retry_of": 3,
            "emoji": ":wave:",
        }
    ]
    assert calls[2]["payload"]["error"] == "bad chat"  # type: ignore[index]
    assert calls[3]["payload"]["error"] == "Send failed: radio down"  # type: ignore[index]
    assert calls[4]["payload"]["error"] == "Invalid request size"  # type: ignore[index]


def _call_radio(
    calls: list[dict[str, object]],
    *,
    apply_radio_settings_fn,
    parse_radio_settings_request_fn=lambda raw: {"body": raw.decode("utf-8")},
    validate_content_length_fn=_validate_content_length,
) -> None:
    handle_radio_settings_post(
        _Handler(b"radio"),
        apply_radio_settings_fn=apply_radio_settings_fn,
        to_int_fn=to_int,
        validate_content_length_fn=validate_content_length_fn,
        parse_radio_settings_request_fn=parse_radio_settings_request_fn,
        write_json_response_fn=_writer(calls),
    )


def test_radio_settings_handler_maps_parse_apply_and_status_paths() -> None:
    calls: list[dict[str, object]] = []
    received: list[object] = []

    _call_radio(calls, apply_radio_settings_fn=None)
    _call_radio(calls, apply_radio_settings_fn=lambda request: received.append(request) or {"ok": True})
    _call_radio(calls, apply_radio_settings_fn=lambda request: {"ok": False, "error": "rejected"})
    _call_radio(
        calls,
        apply_radio_settings_fn=lambda request: {"ok": True},
        parse_radio_settings_request_fn=lambda raw: (_ for _ in ()).throw(ValueError("bad json")),
    )
    _call_radio(
        calls,
        apply_radio_settings_fn=lambda request: (_ for _ in ()).throw(RuntimeError("write failed")),
    )
    _call_radio(
        calls,
        apply_radio_settings_fn=lambda request: {"ok": True},
        validate_content_length_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad length")),
    )

    assert [call["status"] for call in calls] == [503, 200, 400, 400, 500, 400]
    assert received == [{"body": "radio"}]
    assert calls[1]["no_store"] is True
    assert calls[2]["payload"] == {"ok": False, "error": "rejected"}
    assert calls[3]["payload"]["error"] == "bad json"  # type: ignore[index]
    assert calls[4]["payload"]["error"] == "Radio settings update failed: write failed"  # type: ignore[index]


def _call_channel(
    calls: list[dict[str, object]],
    *,
    apply_channel_settings_fn,
    parse_channel_settings_request_fn=lambda raw: {"body": raw.decode("utf-8")},
    validate_content_length_fn=_validate_content_length,
) -> None:
    handle_channel_settings_post(
        _Handler(b"channel"),
        apply_channel_settings_fn=apply_channel_settings_fn,
        to_int_fn=to_int,
        validate_content_length_fn=validate_content_length_fn,
        parse_channel_settings_request_fn=parse_channel_settings_request_fn,
        write_json_response_fn=_writer(calls),
    )


def test_channel_settings_handler_maps_parse_apply_and_status_paths() -> None:
    calls: list[dict[str, object]] = []

    _call_channel(calls, apply_channel_settings_fn=None)
    _call_channel(calls, apply_channel_settings_fn=lambda request: {"ok": True, "request": request})
    _call_channel(calls, apply_channel_settings_fn=lambda request: {"ok": False, "error": "invalid channel"})
    _call_channel(
        calls,
        apply_channel_settings_fn=lambda request: {"ok": True},
        parse_channel_settings_request_fn=lambda raw: (_ for _ in ()).throw(ValueError("bad channel json")),
    )
    _call_channel(
        calls,
        apply_channel_settings_fn=lambda request: (_ for _ in ()).throw(RuntimeError("channel write failed")),
    )
    _call_channel(
        calls,
        apply_channel_settings_fn=lambda request: {"ok": True},
        validate_content_length_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad length")),
    )

    assert [call["status"] for call in calls] == [503, 200, 400, 400, 500, 400]
    assert calls[1]["payload"] == {"ok": True, "request": {"body": "channel"}}
    assert calls[3]["payload"]["error"] == "bad channel json"  # type: ignore[index]
    assert calls[4]["payload"]["error"] == "Channel settings update failed: channel write failed"  # type: ignore[index]


def test_theme_settings_get_and_post_handlers_cover_success_and_failures() -> None:
    calls: list[dict[str, object]] = []

    handle_theme_settings_get(
        _Handler(),
        get_theme_settings_fn=None,
        write_json_response_fn=_writer(calls),
    )
    handle_theme_settings_get(
        _Handler(),
        get_theme_settings_fn=lambda: {"ok": True, "theme": "dark"},
        write_json_response_fn=_writer(calls),
    )
    handle_theme_settings_get(
        _Handler(),
        get_theme_settings_fn=lambda: (_ for _ in ()).throw(RuntimeError("theme read failed")),
        write_json_response_fn=_writer(calls),
    )
    handle_theme_settings_post(
        _Handler(b"theme"),
        set_theme_preset_fn=None,
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_theme_settings_request_fn=lambda raw: {"preset": raw.decode("utf-8")},
        write_json_response_fn=_writer(calls),
    )
    handle_theme_settings_post(
        _Handler(b"theme"),
        set_theme_preset_fn=lambda request: {"ok": True, "request": request},
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_theme_settings_request_fn=lambda raw: {"preset": raw.decode("utf-8")},
        write_json_response_fn=_writer(calls),
    )
    handle_theme_settings_post(
        _Handler(b"theme"),
        set_theme_preset_fn=lambda request: {"ok": False, "error": "bad theme"},
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_theme_settings_request_fn=lambda raw: {"preset": raw.decode("utf-8")},
        write_json_response_fn=_writer(calls),
    )
    handle_theme_settings_post(
        _Handler(b"theme"),
        set_theme_preset_fn=lambda request: (_ for _ in ()).throw(RuntimeError("write failed")),
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_theme_settings_request_fn=lambda raw: {"preset": raw.decode("utf-8")},
        write_json_response_fn=_writer(calls),
    )
    handle_theme_settings_post(
        _Handler(b"theme"),
        set_theme_preset_fn=lambda request: {"ok": True},
        to_int_fn=to_int,
        validate_content_length_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad length")),
        parse_theme_settings_request_fn=lambda raw: {"preset": raw.decode("utf-8")},
        write_json_response_fn=_writer(calls),
    )

    assert [call["status"] for call in calls] == [503, 200, 500, 503, 200, 400, 500, 400]
    assert calls[1] == {"status": 200, "payload": {"ok": True, "theme": "dark"}, "no_store": True}
    assert calls[2]["payload"]["error"] == "Theme settings failed: theme read failed"  # type: ignore[index]
    assert calls[6]["payload"]["error"] == "Theme settings update failed: write failed"  # type: ignore[index]


def test_custom_telemetry_handlers_cover_read_write_and_validation_paths() -> None:
    calls: list[dict[str, object]] = []

    handle_custom_telemetry_settings_get(
        _Handler(),
        get_custom_telemetry_settings_fn=None,
        write_json_response_fn=_writer(calls),
    )
    handle_custom_telemetry_settings_get(
        _Handler(),
        get_custom_telemetry_settings_fn=lambda: {"ok": True, "rules": []},
        write_json_response_fn=_writer(calls),
    )
    handle_custom_telemetry_settings_get(
        _Handler(),
        get_custom_telemetry_settings_fn=lambda: (_ for _ in ()).throw(RuntimeError("read failed")),
        write_json_response_fn=_writer(calls),
    )
    handle_custom_telemetry_settings_post(
        _Handler(b"rules"),
        set_custom_telemetry_settings_fn=None,
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_custom_telemetry_settings_request_fn=lambda raw: SimpleNamespace(rules=[]),
        write_json_response_fn=_writer(calls),
    )
    handle_custom_telemetry_settings_post(
        _Handler(b"rules"),
        set_custom_telemetry_settings_fn=lambda rules: {"ok": True, "rules": rules},
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_custom_telemetry_settings_request_fn=lambda raw: SimpleNamespace(rules=[{"name": raw.decode("utf-8")}]),
        write_json_response_fn=_writer(calls),
    )
    handle_custom_telemetry_settings_post(
        _Handler(b"rules"),
        set_custom_telemetry_settings_fn=lambda rules: {"ok": True},
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_custom_telemetry_settings_request_fn=lambda raw: SimpleNamespace(rules=None),
        write_json_response_fn=_writer(calls),
    )
    handle_custom_telemetry_settings_post(
        _Handler(b"rules"),
        set_custom_telemetry_settings_fn=lambda rules: (_ for _ in ()).throw(ValueError("bad rule")),
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_custom_telemetry_settings_request_fn=lambda raw: SimpleNamespace(rules=[]),
        write_json_response_fn=_writer(calls),
    )
    handle_custom_telemetry_settings_post(
        _Handler(b"rules"),
        set_custom_telemetry_settings_fn=lambda rules: (_ for _ in ()).throw(RuntimeError("write failed")),
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_custom_telemetry_settings_request_fn=lambda raw: SimpleNamespace(rules=[]),
        write_json_response_fn=_writer(calls),
    )
    handle_custom_telemetry_settings_post(
        _Handler(b"rules"),
        set_custom_telemetry_settings_fn=lambda rules: {"ok": True},
        to_int_fn=to_int,
        validate_content_length_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad length")),
        parse_custom_telemetry_settings_request_fn=lambda raw: SimpleNamespace(rules=[]),
        write_json_response_fn=_writer(calls),
    )

    assert [call["status"] for call in calls] == [503, 200, 500, 503, 200, 400, 400, 500, 400]
    assert calls[1] == {"status": 200, "payload": {"ok": True, "rules": []}, "no_store": True}
    assert calls[4]["payload"] == {"ok": True, "rules": [{"name": "rules"}]}
    assert calls[5]["payload"]["error"] == "No custom telemetry rules provided"  # type: ignore[index]
    assert calls[6]["payload"]["error"] == "bad rule"  # type: ignore[index]
    assert calls[7]["payload"]["error"] == "Custom telemetry settings update failed: write failed"  # type: ignore[index]
