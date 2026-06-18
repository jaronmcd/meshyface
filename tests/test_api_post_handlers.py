import io
from types import SimpleNamespace

from meshdash.api_bbs import (
    handle_bbs_host_get,
    handle_bbs_host_post,
    handle_bbs_settings_get,
    handle_bbs_settings_post,
)
from meshdash.api_bots import handle_zork_bot_toggle_post
from meshdash.api_channels import handle_channel_settings_post
from meshdash.api_chat import handle_chat_send_post
from meshdash.api_custom_telemetry import (
    handle_custom_telemetry_settings_get,
    handle_custom_telemetry_settings_post,
)
from meshdash.api_input_bbs import parse_bbs_host_request, parse_bbs_settings_request
from meshdash.api_input_bots import parse_zork_bot_toggle_request
from meshdash.api_input_chat import (
    parse_chat_send_body,
    parse_chat_send_request,
    validate_content_length as validate_chat_content_length,
)
from meshdash.api_input_custom_telemetry import parse_custom_telemetry_settings_request
from meshdash.api_input_zork import parse_standalone_zork_request
from meshdash.api_network_tools import handle_network_tool_post
from meshdash.api_radio import handle_radio_settings_post
from meshdash.api_theme import handle_theme_settings_get, handle_theme_settings_post
from meshdash.api_zork import handle_standalone_zork_post
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


def test_bbs_settings_handlers_cover_read_write_and_validation_paths() -> None:
    calls: list[dict[str, object]] = []
    requests: list[object] = []

    handle_bbs_settings_get(
        _Handler(),
        get_bbs_settings_fn=None,
        write_json_response_fn=_writer(calls),
    )
    handle_bbs_settings_get(
        _Handler(),
        get_bbs_settings_fn=lambda: {"ok": True, "settings": {"title": "Mesh BBS"}},
        write_json_response_fn=_writer(calls),
    )
    handle_bbs_settings_get(
        _Handler(),
        get_bbs_settings_fn=lambda: (_ for _ in ()).throw(RuntimeError("read failed")),
        write_json_response_fn=_writer(calls),
    )
    handle_bbs_settings_post(
        _Handler(b"bbs"),
        set_bbs_settings_fn=None,
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_bbs_settings_request_fn=lambda raw: {"title": raw.decode("utf-8")},
        write_json_response_fn=_writer(calls),
    )
    handle_bbs_settings_post(
        _Handler(b"bbs"),
        set_bbs_settings_fn=lambda request: requests.append(request) or {"ok": True, "request": request},
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_bbs_settings_request_fn=lambda raw: {"title": raw.decode("utf-8")},
        write_json_response_fn=_writer(calls),
    )
    handle_bbs_settings_post(
        _Handler(b"bbs"),
        set_bbs_settings_fn=lambda request: {"ok": False, "error": "invalid bbs settings"},
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_bbs_settings_request_fn=lambda raw: {"title": raw.decode("utf-8")},
        write_json_response_fn=_writer(calls),
    )
    handle_bbs_settings_post(
        _Handler(b"bbs"),
        set_bbs_settings_fn=lambda request: (_ for _ in ()).throw(ValueError("bad board")),
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_bbs_settings_request_fn=lambda raw: {"title": raw.decode("utf-8")},
        write_json_response_fn=_writer(calls),
    )
    handle_bbs_settings_post(
        _Handler(b"bbs"),
        set_bbs_settings_fn=lambda request: (_ for _ in ()).throw(RuntimeError("write failed")),
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_bbs_settings_request_fn=lambda raw: {"title": raw.decode("utf-8")},
        write_json_response_fn=_writer(calls),
    )
    handle_bbs_settings_post(
        _Handler(b"bbs"),
        set_bbs_settings_fn=lambda request: {"ok": True},
        to_int_fn=to_int,
        validate_content_length_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad length")),
        parse_bbs_settings_request_fn=lambda raw: {"title": raw.decode("utf-8")},
        write_json_response_fn=_writer(calls),
    )

    assert [call["status"] for call in calls] == [503, 200, 500, 503, 200, 400, 400, 500, 400]
    assert calls[1] == {
        "status": 200,
        "payload": {"ok": True, "settings": {"title": "Mesh BBS"}},
        "no_store": True,
    }
    assert requests == [{"title": "bbs"}]
    assert calls[2]["payload"]["error"] == "BBS settings failed: read failed"  # type: ignore[index]
    assert calls[6]["payload"]["error"] == "bad board"  # type: ignore[index]
    assert calls[7]["payload"]["error"] == "BBS settings update failed: write failed"  # type: ignore[index]


def test_bbs_host_handlers_cover_runtime_actions_and_errors() -> None:
    calls: list[dict[str, object]] = []
    actions: list[object] = []

    handle_bbs_host_get(
        _Handler(),
        get_bbs_host_runtime_fn=None,
        write_json_response_fn=_writer(calls),
    )
    handle_bbs_host_get(
        _Handler(),
        get_bbs_host_runtime_fn=lambda: {"ok": True, "host": {"enabled": True}},
        write_json_response_fn=_writer(calls),
    )
    handle_bbs_host_get(
        _Handler(),
        get_bbs_host_runtime_fn=lambda: (_ for _ in ()).throw(RuntimeError("host read failed")),
        write_json_response_fn=_writer(calls),
    )
    handle_bbs_host_post(
        _Handler(b"{}"),
        start_bbs_host_fn=None,
        stop_bbs_host_fn=lambda: {"ok": True},
        append_bbs_host_post_fn=None,
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_bbs_host_request_fn=lambda raw: SimpleNamespace(action="start"),
        write_json_response_fn=_writer(calls),
    )
    handle_bbs_host_post(
        _Handler(b"{}"),
        start_bbs_host_fn=lambda request: {"ok": True},
        stop_bbs_host_fn=lambda: {"ok": True},
        append_bbs_host_post_fn=None,
        to_int_fn=to_int,
        validate_content_length_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad length")),
        parse_bbs_host_request_fn=lambda raw: SimpleNamespace(action="start"),
        write_json_response_fn=_writer(calls),
    )
    handle_bbs_host_post(
        _Handler(b"{}"),
        start_bbs_host_fn=lambda request: {"ok": True},
        stop_bbs_host_fn=lambda: {"ok": True},
        append_bbs_host_post_fn=None,
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_bbs_host_request_fn=lambda raw: SimpleNamespace(action="delete"),
        write_json_response_fn=_writer(calls),
    )
    handle_bbs_host_post(
        _Handler(b"{}"),
        start_bbs_host_fn=lambda request: {"ok": True},
        stop_bbs_host_fn=lambda: {"ok": True},
        append_bbs_host_post_fn=None,
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_bbs_host_request_fn=lambda raw: SimpleNamespace(action="post"),
        write_json_response_fn=_writer(calls),
    )
    handle_bbs_host_post(
        _Handler(b"{}"),
        start_bbs_host_fn=lambda request: actions.append(("start", request)) or {"ok": True, "host": {"enabled": True}},
        stop_bbs_host_fn=lambda: {"ok": True},
        append_bbs_host_post_fn=lambda request: {"ok": True},
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_bbs_host_request_fn=lambda raw: SimpleNamespace(action="start"),
        write_json_response_fn=_writer(calls),
    )
    handle_bbs_host_post(
        _Handler(b"{}"),
        start_bbs_host_fn=lambda request: {"ok": True},
        stop_bbs_host_fn=lambda: actions.append("stop") or {"ok": True, "host": {"enabled": False}},
        append_bbs_host_post_fn=lambda request: {"ok": True},
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_bbs_host_request_fn=lambda raw: SimpleNamespace(action="stop"),
        write_json_response_fn=_writer(calls),
    )
    handle_bbs_host_post(
        _Handler(b"{}"),
        start_bbs_host_fn=lambda request: {"ok": True},
        stop_bbs_host_fn=lambda: {"ok": True},
        append_bbs_host_post_fn=lambda request: actions.append(("post", request)) or {"ok": True, "post": {"id": 1}},
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_bbs_host_request_fn=lambda raw: SimpleNamespace(action="post"),
        write_json_response_fn=_writer(calls),
    )
    handle_bbs_host_post(
        _Handler(b"{}"),
        start_bbs_host_fn=lambda request: {"ok": False, "error": "host denied"},
        stop_bbs_host_fn=lambda: {"ok": True},
        append_bbs_host_post_fn=lambda request: {"ok": True},
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_bbs_host_request_fn=lambda raw: SimpleNamespace(action="start"),
        write_json_response_fn=_writer(calls),
    )
    handle_bbs_host_post(
        _Handler(b"{}"),
        start_bbs_host_fn=lambda request: (_ for _ in ()).throw(ValueError("bad host")),
        stop_bbs_host_fn=lambda: {"ok": True},
        append_bbs_host_post_fn=lambda request: {"ok": True},
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_bbs_host_request_fn=lambda raw: SimpleNamespace(action="start"),
        write_json_response_fn=_writer(calls),
    )
    handle_bbs_host_post(
        _Handler(b"{}"),
        start_bbs_host_fn=lambda request: {"ok": True},
        stop_bbs_host_fn=lambda: (_ for _ in ()).throw(RuntimeError("stop failed")),
        append_bbs_host_post_fn=lambda request: {"ok": True},
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_bbs_host_request_fn=lambda raw: SimpleNamespace(action="stop"),
        write_json_response_fn=_writer(calls),
    )

    assert [call["status"] for call in calls] == [
        503,
        200,
        500,
        503,
        400,
        400,
        503,
        200,
        200,
        200,
        400,
        400,
        500,
    ]
    assert calls[1] == {"status": 200, "payload": {"ok": True, "host": {"enabled": True}}, "no_store": True}
    assert calls[2]["payload"]["error"] == "BBS host runtime failed: host read failed"  # type: ignore[index]
    assert calls[5]["no_store"] is True
    assert calls[6]["no_store"] is True
    assert actions[0][0] == "start"  # type: ignore[index]
    assert actions[1] == "stop"
    assert actions[2][0] == "post"  # type: ignore[index]
    assert calls[11]["payload"]["error"] == "bad host"  # type: ignore[index]
    assert calls[12]["payload"]["error"] == "BBS host update failed: stop failed"  # type: ignore[index]


def test_zork_bot_toggle_handler_covers_runtime_actions_and_response_shapes() -> None:
    calls: list[dict[str, object]] = []
    actions: list[object] = []

    def _call(
        request: object | None,
        *,
        default_command: str = "zork",
        set_zork_bot_enabled_fn=lambda enabled: actions.append(("zork", enabled)) or True,
        set_ping_bot_enabled_fn=lambda enabled: actions.append(("ping", enabled)) or {"changed": enabled},
        set_ping_bot_message_only_fn=lambda message_only: actions.append(("mode", message_only)) or {"ok": True},
        manage_zork_bot_fn=lambda action, *, peer_id=None: actions.append((action, peer_id)) or {"ok": True},
        validate_content_length_fn=_validate_content_length,
    ) -> None:
        parse_fn = None if request is None else lambda raw: request
        handle_zork_bot_toggle_post(
            _Handler(b"bot"),
            set_zork_bot_enabled_fn=set_zork_bot_enabled_fn,
            set_ping_bot_enabled_fn=set_ping_bot_enabled_fn,
            set_ping_bot_message_only_fn=set_ping_bot_message_only_fn,
            manage_zork_bot_fn=manage_zork_bot_fn,
            default_command=default_command,
            to_int_fn=to_int,
            validate_content_length_fn=validate_content_length_fn,
            parse_zork_bot_toggle_request_fn=parse_fn,
            write_json_response_fn=_writer(calls),
        )

    _call(None)
    _call(
        SimpleNamespace(action="enable"),
        validate_content_length_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad length")),
    )
    handle_zork_bot_toggle_post(
        _Handler(b"bot"),
        set_zork_bot_enabled_fn=lambda enabled: {"ok": True},
        set_ping_bot_enabled_fn=lambda enabled: {"ok": True},
        set_ping_bot_message_only_fn=lambda message_only: {"ok": True},
        manage_zork_bot_fn=lambda action, *, peer_id=None: {"ok": True},
        default_command="zork",
        to_int_fn=to_int,
        validate_content_length_fn=_validate_content_length,
        parse_zork_bot_toggle_request_fn=lambda raw: (_ for _ in ()).throw(ValueError("bad bot json")),
        write_json_response_fn=_writer(calls),
    )
    _call(SimpleNamespace(action="", command="ping", message_only=True))
    _call(SimpleNamespace(action="enable", command="", message_only=None), default_command="ping")
    _call(SimpleNamespace(action="disable", command="zork", message_only=None))
    _call(
        SimpleNamespace(action="enable", command="ping", message_only=False),
        set_ping_bot_message_only_fn=lambda message_only: actions.append(("mode-denied", message_only))
        or {"ok": False, "error": "mode denied"},
    )
    _call(SimpleNamespace(action="clear_sessions", command="zork", peer_id="!node"))
    _call(SimpleNamespace(action="end_session", command="ping", peer_id="!node"))
    _call(
        SimpleNamespace(action="end_session", command="zork", peer_id="!node"),
        manage_zork_bot_fn=None,
    )
    _call(
        SimpleNamespace(action="enable", command="ping"),
        set_ping_bot_enabled_fn=None,
    )
    _call(
        SimpleNamespace(action="configure", command="ping", message_only=True),
        set_ping_bot_message_only_fn=None,
    )
    _call(
        SimpleNamespace(action="enable", command="ping", message_only=True),
        set_ping_bot_message_only_fn=None,
    )
    _call(SimpleNamespace(action="dance", command="zork"))
    _call(
        SimpleNamespace(action="enable", command="zork"),
        set_zork_bot_enabled_fn=lambda enabled: (_ for _ in ()).throw(RuntimeError("runtime blew up")),
    )

    assert [call["status"] for call in calls] == [
        503,
        400,
        400,
        200,
        200,
        200,
        400,
        200,
        400,
        400,
        400,
        400,
        400,
        400,
        500,
    ]
    assert actions[:6] == [
        ("mode", True),
        ("ping", True),
        ("zork", False),
        ("ping", True),
        ("mode-denied", False),
        ("clear_sessions", "!node"),
    ]
    assert calls[4]["payload"] == {"changed": True, "ok": True}
    assert calls[5]["payload"] == {"ok": True}
    assert calls[8]["payload"]["error"] == "Session management is only available for zork"  # type: ignore[index]
    assert calls[14]["payload"]["error"] == "Zork bot update failed: runtime blew up"  # type: ignore[index]


def test_bbs_and_bot_input_parsers_normalize_nested_payloads_and_bad_json() -> None:
    settings = parse_bbs_settings_request(b'{"settings":{"title":"Mesh","boardId":"mesh-board","motd":"hello"}}')
    host = parse_bbs_host_request(
        b'{"action":" START ","channelIndex":2,"settings":{"title":"Mesh","board_id":"mesh-board"},'
        b'"text":"post","authorName":"Node","entryId":"entry-1"}'
    )
    bad_settings = parse_bbs_settings_request(b"{bad json")
    bad_host = parse_bbs_host_request(b"{bad json")
    enabled = parse_zork_bot_toggle_request(
        b'{"settings":{"enabled":"yes","command":"ping","messageOnly":"off","peerId":"!peer"}}'
    )
    disabled = parse_zork_bot_toggle_request(b'{"enabled":0,"message_only":1}')
    text_disabled = parse_zork_bot_toggle_request(b'{"enabled":"disabled","messageOnly":"enabled"}')
    bad_bot = parse_zork_bot_toggle_request(b"{bad json")

    assert settings.title == "Mesh"
    assert settings.board_id == "mesh-board"
    assert settings.motd == "hello"
    assert host.action == "start"
    assert host.channel_index == 2
    assert host.title == "Mesh"
    assert host.board_id == "mesh-board"
    assert host.text == "post"
    assert host.author_name == "Node"
    assert host.entry_id == "entry-1"
    assert bad_settings.title is None
    assert bad_host.action == ""
    assert enabled.enabled is True
    assert enabled.action == "enable"
    assert enabled.command == "ping"
    assert enabled.message_only is False
    assert enabled.peer_id == "!peer"
    assert disabled.enabled is False
    assert disabled.action == "disable"
    assert disabled.message_only is True
    assert text_disabled.enabled is False
    assert text_disabled.message_only is True
    assert bad_bot.enabled is None
    assert bad_bot.action == ""


def test_zork_bot_input_parser_rejects_bad_boolean_values() -> None:
    for raw_body, expected in [
        (b'{"enabled":null}', "enabled is required"),
        (b'{"enabled":"maybe"}', "enabled must be boolean"),
        (b'{"message_only":"maybe"}', "message_only must be boolean"),
    ]:
        try:
            parse_zork_bot_toggle_request(raw_body)
        except ValueError as exc:
            assert str(exc) == expected
        else:
            raise AssertionError(f"{raw_body!r} should have failed")


def test_chat_custom_telemetry_and_standalone_zork_input_parsers() -> None:
    chat = parse_chat_send_request(
        b'{"text":"hello","destination":"!node","channel_index":"2","reply_id":"10","retry_of":"8","emoji":":wave:"}',
        to_int_fn=to_int,
    )
    body = parse_chat_send_body(b"not json", to_int_fn=to_int)
    telemetry = parse_custom_telemetry_settings_request(b'{"rules":[{"name":"battery"}]}')
    empty_telemetry = parse_custom_telemetry_settings_request(b"not json")
    zork = parse_standalone_zork_request(b'{"text":"look","session_id":"local-1"}')
    empty_zork = parse_standalone_zork_request(b"not json")

    assert validate_chat_content_length({"Content-Length": "4"}, to_int_fn=to_int) == 4
    for headers, max_bytes in [
        ({}, 8192),
        ({"Content-Length": "0"}, 8192),
        ({"Content-Length": "9"}, 8),
    ]:
        try:
            validate_chat_content_length(headers, to_int_fn=to_int, max_bytes=max_bytes)
        except ValueError as exc:
            assert str(exc) == "Invalid request size"
        else:
            raise AssertionError(f"{headers!r} should have failed")

    assert chat.text == "hello"
    assert chat.destination == "!node"
    assert chat.channel_index == 2
    assert chat.reply_id == 10
    assert chat.retry_of == 8
    assert chat.emoji == ":wave:"
    assert body == {
        "text": None,
        "destination": None,
        "channel_index": None,
        "reply_id": None,
        "retry_of": None,
        "emoji": None,
    }
    assert telemetry.rules == [{"name": "battery"}]
    assert empty_telemetry.rules is None
    assert zork.text == "look"
    assert zork.session_id == "local-1"
    assert empty_zork.text is None
    assert empty_zork.session_id is None


def test_standalone_zork_handler_maps_validation_and_runtime_paths() -> None:
    calls: list[dict[str, object]] = []
    played: list[dict[str, object]] = []

    def _call(
        *,
        play_standalone_zork_fn,
        parse_standalone_zork_request_fn=lambda raw: SimpleNamespace(
            text=raw.decode("utf-8"),
            session_id="session-1",
        ),
        validate_content_length_fn=_validate_content_length,
    ) -> None:
        handle_standalone_zork_post(
            _Handler(b"look"),
            play_standalone_zork_fn=play_standalone_zork_fn,
            to_int_fn=to_int,
            validate_content_length_fn=validate_content_length_fn,
            parse_standalone_zork_request_fn=parse_standalone_zork_request_fn,
            write_json_response_fn=_writer(calls),
        )

    _call(play_standalone_zork_fn=None)
    _call(
        play_standalone_zork_fn=lambda **kwargs: {"ok": True},
        validate_content_length_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad length")),
    )
    _call(
        play_standalone_zork_fn=lambda **kwargs: played.append(kwargs) or {"ok": True, "reply_text": "seen"},
    )
    _call(play_standalone_zork_fn=lambda **kwargs: {"ok": False, "error": "lost"})
    _call(
        play_standalone_zork_fn=lambda **kwargs: (_ for _ in ()).throw(ValueError("bad command")),
    )
    _call(
        play_standalone_zork_fn=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("engine crashed")),
    )

    assert [call["status"] for call in calls] == [503, 400, 200, 400, 400, 500]
    assert played == [{"text": "look", "session_id": "session-1"}]
    assert calls[2] == {"status": 200, "payload": {"ok": True, "reply_text": "seen"}, "no_store": True}
    assert calls[4]["payload"]["error"] == "bad command"  # type: ignore[index]
    assert calls[5]["payload"]["error"] == "Standalone Zork failed"  # type: ignore[index]


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


def _call_network_tool(
    calls: list[dict[str, object]],
    *,
    run_network_tool_fn,
    parse_network_tool_request_fn=lambda raw, *, to_int_fn: {"body": raw.decode("utf-8")},
    validate_content_length_fn=_validate_content_length,
) -> None:
    handle_network_tool_post(
        _Handler(b"tool"),
        run_network_tool_fn=run_network_tool_fn,
        to_int_fn=to_int,
        validate_content_length_fn=validate_content_length_fn,
        parse_network_tool_request_fn=parse_network_tool_request_fn,
        write_json_response_fn=_writer(calls),
    )


def test_network_tool_handler_maps_disabled_parse_run_and_status_paths() -> None:
    calls: list[dict[str, object]] = []
    received: list[object] = []

    _call_network_tool(calls, run_network_tool_fn=None)
    _call_network_tool(calls, run_network_tool_fn=lambda request: received.append(request) or {"ok": True})
    _call_network_tool(calls, run_network_tool_fn=lambda request: {"ok": False, "error": "denied"})
    _call_network_tool(
        calls,
        run_network_tool_fn=lambda request: {"ok": True},
        parse_network_tool_request_fn=lambda raw, *, to_int_fn: (_ for _ in ()).throw(ValueError("bad tool json")),
    )
    _call_network_tool(
        calls,
        run_network_tool_fn=lambda request: (_ for _ in ()).throw(ValueError("bad target")),
    )
    _call_network_tool(
        calls,
        run_network_tool_fn=lambda request: (_ for _ in ()).throw(RuntimeError("tool crashed")),
    )
    _call_network_tool(
        calls,
        run_network_tool_fn=lambda request: {"ok": True},
        validate_content_length_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad length")),
    )

    assert [call["status"] for call in calls] == [503, 200, 400, 400, 400, 500, 400]
    assert received == [{"body": "tool"}]
    assert calls[1]["no_store"] is True
    assert calls[2]["payload"] == {"ok": False, "error": "denied"}
    assert calls[3]["payload"]["error"] == "bad tool json"  # type: ignore[index]
    assert calls[4]["payload"]["error"] == "bad target"  # type: ignore[index]
    assert calls[5]["payload"]["error"] == "Network tool failed: tool crashed"  # type: ignore[index]
