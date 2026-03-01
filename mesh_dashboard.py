import argparse
import os
from typing import Optional

try:
    import meshtastic
except Exception:
    meshtastic = None
from mesh_connection import add_mesh_connection_args, mesh_target_label, open_mesh_interface
try:
    from meshdash import __version__ as _package_version
except Exception:
    _package_version = "0.0.0"
from meshdash.config import (
    DEFAULT_APP_VERSION_FALLBACK,
    DEFAULT_CHAT_MAX_BYTES,
    DEFAULT_GATEWAY_HOST,
    DEFAULT_GATEWAY_PORT,
    DEFAULT_HISTORY_DB,
    DEFAULT_HISTORY_EVENT_MAX_ROWS,
    DEFAULT_HISTORY_EVENT_RETENTION_DAYS,
    DEFAULT_HISTORY_MAX_ROWS,
    DEFAULT_HISTORY_RETENTION_DAYS,
    DEFAULT_HISTORY_ROLLUP_RETENTION_DAYS,
    DEFAULT_HTTP_HOST,
    DEFAULT_HTTP_PORT,
    DEFAULT_MESH_PORT,
    DEFAULT_NODE_HISTORY_HOURS,
    DEFAULT_NODE_HISTORY_MAX_POINTS,
    DEFAULT_PACKET_LIMIT,
    DEFAULT_REFRESH_MS,
    SENSITIVE_FIELD_NAMES,
    UNKNOWN_GIT_COMMIT,
)
from meshdash.helpers import (
    format_epoch as _format_epoch,
    normalize_single_emoji as _normalize_single_emoji,
    to_jsonable as _to_jsonable_helper,
    to_int as _to_int,
)
from meshdash.app_meta import (
    detect_git_commit_from_env as _detect_git_commit_from_env_helper,
    revision_info_from_env as _revision_info_from_env_helper,
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
from meshdash.state import build_state as _build_state_helper, build_state_lite as _build_state_lite_helper
from meshdash.services import (
    build_node_history_loader as _build_node_history_loader,
    build_online_activity_loader as _build_online_activity_loader,
    build_summary_metrics_loader as _build_summary_metrics_loader,
    send_chat_message as _send_chat_message_helper,
)
from meshdash.theme_presets import (
    load_theme_presets as _load_theme_presets_helper,
)
from meshdash.theme_settings import ThemePresetSettings as _ThemePresetSettings
from meshdash.cli import build_dashboard_parser as _build_dashboard_parser_helper
from meshdash.dashboard_runtime import run_dashboard_runtime as _run_dashboard_runtime_helper
from meshdash.history_store import HistoryStore
from meshdash.revision import RevisionInfo
from meshdash.tracker import DashboardTracker, seed_tracker_from_node_db as _seed_tracker_from_node_db_helper
from meshdash.html import render_html as _render_html_helper
from meshdash.http_api import make_http_handler as _make_http_handler_helper
from meshdash.wiring import (
    build_dashboard_runtime_dependencies as _build_dashboard_runtime_dependencies_helper,
    ensure_runtime_dependencies as _ensure_runtime_dependencies_helper,
)
try:
    from pubsub import pub
except Exception:
    pub = None

try:
    from meshtastic.protobuf import mesh_pb2, portnums_pb2
except Exception:
    mesh_pb2 = None
    portnums_pb2 = None


DEFAULT_APP_VERSION = _package_version or DEFAULT_APP_VERSION_FALLBACK


def _detect_git_commit() -> Optional[str]:
    return _detect_git_commit_from_env_helper(
        script_file=__file__,
        cwd=os.getcwd(),
        explicit_commit=os.environ.get("MESH_DASH_GIT_COMMIT", ""),
        unknown_git_commit=UNKNOWN_GIT_COMMIT,
    )


def _revision_info() -> RevisionInfo:
    return _revision_info_from_env_helper(
        env_version=os.environ.get("MESH_DASH_VERSION"),
        default_version=DEFAULT_APP_VERSION,
        unknown_git_commit=UNKNOWN_GIT_COMMIT,
        detect_commit_fn=_detect_git_commit,
    )


def _build_theme_preset_settings(args: argparse.Namespace) -> _ThemePresetSettings:
    presets = _load_theme_presets_helper(getattr(args, "theme_presets", None))
    return _ThemePresetSettings(
        presets=presets,
        selected_preset=getattr(args, "theme_preset", None),
        settings_path=getattr(args, "theme_settings_file", None),
    )


def _build_render_html_fn_with_theme(
    args: argparse.Namespace,
    *,
    theme_preset_settings: _ThemePresetSettings | None = None,
):
    settings = theme_preset_settings or _build_theme_preset_settings(args)

    def _render_html_with_theme(**kwargs):
        selected = settings.selected_preset_tokens()
        return _render_html_helper(
            **kwargs,
            light_theme_vars=selected.get("light"),
            dark_theme_vars=selected.get("dark"),
        )

    return _render_html_with_theme


def _build_make_http_handler_with_theme_settings(theme_settings: _ThemePresetSettings):
    def _make_http_handler_with_theme_settings(
        html_text: str,
        state_fn,
        node_history_fn=None,
        online_activity_fn=None,
        summary_metrics_fn=None,
        send_chat_fn=None,
        default_node_history_hours: int = 72,
        to_int_fn=_to_int,
    ):
        return _make_http_handler_helper(
            html_text=html_text,
            state_fn=state_fn,
            node_history_fn=node_history_fn,
            online_activity_fn=online_activity_fn,
            summary_metrics_fn=summary_metrics_fn,
            send_chat_fn=send_chat_fn,
            get_theme_settings_fn=theme_settings.get_settings_payload,
            set_theme_preset_fn=theme_settings.set_selected_preset,
            default_node_history_hours=default_node_history_hours,
            to_int_fn=to_int_fn,
        )

    return _make_http_handler_with_theme_settings


def run_dashboard(args: argparse.Namespace) -> None:
    theme_preset_settings = _build_theme_preset_settings(args)
    _ensure_runtime_dependencies_helper(
        meshtastic_module=meshtastic,
        pub_module=pub,
    )
    runtime_dependencies = _build_dashboard_runtime_dependencies_helper(
        meshtastic_module=meshtastic,
        pub_module=pub,
        mesh_target_label_fn=mesh_target_label,
        open_mesh_interface_fn=open_mesh_interface,
        history_store_cls=HistoryStore,
        dashboard_tracker_cls=DashboardTracker,
        seed_tracker_fn=_seed_tracker_from_node_db_helper,
        revision_info_fn=_revision_info,
        build_state_fn=_build_state_helper,
        build_state_lite_fn=_build_state_lite_helper,
        sensitive_field_names=SENSITIVE_FIELD_NAMES,
        build_node_history_loader_fn=_build_node_history_loader,
        build_online_activity_loader_fn=_build_online_activity_loader,
        build_summary_metrics_loader_fn=_build_summary_metrics_loader,
        send_chat_message_fn=_send_chat_message_helper,
        send_emoji_reaction_packet_fn=_send_emoji_reaction_packet_helper,
        mesh_pb2_module=mesh_pb2,
        portnums_pb2_module=portnums_pb2,
        get_local_node_id_fn=_get_local_node_id_helper,
        to_jsonable_fn=_to_jsonable_helper,
        normalize_single_emoji_fn=_normalize_single_emoji,
        to_int_fn=_to_int,
        utc_now_fn=_utc_now_helper,
        render_html_fn=_build_render_html_fn_with_theme(
            args,
            theme_preset_settings=theme_preset_settings,
        ),
        make_http_handler_fn=_build_make_http_handler_with_theme_settings(theme_preset_settings),
        default_node_history_hours=DEFAULT_NODE_HISTORY_HOURS,
        guess_lan_ipv4_fn=_guess_lan_ipv4_helper,
        default_chat_max_bytes=DEFAULT_CHAT_MAX_BYTES,
    )
    _run_dashboard_runtime_helper(
        args,
        mesh_target_label_fn=runtime_dependencies.mesh_target_label_fn,
        open_mesh_interface_fn=runtime_dependencies.open_mesh_interface_fn,
        history_store_cls=runtime_dependencies.history_store_cls,
        dashboard_tracker_cls=runtime_dependencies.dashboard_tracker_cls,
        subscribe_fn=runtime_dependencies.subscribe_fn,
        seed_tracker_fn=runtime_dependencies.seed_tracker_fn,
        revision_info_fn=runtime_dependencies.revision_info_fn,
        build_state_fn=runtime_dependencies.build_state_fn,
        build_node_history_loader_fn=runtime_dependencies.build_node_history_loader_fn,
        build_online_activity_loader_fn=runtime_dependencies.build_online_activity_loader_fn,
        build_summary_metrics_loader_fn=runtime_dependencies.build_summary_metrics_loader_fn,
        send_chat_message_fn=runtime_dependencies.send_chat_message_fn,
        send_reaction_packet_fn=runtime_dependencies.send_reaction_packet_fn,
        get_local_node_id_fn=runtime_dependencies.get_local_node_id_fn,
        normalize_single_emoji_fn=runtime_dependencies.normalize_single_emoji_fn,
        to_int_fn=runtime_dependencies.to_int_fn,
        utc_now_fn=runtime_dependencies.utc_now_fn,
        render_html_fn=runtime_dependencies.render_html_fn,
        make_http_handler_fn=runtime_dependencies.make_http_handler_fn,
        guess_lan_ipv4_fn=runtime_dependencies.guess_lan_ipv4_fn,
        default_chat_max_bytes=runtime_dependencies.default_chat_max_bytes,
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
        env_theme_presets=os.environ.get("MESH_DASH_THEME_PRESETS"),
        env_theme_preset=os.environ.get("MESH_DASH_THEME_PRESET"),
        env_theme_settings_file=os.environ.get("MESH_DASH_THEME_SETTINGS_FILE"),
    )
    args = parser.parse_args()
    _apply_default_gateway_helper(args, default_mesh_port=DEFAULT_MESH_PORT)
    run_dashboard(args)


if __name__ == "__main__":
    main()
