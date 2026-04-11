from .html_assets import render_asset_template as _render_asset_template_helper


def build_html_shell(
    *,
    app_title: str,
    app_heading: str,
    style_css: str,
    app_js: str,
    revision_title: str,
    revision_label: str,
    safety_label: str,
    packet_limit: int,
    history_label: str,
    refresh_ms: int,
    file_transfer_files_tab_hidden_attrs: str = "",
    file_transfer_section_hidden_attrs: str = "",
    network_diagnostics_tab_hidden_attrs: str = ' hidden disabled aria-hidden="true"',
    network_diagnostics_panel_hidden_attrs: str = ' hidden aria-hidden="true"',
) -> str:
    return _render_asset_template_helper(
        "dashboard.html.tmpl",
        app_title=app_title,
        app_heading=app_heading,
        style_css=style_css,
        app_js=app_js,
        revision_title=revision_title,
        revision_label=revision_label,
        safety_label=safety_label,
        packet_limit=packet_limit,
        history_label=history_label,
        refresh_ms=refresh_ms,
        file_transfer_files_tab_hidden_attrs=file_transfer_files_tab_hidden_attrs,
        file_transfer_section_hidden_attrs=file_transfer_section_hidden_attrs,
        network_diagnostics_tab_hidden_attrs=network_diagnostics_tab_hidden_attrs,
        network_diagnostics_panel_hidden_attrs=network_diagnostics_panel_hidden_attrs,
    )
