from .html_template import render_html as _render_html_template


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
    light_theme_vars: dict | None = None,
    dark_theme_vars: dict | None = None,
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
        revision_label=revision_label,
        revision_title=revision_title,
        light_theme_vars=light_theme_vars,
        dark_theme_vars=dark_theme_vars,
    )
