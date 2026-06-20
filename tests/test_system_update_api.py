from pathlib import Path

from meshdash.api_system_update import (
    GitCommandResult,
    build_update_status_payload,
    run_update_from_github,
)


class _FakeGitRunner:
    def __init__(
        self,
        *,
        dirty: bool = False,
        ahead: int = 0,
        behind: int = 2,
        fetch_fails: bool = False,
        compare_fails: bool = False,
        current_branch: str = "main",
        remote_branches: list[str] | None = None,
        local_branches: set[str] | None = None,
    ) -> None:
        self.dirty = dirty
        self.ahead = ahead
        self.behind = behind
        self.fetch_fails = fetch_fails
        self.compare_fails = compare_fails
        self.current_branch = current_branch
        self.remote_branches = list(remote_branches or ["main", "beta"])
        self.local_branches = set(local_branches or {current_branch})
        self.commit = "aaaaaaaa11111111222222223333333344444444"
        self.new_commit = "bbbbbbbb11111111222222223333333344444444"
        self.commands: list[tuple[str, ...]] = []

    def __call__(self, args, cwd: Path, timeout: float) -> GitCommandResult:
        command = tuple(str(part) for part in args)
        self.commands.append(command)
        if command == ("rev-parse", "--show-toplevel"):
            return GitCommandResult(0, str(cwd))
        if command == ("branch", "--show-current"):
            return GitCommandResult(0, self.current_branch)
        if command == ("rev-parse", "--verify", "HEAD^{commit}"):
            return GitCommandResult(0, self.commit)
        if command == ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"):
            if self.current_branch == "main":
                return GitCommandResult(0, "origin/main")
            if self.current_branch in self.remote_branches:
                return GitCommandResult(0, f"origin/{self.current_branch}")
            return GitCommandResult(128, "no upstream")
        if command == ("remote",):
            return GitCommandResult(0, "origin")
        if command == ("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin"):
            refs = "\n".join(f"origin/{branch}" for branch in self.remote_branches)
            return GitCommandResult(0, refs)
        if command == ("status", "--porcelain"):
            return GitCommandResult(0, " M meshdash/foo.py" if self.dirty else "")
        if command == ("rev-list", "--left-right", "--count", "HEAD...origin/main"):
            if self.compare_fails:
                return GitCommandResult(128, "unknown revision")
            return GitCommandResult(0, f"{self.ahead}\t{self.behind}")
        if command == ("rev-list", "--left-right", "--count", "HEAD...origin/beta"):
            if self.compare_fails:
                return GitCommandResult(128, "unknown revision")
            return GitCommandResult(0, "1\t4" if self.current_branch != "beta" else "0\t0")
        if command == ("rev-list", "--left-right", "--count", "beta...origin/beta"):
            if self.compare_fails:
                return GitCommandResult(128, "unknown revision")
            return GitCommandResult(0, "0\t4")
        if command == ("remote", "get-url", "origin"):
            return GitCommandResult(0, "https://token@example.com/jaronmcd/meshyface.git")
        if command == ("fetch", "--prune", "origin"):
            if self.fetch_fails:
                return GitCommandResult(128, "Could not resolve host: github.com")
            return GitCommandResult(0, "")
        if command == ("show-ref", "--verify", "--quiet", "refs/heads/beta"):
            return GitCommandResult(0 if "beta" in self.local_branches else 1, "")
        if command == ("switch", "beta"):
            if "beta" not in self.local_branches:
                return GitCommandResult(1, "branch not found")
            self.current_branch = "beta"
            self.commit = self.new_commit
            self.ahead = 0
            self.behind = 0
            return GitCommandResult(0, "Switched to branch 'beta'")
        if command == ("switch", "--track", "-c", "beta", "origin/beta"):
            self.local_branches.add("beta")
            self.current_branch = "beta"
            self.commit = self.new_commit
            self.ahead = 0
            self.behind = 0
            return GitCommandResult(0, "branch 'beta' set up to track 'origin/beta'")
        if command == ("merge", "--ff-only", "origin/main"):
            self.commit = self.new_commit
            self.behind = 0
            return GitCommandResult(0, "Fast-forward")
        if command == ("merge", "--ff-only", "origin/beta"):
            self.commit = self.new_commit
            self.behind = 0
            return GitCommandResult(0, "Fast-forward")
        if command == ("diff", "--name-only", self.commit, self.commit):
            return GitCommandResult(0, "")
        if command[0:2] == ("diff", "--name-only"):
            return GitCommandResult(0, "meshdash/api_system_update.py\nrequirements.txt")
        return GitCommandResult(1, f"unexpected command: {' '.join(command)}")


def test_update_status_reports_git_checkout_state(tmp_path: Path) -> None:
    runner = _FakeGitRunner(behind=2)

    payload = build_update_status_payload(repo_dir=tmp_path, runner=runner)

    assert payload["ok"] is True
    assert payload["available"] is True
    assert payload["state"] == "update_available"
    assert payload["can_update"] is True
    assert payload["update_needed"] is True
    assert payload["remote_url"] == "https://example.com/jaronmcd/meshyface.git"
    assert payload["current_commit_short"] == "aaaaaaaa"
    assert payload["branches"] == ["beta", "main"]
    assert payload["target_branch"] == "main"


def test_run_update_fetches_and_fast_forwards(tmp_path: Path) -> None:
    runner = _FakeGitRunner(behind=2)

    payload = run_update_from_github(repo_dir=tmp_path, runner=runner)

    assert payload["ok"] is True
    assert payload["updated"] is True
    assert payload["restart_required"] is True
    assert payload["requirements_changed"] is True
    assert payload["new_commit"] == runner.new_commit
    assert ("fetch", "--prune", "origin") in runner.commands
    assert ("merge", "--ff-only", "origin/main") in runner.commands


def test_run_update_switches_to_selected_remote_branch(tmp_path: Path) -> None:
    runner = _FakeGitRunner(
        current_branch="settings-github-updater",
        local_branches={"settings-github-updater"},
    )

    payload = run_update_from_github(repo_dir=tmp_path, target_branch="beta", runner=runner)

    assert payload["ok"] is True
    assert payload["updated"] is True
    assert payload["branch"] == "beta"
    assert payload["target_branch"] == "beta"
    assert ("switch", "--track", "-c", "beta", "origin/beta") in runner.commands


def test_run_update_blocks_dirty_checkout(tmp_path: Path) -> None:
    runner = _FakeGitRunner(dirty=True)

    payload = run_update_from_github(repo_dir=tmp_path, runner=runner)

    assert payload["ok"] is False
    assert payload["updated"] is False
    assert payload["state"] == "dirty"
    assert ("fetch", "--prune", "origin") not in runner.commands


def test_run_update_reports_fetch_failures(tmp_path: Path) -> None:
    runner = _FakeGitRunner(fetch_fails=True)

    payload = run_update_from_github(repo_dir=tmp_path, runner=runner)

    assert payload["ok"] is False
    assert payload["updated"] is False
    assert payload["state"] == "fetch_failed"
    assert "github.com" in payload["error"]


def test_run_update_reports_compare_failures_after_fetch(tmp_path: Path) -> None:
    runner = _FakeGitRunner(compare_fails=True)

    payload = run_update_from_github(repo_dir=tmp_path, runner=runner)

    assert payload["ok"] is False
    assert payload["updated"] is False
    assert payload["state"] == "compare_failed"
