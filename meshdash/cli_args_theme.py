import argparse
from typing import Optional


def add_theme_args(
    parser: argparse.ArgumentParser,
    *,
    resolved_theme_presets: Optional[str],
    resolved_theme_preset: str,
    resolved_theme_settings_file: Optional[str],
) -> None:
    parser.add_argument(
        "--theme-presets",
        default=resolved_theme_presets,
        help=(
            "Optional JSON file path for custom light/dark theme preset token maps "
            "(defaults to built-in preset only)."
        ),
    )
    parser.add_argument(
        "--theme-preset",
        default=resolved_theme_preset,
        help=(
            "Theme preset name from --theme-presets (or built-ins). "
            f"Built-ins include default and custom (default: {resolved_theme_preset})."
        ),
    )
    parser.add_argument(
        "--theme-settings-file",
        default=resolved_theme_settings_file,
        help=(
            "JSON file used to persist runtime theme preset selection "
            "(default: %(default)s)."
        ),
    )
