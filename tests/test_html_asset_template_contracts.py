import re
from pathlib import Path

from meshdash.html_assets import render_asset_template


_ASSETS_DIR = Path(__file__).resolve().parents[1] / "meshdash" / "assets"
_SINGLE_TEMPLATE_TOKEN_RE = re.compile(r"(?<![${])\{([a-z_][a-z0-9_]*)\}")

_EXPECTED_TEMPLATE_TOKENS = {
    "dashboard.css.tmpl": set(),
    "dashboard.css.base.tmpl": {"theme_css"},
    "dashboard.css.layout.tmpl": set(),
    "dashboard.css.components.tmpl": set(),
    "dashboard.js.tmpl": {
        "refresh_ms",
        "node_history_hours",
        "node_history_max_points",
        "reset_ticker_scale_on_restart",
    },
    "dashboard.js.bootstrap.tmpl": set(),
    "dashboard.js.bootstrap.map.tmpl": {
        "refresh_ms",
        "node_history_hours",
        "node_history_max_points",
        "reset_ticker_scale_on_restart",
    },
    "dashboard.js.bootstrap.tickers.tmpl": set(),
    "dashboard.js.bootstrap.shared.tmpl": set(),
    "dashboard.js.chat.tmpl": set(),
    "dashboard.js.chat.state.tmpl": set(),
    "dashboard.js.chat.state.core.tmpl": set(),
    "dashboard.js.chat.state.games.tmpl": set(),
    "dashboard.js.chat.state.messaging.tmpl": set(),
    "dashboard.js.chat.events.tmpl": set(),
    "dashboard.js.chat.events.core.tmpl": set(),
    "dashboard.js.chat.events.console.tmpl": set(),
    "dashboard.js.chat.events.settings_map.tmpl": set(),
    "dashboard.js.chat.events.settings.tmpl": set(),
    "dashboard.js.chat.events.map_selection.tmpl": set(),
    "dashboard.js.chat.events.bindings.tmpl": set(),
    "dashboard.js.chat.events.data_views.tmpl": set(),
    "dashboard.js.chat.render.tmpl": set(),
    "dashboard.js.runtime.tmpl": set(),
    "dashboard.js.runtime.views.tmpl": set(),
    "dashboard.js.runtime.poll.tmpl": set(),
    "dashboard.js.runtime.boot.tmpl": set(),
    "dashboard.html.tmpl": {
        "app_title",
        "app_heading",
        "style_css",
        "app_js",
        "revision_title",
        "revision_label",
        "safety_label",
        "packet_limit",
        "history_label",
        "refresh_ms",
    },
}


def _template_tokens(template_name: str) -> set[str]:
    raw = (_ASSETS_DIR / template_name).read_text(encoding="utf-8")
    return set(_SINGLE_TEMPLATE_TOKEN_RE.findall(raw))


def test_asset_templates_expose_only_expected_tokens():
    for template_name, expected_tokens in _EXPECTED_TEMPLATE_TOKENS.items():
        assert _template_tokens(template_name) == expected_tokens


def test_rendered_asset_templates_leave_no_single_token_placeholders():
    render_values = {
        "dashboard.css.tmpl": {},
        "dashboard.css.base.tmpl": {
            "theme_css": ":root { --unit-test-token: #123456; }",
        },
        "dashboard.css.layout.tmpl": {},
        "dashboard.css.components.tmpl": {},
        "dashboard.js.tmpl": {
            "refresh_ms": 3000,
            "node_history_hours": 72,
            "node_history_max_points": 1440,
            "reset_ticker_scale_on_restart": 1,
        },
        "dashboard.js.bootstrap.tmpl": {},
        "dashboard.js.bootstrap.map.tmpl": {
            "refresh_ms": 3000,
            "node_history_hours": 72,
            "node_history_max_points": 1440,
            "reset_ticker_scale_on_restart": 1,
        },
        "dashboard.js.bootstrap.tickers.tmpl": {},
        "dashboard.js.bootstrap.shared.tmpl": {},
        "dashboard.js.chat.tmpl": {},
        "dashboard.js.chat.state.tmpl": {},
        "dashboard.js.chat.state.core.tmpl": {},
        "dashboard.js.chat.state.games.tmpl": {},
        "dashboard.js.chat.state.messaging.tmpl": {},
        "dashboard.js.chat.events.tmpl": {},
        "dashboard.js.chat.events.core.tmpl": {},
        "dashboard.js.chat.events.console.tmpl": {},
        "dashboard.js.chat.events.settings_map.tmpl": {},
        "dashboard.js.chat.events.settings.tmpl": {},
        "dashboard.js.chat.events.map_selection.tmpl": {},
        "dashboard.js.chat.events.bindings.tmpl": {},
        "dashboard.js.chat.events.data_views.tmpl": {},
        "dashboard.js.chat.render.tmpl": {},
        "dashboard.js.runtime.tmpl": {},
        "dashboard.js.runtime.views.tmpl": {},
        "dashboard.js.runtime.poll.tmpl": {},
        "dashboard.js.runtime.boot.tmpl": {},
        "dashboard.html.tmpl": {
            "app_title": "Meshyface",
            "app_heading": "Meshyface",
            "style_css": "/* css */",
            "app_js": "// js",
            "revision_title": "Rev title",
            "revision_label": "Rev label",
            "safety_label": "Secrets redacted",
            "packet_limit": 250,
            "history_label": "History: on",
            "refresh_ms": 3000,
        },
    }

    for template_name, values in render_values.items():
        rendered = render_asset_template(template_name, **values)
        for token in _EXPECTED_TEMPLATE_TOKENS[template_name]:
            assert f"{{{token}}}" not in rendered
