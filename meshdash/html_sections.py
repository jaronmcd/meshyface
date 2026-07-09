from html import escape as _html_escape

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


def _background_type(value: object) -> str:
    clean = str(value or "").strip().lower()
    if clean in {"live-map", "live_map", "map"}:
        clean = "livemap"
    return clean if clean in {"particles", "livemap", "image"} else "particles"


def _background_image_data(value: object) -> str:
    clean = str(value or "").strip()
    if clean.startswith("data:image/") and ";base64," in clean:
        return clean
    return ""


def _background_image_layout(value: object) -> str:
    aliases = {
        "fill": "cover",
        "fit": "contain",
        "fit-screen": "contain",
        "fit_screen": "contain",
        "full": "stretch",
        "stretched": "stretch",
        "repeat": "tile",
        "tiled": "tile",
        "centered": "center",
    }
    clean = str(value or "").strip().lower()
    clean = aliases.get(clean, clean)
    return clean if clean in {"cover", "contain", "stretch", "center", "tile"} else "cover"


def _background_image_layout_css(layout: str) -> tuple[str, str, str]:
    if layout == "contain":
        return ("contain", "no-repeat", "center center")
    if layout == "stretch":
        return ("100% 100%", "no-repeat", "center center")
    if layout == "center":
        return ("auto", "no-repeat", "center center")
    if layout == "tile":
        return ("auto", "repeat", "center center")
    return ("cover", "no-repeat", "center center")


def _background_image_darken(value: object) -> int:
    try:
        parsed = int(str(value if value is not None else "").strip())
    except (TypeError, ValueError):
        parsed = 0
    return max(0, min(100, parsed))


def _particles_enabled(value: object) -> bool:
    if isinstance(value, bool):
        return value
    clean = str(value or "").strip().lower()
    if clean in {"1", "true", "yes", "on", "enabled"}:
        return True
    if clean in {"0", "false", "no", "off", "disabled"}:
        return False
    return bool(value)


def _particles_opacity(value: object) -> int:
    try:
        parsed = int(str(value if value is not None else "").strip())
    except (TypeError, ValueError):
        parsed = 42
    return max(0, min(100, parsed))


def _initial_background_attrs(settings: object) -> dict[str, str]:
    payload = settings if isinstance(settings, dict) else {}
    background_type = _background_type(payload.get("background_type"))
    body_classes: list[str] = []
    image_classes = "dashboard-image-bg"
    particles_classes = "dashboard-particles-bg"
    livemap_classes = "dashboard-livemap-bg"
    image_attrs = ""
    particles_attrs = ""
    livemap_attrs = ""

    if background_type == "image":
        image_data = _background_image_data(payload.get("background_image_data"))
        if image_data:
            layout = _background_image_layout(payload.get("background_image_layout"))
            darken = _background_image_darken(payload.get("background_image_darken"))
            size, repeat, position = _background_image_layout_css(layout)
            image_signature = f"image:{layout}:{image_data}"
            image_style = (
                f"background-image: url('{_html_escape(image_data, quote=True)}'); "
                f"background-size: {size}; "
                f"background-repeat: {repeat}; "
                f"background-position: {position}; "
                f"--dashboard-image-darken: {darken / 100:g};"
            )
            body_classes.append("dashboard-image-enabled")
            image_classes += " dashboard-background-ready dashboard-background-active"
            image_attrs = (
                f' style="{image_style}"'
                f' data-dashboard-background-signature="{_html_escape(image_signature, quote=True)}"'
            )
    elif background_type == "livemap":
        body_classes.append("dashboard-livemap-enabled")
    elif _particles_enabled(payload.get("particles_enabled")):
        opacity = _particles_opacity(payload.get("particles_opacity"))
        body_classes.append("dashboard-particles-enabled")
        particles_attrs = f' style="--dashboard-particles-opacity: {opacity / 100:g};"'

    body_attrs = f' class="{" ".join(body_classes)}"' if body_classes else ""
    return {
        "body_attrs": body_attrs,
        "dashboard_image_bg_class": image_classes,
        "dashboard_image_bg_attrs": image_attrs,
        "dashboard_particles_bg_class": particles_classes,
        "dashboard_particles_bg_attrs": particles_attrs,
        "dashboard_livemap_bg_class": livemap_classes,
        "dashboard_livemap_bg_attrs": livemap_attrs,
    }


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
    bots_app_tab_hidden_attrs: str = "",
    bots_section_hidden_attrs: str = "",
    games_enabled: bool = False,
    network_diagnostics_tab_hidden_attrs: str = ' hidden disabled aria-hidden="true"',
    network_diagnostics_panel_hidden_attrs: str = ' hidden aria-hidden="true"',
    chat_max_bytes: int = _DEFAULT_CHAT_MAX_BYTES,
    initial_background_settings: dict[str, object] | None = None,
) -> str:
    try:
        normalized_chat_max_bytes = max(1, int(chat_max_bytes))
    except (TypeError, ValueError):
        normalized_chat_max_bytes = int(_DEFAULT_CHAT_MAX_BYTES)
    background_attrs = _initial_background_attrs(initial_background_settings)
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
        **background_attrs,
        bbs_app_tab_hidden_attrs=bbs_app_tab_hidden_attrs,
        bbs_section_hidden_attrs=bbs_section_hidden_attrs,
        file_transfer_files_tab_hidden_attrs=file_transfer_files_tab_hidden_attrs,
        file_transfer_section_hidden_attrs=file_transfer_section_hidden_attrs,
        bots_app_tab_hidden_attrs=bots_app_tab_hidden_attrs,
        bots_section_hidden_attrs=bots_section_hidden_attrs,
        bots_zork_state_label="Enabled" if games_enabled else "Disabled",
        bots_zork_state_class="is-enabled" if games_enabled else "is-disabled",
        bots_ping_state_label="Disabled",
        bots_ping_state_class="is-disabled",
        bots_zork_hint=(
            "Public chat zork starts a private session. Direct messages continue gameplay."
            if games_enabled
            else "Live replies are disabled. Enable Zork here to answer public starts and direct messages."
        ),
        network_diagnostics_tab_hidden_attrs=network_diagnostics_tab_hidden_attrs,
        network_diagnostics_panel_hidden_attrs=network_diagnostics_panel_hidden_attrs,
    )
