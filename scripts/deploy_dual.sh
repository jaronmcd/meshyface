#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_DEPLOY_SCRIPT="${ROOT_DIR}/scripts/deploy_meshyface.sh"

MAIN_BRANCH="main"
PUBLIC_BRANCH="release/public-v0"
MAIN_TARGET="j@192.168.1.241"
PUBLIC_TARGET="j@192.168.1.29"
MAIN_MESH_HOST="192.168.1.69"
PUBLIC_MESH_HOST="192.168.1.211"
MAIN_UI_PROFILE=""
PUBLIC_UI_PROFILE="core-ui"

DEPLOY_MAIN=1
DEPLOY_PUBLIC=1
CLEAN_APP_DIR=1
BOOTSTRAP_MAIN=0
BOOTSTRAP_PUBLIC=0
DRY_RUN=0

WORKTREE_DIRS=()
LAST_WORKTREE_DIR=""

usage() {
  cat <<'EOF'
Deploy private + public dashboard environments in one command.

Defaults:
  Private deploy:
    branch: main
    target: j@192.168.1.241
    radio : 192.168.1.69
  Public deploy:
    branch: release/public-v0
    target: j@192.168.1.29
    radio : 192.168.1.211
    ui    : core-ui
  Cleanup mode:
    --clean-app-dir is enabled by default for both deploys.

Usage:
  ./scripts/deploy_dual.sh [options]

Options:
  --main-only              Deploy only the private environment.
  --public-only            Deploy only the public environment.
  --main-branch <name>     Override private branch (default: main).
  --public-branch <name>   Override public branch (default: release/public-v0).
  --main-target <user@ip>  Override private deploy target.
  --public-target <user@ip> Override public deploy target.
  --main-mesh-host <ip>    Override private radio host.
  --public-mesh-host <ip>  Override public radio host.
  --main-ui-profile <name> Override private dashboard UI profile.
  --public-ui-profile <name> Override public dashboard UI profile.
  --bootstrap-main         Bootstrap private target before deploy.
  --bootstrap-public       Bootstrap public target before deploy.
  --bootstrap-all          Bootstrap both targets before deploy.
  --no-clean               Disable --clean-app-dir for both deploys.
  --clean                  Force-enable --clean-app-dir for both deploys.
  --dry-run                Print resolved deploy commands only.
  -h, --help               Show this help text.
EOF
}

require_arg() {
  local flag="$1"
  local value="${2:-}"
  if [[ -z "$value" ]]; then
    echo "${flag} requires a value" >&2
    exit 2
  fi
}

cleanup_worktrees() {
  local wt
  for wt in "${WORKTREE_DIRS[@]}"; do
    git -C "${ROOT_DIR}" worktree remove --force "${wt}" >/dev/null 2>&1 || true
    rm -rf "${wt}" >/dev/null 2>&1 || true
  done
}
trap cleanup_worktrees EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --main-only)
      DEPLOY_MAIN=1
      DEPLOY_PUBLIC=0
      shift
      ;;
    --public-only)
      DEPLOY_MAIN=0
      DEPLOY_PUBLIC=1
      shift
      ;;
    --main-branch)
      require_arg "$1" "${2:-}"
      MAIN_BRANCH="$2"
      shift 2
      ;;
    --public-branch)
      require_arg "$1" "${2:-}"
      PUBLIC_BRANCH="$2"
      shift 2
      ;;
    --main-target)
      require_arg "$1" "${2:-}"
      MAIN_TARGET="$2"
      shift 2
      ;;
    --public-target)
      require_arg "$1" "${2:-}"
      PUBLIC_TARGET="$2"
      shift 2
      ;;
    --main-mesh-host)
      require_arg "$1" "${2:-}"
      MAIN_MESH_HOST="$2"
      shift 2
      ;;
    --public-mesh-host)
      require_arg "$1" "${2:-}"
      PUBLIC_MESH_HOST="$2"
      shift 2
      ;;
    --main-ui-profile)
      require_arg "$1" "${2:-}"
      MAIN_UI_PROFILE="$2"
      shift 2
      ;;
    --public-ui-profile)
      require_arg "$1" "${2:-}"
      PUBLIC_UI_PROFILE="$2"
      shift 2
      ;;
    --bootstrap-main)
      BOOTSTRAP_MAIN=1
      shift
      ;;
    --bootstrap-public)
      BOOTSTRAP_PUBLIC=1
      shift
      ;;
    --bootstrap-all)
      BOOTSTRAP_MAIN=1
      BOOTSTRAP_PUBLIC=1
      shift
      ;;
    --no-clean)
      CLEAN_APP_DIR=0
      shift
      ;;
    --clean)
      CLEAN_APP_DIR=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "${DEPLOY_MAIN}" -eq 0 && "${DEPLOY_PUBLIC}" -eq 0 ]]; then
  echo "nothing to deploy (both main/public disabled)" >&2
  exit 2
fi

if [[ ! -x "${BASE_DEPLOY_SCRIPT}" ]]; then
  echo "deploy script not found or not executable: ${BASE_DEPLOY_SCRIPT}" >&2
  exit 1
fi

add_worktree_for_branch() {
  local branch="$1"
  local wt
  wt="$(mktemp -d "${TMPDIR:-/tmp}/mesh-deploy-${branch//\//-}.XXXXXX")"
  WORKTREE_DIRS+=("${wt}")
  git -C "${ROOT_DIR}" rev-parse --verify "${branch}^{commit}" >/dev/null 2>&1 \
    || { echo "branch not found: ${branch}" >&2; exit 1; }
  git -C "${ROOT_DIR}" worktree add --quiet --detach "${wt}" "${branch}"
  LAST_WORKTREE_DIR="${wt}"
}

render_cmd() {
  local -a cmd=("$@")
  local out=""
  local part
  for part in "${cmd[@]}"; do
    printf -v part_q '%q' "${part}"
    if [[ -z "${out}" ]]; then
      out="${part_q}"
    else
      out="${out} ${part_q}"
    fi
  done
  printf '%s\n' "${out}"
}

deploy_one() {
  local label="$1"
  local branch="$2"
  local target="$3"
  local mesh_host="$4"
  local ui_profile="$5"
  local bootstrap="$6"
  local -a cmd

  git -C "${ROOT_DIR}" rev-parse --verify "${branch}^{commit}" >/dev/null 2>&1 \
    || { echo "branch not found: ${branch}" >&2; exit 1; }

  cmd=("./scripts/deploy_meshyface.sh" "--target" "${target}" "--mesh-host" "${mesh_host}")
  if [[ -n "${ui_profile}" ]]; then
    cmd+=("--ui-profile" "${ui_profile}")
  fi
  if [[ "${CLEAN_APP_DIR}" -eq 1 ]]; then
    cmd+=("--clean-app-dir")
  fi
  if [[ "${bootstrap}" -eq 1 ]]; then
    cmd+=("--bootstrap")
  fi

  echo "[dual-deploy] ${label}"
  echo "[dual-deploy] branch=${branch} target=${target} mesh=${mesh_host} ui_profile=${ui_profile:-full} clean=${CLEAN_APP_DIR} bootstrap=${bootstrap}"

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "[dual-deploy] dry-run command: deploy branch '${branch}' then run: $(render_cmd "${cmd[@]}")"
    return 0
  fi

  local wt
  add_worktree_for_branch "${branch}"
  wt="${LAST_WORKTREE_DIR}"
  (
    cd "${wt}"
    "${cmd[@]}"
  )
}

if [[ "${DEPLOY_MAIN}" -eq 1 ]]; then
  deploy_one "private" "${MAIN_BRANCH}" "${MAIN_TARGET}" "${MAIN_MESH_HOST}" "${MAIN_UI_PROFILE}" "${BOOTSTRAP_MAIN}"
fi

if [[ "${DEPLOY_PUBLIC}" -eq 1 ]]; then
  deploy_one "public" "${PUBLIC_BRANCH}" "${PUBLIC_TARGET}" "${PUBLIC_MESH_HOST}" "${PUBLIC_UI_PROFILE}" "${BOOTSTRAP_PUBLIC}"
fi

echo "[dual-deploy] complete"
