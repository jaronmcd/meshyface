from http.server import BaseHTTPRequestHandler
from typing import Callable

from .http_handler_contracts import DashboardHttpHandler


def build_dashboard_handler_class(
    *,
    dispatch_get_fn: Callable[[DashboardHttpHandler], None],
    dispatch_post_fn: Callable[[DashboardHttpHandler], None],
) -> type[BaseHTTPRequestHandler]:
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

        def log_message(self, format: str, *args: object) -> None:
            return

    return DashboardHandler
