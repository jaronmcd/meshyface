from typing import Dict

from .theme import build_theme_css as _build_theme_css


def build_html_render_context(
    *,
    show_secrets: bool,
    history_enabled: bool,
    history_max_rows: int,
    history_retention_days: int,
) -> Dict[str, str]:
    safety_label = "Secrets visible" if show_secrets else "Secrets redacted"
    history_label = "History: off"
    if history_enabled:
        history_label = (
            f"History: on ({history_retention_days}d retention, {history_max_rows} rows max)"
        )
    theme_css = _build_theme_css()
    return {
        "safety_label": safety_label,
        "history_label": history_label,
        "theme_css": theme_css,
    }
