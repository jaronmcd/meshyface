from typing import Any, Callable, Optional
from urllib.parse import urlparse

from .api_inputs import (
    parse_chat_send_body,
    parse_node_history_query,
    parse_online_activity_query,
    validate_content_length,
)
from .helpers import to_int
from .http_handler import build_dashboard_handler_class
from .http_responses import write_html_response, write_json_response, write_text_response
from .http_routes import handle_dashboard_get, handle_dashboard_post
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
    def _dispatch_get(handler: Any) -> None:
        parsed = urlparse(handler.path)
        handle_dashboard_get(
            handler,
            path=parsed.path,
            query=parsed.query,
            html_text=html_text,
            state_fn=state_fn,
            node_history_fn=node_history_fn,
            online_activity_fn=online_activity_fn,
            default_node_history_hours=default_node_history_hours,
            to_int_fn=to_int_fn,
            parse_node_history_query_fn=parse_node_history_query,
            parse_online_activity_query_fn=parse_online_activity_query,
            empty_node_history_fn=empty_node_history,
            empty_online_activity_fn=empty_online_activity,
            write_html_response_fn=write_html_response,
            write_json_response_fn=write_json_response,
            write_text_response_fn=write_text_response,
        )

    def _dispatch_post(handler: Any) -> None:
        parsed = urlparse(handler.path)
        handle_dashboard_post(
            handler,
            path=parsed.path,
            send_chat_fn=send_chat_fn,
            to_int_fn=to_int_fn,
            validate_content_length_fn=validate_content_length,
            parse_chat_send_body_fn=parse_chat_send_body,
            write_json_response_fn=write_json_response,
        )

    return build_dashboard_handler_class(
        dispatch_get_fn=_dispatch_get,
        dispatch_post_fn=_dispatch_post,
    )
