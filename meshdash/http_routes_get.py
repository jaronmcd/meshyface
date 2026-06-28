from collections.abc import Mapping
from importlib import import_module
import os
from pathlib import Path
from urllib.parse import parse_qs

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
from .api_history_chat import (
    build_chat_history_response as _build_chat_history_response_helper,
)
from .api_system import (
    handle_state_get as _handle_state_get_helper,
)
from .api_system_update import (
    build_update_status_payload as _build_update_status_payload_helper,
    refresh_update_status_from_github as _refresh_update_status_from_github_helper,
)
from .api_theme import (
    handle_theme_settings_get as _handle_theme_settings_get_helper,
)
from .http_handler_contracts import DashboardHttpHandler
from .http_route_contracts import DashboardGetRouteDependencies
from .http_responses import _gzip_if_accepted, _send_no_store_headers
from .offline_atlas import load_offline_atlas_payload as _load_offline_atlas_payload_helper
from .helpers import to_int as _to_int_helper


def _load_optional_handler(module_path: str, attr_name: str):
    try:
        module = import_module(module_path, package=__package__)
    except Exception:
        return None
    value = getattr(module, attr_name, None)
    if callable(value):
        return value
    return None


_handle_custom_telemetry_settings_get_helper = _load_optional_handler(
    ".api_custom_telemetry",
    "handle_custom_telemetry_settings_get",
)
_handle_bbs_settings_get_helper = _load_optional_handler(
    ".api_bbs",
    "handle_bbs_settings_get",
)
_handle_bbs_host_get_helper = _load_optional_handler(
    ".api_bbs",
    "handle_bbs_host_get",
)

_VENDOR_ASSETS_DIR = Path(__file__).with_name("assets") / "vendor"
_VENDOR_ASSETS: Mapping[str, tuple[str, str]] = {
    "/assets/vendor/leaflet-1.9.4.css": ("leaflet-1.9.4.css", "text/css; charset=utf-8"),
    "/assets/vendor/leaflet-1.9.4.js": ("leaflet-1.9.4.js", "application/javascript; charset=utf-8"),
    "/assets/vendor/leaflet-heat-0.2.0.js": ("leaflet-heat-0.2.0.js", "application/javascript; charset=utf-8"),
    "/assets/vendor/images/layers.png": ("images/layers.png", "image/png"),
    "/assets/vendor/images/layers-2x.png": ("images/layers-2x.png", "image/png"),
    "/assets/vendor/images/marker-icon.png": ("images/marker-icon.png", "image/png"),
    "/assets/vendor/images/marker-icon-2x.png": ("images/marker-icon-2x.png", "image/png"),
    "/assets/vendor/images/marker-shadow.png": ("images/marker-shadow.png", "image/png"),
}


def _write_vendor_asset_response(
    handler: DashboardHttpHandler,
    *,
    path: str,
) -> bool:
    asset = _VENDOR_ASSETS.get(path)
    if asset is None:
        return False
    filename, content_type = asset
    try:
        payload = (_VENDOR_ASSETS_DIR / filename).read_bytes()
    except OSError:
        handler.send_response(404)
        handler.send_header("Content-Type", "text/plain; charset=utf-8")
        _send_no_store_headers(handler)
        handler.send_header("Content-Length", "9")
        handler.end_headers()
        handler.wfile.write(b"Not Found")
        return True

    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Cache-Control", "public, max-age=86400")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)
    return True


def _write_dashboard_asset_response(
    handler: DashboardHttpHandler,
    *,
    path: str,
    deps: DashboardGetRouteDependencies,
) -> bool:
    asset_map = getattr(deps, "dashboard_asset_map", None) or {}
    asset = asset_map.get(path) if hasattr(asset_map, "get") else None
    if asset is None:
        return False
    content_type, raw_payload = asset
    payload = bytes(raw_payload)
    payload, content_encoding = _gzip_if_accepted(handler, payload)
    handler.send_response(200)
    handler.send_header("Content-Type", str(content_type))
    handler.send_header("Cache-Control", "public, max-age=31536000, immutable")
    handler.send_header("X-Content-Type-Options", "nosniff")
    if content_encoding:
        handler.send_header("Content-Encoding", content_encoding)
        handler.send_header("Vary", "Accept-Encoding")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)
    return True


def _download_filename_token(value: object, fallback: str) -> str:
    clean = "".join(
        ch if ch.isalnum() or ch in "._-" else "_"
        for ch in str(value or "").strip()
    ).strip("._")
    return clean or fallback


def _write_binary_download_response(
    handler: DashboardHttpHandler,
    *,
    payload: bytes,
    filename: object,
    content_type: object,
) -> None:
    safe_filename = _download_filename_token(filename, "download.bin")
    handler.send_response(200)
    handler.send_header("Content-Type", str(content_type or "application/octet-stream"))
    _send_no_store_headers(handler)
    handler.send_header("Content-Disposition", f'attachment; filename="{safe_filename}"')
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


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


def _clean_top_nodes_excluded_node_id(value: object) -> str:
    return str(value or "").strip()


def _query_branch_value(query: str) -> str:
    try:
        query_obj = parse_qs(query or "")
    except Exception:
        return ""
    return str(
        query_obj.get("branch", [""])[0]
        or query_obj.get("target_branch", [""])[0]
        or ""
    ).strip()


def _query_refresh_requested(query: str) -> bool:
    try:
        query_obj = parse_qs(query or "")
    except Exception:
        return False
    value = str(
        query_obj.get("refresh", [""])[0]
        or query_obj.get("fetch", [""])[0]
        or ""
    ).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _mapping_value(root: Mapping[str, object], *keys: str) -> object:
    for key in keys:
        if key in root:
            return root.get(key)
    return None


def _top_nodes_excluded_local_node_ids(state_fn: object) -> list[str]:
    try:
        snapshot = _state_snapshot_for_ops(state_fn)
    except Exception:
        snapshot = {}
    if not isinstance(snapshot, Mapping):
        return []

    candidates: list[object] = [
        _mapping_value(snapshot, "local_node_id", "localNodeId"),
    ]
    my_info = _mapping_value(snapshot, "my_info", "myInfo")
    if isinstance(my_info, Mapping):
        candidates.append(_mapping_value(my_info, "id", "node_id", "nodeId"))
    local_state = _mapping_value(snapshot, "local_state", "localState")
    if isinstance(local_state, Mapping):
        local_node_info = _mapping_value(local_state, "local_node_info", "localNodeInfo")
        if isinstance(local_node_info, Mapping):
            user = _mapping_value(local_node_info, "user")
            if isinstance(user, Mapping):
                candidates.append(_mapping_value(user, "id", "node_id", "nodeId"))

    seen: set[str] = set()
    excluded: list[str] = []
    for candidate in candidates:
        clean = _clean_top_nodes_excluded_node_id(candidate)
        if not clean or clean.lower() in seen:
            continue
        seen.add(clean.lower())
        excluded.append(clean)
    return excluded


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
    deploy_payload_hash = str(os.environ.get("MESH_DASH_DEPLOY_PAYLOAD_HASH") or "").strip()
    return {
        "ok": True,
        "version": version,
        "commit": commit,
        "label": label,
        "title": title,
        "deploy_payload_hash": deploy_payload_hash or None,
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

    if _write_dashboard_asset_response(handler, path=path, deps=deps):
        return

    if _write_vendor_asset_response(handler, path=path):
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
            no_store=True,
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

    if path == "/api/bbs/host":
        if not callable(_handle_bbs_host_get_helper):
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={"ok": False, "error": "BBS host runtime is not enabled on this dashboard instance"},
            )
            return
        _handle_bbs_host_get_helper(
            handler,
            get_bbs_host_runtime_fn=deps.get_bbs_host_runtime_fn,
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

    if path == "/api/system/database":
        database_stats_fn = getattr(deps.state_fn, "database_stats_fn", None)
        if callable(database_stats_fn):
            try:
                response_obj = database_stats_fn()
            except Exception as exc:
                response_obj = {
                    "ok": False,
                    "enabled": True,
                    "error": str(exc or "database stats failed"),
                }
        else:
            response_obj = {
                "ok": False,
                "enabled": False,
                "error": "history database unavailable on this dashboard instance",
            }
        deps.write_json_response_fn(handler, status_code=200, payload_obj=response_obj, no_store=True)
        return

    if path == "/api/system/database/raw_packets/download":
        download_fn = getattr(deps.state_fn, "raw_packet_database_download_fn", None)
        if not callable(download_fn):
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={"ok": False, "error": "raw packet database unavailable on this dashboard instance"},
                no_store=True,
            )
            return
        try:
            response_obj = download_fn()
        except Exception as exc:
            deps.write_json_response_fn(
                handler,
                status_code=500,
                payload_obj={"ok": False, "error": str(exc or "raw packet database download failed")},
                no_store=True,
            )
            return
        if not isinstance(response_obj, Mapping) or not bool(response_obj.get("ok")):
            status_code = _to_int_helper(response_obj.get("status_code")) if isinstance(response_obj, Mapping) else None
            error = response_obj.get("error") if isinstance(response_obj, Mapping) else None
            deps.write_json_response_fn(
                handler,
                status_code=status_code or 503,
                payload_obj={"ok": False, "error": str(error or "raw packet database download failed")},
                no_store=True,
            )
            return
        raw_payload = response_obj.get("bytes")
        if not isinstance(raw_payload, (bytes, bytearray, memoryview)):
            deps.write_json_response_fn(
                handler,
                status_code=500,
                payload_obj={"ok": False, "error": "raw packet database download payload is invalid"},
                no_store=True,
            )
            return
        _write_binary_download_response(
            handler,
            payload=bytes(raw_payload),
            filename=response_obj.get("filename") or "meshdash_raw_packets.sqlite3",
            content_type=response_obj.get("content_type") or "application/vnd.sqlite3",
        )
        return

    if path == "/api/system/update":
        try:
            target_branch = _query_branch_value(query)
            if _query_refresh_requested(query):
                response_obj = _refresh_update_status_from_github_helper(
                    target_branch=target_branch,
                )
            else:
                response_obj = _build_update_status_payload_helper(
                    target_branch=target_branch,
                )
        except Exception as exc:
            response_obj = {
                "ok": False,
                "available": False,
                "state": "error",
                "can_update": False,
                "update_needed": False,
                "error": str(exc or "update status failed"),
                "message": "Software update status could not be checked.",
            }
        deps.write_json_response_fn(handler, status_code=200, payload_obj=response_obj, no_store=True)
        return

    if path == "/api/settings/theme":
        _handle_theme_settings_get_helper(
            handler,
            get_theme_settings_fn=deps.get_theme_settings_fn,
            write_json_response_fn=deps.write_json_response_fn,
        )
        return

    if path == "/api/settings/bbs":
        if not callable(_handle_bbs_settings_get_helper):
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={"ok": False, "error": "BBS settings are not enabled on this dashboard instance"},
            )
            return
        _handle_bbs_settings_get_helper(
            handler,
            get_bbs_settings_fn=deps.get_bbs_settings_fn,
            write_json_response_fn=deps.write_json_response_fn,
        )
        return

    if path == "/api/settings/custom_telemetry":
        if not callable(_handle_custom_telemetry_settings_get_helper):
            deps.write_json_response_fn(
                handler,
                status_code=503,
                payload_obj={
                    "ok": False,
                    "error": "Custom telemetry settings are not enabled on this dashboard instance",
                },
            )
            return
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

    if path == "/api/history/chat":
        if deps.private_mode:
            _record_private_mode_block(deps)
            deps.write_json_response_fn(
                handler,
                status_code=403,
                payload_obj={"ok": False, "error": "Chat history is disabled in private mode"},
                no_store=True,
            )
            return
        query_obj = parse_qs(query or "")
        chat_history_fn = getattr(deps.state_fn, "chat_history_fn", None)
        try:
            response_obj = _build_chat_history_response_helper(
                query_obj=query_obj,
                chat_history_fn=chat_history_fn,
                to_int_fn=deps.to_int_fn,
            )
        except Exception as exc:
            response_obj = {
                "ok": False,
                "enabled": True,
                "error": str(exc or "chat history failed"),
                "messages": [],
                "count": 0,
                "has_more": False,
            }
        deps.write_json_response_fn(handler, status_code=200, payload_obj=response_obj, no_store=True)
        return

    if path == "/api/history/top_nodes":
        query_obj = parse_qs(query or "")
        category = str(
            query_obj.get("category", [""])[0]
            or query_obj.get("cat", [""])[0]
            or "saved_packets"
        ).strip()
        limit = deps.to_int_fn(query_obj.get("limit", [""])[0])
        top_nodes_fn = getattr(deps.state_fn, "top_nodes_fn", None)
        if callable(top_nodes_fn):
            try:
                response_obj = top_nodes_fn(
                    category=category or "saved_packets",
                    limit=limit or 10,
                    exclude_node_ids=_top_nodes_excluded_local_node_ids(deps.state_fn),
                )
            except Exception as exc:
                response_obj = {
                    "ok": False,
                    "error": str(exc or "top nodes failed"),
                    "category": category or "saved_packets",
                    "items": [],
                }
        else:
            response_obj = {
                "ok": False,
                "error": "top nodes history unavailable on this node",
                "category": category or "saved_packets",
                "items": [],
            }
        deps.write_json_response_fn(handler, status_code=200, payload_obj=response_obj, no_store=True)
        return

    if path == "/api/history/links":
        query_obj = parse_qs(query or "")
        window = str(
            query_obj.get("window", [""])[0]
            or query_obj.get("range", [""])[0]
            or query_obj.get("mode", [""])[0]
            or "7d"
        ).strip()
        limit = deps.to_int_fn(query_obj.get("limit", [""])[0])
        link_edges_fn = getattr(deps.state_fn, "link_edges_fn", None)
        if callable(link_edges_fn):
            try:
                response_obj = link_edges_fn(
                    window=window or "7d",
                    limit=limit or 1200,
                )
            except Exception as exc:
                response_obj = {
                    "ok": False,
                    "error": str(exc or "link history failed"),
                    "window": window or "7d",
                    "edges": [],
                }
        else:
            response_obj = {
                "ok": False,
                "error": "link history unavailable on this node",
                "window": window or "7d",
                "edges": [],
            }
        deps.write_json_response_fn(handler, status_code=200, payload_obj=response_obj, no_store=True)
        return

    if path == "/api/history/location_estimates":
        query_obj = parse_qs(query or "")
        window = str(
            query_obj.get("window", [""])[0]
            or query_obj.get("range", [""])[0]
            or query_obj.get("mode", [""])[0]
            or "72h"
        ).strip()
        limit = deps.to_int_fn(query_obj.get("limit", [""])[0])
        location_estimates_fn = getattr(deps.state_fn, "location_estimates_fn", None)
        if callable(location_estimates_fn):
            try:
                response_obj = location_estimates_fn(
                    window=window or "72h",
                    limit=limit or 600,
                )
            except Exception as exc:
                response_obj = {
                    "ok": False,
                    "error": str(exc or "location estimates failed"),
                    "window": window or "72h",
                    "estimates": [],
                }
        else:
            response_obj = {
                "ok": False,
                "error": "location estimates unavailable on this node",
                "window": window or "72h",
                "estimates": [],
            }
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
        gap_scan_raw = str(
            query_obj.get("include_gap_scan", [""])[0]
            or query_obj.get("gap_scan", [""])[0]
            or query_obj.get("gap", [""])[0]
            or ""
        ).strip().lower()
        include_gap_scan = gap_scan_raw not in {"0", "false", "no", "off", "skip"}
        environment_history_fn = getattr(deps.state_fn, "environment_metrics_history_fn", None)
        if callable(environment_history_fn):
            try:
                response_obj = environment_history_fn(
                    window_hours=hours_override,
                    metric=metric or None,
                    node_id=node_id or None,
                    limit=limit,
                    include_gap_scan=include_gap_scan,
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
                        "include_gap_scan": include_gap_scan,
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
                    "include_gap_scan": include_gap_scan,
                },
                "points": [],
                "metrics": [],
                "nodes": [],
            }
        deps.write_json_response_fn(handler, status_code=200, payload_obj=response_obj, no_store=True)
        return

    if path == "/api/history/malformed":
        query_obj = parse_qs(query or "")
        hours_override = deps.to_int_fn(
            query_obj.get("hours", [""])[0]
            or query_obj.get("window", [""])[0]
        )
        limit = deps.to_int_fn(
            query_obj.get("limit", [""])[0]
            or query_obj.get("scan", [""])[0]
            or query_obj.get("n", [""])[0]
        )
        node_id = str(
            query_obj.get("node_id", [""])[0]
            or query_obj.get("node", [""])[0]
            or query_obj.get("from_id", [""])[0]
            or ""
        ).strip()
        malformed_history_fn = getattr(deps.state_fn, "malformed_text_history_fn", None)
        if callable(malformed_history_fn):
            try:
                response_obj = malformed_history_fn(
                    window_hours=hours_override,
                    node_id=node_id or None,
                    limit=limit,
                )
            except Exception as exc:
                response_obj = {
                    "ok": False,
                    "error": str(exc or "malformed history failed"),
                    "window_hours": hours_override,
                    "limit": limit,
                    "node_id": node_id,
                    "summary": {
                        "total_packets": 0,
                        "distinct_senders": 0,
                        "first_seen_unix": None,
                        "last_seen_unix": None,
                    },
                    "senders": [],
                    "entries": [],
                }
        else:
            response_obj = {
                "ok": False,
                "error": "malformed text history unavailable on this node",
                "window_hours": hours_override,
                "limit": limit,
                "node_id": node_id,
                "summary": {
                    "total_packets": 0,
                    "distinct_senders": 0,
                    "first_seen_unix": None,
                    "last_seen_unix": None,
                },
                "senders": [],
                "entries": [],
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
