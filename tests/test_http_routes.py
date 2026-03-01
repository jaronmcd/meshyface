import io

from meshdash.api_inputs import (
    ChatSendRequest,
    NodeHistoryQuery,
    OnlineActivityQuery,
    ThemeSettingsRequest,
)
from meshdash.http_route_contracts import (
    DashboardGetRouteDependencies,
    DashboardPostRouteDependencies,
)
from meshdash.http_routes import handle_dashboard_get, handle_dashboard_post


def _fake_handler():
    class _H:
        headers = {}
        rfile = io.BytesIO()

    return _H()


def test_handle_dashboard_get_returns_state_and_404():
    handler = _fake_handler()
    calls = {"json": [], "text": []}
    deps = DashboardGetRouteDependencies(
        html_text="<html></html>",
        state_fn=lambda: {"ok": True},
        node_history_fn=None,
        online_activity_fn=None,
        summary_metrics_fn=None,
        default_node_history_hours=72,
        to_int_fn=lambda value: int(value) if value else None,
        parse_node_history_request_fn=lambda *_args, **_kwargs: NodeHistoryQuery(
            node_id="",
            hours_override=None,
            points_override=None,
        ),
        parse_online_activity_request_fn=lambda *_args, **_kwargs: OnlineActivityQuery(hours_override=6),
        empty_node_history_fn=lambda node_id: {"node_id": node_id},
        empty_online_activity_fn=lambda hours: {"window_hours": hours},
        empty_summary_metrics_fn=lambda hours: {"window_hours": hours, "points": []},
        write_html_response_fn=lambda *_args, **_kwargs: None,
        write_json_response_fn=lambda *_args, **kwargs: calls["json"].append(kwargs),
        write_text_response_fn=lambda *_args, **kwargs: calls["text"].append(kwargs),
        get_theme_settings_fn=lambda: {"ok": True, "selected_preset": "default"},
    )

    handle_dashboard_get(
        handler,
        path="/api/state",
        query="",
        deps=deps,
    )
    assert calls["json"][0]["status_code"] == 200
    assert calls["json"][0]["payload_obj"]["ok"] is True

    handle_dashboard_get(
        handler,
        path="/api/settings/theme",
        query="",
        deps=deps,
    )
    assert calls["json"][1]["status_code"] == 200
    assert calls["json"][1]["payload_obj"]["selected_preset"] == "default"

    handle_dashboard_get(
        handler,
        path="/api/history/summary",
        query="hours=6",
        deps=deps,
    )
    assert calls["json"][2]["status_code"] == 200
    assert calls["json"][2]["payload_obj"]["window_hours"] == 6

    handle_dashboard_get(
        handler,
        path="/not-found",
        query="",
        deps=deps,
    )
    assert calls["text"][0]["status_code"] == 404


def test_handle_dashboard_post_handles_disabled_and_success():
    handler = _fake_handler()
    handler.rfile = io.BytesIO(b"{}")
    handler.headers = {"Content-Length": "2"}
    calls = {"json": []}

    disabled_deps = DashboardPostRouteDependencies(
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
        write_json_response_fn=lambda *_args, **kwargs: calls["json"].append(kwargs),
    )
    handle_dashboard_post(
        handler,
        path="/api/chat/send",
        deps=disabled_deps,
    )
    assert calls["json"][0]["status_code"] == 503

    enabled_deps = DashboardPostRouteDependencies(
        send_chat_fn=lambda **_kwargs: {"ok": True},
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
        write_json_response_fn=lambda *_args, **kwargs: calls["json"].append(kwargs),
    )
    handle_dashboard_post(
        handler,
        path="/api/chat/send",
        deps=enabled_deps,
    )
    assert calls["json"][1]["status_code"] == 200
    assert calls["json"][1]["payload_obj"]["ok"] is True

    theme_deps = DashboardPostRouteDependencies(
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
        write_json_response_fn=lambda *_args, **kwargs: calls["json"].append(kwargs),
        set_theme_preset_fn=lambda preset_name: {"ok": True, "selected_preset": str(preset_name)},
        parse_theme_settings_request_fn=lambda _raw: ThemeSettingsRequest(preset_name="forest"),
    )
    handle_dashboard_post(
        handler,
        path="/api/settings/theme",
        deps=theme_deps,
    )
    assert calls["json"][2]["status_code"] == 200
    assert calls["json"][2]["payload_obj"]["selected_preset"] == "forest"
