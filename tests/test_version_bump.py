from pathlib import Path

from scripts.bump_version import (
    bump_patch_version,
    bump_version_file,
    bump_version_text,
)


def test_bump_patch_version_increments_patch_only() -> None:
    assert bump_patch_version("0.1.0") == "0.1.1"
    assert bump_patch_version("1.2.9") == "1.2.10"


def test_bump_patch_version_rejects_non_semver() -> None:
    try:
        bump_patch_version("v1.2.3")
    except ValueError as exc:
        assert "MAJOR.MINOR.PATCH" in str(exc)
    else:
        raise AssertionError("bump_patch_version should reject prefixed versions")


def test_bump_version_text_updates_package_version_once() -> None:
    updated, version = bump_version_text(
        '"""Package."""\n\n__version__ = "2.3.4"\nOTHER = "__version__ = 9.9.9"\n'
    )

    assert version == "2.3.5"
    assert '__version__ = "2.3.5"' in updated
    assert 'OTHER = "__version__ = 9.9.9"' in updated


def test_bump_version_text_requires_version_assignment() -> None:
    try:
        bump_version_text('VERSION = "1.2.3"\n')
    except ValueError as exc:
        assert "__version__" in str(exc)
    else:
        raise AssertionError("bump_version_text should require __version__")


def test_bump_version_file_updates_requested_path(tmp_path: Path) -> None:
    version_file = tmp_path / "__init__.py"
    version_file.write_text('__version__ = "3.4.5"\n', encoding="utf-8")

    assert bump_version_file(version_file) == "3.4.6"
    assert version_file.read_text(encoding="utf-8") == '__version__ = "3.4.6"\n'


def test_ci_does_not_create_version_bump_branches() -> None:
    ci_workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert not Path(".github/workflows/version-bump.yml").exists()
    assert "python scripts/bump_version.py" not in ci_workflow
    assert "version-bump/" not in ci_workflow
    assert "gh pr create" not in ci_workflow
