import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_css import build_dashboard_css
from meshdash.html_js import build_dashboard_js
from meshdash.html_sections import build_html_shell


def test_workspace_view_launcher_replaces_legacy_rail_nav() -> None:
    html = build_html_shell(
        app_title="Meshyface",
        app_heading="Meshyface",
        style_css="",
        app_js="",
        revision_title="rev",
        revision_label="rev",
        safety_label="safe",
        packet_limit=100,
        history_label="history",
        refresh_ms=1000,
    )
    css = build_dashboard_css(theme_css="")
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'class="workspace-launcher-row"' in html
    assert 'class="workspace-launcher-row" aria-label="Dashboard views">' in html
    assert 'class="workspace-launcher-shell chat-users-head-launcher-shell"' in html
    assert 'id="theme-toggle-inline-btn"' in html
    assert 'data-theme-toggle="compact"' in html
    assert 'class="chat-users-head-theme-icon"' in html
    assert 'id="layout-view-menu-btn-label"' in html
    assert 'id="layout-view-menu-btn-label-text"' in html
    assert 'class="topbar-view-menu-btn-label-text">Chat<' in html
    assert 'class="topbar-update-ticker workspace-update-ticker"' in html
    assert 'workspace-peer-dm-menu-wrap' not in html
    assert 'id="peer-dm-toggle-btn"' not in html
    assert 'class="topbar-view-menu-head"' not in html
    assert 'id="layout-view-menu-head-mark"' not in html
    assert 'id="layout-view-menu-head-brand"' not in html
    assert 'id="layout-view-menu-head-version"' not in html
    assert 'id="layout-view-menu-head-commit"' not in html
    assert 'id="chat-users-head-title"' not in html
    assert 'id="chat-users-head-version"' not in html
    assert 'id="chat-users-head-commit"' not in html
    assert 'id="layout-view-menu-btn"' in html
    assert 'id="layout-view-menu"' in html
    assert 'data-submenu="apps"' in html
    assert 'id="layout-view-menu-apps-current"' in html
    assert 'id="layout-view-menu-apps-meta"' in html
    assert 'id="layout-view-menu-apps-submenu"' in html
    assert 'class="topbar-view-submenu-item is-active"' in html
    assert 'id="settings-about-version"' in html
    assert 'id="settings-about-commit"' in html
    assert 'data-view="chat"' in html
    assert 'data-view="network"' in html
    assert 'data-view="apps"' in html
    assert 'id="chat-users-title"' not in html
    assert 'class="topbar-notify-corner"' not in html
    assert 'id="self-radio-profile"' not in html
    assert 'id="chat-change-toggle-btn"' not in html
    assert 'id="revision-text"' not in html
    assert 'class="topbar-main-row"' not in html
    assert 'topbar-view-menu-head-kicker' not in html
    assert 'topbar-view-menu-head-title' not in html
    assert 'layout-view-menu-head-current' not in html
    assert 'class="chat-peer-add-toggle-btn chat-node-navigator-menu-btn chat-node-navigator-dock-btn"' in html
    assert 'class="chat-peer-add-toggle-btn chat-panel-collapse-btn chat-users-head-action-btn"' in html
    assert 'class="chat-users-head-gear-icon"' in html
    assert '>View</button>' not in html
    assert '<aside class="teams-rail"' not in html
    assert re.search(r'<div class="workspace-launcher-row"[\s\S]*id="topbar-update-ticker"', html)
    assert re.search(
        r'<div class="chat-users-head"[\s\S]*id="theme-toggle-inline-btn"[\s\S]*id="layout-view-menu-btn"[\s\S]*id="chat-panel-collapse-btn"',
        html,
    )
    assert re.search(
        r'<div class="chat-left-bottom-bar"[\s\S]*id="chat-user-search-input"[\s\S]*id="chat-node-navigator-menu-btn"[\s\S]*id="chat-node-navigator-menu"',
        html,
    )

    assert ".workspace-launcher-row {" in css
    assert ".topbar-update-ticker[hidden] {" in css
    assert "z-index: 500;" in css
    assert ".workspace-launcher-shell {" in css
    assert ".chat-users-head-launcher-shell {" in css
    assert ".chat-users-head-theme-btn {" in css
    assert ".chat-users-head-theme-icon {" in css
    assert '.chat-users-head-theme-btn[aria-pressed="true"] {' in css
    assert ".chat-users-head-view-btn {" in css
    assert ".chat-users-head-action-btn {" in css
    assert ".chat-users-head-gear-icon {" in css
    assert ".chat-node-navigator-dock-btn {" in css
    assert ".chat-node-navigator-menu-docked {" in css
    assert "min-height: 38px;" in css
    assert ".topbar-update-ticker {" in css
    assert ".workspace-update-ticker {" in css
    assert "flex: 1 1 auto;" in css
    assert "--topbar-corner-reserve: 0px;" in css
    assert "padding-right: var(--topbar-right-inset);" in css
    assert ".topbar-view-menu-btn {" in css
    assert ".topbar-view-menu-btn-main {" in css
    assert ".topbar-view-menu-btn-label {" in css
    assert ".topbar-view-menu-btn-label-text {" in css
    assert ".topbar-view-menu-head {" not in css
    assert ".topbar-view-menu-brand {" not in css
    assert ".topbar-view-menu-brand-mark {" not in css
    assert ".topbar-view-menu-head-brand {" not in css
    assert ".topbar-view-menu-head-version," not in css
    assert ".topbar-view-menu-head-commit {" not in css
    assert ".topbar-view-menu-item-icon {" in css
    assert ".topbar-view-menu-item-label-row {" in css
    assert ".topbar-view-menu-item-context {" in css
    assert ".topbar-view-menu-item-has-submenu {" in css
    assert ".topbar-view-menu-item-branch {" in css
    assert ".topbar-view-menu {" in css
    assert ".topbar-view-submenu {" in css
    assert ".topbar-view-submenu[data-side=\"overlay\"] {" in css
    assert ".topbar-view-submenu-item {" in css
    assert "z-index: 1350;" in css
    topbar_section = css.split(".topbar {", 1)[1].split("}", 1)[0]
    topbar_sub_section = css.split(".topbar .sub {", 1)[1].split("}", 1)[0]
    topbar_summary_row_padding_section = css.split(".topbar .sub .summary-ticker-row {", 3)[2].split("}", 1)[0]
    topbar_ticker_section = css.split(".topbar .summary-ticker-item {", 1)[1].split("}", 1)[0]
    topbar_update_section = css.split(".topbar-update-ticker {", 1)[1].split("}", 1)[0]
    topbar_launcher_section = css.split(".topbar-view-menu-btn {", 1)[1].split("}", 1)[0]
    assert "padding: 8px 8px 0;" in topbar_section
    assert "box-shadow: none;" in topbar_section
    assert "padding: 0;" in topbar_sub_section
    assert "padding-right: 0;" in topbar_summary_row_padding_section
    assert "box-shadow: none;" in topbar_ticker_section
    assert "box-shadow: none;" in topbar_update_section
    assert "box-shadow: none;" in topbar_launcher_section
    assert ".chat-panel-collapse-glyph-collapse {" in css
    assert ".chat-panel-collapse-glyph-expand {" in css
    assert '.chat-panel-collapse-btn[aria-pressed="true"] .chat-panel-collapse-glyph-collapse {' in css
    assert '.chat-panel-collapse-btn[aria-pressed="true"] .chat-panel-collapse-glyph-expand {' in css
    assert re.search(
        r"\.workspace-shell \{\s*--chat-panel-width: 250px;[\s\S]*grid-template-rows: auto minmax\(0, 1fr\);[\s\S]*column-gap: 8px;[\s\S]*row-gap: 0;",
        css,
    )
    assert ".workspace-shell.has-topbar-update-ticker {" in css
    assert "row-gap: 8px;" in css
    assert re.search(
        r"\.workspace-shell\.chat-panel-open \{[\s\S]*grid-template-rows: auto minmax\(0, 1fr\);",
        css,
    )

    assert "function syncLayoutViewLauncherButtonState(viewName = activeLayoutView) {" in js
    assert "function setTopbarUpdateTickerVisibility(tickerEl, visible) {" in js
    assert 'const launcherRow = tickerEl.closest(".workspace-launcher-row");' in js
    assert "launcherRow.hidden = !visible;" in js
    assert 'workspaceShell.classList.toggle("has-topbar-update-ticker", !!visible);' in js
    assert "function shouldCloseLayoutViewMenuForScrollTarget(target = null) {" in js
    assert 'document.getElementById("settings-about-version")' in js
    assert 'document.getElementById("settings-about-commit")' in js
    assert 'const settingsBadgeEmojiStorageKey = "meshDashboardSettingsBadgeEmojiV1";' in js
    assert 'document.getElementById("layout-view-menu-head-mark")' not in js
    assert 'document.getElementById("layout-view-menu-head-version")' not in js
    assert 'document.getElementById("layout-view-menu-head-commit")' not in js
    assert 'document.getElementById("chat-users-head-version")' not in js
    assert 'document.getElementById("chat-users-head-commit")' not in js
    assert 'target.closest("#layout-view-menu .topbar-view-menu-item")' in js
    assert 'document.getElementById("layout-view-menu-btn-label")' in js
    assert 'const launcherLabelText = document.getElementById("layout-view-menu-btn-label-text");' in js
    assert 'document.getElementById("layout-view-menu-btn")' in js
    assert 'document.querySelectorAll("[data-theme-toggle]")' in js
    assert 'btn.dataset.themeToggleBound = "1";' in js
    assert 'if (typeof syncLayoutViewLauncherButtonState === "function") {' in js
    assert 'syncLayoutViewLauncherButtonState(activeLayoutView);' in js
    assert 'document.getElementById("layout-view-menu-apps-current")' in js
    assert 'document.getElementById("layout-view-menu-apps-submenu")' in js
    assert "function closeLayoutViewSubmenus() {" in js
    assert "function openLayoutViewSubmenu(name = \"\") {" in js
    assert "function toggleLayoutViewSubmenu(name = \"\") {" in js
    assert "function currentWorkspaceLauncherLabel(viewName = activeLayoutView) {" in js
    assert 'target.closest("#layout-view-menu .topbar-view-submenu-item")' in js
    assert 'target.closest(\'#layout-view-menu .topbar-view-menu-item[data-submenu="apps"]\')' in js
    assert 'return `Apps · ${currentAppsLauncherLabel(viewName)}`;' in js
    assert 'Math.max(260, Math.ceil(btnRect.width))' in js
    assert 'if (!shouldCloseLayoutViewMenuForScrollTarget(ev ? ev.target : null)) {' in js
    assert 'return target === document.body || target === document.documentElement;' in js
    assert "let topbarCornerReservePx = 0;" in js
    assert 'window.syncLayoutViewLauncherButtonState = syncLayoutViewLauncherButtonState;' in js


def test_apps_launcher_submenu_uses_in_menu_flyout_alignment() -> None:
    css = build_dashboard_css(theme_css="")
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    overlay_section = css.split('.topbar-view-submenu[data-side="overlay"] {', 1)[1].split("}", 1)[0]
    assert "top: calc(100% + 6px);" in overlay_section
    assert "left: 0;" in overlay_section
    assert 'submenu.dataset.side = canOpenRight ? "" : "overlay";' in js
    assert 'positionFloatingPanelNearAnchor(submenu, trigger' not in js
