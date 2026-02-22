import argparse
import json
import os
from typing import Any, Dict, Optional

try:
    import meshtastic
except Exception:
    meshtastic = None
from mesh_connection import add_mesh_connection_args, mesh_target_label, open_mesh_interface
try:
    from meshdash import __version__ as _package_version
except Exception:
    _package_version = "0.0.0"
from meshdash.helpers import (
    format_epoch as _format_epoch,
    normalize_single_emoji as _normalize_single_emoji,
    to_jsonable as _to_jsonable_helper,
    to_int as _to_int,
)
from meshdash.revision import (
    detect_git_commit as _detect_git_commit_helper,
    revision_info as _build_revision_info,
    sanitize_revision_token as _sanitize_revision_token_helper,
)
from meshdash.nodes import utc_now as _utc_now_helper
from meshdash.mesh_ops import (
    get_local_node_id as _get_local_node_id_helper,
    send_emoji_reaction_packet as _send_emoji_reaction_packet_helper,
)
from meshdash.runtime import (
    apply_default_gateway as _apply_default_gateway_helper,
    guess_lan_ipv4 as _guess_lan_ipv4_helper,
)
from meshdash.state import build_state as _build_state_helper
from meshdash.services import (
    build_node_history_loader as _build_node_history_loader,
    build_online_activity_loader as _build_online_activity_loader,
    send_chat_message as _send_chat_message_helper,
)
from meshdash.cli import build_dashboard_parser as _build_dashboard_parser_helper
from meshdash.dashboard_runtime import run_dashboard_runtime as _run_dashboard_runtime_helper
from meshdash.history_store import HistoryStore
from meshdash.tracker import DashboardTracker, seed_tracker_from_node_db as _seed_tracker_from_node_db_helper
from meshdash.html import render_html as _render_html_helper
from meshdash.http_api import make_http_handler as _make_http_handler_helper
try:
    from pubsub import pub
except Exception:
    pub = None

try:
    from meshtastic.protobuf import mesh_pb2, portnums_pb2
except Exception:
    mesh_pb2 = None
    portnums_pb2 = None


DEFAULT_MESH_PORT = "/dev/ttyACM0"
DEFAULT_GATEWAY_HOST = "192.168.1.241"
DEFAULT_GATEWAY_PORT = 4403
DEFAULT_HTTP_HOST = "0.0.0.0"
DEFAULT_HTTP_PORT = 8877
DEFAULT_REFRESH_MS = 3000
DEFAULT_PACKET_LIMIT = 250
DEFAULT_HISTORY_DB = "mesh_dashboard_history.sqlite3"
DEFAULT_HISTORY_MAX_ROWS = 5000
DEFAULT_HISTORY_RETENTION_DAYS = 7
DEFAULT_HISTORY_EVENT_MAX_ROWS = 200000
DEFAULT_HISTORY_EVENT_RETENTION_DAYS = 30
DEFAULT_HISTORY_ROLLUP_RETENTION_DAYS = 365
DEFAULT_NODE_HISTORY_HOURS = 72
DEFAULT_NODE_HISTORY_MAX_POINTS = 1440
DEFAULT_CHAT_MAX_BYTES = 220
DEFAULT_APP_VERSION = _package_version or "0.1.0"
UNKNOWN_GIT_COMMIT = "nogit"

SENSITIVE_FIELD_NAMES = {
    "private_key",
    "wifi_psk",
    "password",
    "psk",
    "session_passkey",
    "admin_key",
}


def _detect_git_commit() -> Optional[str]:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cwd = os.getcwd()
    explicit = os.environ.get("MESH_DASH_GIT_COMMIT", "")
    return _detect_git_commit_helper(
        explicit_commit=explicit,
        script_dir=script_dir,
        cwd=cwd,
        unknown_git_commit=UNKNOWN_GIT_COMMIT,
        sanitize_token=_sanitize_revision_token_helper,
    )


def _revision_info() -> Dict[str, str]:
    version_raw = os.environ.get("MESH_DASH_VERSION", DEFAULT_APP_VERSION)
    return _build_revision_info(
        version_raw=version_raw,
        default_version=DEFAULT_APP_VERSION,
        unknown_git_commit=UNKNOWN_GIT_COMMIT,
        detect_commit=_detect_git_commit,
        sanitize_token=_sanitize_revision_token_helper,
    )


def run_dashboard(args: argparse.Namespace) -> None:
    if meshtastic is None:
        raise RuntimeError(
            "meshtastic Python package is required. Install with: pip install meshtastic"
        )
    if pub is None:
        raise RuntimeError(
            "pypubsub is required. Install with: pip install pypubsub"
        )
    _run_dashboard_runtime_helper(
        args,
        mesh_target_label_fn=mesh_target_label,
        open_mesh_interface_fn=open_mesh_interface,
        history_store_cls=HistoryStore,
        dashboard_tracker_cls=DashboardTracker,
        subscribe_fn=pub.subscribe,
        seed_tracker_fn=_seed_tracker_from_node_db_helper,
        revision_info_fn=_revision_info,
        build_state_fn=lambda **kwargs: _build_state_helper(
            sensitive_field_names=SENSITIVE_FIELD_NAMES,
            **kwargs,
        ),
        build_node_history_loader_fn=_build_node_history_loader,
        build_online_activity_loader_fn=_build_online_activity_loader,
        send_chat_message_fn=_send_chat_message_helper,
        send_reaction_packet_fn=lambda **kwargs: _send_emoji_reaction_packet_helper(
            mesh_pb2_module=mesh_pb2,
            portnums_pb2_module=portnums_pb2,
            **kwargs,
        ),
        get_local_node_id_fn=lambda iface: _get_local_node_id_helper(
            iface,
            meshtastic_module=meshtastic,
            to_jsonable_fn=_to_jsonable_helper,
            to_int_fn=_to_int,
        ),
        normalize_single_emoji_fn=_normalize_single_emoji,
        to_int_fn=_to_int,
        utc_now_fn=_utc_now_helper,
        render_html_fn=_render_html_helper,
        make_http_handler_fn=lambda html_text, state_fn, node_history_fn=None, online_activity_fn=None, send_chat_fn=None: _make_http_handler_helper(
            html_text=html_text,
            state_fn=state_fn,
            node_history_fn=node_history_fn,
            online_activity_fn=online_activity_fn,
            send_chat_fn=send_chat_fn,
            default_node_history_hours=DEFAULT_NODE_HISTORY_HOURS,
            to_int_fn=_to_int,
        ),
        guess_lan_ipv4_fn=_guess_lan_ipv4_helper,
        default_chat_max_bytes=DEFAULT_CHAT_MAX_BYTES,
    )


def main() -> None:
    parser = _build_dashboard_parser_helper(
        add_mesh_connection_args_fn=add_mesh_connection_args,
        default_mesh_port=DEFAULT_MESH_PORT,
        default_gateway_host=DEFAULT_GATEWAY_HOST,
        default_gateway_port=DEFAULT_GATEWAY_PORT,
        env_gateway_host=os.environ.get("MESH_GATEWAY_HOST", DEFAULT_GATEWAY_HOST),
        env_gateway_port=os.environ.get("MESH_GATEWAY_PORT"),
        default_http_host=DEFAULT_HTTP_HOST,
        default_http_port=DEFAULT_HTTP_PORT,
        default_refresh_ms=DEFAULT_REFRESH_MS,
        default_packet_limit=DEFAULT_PACKET_LIMIT,
        default_history_db=DEFAULT_HISTORY_DB,
        env_history_db=os.environ.get("MESH_DASH_HISTORY_DB"),
        default_history_max_rows=DEFAULT_HISTORY_MAX_ROWS,
        default_history_retention_days=DEFAULT_HISTORY_RETENTION_DAYS,
        default_history_event_max_rows=DEFAULT_HISTORY_EVENT_MAX_ROWS,
        default_history_event_retention_days=DEFAULT_HISTORY_EVENT_RETENTION_DAYS,
        default_history_rollup_retention_days=DEFAULT_HISTORY_ROLLUP_RETENTION_DAYS,
        default_node_history_hours=DEFAULT_NODE_HISTORY_HOURS,
        default_node_history_max_points=DEFAULT_NODE_HISTORY_MAX_POINTS,
    )
    args = parser.parse_args()
    _apply_default_gateway_helper(args, default_mesh_port=DEFAULT_MESH_PORT)
    run_dashboard(args)


if __name__ == "__main__":
    main()
