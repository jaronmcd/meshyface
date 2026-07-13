import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_css import build_dashboard_css
from meshdash.theme import DARK_THEME_VARS, LIGHT_THEME_VARS, build_theme_css


def _css_rule(css: str, selector: str) -> str:
    marker = f"{selector} {{"
    assert marker in css
    return css.split(marker, 1)[1].split("}", 1)[0]


def _last_css_rule(css: str, selector: str) -> str:
    marker = f"{selector} {{"
    assert marker in css
    return css.rsplit(marker, 1)[1].split("}", 1)[0]


def test_production_theme_sources_do_not_reintroduce_legacy_tokens() -> None:
    legacy_names = (
        "bg",
        "panel",
        "line",
        "ink",
        "accent",
        "accent-2",
        "muted",
        "danger",
        "shadow",
    )
    legacy_pattern = re.compile(
        r"--(?:" + "|".join(re.escape(name) for name in legacy_names) + r")(?![-\w])"
    )
    source_root = Path(__file__).resolve().parents[1] / "meshdash"
    source_paths = sorted(source_root.rglob("*.py")) + sorted(source_root.rglob("*.tmpl"))
    violations = {}
    for source_path in source_paths:
        matches = sorted(set(legacy_pattern.findall(source_path.read_text(encoding="utf-8"))))
        if matches:
            violations[str(source_path.relative_to(source_root.parent))] = matches

    assert violations == {}
    assert not legacy_pattern.search("\n".join(LIGHT_THEME_VARS))
    assert not legacy_pattern.search("\n".join(DARK_THEME_VARS))


def test_theme_exposes_shared_workspace_shell_tokens() -> None:
    theme_css = build_theme_css(indent="")

    assert LIGHT_THEME_VARS["--workspace-shell-bg"] == "#f4f8fe"
    assert LIGHT_THEME_VARS["--workspace-shell-bg-alt"] == "#e9f0fc"
    assert LIGHT_THEME_VARS["--workspace-shell-border"] == "#4266d0"
    assert LIGHT_THEME_VARS["--theme-background-gradient"] == "linear-gradient(to bottom, #eff2f7, #eff2f7)"
    assert LIGHT_THEME_VARS["--theme-gradient-primary"] == LIGHT_THEME_VARS["--theme-background-gradient"]
    assert LIGHT_THEME_VARS["--workspace-shell-divider-bg"] == "linear-gradient(to right, #dee8fb, #c0d2f3)"
    assert DARK_THEME_VARS["--workspace-shell-bg"] == "#253a63"
    assert DARK_THEME_VARS["--workspace-shell-bg-alt"] == "#263b65"
    assert DARK_THEME_VARS["--workspace-shell-border"] == "#4d65be"
    assert DARK_THEME_VARS["--workspace-shell-border-muted"] == "#41569d"
    assert DARK_THEME_VARS["--workspace-shell-border-strong"] == "#5266bb"
    assert DARK_THEME_VARS["--workspace-shell-active-bg"] == "#375c9a"
    assert DARK_THEME_VARS["--workspace-shell-active-text"] == "#bdd6fb"
    assert DARK_THEME_VARS["--theme-background-gradient"] == "linear-gradient(to bottom, #0e121b, #171d2c)"
    assert DARK_THEME_VARS["--theme-gradient-primary"] == "linear-gradient(to bottom, #0e121b, #171d2c)"
    assert DARK_THEME_VARS["--theme-gradient-primary"] == DARK_THEME_VARS["--theme-background-gradient"]
    assert DARK_THEME_VARS["--theme-gradient-secondary"] == DARK_THEME_VARS["--theme-gradient-primary"]
    assert DARK_THEME_VARS["--workspace-shell-divider-bg"] == "linear-gradient(to right, #2a4270, #314875)"
    assert DARK_THEME_VARS["--theme-foreground-transparency"] == "0"
    assert DARK_THEME_VARS["--theme-foreground-blur"] == "none"
    assert LIGHT_THEME_VARS["--theme-foreground-blur"] == "none"
    assert DARK_THEME_VARS["--theme-font-family"] == "\"IBM Plex Sans\", \"Segoe UI\", sans-serif"
    assert DARK_THEME_VARS["--theme-text-color"] == "#e6edf3"
    assert DARK_THEME_VARS["--theme-text-color-strong"] == "#eaf0f5"
    assert DARK_THEME_VARS["--theme-text-color-soft"] == "#bfc9d6"
    assert DARK_THEME_VARS["--theme-text-color-muted"] == "#a1adbf"
    assert DARK_THEME_VARS["--theme-text-color-accent"] == "#c4d6f3"
    assert DARK_THEME_VARS["--theme-text-color-on-fill"] == "#0f172a"
    assert DARK_THEME_VARS["--theme-text-color-code"] == "#d4e1f3"
    assert DARK_THEME_VARS["--surface-tint-bg"] == "#253a63"
    assert DARK_THEME_VARS["--surface-tint-border"] == "#41569d"
    assert DARK_THEME_VARS["--surface-tint-vignette"].startswith("radial-gradient(")
    assert "--theme-background-gradient: linear-gradient(to bottom, #eff2f7, #eff2f7);" in theme_css
    assert "--workspace-shell-bg: #f4f8fe;" in theme_css
    assert "--workspace-shell-bg-alt: #e9f0fc;" in theme_css
    assert "--workspace-shell-bg: #253a63;" in theme_css
    assert "--workspace-shell-bg-alt: #263b65;" in theme_css
    assert "--workspace-shell-border: #4266d0;" in theme_css
    assert "--workspace-shell-border: #4d65be;" in theme_css
    assert "--workspace-shell-divider-bg: linear-gradient(to right, #2a4270, #314875);" in theme_css
    assert "--surface-tint-bg: #253a63;" in theme_css
    assert "--surface-tint-border: #41569d;" in theme_css
    assert "--surface-tint-vignette: radial-gradient(" in theme_css


def test_dashboard_background_layers_are_ordered_when_enabled() -> None:
    css = build_dashboard_css(theme_css="")

    base_layer = _css_rule(
        css,
        ".dashboard-image-bg,\n    .dashboard-particles-bg,\n    .dashboard-livemap-bg",
    )
    image_enabled = _css_rule(css, "body.dashboard-image-enabled .dashboard-image-bg")
    image_loaded = _css_rule(
        css,
        "body.dashboard-image-enabled .dashboard-image-bg.dashboard-image-background-loaded",
    )
    image_overlay = _css_rule(css, ".dashboard-image-bg::after")
    particles_layer = _css_rule(css, ".dashboard-particles-bg")
    non_image_over_image = _css_rule(
        css,
        "body.dashboard-particles-enabled .dashboard-image-bg,\n    body.dashboard-livemap-enabled .dashboard-image-bg",
    )
    particles_enabled = _css_rule(css, "body.dashboard-particles-enabled .dashboard-particles-bg")
    particles_loaded = _css_rule(
        css,
        "body.dashboard-particles-enabled .dashboard-particles-bg.dashboard-particles-background-loaded",
    )
    livemap_enabled = _css_rule(css, "body.dashboard-livemap-enabled .dashboard-livemap-bg")
    livemap_ready = _css_rule(css, "body.dashboard-livemap-enabled .dashboard-livemap-bg.dashboard-background-ready")
    active_class = _css_rule(css, ".dashboard-background-active")

    assert "dashboard-background-fade-in" not in css
    assert "@keyframes dashboard-background-fade-in" not in css
    assert "display: block;" in base_layer
    assert "display: none;" not in base_layer
    assert "opacity: 0;" in base_layer
    assert "visibility: hidden;" in base_layer
    assert "--dashboard-background-target-opacity: 0;" in image_enabled
    assert "opacity: 0;" in image_enabled
    assert "visibility: visible;" in image_enabled
    assert "transition: opacity 1800ms ease;" in image_enabled
    assert "--dashboard-background-target-opacity: 1;" in image_loaded
    assert "opacity: var(--dashboard-background-target-opacity);" in image_loaded
    assert 'content: "";' in image_overlay
    assert "background: rgba(0, 0, 0, var(--dashboard-image-darken, 0));" in image_overlay
    assert "opacity: 0;" in non_image_over_image
    assert "visibility: hidden;" in non_image_over_image
    assert "--dashboard-background-target-opacity: var(--dashboard-particles-opacity, 0.42);" in particles_layer
    assert "opacity: 0;" in particles_enabled
    assert "transition: opacity 1800ms ease;" in particles_enabled
    assert "visibility: visible;" in particles_enabled
    assert "opacity: var(--dashboard-background-target-opacity);" in particles_loaded
    assert ".dashboard-livemap-bg {\n      transition: opacity 1400ms ease;\n    }" in css
    assert "--dashboard-background-target-opacity: 1;" in livemap_enabled
    assert "visibility: visible;" in livemap_enabled
    assert "opacity: var(--dashboard-background-target-opacity);" in livemap_ready
    assert "z-index: 1;" in active_class


def test_workspace_views_reuse_shared_shell_tokens() -> None:
    css = build_dashboard_css(theme_css="")

    assert "--network-pane-head-bg: var(--workspace-shell-bg-alt);" not in css
    assert "--network-pane-body-bg: var(--workspace-shell-bg);" not in css
    assert "--network-pane-head-border: var(--workspace-shell-border);" not in css
    assert "--saved-pane-head-border: var(--workspace-shell-border);" not in css
    assert "--network-pane-head-border: var(--surface-tint-border);" in css
    assert "--saved-pane-head-border:" not in css
    assert "--network-pane-head-bg: transparent;" in css
    assert "--network-pane-body-bg: transparent;" in css
    assert "--network-pane-divider-bg: transparent;" in css
    assert "--saved-pane-head-bg:" not in css
    assert "--saved-pane-body-bg:" not in css
    assert ".settings-help-note {" in css
    assert "background: var(--surface-tint-bg-soft);" in css
    help_note_link = _css_rule(css, ".settings-help-note a")
    assert "color: var(--settings-text-accent);" in help_note_link
    assert "text-decoration: underline;" in help_note_link
    topbar = _css_rule(css, ".topbar")
    topbar_sub = _css_rule(css, ".topbar .sub")
    workspace_shell = _css_rule(css, ".workspace-shell")
    workspace_main = _css_rule(css, ".workspace-main")
    dark_topbar = css.rsplit("[data-theme=\"dark\"] .topbar {", 1)[1].split("}", 1)[0]
    dark_workspace_stage = css.split(
        "[data-theme=\"dark\"] .workspace-shell,\n    [data-theme=\"dark\"] .workspace-main {",
        1,
    )[1].split("}", 1)[0]
    settings_view_panel = _css_rule(css, ".layout.view-settings .settings-panel")
    dark_settings_view_panel = _css_rule(css, "[data-theme=\"dark\"] .layout.view-settings .settings-panel")
    assert "background: transparent;" in topbar
    assert "background: transparent;" in topbar_sub
    assert "background: transparent;" in workspace_shell
    assert "background: transparent;" in workspace_main
    assert "background: transparent !important;" in dark_topbar
    assert "background: transparent;" in dark_workspace_stage
    assert "background: var(--workspace-shell-bg);" in settings_view_panel
    assert "border-color: var(--workspace-shell-border);" in settings_view_panel
    assert "border-radius: 10px;" in settings_view_panel
    assert "box-shadow: none;" in settings_view_panel
    assert "background: var(--workspace-shell-bg);" in dark_settings_view_panel
    assert "border-color: var(--workspace-shell-border);" in dark_settings_view_panel
    assert "border-radius: 10px;" in dark_settings_view_panel
    assert "box-shadow: none;" in dark_settings_view_panel
    assert "background: var(--floating-stage-bg);" not in topbar
    assert "background: var(--floating-stage-bg);" not in topbar_sub
    assert "background: var(--floating-stage-bg);" not in workspace_shell
    assert "background: var(--floating-stage-bg" not in dark_workspace_stage
    dark_body = _css_rule(css, "[data-theme=\"dark\"] body")
    assert "background:" not in dark_body
    assert "html[data-theme=\"dark\"] body" not in css
    assert "background: var(--floating-stage-bg) !important;" not in css
    assert "background: var(--ui-bg) !important;" not in css
    assert "--bg: #0f1512;" not in css
    assert "--bg: #000000;" not in css
    assert "--panel: #040704;" not in css
    assert "--accent: #33ff8f;" not in css
    settings_panel = _css_rule(css, ".settings-panel")
    assert "--settings-bg: var(--workspace-shell-bg, var(--ui-panel));" in settings_panel
    assert "--settings-bg-soft: var(--workspace-shell-bg-alt, color-mix(in srgb, var(--ui-panel) 88%, var(--ui-bg) 12%));" in settings_panel
    assert "--settings-bg-muted: color-mix(in srgb, var(--workspace-shell-bg-alt, var(--ui-panel)) 70%, transparent);" in settings_panel
    assert "--settings-bg-strong: color-mix(in srgb, var(--workspace-shell-bg, var(--ui-panel)) 84%, transparent);" in settings_panel
    assert "--settings-font-family: var(--theme-font-family, \"IBM Plex Sans\", \"Segoe UI\", sans-serif);" in settings_panel
    assert "--settings-text: var(--theme-text-color, var(--workspace-shell-text, var(--ui-text)));" in settings_panel
    assert "--settings-text-strong: var(--theme-text-color-strong, var(--settings-text));" in settings_panel
    assert "--settings-text-soft: var(--theme-text-color-soft, var(--workspace-shell-text-soft, var(--ui-text-soft)));" in settings_panel
    assert "--settings-text-muted: var(--theme-text-color-muted, var(--settings-text-soft));" in settings_panel
    assert "--settings-text-accent: var(--theme-text-color-accent, var(--workspace-shell-active-text, var(--ui-accent-soft)));" in settings_panel
    assert "--settings-text-on-fill: var(--theme-text-color-on-fill, var(--settings-text));" in settings_panel
    assert "--settings-text-code: var(--theme-text-color-code, var(--settings-text));" in settings_panel
    assert "--settings-line: var(--workspace-shell-border, var(--ui-border));" in css
    assert "--settings-line-soft: var(--workspace-shell-border-muted, color-mix(in srgb, var(--settings-line) 72%, transparent));" in css
    assert "--settings-line-strong: var(--workspace-shell-border-strong, color-mix(in srgb, var(--settings-line) 82%, var(--settings-text) 18%));" in css
    assert "--settings-control-bg: color-mix(in srgb, var(--settings-bg-soft) 86%, transparent);" in css
    assert "--settings-control-text: var(--settings-text);" in css
    assert "--settings-control-border: var(--settings-line);" in css
    assert "background: var(--settings-bg);" in settings_panel
    assert "font-family: var(--settings-font-family);" in settings_panel
    assert "color: var(--settings-text-muted);" in css
    assert "color: var(--settings-control-text);" in css
    assert "border: 1px solid var(--settings-line-soft);" in css
    assert "--floating-stage-bg: var(--theme-background-gradient" in css
    assert "background: var(--theme-background-gradient, var(--theme-gradient-primary, var(--ui-bg)));" in css
    control_section_rule = _css_rule(css, ".settings-control-section + .settings-control-section")
    assert "border-top: 1px solid color-mix(in srgb, var(--settings-line-soft) 42%, transparent);" in control_section_rule
    assert "theme-live-preview" not in css
    assert ".theme-preview {" not in css
    assert ".node-profile-theme-swatch" not in css
    assert "#chat-room-pinned-list .chat-member-item.profiled-node:not(.tagged-node):not(.muted-node):not(.selected-node)::before {" not in css
    assert ".chat-member-item.profiled-node:not(.tagged-node):not(.muted-node) .chat-member-name {" in css
    assert ".chat-feed-item.profiled-node:not(.kind-status):not(.kind-alert) .chat-feed-author .chat-name {" in css
    assert "var(--chat-member-node-gradient)," in css
    assert "var(--chat-member-node-gradient-hover)," in css
    assert ".network-graph-node.has-theme-identity .network-graph-node-label {" in css
    dark_pinned_profile = _css_rule(
        css,
        '[data-theme="dark"] #chat-room-pinned-list .chat-member-item:not(.muted-node)',
    )
    dark_pinned_profile_hover = _css_rule(
        css,
        '[data-theme="dark"] #chat-room-pinned-list .chat-member-item:not(.muted-node):hover',
    )
    assert "var(--chat-member-node-gradient)" in dark_pinned_profile
    assert "var(--chat-member-node-gradient-hover)" in dark_pinned_profile_hover
    assert ".card.chat .chat-feed-item.profiled-node:not(.selected-node):not(.kind-status):not(.kind-alert):not(.has-change-marker) {" in css
    assert ".chat-feed-item.profiled-node:not(.selected-node):not(.kind-status):not(.kind-alert):not(.has-change-marker) {" in css
    assert ".chat-feed-item.profiled-node.self-authored:not(.selected-node):not(.kind-status):not(.kind-alert):not(.has-change-marker) {" not in css
    assert ".chat-feed.chat-feed-view-monitor .chat-feed-item.profiled-node:not(.kind-status):not(.kind-alert) .short-name {" in css
    assert ".card.chat .chat-reply-inline.profiled-node:not(.missing) {" in css
    assert ".peer-dm-popout-head.profiled-node {" in css
    assert ".peer-dm-popout-msg.profiled-node:not(.is-alert) {" in css
    dark_color_picker = _css_rule(css, "[data-theme=\"dark\"] .dashboard-color-picker-popover")
    color_picker = _css_rule(css, ".dashboard-color-picker-popover")
    assert "backdrop-filter: blur(14px) saturate(120%);" in color_picker
    assert "-webkit-backdrop-filter: blur(14px) saturate(120%);" in color_picker
    assert "background: color-mix(in srgb, var(--workspace-shell-bg-alt) 88%, transparent);" in dark_color_picker
    assert "workspace-shell-bg" in dark_color_picker
    dark_color_picker_inputs = _css_rule(
        css,
        "[data-theme=\"dark\"] .dashboard-color-picker-preview,\n    [data-theme=\"dark\"] .dashboard-color-picker-field-input",
    )
    assert "background: var(--workspace-shell-bg);" in dark_color_picker_inputs
    assert "workspace-shell-bg" in dark_color_picker_inputs
    assert "var(--surface-tint-bg-soft)" in css
    assert "var(--surface-tint-border-strong)" in css
    assert ".chat-member-item {" in css
    assert "--chat-member-node-bg: var(--workspace-shell-bg);" in css
    assert "--chat-member-node-bg-hover: var(--workspace-shell-hover-bg);" in css
    assert "--chat-member-node-sat-mult: 0;" in css
    assert "--chat-member-node-fg: var(--workspace-shell-text);" in css
    assert ".chat-feed-item {" in css
    assert "--chat-feed-node-bg: color-mix(in srgb, var(--ui-panel) 94%, var(--ui-bg) 6%);" in css
    assert "--chat-feed-node-sat-mult: 0;" in css
    assert ".chat-inline-emoji {" in css
    assert "background: var(--workspace-shell-bg);" in css
    assert "background: var(--workspace-shell-bg-alt);" in css
    assert "border-color: var(--workspace-shell-border);" in css
    assert "[data-theme=\"dark\"] .card.games {" not in css
    assert "[data-theme=\"dark\"] .card.files {" not in css
    assert '[data-theme="dark"] .card.workspace-app-shell {' in css
    assert "[data-theme=\"dark\"] .games-sidebar," in css
    dark_app_canvas = css.rsplit(
        '[data-theme="dark"] .card.workspace-app-shell {', 1
    )[1].split("}", 1)[0]
    assert "background: transparent;" in dark_app_canvas
    assert "[data-theme=\"dark\"] .reversi-status-text," in css
    assert "[data-theme=\"dark\"] .reversi-link-status," in css
    assert "[data-theme=\"dark\"] .reversi-invite-list {" in css
    assert "[data-theme=\"dark\"] .reversi-player-pill {" in css
    assert "[data-theme=\"dark\"] .topbar-view-menu-item-context {" in css
    assert "[data-theme=\"dark\"] .topbar-view-submenu {" in css
    assert "[data-theme=\"dark\"] .topbar-view-submenu-item.is-active," in css
    assert "[data-theme=\"dark\"] .chat-users-head-launcher-shell .topbar-view-menu-btn:hover," in css
    assert "[data-theme=\"dark\"] .settings-tab-btn {" in css
    assert "[data-theme=\"dark\"] .settings-panel {" in css
    dark_settings_panel = _css_rule(css, "[data-theme=\"dark\"] .settings-panel")
    assert "--settings-bg: var(--workspace-shell-bg);" in dark_settings_panel
    assert "--settings-bg-soft: var(--workspace-shell-bg-alt);" in dark_settings_panel
    assert "--settings-bg-muted: color-mix(in srgb, var(--workspace-shell-bg-alt) 70%, transparent);" in dark_settings_panel
    assert "--settings-bg-strong: color-mix(in srgb, var(--workspace-shell-bg) 84%, transparent);" in dark_settings_panel
    assert "--settings-font-family: var(--theme-font-family, \"IBM Plex Sans\", \"Segoe UI\", sans-serif);" in dark_settings_panel
    assert "--settings-text: var(--theme-text-color, var(--workspace-shell-text));" in dark_settings_panel
    assert "--settings-text-strong: var(--theme-text-color-strong, var(--settings-text));" in dark_settings_panel
    assert "--settings-text-soft: var(--theme-text-color-soft, var(--workspace-shell-text-soft));" in dark_settings_panel
    assert "--settings-text-muted: var(--theme-text-color-muted, var(--settings-text-soft));" in dark_settings_panel
    assert "--settings-text-accent: var(--theme-text-color-accent, var(--workspace-shell-active-text));" in dark_settings_panel
    assert "--settings-text-on-fill: var(--theme-text-color-on-fill, var(--settings-text));" in dark_settings_panel
    assert "--settings-text-code: var(--theme-text-color-code, var(--settings-text));" in dark_settings_panel
    assert "--settings-line: var(--workspace-shell-border);" in dark_settings_panel
    assert "--settings-line-soft: var(--workspace-shell-border-muted);" in dark_settings_panel
    assert "--settings-line-strong: var(--workspace-shell-border-strong);" in dark_settings_panel
    assert "--settings-control-bg: color-mix(in srgb, var(--settings-bg-soft) 86%, transparent);" in dark_settings_panel
    assert "--settings-control-text: var(--settings-text);" in dark_settings_panel
    assert "background: var(--settings-bg);" in dark_settings_panel
    assert "[data-theme=\"dark\"] .settings-ticker-config {" in css
    assert "[data-theme=\"dark\"] .layout.view-settings .settings," in css
    assert "[data-theme=\"dark\"] .layout.view-settings .settings .body {" in css


def test_received_profile_uses_simple_theme_background_and_border() -> None:
    css = build_dashboard_css(theme_css="")

    profile_tokens = _css_rule(css, "    .profiled-node")
    roster = _last_css_rule(
        css,
        ".chat-member-item.profiled-node:not(.tagged-node):not(.muted-node):not(.selected-node)",
    )
    feed = _last_css_rule(
        css,
        ".card.chat .chat-feed:not(.chat-feed-view-monitor) .chat-feed-item.profiled-node:not(.kind-status):not(.kind-alert):not(.has-change-marker)",
    )
    feed_author = _last_css_rule(
        css,
        ".chat-feed-item.profiled-node:not(.kind-status):not(.kind-alert) .chat-feed-author .chat-name",
    )
    roster_name = _last_css_rule(
        css,
        ".chat-member-item.profiled-node:not(.tagged-node):not(.muted-node) .chat-member-name",
    )
    table_name = _last_css_rule(css, "#nodes-table tbody tr.profiled-node .node-name-label")
    ticker_name = _last_css_rule(
        css,
        ".topbar .summary-ticker-item-self .value.self-node-value .self-node-identity-slot.profiled-node .self-node-name-text",
    )
    self_ticker_card = _last_css_rule(
        css,
        ".topbar .summary-ticker-item-self.profiled-node",
    )
    self_ticker_label = _last_css_rule(
        css,
        ".topbar .summary-ticker-item-self.profiled-node > .label",
    )
    self_ticker_compact_label = _last_css_rule(
        css,
        ".topbar:not(.ticker-expanded) .summary-ticker-item-self.profiled-node > .label",
    )
    self_ticker_themed_name = _last_css_rule(
        css,
        ".topbar .summary-ticker-item-self.profiled-node .self-node-name-text",
    )
    graph_label = _last_css_rule(
        css,
        ".network-graph-node.has-theme-identity .network-graph-node-label",
    )
    map_marker = _css_rule(
        css,
        ".map-node-emoji-marker.profiled-node:not(.is-trace-running):not(.is-trace-result)",
    )
    node_details_theme_preview = _last_css_rule(
        css,
        ".chat-node-details-footer-actions.has-node-theme",
    )
    roster_watermark = _css_rule(
        css,
        ".chat-member-item.profiled-node:not(.tagged-node):not(.muted-node)::after",
    )
    roster_base = _css_rule(css, "    .chat-member-item")
    assert "--node-profile-identity-edge" in profile_tokens
    assert "--node-profile-identity-color: var(" in profile_tokens
    assert "--node-profile-theme-line," in profile_tokens
    assert "var(--node-profile-border, var(--ui-accent))" in profile_tokens
    assert "--node-profile-identity-edge: var(--node-profile-identity-color);" in profile_tokens
    assert "--node-profile-theme-surface:" in profile_tokens
    assert "--node-profile-theme-surface-hover:" in profile_tokens
    assert "--node-profile-theme-shell, transparent" in profile_tokens
    assert "--node-profile-theme-shell-hover" in profile_tokens
    assert "--node-profile-theme-background," in profile_tokens
    assert "--node-profile-theme-base" in profile_tokens
    assert "color-mix(" not in profile_tokens
    assert "border-bottom-color: var(--node-profile-theme-border-muted, var(--node-profile-identity-color));" in roster
    assert "background-image: var(--node-profile-theme-surface) !important;" in roster
    assert "box-shadow: none;" in roster
    assert "border-color: var(--node-profile-identity-color);" in feed
    assert "background-image: var(--chat-feed-channel-edge-bg), var(--node-profile-theme-surface) !important;" in feed
    assert "box-shadow:" not in feed
    assert "color: var(--chat-member-node-fg, var(--workspace-shell-text)) !important;" in roster_name
    assert "color: var(--surface-tint-text) !important;" in table_name
    assert "color: var(--theme-text-color, var(--ui-text)) !important;" in feed_author
    assert "color: var(--ticker-text-strong);" in ticker_name
    assert "--self-node-channel-edge-bg:" in self_ticker_card
    assert "var(--self-node-channel-edge-fill, transparent) 0 4px" in self_ticker_card
    assert "--node-profile-self-text:" in self_ticker_card
    assert "--node-profile-self-label-text:" in self_ticker_card
    assert "color: var(--node-profile-self-text);" in self_ticker_card
    assert "background: var(--self-node-channel-edge-bg), var(--node-profile-theme-surface) !important;" in self_ticker_card
    assert "border-color: var(--node-profile-identity-edge);" in self_ticker_card
    assert "color: var(--node-profile-self-label-text);" in self_ticker_label
    assert "var(--node-profile-self-label-text) 84%" in self_ticker_compact_label
    assert "color: var(--node-profile-self-text);" in self_ticker_themed_name
    assert "fill: var(--surface-tint-text);" in graph_label
    for text_rule in (roster_name, table_name, feed_author, ticker_name, graph_label):
        assert "--node-profile-identity-edge" not in text_rule
        assert "--node-profile-theme-contrast" not in text_rule
    assert "!important" in feed_author
    assert "--node-profile-theme-motif" not in css
    assert "--node-profile-theme-ribbon-size" not in css
    assert "inset 4px 0 0 var(--node-profile-identity-edge)" not in css
    assert ".chat-member-item.profiled-node:not(.tagged-node):not(.muted-node) .chat-member-name-left::after {" not in css
    assert ".chat-feed-item.profiled-node:not(.kind-status):not(.kind-alert) .chat-feed-author::after {" not in css
    assert "#nodes-table tbody tr.profiled-node .node-name-row::after {" not in css
    assert ".map-node-info-card.profiled-node .map-node-info-title-wrap::after {" not in css
    assert 'content: "Theme";' not in css
    assert 'content: "  Theme";' not in css
    assert "is-trace-running" in css
    assert "is-trace-result" in css
    assert "border-color: var(--node-profile-identity-edge);" in map_marker
    assert "background-image: var(--node-profile-theme-surface) !important;" in node_details_theme_preview
    assert "--node-profile-theme-contrast" not in node_details_theme_preview
    assert "font-family: var(--node-profile-theme-font-family, inherit);" not in node_details_theme_preview
    assert ".chat-node-details-footer-actions.has-node-theme .chat-node-details-action-btn" not in css
    assert ".chat-node-details-footer-actions.has-node-theme .chat-node-details-footer-label" not in css
    assert ".chat-node-details-tabs.has-node-theme .chat-node-details-tab-btn" not in css
    themed_tabs = _last_css_rule(css, ".chat-node-details-tabs.has-node-theme")
    assert "background-image: var(--node-profile-theme-surface) !important;" in themed_tabs
    assert ".chat-node-details-footer-actions.has-node-theme::after" not in css
    assert "#chat-node-details-inline-host > .chat-node-details-drawer.profiled-node .chat-node-details-head::after {" in css
    assert "#chat-node-details-inline-host > .chat-node-details-drawer.profiled-node .chat-node-details-head {" in css
    themed_head = _last_css_rule(
        css,
        "#chat-node-details-inline-host > .chat-node-details-drawer.profiled-node .chat-node-details-head",
    )
    assert "background-image: var(--node-profile-theme-surface) !important;" in themed_head
    assert "\n    .node-details.profiled-node {\n" not in css
    assert ".node-details.profiled-node .node-details-section:first-child {" not in css
    assert ".node-details.profiled-node .node-details-section:first-child::after," not in css
    assert 'content: var(--node-profile-ghost-text, "");' in roster_watermark
    assert "left: var(--node-profile-ghost-anchor-x, 50%);" in roster_watermark
    assert "opacity: var(--node-profile-ghost-opacity, 0);" in roster_watermark
    assert "pointer-events: none;" in roster_watermark
    assert "flex: 0 0 auto;" in roster_base
    assert "box-shadow:" not in node_details_theme_preview
