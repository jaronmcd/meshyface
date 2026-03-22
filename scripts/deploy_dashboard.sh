#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/deploy_dashboard.sh [target] [options]

Examples:
  # Fast update to an already configured host
  ./scripts/deploy_dashboard.sh j@192.168.1.241

  # First-time bootstrap + deploy
  ./scripts/deploy_dashboard.sh \
    --target j@192.168.1.29 \
    --bootstrap \
    --mesh-host 192.168.1.211

Options:
  --target <user@host>     SSH deploy target.
  --bootstrap              Prepare a fresh host (venv, deps, service, env file).
  --mesh-host <ip_or_dns>  Radio host for dashboard.env MESH_HOST.
  --mesh-port <port>       Radio TCP port (default: 4403).
  --dash-host <ip_or_dns>  Dashboard bind host (default: 0.0.0.0).
  --dash-port <port>       Dashboard bind port (default: 8877).
  --refresh-ms <ms>        Poll interval in ms (default: 3000).
  --history-db <path>      History DB path on target host.
  --service <name>         Systemd service name (default: meshtastic-dashboard).
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
  MESH_DASH_DEPLOY_MESH_HOST
  MESH_DASH_DEPLOY_MESH_PORT
  MESH_DASH_DEPLOY_DASH_HOST
  MESH_DASH_DEPLOY_DASH_PORT
  MESH_DASH_DEPLOY_REFRESH_MS
  MESH_DASH_DEPLOY_HISTORY_DB
  MESH_DASH_DEPLOY_PYTHON_UNBUFFERED
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

TARGET="${MESH_DASH_DEPLOY_TARGET:-}"
REMOTE_ROOT="${MESH_DASH_DEPLOY_ROOT:-/home/j/mesh}"
APP_DIR="${MESH_DASH_DEPLOY_APP_DIR:-${REMOTE_ROOT}/app}"
CONFIG_DIR="${MESH_DASH_DEPLOY_CONFIG_DIR:-${REMOTE_ROOT}/config}"
LOG_DIR="${MESH_DASH_DEPLOY_LOG_DIR:-${REMOTE_ROOT}/logs}"
REMOTE_VENV="${MESH_DASH_DEPLOY_REMOTE_VENV:-${REMOTE_ROOT}/.venv}"
REMOTE_PYTHON="${MESH_DASH_DEPLOY_REMOTE_PYTHON:-${REMOTE_VENV}/bin/python}"
SERVICE_NAME="${MESH_DASH_DEPLOY_SERVICE:-meshtastic-dashboard}"

BOOTSTRAP=0
MESH_HOST="${MESH_DASH_DEPLOY_MESH_HOST:-}"
MESH_PORT="${MESH_DASH_DEPLOY_MESH_PORT:-4403}"
DASH_HOST="${MESH_DASH_DEPLOY_DASH_HOST:-0.0.0.0}"
DASH_PORT="${MESH_DASH_DEPLOY_DASH_PORT:-8877}"
REFRESH_MS="${MESH_DASH_DEPLOY_REFRESH_MS:-3000}"
HISTORY_DB="${MESH_DASH_DEPLOY_HISTORY_DB:-${REMOTE_ROOT}/mesh_dashboard_history.sqlite3}"
PYTHON_UNBUFFERED="${MESH_DASH_DEPLOY_PYTHON_UNBUFFERED:-1}"
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
    --service)
      require_arg "$1" "${2:-}"
      SERVICE_NAME="$2"
      shift 2
      ;;
    --app-dir)
      require_arg "$1" "${2:-}"
      APP_DIR="$2"
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
      shift 2
      ;;
    --remote-python)
      require_arg "$1" "${2:-}"
      REMOTE_PYTHON="$2"
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

Copy/paste one of these, then change only the last IP number:
  ./scripts/deploy_dashboard.sh --target j@192.168.1.29
  ./scripts/deploy_dashboard.sh --target j@192.168.1.29 --bootstrap --mesh-host 192.168.1.211

You can also set MESH_DASH_DEPLOY_TARGET in your environment.
EOF
  exit 2
fi

for local_required in mesh_dashboard.py mesh_connection.py meshdash meshtastic-dashboard.service; do
  if [[ ! -e "${ROOT_DIR}/${local_required}" ]]; then
    echo "${local_required} not found under ${ROOT_DIR}" >&2
    exit 1
  fi
done

if [[ -z "${MESH_HOST}" ]]; then
  MESH_HOST="$(
    ssh_cmd "${TARGET}" "if [[ -f '${CONFIG_DIR}/dashboard.env' ]]; then awk -F= '/^MESH_HOST=/{print \$2; exit}' '${CONFIG_DIR}/dashboard.env'; fi" \
      2>/dev/null \
      || true
  )"
fi

if [[ "${BOOTSTRAP}" -eq 1 && -z "${MESH_HOST}" ]]; then
  echo "--bootstrap requires --mesh-host (or an existing ${CONFIG_DIR}/dashboard.env on target)" >&2
  exit 1
fi

echo "[deploy] target=${TARGET}"
echo "[deploy] app_dir=${APP_DIR} config_dir=${CONFIG_DIR} logs_dir=${LOG_DIR}"
echo "[deploy] service=${SERVICE_NAME} bootstrap=${BOOTSTRAP}"
if [[ -n "${MESH_HOST}" ]]; then
  echo "[deploy] mesh=${MESH_HOST}:${MESH_PORT} dash=${DASH_HOST}:${DASH_PORT} refresh_ms=${REFRESH_MS}"
fi

ssh_cmd "${TARGET}" "mkdir -p '${REMOTE_ROOT}' '${APP_DIR}' '${CONFIG_DIR}' '${LOG_DIR}'"

scp_cmd \
  "${ROOT_DIR}/mesh_dashboard.py" \
  "${ROOT_DIR}/mesh_connection.py" \
  "${TARGET}:${APP_DIR}/"

tar \
  -C "${ROOT_DIR}" \
  --warning=no-timestamp \
  --exclude='meshdash/__pycache__' \
  --exclude='*.pyc' \
  -cf - \
  meshdash \
| ssh_cmd "${TARGET}" "tar -C '${APP_DIR}' -xf -"

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
  ssh_cmd "${TARGET}" "'${REMOTE_VENV}/bin/pip' install meshtastic pypubsub protobuf"

  tmp_service="/tmp/${SERVICE_NAME}.service"
  scp_cmd "${ROOT_DIR}/meshtastic-dashboard.service" "${TARGET}:${tmp_service}"
  ssh_cmd -t "${TARGET}" "\
sudo install -m 0644 '${tmp_service}' '/etc/systemd/system/${SERVICE_NAME}.service' && \
rm -f '${tmp_service}' && \
sudo systemctl daemon-reload"
fi

if [[ -n "${MESH_HOST}" ]] || [[ "${BOOTSTRAP}" -eq 1 ]]; then
  echo "[deploy] writing ${CONFIG_DIR}/dashboard.env"
  ssh_cmd "${TARGET}" "cat > '${CONFIG_DIR}/dashboard.env' <<'EOF'
MESH_HOST=${MESH_HOST}
MESH_PORT=${MESH_PORT}
DASH_HOST=${DASH_HOST}
DASH_PORT=${DASH_PORT}
REFRESH_MS=${REFRESH_MS}
MESH_DASH_HISTORY_DB=${HISTORY_DB}
PYTHONUNBUFFERED=${PYTHON_UNBUFFERED}
EOF"
fi

if ! ssh_cmd "${TARGET}" "test -x '${REMOTE_PYTHON}'"; then
  echo "remote python not found at ${REMOTE_PYTHON}; rerun with --bootstrap" >&2
  exit 1
fi

if [[ "${BOOTSTRAP}" -eq 1 ]]; then
  ssh_cmd -t "${TARGET}" "\
'${REMOTE_PYTHON}' -m compileall -q '${APP_DIR}' && \
sudo systemctl enable --now '${SERVICE_NAME}' && \
SYSTEMD_PAGER=cat sudo systemctl --no-pager -l status '${SERVICE_NAME}'"
else
  if ! ssh_cmd "${TARGET}" "systemctl list-unit-files --type=service --all | grep -q '^${SERVICE_NAME}\.service'"; then
    echo "service ${SERVICE_NAME}.service is not installed on target; rerun with --bootstrap" >&2
    exit 1
  fi
  ssh_cmd -t "${TARGET}" "\
'${REMOTE_PYTHON}' -m compileall -q '${APP_DIR}' && \
sudo systemctl restart '${SERVICE_NAME}' && \
SYSTEMD_PAGER=cat sudo systemctl --no-pager -l status '${SERVICE_NAME}'"
fi

target_host="${TARGET#*@}"
echo "[deploy] complete"
echo "[deploy] open: http://${target_host}:${DASH_PORT}"
