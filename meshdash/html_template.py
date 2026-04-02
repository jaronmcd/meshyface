from .html_context import build_html_render_context as _build_html_render_context_helper
from .html_css import build_dashboard_css as _build_dashboard_css_helper
from .html_js import build_dashboard_js as _build_dashboard_js_helper
from .html_sections import build_html_shell as _build_html_shell_helper
from .app_brand import APP_HEADING as _APP_HEADING
from .app_brand import APP_TITLE as _APP_TITLE


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
    render_context = _build_html_render_context_helper(
        show_secrets=show_secrets,
        history_enabled=history_enabled,
        history_max_rows=history_max_rows,
        history_retention_days=history_retention_days,
        light_theme_vars=light_theme_vars,
        dark_theme_vars=dark_theme_vars,
    )
    style_css = _build_dashboard_css_helper(theme_css=render_context["theme_css"])
    app_js = _build_dashboard_js_helper(
        refresh_ms=refresh_ms,
        node_history_hours=node_history_hours,
        node_history_max_points=node_history_max_points,
        reset_ticker_scale_on_restart=reset_ticker_scale_on_restart,
    )
    return _build_html_shell_helper(
        app_title=_APP_TITLE,
        app_heading=_APP_HEADING,
        style_css=style_css,
        app_js=app_js,
        revision_title=revision_title,
        revision_label=revision_label,
        safety_label=render_context["safety_label"],
        packet_limit=packet_limit,
        history_label=render_context["history_label"],
        refresh_ms=refresh_ms,
    )
