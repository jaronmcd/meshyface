from typing import Dict, Optional

# Single source of truth for dashboard theme tokens.
# Keep palette changes here so CSS values stay centralized.
LIGHT_THEME_VARS: Dict[str, str] = {
    "--bg": "#f3f7f1",
    "--ink": "#112015",
    "--panel": "#ffffff",
    "--line": "#c6d6c0",
    "--accent": "#2f855a",
    "--accent-2": "#1f6f53",
    "--danger": "#c53030",
    "--muted": "#5e6e64",
    "--shadow": "0 10px 24px rgba(18, 40, 20, 0.08)",
}

DARK_THEME_VARS: Dict[str, str] = {
    "--ui-bg": "#0d1117",
    "--ui-bg-elev": "#111827",
    "--ui-panel": "#161b22",
    "--ui-panel-alt": "#1b2430",
    "--ui-border": "#2f3b4b",
    "--ui-text": "#e6edf3",
    "--ui-text-soft": "#9fb0c3",
    "--ui-accent": "#3fb950",
    "--ui-accent-soft": "#2ea043",
    "--ui-link": "#79c0ff",
    "--ui-shadow": "0 10px 24px rgba(1, 4, 9, 0.36)",
}


def _render_vars(selector: str, vars_map: Dict[str, str], indent: str) -> str:
    lines = [f"{indent}{selector} {{"]
    for key, value in vars_map.items():
        lines.append(f"{indent}  {key}: {value};")
    lines.append(f"{indent}}}")
    return "\n".join(lines)


def build_theme_css(
    indent: str = "    ",
    *,
    light_vars: Optional[Dict[str, str]] = None,
    dark_vars: Optional[Dict[str, str]] = None,
) -> str:
    light_tokens = light_vars if isinstance(light_vars, dict) else LIGHT_THEME_VARS
    dark_tokens = dark_vars if isinstance(dark_vars, dict) else DARK_THEME_VARS
    parts = [
        _render_vars(":root", light_tokens, indent),
        f"{indent}/* Readability-first dark theme override */",
        _render_vars('[data-theme="dark"]', dark_tokens, indent),
    ]
    return "\n".join(parts)
