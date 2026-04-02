import io

from meshdash import http_routes_post as routes_post
from meshdash.api_inputs import (
    BotSettingsRequest,
    ChannelSettingsRequest,
    ChatSendRequest,
    CustomTelemetrySettingsRequest,
    RadioSettingsRequest,
    StandaloneZorkRequest,
    ThemeSettingsRequest,
)
from meshdash.http_route_contracts import DashboardPostRouteDependencies


def _fake_handler(body=b"{}", headers=None):
    class _H:
        def __init__(self):
            self.rfile = io.BytesIO(body)
            self.headers = {"Content-Length": str(len(body))}
            if isinstance(headers, dict):
                self.headers.update(headers)

    return _H()


def _build_post_deps(*, json_calls, api_token=None, private_mode=False, api_metrics=None):
    return DashboardPostRouteDependencies(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        to_int_fn=lambda value: int(value) if value not in (None, "") else None,
        validate_content_length_fn=lambda *_args, **_kwargs: 2,
        parse_chat_send_request_fn=lambda *_args, **_kwargs: ChatSendRequest(
            text="hello",
            destination="^all",
            channel_index=0,
            reply_id=None,
            retry_of=None,
            emoji=None,
        ),
        write_json_response_fn=lambda _handler, **kwargs: json_calls.append(kwargs),
        set_theme_preset_fn=lambda preset_name: {"ok": True, "selected_preset": str(preset_name)},
        parse_theme_settings_request_fn=lambda _raw: ThemeSettingsRequest(preset_name="forest"),
        set_custom_telemetry_settings_fn=lambda rules: {"ok": True, "rules": list(rules or []), "updated_unix": 0},
        parse_custom_telemetry_settings_request_fn=lambda _raw: CustomTelemetrySettingsRequest(rules=[]),
        apply_radio_settings_fn=lambda _req: {"ok": True, "applied": True},
        parse_radio_settings_request_fn=lambda _raw: RadioSettingsRequest(),
        apply_channel_settings_fn=lambda _req: {"ok": True, "channel_applied": True},
        parse_channel_settings_request_fn=lambda _raw: ChannelSettingsRequest(action="list"),
        apply_bot_settings_fn=lambda _req: {"ok": True, "bot_applied": True},
        parse_bot_settings_request_fn=lambda _raw: BotSettingsRequest(game_enabled=True),
        play_standalone_zork_fn=lambda **_kwargs: {"ok": True, "route": "zork"},
        parse_standalone_zork_request_fn=lambda _raw: StandaloneZorkRequest(text="zork", session_id="abc"),
        api_token=api_token,
        private_mode=private_mode,
        api_metrics=api_metrics,
    )


def test_handle_dashboard_post_enabled_routes_delegate_to_helpers(monkeypatch):
    json_calls = []
    helper_calls = {"chat": 0, "zork": 0, "radio": 0, "channels": 0, "theme": 0, "custom": 0, "bot": 0}

    monkeypatch.setattr(
        routes_post,
        "_handle_chat_send_post_helper",
        lambda handler, **kwargs: (
            helper_calls.__setitem__("chat", helper_calls["chat"] + 1),
            json_calls.append({"status_code": 200, "payload_obj": {"route": "chat"}}),
        ),
    )
    monkeypatch.setattr(
        routes_post,
        "_handle_standalone_zork_post_helper",
        lambda handler, **kwargs: (
            helper_calls.__setitem__("zork", helper_calls["zork"] + 1),
            json_calls.append({"status_code": 200, "payload_obj": {"route": "zork"}}),
        ),
    )
    monkeypatch.setattr(
        routes_post,
        "_handle_radio_settings_post_helper",
        lambda handler, **kwargs: (
            helper_calls.__setitem__("radio", helper_calls["radio"] + 1),
            json_calls.append({"status_code": 200, "payload_obj": {"route": "radio"}}),
        ),
    )
    monkeypatch.setattr(
        routes_post,
        "_handle_channel_settings_post_helper",
        lambda handler, **kwargs: (
            helper_calls.__setitem__("channels", helper_calls["channels"] + 1),
            json_calls.append({"status_code": 200, "payload_obj": {"route": "channels"}}),
        ),
    )
    monkeypatch.setattr(
        routes_post,
        "_handle_theme_settings_post_helper",
        lambda handler, **kwargs: (
            helper_calls.__setitem__("theme", helper_calls["theme"] + 1),
            json_calls.append({"status_code": 200, "payload_obj": {"route": "theme"}}),
        ),
    )
    monkeypatch.setattr(
        routes_post,
        "_handle_custom_telemetry_settings_post_helper",
        lambda handler, **kwargs: (
            helper_calls.__setitem__("custom", helper_calls["custom"] + 1),
            json_calls.append({"status_code": 200, "payload_obj": {"route": "custom"}}),
        ),
    )
    monkeypatch.setattr(
        routes_post,
        "_handle_bot_settings_post_helper",
        lambda handler, **kwargs: (
            helper_calls.__setitem__("bot", helper_calls["bot"] + 1),
            json_calls.append({"status_code": 200, "payload_obj": {"route": "bot"}}),
        ),
    )

    deps = _build_post_deps(json_calls=json_calls)
    handler = _fake_handler()

    routes_post.handle_dashboard_post(handler, path="/api/chat/send", deps=deps)
    routes_post.handle_dashboard_post(handler, path="/api/games/zork", deps=deps)
    routes_post.handle_dashboard_post(handler, path="/api/settings/radio", deps=deps)
    routes_post.handle_dashboard_post(handler, path="/api/settings/channels", deps=deps)
    routes_post.handle_dashboard_post(handler, path="/api/settings/theme", deps=deps)
    routes_post.handle_dashboard_post(handler, path="/api/settings/custom_telemetry", deps=deps)
    routes_post.handle_dashboard_post(handler, path="/api/settings/bot", deps=deps)
    routes_post.handle_dashboard_post(handler, path="/missing", deps=deps)

    assert helper_calls == {"chat": 1, "zork": 1, "radio": 1, "channels": 1, "theme": 1, "custom": 1, "bot": 1}
    assert json_calls[0]["payload_obj"]["route"] == "chat"
    assert json_calls[1]["payload_obj"]["route"] == "zork"
    assert json_calls[2]["payload_obj"]["route"] == "radio"
    assert json_calls[3]["payload_obj"]["route"] == "channels"
    assert json_calls[4]["payload_obj"]["route"] == "theme"
    assert json_calls[5]["payload_obj"]["route"] == "custom"
    assert json_calls[6]["payload_obj"]["route"] == "bot"
    assert json_calls[7]["status_code"] == 404


def test_handle_dashboard_post_disabled_feature_paths_return_503():
    json_calls = []
    deps = _build_post_deps(json_calls=json_calls)
    handler = _fake_handler()

    deps_disabled_radio = DashboardPostRouteDependencies(
        send_chat_fn=deps.send_chat_fn,
        to_int_fn=deps.to_int_fn,
        validate_content_length_fn=deps.validate_content_length_fn,
        parse_chat_send_request_fn=deps.parse_chat_send_request_fn,
        write_json_response_fn=deps.write_json_response_fn,
        set_theme_preset_fn=deps.set_theme_preset_fn,
        parse_theme_settings_request_fn=deps.parse_theme_settings_request_fn,
        apply_radio_settings_fn=deps.apply_radio_settings_fn,
        parse_radio_settings_request_fn=None,
        apply_channel_settings_fn=deps.apply_channel_settings_fn,
        parse_channel_settings_request_fn=deps.parse_channel_settings_request_fn,
        apply_bot_settings_fn=deps.apply_bot_settings_fn,
        parse_bot_settings_request_fn=deps.parse_bot_settings_request_fn,
        play_standalone_zork_fn=deps.play_standalone_zork_fn,
        parse_standalone_zork_request_fn=deps.parse_standalone_zork_request_fn,
    )
    routes_post.handle_dashboard_post(handler, path="/api/settings/radio", deps=deps_disabled_radio)
    assert json_calls[0]["status_code"] == 503
    assert "Radio settings are not enabled" in json_calls[0]["payload_obj"]["error"]

    deps_disabled_channels = DashboardPostRouteDependencies(
        send_chat_fn=deps.send_chat_fn,
        to_int_fn=deps.to_int_fn,
        validate_content_length_fn=deps.validate_content_length_fn,
        parse_chat_send_request_fn=deps.parse_chat_send_request_fn,
        write_json_response_fn=deps.write_json_response_fn,
        set_theme_preset_fn=deps.set_theme_preset_fn,
        parse_theme_settings_request_fn=deps.parse_theme_settings_request_fn,
        apply_radio_settings_fn=deps.apply_radio_settings_fn,
        parse_radio_settings_request_fn=deps.parse_radio_settings_request_fn,
        apply_channel_settings_fn=deps.apply_channel_settings_fn,
        parse_channel_settings_request_fn=None,
        apply_bot_settings_fn=deps.apply_bot_settings_fn,
        parse_bot_settings_request_fn=deps.parse_bot_settings_request_fn,
        play_standalone_zork_fn=deps.play_standalone_zork_fn,
        parse_standalone_zork_request_fn=deps.parse_standalone_zork_request_fn,
    )
    routes_post.handle_dashboard_post(handler, path="/api/settings/channels", deps=deps_disabled_channels)
    assert json_calls[1]["status_code"] == 503
    assert "Channel settings are not enabled" in json_calls[1]["payload_obj"]["error"]

    deps_disabled_theme = DashboardPostRouteDependencies(
        send_chat_fn=deps.send_chat_fn,
        to_int_fn=deps.to_int_fn,
        validate_content_length_fn=deps.validate_content_length_fn,
        parse_chat_send_request_fn=deps.parse_chat_send_request_fn,
        write_json_response_fn=deps.write_json_response_fn,
        set_theme_preset_fn=deps.set_theme_preset_fn,
        parse_theme_settings_request_fn=None,
        apply_radio_settings_fn=deps.apply_radio_settings_fn,
        parse_radio_settings_request_fn=deps.parse_radio_settings_request_fn,
        apply_channel_settings_fn=deps.apply_channel_settings_fn,
        parse_channel_settings_request_fn=deps.parse_channel_settings_request_fn,
        apply_bot_settings_fn=deps.apply_bot_settings_fn,
        parse_bot_settings_request_fn=deps.parse_bot_settings_request_fn,
        play_standalone_zork_fn=deps.play_standalone_zork_fn,
        parse_standalone_zork_request_fn=deps.parse_standalone_zork_request_fn,
    )
    routes_post.handle_dashboard_post(handler, path="/api/settings/theme", deps=deps_disabled_theme)
    assert json_calls[2]["status_code"] == 503
    assert "Theme settings are not enabled" in json_calls[2]["payload_obj"]["error"]

    deps_disabled_custom = DashboardPostRouteDependencies(
        send_chat_fn=deps.send_chat_fn,
        to_int_fn=deps.to_int_fn,
        validate_content_length_fn=deps.validate_content_length_fn,
        parse_chat_send_request_fn=deps.parse_chat_send_request_fn,
        write_json_response_fn=deps.write_json_response_fn,
        set_theme_preset_fn=deps.set_theme_preset_fn,
        parse_theme_settings_request_fn=deps.parse_theme_settings_request_fn,
        set_custom_telemetry_settings_fn=deps.set_custom_telemetry_settings_fn,
        parse_custom_telemetry_settings_request_fn=None,
        apply_radio_settings_fn=deps.apply_radio_settings_fn,
        parse_radio_settings_request_fn=deps.parse_radio_settings_request_fn,
        apply_channel_settings_fn=deps.apply_channel_settings_fn,
        parse_channel_settings_request_fn=deps.parse_channel_settings_request_fn,
        apply_bot_settings_fn=deps.apply_bot_settings_fn,
        parse_bot_settings_request_fn=deps.parse_bot_settings_request_fn,
        play_standalone_zork_fn=deps.play_standalone_zork_fn,
        parse_standalone_zork_request_fn=deps.parse_standalone_zork_request_fn,
    )
    routes_post.handle_dashboard_post(handler, path="/api/settings/custom_telemetry", deps=deps_disabled_custom)
    assert json_calls[3]["status_code"] == 503
    assert "Custom telemetry settings are not enabled" in json_calls[3]["payload_obj"]["error"]

    deps_disabled_bot = DashboardPostRouteDependencies(
        send_chat_fn=deps.send_chat_fn,
        to_int_fn=deps.to_int_fn,
        validate_content_length_fn=deps.validate_content_length_fn,
        parse_chat_send_request_fn=deps.parse_chat_send_request_fn,
        write_json_response_fn=deps.write_json_response_fn,
        set_theme_preset_fn=deps.set_theme_preset_fn,
        parse_theme_settings_request_fn=deps.parse_theme_settings_request_fn,
        apply_radio_settings_fn=deps.apply_radio_settings_fn,
        parse_radio_settings_request_fn=deps.parse_radio_settings_request_fn,
        apply_channel_settings_fn=deps.apply_channel_settings_fn,
        parse_channel_settings_request_fn=deps.parse_channel_settings_request_fn,
        apply_bot_settings_fn=deps.apply_bot_settings_fn,
        parse_bot_settings_request_fn=None,
        play_standalone_zork_fn=deps.play_standalone_zork_fn,
        parse_standalone_zork_request_fn=deps.parse_standalone_zork_request_fn,
    )
    routes_post.handle_dashboard_post(handler, path="/api/settings/bot", deps=deps_disabled_bot)
    assert json_calls[4]["status_code"] == 503
    assert "Bot settings are not enabled" in json_calls[4]["payload_obj"]["error"]

    deps_disabled_zork = DashboardPostRouteDependencies(
        send_chat_fn=deps.send_chat_fn,
        to_int_fn=deps.to_int_fn,
        validate_content_length_fn=deps.validate_content_length_fn,
        parse_chat_send_request_fn=deps.parse_chat_send_request_fn,
        write_json_response_fn=deps.write_json_response_fn,
        set_theme_preset_fn=deps.set_theme_preset_fn,
        parse_theme_settings_request_fn=deps.parse_theme_settings_request_fn,
        apply_radio_settings_fn=deps.apply_radio_settings_fn,
        parse_radio_settings_request_fn=deps.parse_radio_settings_request_fn,
        apply_channel_settings_fn=deps.apply_channel_settings_fn,
        parse_channel_settings_request_fn=deps.parse_channel_settings_request_fn,
        apply_bot_settings_fn=deps.apply_bot_settings_fn,
        parse_bot_settings_request_fn=deps.parse_bot_settings_request_fn,
        play_standalone_zork_fn=None,
        parse_standalone_zork_request_fn=None,
    )
    routes_post.handle_dashboard_post(handler, path="/api/games/zork", deps=deps_disabled_zork)
    assert json_calls[5]["status_code"] == 503
    assert "Standalone Zork is not enabled" in json_calls[5]["payload_obj"]["error"]


def test_handle_dashboard_post_requires_api_token_for_write_endpoints(monkeypatch):
    json_calls = []
    helper_calls = {"chat": 0, "zork": 0}

    monkeypatch.setattr(
        routes_post,
        "_handle_chat_send_post_helper",
        lambda *_args, **_kwargs: helper_calls.__setitem__("chat", helper_calls["chat"] + 1),
    )
    monkeypatch.setattr(
        routes_post,
        "_handle_standalone_zork_post_helper",
        lambda *_args, **_kwargs: helper_calls.__setitem__("zork", helper_calls["zork"] + 1),
    )

    deps = _build_post_deps(json_calls=json_calls, api_token="secret-token")

    routes_post.handle_dashboard_post(_fake_handler(), path="/api/chat/send", deps=deps)
    assert json_calls[0]["status_code"] == 401
    assert "token required" in json_calls[0]["payload_obj"]["error"].lower()
    assert helper_calls["chat"] == 0

    routes_post.handle_dashboard_post(_fake_handler(), path="/api/games/zork", deps=deps)
    assert json_calls[1]["status_code"] == 401
    assert "token required" in json_calls[1]["payload_obj"]["error"].lower()
    assert helper_calls["zork"] == 0

    routes_post.handle_dashboard_post(_fake_handler(), path="/api/settings/custom_telemetry", deps=deps)
    assert json_calls[2]["status_code"] == 401
    assert "token required" in json_calls[2]["payload_obj"]["error"].lower()

    routes_post.handle_dashboard_post(
        _fake_handler(headers={"Authorization": "Bearer secret-token"}),
        path="/api/chat/send",
        deps=deps,
    )
    assert helper_calls["chat"] == 1

    routes_post.handle_dashboard_post(
        _fake_handler(headers={"Authorization": "Bearer secret-token"}),
        path="/api/games/zork",
        deps=deps,
    )
    assert helper_calls["zork"] == 1

    routes_post.handle_dashboard_post(
        _fake_handler(headers={"Authorization": "Bearer secret-token"}),
        path="/api/settings/custom_telemetry",
        deps=deps,
    )
    assert json_calls[3]["status_code"] == 200


def test_handle_dashboard_post_private_mode_blocks_chat_and_zork():
    json_calls = []
    deps = _build_post_deps(json_calls=json_calls, private_mode=True)

    routes_post.handle_dashboard_post(_fake_handler(), path="/api/chat/send", deps=deps)
    routes_post.handle_dashboard_post(_fake_handler(), path="/api/games/zork", deps=deps)

    assert json_calls[0]["status_code"] == 403
    assert "private mode" in json_calls[0]["payload_obj"]["error"].lower()
    assert json_calls[1]["status_code"] == 403
    assert "private mode" in json_calls[1]["payload_obj"]["error"].lower()
