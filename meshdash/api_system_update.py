from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
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


def _current_branch(repo_root: Path, runner: GitRunner) -> str:
    result = runner(["branch", "--show-current"], repo_root, 5.0)
    return _git_text(result) if result.returncode == 0 else ""


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
        return (
            "switch_available",
            f"Ready to switch from {branch} to {target_branch}.",
            True,
            True,
        )
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
    branch_options = _remote_branches(repo_root, remote, runner)
    selected_branch, selected_available = _select_target_branch(
        requested_branch=target_branch,
        current_branch=branch,
        upstream_branch=current_remote_branch,
        branch_options=branch_options,
    )
    target_upstream = f"{remote}/{selected_branch}" if remote and selected_branch and selected_available else ""
    dirty = _working_tree_dirty(repo_root, runner)
    ahead, behind = _ahead_behind(repo_root, target_upstream, runner)
    remote_url = _remote_url(repo_root, remote, runner)

    state, message, can_update, update_needed = _status_state(
        available=True,
        branch=branch,
        target_branch=selected_branch,
        target_available=selected_available,
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
        "target_upstream": target_upstream,
        "remote": remote,
        "remote_branch": selected_branch,
        "remote_url": remote_url,
        "branches": branch_options,
        "current_commit": commit,
        "current_commit_short": commit[:8] if commit else "",
        "dirty": dirty,
        "ahead": ahead,
        "behind": behind,
        "can_update": can_update,
        "update_needed": update_needed,
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


def _local_branch_exists(repo_root: Path, branch: str, runner: GitRunner) -> bool:
    clean = _clean_branch_name(branch)
    if not clean:
        return False
    result = runner(["show-ref", "--verify", "--quiet", f"refs/heads/{clean}"], repo_root, 5.0)
    return result.returncode == 0


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
        if not remote or not selected_branch or not target_upstream:
            return _failure_payload(
                status,
                state="select_branch",
                message="Software update needs a selected GitHub branch.",
                http_status=409,
            )

        fetch_result = runner(["fetch", "--prune", remote], repo_root, fetch_timeout)
        if fetch_result.returncode != 0:
            error = _short_text(_git_text(fetch_result))
            message = "Could not reach GitHub or fetch the update."
            if fetch_result.timed_out:
                message = "GitHub update check timed out."
            return _failure_payload(
                status,
                state="fetch_failed",
                message=message,
                http_status=503,
                error=error or message,
            )

        after_fetch = build_update_status_payload(
            repo_dir=repo_root,
            target_branch=selected_branch,
            runner=runner,
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
