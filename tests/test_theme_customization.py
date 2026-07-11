import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.api_input_theme import parse_theme_settings_request
from meshdash.html_js import build_dashboard_js
from meshdash.html_template import render_html
from meshdash.theme import (
    DEFAULT_CUSTOM_THEME_BACKGROUND_TYPE,
    DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_DATA,
    DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_DARKEN,
    DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_LAYOUT,
    DEFAULT_CUSTOM_THEME_BASE_COLOR,
    DEFAULT_CUSTOM_THEME_COLOR_DEPTH,
    DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_DIRECTION,
    DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_END_COLOR,
    DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_START_COLOR,
    DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_TYPE,
    DEFAULT_CUSTOM_THEME_FOREGROUND_BLUR,
    DEFAULT_CUSTOM_THEME_FOREGROUND_TRANSPARENCY,
    DEFAULT_CUSTOM_THEME_LIVEMAP_LAYERS,
    DEFAULT_CUSTOM_THEME_LIVEMAP_LINK_COLOR,
    DEFAULT_CUSTOM_THEME_LINE_CONTRAST_COLOR,
    DEFAULT_CUSTOM_THEME_LINE_COLOR,
    DEFAULT_CUSTOM_THEME_PARTICLES_COLOR,
    DEFAULT_CUSTOM_THEME_PARTICLES_COUNT,
    DEFAULT_CUSTOM_THEME_PARTICLES_ENABLED,
    DEFAULT_CUSTOM_THEME_PARTICLES_LINK_COLOR,
    DEFAULT_CUSTOM_THEME_PARTICLES_LINKS,
    DEFAULT_CUSTOM_THEME_PARTICLES_OPACITY,
    DEFAULT_CUSTOM_THEME_PARTICLES_SIZE,
    DEFAULT_CUSTOM_THEME_PARTICLES_SPEED,
    DEFAULT_CUSTOM_THEME_TEXT_FONT,
    build_palette_theme_preset,
    normalize_theme_background_image_data,
    normalize_theme_background_image_darken,
    normalize_theme_background_image_layout,
    normalize_theme_background_type,
    normalize_theme_particles_speed,
)
from meshdash.theme_presets import (
    default_theme_preset_custom_settings,
    default_theme_presets,
    load_theme_presets,
    select_theme_preset,
)
from meshdash.theme_settings import ThemePresetSettings


def _default_custom_gradient_settings() -> dict[str, object]:
    return {
        "gradient_primary_start_color": DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_START_COLOR,
        "gradient_primary_end_color": DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_END_COLOR,
        "gradient_primary_type": DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_TYPE,
        "gradient_primary_direction": DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_DIRECTION,
        "foreground_transparency": DEFAULT_CUSTOM_THEME_FOREGROUND_TRANSPARENCY,
        "foreground_blur": DEFAULT_CUSTOM_THEME_FOREGROUND_BLUR,
    }


def _default_custom_particles_settings() -> dict[str, object]:
    return {
        "background_type": DEFAULT_CUSTOM_THEME_BACKGROUND_TYPE,
        "background_image_data": DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_DATA,
        "background_image_layout": DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_LAYOUT,
        "background_image_darken": DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_DARKEN,
        "particles_enabled": DEFAULT_CUSTOM_THEME_PARTICLES_ENABLED,
        "particles_color": DEFAULT_CUSTOM_THEME_PARTICLES_COLOR,
        "particles_link_color": DEFAULT_CUSTOM_THEME_PARTICLES_LINK_COLOR,
        "livemap_link_color": DEFAULT_CUSTOM_THEME_LIVEMAP_LINK_COLOR,
        "particles_count": DEFAULT_CUSTOM_THEME_PARTICLES_COUNT,
        "particles_speed": DEFAULT_CUSTOM_THEME_PARTICLES_SPEED,
        "particles_size": DEFAULT_CUSTOM_THEME_PARTICLES_SIZE,
        "particles_opacity": DEFAULT_CUSTOM_THEME_PARTICLES_OPACITY,
        "particles_links": DEFAULT_CUSTOM_THEME_PARTICLES_LINKS,
        "livemap_layers": DEFAULT_CUSTOM_THEME_LIVEMAP_LAYERS,
    }


def _default_custom_theme_settings() -> dict[str, object]:
    return {
        "base_color": DEFAULT_CUSTOM_THEME_BASE_COLOR,
        "line_color": DEFAULT_CUSTOM_THEME_LINE_COLOR,
        "line_contrast_color": DEFAULT_CUSTOM_THEME_LINE_CONTRAST_COLOR,
        "text_font": DEFAULT_CUSTOM_THEME_TEXT_FONT,
        "color_depth": DEFAULT_CUSTOM_THEME_COLOR_DEPTH,
        **_default_custom_gradient_settings(),
        **_default_custom_particles_settings(),
    }


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    rgba_match = re.fullmatch(
        r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*[0-9.]+)?\s*\)",
        value,
    )
    if rgba_match:
        return tuple(int(channel) for channel in rgba_match.groups())
    return (
        int(value[1:3], 16),
        int(value[3:5], 16),
        int(value[5:7], 16),
    )


def _rgb_distance(first: str, second: str) -> int:
    return sum(abs(a - b) for a, b in zip(_hex_to_rgb(first), _hex_to_rgb(second)))


def _channel_luminance(channel: int) -> float:
    normalized = max(0.0, min(1.0, float(channel) / 255.0))
    if normalized <= 0.04045:
        return normalized / 12.92
    return ((normalized + 0.055) / 1.055) ** 2.4


def _relative_luminance(value: str) -> float:
    red, green, blue = _hex_to_rgb(value)
    return (
        (0.2126 * _channel_luminance(red))
        + (0.7152 * _channel_luminance(green))
        + (0.0722 * _channel_luminance(blue))
    )


def _contrast_ratio(foreground: str, background: str) -> float:
    fg_luminance = _relative_luminance(foreground)
    bg_luminance = _relative_luminance(background)
    lighter = max(fg_luminance, bg_luminance)
    darker = min(fg_luminance, bg_luminance)
    return (lighter + 0.05) / (darker + 0.05)


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


def test_builtin_default_theme_is_fixed_safe_mode_with_particles_disabled() -> None:
    presets = default_theme_presets()
    default_settings = default_theme_preset_custom_settings()["default"]

    assert "blue" not in presets
    assert presets["default"]["dark"]["--theme-base-color"] == "#003a73"
    assert default_settings["base_color"] == "#003a73"
    assert default_settings["line_color"] == "#2f8cff"
    assert default_settings["line_contrast_color"] == "#d8ecff"
    assert default_settings["gradient_primary_start_color"] == "#003a73"
    assert default_settings["gradient_primary_end_color"] == "#060d1f"
    assert default_settings["background_image_darken"] == 0
    assert default_settings["particles_enabled"] is False
    assert default_settings["particles_link_color"] == "#d8ecff"
    assert default_settings["livemap_link_color"] == "#d8ecff"
    assert default_settings["particles_links"] is False
    assert default_settings["livemap_layers"] == DEFAULT_CUSTOM_THEME_LIVEMAP_LAYERS

    settings = ThemePresetSettings(
        presets=presets,
        selected_preset=None,
        settings_path=None,
    )

    payload = settings.get_settings_payload()
    payload_default_settings = payload["preset_custom_settings"]["default"]

    assert payload["selected_preset"] == "default"
    assert "default" in payload["available_presets"]
    assert "blue" not in payload["available_presets"]
    assert "default" not in payload["custom_preset_names"]
    assert payload_default_settings["particles_enabled"] is False
    assert payload_default_settings["particles_link_color"] == "#d8ecff"
    assert payload_default_settings["livemap_link_color"] == "#d8ecff"
    assert payload_default_settings["particles_links"] is False
    assert payload_default_settings["livemap_layers"] == DEFAULT_CUSTOM_THEME_LIVEMAP_LAYERS


def test_selecting_default_uses_fixed_particle_settings_instead_of_custom_particles() -> None:
    settings = ThemePresetSettings(
        presets=default_theme_presets(),
        selected_preset="custom",
        settings_path=None,
    )
    custom_response = settings.apply_settings(
        {
            "preset_name": "custom",
            "custom_theme": {
                "base_color": "#1d4ed8",
                "particles_enabled": True,
                "particles_links": True,
                "particles_count": 240,
            },
        }
    )

    default_response = settings.apply_settings({"preset_name": "default"})

    assert custom_response["custom_theme"]["particles_enabled"] is True
    assert default_response["selected_preset"] == "default"
    assert default_response["custom_theme"]["particles_enabled"] is True
    assert default_response["preset_custom_settings"]["default"]["particles_enabled"] is False
    assert default_response["preset_custom_settings"]["default"]["particles_link_color"] == "#d8ecff"
    assert default_response["preset_custom_settings"]["default"]["livemap_link_color"] == "#d8ecff"
    assert default_response["preset_custom_settings"]["default"]["particles_links"] is False
    assert default_response["preset_custom_settings"]["default"]["livemap_layers"] == DEFAULT_CUSTOM_THEME_LIVEMAP_LAYERS
    assert settings.selected_preset_tokens() == default_response["presets"]["default"]


def test_legacy_blue_selection_maps_to_default_safe_mode() -> None:
    settings = ThemePresetSettings(
        presets=default_theme_presets(),
        selected_preset="blue",
        settings_path=None,
    )

    response = settings.apply_settings({"preset_name": "blue"})

    assert response["ok"] is True
    assert settings.selected_preset_name() == "default"
    assert response["selected_preset"] == "default"
    assert "blue" not in response["available_presets"]
    assert response["preset_custom_settings"]["default"]["particles_enabled"] is False


def test_theme_settings_support_generated_custom_theme_state() -> None:
    settings = ThemePresetSettings(
        presets=default_theme_presets(),
        selected_preset="default",
        settings_path=None,
    )
    background_image_data = "data:image/png;base64,iVBORw0KGgo="

    response = settings.apply_settings(
        {
            "preset_name": "custom",
            "custom_theme": {
                "base_color": "#1d4ed8",
                "line_color": "#ef4444",
                "line_contrast_color": "#020617",
                "tint_color": "#64748b",
                "tint_intensity": 61,
                "text_color": "#f8fafc",
                "text_font": "mono",
                "color_depth": 72,
                "foreground_transparency": 37,
                "foreground_blur": 12,
                "gradient_primary_start_color": "#111827",
                "gradient_primary_end_color": "#22c55e",
                "gradient_primary_type": "radial",
                "gradient_primary_direction": "down-left",
                "background_type": "image",
                "background_image_data": background_image_data,
                "background_image_layout": "tile",
                "background_image_darken": 34,
                "particles_enabled": True,
                "particles_color": "#facc15",
                "particles_link_color": "#38bdf8",
                "livemap_link_color": "#22c55e",
                "particles_count": 144,
                "particles_speed": 5,
                "particles_size": 4,
                "particles_opacity": 63,
                "particles_links": False,
                "livemap_layers": {
                    "roads": False,
                    "cities": False,
                },
            },
        }
    )

    expected_custom = build_palette_theme_preset(
        "#1d4ed8",
        line_color="#ef4444",
        line_contrast_color="#020617",
        text_font="mono",
        color_depth=72,
        foreground_transparency=37,
        foreground_blur=12,
        gradient_primary_start_color="#111827",
        gradient_primary_end_color="#22c55e",
        gradient_primary_type="radial",
        gradient_primary_direction="down-left",
    )
    default_line_custom = build_palette_theme_preset("#1d4ed8", color_depth=72)

    assert response["ok"] is True
    assert response["selected_preset"] == "custom"
    assert response["custom_theme"] == {
        "base_color": "#1d4ed8",
        "line_color": "#ef4444",
        "line_contrast_color": "#020617",
        "text_font": "mono",
        "color_depth": 72,
        "foreground_transparency": 37,
        "foreground_blur": 12,
        "gradient_primary_start_color": "#111827",
        "gradient_primary_end_color": "#22c55e",
        "gradient_primary_type": "radial",
        "gradient_primary_direction": "down-left",
        "background_type": "image",
        "background_image_data": background_image_data,
        "background_image_layout": "tile",
        "background_image_darken": 34,
        "particles_enabled": True,
        "particles_color": "#facc15",
        "particles_link_color": "#38bdf8",
        "livemap_link_color": "#22c55e",
        "particles_count": 144,
        "particles_speed": 5,
        "particles_size": 4,
        "particles_opacity": 63,
        "particles_links": False,
        "livemap_layers": {
            **DEFAULT_CUSTOM_THEME_LIVEMAP_LAYERS,
            "roads": False,
            "cities": False,
        },
    }
    assert "custom" in response["available_presets"]
    assert response["presets"]["custom"] == expected_custom
    assert response["presets"]["custom"]["light"]["--theme-base-color"] == "#1d4ed8"
    assert response["presets"]["custom"]["dark"]["--theme-base-color"] == "#1d4ed8"
    assert response["presets"]["custom"]["dark"]["--theme-background-gradient"] == (
        "radial-gradient(circle at top right, #111827, #22c55e)"
    )
    assert response["presets"]["custom"]["dark"]["--theme-gradient-primary"] == (
        "radial-gradient(circle at top right, #111827, #22c55e)"
    )
    assert (
        response["presets"]["custom"]["dark"]["--theme-gradient-secondary"]
        == response["presets"]["custom"]["dark"]["--theme-gradient-primary"]
    )
    assert response["presets"]["custom"]["light"]["--surface-tint-divider-bg"].startswith("linear-gradient(")
    assert response["presets"]["custom"]["dark"]["--surface-tint-divider-bg"].startswith("linear-gradient(")
    assert response["presets"]["custom"]["light"]["--surface-tint-divider-bg"] != (
        response["presets"]["custom"]["light"]["--theme-gradient-primary"]
    )
    assert response["presets"]["custom"]["dark"]["--surface-tint-divider-bg"] != (
        response["presets"]["custom"]["dark"]["--theme-gradient-primary"]
    )
    assert response["presets"]["custom"]["dark"]["--theme-foreground-transparency"] == "37"
    assert response["presets"]["custom"]["dark"]["--theme-foreground-blur"] == "blur(12px)"
    assert response["presets"]["custom"]["light"]["--theme-foreground-blur"] == "blur(12px)"
    assert response["presets"]["custom"]["dark"]["--theme-font-family"].startswith("ui-monospace")
    assert "text_color" not in response["custom_theme"]
    assert "tint_color" not in response["custom_theme"]
    assert "tint_intensity" not in response["custom_theme"]
    assert response["presets"]["custom"]["dark"]["--theme-text-color"] != "#f8fafc"
    assert _relative_luminance(response["presets"]["custom"]["dark"]["--theme-text-color"]) >= 0.72
    assert response["presets"]["custom"]["dark"]["--workspace-shell-bg"].startswith("rgba(")
    assert response["presets"]["custom"]["dark"]["--workspace-shell-border"] != default_line_custom["dark"]["--workspace-shell-border"]
    assert settings.selected_preset_name() == "custom"
    assert settings.selected_preset_tokens() == expected_custom


def test_theme_particle_speed_supports_fractional_slow_values() -> None:
    settings = ThemePresetSettings(
        presets=default_theme_presets(),
        selected_preset="custom",
        settings_path=None,
    )

    response = settings.apply_settings(
        {
            "preset_name": "custom",
            "custom_theme": {"particles_speed": "0.4"},
        }
    )

    assert normalize_theme_particles_speed("0.4") == 0.4
    assert normalize_theme_particles_speed("-1") == 0
    assert normalize_theme_particles_speed("12.9") == 12
    assert normalize_theme_particles_speed("nan", fallback=1.7) == 1.7
    assert response["custom_theme"]["particles_speed"] == 0.4
    assert settings.custom_theme_settings()["particles_speed"] == 0.4


def test_theme_background_type_normalizes_and_persists() -> None:
    assert normalize_theme_background_type(None) == "particles"
    assert normalize_theme_background_type("") == "particles"
    assert normalize_theme_background_type("garbage") == "particles"
    assert normalize_theme_background_type("particles") == "particles"
    assert normalize_theme_background_type("livemap") == "livemap"
    assert normalize_theme_background_type("LIVE-MAP") == "livemap"
    assert normalize_theme_background_type("live_map") == "livemap"
    assert normalize_theme_background_type("map") == "livemap"
    assert normalize_theme_background_type("image") == "image"
    assert normalize_theme_background_type("garbage", fallback="livemap") == "livemap"
    assert normalize_theme_background_type("garbage", fallback="image") == "image"

    settings = ThemePresetSettings(
        presets=default_theme_presets(),
        selected_preset="custom",
        settings_path=None,
    )
    response = settings.apply_settings(
        {
            "preset_name": "custom",
            "custom_theme": {"background_type": "livemap"},
        }
    )

    assert response["ok"] is True
    assert response["custom_theme"]["background_type"] == "livemap"
    assert settings.custom_theme_settings()["background_type"] == "livemap"

    invalid = settings.apply_settings(
        {
            "preset_name": "custom",
            "custom_theme": {"background_type": "not-a-background"},
        }
    )
    assert invalid["custom_theme"]["background_type"] == "livemap"

    assert default_theme_preset_custom_settings()["default"]["background_type"] == "particles"


def test_theme_background_image_settings_normalize_and_persist() -> None:
    image_data = "data:image/webp;base64,UklGRiIAAABXRUJQVlA4IBYAAAAwAQCdASoBAAEADsD+JaQAA3AA/vuUAAA="

    assert normalize_theme_background_image_data(None) == ""
    assert normalize_theme_background_image_data("https://example.test/image.png") == ""
    assert normalize_theme_background_image_data("data:image/svg+xml;base64,PHN2Zz4=") == ""
    assert normalize_theme_background_image_data(image_data) == image_data
    assert normalize_theme_background_image_data("bad", fallback=image_data) == image_data
    assert normalize_theme_background_image_layout(None) == "cover"
    assert normalize_theme_background_image_layout("fit") == "contain"
    assert normalize_theme_background_image_layout("stretched") == "stretch"
    assert normalize_theme_background_image_layout("repeat") == "tile"
    assert normalize_theme_background_image_layout("garbage", fallback="center") == "center"
    assert normalize_theme_background_image_darken(None) == 0
    assert normalize_theme_background_image_darken("22") == 22
    assert normalize_theme_background_image_darken("200") == 100
    assert normalize_theme_background_image_darken("bad", fallback=19) == 19

    settings = ThemePresetSettings(
        presets=default_theme_presets(),
        selected_preset="custom",
        settings_path=None,
    )
    response = settings.apply_settings(
        {
            "preset_name": "custom",
            "custom_theme": {
                "background_type": "image",
                "background_image_data": image_data,
                "background_image_layout": "repeat",
                "background_image_darken": "27",
            },
        }
    )

    assert response["ok"] is True
    assert response["custom_theme"]["background_type"] == "image"
    assert response["custom_theme"]["background_image_data"] == image_data
    assert response["custom_theme"]["background_image_layout"] == "tile"
    assert response["custom_theme"]["background_image_darken"] == 27
    assert settings.custom_theme_settings()["background_image_data"] == image_data


def test_render_html_preloads_initial_image_background() -> None:
    image_data = "data:image/png;base64,AAAA"
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
        initial_background_settings={
            "background_type": "image",
            "background_image_data": image_data,
            "background_image_layout": "tile",
            "background_image_darken": 35,
        },
    )

    assert '<body class="dashboard-image-enabled">' in html
    assert (
        'class="dashboard-image-bg dashboard-background-ready '
        'dashboard-background-active"'
    ) in html
    assert f"background-image: url('{image_data}');" in html
    assert f'style="background-image: url("{image_data}")' not in html
    assert "background-size: auto;" in html
    assert "background-repeat: repeat;" in html
    assert "--dashboard-image-darken: 0.35;" in html
    assert 'data-dashboard-background-signature="image:tile:data:image/png;base64,AAAA"' in html


def test_render_html_preloads_initial_particles_and_livemap_background_classes() -> None:
    particles_html = render_html(
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
        initial_background_settings={
            "background_type": "particles",
            "particles_enabled": True,
            "particles_opacity": 88,
        },
    )
    livemap_html = render_html(
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
        initial_background_settings={"background_type": "livemap"},
    )

    assert '<body class="dashboard-particles-enabled">' in particles_html
    assert (
        'id="dashboard-particles-bg" class="dashboard-particles-bg" '
        'aria-hidden="true" style="--dashboard-particles-opacity: 0.88;"'
    ) in particles_html
    assert '<body class="dashboard-livemap-enabled">' in livemap_html
    assert 'id="dashboard-livemap-bg" class="dashboard-livemap-bg"' in livemap_html


def test_theme_settings_custom_palette_defaults_remain_editable_custom_seed() -> None:
    settings = ThemePresetSettings(
        presets=default_theme_presets(),
        selected_preset="custom",
        settings_path=None,
    )

    expected_custom = build_palette_theme_preset(
        DEFAULT_CUSTOM_THEME_BASE_COLOR,
        line_color=DEFAULT_CUSTOM_THEME_LINE_COLOR,
        line_contrast_color=DEFAULT_CUSTOM_THEME_LINE_CONTRAST_COLOR,
        text_font=DEFAULT_CUSTOM_THEME_TEXT_FONT,
        color_depth=DEFAULT_CUSTOM_THEME_COLOR_DEPTH,
        gradient_primary_start_color=DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_START_COLOR,
        gradient_primary_end_color=DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_END_COLOR,
        gradient_primary_type=DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_TYPE,
        gradient_primary_direction=DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_DIRECTION,
        foreground_transparency=DEFAULT_CUSTOM_THEME_FOREGROUND_TRANSPARENCY,
    )

    assert settings.selected_preset_name() == "custom"
    assert settings.custom_theme_settings() == {
        "base_color": DEFAULT_CUSTOM_THEME_BASE_COLOR,
        "line_color": DEFAULT_CUSTOM_THEME_LINE_COLOR,
        "line_contrast_color": DEFAULT_CUSTOM_THEME_LINE_CONTRAST_COLOR,
        "text_font": DEFAULT_CUSTOM_THEME_TEXT_FONT,
        "color_depth": DEFAULT_CUSTOM_THEME_COLOR_DEPTH,
        **_default_custom_gradient_settings(),
        **_default_custom_particles_settings(),
    }
    assert settings.selected_preset_tokens() == expected_custom


def test_theme_settings_ignore_legacy_tint_inputs() -> None:
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
        line_contrast_color=DEFAULT_CUSTOM_THEME_LINE_CONTRAST_COLOR,
        text_font=DEFAULT_CUSTOM_THEME_TEXT_FONT,
        color_depth=0,
        gradient_primary_start_color=DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_START_COLOR,
        gradient_primary_end_color=DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_END_COLOR,
        gradient_primary_type=DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_TYPE,
        gradient_primary_direction=DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_DIRECTION,
        foreground_transparency=DEFAULT_CUSTOM_THEME_FOREGROUND_TRANSPARENCY,
    )

    assert response["ok"] is True
    assert "tint_color" not in response["custom_theme"]
    assert "tint_intensity" not in response["custom_theme"]
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
    assert "tint_color" not in response["custom_theme"]
    assert "tint_intensity" not in response["custom_theme"]
    assert response["custom_theme"]["color_depth"] == 91
    assert settings.selected_preset_name() == "default"
    assert settings.custom_theme_settings() == {
        "base_color": DEFAULT_CUSTOM_THEME_BASE_COLOR,
        "line_color": DEFAULT_CUSTOM_THEME_LINE_COLOR,
        "line_contrast_color": DEFAULT_CUSTOM_THEME_LINE_CONTRAST_COLOR,
        "text_font": DEFAULT_CUSTOM_THEME_TEXT_FONT,
        "color_depth": DEFAULT_CUSTOM_THEME_COLOR_DEPTH,
        **_default_custom_gradient_settings(),
        **_default_custom_particles_settings(),
    }


def test_theme_settings_request_parser_supports_preview_only() -> None:
    request = parse_theme_settings_request(
        b'{"preset_name":"custom","preview_only":true,"custom_theme":{"tint_intensity":77}}'
    )

    assert request.preset_name == "custom"
    assert request.preview_only is True
    assert request.custom_theme == {"tint_intensity": 77}
    assert request.action == "select"
    assert request.new_preset_label is None


def test_theme_settings_request_parser_supports_save_and_rename_actions() -> None:
    save_request = parse_theme_settings_request(
        b'{"action":"save","preset_name":"Sunset","custom_theme":{"base_color":"#ff8800"}}'
    )
    assert save_request.action == "save"
    assert save_request.preset_name == "Sunset"

    rename_request = parse_theme_settings_request(
        b'{"action":"rename","preset_name":"Sunset","new_preset_label":"Dusk"}'
    )
    assert rename_request.action == "rename"
    assert rename_request.preset_name == "Sunset"
    assert rename_request.new_preset_label == "Dusk"


def test_theme_settings_save_named_preset_adds_it_to_catalog_and_selects_it(tmp_path) -> None:
    settings_path = tmp_path / "theme-settings.json"
    settings = ThemePresetSettings(
        presets=default_theme_presets(),
        selected_preset="default",
        settings_path=str(settings_path),
    )

    response = settings.apply_settings(
        {
            "action": "save",
            "preset_name": "Sunset",
            "custom_theme": {"base_color": "#ff8800", "color_depth": 60},
        }
    )

    assert response["ok"] is True
    assert response["selected_preset"] == "Sunset"
    assert "Sunset" in response["available_presets"]
    assert response["custom_preset_names"] == ["Sunset"]
    assert response["presets"]["Sunset"]["dark"]["--theme-base-color"] == "#ff8800"
    assert settings.selected_preset_name() == "Sunset"
    assert settings.selected_preset_tokens() == response["presets"]["Sunset"]

    reloaded = ThemePresetSettings(
        presets=default_theme_presets(),
        selected_preset="default",
        settings_path=str(settings_path),
    )
    assert reloaded.selected_preset_name() == "Sunset"
    assert "Sunset" in reloaded.available_presets()
    assert reloaded.preset_catalog()["Sunset"]["dark"]["--theme-base-color"] == "#ff8800"


def test_theme_settings_save_rejects_reserved_names() -> None:
    settings = ThemePresetSettings(
        presets=default_theme_presets(),
        selected_preset="default",
        settings_path=None,
    )

    for reserved_name in ("custom", "default"):
        response = settings.apply_settings({"action": "save", "preset_name": reserved_name})
        assert response["ok"] is False
        assert "reserved" in response["error"]
        assert settings.selected_preset_name() == "default"


def test_theme_settings_update_overwrites_existing_named_preset() -> None:
    settings = ThemePresetSettings(
        presets=default_theme_presets(),
        selected_preset="default",
        settings_path=None,
    )
    settings.apply_settings(
        {"action": "save", "preset_name": "Sunset", "custom_theme": {"base_color": "#ff8800"}}
    )

    response = settings.apply_settings(
        {"action": "save", "preset_name": "Sunset", "custom_theme": {"base_color": "#112233"}}
    )

    assert response["ok"] is True
    assert response["custom_preset_names"] == ["Sunset"]
    assert response["presets"]["Sunset"]["dark"]["--theme-base-color"] == "#112233"


def test_theme_settings_rename_named_preset_updates_selection() -> None:
    settings = ThemePresetSettings(
        presets=default_theme_presets(),
        selected_preset="default",
        settings_path=None,
    )
    settings.apply_settings(
        {"action": "save", "preset_name": "Sunset", "custom_theme": {"base_color": "#ff8800"}}
    )

    response = settings.apply_settings(
        {"action": "rename", "preset_name": "Sunset", "new_preset_label": "Dusk"}
    )

    assert response["ok"] is True
    assert response["selected_preset"] == "Dusk"
    assert response["custom_preset_names"] == ["Dusk"]
    assert "Sunset" not in response["available_presets"]
    assert settings.selected_preset_name() == "Dusk"


def test_theme_settings_rename_rejects_unknown_or_colliding_names() -> None:
    settings = ThemePresetSettings(
        presets=default_theme_presets(),
        selected_preset="default",
        settings_path=None,
    )
    settings.apply_settings(
        {"action": "save", "preset_name": "Sunset", "custom_theme": {"base_color": "#ff8800"}}
    )

    missing = settings.apply_settings(
        {"action": "rename", "preset_name": "Nope", "new_preset_label": "Whatever"}
    )
    assert missing["ok"] is False

    collides_with_builtin = settings.apply_settings(
        {"action": "rename", "preset_name": "Sunset", "new_preset_label": "default"}
    )
    assert collides_with_builtin["ok"] is False
    assert settings.selected_preset_name() == "Sunset"


def test_theme_settings_delete_named_preset_falls_back_to_default_safe_mode() -> None:
    settings = ThemePresetSettings(
        presets=default_theme_presets(),
        selected_preset="default",
        settings_path=None,
    )
    settings.apply_settings(
        {"action": "save", "preset_name": "Sunset", "custom_theme": {"base_color": "#ff8800"}}
    )
    assert settings.selected_preset_name() == "Sunset"

    response = settings.apply_settings({"action": "delete", "preset_name": "Sunset"})

    assert response["ok"] is True
    assert response["selected_preset"] == "default"
    assert "Sunset" not in response["available_presets"]
    assert response["custom_preset_names"] == []
    assert settings.selected_preset_name() == "default"

    missing = settings.apply_settings({"action": "delete", "preset_name": "Sunset"})
    assert missing["ok"] is False


def test_legacy_tint_settings_are_ignored_by_palette_preset() -> None:
    neutral = build_palette_theme_preset(
        "#2563eb",
        line_color="#9a9996",
        tint_color="#000000",
        tint_intensity=0,
        color_depth=0,
    )
    vivid = build_palette_theme_preset(
        "#2563eb",
        line_color="#9a9996",
        tint_color="#ff000d",
        tint_intensity=100,
        color_depth=0,
    )

    assert neutral == vivid


def test_line_contrast_color_controls_dark_line_shading() -> None:
    default_contrast = build_palette_theme_preset(
        "#000000",
        line_color="#000000",
        line_contrast_color="#ffffff",
        tint_color="#3654a8",
        color_depth=100,
    )
    dark_contrast = build_palette_theme_preset(
        "#000000",
        line_color="#000000",
        line_contrast_color="#000000",
        tint_color="#3654a8",
        color_depth=100,
    )

    assert default_contrast["dark"]["--workspace-shell-border"] == "#7d7e84"
    assert dark_contrast["dark"]["--workspace-shell-border"] == "#07080d"
    assert dark_contrast["dark"]["--workspace-shell-border-muted"] != (
        default_contrast["dark"]["--workspace-shell-border-muted"]
    )
    assert dark_contrast["dark"]["--workspace-shell-border-strong"] != (
        default_contrast["dark"]["--workspace-shell-border-strong"]
    )


def test_dark_base_accent_lift_preserves_saturated_hue() -> None:
    preset = build_palette_theme_preset(
        "#7a0006",
        line_color="#1303ff",
        line_contrast_color="#3b0033",
        tint_color="#3654a8",
        tint_intensity=100,
        color_depth=100,
    )

    assert preset["dark"]["--theme-base-color"] == "#7a0006"
    assert preset["dark"]["--ui-accent-soft"] == "#ff1823"
    assert preset["dark"]["--ui-accent"] == "#ff868c"
    assert preset["dark"]["--ui-accent-soft"] != "#bb7d80"
    assert preset["dark"]["--ui-accent"] != "#d5b0b1"


def test_color_depth_drives_visible_hls_surface_variation() -> None:
    low_depth = build_palette_theme_preset(
        "#007bff",
        line_color="#0da6ff",
        line_contrast_color="#d8ecff",
        color_depth=0,
    )
    high_depth = build_palette_theme_preset(
        "#007bff",
        line_color="#0da6ff",
        line_contrast_color="#d8ecff",
        color_depth=100,
    )

    low_dark = low_depth["dark"]
    high_dark = high_depth["dark"]
    low_hue_spread = (
        int(low_dark["--surface-tint-end-hue"])
        - int(low_dark["--surface-tint-start-hue"])
    ) % 360
    high_hue_spread = (
        int(high_dark["--surface-tint-end-hue"])
        - int(high_dark["--surface-tint-start-hue"])
    ) % 360

    assert _rgb_distance(
        low_dark["--workspace-shell-bg"],
        high_dark["--workspace-shell-bg"],
    ) >= 72
    assert _rgb_distance(
        low_dark["--workspace-shell-bg-alt"],
        high_dark["--workspace-shell-bg-alt"],
    ) >= 72
    assert _rgb_distance(
        high_dark["--workspace-shell-bg"],
        high_dark["--workspace-shell-bg-alt"],
    ) <= 24
    assert _rgb_distance(
        high_dark["--ui-bg"],
        high_dark["--ui-bg-elev"],
    ) <= 24
    assert _rgb_distance(
        high_dark["--ui-panel"],
        high_dark["--ui-panel-alt"],
    ) <= 24
    assert high_dark["--surface-tint-bg"] == high_dark["--workspace-shell-bg"]
    assert high_dark["--surface-tint-bg-alt"] == high_dark["--workspace-shell-bg-alt"]
    assert high_hue_spread >= low_hue_spread + 32
    assert _contrast_ratio(
        high_dark["--workspace-shell-text"],
        high_dark["--workspace-shell-bg"],
    ) >= 4.5
    assert _contrast_ratio(
        high_dark["--theme-text-color"],
        high_dark["--workspace-shell-bg"],
    ) >= 7


def test_translucent_dark_surface_tokens_stay_native_unified() -> None:
    preset = build_palette_theme_preset(
        "#007aff",
        line_color="#0a84ff",
        line_contrast_color="#d8ecff",
        color_depth=81,
        foreground_transparency=51,
    )

    dark = preset["dark"]

    assert dark["--workspace-shell-bg"].startswith("rgba(")
    assert _rgb_distance(
        dark["--workspace-shell-bg"],
        dark["--workspace-shell-bg-alt"],
    ) <= 18
    assert _rgb_distance(
        dark["--ui-bg"],
        dark["--ui-bg-elev"],
    ) <= 18
    assert _rgb_distance(
        dark["--ui-panel"],
        dark["--ui-panel-alt"],
    ) <= 18
    assert dark["--surface-tint-bg"] == dark["--workspace-shell-bg"]
    assert dark["--surface-tint-bg-alt"] == dark["--workspace-shell-bg-alt"]


def test_custom_theme_text_color_seed_is_ignored_for_readable_auto_text() -> None:
    preset = build_palette_theme_preset(
        "#1199b8",
        line_color="#0034f2",
        tint_color="#97a891",
        color_depth=70,
        text_color="#ff146e",
    )
    alternate_text_seed = build_palette_theme_preset(
        "#1199b8",
        line_color="#0034f2",
        tint_color="#97a891",
        color_depth=70,
        text_color="#00ff00",
    )

    assert preset == alternate_text_seed
    assert _contrast_ratio(preset["light"]["--theme-text-color"], preset["light"]["--panel"]) >= 7
    assert _contrast_ratio(preset["dark"]["--theme-text-color"], preset["dark"]["--workspace-shell-bg"]) >= 7
    assert _contrast_ratio(preset["light"]["--theme-text-color-muted"], preset["light"]["--panel"]) >= 4.5
    assert _contrast_ratio(preset["dark"]["--theme-text-color-muted"], preset["dark"]["--workspace-shell-bg"]) >= 4.5
    assert preset["light"]["--theme-text-color"] != "#ff146e"
    assert preset["dark"]["--theme-text-color"] != "#ff146e"
    assert preset["dark"]["--theme-text-color-soft"] != preset["dark"]["--theme-text-color"]


def test_custom_light_theme_gradient_is_auto_lightened_and_text_stays_dark() -> None:
    # Light mode derives its own airy gradient from the same start/end colors
    # (same hue, pushed light) instead of reusing the dark-tuned gradient, so
    # a dark gradient input should not force light-on-light or white text.
    preset = build_palette_theme_preset(
        "#3b3eff",
        line_color="#0a85ff",
        tint_color="#5ac8fa",
        color_depth=29,
        foreground_transparency=76,
        gradient_primary_start_color="#0a0f70",
        gradient_primary_end_color="#000000",
        text_color="#0a0a0a",
    )

    light = preset["light"]
    dark = preset["dark"]

    assert light["--panel"].startswith("rgba(")
    assert light["--bg"].startswith("rgba(")
    assert light["--theme-text-color"] != "#0a0a0a"
    assert light["--theme-background-gradient"] != dark["--theme-background-gradient"]
    assert _relative_luminance(light["--ink"]) <= 0.05
    assert _relative_luminance(light["--muted"]) <= 0.3
    assert _relative_luminance(light["--theme-text-color-muted"]) <= 0.3
    assert _relative_luminance(light["--surface-tint-text"]) <= 0.05
    assert _relative_luminance(light["--surface-tint-text-soft"]) <= 0.3
    # Dark mode keeps the gradient exactly as the user configured it.
    assert dark["--theme-background-gradient"] == "linear-gradient(to right, #0a0f70, #000000)"


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
    css = (Path(__file__).resolve().parents[1] / "meshdash/assets/dashboard.css.base.tmpl").read_text(
        encoding="utf-8"
    )

    assert 'id="theme-custom-base-color"' in html
    assert 'id="theme-custom-line-color"' in html
    assert 'id="theme-custom-line-contrast-color"' in html
    assert 'id="theme-custom-tint-color"' not in html
    assert 'id="theme-custom-text-color"' not in html
    assert 'id="theme-custom-text-font"' in html
    assert 'id="theme-custom-tint-intensity"' not in html
    assert 'id="theme-custom-tint-intensity-value"' not in html
    assert 'id="theme-custom-color-depth"' in html
    assert 'id="theme-custom-color-depth-value"' in html
    assert 'id="theme-custom-foreground-transparency"' in html
    assert 'id="theme-custom-foreground-transparency-value"' in html
    assert 'id="theme-custom-foreground-blur"' in html
    assert 'id="theme-custom-foreground-blur-value"' in html
    assert 'id="theme-custom-gradient-primary-start-color"' in html
    assert 'id="theme-custom-gradient-primary-end-color"' in html
    assert 'id="theme-custom-gradient-primary-type"' in html
    assert 'id="theme-custom-gradient-primary-direction"' in html
    assert 'id="theme-custom-background-type"' in html
    assert '<option value="particles">Particles</option>' in html
    assert '<option value="livemap">Live map</option>' in html
    assert '<option value="image">Image</option>' in html
    assert 'id="dashboard-image-bg"' in html
    assert 'id="dashboard-particles-bg"' in html
    assert 'id="dashboard-livemap-bg"' in html
    assert 'id="theme-custom-background-image-file"' in html
    assert 'id="theme-custom-background-image-layout"' in html
    assert 'id="theme-custom-background-image-darken"' in html
    assert 'id="theme-custom-background-image-darken-value"' in html
    assert '<option value="stretch">Stretch</option>' in html
    assert '<option value="tile">Tile</option>' in html
    assert 'id="theme-custom-background-image-clear"' in html
    assert 'id="theme-custom-background-image-status"' in html
    assert "data-background-image-only" in html
    assert "data-background-particles" in html
    assert "data-particles-random-only" in html
    assert ".settings-gradient-group," in css
    assert ".settings-input," in css
    assert "backdrop-filter: var(--theme-foreground-blur, none);" in css
    assert "--settings-control-bg: color-mix(in srgb, var(--settings-bg-soft) 86%, transparent);" in css
    assert 'src="/assets/vendor/particles-2.0.0.min.js"' in html
    assert 'id="theme-custom-particles-enabled"' in html
    assert 'id="theme-custom-particles-color"' in html
    assert 'id="theme-custom-particles-link-color"' in html
    assert '>Background source<' in html
    assert '>Background gradient<' in html
    assert 'id="theme-custom-particles-count"' in html
    assert 'id="theme-custom-particles-count-value"' in html
    assert 'id="theme-custom-particles-speed"' in html
    particles_speed_markup = html.split('id="theme-custom-particles-speed"', 1)[1].split("/>", 1)[0]
    assert 'step="0.1"' in particles_speed_markup
    assert 'id="theme-custom-particles-size"' in html
    assert 'id="theme-custom-particles-opacity"' in html
    assert 'id="theme-custom-particles-opacity-value"' in html
    assert 'id="theme-custom-particles-links"' in html
    assert '<h3>Appearance</h3>' not in html
    assert 'id="theme-toggle-btn"' not in html
    assert 'data-theme-toggle="full"' not in html
    assert 'data-theme-toggle="compact"' in html
    assert ">Theme: Dark</button>" not in html
    assert 'id="theme-custom-gradient-secondary-start-color"' not in html
    assert 'id="theme-custom-gradient-secondary-end-color"' not in html
    assert 'id="theme-custom-gradient-secondary-type"' not in html
    assert 'id="theme-custom-gradient-secondary-direction"' not in html
    assert "Primary gradient" not in html
    assert "Background gradient" in html
    assert "Particles" in html
    assert "Enable particles" in html
    assert "Divider gradient" not in html
    assert "Secondary gradient" not in html
    assert "Foreground transparency" in html
    assert "Line contrast color" in html
    assert "Text color" not in html
    assert "Text font" in html
    assert '<option value="mono">Mono</option>' in html
    assert '<option value="radial">Radial</option>' in html
    assert '<option value="down-right">Down right</option>' in html
    assert 'id="settings-appearance-badge-emoji"' not in html
    assert "theme-live-preview" not in html
    assert 'id="theme-preview"' not in html
    assert 'id="settings-appearance-tab-theme-btn"' in html
    assert 'id="settings-appearance-tab-node-btn"' in html
    assert 'data-settings-appearance-tab-panel="theme"' in html
    assert 'data-settings-appearance-tab-panel="node"' in html
    assert "function normalizeSettingsAppearanceTab(value)" in js
    assert "function setActiveSettingsAppearanceTab(tab, persist = true)" in js
    assert "settingsAppearanceTabStorageKey" in js
    assert 'runBootStep("loadSettingsAppearanceTabPreference", () => loadSettingsAppearanceTabPreference());' in js
    assert "function normalizeMeshyfaceProfileTheme(rawTheme)" in js
    assert "rawKeys.length !== meshyfaceProfileThemeKeys.size" in js
    assert "function currentMeshyfaceProfileThemeRecipe()" in js
    assert "function currentMeshyfaceNodeThemeSettings()" in js
    assert "const settings = currentMeshyfaceNodeThemeSettings();" in js
    assert 'const meshyfaceNodeThemeModes = new Set(["current", "light", "dark"]);' in js
    assert 'mode: requestedMode === "current" ? resolvedMeshyfaceProfileThemeMode() : requestedMode,' in js
    assert 'id="settings-meshyface-node-theme-preview-card"' in html
    assert 'id="settings-meshyface-node-theme-preview-member"' in html
    assert 'class="settings-meshyface-node-theme-preview-shell"' in html
    assert 'class="chat-feed-item profiled-node chat-selectable"' in html
    assert 'class="chat-member-item status-online profiled-node settings-meshyface-node-theme-preview-member"' in html
    assert "function meshyfaceNodeThemePreviewPayload(rawTheme)" in js
    assert "preview_only: true," in js
    assert "function meshyfaceNodeThemePreviewRenderFromPayload(payload, rawTheme)" in js
    assert "function refreshMeshyfaceNodeThemePreviewRender(rawTheme)" in js
    assert "queueMeshyfaceNodeThemePreviewRenderRefresh(theme);" in js
    assert "applyNodeAppearanceElementStyle(target, appearanceEntry);" in js
    assert "settingsMeshyfaceNodeThemePreviewRender" in js
    assert '? currentMeshyfaceProfileThemeRecipe()' in js
    assert "...(theme ? { theme } : {})," not in js
    assert "if (!theme || !preset) return null;" in js
    assert "function meshyfaceProfileThemeIdentityGradient(rawTheme)" not in js
    assert "function meshyfaceProfileThemeWashGradient(rawTheme, hover = false)" not in js
    assert "function normalizeMeshyfaceProfileThemeRender(rawRender)" in js
    assert "function meshyfaceProfileThemeBackgroundGradient(rawTheme, rawRender = null)" in js
    assert "function meshyfaceProfileThemeStyleEntries(rawTheme, rawRender = null)" in js
    assert "function applyMeshyfaceProfileThemeElementStyle(target, rawTheme, rawRender = null)" in js
    assert "clearMeshyfaceProfileThemeElementStyle(target);" in js
    assert "applyMeshyfaceProfileThemeElementStyle(target, entry.theme, profileRender);" in js
    assert '["--node-profile-theme-background", backgroundGradient]' in js
    assert '["--node-profile-theme-shell", meshyfaceProfileThemeAlphaGradient(' in js
    assert '["--node-profile-theme-border", render.border_color]' in js
    assert '["--node-profile-theme-base", theme.base_color]' in js
    assert '["--node-profile-theme-line", theme.line_color]' in js
    assert '["--node-profile-theme-contrast", theme.line_contrast_color]' in js
    assert "--node-profile-theme-motif" not in js
    assert "--node-profile-theme-gradient" not in js
    assert "--node-profile-theme-wash" not in js
    assert "--node-profile-theme-font-family" not in js
    assert "meshyfaceProfileThemePreviewHtml" not in js
    assert "node-profile-theme-swatch" not in js
    assert "Shared surface wash" not in html
    assert "Subtle panel and note color" not in html
    assert "Text" in html
    assert "Console preview" not in html
    assert "$ mesh status --live" not in html
    assert "RX packets render with this theme" not in html
    assert "RX packets render with this tint" not in html
    assert '<option value="custom">custom</option>' in html
    assert 'id="theme-preset-save-btn"' in html
    assert 'id="theme-preset-update-btn"' in html
    assert 'id="theme-preset-rename-btn"' in html
    assert 'id="theme-preset-delete-btn"' in html
    assert "Fresh installs default to Meshyface blue with a neutral gray line and tint" not in html
    assert 'value="#007bff"' in html
    assert 'value="#0da6ff"' in html
    assert 'value="#4f55ff"' in html
    assert 'value="#5ac8fa"' not in html
    assert 'value="#060d1f"' in html
    assert 'value="46"' not in html
    assert '>46%</output>' not in html
    assert 'value="44"' in html
    assert '>44%</output>' in html
    assert '>39%</output>' in html
    assert 'value="50"' in html
    assert ">50</output>" in html
    assert 'value="0.2"' in html
    assert ">0.2</output>" in html
    assert 'value="88"' in html
    assert ">88%</output>" in html
    assert 'class="settings-gradient-group settings-background-panel"' in html
    assert 'data-background-livemap-only' in html
    assert 'class="settings-livemap-layer-grid"' in html
    assert 'id="theme-custom-livemap-layer-roads"' in html
    assert 'id="theme-custom-livemap-layer-cities"' in html
    assert '>Map layers<' in html
    assert "Primary shell" not in html
    assert "Shared tint surfaces" not in html
    assert "Tint-backed utility chrome" not in html
    assert "Tint color drives the shared shell tint used by help notes, console chrome" not in html
    assert "Tint intensity scales that shared tint from neutral up to a clearly visible wash" not in html
    assert "Dashboard display behavior for always-on monitoring" not in html
    assert "Console tuning for packet logs and command output" not in html
    assert "Badge shows in the workspace launcher square" not in html
    assert "Off leaves untagged node and chat surfaces neutral" not in html
    assert 'id="settings-appearance-unique-node-colors"' not in html
    assert 'id="settings-appearance-unique-chat-colors"' not in html

    assert 'let themePresetSelected = "custom";' in js
    assert "let themePresetCustomSettingsCatalog = {};" in js
    assert 'let themeCustomBaseColor = "#007bff";' in js
    assert 'let themeCustomLineColor = "#0da6ff";' in js
    assert 'let themeCustomLineContrastColor = "#4f55ff";' in js
    assert "themeCustomTintColor" not in js
    assert "themeCustomTintIntensity" not in js
    assert "let themeCustomColorDepth = 44;" in js
    assert "let themeCustomForegroundTransparency = 39;" in js
    assert "themeCustomTextColor" not in js
    assert 'let themeCustomTextFont = "system";' in js
    assert 'let themeCustomGradientPrimaryStartColor = "#00356e";' in js
    assert 'let themeCustomGradientPrimaryEndColor = "#060d1f";' in js
    assert 'let themeCustomGradientPrimaryType = "linear";' in js
    assert 'let themeCustomGradientPrimaryDirection = "right";' in js
    assert 'let themeCustomBackgroundType = "particles";' in js
    assert 'let themeCustomBackgroundImageData = "";' in js
    assert 'let themeCustomBackgroundImageLayout = "cover";' in js
    assert "let themeCustomBackgroundImageDarken = 0;" in js
    assert "let themeCustomParticlesEnabled = true;" in js
    assert 'let themeCustomParticlesColor = "#548dff";' in js
    assert "let themeCustomParticlesCount = 50;" in js
    assert "let themeCustomParticlesSpeed = 0.2;" in js
    assert "let themeCustomParticlesSize = 2;" in js
    assert "let themeCustomParticlesOpacity = 88;" in js
    assert "let themeCustomParticlesLinks = true;" in js
    assert "let themeCustomLivemapLayers = {" in js
    assert "roads: true," in js
    assert "cities: true," in js
    assert "themeCustomGradientSecondary" not in js
    assert 'const settingsBadgeEmojiStorageKey = "meshDashboardSettingsBadgeEmojiV1";' not in js
    assert "settingsUniqueNodeColors" not in js
    assert "settingsUniqueChatColors" not in js
    assert "function formatThemePresetLabel(name) {" in js
    assert 'return "default";' in js
    assert "function normalizeThemeCustomSettings(rawSettings) {" in js
    assert "function normalizeThemePresetCustomSettingsCatalog(rawCatalog) {" in js
    assert "function currentThemeCustomSettings() {" in js
    assert "function applyThemeCustomSettings(rawSettings) {" in js
    assert "function defaultThemeEditableSettings() {" in js
    assert "function themeEditableSettingsForPreset(presetName = null) {" in js
    assert "function beginThemeCustomEditFromSelectedPreset() {" in js
    assert "return defaultThemeEditableSettings();" in js
    assert "applyThemeCustomSettings(themeEditableSettingsForPreset(selected));" in js
    assert "themePresetCustomSettingsCatalog = normalizeThemePresetCustomSettingsCatalog(payload.preset_custom_settings);" in js
    assert "function normalizeThemeCustomLineColor(raw, fallback = \"#0da6ff\") {" in js
    assert "function normalizeThemeCustomLineContrastColor(raw, fallback = \"#4f55ff\") {" in js
    assert "function normalizeThemeCustomTintColor" not in js
    assert "function normalizeThemeCustomTextColor" not in js
    assert "function normalizeThemeCustomTextFont(raw, fallback = \"system\") {" in js
    assert "function normalizeThemeCustomGradientType(raw, fallback = \"linear\") {" in js
    assert "function normalizeThemeCustomGradientDirection(raw, fallback = \"right\") {" in js
    assert "function normalizeThemeCustomForegroundTransparency(raw) {" in js
    assert "function normalizeThemeCustomBackgroundImageData(raw, fallback = \"\") {" in js
    assert 'function normalizeThemeCustomBackgroundImageLayout(raw, fallback = "cover") {' in js
    assert "function normalizeThemeCustomBackgroundImageDarken(raw, fallback = 0) {" in js
    assert "function normalizeThemeCustomParticlesEnabled(raw, fallback = true) {" in js
    assert "function normalizeThemeCustomParticlesColor(raw, fallback = \"#548dff\") {" in js
    assert "function markDashboardBackgroundActive(host, signature = \"\") {" in js
    assert "function resetDashboardBackgroundActiveState(host) {" in js
    assert "let dashboardParticlesBackgroundLoadSerial = 0;" in js
    assert "let dashboardImageBackgroundLoadSerial = 0;" in js
    assert "function scheduleDashboardParticlesReveal(host, signature, serial, attempts = 0) {" in js
    assert 'host.classList.add("dashboard-particles-background-loaded");' in js
    assert "function preloadDashboardImageBackground(imageData, host, signature, serial) {" in js
    assert 'host.classList.add("dashboard-image-background-loaded");' in js
    assert "function deactivateInactiveDashboardBackgrounds(activeType) {" in js
    assert "function applyDashboardParticles(rawSettings = null) {" in js
    assert "function applyDashboardImage(rawSettings = null) {" in js
    assert "markDashboardBackgroundActive(host, backgroundSignature);" in js
    assert "markDashboardBackgroundActive(host instanceof HTMLElement ? host : null, \"livemap\");" in js
    assert 'window.particlesJS("dashboard-particles-bg", buildDashboardParticlesConfig(settings));' in js
    assert "const dashboardBackgroundHandlers = {" in js
    assert "function applyDashboardBackground(rawSettings = null) {" in js
    assert 'if (backgroundType !== "image") {' in js
    assert "disableDashboardImage();" in js
    assert "deactivateInactiveDashboardBackgrounds(backgroundType);" in js
    assert "disableAllDashboardBackgrounds();" in js
    assert "applyDashboardBackground(themeEditableSettingsForPreset(themePresetSelected));" in js
    assert "dashboard-background-fade-in" not in js
    assert 'function normalizeThemeCustomBackgroundType(raw, fallback = "particles") {' in js
    assert "const themeCustomLivemapLayerDefaults = Object.freeze({" in js
    assert "function normalizeThemeCustomLivemapLayers(raw, fallback = null) {" in js
    assert "function applyDashboardLivemap(rawSettings = null) {" in js
    assert "function disableDashboardLivemap() {" in js
    assert "function refreshDashboardLivemapGeometry() {" in js
    assert "function dashboardLivemapLayerSettingKey(layerName) {" in js
    assert "function dashboardLivemapLayerEnabled(settings, layerName) {" in js
    assert "function dashboardLivemapBackdropLayersEnabled(settings) {" in js
    assert "function dashboardLivemapTrimmedBounds(points) {" in js
    assert 'const dashboardLivemapEstimatedRangeFallbackPreset = "LONG_FAST";' in js
    assert "const dashboardLivemapEstimatedRangeByPreset = Object.freeze({" in js
    assert "MEDIUM_FAST: { rangeKm: 32, strongKm: 9 }" in js
    assert "LONG_FAST: { rangeKm: 52, strongKm: 15 }" in js
    assert "const dashboardLivemapEstimatedRangeMaxLinks = 360;" in js
    assert "const dashboardLivemapEstimatedRangeMaxLinksPerNode = 5;" in js
    assert "function dashboardLivemapNormalizeModemPreset(value) {" in js
    assert "function dashboardLivemapModemPresetFromState(state) {" in js
    assert "function dashboardLivemapEstimatedRangeProfile(state) {" in js
    assert "function dashboardLivemapDistanceKm(a, b) {" in js
    assert "function dashboardLivemapBuildEstimatedRangeLinks(points, nowUnix, rangeProfile = null) {" in js
    assert "positionLastSeenUnix" in js
    assert "estimatedRangeLinks" in js
    assert "setLineDash([2.5 * ratio, 7 * ratio])" not in js
    assert "const linkColor = normalizeThemeCustomParticlesColor(" in js
    assert "settings.livemap_link_color," in js
    assert "settings.particles_link_color || settings.line_contrast_color || color" in js
    assert "const mapColor = normalizeThemeCustomLineColor(settings.line_color, color);" in js
    assert "const linkGlowColor = normalizeThemeCustomLineContrastColor(linkColor, color);" in js
    assert "ctx.strokeStyle = linkColor;" in js
    assert "ctx.shadowColor = linkGlowColor;" in js
    assert "ctx.shadowBlur = 5 * ratio;" in js
    assert "ctx.shadowBlur = 7 * ratio;" in js
    assert "const dashboardLivemapViewEasing = 0.055;" in js
    assert "const dashboardLivemapNodeDriftEasing = 0.00035;" in js
    assert "const dashboardLivemapNodeDriftWanderRatio = 0.004;" in js
    assert "const dashboardLivemapNodeDriftPeriodMs = 420000;" in js
    assert "dashboardLivemapNodeCatchupEasing" not in js
    assert "dashboardLivemapNodeGrossEasing" not in js
    assert "dashboardLivemapNodeGrossMissRatio" not in js
    assert "const dashboardLivemapViewSnapEpsilon = 0.000004;" in js
    assert "const dashboardLivemapMapFadeMs = 1600;" in js
    assert "const dashboardLivemapMeshFadeMs = 2800;" in js
    assert "let dashboardLivemapLinkTransitions = new Map();" in js
    assert "const dashboardLivemapLinkFadeInEasing = 0.025;" in js
    assert "const dashboardLivemapLinkFadeOutEasing = 0.012;" in js
    assert "const dashboardLivemapLinkPruneOpacity = 0.004;" in js
    assert "function dashboardLivemapSyncLinkTransitions(geometry, nowMs = null) {" in js
    assert "function dashboardLivemapEaseLinkTransitions() {" in js
    assert "function dashboardLivemapTransitionLinks(type) {" in js
    assert "function dashboardLivemapLinkTransitionOpacity(link) {" in js
    assert "dashboardLivemapSyncLinkTransitions(dashboardLivemapGeometry, dashboardLivemapNowMs());" in js
    assert "const estimatedRangeLinks = dashboardLivemapTransitionLinks(\"estimated\");" in js
    assert "const observedLinks = dashboardLivemapTransitionLinks(\"observed\");" in js
    assert "transitionOpacity: opacity" in js
    assert "aKey: srcKey" in js
    assert "bKey: dstKey" in js
    assert "const dashboardLivemapNodePanAfterMapDelayMs = 450;" in js
    assert "const dashboardLivemapNodePanFallbackMapWaitMs = 2400;" in js
    assert 'const dashboardLivemapCachedViewStorageKey = "meshyface.dashboard.livemap.lastGpsView.v1";' in js
    assert "const dashboardLivemapCachedViewMaxAgeMs = 24 * 60 * 60 * 1000;" in js
    assert "function loadDashboardLivemapCachedNodeView() {" in js
    assert "function storeDashboardLivemapCachedNodeView(view) {" in js
    assert "function dashboardLivemapViewMissRatio(view, target) {" not in js
    assert "function dashboardLivemapDriftViewForTarget(target, nowMs) {" in js
    assert "function dashboardLivemapFallbackView() {" not in js
    assert "function dashboardLivemapPanViewForTarget(target, sourceView = null) {" not in js
    assert "function dashboardLivemapIntroViewForTarget(target) {" not in js
    assert "function dashboardLivemapWideViewForTarget(target) {" not in js
    assert "dashboardLivemapIntroPending = true;" in js
    assert "dashboardLivemapPendingNodeTarget = null;" in js
    assert "const hasLivePoints = points.length > 0;" in js
    assert "const lockedToNodeLocation = hasLivePoints && !!nodeTargetView;" in js
    assert "dashboardLivemapBestNodeView = { ...nodeTargetView };" in js
    assert "storeDashboardLivemapCachedNodeView(nodeTargetView);" in js
    assert "if (!dashboardLivemapView && cachedNodeView) {" in js
    assert "dashboardLivemapTargetView = dashboardLivemapView ? { ...dashboardLivemapView } : null;" in js
    assert "let dashboardLivemapMapLayerFadeStartedAt = new Map();" in js
    assert "function dashboardLivemapMapLayerOpacity(layerKey, nowMs) {" in js
    assert "function dashboardLivemapMeshOpacity(nowMs, hasMeshPoints) {" in js
    assert "const hasEnabledMapBackdrop = dashboardLivemapBackdropLayersEnabled(settings);" in js
    assert "if (!dashboardLivemapLayerEnabled(settings, settingLayer)) return 0;" in js
    assert "if (!dashboardLivemapLayerEnabled(settings, shape.layer || \"base\")) continue;" in js
    assert "if (!dashboardLivemapLayerEnabled(settings, layerName)) continue;" in js
    assert 'mapLayerOpacity(`pack:${layerName}`);' in js
    assert 'mapLayerOpacity("labels:cities");' in js
    assert "function maybeStartDashboardLivemapNodePan(nowMs) {" in js
    assert "function updateDashboardLivemapDriftTarget(nowMs) {" in js
    assert "updateDashboardLivemapDriftTarget(now);" in js
    assert "drawDashboardLivemap(now);" in js
    assert 'if (typeof requestDashboardLivemapRefit === "function") {' in js
    assert "function requestDashboardLivemapRefit() {" in js
    assert "function dashboardLivemapCollectCityPoints(collection) {" in js
    assert "function refreshDashboardLivemapCities() {" in js
    assert "function ensureDashboardLivemapPacks() {" in js
    assert (
        "async function dashboardLivemapLoadPackChunk"
        "(packId, manifest, layerName, cellId, chunkEntry) {"
    ) in js
    assert "function dashboardLivemapPackViewportCells(spec, padCells) {" in js
    assert "function dashboardLivemapEffectiveZoom() {" in js
    assert "function evictDashboardLivemapPackChunks() {" in js
    assert "function dashboardLivemapVisiblePackCityRows() {" in js
    assert "const dashboardLivemapPackBaseReplacements = {" in js
    assert "background_type:" in js
    assert "background_image_data:" in js
    assert "background_image_layout:" in js
    assert "background_image_darken:" in js
    assert "destroypJS" not in js
    assert "prefers-color-scheme" in js
    assert "function normalizeThemeCustomTintIntensity" not in js
    assert "function themeCustomColorInputHasCompleteHex(input) {" in js
    assert "function normalizeSettingsBadgeEmoji(value) {" not in js
    assert "function setThemeLivePreviewStatus" not in js
    assert "function buildCurrentThemeCustomOptions(extraOptions = null) {" in js
    assert "function queueLiveThemePreview() {" in js
    assert "function persistThemeCustomControls() {" in js
    assert "function syncThemeCustomControls() {" in js
    assert "function buildThemeSettingsSavePayload(options = null) {" in js
    assert "preview_only: Boolean(opts.previewOnly)," in js
    assert "custom_theme: {" in js
    assert "line_contrast_color:" in js
    assert "tint_color:" not in js
    assert "tint_intensity:" not in js
    assert "text_color:" not in js
    assert "text_font:" in js
    assert "gradient_primary_start_color:" in js
    assert "foreground_transparency:" in js
    assert "foreground_blur:" in js
    assert "function normalizeThemeCustomForegroundBlur(raw) {" in js
    assert "gradient_primary_end_color:" in js
    assert "gradient_primary_type:" in js
    assert "gradient_primary_direction:" in js
    assert "particles_enabled:" in js
    assert "particles_color:" in js
    assert "particles_link_color:" in js
    assert "livemap_link_color:" in js
    assert "particles_count:" in js
    assert "particles_speed:" in js
    assert "function normalizeThemeCustomParticlesFloat(raw, fallback, min, max) {" in js
    assert "particles_size:" in js
    assert "particles_opacity:" in js
    assert "particles_links:" in js
    assert "livemap_layers:" in js
    assert "livemapLayers: opts.livemapLayers == null ? themeCustomLivemapLayers : opts.livemapLayers" in js
    assert "for (const input of document.querySelectorAll(\"[data-livemap-layer]\")) {" in js
    assert "gradient_secondary_start_color:" not in js
    assert "gradient_secondary_end_color:" not in js
    assert "gradient_secondary_type:" not in js
    assert "gradient_secondary_direction:" not in js
    assert 'presetName: opts.presetName == null ? "custom" : opts.presetName' in js
    assert "function bindThemePresetActionButtons() {" in js
    assert "function saveCurrentThemeAsNewPreset(name) {" in js
    assert "function updateSelectedThemePreset() {" in js
    assert "function renameSelectedThemePreset() {" in js
    assert "function deleteSelectedThemePreset() {" in js
    assert 'runBootStep("bindThemePresetActionButtons", () => bindThemePresetActionButtons());' in js
    assert "function bindThemeCustomControls() {" in js
    assert "attachDashboardColorPicker(colorInput" in js
    assert "attachDashboardColorPicker(lineColorInput" in js
    assert "attachDashboardColorPicker(lineContrastColorInput" in js
    assert "attachDashboardColorPicker(tintColorInput" not in js
    assert "attachDashboardColorPicker(textColorInput" not in js
    assert "attachDashboardColorPicker(particlesColorInput" in js
    assert 'bindGradientColorInput("theme-custom-gradient-primary-start-color"' in js
    assert "function readThemeCustomBackgroundImageFile(file) {" in js
    assert 'bindParticleRangeInput("theme-custom-particles-count"' in js
    assert 'bindGradientSelect("theme-custom-gradient-primary-type"' in js
    assert 'bindGradientColorInput("theme-custom-gradient-secondary-start-color"' not in js
    assert 'bindGradientSelect("theme-custom-gradient-secondary-direction"' not in js
    assert "if (!themeCustomColorInputHasCompleteHex(colorInput)) return;" in js
    assert 'runBootStep("bindThemeCustomControls", () => bindThemeCustomControls());' in js
    assert "beginThemeCustomEditFromSelectedPreset();" in js
    assert 'controlId === "settings-appearance-badge-emoji"' not in js
    assert 'controlId === "theme-custom-base-color"' in js
    assert 'controlId === "theme-custom-line-color"' in js
    assert 'controlId === "theme-custom-line-contrast-color"' in js
    assert 'controlId === "theme-custom-tint-color"' not in js
    assert 'controlId === "theme-custom-text-color"' not in js
    assert 'controlId === "theme-custom-text-font"' in js
    assert 'controlId === "theme-custom-tint-intensity"' not in js
    assert 'controlId === "theme-custom-color-depth"' in js
    assert 'controlId === "theme-custom-foreground-transparency"' in js
    assert 'controlId === "theme-custom-foreground-blur"' in js
    assert 'controlId === "theme-custom-gradient-primary-start-color"' in js
    assert 'controlId === "theme-custom-gradient-primary-type"' in js
    assert 'controlId === "theme-custom-background-type"' in js
    assert 'controlId === "theme-custom-background-image-file"' in js
    assert 'controlId === "theme-custom-background-image-layout"' in js
    assert 'controlId === "theme-custom-background-image-darken"' in js
    assert 'controlId === "theme-custom-particles-enabled"' in js
    assert 'controlId === "theme-custom-particles-color"' in js
    assert 'controlId === "theme-custom-particles-link-color"' in js
    assert 'controlId === "theme-custom-particles-opacity"' in js
    assert 'controlId === "theme-custom-gradient-secondary-end-color"' not in js
    assert 'controlId === "theme-custom-gradient-secondary-direction"' not in js
    assert "payload.custom_theme" in js
