import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.api_input_theme import parse_theme_settings_request
from meshdash.html_js import build_dashboard_js
from meshdash.html_template import render_html
from meshdash.theme import (
    DARK_THEME_VARS,
    DEFAULT_CUSTOM_THEME_BASE_COLOR,
    DEFAULT_CUSTOM_THEME_COLOR_DEPTH,
    DEFAULT_CUSTOM_THEME_LINE_COLOR,
    DEFAULT_CUSTOM_THEME_TINT_COLOR,
    DEFAULT_CUSTOM_THEME_TINT_INTENSITY,
    DEV_THEME_BASE_COLOR,
    DEFAULT_THEME_COLOR_DEPTH,
    LIGHT_THEME_VARS,
    build_palette_theme_preset,
)
from meshdash.theme_presets import default_theme_presets, load_theme_presets, select_theme_preset
from meshdash.theme_settings import ThemePresetSettings


def test_default_theme_presets_include_blue_generated_palette() -> None:
    presets = default_theme_presets()

    assert "blue" in presets
    assert presets["blue"] == build_palette_theme_preset(
        DEV_THEME_BASE_COLOR,
        color_depth=DEFAULT_THEME_COLOR_DEPTH,
    )
    assert set(presets["blue"]["light"].keys()) == set(LIGHT_THEME_VARS.keys())
    assert set(presets["blue"]["dark"].keys()) == set(DARK_THEME_VARS.keys())
    assert presets["blue"]["dark"]["--workspace-shell-border"] != DARK_THEME_VARS["--workspace-shell-border"]


def test_load_theme_presets_merges_valid_external_presets_and_ignores_invalid_data() -> None:
    defaults = default_theme_presets()
    custom_light = {**defaults["default"]["light"], "--theme-base-color": "#123456"}
    custom_dark = {**defaults["default"]["dark"], "--theme-base-color": "#abcdef"}

    loaded = load_theme_presets(
        "themes.json",
        read_text_fn=lambda path: json.dumps(
            {
                "sunrise": {"light": custom_light, "dark": custom_dark},
                "missing-dark": {"light": custom_light},
                "bad": "not a preset",
            }
        ),
    )

    assert loaded["sunrise"]["light"]["--theme-base-color"] == "#123456"
    assert loaded["sunrise"]["dark"]["--theme-base-color"] == "#abcdef"
    assert "missing-dark" not in loaded
    assert "bad" not in loaded
    assert select_theme_preset(loaded, "sunrise") is loaded["sunrise"]
    assert select_theme_preset(loaded, "missing") is loaded["default"]


def test_load_theme_presets_falls_back_to_defaults_on_empty_or_bad_sources() -> None:
    defaults = default_theme_presets()

    assert load_theme_presets(None).keys() == defaults.keys()
    assert load_theme_presets("themes.json", read_text_fn=lambda path: "[]").keys() == defaults.keys()
    assert load_theme_presets(
        "themes.json",
        read_text_fn=lambda path: (_ for _ in ()).throw(OSError("missing")),
    ).keys() == defaults.keys()
    assert load_theme_presets(
        "themes.json",
        read_text_fn=lambda path: "{bad",
        json_loads_fn=lambda text: (_ for _ in ()).throw(ValueError("bad json")),
    ).keys() == defaults.keys()


def test_theme_settings_support_generated_custom_theme_state() -> None:
    settings = ThemePresetSettings(
        presets=default_theme_presets(),
        selected_preset="default",
        settings_path=None,
    )

    response = settings.apply_settings(
        {
            "preset_name": "custom",
            "custom_theme": {
                "base_color": "#1d4ed8",
                "line_color": "#ef4444",
                "tint_color": "#64748b",
                "tint_intensity": 61,
                "color_depth": 72,
            },
        }
    )

    expected_custom = build_palette_theme_preset(
        "#1d4ed8",
        line_color="#ef4444",
        tint_color="#64748b",
        tint_intensity=61,
        color_depth=72,
    )
    default_line_custom = build_palette_theme_preset("#1d4ed8", color_depth=72)

    assert response["ok"] is True
    assert response["selected_preset"] == "custom"
    assert response["custom_theme"] == {
        "base_color": "#1d4ed8",
        "line_color": "#ef4444",
        "tint_color": "#64748b",
        "tint_intensity": 61,
        "color_depth": 72,
    }
    assert "custom" in response["available_presets"]
    assert response["presets"]["custom"] == expected_custom
    assert response["presets"]["custom"]["light"]["--theme-base-color"] == "#1d4ed8"
    assert response["presets"]["custom"]["dark"]["--theme-base-color"] == "#1d4ed8"
    assert response["presets"]["custom"]["dark"]["--workspace-shell-border"] != default_line_custom["dark"]["--workspace-shell-border"]
    assert settings.selected_preset_name() == "custom"
    assert settings.selected_preset_tokens() == expected_custom


def test_theme_settings_default_to_meshyface_custom_palette() -> None:
    settings = ThemePresetSettings(
        presets=default_theme_presets(),
        selected_preset=None,
        settings_path=None,
    )

    expected_custom = build_palette_theme_preset(
        DEFAULT_CUSTOM_THEME_BASE_COLOR,
        line_color=DEFAULT_CUSTOM_THEME_LINE_COLOR,
        tint_color=DEFAULT_CUSTOM_THEME_TINT_COLOR,
        tint_intensity=DEFAULT_CUSTOM_THEME_TINT_INTENSITY,
        color_depth=DEFAULT_CUSTOM_THEME_COLOR_DEPTH,
    )

    assert settings.selected_preset_name() == "custom"
    assert settings.custom_theme_settings() == {
        "base_color": DEFAULT_CUSTOM_THEME_BASE_COLOR,
        "line_color": DEFAULT_CUSTOM_THEME_LINE_COLOR,
        "tint_color": DEFAULT_CUSTOM_THEME_TINT_COLOR,
        "tint_intensity": DEFAULT_CUSTOM_THEME_TINT_INTENSITY,
        "color_depth": DEFAULT_CUSTOM_THEME_COLOR_DEPTH,
    }
    assert settings.selected_preset_tokens() == expected_custom


def test_theme_settings_preserve_zero_tint_intensity() -> None:
    settings = ThemePresetSettings(
        presets=default_theme_presets(),
        selected_preset="custom",
        settings_path=None,
    )

    response = settings.apply_settings(
        {
            "preset_name": "custom",
            "custom_theme": {
                "base_color": "#1d4ed8",
                "line_color": "#9a9996",
                "tint_color": "#9a9996",
                "tint_intensity": 0,
                "color_depth": 0,
            },
        }
    )

    expected_custom = build_palette_theme_preset(
        "#1d4ed8",
        line_color="#9a9996",
        tint_color="#9a9996",
        tint_intensity=0,
        color_depth=0,
    )

    assert response["ok"] is True
    assert response["custom_theme"]["tint_intensity"] == 0
    assert response["custom_theme"]["color_depth"] == 0
    assert settings.selected_preset_tokens() == expected_custom


def test_theme_settings_preview_request_does_not_persist_runtime_state() -> None:
    settings = ThemePresetSettings(
        presets=default_theme_presets(),
        selected_preset="default",
        settings_path=None,
    )

    response = settings.apply_settings(
        {
            "preset_name": "custom",
            "preview_only": True,
            "custom_theme": {
                "base_color": "#1d4ed8",
                "line_color": "#ef4444",
                "tint_color": "#64748b",
                "tint_intensity": 83,
                "color_depth": 91,
            },
        }
    )

    assert response["ok"] is True
    assert response["selected_preset"] == "custom"
    assert response["custom_theme"]["tint_intensity"] == 83
    assert response["custom_theme"]["color_depth"] == 91
    assert settings.selected_preset_name() == "default"
    assert settings.custom_theme_settings() == {
        "base_color": DEFAULT_CUSTOM_THEME_BASE_COLOR,
        "line_color": DEFAULT_CUSTOM_THEME_LINE_COLOR,
        "tint_color": DEFAULT_CUSTOM_THEME_TINT_COLOR,
        "tint_intensity": DEFAULT_CUSTOM_THEME_TINT_INTENSITY,
        "color_depth": DEFAULT_CUSTOM_THEME_COLOR_DEPTH,
    }


def test_theme_settings_request_parser_supports_preview_only() -> None:
    request = parse_theme_settings_request(
        b'{"preset_name":"custom","preview_only":true,"custom_theme":{"tint_intensity":77}}'
    )

    assert request.preset_name == "custom"
    assert request.preview_only is True
    assert request.custom_theme == {"tint_intensity": 77}


def test_tint_intensity_generates_clear_surface_spread() -> None:
    def _hex_to_rgb(value: str) -> tuple[int, int, int]:
        return (
            int(value[1:3], 16),
            int(value[3:5], 16),
            int(value[5:7], 16),
        )

    def _rgb_distance(start: str, end: str) -> int:
        start_rgb = _hex_to_rgb(start)
        end_rgb = _hex_to_rgb(end)
        return sum(abs(end_channel - start_channel) for start_channel, end_channel in zip(start_rgb, end_rgb))

    neutral = build_palette_theme_preset(
        "#2563eb",
        line_color="#9a9996",
        tint_color="#2563eb",
        tint_intensity=0,
        color_depth=0,
    )
    vivid = build_palette_theme_preset(
        "#2563eb",
        line_color="#9a9996",
        tint_color="#2563eb",
        tint_intensity=100,
        color_depth=0,
    )

    assert neutral["light"]["--surface-tint-bg"] == "#ffffff"
    assert neutral["dark"]["--surface-tint-bg"] == "#0c1d2f"
    assert neutral["light"]["--surface-tint-alpha-mult"] == "0"
    assert vivid["light"]["--surface-tint-alpha-mult"] == "1"
    assert _rgb_distance(neutral["light"]["--surface-tint-bg"], vivid["light"]["--surface-tint-bg"]) >= 90
    assert _rgb_distance(neutral["dark"]["--surface-tint-bg"], vivid["dark"]["--surface-tint-bg"]) >= 55
    assert vivid["light"]["--surface-tint-border"] != neutral["light"]["--surface-tint-border"]
    assert vivid["dark"]["--surface-tint-border"] != neutral["dark"]["--surface-tint-border"]


def test_theme_customization_controls_are_rendered_and_wired() -> None:
    html = render_html(
        refresh_ms=1000,
        packet_limit=200,
        show_secrets=False,
        history_enabled=True,
        history_max_rows=200,
        history_retention_days=7,
        node_history_hours=24,
        node_history_max_points=240,
        revision_label="test",
        revision_title="test",
    )
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'id="theme-custom-base-color"' in html
    assert 'id="theme-custom-line-color"' in html
    assert 'id="theme-custom-tint-color"' in html
    assert 'id="theme-custom-tint-intensity"' in html
    assert 'id="theme-custom-tint-intensity-value"' in html
    assert 'id="theme-custom-color-depth"' in html
    assert 'id="theme-custom-color-depth-value"' in html
    assert 'id="settings-appearance-badge-emoji"' not in html
    assert 'id="theme-live-preview"' in html
    assert 'id="theme-live-preview-status"' in html
    assert '<option value="custom">custom</option>' in html
    assert "Fresh installs default to Meshyface blue with a neutral gray line and tint" in html
    assert 'value="#2563eb"' in html
    assert 'value="#9a9996"' in html
    assert 'value="50"' in html
    assert '>50%</output>' in html
    assert "Live preview" in html
    assert "Primary shell" in html
    assert "Shared tint surfaces" in html
    assert "Tint-backed utility chrome" in html
    assert "Tint color drives the shared shell tint used by help notes, console chrome" in html
    assert "Tint intensity scales that shared tint from neutral up to a clearly visible wash" in html
    assert "Badge shows in the workspace launcher square" not in html
    assert "Off leaves untagged node and chat surfaces neutral" in html

    assert 'let themePresetSelected = "custom";' in js
    assert 'let themeCustomBaseColor = "#2563eb";' in js
    assert 'let themeCustomLineColor = "#9a9996";' in js
    assert 'let themeCustomTintColor = "#9a9996";' in js
    assert "let themeCustomTintIntensity = 50;" in js
    assert "let themeCustomColorDepth = 50;" in js
    assert 'const settingsBadgeEmojiStorageKey = "meshDashboardSettingsBadgeEmojiV1";' not in js
    assert "function formatThemePresetLabel(name) {" in js
    assert 'return "green";' in js
    assert "function normalizeThemeCustomSettings(rawSettings) {" in js
    assert "function normalizeThemeCustomLineColor(raw, fallback = \"#9a9996\") {" in js
    assert "function normalizeThemeCustomTintColor(raw, fallback = \"#9a9996\") {" in js
    assert "function normalizeThemeCustomTintIntensity(raw) {" in js
    assert "function normalizeSettingsBadgeEmoji(value) {" not in js
    assert "function setThemeLivePreviewStatus(message = \"Updates while you drag.\", resetDelayMs = 0) {" in js
    assert "function buildCurrentThemeCustomOptions(extraOptions = null) {" in js
    assert "function queueLiveThemePreview() {" in js
    assert "function persistThemeCustomControls() {" in js
    assert "function syncThemeCustomControls() {" in js
    assert "function buildThemeSettingsSavePayload(options = null) {" in js
    assert "preview_only: Boolean(opts.previewOnly)," in js
    assert "custom_theme: {" in js
    assert 'presetName: opts.presetName == null ? "custom" : opts.presetName' in js
    assert "function bindThemeCustomControls() {" in js
    assert 'runBootStep("bindThemeCustomControls", () => bindThemeCustomControls());' in js
    assert 'controlId === "settings-appearance-badge-emoji"' not in js
    assert 'controlId === "theme-custom-base-color"' in js
    assert 'controlId === "theme-custom-line-color"' in js
    assert 'controlId === "theme-custom-tint-color"' in js
    assert 'controlId === "theme-custom-tint-intensity"' in js
    assert 'controlId === "theme-custom-color-depth"' in js
    assert "payload.custom_theme" in js
