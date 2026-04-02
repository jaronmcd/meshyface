#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Create a curated public release commit from allowlisted paths and push it.

Usage:
  ./scripts/release_public.sh [options]

Options:
  --source-branch <name>   Source branch to export (default: current branch)
  --target-remote <name>   Public remote name (default: $PUBLIC_RELEASE_REMOTE or public)
  --target-branch <name>   Public branch name (default: $PUBLIC_RELEASE_BRANCH or main)
  --allowlist <path>       Allowlist file (default: .public-release-allowlist)
  --message <text>         Commit message for the public release commit
  --dry-run                Build the release commit locally, but do not push
  --allow-dirty            Skip clean working tree check in source repo
  -h, --help               Show this help

Allowlist format:
  - One repo-root-relative path per line.
  - Blank lines and lines starting with # are ignored.
EOF
}

die() {
  echo "error: $*" >&2
  exit 1
}

require_arg() {
  local arg_name="$1"
  local arg_value="${2-}"
  [[ -n "$arg_value" ]] || die "missing value for ${arg_name}"
}

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

source_branch="$(git rev-parse --abbrev-ref HEAD)"
target_remote="${PUBLIC_RELEASE_REMOTE:-public}"
target_branch="${PUBLIC_RELEASE_BRANCH:-main}"
allowlist_file=".public-release-allowlist"
commit_message=""
dry_run=0
allow_dirty=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source-branch)
      require_arg "$1" "${2-}"
      source_branch="$2"
      shift 2
      ;;
    --target-remote)
      require_arg "$1" "${2-}"
      target_remote="$2"
      shift 2
      ;;
    --target-branch)
      require_arg "$1" "${2-}"
      target_branch="$2"
      shift 2
      ;;
    --allowlist)
      require_arg "$1" "${2-}"
      allowlist_file="$2"
      shift 2
      ;;
    --message)
      require_arg "$1" "${2-}"
      commit_message="$2"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    --allow-dirty)
      allow_dirty=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

[[ -f "$allowlist_file" ]] || die "allowlist file not found: $allowlist_file"
git remote get-url "$target_remote" >/dev/null 2>&1 || die "remote '$target_remote' not found"
source_commit="$(git rev-parse --verify "${source_branch}^{commit}")" || die "invalid source branch/commit: $source_branch"

if [[ "$allow_dirty" -eq 0 ]] && [[ -n "$(git status --porcelain)" ]]; then
  die "source repo has uncommitted changes (commit/stash first, or use --allow-dirty)"
fi

allowlist_paths=()
while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
  line="$(trim "$raw_line")"
  [[ -z "$line" ]] && continue
  [[ "${line:0:1}" == "#" ]] && continue
  if [[ "$line" == /* ]]; then
    die "allowlist path must be repo-relative, not absolute: $line"
  fi
  if [[ "$line" == ".." || "$line" == ../* || "$line" == */.. || "$line" == */../* ]]; then
    die "allowlist path cannot escape repository root: $line"
  fi
  allowlist_paths+=("$line")
done < "$allowlist_file"

[[ "${#allowlist_paths[@]}" -gt 0 ]] || die "allowlist is empty: $allowlist_file"

has_target_branch=0
if git ls-remote --exit-code --heads "$target_remote" "$target_branch" >/dev/null 2>&1; then
  has_target_branch=1
  git fetch "$target_remote" "$target_branch"
fi

worktree_dir="$(mktemp -d "${TMPDIR:-/tmp}/public-release.XXXXXX")"
tmp_branch="public-release-$(date +%Y%m%d%H%M%S)-$RANDOM"

cleanup() {
  git worktree remove --force "$worktree_dir" >/dev/null 2>&1 || true
  git branch -D "$tmp_branch" >/dev/null 2>&1 || true
  rm -rf "$worktree_dir"
}
trap cleanup EXIT

if [[ "$has_target_branch" -eq 1 ]]; then
  git worktree add --quiet -b "$tmp_branch" "$worktree_dir" "$target_remote/$target_branch"
else
  # First release branch: start orphaned so private history is never pushed.
  git worktree add --quiet --detach "$worktree_dir" "$source_commit"
  (
    cd "$worktree_dir"
    git switch --orphan "$tmp_branch" >/dev/null
  )
fi

(
  cd "$worktree_dir"

  git rm -r -q --ignore-unmatch .
  git clean -fdx -q

  git checkout "$source_commit" -- "${allowlist_paths[@]}"
  git add -A

  if git diff --cached --quiet; then
    echo "No approved file changes to publish for ${target_remote}/${target_branch}."
    exit 0
  fi

  echo "Files queued for public release:"
  git --no-pager diff --cached --name-status

  source_short="$(git rev-parse --short "$source_commit")"
  if [[ -z "$commit_message" ]]; then
    commit_message="Public release from ${source_branch} (${source_short})"
  fi

  git commit -m "$commit_message" >/dev/null
  echo "Created release commit $(git rev-parse --short HEAD)."

  if [[ "$dry_run" -eq 1 ]]; then
    echo "Dry run enabled: not pushing to ${target_remote}/${target_branch}."
    exit 0
  fi

  git push "$target_remote" "HEAD:${target_branch}"
  echo "Published to ${target_remote}/${target_branch}."
)
