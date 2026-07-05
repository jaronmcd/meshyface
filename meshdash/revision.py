import subprocess
from dataclasses import dataclass
from typing import Callable, Mapping, Optional


@dataclass(frozen=True)
class RevisionInfo:
    version: str
    commit: str
    label: str
    title: str
    build_ref: str = ""
    pr_number: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "version": self.version,
            "commit": self.commit,
            "label": self.label,
            "title": self.title,
            "build_ref": self.build_ref,
            "pr_number": self.pr_number,
        }


def short_commit_token(commit: object, length: int = 7) -> str:
    text = sanitize_revision_token(commit, "nogit")
    if text == "nogit":
        return text
    clean_length = max(1, int(length or 7))
    return text[:clean_length]


def normalize_pr_number(raw: object) -> str:
    text = str(raw or "").strip()
    if text.startswith("#"):
        text = text[1:].strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[:12]


def build_revision_ref(commit: object, pr_number: object = "") -> str:
    short_commit = short_commit_token(commit)
    clean_pr = normalize_pr_number(pr_number)
    if clean_pr:
        return f"PR #{clean_pr} {short_commit}"
    return short_commit


def build_revision_label(build_ref: object) -> str:
    return f"Rev: {str(build_ref or 'nogit')}"


def build_revision_title(version: object, commit: object, build_ref: object) -> str:
    clean_version = sanitize_revision_token(version, "0.0.0")
    clean_commit = sanitize_revision_token(commit, "nogit")
    clean_ref = str(build_ref or short_commit_token(clean_commit))
    return f"Dashboard revision: {clean_ref}, version {clean_version}, commit {clean_commit}"


def coerce_revision_info(value: RevisionInfo | Mapping[str, object]) -> RevisionInfo:
    if isinstance(value, RevisionInfo):
        return value
    if not isinstance(value, Mapping):
        raise TypeError(f"Expected RevisionInfo or mapping, got {type(value)!r}")

    version = str(value.get("version") or "0.0.0")
    commit = str(value.get("commit") or "nogit")
    pr_number = normalize_pr_number(value.get("pr_number") or value.get("pull_request"))
    build_ref = str(value.get("build_ref") or build_revision_ref(commit, pr_number))
    label = str(value.get("label") or build_revision_label(build_ref))
    title = str(value.get("title") or build_revision_title(version, commit, build_ref))
    return RevisionInfo(
        version=version,
        commit=commit,
        label=label,
        title=title,
        build_ref=build_ref,
        pr_number=pr_number,
    )


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
    pr_number_raw: object = "",
    sanitize_token: Callable[[object, str], str] = sanitize_revision_token,
) -> RevisionInfo:
    version = sanitize_token(version_raw or default_version, "0.0.0")
    if version.lower().startswith("v"):
        version = version[1:] or "0.0.0"

    commit = detect_commit() or unknown_git_commit
    pr_number = normalize_pr_number(pr_number_raw)
    build_ref = build_revision_ref(commit, pr_number)
    label = build_revision_label(build_ref)
    title = build_revision_title(version, commit, build_ref)

    return RevisionInfo(
        version=version,
        commit=commit,
        label=label,
        title=title,
        build_ref=build_ref,
        pr_number=pr_number,
    )
