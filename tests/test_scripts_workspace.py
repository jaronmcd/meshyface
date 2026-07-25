import json
from pathlib import Path
from types import SimpleNamespace

from meshdash.html_css import build_dashboard_css
from meshdash.html_js import build_dashboard_js
from meshdash.html_sections import build_html_shell
from meshdash.plugin_composition import build_plugin_subsystem


def _html() -> str:
    return build_html_shell(
        app_title="MeshyFace",
        app_heading="MeshyFace",
        style_css="",
        app_js="",
        revision_title="rev",
        revision_label="rev",
        safety_label="safe",
        packet_limit=100,
        history_label="history",
        refresh_ms=1000,
    )


def _js(**overrides: object) -> str:
    kwargs: dict[str, object] = {
        "refresh_ms": 1000,
        "node_history_hours": 24,
        "node_history_max_points": 240,
    }
    kwargs.update(overrides)
    return build_dashboard_js(**kwargs)


def test_scripts_alpha_workspace_is_nested_under_apps() -> None:
    html = _html()
    css = build_dashboard_css(theme_css="")
    js = _js()

    assert 'data-app-view="scripts"' in html
    assert '<span class="topbar-view-submenu-item-label">Scripts</span>' in html
    assert '<span class="topbar-view-submenu-item-alpha">ALPHA</span>' in html
    scripts_section = html.split('<section class="card scripts workspace-app-shell"', 1)[1].split(
        '<section class="card games workspace-app-shell"', 1
    )[0]
    assert 'class="card scripts workspace-app-shell"' in html
    assert 'class="scripts-head workspace-chrome-bar workspace-stack-head-shell"' in scripts_section
    assert 'class="scripts-toolbar workspace-chrome-row"' in scripts_section
    assert 'id="scripts-tabs"' in scripts_section
    assert 'class="scripts-tabs workspace-pillbar"' in scripts_section
    assert 'id="scripts-tab-plugins"' in scripts_section
    assert 'data-scripts-tab="plugins"' in scripts_section
    assert 'id="scripts-tab-debug"' in scripts_section
    assert 'data-scripts-tab="debug"' in scripts_section
    assert 'id="scripts-runtime-master-toggle"' in scripts_section
    assert 'class="btn btn-secondary scripts-runtime-master-toggle"' in scripts_section
    assert 'id="scripts-panel-plugins"' in scripts_section
    assert 'id="scripts-panel-debug"' in scripts_section
    assert 'id="scripts-list"' in html
    assert 'id="scripts-readme-modal"' in html
    assert 'id="scripts-readme-body"' in html
    assert 'data-script-readme-close' in html
    assert 'id="scripts-debug-output"' in html
    assert 'id="scripts-debug-clear"' in html
    assert 'id="scripts-admin-access"' in html
    assert 'id="scripts-admin-token"' in html
    assert 'type="password"' in html
    assert "Administrator-installed Python automations" not in html
    assert "New scripts start disabled." not in html
    assert "are not sandboxed" not in html
    assert "<h2>Scripts</h2>" not in scripts_section
    assert "scripts-alpha-badge" not in scripts_section
    assert "scripts-runtime-status" not in scripts_section
    assert "Installed scripts" not in scripts_section
    assert "scripts-count" not in scripts_section
    assert "scripts-list-head" not in scripts_section
    assert "No code editor" not in html
    assert (
        'type="file"'
        not in scripts_section
    )

    assert ".layout.view-scripts .scripts {" in css
    assert ".scripts-tab-panel[hidden] {" in css
    assert ".scripts-tab-panel-plugins {" in css
    assert ".scripts-runtime-master-toggle {" in css
    assert ".scripts-list {" in css
    scripts_list_css = css.split(".scripts-list {", 1)[1].split("}", 1)[0]
    assert "display: flex;" in scripts_list_css
    assert "flex-direction: column;" in scripts_list_css
    assert ".scripts-readme-modal {" in css
    assert ".scripts-readme-body {" in css
    assert ".scripts-settings-toggle {" in css
    assert ".scripts-configure-btn {" not in css
    assert ".scripts-debug-console {" in css
    assert ".scripts-admin-access {" in css

    known_views = js.split("const knownLayoutViews = new Set([", 1)[1].split("]);", 1)[0]
    assert '"scripts"' in known_views
    assert 'clean === "scripts"' in js
    assert 'if (normalized === "scripts") return "Scripts";' in js
    assert 'renderScriptsViewSafely(latestState, "navigation.cached.scripts");' in js
    assert 'renderScriptsViewSafely(state, "poll.updated.scripts");' in js
    assert 'runBootStep("bindScriptsView", () => bindScriptsView());' in js
    scripts_js = js.split("function scriptsRuntimeSummary", 1)[1].split(
        "function normalizeAppsLayoutView", 1
    )[0]
    assert "esc(" not in scripts_js
    assert "escAttr(emptyText)" in scripts_js
    assert "function renderScriptsDebug(runtimeSummary)" in scripts_js
    assert "Array.isArray(runtime.debug)" in scripts_js
    assert "scriptsDebugClearedThrough" in scripts_js
    assert "function applyScriptsTab(value)" in scripts_js
    assert 'event.target.closest("[data-scripts-tab]")' in scripts_js
    assert 'document.getElementById("scripts-runtime-master-toggle")' in scripts_js


def test_scripts_view_renders_waiting_discovery_and_live_lifecycle_states() -> None:
    js = _js(plugins_enabled=True)

    assert "const pluginsFeatureEnabled = !!Number(1);" in js
    assert 'clean === "scripts" && pluginsFeatureEnabled' in js
    assert "runtimeSummary.enabled === false" in js
    assert 'label: "Waiting for runtime"' in js
    assert "Scripts will be inspected after the dashboard connects" in js
    assert 'label: "Discovery error"' in js
    assert "scriptsDiscoveryErrors(runtimeSummary)" in js
    assert "scriptsConfiguredDirectory(runtimeSummary)" in js
    assert "No scripts found in ${directory}." in js
    assert "containing plugin.toml, then restart MeshyFace" in js
    assert "scriptsMasterOffGuidance" not in js
    assert "runtimeSummary.runtime_enabled === false" in js
    assert "function scriptsRuntimeMasterEnabled(runtimeSummary)" in js
    assert "function scriptsSyncRuntimeMasterControl(" in js
    assert 'fetch("/api/settings/plugins/runtime"' in js
    assert "runtimeSummary.available === false" in js
    assert 'label: "Waiting for runtime"' in js
    assert "scriptsConfiguredStateMismatch(row)" in js
    assert 'label: "Applying"' in js
    assert 'label: "Starting"' in js
    assert 'label: "Running"' in js
    assert 'label: "Error"' in js
    assert 'label: "Scripts disabled"' in js
    assert 'fetch("/api/settings/plugins"' in js
    assert 'fetch("/api/settings/plugins/config"' in js
    assert 'fetch("/api/settings/plugins/routes"' in js
    assert 'fetch("/api/admin/plugins"' in js
    assert "window.sessionStorage.setItem(scriptsAdminTokenStorageKey, clean)" in js
    assert 'headers["X-API-Token"] = token' in js
    scripts_admin_js = js.split("function scriptsStoredApiToken", 1)[1].split(
        "function scriptsRuntimeErrorMessage", 1
    )[0]
    assert "localStorage" not in scripts_admin_js
    assert "data-script-configure" in js
    assert "data-script-config-form" in js
    assert "scripts-settings-toggle" in js
    assert 'aria-expanded="${configOpen ? "true" : "false"}"' in js
    assert 'aria-controls="script-config-${escAttr(scriptId)}"' in js
    assert ">Configure<" not in js
    assert "scripts-configure-btn" not in js
    assert "data-script-route-toggle" in js
    assert "data-script-readme" in js
    assert "scriptsReadmeMarkdownHtml" in js
    assert 'document.getElementById("scripts-readme-modal")' in js
    assert "const consoleRouteVisible = commands.length > 0;" in js
    assert "const tickerRouteVisible = tickerDefinitions.length > 0 || row.ticker_enabled === false;" in js
    assert "registryEntry.on_packet === true" in js
    assert "registryEntry.on_start === true" in js
    assert "registryEntry.on_stop === true" in js
    assert "previous.consoleEnabled" in js
    assert "previous.tickerEnabled" in js
    assert 'data-route-key="ticker"' in js
    assert "ticker_enabled: !!tickerEnabled" in js
    assert "data-package-digest" in js
    assert 'data-setting-type="node_ids"' in js
    assert ".scripts-config-form {" in build_dashboard_css(theme_css="")
    assert ".scripts-route-toggles {" in build_dashboard_css(theme_css="")
    assert "const hasPackageDigest = /^sha256:[0-9a-f]{64}$/.test(packageDigest);" in js
    assert "`sha256:${packageDigest.slice(7, 19)}…`" in js
    assert 'title="${escAttr(packageDigest || "Package identity unavailable")}"' in js
    assert "package_digest: expectedPackageDigest" in js
    assert "scriptsPackageDigest" not in js
    assert "async function saveScriptConfig(scriptId, packageDigest, settings)" in js
    assert "async function setScriptRoutePolicy(" in js
    assert "async function setScriptEnabled(scriptId, packageDigest, enabled, button)" in js
    assert "async function setScriptsRuntimeMasterEnabled(enabled, button)" in js
    assert "form.dataset.packageDigest" in js
    assert "target.dataset.packageDigest" in js
    assert "draft.packageDigest === packageDigest" in js
    assert "packageDigest: expectedPackageDigest" in js
    assert "scriptsUpdateCachedRoutePolicy(\n        cleanId" in js
    assert "scriptsUpdateCachedEnabled(cleanId, !!payload.enabled, !!payload.active)" in js
    assert "scriptsUpdateCachedRuntimeMaster(" in js
    assert "Restart MeshyFace to apply the change." not in _html()


def test_scripts_view_avoids_poll_churn_duplicate_writes_and_render_cascade_failures() -> None:
    js = _js()

    assert "const scriptsPendingRequests = new Map();" in js
    assert "const scriptsPendingRouteRequests = new Set();" in js
    assert "let scriptsRuntimeMasterPending = false;" in js
    assert "if (!cleanId || scriptsPendingRequests.has(cleanId)) return false;" in js
    assert "if (!cleanId || scriptsPendingRouteRequests.has(cleanId)) return false;" in js
    assert "if (scriptsRuntimeMasterPending) return false;" in js
    assert "scriptsPendingRequests.set(cleanId, { enabled: !!enabled });" in js
    assert "scriptsPendingRouteRequests.add(cleanId);" in js
    assert "scriptsRuntimeMasterPending = true;" in js
    assert "scriptsPendingRequests.delete(cleanId);" in js
    assert "scriptsPendingRouteRequests.delete(cleanId);" in js
    assert "scriptsRuntimeMasterPending = false;" in js
    assert "if (signature === scriptsLastRenderSignature) return false;" in js
    assert "const focusedScriptId = activeElement instanceof HTMLElement" in js
    assert "replacement.focus({ preventScroll: true });" in js
    assert "rendered = runPollStep(stepName, () => renderScriptsView(state), false);" in js
    assert 'renderScriptsViewSafely(latestState, "poll.notModified.scripts");' in js
    assert 'renderScriptsViewSafely(state, "poll.updated.scripts");' in js
    assert 'renderScriptsViewSafely(latestState, "navigation.loading.scripts");' in js
    assert "window.__meshPollStepErrors = ledger;" in js
    assert "window.__meshPollStepErrorSequence = sequence;" in js
    assert "if (ledger.length > 25) ledger.splice(0, ledger.length - 25);" in js


def test_scripts_view_binds_mutations_and_drafts_to_rendered_package_identity() -> None:
    js = _js()

    assert 'data-package-digest="${escAttr(packageDigest)}"' in js
    assert "const packageDigest = String(form.dataset.packageDigest || \"\").trim();" in js
    assert "const packageDigest = String(target.dataset.packageDigest || \"\").trim();" in js
    assert "void saveScriptConfig(scriptId, packageDigest, settings);" in js
    assert "void setScriptEnabled(scriptId, packageDigest, enabled, target);" in js
    assert "void setScriptRoutePolicy(" in js
    assert "scriptsPackageDigest" not in js
    assert "draft.packageDigest === packageDigest" in js
    assert "if (draft && !draftMatchesPackage)" in js
    assert "scriptsConfigDrafts.delete(scriptId);" in js
    assert "packageDigest: expectedPackageDigest" in js
    assert js.count("if (response.status === 409)") == 3
    stale_config_handler = js.split("if (response.status === 409)", 1)[1].split(
        "throw new Error",
        1,
    )[0]
    assert "scriptsDiscardStaleConfig(cleanId);" in stale_config_handler
    assert "refreshScriptsAdminSummary(true)" in stale_config_handler
    discard_helper = js.split("function scriptsDiscardStaleConfig", 1)[1].split(
        "function scriptsReadConfigForm",
        1,
    )[0]
    assert "scriptsConfigDrafts.delete(cleanId);" in discard_helper
    assert 'scriptsOpenConfigId = "";' in discard_helper
    assert "activeElement.blur();" in discard_helper


def test_scripts_view_keeps_fingerprint_without_changed_package_confirmation() -> None:
    js = _js()

    assert "`sha256:${packageDigest.slice(7, 19)}…`" in js
    assert 'data-package-digest="${escAttr(packageDigest)}"' in js
    assert '"Review & enable"' not in js
    assert "data-identity-changed" not in js
    assert "identityChanged" not in js
    assert "Review its files and fingerprint" not in js


def test_scripts_view_scrubs_privileged_state_on_auth_loss_or_forgotten_token() -> None:
    js = _js()

    scrub_helper = js.split("function scriptsDiscardPrivilegedState", 1)[1].split(
        "function scriptsAdminRequestHeaders",
        1,
    )[0]
    assert "activeElement.blur();" in scrub_helper
    assert 'scriptsOpenConfigId = "";' in scrub_helper
    assert "scriptsConfigDrafts.clear();" in scrub_helper
    assert "scriptsAdminRuntimeSummary = null;" in scrub_helper
    assert "renderScriptsDebug(null);" in scrub_helper
    assert js.count("scriptsDiscardPrivilegedState();") >= 3

    focused_form_guard = js.split(
        "activeConfigForm instanceof HTMLFormElement",
        1,
    )[1].split(")", 1)[0]
    assert "scriptsAdminRuntimeSummary" in focused_form_guard
    assert "!scriptsAdminAccessState" in focused_form_guard

    forget_handler = js.split(
        'forgetButton.addEventListener("click"',
        1,
    )[1].split("});", 1)[0]
    assert 'scriptsSetStoredApiToken("");' in forget_handler
    assert "scriptsDiscardPrivilegedState();" in forget_handler


class _Tracker:
    def __init__(self) -> None:
        self.listeners: list[object] = []

    def add_accepted_packet_listener(self, listener: object) -> None:
        self.listeners.append(listener)

    def remove_accepted_packet_listener(self, listener: object) -> None:
        self.listeners.remove(listener)


def test_plugin_status_exposes_safe_script_metadata_and_configured_state(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins" / "weather"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.toml").write_text(
        "\n".join(
            (
                "api_version = 1",
                'id = "weather"',
                'name = "Weather Alerts"',
                'version = "2.1.0"',
                'entrypoint = "script.py:script"',
                'commands = ["weather", "forecast"]',
                "default_enabled = false",
            )
        ),
        encoding="utf-8",
    )
    (plugin_dir / "script.py").write_text("script = None\n", encoding="utf-8")
    subsystem = build_plugin_subsystem(
        args=SimpleNamespace(
            plugins_included_directory=None,
            plugins_directory=str(tmp_path / "plugins"),
            plugins_state_db=str(tmp_path / "plugin-state.sqlite3"),
            plugins_files_directory=str(tmp_path / "files"),
            plugins_event_queue_size=8,
            plugins_handler_timeout=1.0,
            plugin_enable=[],
            plugin_disable=[],
            file_transfer_enable=False,
            file_transfer_max_bytes=4096,
        ),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        status = subsystem.status()
        package_digest = status["scripts"][0]["package_digest"]
        assert str(package_digest).startswith("sha256:")
        assert status["runtime_enabled"] is True
        assert status["scripts"] == [
            {
                "id": "weather",
                "name": "Weather Alerts",
                "version": "2.1.0",
                "commands": ["weather", "forecast"],
                "source": "local",
                "default_enabled": False,
                "declared_default_enabled": False,
                "package_digest": package_digest,
                "approval_status": "new",
                "identity_changed": False,
                "enabled": False,
                "active": False,
                "mesh_enabled": True,
                "console_enabled": True,
                "ticker_enabled": True,
                "runtime_status": "disabled",
                "runtime_error": "",
                "restart_required": False,
                "settings_schema": [],
                "settings": {},
            }
        ]
        assert str(tmp_path) not in json.dumps(status["scripts"])

        result = subsystem.set_plugin_enabled(
            "weather",
            True,
            expected_package_digest=package_digest,
        )
        assert result["restart_required"] is False
        assert result["active"] is True
        assert subsystem.status()["scripts"][0]["enabled"] is True
        assert subsystem.status()["scripts"][0]["active"] is True
        route_result = subsystem.set_plugin_route_policy(
            "weather",
            mesh_enabled=False,
            console_enabled=True,
            expected_package_digest=package_digest,
        )
        assert route_result == {
            "ok": True,
            "plugin_id": "weather",
            "mesh_enabled": False,
            "console_enabled": True,
            "ticker_enabled": True,
        }
        route_status = subsystem.status()["scripts"][0]
        assert route_status["mesh_enabled"] is False
        assert route_status["console_enabled"] is True
        assert route_status["ticker_enabled"] is True
    finally:
        subsystem.close()
