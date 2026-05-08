from .html_assets import render_asset_template as _render_asset_template_helper
from .config import DEFAULT_CHAT_MAX_BYTES as _DEFAULT_CHAT_MAX_BYTES


def _short_mark(label: str) -> str:
    text = "".join(ch if ch.isalnum() else " " for ch in str(label or "")).strip()
    parts = [part for part in text.split() if part]
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[1][0]}".upper()
    if len(parts) == 1:
        token = parts[0][:2]
        return token.upper() if token else "MF"
    return "MF"


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
    bbs_app_tab_hidden_attrs: str = "",
    bbs_section_hidden_attrs: str = "",
    file_transfer_files_tab_hidden_attrs: str = "",
    file_transfer_section_hidden_attrs: str = "",
    zork_enabled: bool = False,
    network_diagnostics_tab_hidden_attrs: str = ' hidden disabled aria-hidden="true"',
    network_diagnostics_panel_hidden_attrs: str = ' hidden aria-hidden="true"',
    chat_max_bytes: int = _DEFAULT_CHAT_MAX_BYTES,
) -> str:
    try:
        normalized_chat_max_bytes = max(1, int(chat_max_bytes))
    except (TypeError, ValueError):
        normalized_chat_max_bytes = int(_DEFAULT_CHAT_MAX_BYTES)
    return _render_asset_template_helper(
        "dashboard.html.tmpl",
        app_title=app_title,
        app_heading=app_heading,
        app_short_mark=_short_mark(app_heading or app_title),
        style_css=style_css,
        app_js=app_js,
        revision_title=revision_title,
        revision_label=revision_label,
        safety_label=safety_label,
        packet_limit=packet_limit,
        history_label=history_label,
        refresh_ms=refresh_ms,
        chat_max_bytes=normalized_chat_max_bytes,
        bbs_app_tab_hidden_attrs=bbs_app_tab_hidden_attrs,
        bbs_section_hidden_attrs=bbs_section_hidden_attrs,
        file_transfer_files_tab_hidden_attrs=file_transfer_files_tab_hidden_attrs,
        file_transfer_section_hidden_attrs=file_transfer_section_hidden_attrs,
        bots_zork_state_label="Enabled" if zork_enabled else "Disabled",
        bots_zork_state_class="is-enabled" if zork_enabled else "is-disabled",
        bots_zork_hint=(
            "Direct-message this node with zork to start a session. The Console zork command is also available."
            if zork_enabled
            else "Start the dashboard with --zork-enable or MESH_DASH_ZORK_ENABLE=1 to turn on live replies."
        ),
        network_diagnostics_tab_hidden_attrs=network_diagnostics_tab_hidden_attrs,
        network_diagnostics_panel_hidden_attrs=network_diagnostics_panel_hidden_attrs,
    )
