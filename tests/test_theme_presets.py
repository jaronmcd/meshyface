import json

from meshdash.theme import DARK_THEME_VARS, LIGHT_THEME_VARS
from meshdash.theme_presets import (
    default_theme_presets,
    load_theme_presets,
    select_theme_preset,
)


def test_default_theme_presets_include_default_light_and_dark():
    presets = default_theme_presets()
    assert "default" in presets
    assert presets["default"]["light"] == LIGHT_THEME_VARS
    assert presets["default"]["dark"] == DARK_THEME_VARS


def test_load_theme_presets_returns_defaults_for_missing_or_invalid_path(tmp_path):
    missing = load_theme_presets(str(tmp_path / "missing.json"))
    assert "default" in missing
    assert missing["default"]["light"] == LIGHT_THEME_VARS
    assert missing["default"]["dark"] == DARK_THEME_VARS


def test_load_theme_presets_merges_valid_presets_and_skips_invalid(tmp_path):
    valid_light = dict(LIGHT_THEME_VARS)
    valid_dark = dict(DARK_THEME_VARS)
    valid_light["--accent"] = "#123456"
    valid_dark["--ui-accent"] = "#abcdef"

    raw = {
        "forest": {"light": valid_light, "dark": valid_dark},
        "broken": {"light": {"--accent": "#123456"}, "dark": valid_dark},
    }
    path = tmp_path / "theme_presets.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    presets = load_theme_presets(str(path))

    assert "default" in presets
    assert "forest" in presets
    assert "broken" not in presets
    assert presets["forest"]["light"]["--accent"] == "#123456"
    assert presets["forest"]["dark"]["--ui-accent"] == "#abcdef"


def test_select_theme_preset_falls_back_to_default():
    presets = default_theme_presets()
    selected = select_theme_preset(presets, "missing")
    assert selected is presets["default"]
