import io
import json

from meshdash.http_api import make_http_handler


def _run_get(handler_cls, path: str):
    handler = handler_cls.__new__(handler_cls)
    handler.path = path
    handler.headers = {}
    handler.rfile = io.BytesIO()
    handler.wfile = io.BytesIO()
    sent = {"status": None, "headers": []}

    handler.send_response = lambda code: sent.__setitem__("status", code)
    handler.send_header = lambda key, value: sent["headers"].append((key, value))
    handler.end_headers = lambda: None

    handler.do_GET()
    return sent, handler.wfile.getvalue()


def _run_post(handler_cls, path: str, body: dict):
    payload = json.dumps(body).encode("utf-8")
    handler = handler_cls.__new__(handler_cls)
    handler.path = path
    handler.headers = {"Content-Length": str(len(payload))}
    handler.rfile = io.BytesIO(payload)
    handler.wfile = io.BytesIO()
    sent = {"status": None, "headers": []}

    handler.send_response = lambda code: sent.__setitem__("status", code)
    handler.send_header = lambda key, value: sent["headers"].append((key, value))
    handler.end_headers = lambda: None

    handler.do_POST()
    return sent, handler.wfile.getvalue()


def test_http_api_state_and_history_endpoints():
    def _state():
        return {"ok": True, "nodes": 3}

    setattr(
        _state,
        "search_history_packets_fn",
        lambda query_text, **kwargs: {
            "ok": True,
            "query": query_text,
            "entries": [],
            "matches": 0,
            "returned_matches": 0,
            "kwargs": kwargs,
        },
    )

    handler_cls = make_http_handler(
        html_text="<html>ok</html>",
        state_fn=_state,
        node_history_fn=lambda node_id, hours, points: {
            "node_id": node_id,
            "hours": hours,
            "points_req": points,
            "points": [],
            "positions": [],
            "summary": {},
        },
        online_activity_fn=None,
        summary_metrics_fn=lambda hours: {
            "window_hours": hours,
            "points": [{"bucket_unix": 60}],
        },
        send_chat_fn=None,
        default_node_history_hours=72,
    )

    sent, data = _run_get(handler_cls, "/api/state")
    assert sent["status"] == 200
    assert json.loads(data.decode("utf-8"))["ok"] is True

    sent, data = _run_get(handler_cls, "/api/history/node?node_id=!abc123&hours=6&points=50")
    assert sent["status"] == 200
    body = json.loads(data.decode("utf-8"))
    assert body["node_id"] == "!abc123"
    assert body["hours"] == 6
    assert body["points_req"] == 50

    sent, data = _run_get(handler_cls, "/api/history/online?hours=12")
    assert sent["status"] == 200
    online = json.loads(data.decode("utf-8"))
    assert online["window_hours"] == 12
    assert len(online["hourly_profile"]) == 24

    sent, data = _run_get(handler_cls, "/api/history/summary?hours=6")
    assert sent["status"] == 200
    summary = json.loads(data.decode("utf-8"))
    assert summary["window_hours"] == 6
    assert summary["points"][0]["bucket_unix"] == 60

    sent, data = _run_get(
        handler_cls,
        "/api/history/search?q=!3369d0b8&before=1&after=1&scope=both&scan=300",
    )
    assert sent["status"] == 200
    search_payload = json.loads(data.decode("utf-8"))
    assert search_payload["ok"] is True
    assert search_payload["query"] == "!3369d0b8"
    assert search_payload["kwargs"]["before"] == 1
    assert search_payload["kwargs"]["after"] == 1
    assert search_payload["kwargs"]["scope"] == "both"
    assert search_payload["kwargs"]["scan_limit"] == 300


def test_http_api_chat_send_success_and_disabled():
    enabled_handler = make_http_handler(
        html_text="<html>ok</html>",
        state_fn=lambda: {"ok": True},
        send_chat_fn=lambda **kwargs: {"ok": True, "echo": kwargs.get("text", "")},
    )
    sent, data = _run_post(enabled_handler, "/api/chat/send", {"text": "hello"})
    assert sent["status"] == 200
    assert json.loads(data.decode("utf-8"))["echo"] == "hello"

    disabled_handler = make_http_handler(
        html_text="<html>ok</html>",
        state_fn=lambda: {"ok": True},
        send_chat_fn=None,
    )
    sent, data = _run_post(disabled_handler, "/api/chat/send", {"text": "hello"})
    assert sent["status"] == 503
    assert "not enabled" in json.loads(data.decode("utf-8"))["error"].lower()


def test_http_api_standalone_zork_success_and_disabled():
    def _state():
        return {"ok": True}

    setattr(
        _state,
        "play_standalone_zork_fn",
        lambda **_kwargs: {
            "ok": True,
            "session_id": "abc123",
            "reply_text": "West of House.",
            "active_session": True,
        },
    )
    enabled_handler = make_http_handler(
        html_text="<html>ok</html>",
        state_fn=_state,
        send_chat_fn=None,
    )
    sent, data = _run_post(enabled_handler, "/api/games/zork", {"text": "zork"})
    assert sent["status"] == 200
    enabled_body = json.loads(data.decode("utf-8"))
    assert enabled_body["session_id"] == "abc123"
    assert "West of House" in enabled_body["reply_text"]

    disabled_handler = make_http_handler(
        html_text="<html>ok</html>",
        state_fn=lambda: {"ok": True},
        send_chat_fn=None,
    )
    sent, data = _run_post(disabled_handler, "/api/games/zork", {"text": "zork"})
    assert sent["status"] == 503
    assert "standalone zork is not enabled" in json.loads(data.decode("utf-8"))["error"].lower()


def test_http_api_theme_settings_get_and_post():
    selected = {"name": "default"}
    presets = {
        "default": {"light": {"--bg": "#fff"}, "dark": {"--bg": "#000"}},
        "forest": {"light": {"--bg": "#efe"}, "dark": {"--bg": "#131"}},
    }

    def _get_theme_settings():
        return {
            "ok": True,
            "selected_preset": selected["name"],
            "available_presets": ["default", "forest"],
            "presets": presets,
        }

    def _set_theme_preset(preset_name):
        selected["name"] = str(preset_name)
        return _get_theme_settings()

    handler_cls = make_http_handler(
        html_text="<html>ok</html>",
        state_fn=lambda: {"ok": True},
        get_theme_settings_fn=_get_theme_settings,
        set_theme_preset_fn=_set_theme_preset,
    )

    sent, data = _run_get(handler_cls, "/api/settings/theme")
    assert sent["status"] == 200
    body = json.loads(data.decode("utf-8"))
    assert body["selected_preset"] == "default"
    assert "forest" in body["available_presets"]

    sent, data = _run_post(handler_cls, "/api/settings/theme", {"preset_name": "forest"})
    assert sent["status"] == 200
    updated = json.loads(data.decode("utf-8"))
    assert updated["selected_preset"] == "forest"
