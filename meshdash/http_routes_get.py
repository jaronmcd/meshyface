from .api_history import (
    build_node_history_response as _build_node_history_response_helper,
    build_online_activity_response as _build_online_activity_response_helper,
    build_summary_metrics_response as _build_summary_metrics_response_helper,
)
from .api_system import (
    handle_state_get as _handle_state_get_helper,
)
from .api_theme import (
    handle_theme_settings_get as _handle_theme_settings_get_helper,
)
from .http_handler_contracts import DashboardHttpHandler
from .http_route_contracts import DashboardGetRouteDependencies


def handle_dashboard_get(
    handler: DashboardHttpHandler,
    *,
    path: str,
    query: str,
    deps: DashboardGetRouteDependencies,
) -> None:
    if path in ("/", "/index.html"):
        deps.write_html_response_fn(handler, html_text=deps.html_text)
        return

    if path == "/api/state":
        _handle_state_get_helper(
            handler,
            query=query,
            state_fn=deps.state_fn,
            write_json_response_fn=deps.write_json_response_fn,
        )
        return

    # Raw/debug payloads are fetched on-demand (Data view) so the primary
    # /api/state polling stays lean.
    if path == "/api/raw/my_info":
        raw_fn = getattr(deps.state_fn, "raw_my_info", None)
        if callable(raw_fn):
            response_obj = raw_fn()
        else:
            snapshot = deps.state_fn()
            response_obj = snapshot.get("my_info") if isinstance(snapshot, dict) else {}
        deps.write_json_response_fn(handler, status_code=200, payload_obj=response_obj, no_store=True)
        return

    if path == "/api/raw/metadata":
        raw_fn = getattr(deps.state_fn, "raw_metadata", None)
        if callable(raw_fn):
            response_obj = raw_fn()
        else:
            snapshot = deps.state_fn()
            response_obj = snapshot.get("metadata") if isinstance(snapshot, dict) else {}
        deps.write_json_response_fn(handler, status_code=200, payload_obj=response_obj, no_store=True)
        return

    if path == "/api/raw/local_state":
        raw_fn = getattr(deps.state_fn, "raw_local_state", None)
        if callable(raw_fn):
            response_obj = raw_fn()
        else:
            snapshot = deps.state_fn()
            response_obj = snapshot.get("local_state") if isinstance(snapshot, dict) else {}
        deps.write_json_response_fn(handler, status_code=200, payload_obj=response_obj, no_store=True)
        return

    if path == "/api/raw/nodes_full":
        raw_fn = getattr(deps.state_fn, "raw_nodes_full", None)
        if callable(raw_fn):
            response_obj = raw_fn()
        else:
            snapshot = deps.state_fn()
            response_obj = snapshot.get("nodes_full") if isinstance(snapshot, dict) else []
        deps.write_json_response_fn(handler, status_code=200, payload_obj=response_obj, no_store=True)
        return

    if path == "/api/settings/theme":
        _handle_theme_settings_get_helper(
            handler,
            get_theme_settings_fn=deps.get_theme_settings_fn,
            write_json_response_fn=deps.write_json_response_fn,
        )
        return

    if path == "/api/history/node":
        response_obj = _build_node_history_response_helper(
            query=query,
            node_history_fn=deps.node_history_fn,
            to_int_fn=deps.to_int_fn,
            parse_node_history_request_fn=deps.parse_node_history_request_fn,
            empty_node_history_fn=deps.empty_node_history_fn,
        )
        deps.write_json_response_fn(handler, status_code=200, payload_obj=response_obj, no_store=True)
        return

    if path == "/api/history/online":
        response_obj = _build_online_activity_response_helper(
            query=query,
            online_activity_fn=deps.online_activity_fn,
            default_node_history_hours=deps.default_node_history_hours,
            to_int_fn=deps.to_int_fn,
            parse_online_activity_request_fn=deps.parse_online_activity_request_fn,
            empty_online_activity_fn=deps.empty_online_activity_fn,
        )
        deps.write_json_response_fn(handler, status_code=200, payload_obj=response_obj, no_store=True)
        return

    if path == "/api/history/summary":
        response_obj = _build_summary_metrics_response_helper(
            query=query,
            summary_metrics_fn=deps.summary_metrics_fn,
            default_node_history_hours=deps.default_node_history_hours,
            to_int_fn=deps.to_int_fn,
            parse_online_activity_request_fn=deps.parse_online_activity_request_fn,
            empty_summary_metrics_fn=deps.empty_summary_metrics_fn,
        )
        deps.write_json_response_fn(handler, status_code=200, payload_obj=response_obj, no_store=True)
        return

    deps.write_text_response_fn(handler, status_code=404, text="Not Found")
