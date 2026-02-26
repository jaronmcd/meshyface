import json

from .http_handler_contracts import DashboardHttpHandler


def json_bytes(payload_obj: object) -> bytes:
    return json.dumps(payload_obj, separators=(",", ":")).encode("utf-8")


def write_json_response(
    handler: DashboardHttpHandler,
    *,
    status_code: int,
    payload_obj: object,
    no_store: bool = False,
) -> None:
    payload = json_bytes(payload_obj)
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    if no_store:
        handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def write_html_response(handler: DashboardHttpHandler, *, html_text: str) -> None:
    payload = html_text.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def write_text_response(handler: DashboardHttpHandler, *, status_code: int, text: str) -> None:
    payload = text.encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)
