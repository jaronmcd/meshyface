from pathlib import Path

from meshdash.api_system_update import (
    GitCommandResult,
    build_update_status_payload,
    refresh_update_status_from_github,
    run_update_from_github,
    sync_update_branches_from_github,
)


class _FakeGitRunner:
    def __init__(
        self,
        *,
        dirty: bool = False,
        ahead: int = 0,
        behind: int = 2,
        fetch_fails: bool = False,
        prune_fails: bool = False,
        fetch_without_prune_fails: bool = False,
        compare_fails: bool = False,
        current_branch: str = "main",
        remote_branches: list[str] | None = None,
        live_remote_branches: list[str] | None = None,
        local_branches: set[str] | None = None,
        previous_branch: str = "",
        branch_ahead: int = 0,
        branch_behind: int = 4,
    ) -> None:
        self.dirty = dirty
        self.ahead = ahead
        self.behind = behind
        self.fetch_fails = fetch_fails
        self.prune_fails = prune_fails
        self.fetch_without_prune_fails = fetch_without_prune_fails
        self.compare_fails = compare_fails
        self.current_branch = current_branch
        self.remote_branches = list(remote_branches or ["main", "beta"])
        self.live_remote_branches = list(live_remote_branches or self.remote_branches)
        self.local_branches = set(local_branches or {current_branch})
        self.previous_branch = previous_branch
        self.branch_ahead = branch_ahead
        self.branch_behind = branch_behind
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
        if command == ("rev-parse", "--short=7", "beta"):
            return GitCommandResult(0, "bbbbbbb")
        if command == ("rev-parse", "--abbrev-ref", "@{-1}"):
            if not self.previous_branch:
                return GitCommandResult(128, "no previous checkout")
            return GitCommandResult(0, self.previous_branch)
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
        if command == ("for-each-ref", "--format=%(refname:short)", "refs/heads"):
            refs = "\n".join(sorted(self.local_branches))
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
        if command == ("rev-list", "--left-right", "--count", "main...origin/main"):
            if self.compare_fails:
                return GitCommandResult(128, "unknown revision")
            return GitCommandResult(0, "0\t0")
        if command == ("rev-list", "--left-right", "--count", "beta...origin/beta"):
            if self.compare_fails:
                return GitCommandResult(128, "unknown revision")
            return GitCommandResult(0, f"{self.branch_ahead}\t{self.branch_behind}")
        if command == ("remote", "get-url", "origin"):
            return GitCommandResult(0, "https://token@github.com/jaronmcd/meshyface.git")
        if command[0:5] == (
            "log",
            "--first-parent",
            "--max-count=25",
            "--date=short",
            "--pretty=format:%H%x1f%h%x1f%ad%x1f%s%x1f%b%x1e",
        ):
            sep = "\x1f"
            end = "\x1e"
            records = [
                sep.join(
                    [
                        "ffffffff11111111222222223333333344444444",
                        "ffffffff",
                        "2026-06-20",
                        "Bump version to v0.1.2 [skip ci]",
                        "",
                    ]
                ),
                sep.join(
                    [
                        "cccccccc11111111222222223333333344444444",
                        "cccccccc",
                        "2026-06-20",
                        "Merge pull request #42 from j/update-tab",
                        "Add Update tab",
                    ]
                ),
                sep.join(
                    [
                        "9999999911111111222222223333333344444444",
                        "99999999",
                        "2026-06-19",
                        "Bump version to v0.1.1 [skip ci]",
                        "",
                    ]
                ),
                sep.join(
                    [
                        "dddddddd11111111222222223333333344444444",
                        "dddddddd",
                        "2026-06-19",
                        "Hold local coverage threshold (#43)",
                        "Detailed coverage notes\n\nReviewed-by: local",
                    ]
                ),
                sep.join(
                    [
                        "eeeeeeee11111111222222223333333344444444",
                        "eeeeeeee",
                        "2026-06-18",
                        "Internal maintenance commit",
                        "",
                    ]
                ),
            ]
            return GitCommandResult(0, end.join(records) + end)
        if command == ("fetch", "--prune", "origin"):
            if self.prune_fails:
                return GitCommandResult(
                    128,
                    "error: could not delete references: cannot lock ref "
                    "'refs/remotes/origin/pr/dashboard-perf': Permission denied",
                )
            if self.fetch_fails:
                return GitCommandResult(128, "Could not resolve host: github.com")
            return GitCommandResult(0, "")
        if command == ("fetch", "origin"):
            if self.fetch_fails or self.fetch_without_prune_fails:
                return GitCommandResult(128, "Could not resolve host: github.com")
            return GitCommandResult(0, "")
        if command[0:2] == ("fetch", "origin") and len(command) == 3:
            refspec = command[2]
            prefix = "+refs/heads/"
            middle = ":refs/remotes/origin/"
            if not refspec.startswith(prefix) or middle not in refspec:
                return GitCommandResult(1, f"unexpected command: {' '.join(command)}")
            branch = refspec[len(prefix) : refspec.index(middle)]
            if branch not in self.live_remote_branches:
                return GitCommandResult(128, f"fatal: couldn't find remote ref {branch}")
            if branch not in self.remote_branches:
                self.remote_branches.append(branch)
            return GitCommandResult(0, "")
        if command == ("ls-remote", "--heads", "origin"):
            if self.fetch_fails:
                return GitCommandResult(128, "Could not resolve host: github.com")
            refs = "\n".join(
                f"bbbbbbbb11111111222222223333333344444444\trefs/heads/{branch}"
                for branch in self.live_remote_branches
            )
            return GitCommandResult(0, refs)
        if command[0:3] == ("show-ref", "--verify", "--quiet") and len(command) == 4:
            branch_ref = command[3]
            branch_name = branch_ref.removeprefix("refs/heads/")
            return GitCommandResult(0 if branch_name in self.local_branches else 1, "")
        if command[0:1] == ("branch",) and len(command) == 3 and command[1] != "-f":
            backup_branch = command[1]
            source_branch = command[2]
            if source_branch not in self.local_branches or backup_branch in self.local_branches:
                return GitCommandResult(1, "branch backup failed")
            self.local_branches.add(backup_branch)
            return GitCommandResult(0, f"branch '{backup_branch}' created")
        if command == ("branch", "-f", "beta", "origin/beta"):
            self.local_branches.add("beta")
            self.branch_ahead = 0
            self.branch_behind = 0
            return GitCommandResult(0, "branch 'beta' reset")
        if command == ("reset", "--hard", "origin/beta"):
            self.commit = self.new_commit
            self.ahead = 0
            self.behind = 0
            self.branch_ahead = 0
            self.branch_behind = 0
            return GitCommandResult(0, "HEAD is now at bbbbbbb")
        if command[0:1] == ("switch",) and len(command) == 2:
            branch = command[1]
            if branch not in self.local_branches:
                return GitCommandResult(1, "branch not found")
            self.previous_branch = self.current_branch
            self.current_branch = branch
            self.commit = self.new_commit
            self.ahead = 0
            self.behind = 0
            return GitCommandResult(0, f"Switched to branch '{branch}'")
        if command == ("switch", "--track", "-c", "beta", "origin/beta"):
            self.local_branches.add("beta")
            self.previous_branch = self.current_branch
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
    assert payload["remote_url"] == "https://github.com/jaronmcd/meshyface.git"
    assert payload["current_commit_short"] == "aaaaaaaa"
    assert payload["branches"] == ["beta", "main"]
    assert payload["target_branch"] == "main"
    expected_history = [
        {
            "number": "42",
            "title": "Add Update tab",
            "subject": "Merge pull request #42 from j/update-tab",
            "body": "Add Update tab",
            "message": "Merge pull request #42 from j/update-tab\n\nAdd Update tab",
            "date": "2026-06-20",
            "commit": "cccccccc11111111222222223333333344444444",
            "commit_short": "cccccccc",
            "url": "https://github.com/jaronmcd/meshyface/pull/42",
            "version": "0.1.2",
            "version_label": "v0.1.2",
            "version_commit": "ffffffff11111111222222223333333344444444",
            "version_commit_short": "ffffffff",
        },
        {
            "number": "43",
            "title": "Hold local coverage threshold",
            "subject": "Hold local coverage threshold (#43)",
            "body": "Detailed coverage notes\n\nReviewed-by: local",
            "message": "Hold local coverage threshold (#43)\n\nDetailed coverage notes\n\nReviewed-by: local",
            "date": "2026-06-19",
            "commit": "dddddddd11111111222222223333333344444444",
            "commit_short": "dddddddd",
            "url": "https://github.com/jaronmcd/meshyface/pull/43",
            "version": "0.1.1",
            "version_label": "v0.1.1",
            "version_commit": "9999999911111111222222223333333344444444",
            "version_commit_short": "99999999",
        },
        {
            "number": "",
            "title": "Internal maintenance commit",
            "subject": "Internal maintenance commit",
            "body": "",
            "message": "Internal maintenance commit",
            "date": "2026-06-18",
            "commit": "eeeeeeee11111111222222223333333344444444",
            "commit_short": "eeeeeeee",
            "url": "https://github.com/jaronmcd/meshyface/commit/eeeeeeee11111111222222223333333344444444",
        },
    ]
    assert payload["commit_history"] == expected_history
    assert payload["pull_request_history"] == expected_history
    log_commands = [
        command
        for command in runner.commands
        if command[0:5]
        == (
            "log",
            "--first-parent",
            "--max-count=25",
            "--date=short",
            "--pretty=format:%H%x1f%h%x1f%ad%x1f%s%x1f%b%x1e",
        )
    ]
    assert log_commands[-1][-1] == "HEAD"


def test_update_status_uses_local_selected_branch_history_when_available(tmp_path: Path) -> None:
    runner = _FakeGitRunner(local_branches={"main", "beta"})

    payload = build_update_status_payload(repo_dir=tmp_path, target_branch="beta", runner=runner)

    assert payload["target_branch"] == "beta"
    assert ("show-ref", "--verify", "--quiet", "refs/heads/beta") in runner.commands
    log_commands = [
        command
        for command in runner.commands
        if command[0:5]
        == (
            "log",
            "--first-parent",
            "--max-count=25",
            "--date=short",
            "--pretty=format:%H%x1f%h%x1f%ad%x1f%s%x1f%b%x1e",
        )
    ]
    assert log_commands[-1][-1] == "beta"


def test_refresh_update_status_fetches_without_merging(tmp_path: Path) -> None:
    runner = _FakeGitRunner(behind=2)

    payload = refresh_update_status_from_github(repo_dir=tmp_path, runner=runner)

    assert payload["ok"] is True
    assert payload["refreshed"] is True
    assert payload["connection_ok"] is True
    assert payload["state"] == "update_available"
    assert ("fetch", "--prune", "origin") in runner.commands
    assert ("merge", "--ff-only", "origin/main") not in runner.commands
    assert runner.commit == "aaaaaaaa11111111222222223333333344444444"


def test_refresh_update_status_recovers_deleted_selected_branch_after_prune_failure(tmp_path: Path) -> None:
    runner = _FakeGitRunner(
        current_branch="pr/dashboard-perf",
        remote_branches=["main", "pr/dashboard-perf"],
        live_remote_branches=["dev", "main"],
        local_branches={"pr/dashboard-perf"},
        prune_fails=True,
    )

    payload = refresh_update_status_from_github(
        repo_dir=tmp_path,
        target_branch="pr/dashboard-perf",
        runner=runner,
    )

    assert payload["ok"] is True
    assert payload["connection_ok"] is True
    assert payload["refreshed"] is True
    assert payload["prune_failed"] is True
    assert payload["state"] == "local_branch"
    assert payload["target_branch"] == "pr/dashboard-perf"
    assert payload["branches"] == ["dev", "main", "pr/dashboard-perf"]
    assert payload["can_update"] is False
    assert "Select a live branch" in payload["message"]
    assert "Permission denied" in payload["prune_error"]
    assert ("fetch", "--prune", "origin") in runner.commands
    assert ("fetch", "origin") in runner.commands
    assert ("ls-remote", "--heads", "origin") in runner.commands


def test_update_status_allows_local_only_branch_as_rollback_target(tmp_path: Path) -> None:
    runner = _FakeGitRunner(
        current_branch="main",
        remote_branches=["dev", "main"],
        local_branches={"main", "old-stale", "pr/dashboard-perf"},
        previous_branch="pr/dashboard-perf",
    )

    payload = build_update_status_payload(
        repo_dir=tmp_path,
        target_branch="pr/dashboard-perf",
        runner=runner,
    )

    assert payload["state"] == "local_switch_available"
    assert payload["target_branch"] == "pr/dashboard-perf"
    assert payload["target_source"] == "local"
    assert payload["target_remote_available"] is False
    assert payload["target_local_available"] is True
    assert payload["branches"] == ["dev", "main", "pr/dashboard-perf"]
    assert payload["local_branches"] == ["pr/dashboard-perf"]
    assert payload["previous_branch"] == "pr/dashboard-perf"
    assert payload["can_update"] is True


def test_update_status_hides_unrelated_stale_local_branches(tmp_path: Path) -> None:
    runner = _FakeGitRunner(
        current_branch="main",
        remote_branches=["dev", "main"],
        local_branches={"main", "old-stale", "pr/dashboard-perf"},
        previous_branch="pr/dashboard-perf",
    )

    payload = build_update_status_payload(
        repo_dir=tmp_path,
        target_branch="old-stale",
        runner=runner,
    )

    assert payload["state"] == "invalid_branch"
    assert payload["target_branch"] == "old-stale"
    assert payload["branches"] == ["dev", "main", "pr/dashboard-perf"]
    assert payload["local_branches"] == ["pr/dashboard-perf"]
    assert payload["target_local_available"] is False
    assert payload["can_update"] is False


def test_run_update_switches_to_local_only_rollback_branch_without_fetch(tmp_path: Path) -> None:
    runner = _FakeGitRunner(
        current_branch="main",
        remote_branches=["dev", "main"],
        local_branches={"main", "pr/dashboard-perf"},
        previous_branch="pr/dashboard-perf",
    )

    payload = run_update_from_github(
        repo_dir=tmp_path,
        target_branch="pr/dashboard-perf",
        runner=runner,
    )

    assert payload["ok"] is True
    assert payload["updated"] is True
    assert payload["branch"] == "pr/dashboard-perf"
    assert payload["target_source"] == "local"
    assert runner.current_branch == "pr/dashboard-perf"
    assert ("fetch", "--prune", "origin") not in runner.commands
    assert ("switch", "pr/dashboard-perf") in runner.commands
    assert "Switched to local branch pr/dashboard-perf" in payload["message"]


def test_run_update_can_switch_to_live_branch_after_stale_ref_prune_failure(tmp_path: Path) -> None:
    runner = _FakeGitRunner(
        current_branch="pr/dashboard-perf",
        remote_branches=["main", "pr/dashboard-perf"],
        live_remote_branches=["dev", "main"],
        local_branches={"pr/dashboard-perf", "main"},
        prune_fails=True,
    )

    payload = run_update_from_github(repo_dir=tmp_path, target_branch="main", runner=runner)

    assert payload["ok"] is True
    assert payload["updated"] is True
    assert payload["branch"] == "main"
    assert runner.current_branch == "main"
    assert ("fetch", "--prune", "origin") in runner.commands
    assert (
        "fetch",
        "origin",
        "+refs/heads/main:refs/remotes/origin/main",
    ) in runner.commands
    assert ("switch", "main") in runner.commands
    assert ("merge", "--ff-only", "origin/main") in runner.commands


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


def test_sync_update_branches_fetches_without_merging(tmp_path: Path) -> None:
    runner = _FakeGitRunner(behind=2)

    payload = sync_update_branches_from_github(repo_dir=tmp_path, runner=runner)

    assert payload["ok"] is True
    assert payload["synced"] is True
    assert payload["updated"] is False
    assert payload["connection_ok"] is True
    assert payload["state"] == "update_available"
    assert ("fetch", "--prune", "origin") in runner.commands
    assert ("merge", "--ff-only", "origin/main") not in runner.commands
    assert runner.commit == "aaaaaaaa11111111222222223333333344444444"


def test_sync_update_branches_backs_up_and_aligns_stale_selected_branch(tmp_path: Path) -> None:
    runner = _FakeGitRunner(
        current_branch="main",
        local_branches={"main", "beta"},
        branch_ahead=3,
        branch_behind=4,
    )

    payload = sync_update_branches_from_github(repo_dir=tmp_path, target_branch="beta", runner=runner)

    assert payload["ok"] is True
    assert payload["synced"] is True
    assert payload["branch_synced"] is True
    assert payload["updated"] is False
    assert payload["backup_branch"] == "beta-before-sync-bbbbbbb"
    assert "beta-before-sync-bbbbbbb" in runner.local_branches
    assert ("branch", "beta-before-sync-bbbbbbb", "beta") in runner.commands
    assert ("branch", "-f", "beta", "origin/beta") in runner.commands
    assert runner.current_branch == "main"
    assert runner.branch_ahead == 0
    assert runner.branch_behind == 0
    assert "backed up as beta-before-sync-bbbbbbb" in payload["message"]


def test_sync_update_branches_can_align_clean_checked_out_branch(tmp_path: Path) -> None:
    runner = _FakeGitRunner(
        current_branch="beta",
        local_branches={"beta"},
        branch_ahead=3,
        branch_behind=4,
    )

    payload = sync_update_branches_from_github(repo_dir=tmp_path, target_branch="beta", runner=runner)

    assert payload["ok"] is True
    assert payload["synced"] is True
    assert payload["branch_synced"] is True
    assert payload["updated"] is True
    assert payload["restart_required"] is True
    assert payload["backup_branch"] == "beta-before-sync-bbbbbbb"
    assert ("branch", "beta-before-sync-bbbbbbb", "beta") in runner.commands
    assert ("reset", "--hard", "origin/beta") in runner.commands
    assert runner.current_branch == "beta"
    assert runner.branch_ahead == 0
    assert runner.branch_behind == 0


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
