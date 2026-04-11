from .html_template import render_html as _render_html_template
from .config import (
    DEFAULT_FILE_TRANSFER_MAX_BYTES as _DEFAULT_FILE_TRANSFER_MAX_BYTES,
)


def render_html(
    refresh_ms: int,
    packet_limit: int,
    show_secrets: bool,
    history_enabled: bool,
    history_max_rows: int,
    history_retention_days: int,
    node_history_hours: int,
    node_history_max_points: int,
    revision_label: str,
    revision_title: str,
    reset_ticker_scale_on_restart: bool = True,
    debug_mode: bool = False,
    ui_profile: str | None = None,
    light_theme_vars: dict | None = None,
    dark_theme_vars: dict | None = None,
    file_transfer_enabled: bool = False,
    file_transfer_max_bytes: int = _DEFAULT_FILE_TRANSFER_MAX_BYTES,
) -> str:
    return _render_html_template(
        refresh_ms=refresh_ms,
        packet_limit=packet_limit,
        show_secrets=show_secrets,
        history_enabled=history_enabled,
        history_max_rows=history_max_rows,
        history_retention_days=history_retention_days,
        node_history_hours=node_history_hours,
        node_history_max_points=node_history_max_points,
        reset_ticker_scale_on_restart=reset_ticker_scale_on_restart,
        debug_mode=debug_mode,
        ui_profile=ui_profile,
        revision_label=revision_label,
        revision_title=revision_title,
        light_theme_vars=light_theme_vars,
        dark_theme_vars=dark_theme_vars,
        file_transfer_enabled=file_transfer_enabled,
        file_transfer_max_bytes=file_transfer_max_bytes,
    )
