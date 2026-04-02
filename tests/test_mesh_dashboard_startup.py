import argparse

import pytest

import mesh_dashboard as md


def test_run_dashboard_requires_meshtastic(monkeypatch):
    monkeypatch.setattr(md, "meshtastic", None)
    monkeypatch.setattr(md, "pub", object())
    with pytest.raises(RuntimeError, match="meshtastic Python package is required"):
        md.run_dashboard(argparse.Namespace())


def test_run_dashboard_requires_pubsub(monkeypatch):
    monkeypatch.setattr(md, "meshtastic", object())
    monkeypatch.setattr(md, "pub", None)
    with pytest.raises(RuntimeError, match="pypubsub is required"):
        md.run_dashboard(argparse.Namespace())


def test_revision_info_prefers_environment(monkeypatch):
    monkeypatch.setenv("MESH_DASH_VERSION", "v9.1.2")
    monkeypatch.setenv("MESH_DASH_GIT_COMMIT", "abc123def")
    info = md._revision_info()
    assert info.version == "9.1.2"
    assert info.commit == "abc123def"
    assert info.label == "Rev: v9.1.2 (abc123def)"


def test_revision_info_uses_nogit_fallback(monkeypatch):
    monkeypatch.delenv("MESH_DASH_VERSION", raising=False)
    monkeypatch.delenv("MESH_DASH_GIT_COMMIT", raising=False)
    monkeypatch.setattr(md, "_detect_git_commit", lambda: None)
    info = md._revision_info()
    assert info.commit == md.UNKNOWN_GIT_COMMIT


def test_build_render_html_fn_with_theme_uses_selected_preset(monkeypatch):
    args = argparse.Namespace(
        theme_presets="/tmp/themes.json",
        theme_preset="forest",
        theme_settings_file="/tmp/theme_settings.json",
    )
    selected = {"light": {"--bg": "#ffffff"}, "dark": {"--ui-bg": "#000000"}}
    calls = {}

    class _Settings:
        def selected_preset_tokens(self):
            return selected

    monkeypatch.setattr(md, "_build_theme_preset_settings", lambda _args: _Settings())

    def _render_html_helper(**kwargs):
        calls.update(kwargs)
        return "<html></html>"

    monkeypatch.setattr(md, "_render_html_helper", _render_html_helper)

    render_fn = md._build_render_html_fn_with_theme(args)
    html = render_fn(
        refresh_ms=3000,
        packet_limit=250,
        show_secrets=False,
        history_enabled=True,
        history_max_rows=5000,
        history_retention_days=7,
        node_history_hours=72,
        node_history_max_points=1440,
        revision_label="Rev: test",
        revision_title="Rev",
    )

    assert html == "<html></html>"
    assert calls["light_theme_vars"] == selected["light"]
    assert calls["dark_theme_vars"] == selected["dark"]


def test_build_make_http_handler_with_theme_settings_binds_theme_callbacks(monkeypatch):
    calls = {}

    class _Settings:
        def get_settings_payload(self):
            return {"ok": True, "selected_preset": "default"}

        def set_selected_preset(self, preset_name):
            return {"ok": True, "selected_preset": str(preset_name)}

    def _fake_make_http_handler_helper(**kwargs):
        calls.update(kwargs)
        return object()

    monkeypatch.setattr(md, "_make_http_handler_helper", _fake_make_http_handler_helper)
    settings = _Settings()
    build_handler = md._build_make_http_handler_with_theme_settings(
        settings,
        api_token="s3cr3t",
        private_mode=True,
    )
    handler_obj = build_handler("<html>", lambda: {"ok": True})

    assert handler_obj is not None
    assert calls["get_theme_settings_fn"]() == {"ok": True, "selected_preset": "default"}
    assert calls["set_theme_preset_fn"]("forest") == {"ok": True, "selected_preset": "forest"}
    assert calls["api_token"] == "s3cr3t"
    assert calls["private_mode"] is True
