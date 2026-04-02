from urllib.parse import parse_qs
from collections.abc import Mapping

from .api_metrics import (
    build_prometheus_metrics_text as _build_prometheus_metrics_text_helper,
    derive_live_packet_count as _derive_live_packet_count_helper,
    derive_node_count as _derive_node_count_helper,
    derive_radio_link_up as _derive_radio_link_up_helper,
)
from .emoji_catalog import (
    load_chat_emoji_catalog_payload as _load_chat_emoji_catalog_payload_helper,
)
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
from .api_custom_telemetry import (
    handle_custom_telemetry_settings_get as _handle_custom_telemetry_settings_get_helper,
)
from .http_handler_contracts import DashboardHttpHandler
from .http_route_contracts import DashboardGetRouteDependencies
from .offline_atlas import load_offline_atlas_payload as _load_offline_atlas_payload_helper
from .helpers import to_int as _to_int_helper


def _record_state_poll_request(deps: DashboardGetRouteDependencies) -> None:
    metrics = deps.api_metrics
    record_fn = getattr(metrics, "record_state_poll_request", None)
    if callable(record_fn):
        record_fn()


def _record_state_poll_error(deps: DashboardGetRouteDependencies) -> None:
    metrics = deps.api_metrics
    record_fn = getattr(metrics, "record_state_poll_error", None)
    if callable(record_fn):
        record_fn()


def _record_private_mode_block(deps: DashboardGetRouteDependencies) -> None:
    metrics = deps.api_metrics
    record_fn = getattr(metrics, "record_private_mode_block", None)
    if callable(record_fn):
        record_fn()


def _state_snapshot_for_ops(state_fn: object) -> object:
    lite_fn = getattr(state_fn, "lite", None)
    if callable(lite_fn):
        return lite_fn()
    if callable(state_fn):
        return state_fn()
    return {}


def _summary_from_state_payload(payload: object) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        return {}
    summary = payload.get("summary")
    if isinstance(summary, Mapping):
        return summary
    return {}


def _build_version_payload(state_payload: object) -> dict[str, object]:
    summary = _summary_from_state_payload(state_payload)
    revision = summary.get("revision") if isinstance(summary, Mapping) else None
    revision_map = revision if isinstance(revision, Mapping) else {}
    version = str(revision_map.get("version") or "0.0.0")
    commit = str(revision_map.get("commit") or "nogit")
    label = str(revision_map.get("label") or f"Rev: v{version} ({commit})")
    title = str(
        revision_map.get("title")
        or f"Dashboard revision: version {version}, commit {commit}"
    )
    return {
        "ok": True,
        "version": version,
        "commit": commit,
        "label": label,
        "title": title,
    }


def _build_health_payload(state_payload: object) -> dict[str, object]:
    summary = _summary_from_state_payload(state_payload)
    tracker_error = ""
    summary_error = ""
    generated_at = None
    if isinstance(state_payload, Mapping):
        tracker_error = str(state_payload.get("tracker_error") or "").strip()
        summary_error = str(state_payload.get("summary_error") or "").strip()
        generated_at = state_payload.get("generated_at")

    status = "ok"
    if tracker_error or summary_error:
        status = "degraded"

    return {
        "ok": True,
        "status": status,
        "generated_at": generated_at,
        "uptime_seconds": int(_to_int_helper(summary.get("uptime_seconds")) or 0),
        "node_count": _derive_node_count_helper(state_payload),
        "live_packet_count": _derive_live_packet_count_helper(state_payload),
        "radio_link_up": _derive_radio_link_up_helper(state_payload),
        "tracker_error": tracker_error or None,
        "summary_error": summary_error or None,
    }


def handle_dashboard_get(
    handler: DashboardHttpHandler,
    *,
    path: str,
    query: str,
    deps: DashboardGetRouteDependencies,
) -> None:
    if path in ("/", "/index.html"):
        deps.write_html_response_fn(handler, html_text=deps.html_text, no_store=True)
        return

    if path == "/api/version":
        try:
            state_payload = _state_snapshot_for_ops(deps.state_fn)
            payload = _build_version_payload(state_payload)
            deps.write_json_response_fn(handler, status_code=200, payload_obj=payload, no_store=True)
        except Exception as exc:
            deps.write_json_response_fn(
                handler,
                status_code=500,
                payload_obj={"ok": False, "error": f"version check failed: {exc}"},
                no_store=True,
            )
        return

    if path == "/api/health":
        try:
            state_payload = _state_snapshot_for_ops(deps.state_fn)
            payload = _build_health_payload(state_payload)
            deps.write_json_response_fn(handler, status_code=200, payload_obj=payload, no_store=True)
        except Exception as exc:
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={"ok": False, "status": "error", "error": f"health check failed: {exc}"},
                no_store=True,
            )
        return

    if path == "/metrics":
        state_payload = {}
        try:
            state_payload = _state_snapshot_for_ops(deps.state_fn)
        except Exception:
            state_payload = {}
        counter_snapshot = None
        if deps.api_metrics is not None:
            snapshot_fn = getattr(deps.api_metrics, "snapshot", None)
            if callable(snapshot_fn):
                counter_snapshot = snapshot_fn()
        metrics_text = _build_prometheus_metrics_text_helper(
            state_payload=state_payload,
            counters=counter_snapshot,
        )
        deps.write_text_response_fn(
            handler,
            status_code=200,
            text=metrics_text,
            extra_headers={"Cache-Control": "no-store"},
        )
        return

    if path == "/api/state":
        _record_state_poll_request(deps)
        try:
            _handle_state_get_helper(
                handler,
                query=query,
                state_fn=deps.state_fn,
                write_json_response_fn=deps.write_json_response_fn,
                private_mode=deps.private_mode,
            )
        except Exception as exc:
            _record_state_poll_error(deps)
            deps.write_json_response_fn(
                handler,
                status_code=500,
                payload_obj={"ok": False, "error": f"state poll failed: {exc}"},
                no_store=True,
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

    if path == "/api/settings/custom_telemetry":
        _handle_custom_telemetry_settings_get_helper(
            handler,
            get_custom_telemetry_settings_fn=deps.get_custom_telemetry_settings_fn,
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

    if path == "/api/history/environment":
        query_obj = parse_qs(query or "")
        hours_override = deps.to_int_fn(
            query_obj.get("hours", [""])[0]
        )
        limit = deps.to_int_fn(
            query_obj.get("limit", [""])[0]
            or query_obj.get("scan", [""])[0]
        )
        metric = str(query_obj.get("metric", [""])[0] or "").strip()
        node_id = str(
            query_obj.get("node_id", [""])[0]
            or query_obj.get("node", [""])[0]
            or ""
        ).strip()
        environment_history_fn = getattr(deps.state_fn, "environment_metrics_history_fn", None)
        if callable(environment_history_fn):
            try:
                response_obj = environment_history_fn(
                    window_hours=hours_override,
                    metric=metric or None,
                    node_id=node_id or None,
                    limit=limit,
                )
            except Exception as exc:
                response_obj = {
                    "ok": False,
                    "error": str(exc or "environment history failed"),
                    "window_hours": hours_override,
                    "query": {
                        "metric": metric,
                        "node_id": node_id,
                        "limit": limit,
                    },
                    "points": [],
                    "metrics": [],
                    "nodes": [],
                }
        else:
            response_obj = {
                "ok": False,
                "error": "environment history unavailable on this node",
                "window_hours": hours_override,
                "query": {
                    "metric": metric,
                    "node_id": node_id,
                    "limit": limit,
                },
                "points": [],
                "metrics": [],
                "nodes": [],
            }
        deps.write_json_response_fn(handler, status_code=200, payload_obj=response_obj, no_store=True)
        return

    if path == "/api/history/search":
        if deps.private_mode:
            _record_private_mode_block(deps)
            deps.write_json_response_fn(
                handler,
                status_code=403,
                payload_obj={"ok": False, "error": "History search is disabled in private mode"},
                no_store=True,
            )
            return
        query_obj = parse_qs(query or "")
        query_text = str(
            query_obj.get("q", [""])[0]
            or query_obj.get("needle", [""])[0]
            or ""
        ).strip()
        limit = deps.to_int_fn(query_obj.get("limit", [""])[0])
        before = deps.to_int_fn(
            query_obj.get("before", [""])[0]
            or query_obj.get("b", [""])[0]
        )
        after = deps.to_int_fn(
            query_obj.get("after", [""])[0]
            or query_obj.get("a", [""])[0]
        )
        context = deps.to_int_fn(
            query_obj.get("context", [""])[0]
            or query_obj.get("c", [""])[0]
        )
        if isinstance(context, int) and context > 0:
            before = max(before or 0, context)
            after = max(after or 0, context)
        scope = str(query_obj.get("scope", ["both"])[0] or "both").strip().lower() or "both"
        source = str(
            query_obj.get("source", [""])[0]
            or query_obj.get("src", [""])[0]
            or ""
        ).strip().lower()
        scan_limit = deps.to_int_fn(
            query_obj.get("scan", [""])[0]
            or query_obj.get("scan_limit", [""])[0]
        )
        search_fn = getattr(deps.state_fn, "search_history_packets_fn", None)
        if not query_text:
            response_obj = {
                "ok": False,
                "error": "missing query text",
                "query": "",
                "entries": [],
                "matches": 0,
                "returned_matches": 0,
            }
        elif callable(search_fn):
            try:
                search_kwargs = {
                    "limit": limit,
                    "before": before,
                    "after": after,
                    "scope": scope,
                    "scan_limit": scan_limit,
                }
                if source:
                    search_kwargs["source"] = source
                response_obj = search_fn(query_text, **search_kwargs)
            except Exception as exc:
                response_obj = {
                    "ok": False,
                    "error": str(exc or "history search failed"),
                    "query": query_text,
                    "entries": [],
                    "matches": 0,
                    "returned_matches": 0,
                }
        else:
            response_obj = {
                "ok": False,
                "error": "history search unavailable on this node",
                "query": query_text,
                "entries": [],
                "matches": 0,
                "returned_matches": 0,
            }
        deps.write_json_response_fn(handler, status_code=200, payload_obj=response_obj, no_store=True)
        return

    if path == "/api/offline/atlas":
        deps.write_json_response_fn(
            handler,
            status_code=200,
            payload_obj=_load_offline_atlas_payload_helper(),
            no_store=False,
        )
        return

    if path == "/api/chat/emoji-catalog":
        if deps.private_mode:
            _record_private_mode_block(deps)
            deps.write_text_response_fn(handler, status_code=404, text="Not Found")
            return
        deps.write_json_response_fn(
            handler,
            status_code=200,
            payload_obj=_load_chat_emoji_catalog_payload_helper(),
            no_store=False,
        )
        return

    deps.write_text_response_fn(handler, status_code=404, text="Not Found")
