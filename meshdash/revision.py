import subprocess
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class RevisionInfo:
    version: str
    commit: str
    label: str
    title: str

    def as_dict(self) -> dict[str, str]:
        return {
            "version": self.version,
            "commit": self.commit,
            "label": self.label,
            "title": self.title,
        }


def sanitize_revision_token(raw: object, fallback: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return fallback
    safe = "".join(ch for ch in text if ch.isalnum() or ch in ("-", "_", ".", "+"))
    return safe or fallback


def detect_git_commit(
    explicit_commit: object,
    script_dir: str,
    cwd: str,
    unknown_git_commit: str,
    sanitize_token: Callable[[object, str], str] = sanitize_revision_token,
) -> Optional[str]:
    explicit = str(explicit_commit or "").strip()
    if explicit:
        return sanitize_token(explicit, unknown_git_commit)

    search_roots: list[str] = []
    for root in (script_dir, cwd):
        if root and root not in search_roots:
            search_roots.append(root)

    for root in search_roots:
        try:
            proc = subprocess.run(
                ["git", "-C", root, "rev-parse", "--short=12", "HEAD"],
                check=False,
                capture_output=True,
                text=True,
                timeout=1.0,
            )
        except Exception:
            continue
        if proc.returncode == 0:
            commit = sanitize_token(proc.stdout, "")
            if commit:
                return commit
    return None


def revision_info(
    version_raw: object,
    default_version: str,
    unknown_git_commit: str,
    detect_commit: Callable[[], Optional[str]],
    sanitize_token: Callable[[object, str], str] = sanitize_revision_token,
) -> RevisionInfo:
    version = sanitize_token(version_raw or default_version, "0.0.0")
    if version.lower().startswith("v"):
        version = version[1:] or "0.0.0"

    commit = detect_commit() or unknown_git_commit
    label = f"Rev: v{version} ({commit})"
    title = f"Dashboard revision: version {version}, commit {commit}"

    return RevisionInfo(
        version=version,
        commit=commit,
        label=label,
        title=title,
    )
