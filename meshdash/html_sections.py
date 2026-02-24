from .html_assets import render_asset_template as _render_asset_template_helper


def build_html_shell(
    *,
    style_css: str,
    app_js: str,
    revision_title: str,
    revision_label: str,
    safety_label: str,
    packet_limit: int,
    history_label: str,
    refresh_ms: int,
) -> str:
    return _render_asset_template_helper(
        "dashboard.html.tmpl",
        style_css=style_css,
        app_js=app_js,
        revision_title=revision_title,
        revision_label=revision_label,
        safety_label=safety_label,
        packet_limit=packet_limit,
        history_label=history_label,
        refresh_ms=refresh_ms,
    )
