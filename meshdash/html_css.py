from .html_assets import render_asset_template as _render_asset_template_helper


def build_dashboard_css(*, theme_css: str) -> str:
    return _render_asset_template_helper("dashboard.css.tmpl", theme_css=theme_css)
