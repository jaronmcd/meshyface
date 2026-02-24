from http.server import BaseHTTPRequestHandler
from typing import Any, Callable


def build_dashboard_handler_class(
    *,
    dispatch_get_fn: Callable[[Any], None],
    dispatch_post_fn: Callable[[Any], None],
) -> Any:
    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            try:
                dispatch_get_fn(self)
            except (BrokenPipeError, ConnectionResetError):
                return

        def do_POST(self) -> None:
            try:
                dispatch_post_fn(self)
            except (BrokenPipeError, ConnectionResetError):
                return

        def log_message(self, format: str, *args: Any) -> None:
            return

    return DashboardHandler
