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


def _js() -> str:
    return build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )


def test_scripts_alpha_workspace_is_nested_under_apps() -> None:
    html = _html()
    css = build_dashboard_css(theme_css="")
    js = _js()

    assert 'data-app-view="scripts"' in html
    assert '<span class="topbar-view-submenu-item-label">Scripts</span>' in html
    assert '<span class="topbar-view-submenu-item-alpha">ALPHA</span>' in html
    assert 'class="card scripts workspace-app-shell"' in html
    assert 'id="scripts-runtime-status"' in html
    assert 'id="scripts-list"' in html
    assert 'id="scripts-debug-output"' in html
    assert 'id="scripts-debug-clear"' in html
    assert 'id="scripts-restart-notice"' in html
    assert "No code editor" not in html
    assert 'type="file"' not in html.split(
        '<section class="card scripts workspace-app-shell"', 1
    )[1].split('<section class="card games workspace-app-shell"', 1)[0]

    assert '.layout.view-scripts .scripts {' in css
    assert ".scripts-runtime-status.is-enabled {" in css
    assert ".scripts-runtime-status.is-disabled {" in css
    assert ".scripts-runtime-status.is-error {" in css
    assert ".scripts-list {" in css
    assert ".scripts-debug-console {" in css

    known_views = js.split("const knownLayoutViews = new Set([", 1)[1].split(
        "]);", 1
    )[0]
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


def test_scripts_view_renders_master_off_offline_and_restart_pending_states() -> None:
    js = _js()

    assert 'runtimeSummary.enabled === false' in js
    assert 'label: "Not inspected", message: scriptsMasterOffGuidance' in js
    assert '? "Not inspected"' in js
    assert "--bots-directory path" in js
    assert "--bots-enable or MESH_DASH_BOTS_ENABLE=true" in js
    assert "then restart MeshyFace" in js
    assert 'runtimeSummary.available === false' in js
    assert 'label: "Waiting for runtime"' in js
    assert 'scriptsConfiguredStateMismatch(row)' in js
    assert 'label: "Restart pending"' in js
    assert 'label: "Starting"' in js
    assert 'label: "Running"' in js
    assert 'label: "Error"' in js
    assert 'fetch("/api/settings/plugins"' in js
    assert 'JSON.stringify({ plugin_id: cleanId, enabled: !!enabled })' in js
    assert "restartNotice.hidden = !restartRequired;" in js
    assert 'rows.some((row) => scriptsConfiguredStateMismatch(row))' in js
    assert "Restart MeshyFace to apply the change." in _html()


def test_scripts_view_avoids_poll_churn_duplicate_writes_and_render_cascade_failures() -> None:
    js = _js()

    assert 'const scriptsPendingRequests = new Map();' in js
    assert 'if (!cleanId || scriptsPendingRequests.has(cleanId)) return false;' in js
    assert 'scriptsPendingRequests.set(cleanId, { enabled: !!enabled });' in js
    assert 'scriptsPendingRequests.delete(cleanId);' in js
    assert 'if (signature === scriptsLastRenderSignature) return false;' in js
    assert 'const focusedScriptId = activeElement instanceof HTMLElement' in js
    assert 'replacement.focus({ preventScroll: true });' in js
    assert 'return runPollStep(stepName, () => renderScriptsView(state), false);' in js
    assert 'renderScriptsViewSafely(latestState, "poll.notModified.scripts");' in js
    assert 'renderScriptsViewSafely(state, "poll.updated.scripts");' in js
    assert 'renderScriptsViewSafely(latestState, "navigation.loading.scripts");' in js
    assert 'window.__meshPollStepErrors = ledger;' in js
    assert 'window.__meshPollStepErrorSequence = sequence;' in js
    assert 'if (ledger.length > 25) ledger.splice(0, ledger.length - 25);' in js


class _Tracker:
    def add_accepted_packet_listener(self, _listener: object) -> None:
        raise AssertionError("disabled script must not register a listener")


def test_plugin_status_exposes_safe_script_metadata_and_configured_state(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins" / "weather"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "bot.toml").write_text(
        "\n".join(
            (
                "api_version = 1",
                'id = "weather"',
                'name = "Weather Alerts"',
                'version = "2.1.0"',
                'entrypoint = "bot.py:bot"',
                'commands = ["weather", "forecast"]',
                "default_enabled = false",
            )
        ),
        encoding="utf-8",
    )
    (plugin_dir / "bot.py").write_text("bot = None\n", encoding="utf-8")
    subsystem = build_plugin_subsystem(
        args=SimpleNamespace(
            bots_directory=str(tmp_path / "plugins"),
            bots_state_db=str(tmp_path / "plugin-state.sqlite3"),
            bots_files_directory=str(tmp_path / "files"),
            bots_event_queue_size=8,
            bots_handler_timeout=1.0,
            bot_enable=[],
            bot_disable=[],
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
        assert status["scripts"] == [
            {
                "id": "weather",
                "name": "Weather Alerts",
                "version": "2.1.0",
                "commands": ["weather", "forecast"],
                "source": "local",
                "default_enabled": False,
                "enabled": False,
                "active": False,
                "runtime_status": "disabled",
                "runtime_error": "",
                "restart_required": False,
            }
        ]
        assert str(tmp_path) not in json.dumps(status["scripts"])

        result = subsystem.set_plugin_enabled("weather", True)
        assert result["restart_required"] is True
        assert subsystem.status()["scripts"][0]["enabled"] is True
        assert subsystem.status()["scripts"][0]["active"] is False
    finally:
        subsystem.close()
