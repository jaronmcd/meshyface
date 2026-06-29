from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import threading
from collections.abc import Callable, Sequence
from urllib.parse import urlsplit, urlunsplit


@dataclass(frozen=True)
class GitCommandResult:
    returncode: int
    stdout: str
    timed_out: bool = False


GitRunner = Callable[[Sequence[str], Path, float], GitCommandResult]

_UPDATE_LOCK = threading.Lock()


def _truthy_env(name: str) -> bool:
    value = str(os.environ.get(name) or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _run_git(args: Sequence[str], cwd: Path, timeout: float) -> GitCommandResult:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=max(1.0, float(timeout)),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout if isinstance(exc.stdout, str) else ""
        return GitCommandResult(
            returncode=124,
            stdout=(output or "git command timed out").strip(),
            timed_out=True,
        )
    except OSError as exc:
        return GitCommandResult(returncode=127, stdout=str(exc), timed_out=False)
    return GitCommandResult(returncode=int(proc.returncode), stdout=(proc.stdout or "").strip())


def _git_text(result: GitCommandResult) -> str:
    return str(result.stdout or "").strip()


def _short_text(value: object, *, limit: int = 1600) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _clean_branch_name(value: object) -> str:
    branch = str(value or "").strip()
    if not branch or len(branch) > 180:
        return ""
    if branch.startswith("-") or branch.endswith("/") or branch.endswith("."):
        return ""
    if "\\" in branch or ".." in branch or "//" in branch or "@{" in branch:
        return ""
    if any(ch in branch for ch in " ~^:?*["):
        return ""
    return branch


def _clean_commit_ref(value: object) -> str:
    commit = str(value or "").strip()
    if not re.fullmatch(r"[0-9A-Fa-f]{7,40}", commit):
        return ""
    return commit.lower()


def _snapshot_branch_stem(branch: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(branch or "").strip()).strip(".-")


def _is_snapshot_branch(branch: object) -> bool:
    name = str(branch or "").strip()
    return name.startswith("rollback/") or name.startswith("snapshot/")


def _candidate_repo_dirs(repo_dir: str | os.PathLike[str] | None = None) -> list[Path]:
    raw_candidates: list[object] = []
    if repo_dir:
        raw_candidates.append(repo_dir)
    env_repo_dir = str(os.environ.get("MESH_DASH_UPDATE_REPO_DIR") or "").strip()
    if env_repo_dir:
        raw_candidates.append(env_repo_dir)
    try:
        raw_candidates.append(Path.cwd())
    except OSError:
        pass
    raw_candidates.append(Path(__file__).resolve().parents[1])

    seen: set[str] = set()
    candidates: list[Path] = []
    for raw in raw_candidates:
        try:
            path = Path(raw).expanduser().resolve()
        except OSError:
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(path)
    return candidates


def _resolve_repo_root(
    *,
    repo_dir: str | os.PathLike[str] | None = None,
    runner: GitRunner = _run_git,
) -> tuple[Path | None, str]:
    if _truthy_env("MESH_DASH_UPDATE_DISABLED"):
        return None, "software update is disabled by MESH_DASH_UPDATE_DISABLED"

    errors: list[str] = []
    for candidate in _candidate_repo_dirs(repo_dir):
        result = runner(["rev-parse", "--show-toplevel"], candidate, 5.0)
        if result.returncode == 0:
            root_text = _git_text(result)
            if root_text:
                return Path(root_text), ""
        error = _short_text(_git_text(result), limit=220)
        if error:
            errors.append(f"{candidate}: {error}")
    detail = "; ".join(errors[:2])
    if detail:
        return None, f"not a Git checkout ({detail})"
    return None, "not a Git checkout"


def _redact_remote_url(remote_url: str) -> str:
    value = str(remote_url or "").strip()
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
    except Exception:
        return value
    if not parsed.scheme or "@" not in parsed.netloc:
        return value
    host = parsed.hostname or parsed.netloc.rsplit("@", 1)[-1]
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path, "", ""))


def _split_upstream(upstream: str) -> tuple[str, str]:
    value = str(upstream or "").strip()
    if "/" not in value:
        return value, ""
    remote, branch = value.split("/", 1)
    return remote.strip(), branch.strip()


def _remote_names(repo_root: Path, runner: GitRunner) -> list[str]:
    result = runner(["remote"], repo_root, 5.0)
    if result.returncode != 0:
        return []
    names: list[str] = []
    seen: set[str] = set()
    for raw in _git_text(result).splitlines():
        name = str(raw or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def _default_update_remote(
    repo_root: Path,
    *,
    preferred_remote: str = "",
    runner: GitRunner,
) -> str:
    forced = str(os.environ.get("MESH_DASH_UPDATE_REMOTE") or "").strip()
    names = _remote_names(repo_root, runner)
    for candidate in (forced, preferred_remote, "meshyface", "origin"):
        clean = str(candidate or "").strip()
        if clean and clean in names:
            return clean
    return names[0] if names else ""


def _remote_branches(repo_root: Path, remote: str, runner: GitRunner) -> list[str]:
    clean_remote = str(remote or "").strip()
    if not clean_remote:
        return []
    result = runner(
        ["for-each-ref", "--format=%(refname:short)", f"refs/remotes/{clean_remote}"],
        repo_root,
        8.0,
    )
    if result.returncode != 0:
        return []
    prefix = f"{clean_remote}/"
    branches: list[str] = []
    seen: set[str] = set()
    for raw in _git_text(result).splitlines():
        ref = str(raw or "").strip()
        if not ref.startswith(prefix):
            continue
        branch = ref[len(prefix) :].strip()
        if not branch or branch == "HEAD" or branch in seen:
            continue
        if not _clean_branch_name(branch):
            continue
        seen.add(branch)
        branches.append(branch)
    return sorted(branches)


def _local_branches(repo_root: Path, runner: GitRunner) -> list[str]:
    result = runner(
        ["for-each-ref", "--format=%(refname:short)", "refs/heads"],
        repo_root,
        8.0,
    )
    if result.returncode != 0:
        return []
    return _normalize_branch_options(_git_text(result).splitlines())


def _normalize_branch_options(branches: Sequence[object]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in branches:
        branch = _clean_branch_name(raw)
        if not branch or branch in seen:
            continue
        seen.add(branch)
        normalized.append(branch)
    return sorted(normalized)


def _live_remote_branches(repo_root: Path, remote: str, runner: GitRunner) -> list[str]:
    clean_remote = str(remote or "").strip()
    if not clean_remote:
        return []
    result = runner(["ls-remote", "--heads", clean_remote], repo_root, 20.0)
    if result.returncode != 0:
        return []
    branches: list[str] = []
    for raw in _git_text(result).splitlines():
        parts = str(raw or "").strip().split()
        if len(parts) < 2:
            continue
        ref = parts[1].strip()
        if not ref.startswith("refs/heads/"):
            continue
        branches.append(ref.removeprefix("refs/heads/"))
    return _normalize_branch_options(branches)


def _current_branch(repo_root: Path, runner: GitRunner) -> str:
    result = runner(["branch", "--show-current"], repo_root, 5.0)
    return _git_text(result) if result.returncode == 0 else ""


def _previous_checkout_branch(repo_root: Path, runner: GitRunner) -> str:
    result = runner(["rev-parse", "--abbrev-ref", "@{-1}"], repo_root, 5.0)
    if result.returncode != 0:
        return ""
    branch = _clean_branch_name(_git_text(result))
    return "" if branch == "HEAD" else branch


def _current_commit(repo_root: Path, runner: GitRunner) -> str:
    result = runner(["rev-parse", "--verify", "HEAD^{commit}"], repo_root, 5.0)
    return _git_text(result) if result.returncode == 0 else ""


def _working_tree_dirty(repo_root: Path, runner: GitRunner) -> bool:
    result = runner(["status", "--porcelain"], repo_root, 8.0)
    if result.returncode != 0:
        return True
    return bool(_git_text(result))


def _configured_upstream(
    repo_root: Path,
    *,
    branch: str,
    runner: GitRunner,
) -> tuple[str, str, str]:
    forced = str(os.environ.get("MESH_DASH_UPDATE_UPSTREAM") or "").strip()
    if forced:
        remote, remote_branch = _split_upstream(forced)
        return forced, remote, remote_branch

    result = runner(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        repo_root,
        5.0,
    )
    if result.returncode == 0:
        upstream = _git_text(result)
        remote, remote_branch = _split_upstream(upstream)
        return upstream, remote, remote_branch

    if branch == "main":
        remote_names = set(_remote_names(repo_root, runner))
        if "meshyface" in remote_names:
            return "meshyface/main", "meshyface", "main"
        if "origin" in remote_names:
            return "origin/main", "origin", "main"

    return "", "", ""


def _remote_url(repo_root: Path, remote: str, runner: GitRunner) -> str:
    if not remote:
        return ""
    result = runner(["remote", "get-url", remote], repo_root, 5.0)
    if result.returncode != 0:
        return ""
    return _redact_remote_url(_git_text(result))


def _github_repo_url(remote_url: str) -> str:
    value = str(remote_url or "").strip()
    if not value:
        return ""
    if value.startswith("git@github.com:"):
        path = value.split(":", 1)[1].strip()
        if path.endswith(".git"):
            path = path[:-4]
        return f"https://github.com/{path.strip('/')}" if path else ""
    try:
        parsed = urlsplit(value)
    except Exception:
        return ""
    host = (parsed.hostname or "").lower()
    if host != "github.com":
        return ""
    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return f"https://github.com/{path}" if path else ""


_VERSION_BUMP_SUBJECT_RE = re.compile(
    r"^Bump version to v(?P<version>\d+\.\d+\.\d+)(?:\s+\[skip ci\])?$",
    flags=re.IGNORECASE,
)


def _parse_update_history_record(record: str, repo_url: str) -> dict[str, object] | None:
    fields = str(record or "").strip("\n\x1e").split("\x1f", 4)
    if len(fields) < 4:
        return None
    commit, commit_short, date_text, subject = (field.strip() for field in fields[:4])
    body = fields[4].strip() if len(fields) > 4 else ""
    number = ""
    title = subject

    merge_match = re.search(r"\bMerge pull request #(\d+)\b", subject, flags=re.IGNORECASE)
    if merge_match:
        number = merge_match.group(1)
        body_lines = [line.strip() for line in body.splitlines() if line.strip()]
        if body_lines:
            title = body_lines[0]
    else:
        squash_match = re.search(r"\(#(\d+)\)\s*$", subject)
        if squash_match:
            number = squash_match.group(1)
            title = subject[: squash_match.start()].strip()

    message = subject
    if body:
        message = f"{subject}\n\n{body}"
    if number:
        url = f"{repo_url}/pull/{number}" if repo_url else ""
    else:
        url = f"{repo_url}/commit/{commit}" if repo_url and commit else ""
    return {
        "number": number,
        "title": title or (f"Pull request #{number}" if number else commit_short or "Commit"),
        "subject": subject,
        "body": body,
        "message": message,
        "date": date_text,
        "commit": commit,
        "commit_short": commit_short,
        "url": url,
    }


def _parse_version_bump_history_record(record: str) -> dict[str, str] | None:
    fields = str(record or "").strip("\n\x1e").split("\x1f", 4)
    if len(fields) < 4:
        return None
    commit, commit_short, _date_text, subject = (field.strip() for field in fields[:4])
    match = _VERSION_BUMP_SUBJECT_RE.search(subject)
    if not match:
        return None
    version = match.group("version")
    return {
        "version": version,
        "version_label": f"v{version}",
        "version_commit": commit,
        "version_commit_short": commit_short,
    }


def _commit_history(
    repo_root: Path,
    history_ref: str,
    remote_url: str,
    runner: GitRunner,
    *,
    limit: int = 8,
) -> list[dict[str, object]]:
    ref = str(history_ref or "").strip()
    if not ref:
        return []
    result = runner(
        [
            "log",
            "--first-parent",
            "--max-count=25",
            "--date=short",
            "--pretty=format:%H%x1f%h%x1f%ad%x1f%s%x1f%b%x1e",
            ref,
        ],
        repo_root,
        10.0,
    )
    if result.returncode != 0:
        return []
    repo_url = _github_repo_url(remote_url)
    rows: list[dict[str, object]] = []
    pending_version: dict[str, str] | None = None
    for raw_record in _git_text(result).split("\x1e"):
        version_bump = _parse_version_bump_history_record(raw_record)
        if version_bump:
            pending_version = version_bump
            continue
        row = _parse_update_history_record(raw_record, repo_url)
        if not row:
            continue
        if pending_version:
            row.update(pending_version)
            pending_version = None
        rows.append(row)
        if len(rows) >= limit:
            break
    return rows


def _update_history_ref(
    repo_root: Path,
    *,
    current_branch: str,
    selected_branch: str,
    selected_available: bool,
    target_upstream: str,
    current_upstream: str,
    runner: GitRunner,
) -> str:
    if selected_branch and selected_branch == current_branch:
        return "HEAD"
    if target_upstream:
        return target_upstream
    if selected_available and selected_branch and _local_branch_exists(repo_root, selected_branch, runner):
        return selected_branch
    return target_upstream or current_upstream or "HEAD"


def _annotate_commit_history(
    repo_root: Path,
    rows: Sequence[dict[str, object]],
    running_commit: str,
    runner: GitRunner,
) -> list[dict[str, object]]:
    commit = str(running_commit or "").strip()
    running_index = -1
    for index, row in enumerate(rows):
        if str(row.get("commit") or "").strip() == commit:
            running_index = index
            break

    annotated: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        next_row = dict(row)
        is_running = index == running_index
        recovery_required = not is_running and not _commit_supports_in_app_recovery(
            repo_root,
            str(row.get("commit") or ""),
            runner,
        )
        if is_running:
            state = "running"
            label = "Running"
        elif recovery_required:
            state = "recovery_required"
            label = "Recovery Required"
        elif running_index >= 0 and index > running_index:
            state = "previous"
            label = "Previous"
        else:
            state = "available"
            label = "Available"
        next_row.update(
            {
                "running": is_running,
                "recovery_required": recovery_required,
                "timeline_state": state,
                "timeline_label": label,
            }
        )
        annotated.append(next_row)
    return annotated


def _commit_supports_in_app_recovery(repo_root: Path, commit: str, runner: GitRunner) -> bool:
    commit_ref = _clean_commit_ref(commit)
    if not commit_ref:
        return False
    checks = [
        (
            "rollback_update_to_commit",
            "meshdash/api_system_update.py",
        ),
        (
            "runSettingsHistoryRollback",
            "meshdash/assets/dashboard.js.chat.events.settings.state_normalize.render_read.tmpl",
        ),
    ]
    for pattern, path in checks:
        result = runner(["grep", "-q", pattern, commit_ref, "--", path], repo_root, 5.0)
        if result.returncode != 0:
            return False
    return True


def _git_config_get(repo_root: Path, key: str, runner: GitRunner) -> str:
    result = runner(["config", "--get", key], repo_root, 5.0)
    if result.returncode != 0:
        return ""
    return _git_text(result)


def _snapshot_metadata_source_branch(repo_root: Path, branch: str, runner: GitRunner) -> str:
    clean_branch = _clean_branch_name(branch)
    if not clean_branch or not _is_snapshot_branch(clean_branch):
        return ""
    return _clean_branch_name(
        _git_config_get(repo_root, f"branch.{clean_branch}.mesh-dashboard-source-branch", runner)
    )


def _snapshot_source_branch(
    repo_root: Path,
    *,
    branch: str,
    branch_options: Sequence[str],
    previous_branch: str,
    runner: GitRunner,
) -> str:
    if not _is_snapshot_branch(branch):
        return ""

    configured = _clean_branch_name(
        _git_config_get(repo_root, f"branch.{branch}.mesh-dashboard-source-branch", runner)
    )
    if configured and configured in branch_options:
        return configured

    if previous_branch and previous_branch in branch_options:
        return previous_branch

    for candidate in branch_options:
        stem = _snapshot_branch_stem(candidate)
        if stem and re.fullmatch(rf"(?:rollback|snapshot)/{re.escape(stem)}-[0-9a-fA-F]{{7,40}}", branch):
            return candidate
    return ""


def _ahead_behind(repo_root: Path, upstream: str, runner: GitRunner) -> tuple[int | None, int | None]:
    if not upstream:
        return None, None
    return _ahead_behind_refs(repo_root, "HEAD", upstream, runner)


def _ahead_behind_refs(
    repo_root: Path,
    left_ref: str,
    right_ref: str,
    runner: GitRunner,
) -> tuple[int | None, int | None]:
    if not left_ref or not right_ref:
        return None, None
    result = runner(
        ["rev-list", "--left-right", "--count", f"{left_ref}...{right_ref}"],
        repo_root,
        10.0,
    )
    if result.returncode != 0:
        return None, None
    parts = _git_text(result).replace("\t", " ").split()
    if len(parts) < 2:
        return None, None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None, None


def _status_state(
    *,
    available: bool,
    branch: str,
    target_branch: str,
    target_available: bool,
    target_remote_available: bool,
    target_local_available: bool,
    dirty: bool,
    ahead: int | None,
    behind: int | None,
) -> tuple[str, str, bool, bool]:
    if not available:
        return "unavailable", "Software update is unavailable.", False, False
    if not branch:
        return "detached", "Software update is unavailable on a detached Git checkout.", False, False
    if not target_branch:
        return "select_branch", "Select a GitHub branch to update from.", False, False
    if not target_available:
        return "invalid_branch", f"GitHub branch {target_branch} is not available.", False, False
    if dirty:
        return "dirty", "Software update is blocked by local uncommitted changes.", False, False
    if target_branch != branch:
        if target_local_available and not target_remote_available:
            return (
                "local_switch_available",
                f"Ready to switch from {branch} to local branch {target_branch}.",
                True,
                True,
            )
        return (
            "switch_available",
            f"Ready to switch from {branch} to {target_branch}.",
            True,
            True,
        )
    if target_local_available and not target_remote_available:
        return "local_branch", f"Running local branch {target_branch}.", False, False
    if ahead is not None and behind is not None:
        if ahead > 0 and behind > 0:
            return "diverged", "Software update is blocked because local and remote commits diverged.", False, True
        if ahead > 0:
            return "local_ahead", "Software update is blocked because this checkout has local-only commits.", False, False
        if behind > 0:
            return "update_available", f"Update available: {behind} commit(s) behind {target_branch}.", True, True
        return "up_to_date", "Software is up to date.", True, False
    return "ready", "Software update is ready to check GitHub.", True, False


def _select_target_branch(
    *,
    requested_branch: object,
    current_branch: str,
    upstream_branch: str,
    branch_options: Sequence[str],
) -> tuple[str, bool]:
    requested_raw = str(requested_branch or "").strip()
    requested = _clean_branch_name(requested_raw)
    if requested_raw and not requested:
        return "", False
    if requested:
        return requested, requested in branch_options
    if upstream_branch and upstream_branch in branch_options:
        return upstream_branch, True
    if current_branch and current_branch in branch_options:
        return current_branch, True
    return "", False


def build_update_status_payload(
    *,
    repo_dir: str | os.PathLike[str] | None = None,
    target_branch: object = None,
    runner: GitRunner = _run_git,
    remote_branches_override: Sequence[object] | None = None,
    local_branches_override: Sequence[object] | None = None,
) -> dict[str, object]:
    repo_root, error = _resolve_repo_root(repo_dir=repo_dir, runner=runner)
    if repo_root is None:
        return {
            "ok": True,
            "available": False,
            "state": "unavailable",
            "can_update": False,
            "update_needed": False,
            "error": error,
            "message": error,
        }

    branch = _current_branch(repo_root, runner)
    commit = _current_commit(repo_root, runner)
    current_upstream, current_remote, current_remote_branch = _configured_upstream(
        repo_root,
        branch=branch,
        runner=runner,
    )
    remote = _default_update_remote(repo_root, preferred_remote=current_remote, runner=runner)
    branch_options = (
        _normalize_branch_options(remote_branches_override)
        if remote_branches_override is not None
        else _remote_branches(repo_root, remote, runner)
    )
    local_branch_options = (
        _normalize_branch_options(local_branches_override)
        if local_branches_override is not None
        else _local_branches(repo_root, runner)
    )
    rollback_branch_options = _normalize_branch_options(
        branch_name for branch_name in local_branch_options if _is_snapshot_branch(branch_name)
    )
    managed_rollback_branch_options = _normalize_branch_options(
        branch_name
        for branch_name in rollback_branch_options
        if _snapshot_metadata_source_branch(repo_root, branch_name, runner)
    )
    previous_branch = _previous_checkout_branch(repo_root, runner)
    snapshot_source_branch = _snapshot_source_branch(
        repo_root,
        branch=branch,
        branch_options=branch_options,
        previous_branch=previous_branch,
        runner=runner,
    )
    local_rollback_options = _normalize_branch_options(
        branch_name
        for branch_name in (branch, previous_branch)
        if branch_name
        and branch_name in local_branch_options
        and branch_name not in branch_options
        and not (_is_snapshot_branch(branch_name) and snapshot_source_branch)
    )
    combined_branch_options = _normalize_branch_options([*branch_options, *local_rollback_options])
    selected_branch, selected_available = _select_target_branch(
        requested_branch=target_branch,
        current_branch="" if snapshot_source_branch else branch,
        upstream_branch=snapshot_source_branch or current_remote_branch,
        branch_options=combined_branch_options,
    )
    selected_remote_available = selected_branch in branch_options
    selected_local_available = selected_branch in local_rollback_options
    selected_available = bool(selected_remote_available or selected_local_available)
    target_upstream = f"{remote}/{selected_branch}" if remote and selected_branch and selected_remote_available else ""
    dirty = _working_tree_dirty(repo_root, runner)
    ahead, behind = _ahead_behind(repo_root, target_upstream, runner)
    remote_url = _remote_url(repo_root, remote, runner)
    history_ref = _update_history_ref(
        repo_root,
        current_branch=branch,
        selected_branch=selected_branch,
        selected_available=selected_available,
        target_upstream=target_upstream,
        current_upstream=current_upstream,
        runner=runner,
    )
    commit_history = _annotate_commit_history(
        repo_root,
        _commit_history(repo_root, history_ref, remote_url, runner),
        commit,
        runner,
    )

    state, message, can_update, update_needed = _status_state(
        available=True,
        branch=branch,
        target_branch=selected_branch,
        target_available=selected_available,
        target_remote_available=selected_remote_available,
        target_local_available=selected_local_available,
        dirty=dirty,
        ahead=ahead,
        behind=behind,
    )
    return {
        "ok": True,
        "available": True,
        "state": state,
        "message": message,
        "repo_root": str(repo_root),
        "branch": branch,
        "current_upstream": current_upstream,
        "current_remote": current_remote,
        "current_remote_branch": current_remote_branch,
        "upstream": target_upstream,
        "target_branch": selected_branch,
        "history_branch": selected_branch,
        "target_upstream": target_upstream,
        "remote": remote,
        "remote_branch": selected_branch,
        "remote_url": remote_url,
        "branches": combined_branch_options,
        "remote_branches": branch_options,
        "local_branches": local_rollback_options,
        "rollback_branches": rollback_branch_options,
        "cleanup_rollback_branches": _normalize_branch_options(
            branch_name for branch_name in managed_rollback_branch_options if branch_name != branch
        ),
        "previous_branch": previous_branch,
        "snapshot_branch": branch if _is_snapshot_branch(branch) else "",
        "snapshot_source_branch": snapshot_source_branch,
        "target_remote_available": selected_remote_available,
        "target_local_available": selected_local_available,
        "target_source": "remote" if selected_remote_available else ("local" if selected_local_available else ""),
        "current_commit": commit,
        "current_commit_short": commit[:8] if commit else "",
        "running_commit": commit,
        "running_commit_short": commit[:8] if commit else "",
        "dirty": dirty,
        "ahead": ahead,
        "behind": behind,
        "can_update": can_update,
        "update_needed": update_needed,
        "commit_history": commit_history,
        "pull_request_history": commit_history,
    }


def _changed_files(
    repo_root: Path,
    old_commit: str,
    new_commit: str,
    runner: GitRunner,
) -> list[str]:
    if not old_commit or not new_commit or old_commit == new_commit:
        return []
    result = runner(["diff", "--name-only", old_commit, new_commit], repo_root, 10.0)
    if result.returncode != 0:
        return []
    return [line.strip() for line in _git_text(result).splitlines() if line.strip()][:50]


def _failure_payload(
    status: dict[str, object],
    *,
    state: str,
    message: str,
    http_status: int = 409,
    error: str = "",
) -> dict[str, object]:
    payload = dict(status)
    payload.update(
        {
            "ok": False,
            "updated": False,
            "state": state,
            "message": message,
            "error": error or message,
            "http_status": http_status,
        }
    )
    return payload


def _fetch_prune_failure_can_fallback(result: GitCommandResult) -> bool:
    if result.returncode == 0 or result.timed_out:
        return False
    text = _git_text(result).lower()
    return any(
        marker in text
        for marker in (
            "could not delete references",
            "cannot lock ref",
            "unable to create",
            "permission denied",
            "unable to update local ref",
        )
    )


def _fetch_remote_with_prune_fallback(
    repo_root: Path,
    remote: str,
    runner: GitRunner,
    timeout: float,
    *,
    selected_branch: str = "",
    fetch_selected_only: bool = False,
) -> tuple[GitCommandResult, str, bool]:
    prune_result = runner(["fetch", "--prune", remote], repo_root, timeout)
    if prune_result.returncode == 0 or not _fetch_prune_failure_can_fallback(prune_result):
        return prune_result, "", False

    clean_branch = _clean_branch_name(selected_branch)
    fallback_args = ["fetch", remote]
    if fetch_selected_only and clean_branch:
        fallback_args = [
            "fetch",
            remote,
            f"+refs/heads/{clean_branch}:refs/remotes/{remote}/{clean_branch}",
        ]
    fallback_result = runner(fallback_args, repo_root, timeout)
    prune_error = _short_text(_git_text(prune_result))
    if fallback_result.returncode == 0:
        return fallback_result, prune_error, True

    fallback_error = _short_text(_git_text(fallback_result))
    combined = prune_error
    if fallback_error:
        combined = f"{combined}\nFallback fetch without prune also failed:\n{fallback_error}"
    return GitCommandResult(
        returncode=fallback_result.returncode,
        stdout=combined,
        timed_out=fallback_result.timed_out,
    ), "", False


def _apply_prune_recovery_status(
    payload: dict[str, object],
    *,
    prune_error: str,
) -> dict[str, object]:
    recovered = dict(payload)
    message = str(recovered.get("message") or "").strip()
    if str(recovered.get("state") or "") in {"invalid_branch", "select_branch", "local_branch"}:
        suffix = "Select a live branch to recover; local stale Git refs could not be pruned automatically."
        message = f"{message} {suffix}".strip()
    recovered.update(
        {
            "ok": True,
            "connection_ok": True,
            "prune_failed": True,
            "prune_error": prune_error,
            "error": prune_error,
            "message": message or "GitHub is reachable, but local stale Git refs could not be pruned automatically.",
            "http_status": 200,
        }
    )
    return recovered


def _local_branch_exists(repo_root: Path, branch: str, runner: GitRunner) -> bool:
    clean = _clean_branch_name(branch)
    if not clean:
        return False
    result = runner(["show-ref", "--verify", "--quiet", f"refs/heads/{clean}"], repo_root, 5.0)
    return result.returncode == 0


def _ref_short_commit(repo_root: Path, ref: str, runner: GitRunner) -> str:
    clean_ref = str(ref or "").strip()
    if not clean_ref:
        return ""
    result = runner(["rev-parse", "--short=7", clean_ref], repo_root, 5.0)
    return _git_text(result) if result.returncode == 0 else ""


def _sync_backup_branch_name(repo_root: Path, branch: str, runner: GitRunner) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", str(branch or "").strip()).strip(".-")
    if not stem:
        stem = "branch"
    short_commit = _ref_short_commit(repo_root, branch, runner) or "local"
    base = f"{stem[:120]}-before-sync-{short_commit}"
    for idx in range(50):
        candidate = base if idx == 0 else f"{base}-{idx + 1}"
        if _clean_branch_name(candidate) and not _local_branch_exists(repo_root, candidate, runner):
            return candidate
    return ""


def _rollback_branch_name(branch: str, commit: str) -> str:
    stem = _snapshot_branch_stem(branch)
    if not stem:
        stem = "branch"
    short_commit = _clean_commit_ref(commit)[:12] or "commit"
    candidate = f"rollback/{stem[:100]}-{short_commit}"
    return candidate if _clean_branch_name(candidate) else ""


def refresh_update_status_from_github(
    *,
    repo_dir: str | os.PathLike[str] | None = None,
    target_branch: object = None,
    runner: GitRunner = _run_git,
    fetch_timeout: float = 60.0,
) -> dict[str, object]:
    if not _UPDATE_LOCK.acquire(blocking=False):
        return {
            "ok": False,
            "available": True,
            "state": "busy",
            "can_update": False,
            "update_needed": False,
            "connection_ok": False,
            "refreshed": False,
            "message": "Software update is already running.",
            "error": "software update is already running",
            "http_status": 409,
        }

    try:
        status = build_update_status_payload(
            repo_dir=repo_dir,
            target_branch=target_branch,
            runner=runner,
        )
        if not bool(status.get("available")):
            payload = dict(status)
            payload.update({"connection_ok": False, "refreshed": False})
            return payload

        repo_root = Path(str(status.get("repo_root") or "."))
        remote = str(status.get("remote") or "").strip()
        if not remote:
            payload = dict(status)
            payload.update(
                {
                    "ok": False,
                    "state": "no_remote",
                    "connection_ok": False,
                    "refreshed": False,
                    "message": "Software update check needs a configured Git remote.",
                    "error": "no git remote is configured",
                    "http_status": 409,
                }
            )
            return payload

        selected_branch = str(status.get("target_branch") or target_branch or "").strip()
        fetch_result, prune_error, used_prune_fallback = _fetch_remote_with_prune_fallback(
            repo_root,
            remote,
            runner,
            fetch_timeout,
            selected_branch=selected_branch,
        )
        if fetch_result.returncode != 0:
            error_text = _short_text(_git_text(fetch_result))
            live_branches = _live_remote_branches(repo_root, remote, runner)
            if live_branches and _fetch_prune_failure_can_fallback(fetch_result):
                payload = build_update_status_payload(
                    repo_dir=repo_root,
                    target_branch=target_branch,
                    runner=runner,
                    remote_branches_override=live_branches,
                )
                return _apply_prune_recovery_status(payload, prune_error=error_text)
            message = "Could not reach GitHub or check updates."
            if fetch_result.timed_out:
                message = "GitHub update check timed out."
            payload = dict(status)
            payload.update(
                {
                    "ok": False,
                    "state": "fetch_failed",
                    "can_update": False,
                    "update_needed": False,
                    "connection_ok": False,
                    "refreshed": False,
                    "message": message,
                    "error": error_text or message,
                    "http_status": 503,
                }
            )
            return payload

        live_branch_override = _live_remote_branches(repo_root, remote, runner) if used_prune_fallback else []
        payload = build_update_status_payload(
            repo_dir=repo_root,
            target_branch=target_branch,
            runner=runner,
            remote_branches_override=live_branch_override or None,
        )
        if used_prune_fallback:
            payload = _apply_prune_recovery_status(payload, prune_error=prune_error)
        payload.update(
            {
                "connection_ok": True,
                "refreshed": True,
                "http_status": 200,
            }
        )
        return payload
    finally:
        _UPDATE_LOCK.release()


def run_update_from_github(
    *,
    repo_dir: str | os.PathLike[str] | None = None,
    target_branch: object = None,
    runner: GitRunner = _run_git,
    fetch_timeout: float = 60.0,
    merge_timeout: float = 45.0,
) -> dict[str, object]:
    if not _UPDATE_LOCK.acquire(blocking=False):
        return {
            "ok": False,
            "updated": False,
            "available": True,
            "state": "busy",
            "message": "Software update is already running.",
            "error": "software update is already running",
            "http_status": 409,
        }

    try:
        status = build_update_status_payload(
            repo_dir=repo_dir,
            target_branch=target_branch,
            runner=runner,
        )
        if not bool(status.get("available")):
            return _failure_payload(
                status,
                state="unavailable",
                message=str(status.get("message") or "Software update is unavailable."),
                http_status=409,
            )
        if not bool(status.get("can_update")):
            return _failure_payload(
                status,
                state=str(status.get("state") or "blocked"),
                message=str(status.get("message") or "Software update is blocked."),
                http_status=409,
            )

        repo_root = Path(str(status.get("repo_root") or "."))
        remote = str(status.get("remote") or "").strip()
        selected_branch = str(status.get("target_branch") or "").strip()
        target_upstream = str(status.get("target_upstream") or status.get("upstream") or "").strip()
        target_remote_available = bool(status.get("target_remote_available"))
        target_local_available = bool(status.get("target_local_available"))
        if not selected_branch or not (target_upstream or target_local_available):
            return _failure_payload(
                status,
                state="select_branch",
                message="Software update needs a selected GitHub branch.",
                http_status=409,
            )

        if target_local_available and not target_remote_available:
            old_commit = str(status.get("current_commit") or "")
            current_branch = str(status.get("branch") or "").strip()
            if selected_branch == current_branch:
                payload = dict(status)
                payload.update(
                    {
                        "ok": True,
                        "updated": False,
                        "connection_ok": True,
                        "state": "local_branch",
                        "message": f"Already running local branch {selected_branch}.",
                        "http_status": 200,
                    }
                )
                return payload
            switch_result = runner(["switch", selected_branch], repo_root, 20.0)
            if switch_result.returncode != 0:
                error = _short_text(_git_text(switch_result))
                return _failure_payload(
                    status,
                    state="switch_failed",
                    message=f"Could not switch to local branch {selected_branch}.",
                    http_status=409,
                    error=error or "git switch failed",
                )
            final_status = build_update_status_payload(
                repo_dir=repo_root,
                target_branch=selected_branch,
                runner=runner,
            )
            new_commit = str(final_status.get("current_commit") or "")
            changed_files = _changed_files(repo_root, old_commit, new_commit, runner)
            requirements_changed = any(
                path == "requirements.txt" or path == "requirements-dev.txt"
                for path in changed_files
            )
            message = f"Switched to local branch {selected_branch}. Restart the dashboard process to use the selected code."
            if requirements_changed:
                message = (
                    f"Switched to local branch {selected_branch}. Python requirements changed; "
                    "install requirements and restart the dashboard process."
                )
            payload = dict(final_status)
            payload.update(
                {
                    "ok": True,
                    "updated": old_commit != new_commit,
                    "connection_ok": True,
                    "previous_commit": old_commit,
                    "new_commit": new_commit,
                    "changed_files": changed_files,
                    "requirements_changed": requirements_changed,
                    "restart_required": old_commit != new_commit,
                    "message": message,
                    "http_status": 200,
                }
            )
            return payload

        if not remote or not target_upstream:
            return _failure_payload(
                status,
                state="select_branch",
                message="Software update needs a selected GitHub branch.",
                http_status=409,
            )

        fetch_result, _prune_error, used_prune_fallback = _fetch_remote_with_prune_fallback(
            repo_root,
            remote,
            runner,
            fetch_timeout,
            selected_branch=selected_branch,
            fetch_selected_only=True,
        )
        if fetch_result.returncode != 0:
            error = _short_text(_git_text(fetch_result))
            message = "Could not reach GitHub or fetch the update."
            if fetch_result.timed_out:
                message = "GitHub update check timed out."
            live_branches = _live_remote_branches(repo_root, remote, runner)
            if live_branches and selected_branch not in live_branches:
                after_fetch = build_update_status_payload(
                    repo_dir=repo_root,
                    target_branch=selected_branch,
                    runner=runner,
                    remote_branches_override=live_branches,
                )
                return _failure_payload(
                    after_fetch,
                    state=str(after_fetch.get("state") or "invalid_branch"),
                    message=str(
                        after_fetch.get("message")
                        or f"GitHub branch {selected_branch} is not available."
                    ),
                    http_status=409,
                    error=error or message,
                )
            return _failure_payload(
                status,
                state="fetch_failed",
                message=message,
                http_status=503,
                error=error or message,
            )

        live_branch_override = _live_remote_branches(repo_root, remote, runner) if used_prune_fallback else []
        after_fetch = build_update_status_payload(
            repo_dir=repo_root,
            target_branch=selected_branch,
            runner=runner,
            remote_branches_override=live_branch_override or None,
        )
        ahead = after_fetch.get("ahead")
        behind = after_fetch.get("behind")
        if not bool(after_fetch.get("can_update")):
            return _failure_payload(
                after_fetch,
                state=str(after_fetch.get("state") or "blocked"),
                message=str(after_fetch.get("message") or "Software update is blocked."),
                http_status=409,
            )
        if ahead is None or behind is None:
            return _failure_payload(
                after_fetch,
                state="compare_failed",
                message="Fetched updates, but could not compare this checkout with its upstream branch.",
                http_status=409,
            )
        current_branch = str(after_fetch.get("branch") or "").strip()
        target_upstream = str(after_fetch.get("target_upstream") or after_fetch.get("upstream") or "").strip()

        old_commit = str(after_fetch.get("current_commit") or "")
        if selected_branch != current_branch:
            if _local_branch_exists(repo_root, selected_branch, runner):
                branch_ahead, _branch_behind = _ahead_behind_refs(
                    repo_root,
                    selected_branch,
                    target_upstream,
                    runner,
                )
                if branch_ahead is None:
                    return _failure_payload(
                        after_fetch,
                        state="compare_failed",
                        message="Fetched updates, but could not compare the selected local branch with GitHub.",
                        http_status=409,
                    )
                if int(branch_ahead or 0) > 0:
                    return _failure_payload(
                        after_fetch,
                        state="local_branch_ahead",
                        message=(
                            f"Software update is blocked because local branch "
                            f"{selected_branch} has local-only commits."
                        ),
                        http_status=409,
                    )
                switch_result = runner(["switch", selected_branch], repo_root, 20.0)
                if switch_result.returncode != 0:
                    error = _short_text(_git_text(switch_result))
                    return _failure_payload(
                        after_fetch,
                        state="switch_failed",
                        message=f"Fetched updates, but could not switch to {selected_branch}.",
                        http_status=409,
                        error=error or "git switch failed",
                    )
                merge_result = runner(["merge", "--ff-only", target_upstream], repo_root, merge_timeout)
                if merge_result.returncode != 0:
                    error = _short_text(_git_text(merge_result))
                    return _failure_payload(
                        after_fetch,
                        state="merge_failed",
                        message="Switched branches, but fast-forward failed.",
                        http_status=409,
                        error=error or "git merge --ff-only failed",
                    )
            else:
                switch_result = runner(
                    ["switch", "--track", "-c", selected_branch, target_upstream],
                    repo_root,
                    20.0,
                )
                if switch_result.returncode != 0:
                    error = _short_text(_git_text(switch_result))
                    return _failure_payload(
                        after_fetch,
                        state="switch_failed",
                        message=f"Fetched updates, but could not create branch {selected_branch}.",
                        http_status=409,
                        error=error or "git switch --track failed",
                    )
        elif int(ahead or 0) > 0:
            return _failure_payload(
                after_fetch,
                state=str(after_fetch.get("state") or "local_ahead"),
                message=str(after_fetch.get("message") or "Software update is blocked by local commits."),
                http_status=409,
            )
        elif int(behind or 0) <= 0:
            payload = dict(after_fetch)
            payload.update(
                {
                    "ok": True,
                    "updated": False,
                    "connection_ok": True,
                    "state": "up_to_date",
                    "message": "Software is already up to date.",
                    "http_status": 200,
                }
            )
            return payload
        else:
            merge_result = runner(["merge", "--ff-only", target_upstream], repo_root, merge_timeout)
            if merge_result.returncode != 0:
                error = _short_text(_git_text(merge_result))
                return _failure_payload(
                    after_fetch,
                    state="merge_failed",
                    message="Fetched updates, but fast-forward failed.",
                    http_status=409,
                    error=error or "git merge --ff-only failed",
                )

        final_status = build_update_status_payload(
            repo_dir=repo_root,
            target_branch=selected_branch,
            runner=runner,
        )
        new_commit = str(final_status.get("current_commit") or "")
        changed_files = _changed_files(repo_root, old_commit, new_commit, runner)
        requirements_changed = any(
            path == "requirements.txt" or path == "requirements-dev.txt"
            for path in changed_files
        )
        message = "Software update applied. Restart the dashboard process to use the new code."
        if requirements_changed:
            message = (
                "Software update applied. Python requirements changed; install requirements "
                "and restart the dashboard process."
            )
        payload = dict(final_status)
        payload.update(
            {
                "ok": True,
                "updated": old_commit != new_commit,
                "connection_ok": True,
                "previous_commit": old_commit,
                "new_commit": new_commit,
                "changed_files": changed_files,
                "requirements_changed": requirements_changed,
                "restart_required": old_commit != new_commit,
                "message": message,
                "http_status": 200,
            }
        )
        return payload
    finally:
        _UPDATE_LOCK.release()


def rollback_update_to_commit(
    *,
    repo_dir: str | os.PathLike[str] | None = None,
    target_branch: object = None,
    target_commit: object = None,
    runner: GitRunner = _run_git,
) -> dict[str, object]:
    if not _UPDATE_LOCK.acquire(blocking=False):
        return {
            "ok": False,
            "updated": False,
            "available": True,
            "state": "busy",
            "message": "Software update is already running.",
            "error": "software update is already running",
            "http_status": 409,
        }

    try:
        commit_ref = _clean_commit_ref(target_commit)
        if not commit_ref:
            return {
                "ok": False,
                "updated": False,
                "available": True,
                "state": "invalid_commit",
                "message": "Rollback needs a valid commit from the selected branch history.",
                "error": "invalid rollback commit",
                "http_status": 400,
            }

        status = build_update_status_payload(
            repo_dir=repo_dir,
            target_branch=target_branch,
            runner=runner,
        )
        if not bool(status.get("available")):
            return _failure_payload(
                status,
                state="unavailable",
                message=str(status.get("message") or "Software update is unavailable."),
                http_status=409,
            )
        if bool(status.get("dirty")):
            return _failure_payload(
                status,
                state="dirty",
                message="Rollback is blocked by local uncommitted changes.",
                http_status=409,
            )

        repo_root = Path(str(status.get("repo_root") or "."))
        selected_branch = str(status.get("target_branch") or "").strip()
        if not selected_branch:
            return _failure_payload(
                status,
                state="select_branch",
                message="Rollback needs a selected branch.",
                http_status=409,
            )

        commit_result = runner(["rev-parse", "--verify", f"{commit_ref}^{{commit}}"], repo_root, 5.0)
        if commit_result.returncode != 0:
            error = _short_text(_git_text(commit_result))
            return _failure_payload(
                status,
                state="invalid_commit",
                message="Rollback commit is not available in this checkout.",
                http_status=409,
                error=error or "rollback commit not found",
            )
        full_commit = _git_text(commit_result)
        target_upstream = str(status.get("target_upstream") or status.get("upstream") or "").strip()
        target_ref = target_upstream if bool(status.get("target_remote_available")) else ""
        if not target_ref and bool(status.get("target_local_available")):
            target_ref = selected_branch
        if not target_ref:
            return _failure_payload(
                status,
                state="invalid_branch",
                message=f"Rollback branch {selected_branch} is not available.",
                http_status=409,
            )

        ancestor_result = runner(["merge-base", "--is-ancestor", full_commit, target_ref], repo_root, 10.0)
        if ancestor_result.returncode != 0:
            error = _short_text(_git_text(ancestor_result))
            return _failure_payload(
                status,
                state="invalid_commit",
                message=f"Rollback commit is not in {selected_branch} history.",
                http_status=409,
                error=error or "rollback commit is not an ancestor of the selected branch",
            )

        rollback_branch = _rollback_branch_name(selected_branch, full_commit)
        if not rollback_branch:
            return _failure_payload(
                status,
                state="invalid_branch",
                message="Could not choose a local rollback branch name.",
                http_status=409,
                error="rollback branch name could not be generated",
            )

        old_commit = str(status.get("current_commit") or "")
        switch_result = runner(["switch", "-C", rollback_branch, full_commit], repo_root, 20.0)
        if switch_result.returncode != 0:
            error = _short_text(_git_text(switch_result))
            return _failure_payload(
                status,
                state="rollback_failed",
                message=f"Could not switch to rollback branch {rollback_branch}.",
                http_status=409,
                error=error or "git switch -C failed",
            )

        runner(
            ["config", f"branch.{rollback_branch}.mesh-dashboard-source-branch", selected_branch],
            repo_root,
            5.0,
        )
        final_status = build_update_status_payload(
            repo_dir=repo_root,
            target_branch=selected_branch,
            runner=runner,
        )
        new_commit = str(final_status.get("current_commit") or "")
        changed_files = _changed_files(repo_root, old_commit, new_commit, runner)
        requirements_changed = any(
            path == "requirements.txt" or path == "requirements-dev.txt"
            for path in changed_files
        )
        message = (
            f"Rolled back to {full_commit[:8]} on local branch {rollback_branch}. "
            "Restart the dashboard process to use the selected code."
        )
        if requirements_changed:
            message = (
                f"Rolled back to {full_commit[:8]} on local branch {rollback_branch}. "
                "Python requirements changed; install requirements and restart the dashboard process."
            )
        payload = dict(final_status)
        payload.update(
            {
                "ok": True,
                "updated": old_commit != new_commit,
                "connection_ok": True,
                "rollback": True,
                "rollback_branch": rollback_branch,
                "rollback_commit": full_commit,
                "previous_commit": old_commit,
                "new_commit": new_commit,
                "changed_files": changed_files,
                "requirements_changed": requirements_changed,
                "restart_required": old_commit != new_commit,
                "message": message,
                "http_status": 200,
            }
        )
        return payload
    finally:
        _UPDATE_LOCK.release()


def _rollback_cleanup_message(
    *,
    deleted_count: int,
    protected_count: int,
    failed_count: int,
) -> str:
    if failed_count:
        base = "Rollback cleanup could not delete every local snapshot branch."
        if deleted_count:
            plural = "es" if deleted_count != 1 else ""
            base = f"Deleted {deleted_count} local rollback branch{plural}, but some cleanup failed."
        return base
    if deleted_count:
        suffix = ""
        if protected_count:
            suffix = " The checked-out rollback branch was left in place."
        plural = "es" if deleted_count != 1 else ""
        return f"Deleted {deleted_count} local rollback branch{plural}.{suffix}"
    if protected_count:
        return "No inactive rollback branches to clean up. The checked-out rollback branch was left in place."
    return "No local rollback branches to clean up."


def cleanup_update_rollback_branches(
    *,
    repo_dir: str | os.PathLike[str] | None = None,
    runner: GitRunner = _run_git,
) -> dict[str, object]:
    if not _UPDATE_LOCK.acquire(blocking=False):
        return {
            "ok": False,
            "cleanup": False,
            "available": True,
            "state": "busy",
            "message": "Software update is already running.",
            "error": "software update is already running",
            "http_status": 409,
        }

    try:
        repo_root, error = _resolve_repo_root(repo_dir=repo_dir, runner=runner)
        if repo_root is None:
            return {
                "ok": False,
                "cleanup": False,
                "available": False,
                "state": "unavailable",
                "can_update": False,
                "update_needed": False,
                "message": error,
                "error": error,
                "http_status": 409,
            }

        current_branch = _current_branch(repo_root, runner)
        rollback_branches = _normalize_branch_options(
            branch_name
            for branch_name in _local_branches(repo_root, runner)
            if _snapshot_metadata_source_branch(repo_root, branch_name, runner)
        )
        deleted: list[str] = []
        protected: list[str] = []
        failed: list[dict[str, str]] = []
        for branch_name in rollback_branches:
            if branch_name == current_branch:
                protected.append(branch_name)
                continue
            result = runner(["branch", "-D", branch_name], repo_root, 10.0)
            if result.returncode == 0:
                deleted.append(branch_name)
                continue
            failed.append(
                {
                    "branch": branch_name,
                    "error": _short_text(_git_text(result), limit=360) or "git branch -D failed",
                }
            )

        payload = build_update_status_payload(repo_dir=repo_root, runner=runner)
        failed_count = len(failed)
        message = _rollback_cleanup_message(
            deleted_count=len(deleted),
            protected_count=len(protected),
            failed_count=failed_count,
        )
        payload.update(
            {
                "ok": failed_count == 0,
                "cleanup": True,
                "deleted": deleted,
                "deleted_count": len(deleted),
                "protected": protected,
                "protected_count": len(protected),
                "failed": failed,
                "failed_count": failed_count,
                "state": "rollback_cleanup_failed" if failed_count else "rollback_cleanup_complete",
                "message": message,
                "error": message if failed_count else "",
                "http_status": 409 if failed_count else 200,
            }
        )
        return payload
    finally:
        _UPDATE_LOCK.release()


def sync_update_branches_from_github(
    *,
    repo_dir: str | os.PathLike[str] | None = None,
    target_branch: object = None,
    runner: GitRunner = _run_git,
    fetch_timeout: float = 60.0,
) -> dict[str, object]:
    if not _UPDATE_LOCK.acquire(blocking=False):
        return {
            "ok": False,
            "synced": False,
            "updated": False,
            "available": True,
            "state": "busy",
            "message": "Software update is already running.",
            "error": "software update is already running",
            "http_status": 409,
        }

    try:
        repo_root, error = _resolve_repo_root(repo_dir=repo_dir, runner=runner)
        if repo_root is None:
            return {
                "ok": False,
                "synced": False,
                "updated": False,
                "available": False,
                "state": "unavailable",
                "can_update": False,
                "update_needed": False,
                "message": error,
                "error": error,
                "http_status": 409,
            }

        branch = _current_branch(repo_root, runner)
        old_commit = _current_commit(repo_root, runner)
        _current_upstream, current_remote, _current_remote_branch = _configured_upstream(
            repo_root,
            branch=branch,
            runner=runner,
        )
        remote = _default_update_remote(repo_root, preferred_remote=current_remote, runner=runner)
        if not remote:
            return {
                "ok": False,
                "synced": False,
                "updated": False,
                "available": False,
                "state": "no_remote",
                "can_update": False,
                "update_needed": False,
                "message": "Software branch sync needs a configured Git remote.",
                "error": "no git remote is configured",
                "http_status": 409,
            }

        fetch_result = runner(["fetch", "--prune", remote], repo_root, fetch_timeout)
        if fetch_result.returncode != 0:
            error_text = _short_text(_git_text(fetch_result))
            message = "Could not reach GitHub or sync branches."
            if fetch_result.timed_out:
                message = "GitHub branch sync timed out."
            return {
                "ok": False,
                "synced": False,
                "updated": False,
                "available": True,
                "state": "fetch_failed",
                "can_update": False,
                "update_needed": False,
                "remote": remote,
                "message": message,
                "error": error_text or message,
                "http_status": 503,
            }

        branch_synced = False
        backup_branch = ""
        selected_branch = _clean_branch_name(target_branch)
        branch_options = _remote_branches(repo_root, remote, runner)
        if selected_branch and selected_branch in branch_options:
            target_upstream = f"{remote}/{selected_branch}"
            selected_is_current = selected_branch == branch
            selected_exists = selected_is_current or _local_branch_exists(repo_root, selected_branch, runner)
            if selected_exists:
                branch_ahead, branch_behind = _ahead_behind_refs(
                    repo_root,
                    selected_branch,
                    target_upstream,
                    runner,
                )
                if branch_ahead is None or branch_behind is None:
                    return {
                        "ok": False,
                        "synced": False,
                        "updated": False,
                        "available": True,
                        "state": "compare_failed",
                        "can_update": False,
                        "update_needed": False,
                        "remote": remote,
                        "target_branch": selected_branch,
                        "target_upstream": target_upstream,
                        "message": "Fetched branches, but could not compare the selected local branch with GitHub.",
                        "error": "selected branch comparison failed",
                        "http_status": 409,
                    }
                if int(branch_ahead or 0) > 0:
                    backup_branch = _sync_backup_branch_name(repo_root, selected_branch, runner)
                    if not backup_branch:
                        return {
                            "ok": False,
                            "synced": False,
                            "updated": False,
                            "available": True,
                            "state": "backup_failed",
                            "can_update": False,
                            "update_needed": False,
                            "remote": remote,
                            "target_branch": selected_branch,
                            "target_upstream": target_upstream,
                            "message": f"Fetched branches, but could not choose a backup branch name for {selected_branch}.",
                            "error": "backup branch name could not be generated",
                            "http_status": 409,
                        }
                    backup_result = runner(["branch", backup_branch, selected_branch], repo_root, 10.0)
                    if backup_result.returncode != 0:
                        error_text = _short_text(_git_text(backup_result))
                        return {
                            "ok": False,
                            "synced": False,
                            "updated": False,
                            "available": True,
                            "state": "backup_failed",
                            "can_update": False,
                            "update_needed": False,
                            "remote": remote,
                            "target_branch": selected_branch,
                            "target_upstream": target_upstream,
                            "message": f"Fetched branches, but could not back up local branch {selected_branch}.",
                            "error": error_text or "git branch backup failed",
                            "http_status": 409,
                        }
                if int(branch_ahead or 0) > 0 or int(branch_behind or 0) > 0:
                    if selected_is_current and _working_tree_dirty(repo_root, runner):
                        return {
                            "ok": False,
                            "synced": False,
                            "updated": False,
                            "available": True,
                            "state": "dirty",
                            "can_update": False,
                            "update_needed": False,
                            "remote": remote,
                            "target_branch": selected_branch,
                            "target_upstream": target_upstream,
                            "backup_branch": backup_branch,
                            "message": "Fetched branches, but the checked-out branch has uncommitted changes.",
                            "error": "working tree has uncommitted changes",
                            "http_status": 409,
                        }
                    sync_args = (
                        ["reset", "--hard", target_upstream]
                        if selected_is_current
                        else ["branch", "-f", selected_branch, target_upstream]
                    )
                    sync_result = runner(sync_args, repo_root, 10.0)
                    if sync_result.returncode != 0:
                        error_text = _short_text(_git_text(sync_result))
                        return {
                            "ok": False,
                            "synced": False,
                            "updated": False,
                            "available": True,
                            "state": "branch_sync_failed",
                            "can_update": False,
                            "update_needed": False,
                            "remote": remote,
                            "target_branch": selected_branch,
                            "target_upstream": target_upstream,
                            "backup_branch": backup_branch,
                            "message": f"Fetched branches, but could not align {selected_branch} to {target_upstream}.",
                            "error": error_text or ("git reset --hard failed" if selected_is_current else "git branch -f failed"),
                            "http_status": 409,
                        }
                    branch_synced = True

        payload = build_update_status_payload(
            repo_dir=repo_root,
            target_branch=target_branch,
            runner=runner,
        )
        if branch_synced and backup_branch:
            message = f"Branches synced from GitHub. Local {selected_branch} was backed up as {backup_branch} and aligned to {remote}/{selected_branch}."
        elif branch_synced:
            message = f"Branches synced from GitHub. Local {selected_branch} was aligned to {remote}/{selected_branch}."
        else:
            message = "Branches synced from GitHub."
        new_commit = str(payload.get("current_commit") or "")
        checked_out_updated = bool(branch_synced and selected_branch == branch and old_commit and new_commit and old_commit != new_commit)
        changed_files = _changed_files(repo_root, old_commit, new_commit, runner) if checked_out_updated else []
        requirements_changed = any(
            path == "requirements.txt" or path == "requirements-dev.txt"
            for path in changed_files
        )
        if checked_out_updated:
            message = f"{message} Reload the dashboard process to use the synced code."
            if requirements_changed:
                message = (
                    f"{message} Python requirements changed; install requirements "
                    "before reloading."
                )
        payload.update(
            {
                "ok": True,
                "synced": True,
                "branch_synced": branch_synced,
                "backup_branch": backup_branch,
                "updated": checked_out_updated,
                "connection_ok": True,
                "previous_commit": old_commit if checked_out_updated else "",
                "new_commit": new_commit if checked_out_updated else "",
                "changed_files": changed_files,
                "requirements_changed": requirements_changed,
                "restart_required": checked_out_updated,
                "message": message,
                "http_status": 200,
            }
        )
        return payload
    finally:
        _UPDATE_LOCK.release()
