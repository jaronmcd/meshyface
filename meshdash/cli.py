import argparse
from typing import Optional, Protocol

from .cli_arguments import (
    add_default_gateway_args as _add_default_gateway_args_helper,
    add_history_args as _add_history_args_helper,
    add_http_runtime_args as _add_http_runtime_args_helper,
    add_node_history_args as _add_node_history_args_helper,
    add_theme_args as _add_theme_args_helper,
)


class AddMeshConnectionArgsFn(Protocol):
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        *,
        default_mesh_port: str,
    ) -> None:
        ...


def resolve_default_gateway_port(raw_value: Optional[str], fallback: int) -> int:
    try:
        return int(raw_value) if raw_value else int(fallback)
    except ValueError:
        return int(fallback)


def parse_env_bool(raw_value: Optional[str], fallback: bool = False) -> bool:
    if raw_value is None:
        return bool(fallback)
    text = str(raw_value).strip().lower()
    if not text:
        return bool(fallback)
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return bool(fallback)


def build_dashboard_parser(
    *,
    add_mesh_connection_args_fn: AddMeshConnectionArgsFn,
    default_mesh_port: str,
    default_gateway_host: str,
    default_gateway_port: int,
    env_gateway_host: str,
    env_gateway_port: Optional[str],
    default_http_host: str,
    default_http_port: int,
    default_refresh_ms: int,
    default_packet_limit: int,
    default_reset_ticker_scale_on_restart: bool,
    default_history_db: str,
    env_history_db: Optional[str],
    default_history_max_rows: int,
    default_history_retention_days: int,
    default_history_event_max_rows: int,
    default_history_event_retention_days: int,
    default_history_rollup_retention_days: int,
    default_node_history_hours: int,
    default_node_history_max_points: int,
    env_theme_presets: Optional[str],
    env_theme_preset: Optional[str],
    env_theme_settings_file: Optional[str],
    env_private_mode: Optional[str] = None,
    env_api_token: Optional[str] = None,
) -> argparse.ArgumentParser:
    resolved_gateway_port = resolve_default_gateway_port(env_gateway_port, default_gateway_port)
    resolved_gateway_host = str(env_gateway_host or default_gateway_host)
    resolved_history_db = str(env_history_db or default_history_db)
    resolved_theme_presets = str(env_theme_presets) if env_theme_presets else None
    resolved_theme_preset = str(env_theme_preset or "default")
    resolved_theme_settings_file = str(env_theme_settings_file or "mesh_dashboard_theme_settings.json")
    resolved_private_mode = parse_env_bool(env_private_mode, False)
    resolved_api_token = str(env_api_token or "").strip() or None

    parser = argparse.ArgumentParser(
        description="Serve a high-detail Meshtastic dashboard with map, node tables, configs, and packet logs."
    )
    add_mesh_connection_args_fn(parser, default_mesh_port=default_mesh_port)
    _add_default_gateway_args_helper(
        parser,
        resolved_gateway_host=resolved_gateway_host,
        resolved_gateway_port=resolved_gateway_port,
    )
    _add_http_runtime_args_helper(
        parser,
        default_http_host=default_http_host,
        default_http_port=default_http_port,
        default_refresh_ms=default_refresh_ms,
        default_packet_limit=default_packet_limit,
        default_reset_ticker_scale_on_restart=default_reset_ticker_scale_on_restart,
        default_private_mode=resolved_private_mode,
        default_api_token=resolved_api_token,
    )
    _add_history_args_helper(
        parser,
        resolved_history_db=resolved_history_db,
        default_history_db=default_history_db,
        default_history_max_rows=default_history_max_rows,
        default_history_retention_days=default_history_retention_days,
        default_history_event_max_rows=default_history_event_max_rows,
        default_history_event_retention_days=default_history_event_retention_days,
        default_history_rollup_retention_days=default_history_rollup_retention_days,
    )
    _add_node_history_args_helper(
        parser,
        default_node_history_hours=default_node_history_hours,
        default_node_history_max_points=default_node_history_max_points,
    )
    _add_theme_args_helper(
        parser,
        resolved_theme_presets=resolved_theme_presets,
        resolved_theme_preset=resolved_theme_preset,
        resolved_theme_settings_file=resolved_theme_settings_file,
    )
    return parser
