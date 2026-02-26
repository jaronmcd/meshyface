import os
from typing import Callable, Optional

from .revision import (
    RevisionInfo,
    detect_git_commit as _detect_git_commit_helper,
    revision_info as _build_revision_info_helper,
    sanitize_revision_token as _sanitize_revision_token_helper,
)


def detect_git_commit_from_env(
    *,
    script_file: str,
    cwd: str,
    explicit_commit: object,
    unknown_git_commit: str,
    detect_git_commit_fn: Callable[..., Optional[str]] = _detect_git_commit_helper,
    sanitize_token_fn: Callable[[object, str], str] = _sanitize_revision_token_helper,
) -> Optional[str]:
    script_dir = os.path.dirname(os.path.abspath(script_file))
    return detect_git_commit_fn(
        explicit_commit=explicit_commit,
        script_dir=script_dir,
        cwd=cwd,
        unknown_git_commit=unknown_git_commit,
        sanitize_token=sanitize_token_fn,
    )


def revision_info_from_env(
    *,
    env_version: object,
    default_version: str,
    unknown_git_commit: str,
    detect_commit_fn: Callable[[], Optional[str]],
    build_revision_info_fn: Callable[..., RevisionInfo] = _build_revision_info_helper,
    sanitize_token_fn: Callable[[object, str], str] = _sanitize_revision_token_helper,
) -> RevisionInfo:
    version_raw = env_version or default_version
    return build_revision_info_fn(
        version_raw=version_raw,
        default_version=default_version,
        unknown_git_commit=unknown_git_commit,
        detect_commit=detect_commit_fn,
        sanitize_token=sanitize_token_fn,
    )
