import json
from http.server import BaseHTTPRequestHandler
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from .api_inputs import (
    parse_chat_send_body,
    parse_node_history_query,
    parse_online_activity_query,
    validate_content_length,
)
from .helpers import to_int
from .services import empty_node_history, empty_online_activity


def make_http_handler(
    html_text: str,
    state_fn: Callable[[], dict],
    node_history_fn: Optional[Callable[[str, Optional[int], Optional[int]], dict]] = None,
    online_activity_fn: Optional[Callable[[Optional[int]], dict]] = None,
    send_chat_fn: Optional[Callable[..., dict]] = None,
    default_node_history_hours: int = 72,
    to_int_fn: Callable[[Any], Optional[int]] = to_int,
):
    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            try:
                parsed = urlparse(self.path)
                path = parsed.path

                if path in ("/", "/index.html"):
                    body = html_text.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

                if path == "/api/state":
                    payload = json.dumps(state_fn(), separators=(",", ":")).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return

                if path == "/api/history/node":
                    node_id, hours_override, points_override = parse_node_history_query(
                        parsed.query,
                        to_int_fn=to_int_fn,
                    )
                    if node_history_fn is None:
                        response_obj = empty_node_history(node_id)
                    else:
                        response_obj = node_history_fn(node_id, hours_override, points_override)
                    payload = json.dumps(response_obj, separators=(",", ":")).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return

                if path == "/api/history/online":
                    hours_override = parse_online_activity_query(
                        parsed.query,
                        to_int_fn=to_int_fn,
                    )
                    if online_activity_fn is None:
                        clean_hours = (
                            hours_override
                            if isinstance(hours_override, int) and hours_override > 0
                            else default_node_history_hours
                        )
                        response_obj = empty_online_activity(clean_hours)
                    else:
                        response_obj = online_activity_fn(hours_override)
                    payload = json.dumps(response_obj, separators=(",", ":")).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return

                self.send_response(404)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Not Found")
            except (BrokenPipeError, ConnectionResetError):
                return

        def do_POST(self) -> None:
            try:
                parsed = urlparse(self.path)
                path = parsed.path
                if path != "/api/chat/send":
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b'{"ok":false,"error":"Not Found"}')
                    return

                if send_chat_fn is None:
                    payload = json.dumps(
                        {"ok": False, "error": "Chat send is not enabled on this dashboard instance"},
                        separators=(",", ":"),
                    ).encode("utf-8")
                    self.send_response(503)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return

                try:
                    content_length = validate_content_length(
                        self.headers,
                        to_int_fn=to_int_fn,
                    )
                except ValueError:
                    payload = json.dumps(
                        {"ok": False, "error": "Invalid request size"},
                        separators=(",", ":"),
                    ).encode("utf-8")
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return

                raw = self.rfile.read(content_length)
                chat_request = parse_chat_send_body(raw, to_int_fn=to_int_fn)

                try:
                    response_obj = send_chat_fn(
                        text=chat_request["text"],
                        destination=chat_request["destination"],
                        channel_index=chat_request["channel_index"],
                        reply_id=chat_request["reply_id"],
                        retry_of=chat_request["retry_of"],
                        emoji=chat_request["emoji"],
                    )
                except ValueError as exc:
                    payload = json.dumps(
                        {"ok": False, "error": str(exc)},
                        separators=(",", ":"),
                    ).encode("utf-8")
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                except Exception as exc:
                    payload = json.dumps(
                        {"ok": False, "error": f"Send failed: {exc}"},
                        separators=(",", ":"),
                    ).encode("utf-8")
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return

                payload = json.dumps(response_obj, separators=(",", ":")).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                return

        def log_message(self, format: str, *args: Any) -> None:
            return

    return DashboardHandler
