from .html_assets import render_asset_template as _render_asset_template_helper

_DASHBOARD_CSS_TEMPLATE_PARTS = (
    "dashboard.css.base.tmpl",
    "dashboard.css.layout.tmpl",
    "dashboard.css.components.tmpl",
)


def build_dashboard_css(*, theme_css: str) -> str:
    return "".join(
        _render_asset_template_helper(template_name, theme_css=theme_css)
        for template_name in _DASHBOARD_CSS_TEMPLATE_PARTS
    )
