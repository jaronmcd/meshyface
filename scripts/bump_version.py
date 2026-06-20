#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


VERSION_FILE = Path("meshdash/__init__.py")
VERSION_PATTERN = re.compile(
    r'(?m)^(?P<prefix>__version__\s*=\s*")'
    r"(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r'(?P<suffix>")[ \t]*$'
)


def bump_patch_version(version: str) -> str:
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"Expected semantic version MAJOR.MINOR.PATCH, got {version!r}")
    major, minor, patch = (int(part) for part in parts)
    return f"{major}.{minor}.{patch + 1}"


def bump_version_text(text: str) -> tuple[str, str]:
    match = VERSION_PATTERN.search(text)
    if not match:
        raise ValueError('Unable to find __version__ = "MAJOR.MINOR.PATCH"')

    current_version = ".".join(
        match.group(name) for name in ("major", "minor", "patch")
    )
    next_version = bump_patch_version(current_version)
    updated = VERSION_PATTERN.sub(
        rf'\g<prefix>{next_version}\g<suffix>',
        text,
        count=1,
    )
    return updated, next_version


def bump_version_file(path: Path = VERSION_FILE) -> str:
    text = path.read_text(encoding="utf-8")
    updated, next_version = bump_version_text(text)
    path.write_text(updated, encoding="utf-8")
    return next_version


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Increment the Meshyface dashboard patch version."
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=VERSION_FILE,
        help="Python module containing __version__. Defaults to meshdash/__init__.py.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(bump_version_file(args.file))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
