#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/deploy_meshyface.sh [target] [options]

Examples:
  # Fast update to an already configured host
  ./scripts/deploy_meshyface.sh pi@meshyface.local

  # Git-compatible update of an existing checkout used by the systemd service
  ./scripts/deploy_meshyface.sh \
    --target pi@meshyface.local \
    --git-safe-export

  # Full reset + redeploy
  ./scripts/deploy_meshyface.sh \
    --target pi@meshyface.local \
    --wipe-remote-root \
    --serial-path /dev/serial/by-id/usb-...

  # Full uninstall + hard reboot
  ./scripts/deploy_meshyface.sh \
    --target pi@meshyface.local \
    --uninstall \
    --hard-reboot

  # First-time bootstrap + deploy
  ./scripts/deploy_meshyface.sh \
    --target pi@meshyface.local \
    --bootstrap \
    --mesh-host meshtastic-radio.local

Options:
  --target <user@host>     SSH deploy target.
  --bootstrap              Prepare a fresh host (venv, deps, service, env file).
  --git-safe-export        Update the active remote git checkout to this clean, pushed local HEAD.
                           Preserves the remote branch and refuses branch mismatches.
  --git-safe-allow-dirty   Escape hatch: allow tar overlay export when git-compatible deploy is not possible.
  --clean-app-dir          Remove stale managed app code in APP_DIR before copy.
  --wipe-remote-root       Remove Meshyface service + REMOTE_ROOT, then bootstrap fresh.
  --uninstall              Remove Meshyface service + managed files from the target and exit.
  --hard-reboot            Force reboot the target after uninstall or deploy.
  --remote-root <path>     Managed root on target host.
  --mesh-host <ip_or_dns>  Radio host for dashboard.env MESH_HOST.
  --mesh-port <port>       Radio TCP port (default: 4403).
  --serial-path <path>     Radio serial device path for dashboard.env MESH_SERIAL_PATH.
  --dash-host <ip_or_dns>  Dashboard bind host (default: 0.0.0.0).
  --dash-port <port>       Dashboard bind port (default: 8877).
  --refresh-ms <ms>        Poll interval in ms (default: 3000).
  --history-db <path>      History DB path on target host.
  --bbs-enable             Enable BBS/profile workspace in dashboard.env (requires disclaimer).
  --no-bbs-enable          Disable BBS/profile workspace in dashboard.env.
  --games-enable           Enable playable game bots and console support in dashboard.env.
  --no-games-enable        Disable playable game bots and console support in dashboard.env.
  --file-transfer-enable   Enable file transfer in dashboard.env (requires disclaimer).
  --no-file-transfer-enable Disable file transfer in dashboard.env.
  --file-transfer-auto-accept
                           Enable backend auto accept and default browser preference.
  --no-file-transfer-auto-accept
                           Disable backend auto accept; default browsers to manual accept.
  --file-transfer-max-bytes <bytes>
                           Max file transfer size written to dashboard.env.
  --accept-file-transfer-traffic-disclaimer
                           Acknowledge mesh airtime/congestion risk when enabling BBS/files.
  --no-accept-file-transfer-traffic-disclaimer
                           Clear disclaimer acceptance in dashboard.env.
  --service <name>         Systemd service name (default: meshtastic-dashboard).
  --service-user <name>    Systemd service user on target (default: remote SSH user).
  --service-group <name>   Systemd service group on target (default: dialout).
  --app-dir <path>         App directory on target host.
  --config-dir <path>      Config directory on target host.
  --logs-dir <path>        Logs directory on target host.
  --remote-venv <path>     Venv root on target host.
  --remote-python <path>   Python executable on target host.
  -h, --help               Show this help text.

Env overrides:
  MESH_DASH_DEPLOY_TARGET
  MESH_DASH_DEPLOY_ROOT
  MESH_DASH_DEPLOY_APP_DIR
  MESH_DASH_DEPLOY_CONFIG_DIR
  MESH_DASH_DEPLOY_LOG_DIR
  MESH_DASH_DEPLOY_REMOTE_VENV
  MESH_DASH_DEPLOY_REMOTE_PYTHON
  MESH_DASH_DEPLOY_SERVICE
  MESH_DASH_DEPLOY_SERVICE_USER
  MESH_DASH_DEPLOY_SERVICE_GROUP
  MESH_DASH_DEPLOY_GIT_SAFE_EXPORT
  MESH_DASH_DEPLOY_GIT_SAFE_ALLOW_DIRTY
  MESH_DASH_DEPLOY_CLEAN_APP_DIR
  MESH_DASH_DEPLOY_WIPE_REMOTE_ROOT
  MESH_DASH_DEPLOY_UNINSTALL
  MESH_DASH_DEPLOY_HARD_REBOOT
  MESH_DASH_DEPLOY_MESH_HOST
  MESH_DASH_DEPLOY_MESH_PORT
  MESH_DASH_DEPLOY_SERIAL_PATH
  MESH_DASH_DEPLOY_DASH_HOST
  MESH_DASH_DEPLOY_DASH_PORT
  MESH_DASH_DEPLOY_REFRESH_MS
  MESH_DASH_DEPLOY_HISTORY_DB
  MESH_DASH_DEPLOY_PYTHON_UNBUFFERED
  MESH_DASH_DEPLOY_BBS_ENABLE
  MESH_DASH_DEPLOY_GAMES_ENABLE
  MESH_DASH_DEPLOY_FILE_TRANSFER_ENABLE
  MESH_DASH_DEPLOY_FILE_TRANSFER_AUTO_ACCEPT
  MESH_DASH_DEPLOY_FILE_TRANSFER_MAX_BYTES
  MESH_DASH_DEPLOY_ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER
EOF
}

require_arg() {
  local flag="$1"
  local value="${2:-}"
  if [[ -z "${value}" ]]; then
    echo "${flag} requires a value" >&2
    exit 2
  fi
}

is_truthy() {
  local value
  value="$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')"
  [[ "${value}" == "1" || "${value}" == "true" || "${value}" == "yes" || "${value}" == "on" ]]
}

TARGET="${MESH_DASH_DEPLOY_TARGET:-}"
REMOTE_ROOT="${MESH_DASH_DEPLOY_ROOT:-}"
APP_DIR="${MESH_DASH_DEPLOY_APP_DIR:-}"
CONFIG_DIR="${MESH_DASH_DEPLOY_CONFIG_DIR:-}"
LOG_DIR="${MESH_DASH_DEPLOY_LOG_DIR:-}"
REMOTE_VENV="${MESH_DASH_DEPLOY_REMOTE_VENV:-}"
REMOTE_PYTHON="${MESH_DASH_DEPLOY_REMOTE_PYTHON:-}"
SERVICE_NAME="${MESH_DASH_DEPLOY_SERVICE:-meshtastic-dashboard}"
SERVICE_USER="${MESH_DASH_DEPLOY_SERVICE_USER:-}"
SERVICE_GROUP="${MESH_DASH_DEPLOY_SERVICE_GROUP:-dialout}"
SERVICE_USER_SET=0
SERVICE_GROUP_SET=0
if [[ -n "${MESH_DASH_DEPLOY_SERVICE_USER+x}" ]]; then
  SERVICE_USER_SET=1
fi
if [[ -n "${MESH_DASH_DEPLOY_SERVICE_GROUP+x}" ]]; then
  SERVICE_GROUP_SET=1
fi
APP_DIR_EXPLICIT=0
REMOTE_VENV_EXPLICIT=0
REMOTE_PYTHON_EXPLICIT=0
if [[ -n "${APP_DIR}" ]]; then
  APP_DIR_EXPLICIT=1
fi
if [[ -n "${REMOTE_VENV}" ]]; then
  REMOTE_VENV_EXPLICIT=1
fi
if [[ -n "${REMOTE_PYTHON}" ]]; then
  REMOTE_PYTHON_EXPLICIT=1
fi

BOOTSTRAP=0
GIT_SAFE_EXPORT="${MESH_DASH_DEPLOY_GIT_SAFE_EXPORT:-0}"
GIT_SAFE_ALLOW_DIRTY="${MESH_DASH_DEPLOY_GIT_SAFE_ALLOW_DIRTY:-0}"
CLEAN_APP_DIR="${MESH_DASH_DEPLOY_CLEAN_APP_DIR:-0}"
WIPE_REMOTE_ROOT="${MESH_DASH_DEPLOY_WIPE_REMOTE_ROOT:-0}"
UNINSTALL="${MESH_DASH_DEPLOY_UNINSTALL:-0}"
HARD_REBOOT="${MESH_DASH_DEPLOY_HARD_REBOOT:-0}"
MESH_HOST="${MESH_DASH_DEPLOY_MESH_HOST:-}"
MESH_PORT="${MESH_DASH_DEPLOY_MESH_PORT:-4403}"
SERIAL_PATH="${MESH_DASH_DEPLOY_SERIAL_PATH:-}"
DASH_HOST="${MESH_DASH_DEPLOY_DASH_HOST:-0.0.0.0}"
DASH_PORT="${MESH_DASH_DEPLOY_DASH_PORT:-8877}"
REFRESH_MS="${MESH_DASH_DEPLOY_REFRESH_MS:-3000}"
HISTORY_DB="${MESH_DASH_DEPLOY_HISTORY_DB:-}"
PYTHON_UNBUFFERED="${MESH_DASH_DEPLOY_PYTHON_UNBUFFERED:-1}"
BBS_ENABLE="${MESH_DASH_DEPLOY_BBS_ENABLE:-0}"
GAMES_ENABLE="${MESH_DASH_DEPLOY_GAMES_ENABLE:-0}"
FILE_TRANSFER_ENABLE="${MESH_DASH_DEPLOY_FILE_TRANSFER_ENABLE:-0}"
FILE_TRANSFER_AUTO_ACCEPT="${MESH_DASH_DEPLOY_FILE_TRANSFER_AUTO_ACCEPT:-0}"
FILE_TRANSFER_MAX_BYTES="${MESH_DASH_DEPLOY_FILE_TRANSFER_MAX_BYTES:-65536}"
ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER="${MESH_DASH_DEPLOY_ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER:-0}"
BBS_ENABLE_SET=0
GAMES_ENABLE_SET=0
FILE_TRANSFER_ENABLE_SET=0
FILE_TRANSFER_AUTO_ACCEPT_SET=0
FILE_TRANSFER_MAX_BYTES_SET=0
ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER_SET=0
if [[ -n "${MESH_DASH_DEPLOY_BBS_ENABLE+x}" ]]; then
  BBS_ENABLE_SET=1
fi
if [[ -n "${MESH_DASH_DEPLOY_GAMES_ENABLE+x}" ]]; then
  GAMES_ENABLE_SET=1
fi
if [[ -n "${MESH_DASH_DEPLOY_FILE_TRANSFER_ENABLE+x}" ]]; then
  FILE_TRANSFER_ENABLE_SET=1
fi
if [[ -n "${MESH_DASH_DEPLOY_FILE_TRANSFER_AUTO_ACCEPT+x}" ]]; then
  FILE_TRANSFER_AUTO_ACCEPT_SET=1
fi
if [[ -n "${MESH_DASH_DEPLOY_FILE_TRANSFER_MAX_BYTES+x}" ]]; then
  FILE_TRANSFER_MAX_BYTES_SET=1
fi
if [[ -n "${MESH_DASH_DEPLOY_ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER+x}" ]]; then
  ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER_SET=1
fi

SSH_OPTS=(-F /dev/null)
SCP_OPTS=(-F /dev/null)
if [[ -n "${USER:-}" ]]; then
  DEPLOY_MUX_DIR="${TMPDIR:-/tmp}/meshdash-deploy-${USER}"
  mkdir -p "${DEPLOY_MUX_DIR}"
  DEPLOY_MUX_PATH="${DEPLOY_MUX_DIR}/cm-%r@%h:%p"
  SSH_OPTS+=(-o ControlMaster=auto -o ControlPersist=5m -o ControlPath="${DEPLOY_MUX_PATH}")
  SCP_OPTS+=(-o ControlMaster=auto -o ControlPersist=5m -o ControlPath="${DEPLOY_MUX_PATH}")
fi

ssh_cmd() {
  ssh "${SSH_OPTS[@]}" "$@"
}

scp_cmd() {
  scp "${SCP_OPTS[@]}" "$@"
}

verify_remote_runtime_payload_hash() {
  local expected_hash="$1"
  local max_attempts="${2:-25}"
  local sleep_seconds="${3:-1}"
  if [[ -z "${expected_hash}" ]]; then
    echo "runtime verification failed: expected hash is empty" >&2
    return 1
  fi
  echo "[deploy] verifying runtime payload hash via /api/version"
  ssh_cmd "${TARGET}" "\
EXPECTED_HASH='${expected_hash}' \
DASH_PORT='${DASH_PORT}' \
REMOTE_PYTHON='${REMOTE_PYTHON}' \
MAX_ATTEMPTS='${max_attempts}' \
SLEEP_SECONDS='${sleep_seconds}' \
bash -s" <<'REMOTE'
set -euo pipefail
if [[ ! -x "${REMOTE_PYTHON}" ]]; then
  echo "runtime verification failed: remote python missing at ${REMOTE_PYTHON}" >&2
  exit 1
fi
attempt=1
listener_ready=0
while [[ "${attempt}" -le "${MAX_ATTEMPTS}" ]]; do
  listener_state="$("${REMOTE_PYTHON}" - "${DASH_PORT}" <<'PY'
import socket
import sys

port = int(str(sys.argv[1]).strip() or "8877")
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(1.5)
try:
    sock.connect(("127.0.0.1", port))
except OSError as exc:
    print(f"__NOT_LISTENING__:{exc}")
    raise SystemExit(0)
finally:
    try:
        sock.close()
    except Exception:
        pass

print("__LISTENING__")
PY
)"
  if [[ "${listener_state}" == "__LISTENING__" ]]; then
    listener_ready=1
    break
  fi
  echo "[deploy] waiting for dashboard listener (${attempt}/${MAX_ATTEMPTS})" >&2
  attempt=$((attempt + 1))
  sleep "${SLEEP_SECONDS}"
done
if [[ "${listener_ready}" -ne 1 ]]; then
  echo "runtime verification failed: dashboard listener did not open on 127.0.0.1:${DASH_PORT}" >&2
  exit 1
fi

attempt=1
while [[ "${attempt}" -le "${MAX_ATTEMPTS}" ]]; do
  observed_hash="$("${REMOTE_PYTHON}" - "${DASH_PORT}" <<'PY'
import json
import sys
import time
import urllib.error
import urllib.request

port = str(sys.argv[1]).strip() or "8877"
url = f"http://127.0.0.1:{port}/api/version?cb={int(time.time() * 1000)}"
try:
    with urllib.request.urlopen(url, timeout=4) as response:
        payload = json.loads(response.read().decode("utf-8", "replace"))
except urllib.error.URLError as exc:
    reason = getattr(exc, "reason", None)
    if isinstance(reason, ConnectionRefusedError):
        print("__NOT_READY__:connection refused")
    elif isinstance(reason, TimeoutError):
        print("__NOT_READY__:timeout")
    else:
        print(f"__ERROR__:{exc}")
    raise SystemExit(0)
except Exception as exc:
    print(f"__ERROR__:{exc}")
    raise SystemExit(0)

value = str(payload.get("deploy_payload_hash") or "").strip()
print(value)
PY
)"
  if [[ "${observed_hash}" == "${EXPECTED_HASH}" ]]; then
    echo "[deploy] runtime hash verified: ${observed_hash}"
    exit 0
  fi
  if [[ "${observed_hash}" == __NOT_READY__:* ]]; then
    echo "[deploy] waiting for /api/version (${attempt}/${MAX_ATTEMPTS}): warming up (${observed_hash#__NOT_READY__:})" >&2
  elif [[ "${observed_hash}" == __ERROR__:* ]]; then
    echo "[deploy] waiting for /api/version (${attempt}/${MAX_ATTEMPTS}): ${observed_hash#__ERROR__:}" >&2
  else
    observed_display="${observed_hash:-<empty>}"
    echo "[deploy] waiting for runtime hash (${attempt}/${MAX_ATTEMPTS}): observed=${observed_display} expected=${EXPECTED_HASH}" >&2
  fi
  attempt=$((attempt + 1))
  sleep "${SLEEP_SECONDS}"
done
echo "runtime verification failed: /api/version did not report expected deploy_payload_hash=${EXPECTED_HASH}" >&2
exit 1
REMOTE
}

compute_local_deploy_payload_hash() {
  (
    cd "${ROOT_DIR}" || exit 1
    {
      LC_ALL=C sha256sum "mesh_dashboard.py" "mesh_connection.py" "requirements.txt"
      if [[ -f "scripts/benchmark_gui_responsiveness.py" ]]; then
        LC_ALL=C sha256sum "scripts/benchmark_gui_responsiveness.py"
      fi
      LC_ALL=C find "meshdash" -type f \
        ! -path 'meshdash/__pycache__/*' \
        ! -name '*.pyc' \
        -print0 \
      | LC_ALL=C sort -z \
      | LC_ALL=C xargs -0 sha256sum
    } | LC_ALL=C sha256sum | awk '{print $1}'
  )
}

compute_remote_deploy_payload_hash() {
  ssh_cmd "${TARGET}" "\
set -euo pipefail && \
cd '${APP_DIR}' && \
{ \
  LC_ALL=C sha256sum 'mesh_dashboard.py' 'mesh_connection.py' 'requirements.txt' && \
  if [[ -f 'scripts/benchmark_gui_responsiveness.py' ]]; then \
    LC_ALL=C sha256sum 'scripts/benchmark_gui_responsiveness.py'; \
  fi && \
  LC_ALL=C find 'meshdash' -type f \
    ! -path 'meshdash/__pycache__/*' \
    ! -name '*.pyc' \
    -print0 \
  | LC_ALL=C sort -z \
  | LC_ALL=C xargs -0 sha256sum; \
} | LC_ALL=C sha256sum | awk '{print \$1}'"
}

create_local_git_safe_export_tar() {
  local output_tar="$1"
  (
    cd "${ROOT_DIR}" || exit 1
    git rev-parse --is-inside-work-tree >/dev/null
    git ls-files -z \
    | tar \
      --null \
      --warning=no-timestamp \
      --exclude='*.pyc' \
      --files-from - \
      -cf "${output_tar}"
  )
}

detect_remote_service_app_dir() {
  ssh_cmd "${TARGET}" "SERVICE_NAME='${SERVICE_NAME}' bash -s" <<'REMOTE'
set -euo pipefail
unit_text="$(systemctl cat "${SERVICE_NAME}" --no-pager 2>/dev/null || true)"
if [[ -z "${unit_text}" ]]; then
  exit 0
fi
printf '%s\n' "${unit_text}" | awk -F= '
  $1 == "ExecStart" {
    line = substr($0, index($0, "=") + 1)
    n = split(line, parts, /[[:space:]]+/)
    for (i = 1; i <= n; i++) {
      if (parts[i] ~ /\/mesh_dashboard\.py$/) {
        sub(/\/mesh_dashboard\.py$/, "", parts[i])
        print parts[i]
        exit
      }
    }
  }
'
REMOTE
}

git_safe_export_deploy() {
  local local_tar
  local local_remote_script
  local remote_tar
  local remote_script
  local local_payload_hash
  local local_branch
  local local_commit
  local local_dirty_status
  local local_dirty

  if ! command -v git >/dev/null 2>&1; then
    echo "--git-safe-export requires git locally" >&2
    exit 1
  fi
  if [[ -z "${APP_DIR}" ]]; then
    echo "--git-safe-export could not determine APP_DIR; pass --app-dir" >&2
    exit 2
  fi

  local_branch="$(git -C "${ROOT_DIR}" branch --show-current 2>/dev/null || true)"
  local_commit="$(git -C "${ROOT_DIR}" rev-parse HEAD)"
  local_dirty_status="$(git -C "${ROOT_DIR}" status --short --untracked-files=no)"
  local_dirty=0
  if [[ -n "${local_dirty_status}" ]]; then
    local_dirty=1
  fi

  if [[ "${local_dirty}" -eq 1 && ! ( "${GIT_SAFE_ALLOW_DIRTY}" == "1" || "${GIT_SAFE_ALLOW_DIRTY}" == "true" || "${GIT_SAFE_ALLOW_DIRTY}" == "yes" ) ]]; then
    echo "--git-safe-export refusing dirty local tracked files." >&2
    printf '%s\n' "${local_dirty_status}" >&2
    echo "Commit and push first, or use --git-safe-allow-dirty for an intentional scratch overlay." >&2
    exit 1
  fi

  local_tar="$(mktemp "${TMPDIR:-/tmp}/meshyface-git-safe-export.XXXXXX.tar")"
  local_remote_script="$(mktemp "${TMPDIR:-/tmp}/meshyface-git-safe-export.XXXXXX.sh")"
  remote_tar="/tmp/meshyface-git-safe-export-$(date +%s)-$$.tar"
  remote_script="/tmp/meshyface-git-safe-export-$(date +%s)-$$.sh"
  trap 'rm -f "${local_tar}" "${local_remote_script}"' RETURN
  local_payload_hash="$(compute_local_deploy_payload_hash)"
  cat >"${local_remote_script}" <<'REMOTE'
set -euo pipefail

remote_script_path="${BASH_SOURCE[0]:-$0}"
trap 'rm -f "${REMOTE_TAR:-}" "${remote_script_path}"' EXIT

git_safe() {
  sudo git -c "safe.directory=${APP_DIR}" -C "${APP_DIR}" "$@"
}

allow_dirty_overlay() {
  [[ "${ALLOW_DIRTY}" == "1" || "${ALLOW_DIRTY}" == "true" || "${ALLOW_DIRTY}" == "yes" ]]
}

restart_service() {
  if [[ -x "${REMOTE_PYTHON}" ]]; then
    owner_group="$(sudo stat -c '%U:%G' "${APP_DIR}")"
    owner_user="${owner_group%%:*}"
    sudo -u "${owner_user}" "${REMOTE_PYTHON}" -m compileall -x '(^|/)(\.git|\.venv)(/|$)' -q "${APP_DIR}"
  fi
  sudo systemctl restart "${SERVICE_NAME}"
  systemctl is-active "${SERVICE_NAME}"
}

overlay_export() {
  if [[ -z "${REMOTE_TAR:-}" || ! -f "${REMOTE_TAR}" ]]; then
    echo "--git-safe-export overlay payload missing on remote: ${REMOTE_TAR:-}" >&2
    exit 1
  fi
  dirty_status="$(git_safe status --short --untracked-files=no)"
  if [[ -n "${dirty_status}" && ! allow_dirty_overlay ]]; then
    echo "--git-safe-export refusing dirty remote tracked files in ${APP_DIR}" >&2
    printf '%s\n' "${dirty_status}" >&2
    echo "Re-run with --git-safe-allow-dirty only for an intentional scratch overlay." >&2
    exit 1
  fi

  owner_group="$(sudo stat -c '%U:%G' "${APP_DIR}")"
  sudo bash -c 'cd "$1" && git -c "safe.directory=$1" ls-files -z | xargs -0 -r rm -f --' _ "${APP_DIR}"
  sudo tar -C "${APP_DIR}" -xf "${REMOTE_TAR}"
  sudo find "${APP_DIR}" \
    \( -path "${APP_DIR}/.git" -o -path "${APP_DIR}/.git/*" -o -path "${APP_DIR}/.venv" -o -path "${APP_DIR}/.venv/*" \) -prune \
    -o -type d -exec chown "${owner_group}" {} +
  sudo tar -tf "${REMOTE_TAR}" \
    | sed "s#^#${APP_DIR}/#" \
    | sudo xargs -r -d '\n' chown "${owner_group}"
  restart_service
}

if [[ ! -d "${APP_DIR}" ]]; then
  echo "--git-safe-export remote APP_DIR does not exist: ${APP_DIR}" >&2
  exit 1
fi
if ! git_safe rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "--git-safe-export requires APP_DIR to be a git worktree: ${APP_DIR}" >&2
  exit 1
fi

if [[ "${LOCAL_DIRTY}" == "1" ]]; then
  echo "[deploy] local tracked files are dirty; using explicit scratch overlay."
  overlay_export
  exit 0
fi

remote_branch="$(git_safe branch --show-current)"
if [[ -z "${remote_branch}" ]]; then
  if allow_dirty_overlay; then
    echo "[deploy] remote checkout is detached; using explicit scratch overlay."
    overlay_export
    exit 0
  fi
  echo "--git-safe-export remote checkout is detached; refusing to guess a branch." >&2
  exit 1
fi
if [[ -n "${LOCAL_BRANCH}" && "${remote_branch}" != "${LOCAL_BRANCH}" ]]; then
  if allow_dirty_overlay; then
    echo "[deploy] remote branch ${remote_branch} differs from local ${LOCAL_BRANCH}; using explicit scratch overlay."
    overlay_export
    exit 0
  fi
  echo "--git-safe-export refusing branch mismatch." >&2
  echo "  local branch:  ${LOCAL_BRANCH}" >&2
  echo "  remote branch: ${remote_branch}" >&2
  echo "Switch the remote app branch first, or use --git-safe-allow-dirty for a scratch overlay." >&2
  exit 1
fi

upstream_ref="$(git_safe rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)"
if [[ -z "${upstream_ref}" ]]; then
  upstream_ref="origin/${remote_branch}"
fi
remote_name="${upstream_ref%%/*}"
remote_ref="${upstream_ref#*/}"
if [[ -z "${remote_name}" || "${remote_name}" == "${upstream_ref}" || -z "${remote_ref}" ]]; then
  echo "--git-safe-export could not resolve upstream for ${remote_branch}: ${upstream_ref}" >&2
  exit 1
fi

git_safe fetch "${remote_name}" "${remote_ref}"
if ! git_safe cat-file -e "${LOCAL_COMMIT}^{commit}" >/dev/null 2>&1; then
  if allow_dirty_overlay; then
    echo "[deploy] local commit is not available on remote upstream; using explicit scratch overlay."
    overlay_export
    exit 0
  fi
  echo "--git-safe-export local commit is not available in remote ${remote_name}/${remote_ref}: ${LOCAL_COMMIT}" >&2
  echo "Push the branch first, then rerun deploy." >&2
  exit 1
fi
if ! git_safe merge-base --is-ancestor "${LOCAL_COMMIT}" FETCH_HEAD; then
  if allow_dirty_overlay; then
    echo "[deploy] local commit is not on remote upstream; using explicit scratch overlay."
    overlay_export
    exit 0
  fi
  echo "--git-safe-export local commit is not on remote upstream ${remote_name}/${remote_ref}: ${LOCAL_COMMIT}" >&2
  echo "Push the selected branch or switch the host to the matching branch first." >&2
  exit 1
fi

dirty_status="$(git_safe status --short --untracked-files=no)"
if [[ -n "${dirty_status}" ]]; then
  if git_safe diff --quiet "${LOCAL_COMMIT}" --; then
    echo "[deploy] remote files already match ${LOCAL_COMMIT}; repairing git metadata"
    git_safe reset --mixed "${LOCAL_COMMIT}"
  else
    if allow_dirty_overlay; then
      echo "[deploy] remote tracked files are dirty; using explicit scratch overlay."
      overlay_export
      exit 0
    fi
    echo "--git-safe-export refusing dirty remote tracked files in ${APP_DIR}" >&2
    printf '%s\n' "${dirty_status}" >&2
    echo "Commit/stash remote changes, or use --git-safe-allow-dirty for a scratch overlay." >&2
    exit 1
  fi
else
  git_safe merge --ff-only "${LOCAL_COMMIT}"
fi
restart_service
REMOTE

  echo "[deploy] git_safe_export=1"
  echo "[deploy] local branch: ${local_branch:-detached}"
  echo "[deploy] local commit: ${local_commit}"
  echo "[deploy] local payload hash: ${local_payload_hash}"
  if [[ "${local_dirty}" -eq 1 || "${GIT_SAFE_ALLOW_DIRTY}" == "1" || "${GIT_SAFE_ALLOW_DIRTY}" == "true" || "${GIT_SAFE_ALLOW_DIRTY}" == "yes" ]]; then
    create_local_git_safe_export_tar "${local_tar}"
    scp_cmd "${local_tar}" "${TARGET}:${remote_tar}"
  fi
  scp_cmd "${local_remote_script}" "${TARGET}:${remote_script}"
  ssh_cmd -tt "${TARGET}" "\
APP_DIR='${APP_DIR}' \
REMOTE_TAR='${remote_tar}' \
SERVICE_NAME='${SERVICE_NAME}' \
REMOTE_PYTHON='${REMOTE_PYTHON}' \
ALLOW_DIRTY='${GIT_SAFE_ALLOW_DIRTY}' \
LOCAL_BRANCH='${local_branch}' \
LOCAL_COMMIT='${local_commit}' \
LOCAL_DIRTY='${local_dirty}' \
bash '${remote_script}'"

  echo "[deploy] git-safe deploy complete"
  echo "[deploy] open: http://${TARGET#*@}:${DASH_PORT}"
}

path_is_within_root() {
  local path="${1:-}"
  local root="${2:-}"
  [[ -n "${path}" && -n "${root}" && ( "${path}" == "${root}" || "${path}" == "${root}/"* ) ]]
}

assert_safe_remote_path() {
  local label="$1"
  local path="${2:-}"
  if [[ -z "${path}" ]]; then
    echo "refusing destructive operation on unsafe ${label}='${path}'" >&2
    exit 1
  fi
  case "${path}" in
    /|/home|/root|/usr|/var|/etc|/opt|/tmp)
      echo "refusing destructive operation on unsafe ${label}='${path}'" >&2
      exit 1
      ;;
  esac
  if [[ -n "${REMOTE_HOME_DIR:-}" && "${path}" == "${REMOTE_HOME_DIR}" ]]; then
    echo "refusing destructive operation on unsafe ${label}='${path}'" >&2
    exit 1
  fi
}

build_extra_uninstall_targets() {
  local targets=()
  local candidate
  for candidate in "${APP_DIR}" "${CONFIG_DIR}" "${LOG_DIR}" "${REMOTE_VENV}"; do
    if [[ -n "${candidate}" ]] && ! path_is_within_root "${candidate}" "${REMOTE_ROOT}"; then
      targets+=("${candidate}")
    fi
  done
  if [[ -n "${HISTORY_DB}" ]] && ! path_is_within_root "${HISTORY_DB}" "${REMOTE_ROOT}"; then
    targets+=("${HISTORY_DB}")
  fi
  printf '%s\n' "${targets[@]}"
}

uninstall_remote_meshyface() {
  local extra_targets=()
  local remove_cmd=""
  local target_path

  assert_safe_remote_path "REMOTE_ROOT" "${REMOTE_ROOT}"
  while IFS= read -r target_path; do
    [[ -n "${target_path}" ]] || continue
    assert_safe_remote_path "managed path" "${target_path}"
    extra_targets+=("${target_path}")
  done < <(build_extra_uninstall_targets)

  for target_path in "${extra_targets[@]}"; do
    remove_cmd="${remove_cmd}rm -rf '${target_path}' && "
  done
  remove_cmd="${remove_cmd}rm -rf '${REMOTE_ROOT}'"

  echo "[deploy] uninstalling ${SERVICE_NAME} from ${TARGET}"
  ssh_cmd -tt "${TARGET}" "\
set -euo pipefail && \
if systemctl list-unit-files --type=service --all | grep -q '^${SERVICE_NAME}\.service' || systemctl list-units --type=service --all | grep -q '^${SERVICE_NAME}\.service'; then \
  sudo systemctl disable --now '${SERVICE_NAME}' || true; \
  sudo systemctl stop '${SERVICE_NAME}' || true; \
  sudo systemctl kill --kill-who=all --signal=SIGKILL '${SERVICE_NAME}' || true; \
  active_state=\$(systemctl show '${SERVICE_NAME}' -p ActiveState --value 2>/dev/null || true); \
  sub_state=\$(systemctl show '${SERVICE_NAME}' -p SubState --value 2>/dev/null || true); \
  if [[ \"\${active_state}\" == 'active' || \"\${sub_state}\" == 'running' ]]; then \
    echo 'service process still active after forced stop' >&2; \
    exit 1; \
  fi; \
fi && \
sudo rm -f '/etc/systemd/system/${SERVICE_NAME}.service' && \
sudo systemctl daemon-reload && \
{ sudo systemctl reset-failed || true; } && \
${remove_cmd}"
}

hard_reboot_remote_target() {
  echo "[deploy] forcing reboot of ${TARGET}"
  ssh_cmd -tt "${TARGET}" "sudo systemctl reboot --force --force" || true
}

read_existing_dashboard_env_value() {
  local key="$1"
  ssh_cmd "${TARGET}" "if [[ -f '${CONFIG_DIR}/dashboard.env' ]]; then awk -F= -v key='${key}' 'index(\$0, key \"=\") == 1 { print substr(\$0, length(key) + 2); exit }' '${CONFIG_DIR}/dashboard.env'; fi" 2>/dev/null || true
}

read_remote_identity() {
  local identity
  identity="$(
    ssh_cmd "${TARGET}" "id -un; (getent passwd \"\$(id -un)\" | cut -d: -f6) || printf '%s\n' \"\$HOME\""
  )"
  REMOTE_LOGIN_USER="$(printf '%s\n' "${identity}" | sed -n '1p')"
  REMOTE_HOME_DIR="$(printf '%s\n' "${identity}" | sed -n '2p')"
  if [[ -z "${REMOTE_LOGIN_USER}" || -z "${REMOTE_HOME_DIR}" ]]; then
    echo "failed to determine remote user/home for ${TARGET}" >&2
    exit 1
  fi
}

DETECTED_SERVICE_UNIT=0
DETECTED_SERVICE_USER=""
DETECTED_SERVICE_GROUP=""
DETECTED_SERVICE_WORKING_DIR=""
DETECTED_SERVICE_ENV_FILE=""
DETECTED_SERVICE_CONFIG_DIR=""
DETECTED_SERVICE_EXEC_START=""
DETECTED_SERVICE_APP_DIR=""
DETECTED_SERVICE_REMOTE_PYTHON=""

strip_optional_systemd_path_prefix() {
  local value="$1"
  while [[ "${value}" == -* ]]; do
    value="${value#-}"
  done
  printf '%s\n' "${value}"
}

detect_existing_service_layout() {
  DETECTED_SERVICE_UNIT=0
  DETECTED_SERVICE_USER=""
  DETECTED_SERVICE_GROUP=""
  DETECTED_SERVICE_WORKING_DIR=""
  DETECTED_SERVICE_ENV_FILE=""
  DETECTED_SERVICE_CONFIG_DIR=""
  DETECTED_SERVICE_EXEC_START=""
  DETECTED_SERVICE_APP_DIR=""
  DETECTED_SERVICE_REMOTE_PYTHON=""

  local unit_lines
  unit_lines="$(
    ssh_cmd "${TARGET}" "\
if systemctl cat '${SERVICE_NAME}' >/dev/null 2>&1; then \
  systemctl cat '${SERVICE_NAME}' | awk -F= '/^(User|Group|WorkingDirectory|EnvironmentFile|ExecStart)=/{print}'; \
fi" 2>/dev/null || true
  )"
  if [[ -z "${unit_lines}" ]]; then
    return 0
  fi

  DETECTED_SERVICE_UNIT=1
  local line key value token env_file
  while IFS= read -r line; do
    [[ -n "${line}" ]] || continue
    key="${line%%=*}"
    value="${line#*=}"
    case "${key}" in
      User)
        [[ -n "${value}" ]] && DETECTED_SERVICE_USER="${value}"
        ;;
      Group)
        [[ -n "${value}" ]] && DETECTED_SERVICE_GROUP="${value}"
        ;;
      WorkingDirectory)
        [[ -n "${value}" ]] && DETECTED_SERVICE_WORKING_DIR="${value}"
        ;;
      EnvironmentFile)
        if [[ -n "${value}" ]]; then
          env_file="${value%%[[:space:]]*}"
          DETECTED_SERVICE_ENV_FILE="$(strip_optional_systemd_path_prefix "${env_file}")"
        fi
        ;;
      ExecStart)
        [[ -n "${value}" ]] && DETECTED_SERVICE_EXEC_START="${value}"
        ;;
    esac
  done <<< "${unit_lines}"

  if [[ -n "${DETECTED_SERVICE_ENV_FILE}" ]]; then
    DETECTED_SERVICE_CONFIG_DIR="$(dirname "${DETECTED_SERVICE_ENV_FILE}")"
  fi
  if [[ -n "${DETECTED_SERVICE_EXEC_START}" ]]; then
    DETECTED_SERVICE_REMOTE_PYTHON="${DETECTED_SERVICE_EXEC_START%%[[:space:]]*}"
    for token in ${DETECTED_SERVICE_EXEC_START}; do
      case "${token}" in
        */mesh_dashboard.py)
          DETECTED_SERVICE_APP_DIR="$(dirname "${token}")"
          ;;
      esac
    done
  fi
  if [[ -z "${DETECTED_SERVICE_APP_DIR}" && -n "${DETECTED_SERVICE_WORKING_DIR}" ]]; then
    DETECTED_SERVICE_APP_DIR="${DETECTED_SERVICE_WORKING_DIR}"
  fi
}

guard_existing_service_layout_matches_deploy() {
  if [[ "${DETECTED_SERVICE_UNIT}" -ne 1 ]]; then
    return 0
  fi
  if [[ "${BOOTSTRAP}" -eq 1 || "${WIPE_REMOTE_ROOT}" -eq 1 || "${UNINSTALL}" -eq 1 ]]; then
    return 0
  fi

  local mismatch=0
  local reasons=()
  if [[ -n "${DETECTED_SERVICE_APP_DIR}" && "${DETECTED_SERVICE_APP_DIR}" != "${APP_DIR}" ]]; then
    mismatch=1
    reasons+=("service app_dir=${DETECTED_SERVICE_APP_DIR}, deploy app_dir=${APP_DIR}")
  fi
  if [[ -n "${DETECTED_SERVICE_CONFIG_DIR}" && "${DETECTED_SERVICE_CONFIG_DIR}" != "${CONFIG_DIR}" ]]; then
    mismatch=1
    reasons+=("service config_dir=${DETECTED_SERVICE_CONFIG_DIR}, deploy config_dir=${CONFIG_DIR}")
  fi
  if [[ -n "${DETECTED_SERVICE_REMOTE_PYTHON}" && "${DETECTED_SERVICE_REMOTE_PYTHON}" != "${REMOTE_PYTHON}" ]]; then
    mismatch=1
    reasons+=("service python=${DETECTED_SERVICE_REMOTE_PYTHON}, deploy python=${REMOTE_PYTHON}")
  fi

  if [[ "${mismatch}" -eq 0 ]]; then
    return 0
  fi

  cat >&2 <<EOF
Refusing to deploy because ${SERVICE_NAME}.service is already installed with a different runtime layout.

$(printf '  - %s\n' "${reasons[@]}")

This prevents copying a new payload to one directory while systemd keeps serving another.

To convert the host to the deploy-helper-managed layout, rerun with --bootstrap or --wipe-remote-root.
To keep the existing service layout, pass explicit path overrides that match the service unit:
  --app-dir '${DETECTED_SERVICE_APP_DIR}' \\
  --config-dir '${DETECTED_SERVICE_CONFIG_DIR}' \\
  --remote-python '${DETECTED_SERVICE_REMOTE_PYTHON}'

If the existing service is a git checkout, the in-app Settings GitHub updater is usually the safer update path.
EOF
  exit 1
}

POSITIONAL_TARGET_SET=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      require_arg "$1" "${2:-}"
      TARGET="$2"
      shift 2
      ;;
    --bootstrap)
      BOOTSTRAP=1
      shift
      ;;
    --git-safe-export)
      GIT_SAFE_EXPORT=1
      shift
      ;;
    --git-safe-allow-dirty)
      GIT_SAFE_ALLOW_DIRTY=1
      shift
      ;;
    --clean-app-dir)
      CLEAN_APP_DIR=1
      shift
      ;;
    --wipe-remote-root)
      WIPE_REMOTE_ROOT=1
      shift
      ;;
    --uninstall)
      UNINSTALL=1
      shift
      ;;
    --hard-reboot)
      HARD_REBOOT=1
      shift
      ;;
    --remote-root)
      require_arg "$1" "${2:-}"
      REMOTE_ROOT="$2"
      shift 2
      ;;
    --mesh-host)
      require_arg "$1" "${2:-}"
      MESH_HOST="$2"
      shift 2
      ;;
    --mesh-port)
      require_arg "$1" "${2:-}"
      MESH_PORT="$2"
      shift 2
      ;;
    --serial-path)
      require_arg "$1" "${2:-}"
      SERIAL_PATH="$2"
      shift 2
      ;;
    --dash-host)
      require_arg "$1" "${2:-}"
      DASH_HOST="$2"
      shift 2
      ;;
    --dash-port)
      require_arg "$1" "${2:-}"
      DASH_PORT="$2"
      shift 2
      ;;
    --refresh-ms)
      require_arg "$1" "${2:-}"
      REFRESH_MS="$2"
      shift 2
      ;;
    --history-db)
      require_arg "$1" "${2:-}"
      HISTORY_DB="$2"
      shift 2
      ;;
    --bbs-enable)
      BBS_ENABLE=1
      BBS_ENABLE_SET=1
      shift
      ;;
    --no-bbs-enable)
      BBS_ENABLE=0
      BBS_ENABLE_SET=1
      shift
      ;;
    --games-enable)
      GAMES_ENABLE=1
      GAMES_ENABLE_SET=1
      shift
      ;;
    --no-games-enable)
      GAMES_ENABLE=0
      GAMES_ENABLE_SET=1
      shift
      ;;
    --file-transfer-enable)
      FILE_TRANSFER_ENABLE=1
      FILE_TRANSFER_ENABLE_SET=1
      shift
      ;;
    --no-file-transfer-enable)
      FILE_TRANSFER_ENABLE=0
      FILE_TRANSFER_ENABLE_SET=1
      shift
      ;;
    --file-transfer-auto-accept)
      FILE_TRANSFER_AUTO_ACCEPT=1
      FILE_TRANSFER_AUTO_ACCEPT_SET=1
      shift
      ;;
    --no-file-transfer-auto-accept)
      FILE_TRANSFER_AUTO_ACCEPT=0
      FILE_TRANSFER_AUTO_ACCEPT_SET=1
      shift
      ;;
    --file-transfer-max-bytes)
      require_arg "$1" "${2:-}"
      FILE_TRANSFER_MAX_BYTES="$2"
      FILE_TRANSFER_MAX_BYTES_SET=1
      shift 2
      ;;
    --accept-file-transfer-traffic-disclaimer)
      ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER=1
      ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER_SET=1
      shift
      ;;
    --no-accept-file-transfer-traffic-disclaimer)
      ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER=0
      ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER_SET=1
      shift
      ;;
    --service)
      require_arg "$1" "${2:-}"
      SERVICE_NAME="$2"
      shift 2
      ;;
    --service-user)
      require_arg "$1" "${2:-}"
      SERVICE_USER="$2"
      SERVICE_USER_SET=1
      shift 2
      ;;
    --service-group)
      require_arg "$1" "${2:-}"
      SERVICE_GROUP="$2"
      SERVICE_GROUP_SET=1
      shift 2
      ;;
    --app-dir)
      require_arg "$1" "${2:-}"
      APP_DIR="$2"
      APP_DIR_EXPLICIT=1
      shift 2
      ;;
    --config-dir)
      require_arg "$1" "${2:-}"
      CONFIG_DIR="$2"
      shift 2
      ;;
    --logs-dir)
      require_arg "$1" "${2:-}"
      LOG_DIR="$2"
      shift 2
      ;;
    --remote-venv)
      require_arg "$1" "${2:-}"
      REMOTE_VENV="$2"
      REMOTE_VENV_EXPLICIT=1
      shift 2
      ;;
    --remote-python)
      require_arg "$1" "${2:-}"
      REMOTE_PYTHON="$2"
      REMOTE_PYTHON_EXPLICIT=1
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [[ "${POSITIONAL_TARGET_SET}" -eq 0 ]]; then
        TARGET="$1"
        POSITIONAL_TARGET_SET=1
        shift
      else
        echo "unexpected argument: $1" >&2
        usage >&2
        exit 2
      fi
      ;;
  esac
done

if [[ $# -gt 0 ]]; then
  echo "unexpected trailing arguments: $*" >&2
  usage >&2
  exit 2
fi

if [[ -z "${TARGET}" ]]; then
  cat >&2 <<'EOF'
No deploy target supplied.

Copy/paste one of these, then adjust the target host and radio host:
  ./scripts/deploy_meshyface.sh --target pi@meshyface.local
  ./scripts/deploy_meshyface.sh --target pi@meshyface.local --bootstrap --mesh-host meshtastic-radio.local

You can also set MESH_DASH_DEPLOY_TARGET in your environment.
EOF
  exit 2
fi

for local_required in mesh_dashboard.py mesh_connection.py meshdash; do
  if [[ ! -e "${ROOT_DIR}/${local_required}" ]]; then
    echo "${local_required} not found under ${ROOT_DIR}" >&2
    exit 1
  fi
done

if is_truthy "${GIT_SAFE_EXPORT}" && ! is_truthy "${GIT_SAFE_ALLOW_DIRTY}"; then
  if ! command -v git >/dev/null 2>&1; then
    echo "--git-safe-export requires git locally" >&2
    exit 1
  fi
  preflight_dirty_status="$(git -C "${ROOT_DIR}" status --short --untracked-files=no)"
  if [[ -n "${preflight_dirty_status}" ]]; then
    echo "--git-safe-export refusing dirty local tracked files before connecting to target." >&2
    printf '%s\n' "${preflight_dirty_status}" >&2
    echo "Commit and push first, or use --git-safe-allow-dirty for an intentional scratch overlay." >&2
    exit 1
  fi
fi

read_remote_identity

if [[ -z "${SERVICE_USER}" ]]; then
  SERVICE_USER="${REMOTE_LOGIN_USER}"
fi
if is_truthy "${GIT_SAFE_EXPORT}" && [[ "${APP_DIR_EXPLICIT}" -eq 0 ]]; then
  detected_app_dir="$(detect_remote_service_app_dir || true)"
  if [[ -n "${detected_app_dir}" ]]; then
    APP_DIR="${detected_app_dir}"
  fi
fi
if [[ -z "${REMOTE_ROOT}" ]]; then
  if is_truthy "${GIT_SAFE_EXPORT}" && [[ -n "${APP_DIR}" ]]; then
    REMOTE_ROOT="${APP_DIR}"
  else
    REMOTE_ROOT="${REMOTE_HOME_DIR}/mesh"
  fi
fi
if [[ -z "${APP_DIR}" ]]; then
  APP_DIR="${REMOTE_ROOT}/app"
fi
if [[ -z "${CONFIG_DIR}" ]]; then
  CONFIG_DIR="${REMOTE_ROOT}/config"
fi
if [[ -z "${LOG_DIR}" ]]; then
  LOG_DIR="${REMOTE_ROOT}/logs"
fi
if [[ -z "${REMOTE_VENV}" ]]; then
  if is_truthy "${GIT_SAFE_EXPORT}" && [[ "${REMOTE_VENV_EXPLICIT}" -eq 0 ]]; then
    REMOTE_VENV="${APP_DIR}/.venv"
  else
    REMOTE_VENV="${REMOTE_ROOT}/.venv"
  fi
fi
if [[ -z "${REMOTE_PYTHON}" ]]; then
  if is_truthy "${GIT_SAFE_EXPORT}" && [[ "${REMOTE_PYTHON_EXPLICIT}" -eq 0 ]]; then
    REMOTE_PYTHON="${APP_DIR}/.venv/bin/python"
  else
    REMOTE_PYTHON="${REMOTE_VENV}/bin/python"
  fi
fi

detect_existing_service_layout
if [[ "${SERVICE_USER_SET}" -eq 0 && -n "${DETECTED_SERVICE_USER}" ]]; then
  SERVICE_USER="${DETECTED_SERVICE_USER}"
fi
if [[ "${SERVICE_GROUP_SET}" -eq 0 && -n "${DETECTED_SERVICE_GROUP}" ]]; then
  SERVICE_GROUP="${DETECTED_SERVICE_GROUP}"
fi
guard_existing_service_layout_matches_deploy

if [[ -z "${HISTORY_DB}" ]]; then
  HISTORY_DB="${REMOTE_ROOT}/mesh_dashboard_history.sqlite3"
fi

if [[ "${UNINSTALL}" -eq 1 && "${WIPE_REMOTE_ROOT}" -eq 1 ]]; then
  echo "use either --uninstall or --wipe-remote-root, not both" >&2
  exit 2
fi

if [[ "${UNINSTALL}" -eq 1 && ( "${BOOTSTRAP}" -eq 1 || "${CLEAN_APP_DIR}" -eq 1 ) ]]; then
  echo "--uninstall cannot be combined with --bootstrap or --clean-app-dir" >&2
  exit 2
fi

if [[ "${WIPE_REMOTE_ROOT}" -eq 1 && "${BOOTSTRAP}" -eq 0 ]]; then
  BOOTSTRAP=1
fi

if is_truthy "${GIT_SAFE_EXPORT}"; then
  if [[ "${BOOTSTRAP}" -eq 1 || "${WIPE_REMOTE_ROOT}" -eq 1 || "${UNINSTALL}" -eq 1 || "${CLEAN_APP_DIR}" -eq 1 ]]; then
    echo "--git-safe-export cannot be combined with bootstrap, wipe, uninstall, or clean-app-dir" >&2
    exit 2
  fi
  git_safe_export_deploy
  exit 0
fi

if [[ -z "${MESH_HOST}" ]]; then
  MESH_HOST="$(
    ssh_cmd "${TARGET}" "if [[ -f '${CONFIG_DIR}/dashboard.env' ]]; then awk -F= '/^MESH_HOST=/{print \$2; exit}' '${CONFIG_DIR}/dashboard.env'; fi" \
      2>/dev/null \
      || true
  )"
fi

if [[ -z "${SERIAL_PATH}" ]]; then
  SERIAL_PATH="$(read_existing_dashboard_env_value "MESH_SERIAL_PATH")"
fi

if [[ -n "${MESH_HOST}" && -n "${SERIAL_PATH}" ]]; then
  echo "set either --mesh-host or --serial-path, not both" >&2
  exit 2
fi

if [[ "${BOOTSTRAP}" -eq 1 && -z "${MESH_HOST}" && -z "${SERIAL_PATH}" ]]; then
  echo "--bootstrap requires --mesh-host or --serial-path (or an existing ${CONFIG_DIR}/dashboard.env on target)" >&2
  exit 1
fi

if [[ "${FILE_TRANSFER_ENABLE_SET}" -eq 0 ]]; then
  existing_file_transfer_enable="$(read_existing_dashboard_env_value "MESH_DASH_FILE_TRANSFER_ENABLE")"
  if [[ -n "${existing_file_transfer_enable}" ]]; then
    FILE_TRANSFER_ENABLE="${existing_file_transfer_enable}"
  fi
fi

if [[ "${BBS_ENABLE_SET}" -eq 0 ]]; then
  existing_bbs_enable="$(read_existing_dashboard_env_value "MESH_DASH_BBS_ENABLE")"
  if [[ -n "${existing_bbs_enable}" ]]; then
    BBS_ENABLE="${existing_bbs_enable}"
  fi
fi

if [[ "${GAMES_ENABLE_SET}" -eq 0 ]]; then
  existing_games_enable="$(read_existing_dashboard_env_value "MESH_DASH_GAMES_ENABLE")"
  if [[ -n "${existing_games_enable}" ]]; then
    GAMES_ENABLE="${existing_games_enable}"
  fi
fi

if [[ "${FILE_TRANSFER_MAX_BYTES_SET}" -eq 0 ]]; then
  existing_file_transfer_max_bytes="$(read_existing_dashboard_env_value "MESH_DASH_FILE_TRANSFER_MAX_BYTES")"
  if [[ -n "${existing_file_transfer_max_bytes}" ]]; then
    FILE_TRANSFER_MAX_BYTES="${existing_file_transfer_max_bytes}"
  fi
fi

if [[ "${FILE_TRANSFER_AUTO_ACCEPT_SET}" -eq 0 ]]; then
  existing_file_transfer_auto_accept="$(read_existing_dashboard_env_value "MESH_DASH_FILE_TRANSFER_AUTO_ACCEPT")"
  if [[ -n "${existing_file_transfer_auto_accept}" ]]; then
    FILE_TRANSFER_AUTO_ACCEPT="${existing_file_transfer_auto_accept}"
  fi
fi

if [[ "${ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER_SET}" -eq 0 ]]; then
  existing_file_transfer_disclaimer="$(read_existing_dashboard_env_value "MESH_DASH_ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER")"
  if [[ -n "${existing_file_transfer_disclaimer}" ]]; then
    ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER="${existing_file_transfer_disclaimer}"
  fi
fi

if ! [[ "${FILE_TRANSFER_MAX_BYTES}" =~ ^[0-9]+$ ]]; then
  echo "--file-transfer-max-bytes must be an integer" >&2
  exit 2
fi

if { is_truthy "${FILE_TRANSFER_ENABLE}" || is_truthy "${BBS_ENABLE}"; } && ! is_truthy "${ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER}"; then
  echo "BBS/file-transfer enablement requires disclaimer acceptance." >&2
  echo "Re-run with --accept-file-transfer-traffic-disclaimer or set" >&2
  echo "MESH_DASH_DEPLOY_ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER=1." >&2
  exit 2
fi

echo "[deploy] target=${TARGET}"
echo "[deploy] app_dir=${APP_DIR} config_dir=${CONFIG_DIR} logs_dir=${LOG_DIR}"
echo "[deploy] service=${SERVICE_NAME} bootstrap=${BOOTSTRAP} clean_app_dir=${CLEAN_APP_DIR} wipe_remote_root=${WIPE_REMOTE_ROOT} uninstall=${UNINSTALL} hard_reboot=${HARD_REBOOT}"
echo "[deploy] service_user=${SERVICE_USER} service_group=${SERVICE_GROUP}"
if [[ -n "${MESH_HOST}" ]]; then
  echo "[deploy] mesh=${MESH_HOST}:${MESH_PORT} dash=${DASH_HOST}:${DASH_PORT} refresh_ms=${REFRESH_MS}"
fi
if [[ -n "${SERIAL_PATH}" ]]; then
  echo "[deploy] mesh_serial_path=${SERIAL_PATH} dash=${DASH_HOST}:${DASH_PORT} refresh_ms=${REFRESH_MS}"
fi
echo "[deploy] bbs_enable=${BBS_ENABLE}"
echo "[deploy] games_enable=${GAMES_ENABLE}"
echo "[deploy] file_transfer_enable=${FILE_TRANSFER_ENABLE} file_transfer_auto_accept=${FILE_TRANSFER_AUTO_ACCEPT} file_transfer_max_bytes=${FILE_TRANSFER_MAX_BYTES}"

if [[ "${UNINSTALL}" -eq 1 ]]; then
  uninstall_remote_meshyface
  if [[ "${HARD_REBOOT}" -eq 1 ]]; then
    hard_reboot_remote_target
  fi
  echo "[deploy] uninstall complete"
  exit 0
fi

if [[ "${WIPE_REMOTE_ROOT}" -eq 1 ]]; then
  echo "[deploy] wiping ${REMOTE_ROOT} and reinstalling from scratch"
  uninstall_remote_meshyface
fi

ssh_cmd "${TARGET}" "mkdir -p '${REMOTE_ROOT}' '${APP_DIR}' '${CONFIG_DIR}' '${LOG_DIR}'"

if [[ "${CLEAN_APP_DIR}" -eq 1 ]]; then
  if [[ -z "${APP_DIR}" || "${APP_DIR}" == "/" ]]; then
    echo "refusing to clean unsafe APP_DIR='${APP_DIR}'" >&2
    exit 1
  fi
  echo "[deploy] cleaning managed app paths in ${APP_DIR} (preserving databases/config/logs)"
  ssh_cmd "${TARGET}" "\
rm -rf '${APP_DIR}/meshdash' '${APP_DIR}/__pycache__' && \
rm -f '${APP_DIR}/mesh_dashboard.py' '${APP_DIR}/mesh_connection.py' && \
find '${APP_DIR}' -maxdepth 1 -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete"
fi

scp_cmd \
  "${ROOT_DIR}/mesh_dashboard.py" \
  "${ROOT_DIR}/mesh_connection.py" \
  "${ROOT_DIR}/requirements.txt" \
  "${TARGET}:${APP_DIR}/"

ssh_cmd "${TARGET}" "mkdir -p '${APP_DIR}/scripts'"
scp_cmd \
  "${ROOT_DIR}/scripts/benchmark_gui_responsiveness.py" \
  "${TARGET}:${APP_DIR}/scripts/"

tar \
  -C "${ROOT_DIR}" \
  --warning=no-timestamp \
  --exclude='meshdash/__pycache__' \
  --exclude='*.pyc' \
  -cf - \
  meshdash \
| ssh_cmd "${TARGET}" "tar -C '${APP_DIR}' -xf -"

echo "[deploy] verifying copied payload"
local_payload_hash="$(compute_local_deploy_payload_hash)"
remote_payload_hash="$(compute_remote_deploy_payload_hash)"
if [[ -z "${local_payload_hash}" || -z "${remote_payload_hash}" ]]; then
  echo "deploy payload verification failed: unable to compute hash" >&2
  exit 1
fi
if [[ "${local_payload_hash}" != "${remote_payload_hash}" ]]; then
  echo "deploy payload verification failed: local and remote app payload differ" >&2
  echo "[deploy] local payload hash:  ${local_payload_hash}" >&2
  echo "[deploy] remote payload hash: ${remote_payload_hash}" >&2
  exit 1
fi
echo "[deploy] payload hash: ${remote_payload_hash}"

if [[ "${BOOTSTRAP}" -eq 1 ]]; then
  echo "[deploy] bootstrapping runtime + service"
  ssh_cmd -tt "${TARGET}" "\
if ! command -v python3 >/dev/null 2>&1; then \
  sudo apt-get update && sudo apt-get install -y python3; \
fi"
  ssh_cmd -tt "${TARGET}" "\
PY_MM=\$(python3 -c 'import sys; print(str(sys.version_info.major)+\".\"+str(sys.version_info.minor))') && \
sudo apt-get update && \
(sudo apt-get install -y python3-venv python\${PY_MM}-venv || sudo apt-get install -y python3-venv)"
  ssh_cmd "${TARGET}" "\
if [[ ! -x '${REMOTE_VENV}/bin/python' || ! -x '${REMOTE_VENV}/bin/pip' ]]; then \
  rm -rf '${REMOTE_VENV}'; \
  python3 -m venv '${REMOTE_VENV}'; \
fi"
  ssh_cmd "${TARGET}" "'${REMOTE_VENV}/bin/pip' install --upgrade pip"
  ssh_cmd "${TARGET}" "'${REMOTE_VENV}/bin/pip' install -r '${APP_DIR}/requirements.txt'"

  if [[ -n "${SERIAL_PATH}" ]]; then
    SERVICE_EXEC_START="${REMOTE_PYTHON} ${APP_DIR}/mesh_dashboard.py --mesh-port \${MESH_SERIAL_PATH} --http-host \${DASH_HOST} --http-port \${DASH_PORT} --refresh-ms \${REFRESH_MS}"
  else
    SERVICE_EXEC_START="${REMOTE_PYTHON} ${APP_DIR}/mesh_dashboard.py --mesh-host \${MESH_HOST} --mesh-tcp-port \${MESH_PORT} --http-host \${DASH_HOST} --http-port \${DASH_PORT} --refresh-ms \${REFRESH_MS}"
  fi

  local_service="$(mktemp "${TMPDIR:-/tmp}/meshdash-service.XXXXXX")"
  cat > "${local_service}" <<EOF
[Unit]
Description=Meshtastic Dashboard Web Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${REMOTE_ROOT}
EnvironmentFile=${CONFIG_DIR}/dashboard.env
ExecStart=${SERVICE_EXEC_START}
Restart=always
RestartSec=2
KillSignal=SIGINT
TimeoutStopSec=10

[Install]
WantedBy=multi-user.target
EOF

  tmp_service="/tmp/${SERVICE_NAME}.service"
  scp_cmd "${local_service}" "${TARGET}:${tmp_service}"
  rm -f "${local_service}"
  ssh_cmd -tt "${TARGET}" "\
sudo install -m 0644 '${tmp_service}' '/etc/systemd/system/${SERVICE_NAME}.service' && \
rm -f '${tmp_service}' && \
sudo systemctl daemon-reload"
fi

if [[ -n "${MESH_HOST}" || -n "${SERIAL_PATH}" ]] || [[ "${BOOTSTRAP}" -eq 1 ]]; then
  echo "[deploy] writing ${CONFIG_DIR}/dashboard.env"
  ssh_cmd "${TARGET}" "cat > '${CONFIG_DIR}/dashboard.env' <<'EOF'
MESH_HOST=${MESH_HOST}
MESH_PORT=${MESH_PORT}
MESH_SERIAL_PATH=${SERIAL_PATH}
DASH_HOST=${DASH_HOST}
DASH_PORT=${DASH_PORT}
REFRESH_MS=${REFRESH_MS}
MESH_DASH_HISTORY_DB=${HISTORY_DB}
MESH_DASH_BBS_ENABLE=${BBS_ENABLE}
MESH_DASH_GAMES_ENABLE=${GAMES_ENABLE}
MESH_DASH_FILE_TRANSFER_ENABLE=${FILE_TRANSFER_ENABLE}
MESH_DASH_FILE_TRANSFER_AUTO_ACCEPT=${FILE_TRANSFER_AUTO_ACCEPT}
MESH_DASH_FILE_TRANSFER_MAX_BYTES=${FILE_TRANSFER_MAX_BYTES}
MESH_DASH_ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER=${ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER}
MESH_DASH_DEPLOY_PAYLOAD_HASH=${remote_payload_hash}
PYTHONUNBUFFERED=${PYTHON_UNBUFFERED}
EOF"
else
  echo "[deploy] updating deploy payload hash in existing ${CONFIG_DIR}/dashboard.env"
  ssh_cmd "${TARGET}" "\
if [[ ! -f '${CONFIG_DIR}/dashboard.env' ]]; then \
  echo 'dashboard.env not found at ${CONFIG_DIR}/dashboard.env; rerun with --bootstrap or provide --mesh-host/--serial-path' >&2; \
  exit 1; \
fi && \
if grep -q '^MESH_DASH_DEPLOY_PAYLOAD_HASH=' '${CONFIG_DIR}/dashboard.env'; then \
  sed -i \"s/^MESH_DASH_DEPLOY_PAYLOAD_HASH=.*/MESH_DASH_DEPLOY_PAYLOAD_HASH=${remote_payload_hash}/\" '${CONFIG_DIR}/dashboard.env'; \
else \
  printf '\nMESH_DASH_DEPLOY_PAYLOAD_HASH=%s\n' '${remote_payload_hash}' >> '${CONFIG_DIR}/dashboard.env'; \
fi"
  if [[ "${FILE_TRANSFER_AUTO_ACCEPT_SET}" -eq 1 ]]; then
    echo "[deploy] updating file transfer auto accept in existing ${CONFIG_DIR}/dashboard.env"
    ssh_cmd "${TARGET}" "\
if grep -q '^MESH_DASH_FILE_TRANSFER_AUTO_ACCEPT=' '${CONFIG_DIR}/dashboard.env'; then \
  sed -i \"s/^MESH_DASH_FILE_TRANSFER_AUTO_ACCEPT=.*/MESH_DASH_FILE_TRANSFER_AUTO_ACCEPT=${FILE_TRANSFER_AUTO_ACCEPT}/\" '${CONFIG_DIR}/dashboard.env'; \
else \
  printf '\nMESH_DASH_FILE_TRANSFER_AUTO_ACCEPT=%s\n' '${FILE_TRANSFER_AUTO_ACCEPT}' >> '${CONFIG_DIR}/dashboard.env'; \
fi"
  fi
fi

if ! ssh_cmd "${TARGET}" "test -x '${REMOTE_PYTHON}'"; then
  echo "remote python not found at ${REMOTE_PYTHON}; rerun with --bootstrap" >&2
  exit 1
fi

if [[ "${BOOTSTRAP}" -eq 1 ]]; then
  ssh_cmd -tt "${TARGET}" "\
'${REMOTE_PYTHON}' -m compileall -x '(^|/)(\.git|\.venv)(/|$)' -q '${APP_DIR}' && \
sudo systemctl enable '${SERVICE_NAME}' && \
sudo systemctl restart '${SERVICE_NAME}' && \
SYSTEMD_PAGER=cat sudo systemctl --no-pager -l status '${SERVICE_NAME}'"
else
  if ! ssh_cmd "${TARGET}" "systemctl list-unit-files --type=service --all | grep -q '^${SERVICE_NAME}\.service'"; then
    echo "service ${SERVICE_NAME}.service is not installed on target; rerun with --bootstrap" >&2
    exit 1
  fi
  ssh_cmd -tt "${TARGET}" "\
'${REMOTE_PYTHON}' -m compileall -x '(^|/)(\.git|\.venv)(/|$)' -q '${APP_DIR}' && \
sudo systemctl restart '${SERVICE_NAME}' && \
SYSTEMD_PAGER=cat sudo systemctl --no-pager -l status '${SERVICE_NAME}'"
fi

verify_remote_runtime_payload_hash "${remote_payload_hash}"

target_host="${TARGET#*@}"
if [[ "${HARD_REBOOT}" -eq 1 ]]; then
  hard_reboot_remote_target
  echo "[deploy] reboot requested; wait for ${target_host} to come back before opening the UI"
  exit 0
fi

echo "[deploy] complete"
echo "[deploy] open: http://${target_host}:${DASH_PORT}"
