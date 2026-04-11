#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/deploy_meshyface.sh [target] [options]

Examples:
  # Fast update to an already configured host
  ./scripts/deploy_meshyface.sh j@192.168.1.241

  # First-time bootstrap + deploy
  ./scripts/deploy_meshyface.sh \
    --target j@192.168.1.29 \
    --bootstrap \
    --mesh-host 192.168.1.211

Options:
  --target <user@host>     SSH deploy target.
  --bootstrap              Prepare a fresh host (venv, deps, service, env file).
  --clean-app-dir          Remove stale managed app code in APP_DIR before copy.
  --mesh-host <ip_or_dns>  Radio host for dashboard.env MESH_HOST.
  --mesh-port <port>       Radio TCP port (default: 4403).
  --serial-path <path>     Radio serial device path for dashboard.env MESH_SERIAL_PATH.
  --dash-host <ip_or_dns>  Dashboard bind host (default: 0.0.0.0).
  --dash-port <port>       Dashboard bind port (default: 8877).
  --refresh-ms <ms>        Poll interval in ms (default: 3000).
  --ui-profile <name>      Dashboard UI profile (public branch supports core-ui only).
  --history-db <path>      History DB path on target host.
  --file-transfer-enable   Enable file transfer in dashboard.env.
  --no-file-transfer-enable Disable file transfer in dashboard.env.
  --file-transfer-max-bytes <bytes>
                           Max file transfer size written to dashboard.env.
  --accept-file-transfer-traffic-disclaimer
                           Acknowledge mesh airtime/congestion risk when enabling transfers.
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
  MESH_DASH_DEPLOY_CLEAN_APP_DIR
  MESH_DASH_DEPLOY_MESH_HOST
  MESH_DASH_DEPLOY_MESH_PORT
  MESH_DASH_DEPLOY_SERIAL_PATH
  MESH_DASH_DEPLOY_DASH_HOST
  MESH_DASH_DEPLOY_DASH_PORT
  MESH_DASH_DEPLOY_REFRESH_MS
  MESH_DASH_DEPLOY_UI_PROFILE
  MESH_DASH_DEPLOY_HISTORY_DB
  MESH_DASH_DEPLOY_PYTHON_UNBUFFERED
  MESH_DASH_DEPLOY_FILE_TRANSFER_ENABLE
  MESH_DASH_DEPLOY_FILE_TRANSFER_MAX_BYTES
  MESH_DASH_DEPLOY_ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER
EOF
}

normalize_ui_profile() {
  local raw="${1:-}"
  local token="${raw,,}"
  token="${token//_/-}"
  case "${token}" in
    ""|core|coreui|core-ui)
      printf 'core-ui\n'
      ;;
    *)
      echo "unsupported --ui-profile '${raw}' for release/public-v0; use core-ui" >&2
      exit 2
      ;;
  esac
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

BOOTSTRAP=0
CLEAN_APP_DIR="${MESH_DASH_DEPLOY_CLEAN_APP_DIR:-0}"
MESH_HOST="${MESH_DASH_DEPLOY_MESH_HOST:-}"
MESH_PORT="${MESH_DASH_DEPLOY_MESH_PORT:-4403}"
SERIAL_PATH="${MESH_DASH_DEPLOY_SERIAL_PATH:-}"
DASH_HOST="${MESH_DASH_DEPLOY_DASH_HOST:-0.0.0.0}"
DASH_PORT="${MESH_DASH_DEPLOY_DASH_PORT:-8877}"
REFRESH_MS="${MESH_DASH_DEPLOY_REFRESH_MS:-3000}"
UI_PROFILE="${MESH_DASH_DEPLOY_UI_PROFILE:-core-ui}"
HISTORY_DB="${MESH_DASH_DEPLOY_HISTORY_DB:-}"
PYTHON_UNBUFFERED="${MESH_DASH_DEPLOY_PYTHON_UNBUFFERED:-1}"
FILE_TRANSFER_ENABLE="${MESH_DASH_DEPLOY_FILE_TRANSFER_ENABLE:-0}"
FILE_TRANSFER_MAX_BYTES="${MESH_DASH_DEPLOY_FILE_TRANSFER_MAX_BYTES:-65536}"
ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER="${MESH_DASH_DEPLOY_ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER:-0}"
FILE_TRANSFER_ENABLE_SET=0
FILE_TRANSFER_MAX_BYTES_SET=0
ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER_SET=0
if [[ -n "${MESH_DASH_DEPLOY_FILE_TRANSFER_ENABLE+x}" ]]; then
  FILE_TRANSFER_ENABLE_SET=1
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
    --clean-app-dir)
      CLEAN_APP_DIR=1
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
    --ui-profile)
      require_arg "$1" "${2:-}"
      UI_PROFILE="$2"
      shift 2
      ;;
    --history-db)
      require_arg "$1" "${2:-}"
      HISTORY_DB="$2"
      shift 2
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
      shift 2
      ;;
    --service-group)
      require_arg "$1" "${2:-}"
      SERVICE_GROUP="$2"
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
  ./scripts/deploy_meshyface.sh --target j@192.168.1.29
  ./scripts/deploy_meshyface.sh --target j@192.168.1.29 --bootstrap --mesh-host 192.168.1.211

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

read_remote_identity

if [[ -z "${SERVICE_USER}" ]]; then
  SERVICE_USER="${REMOTE_LOGIN_USER}"
fi
if [[ -z "${REMOTE_ROOT}" ]]; then
  REMOTE_ROOT="${REMOTE_HOME_DIR}/mesh"
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
  REMOTE_VENV="${REMOTE_ROOT}/.venv"
fi
if [[ -z "${REMOTE_PYTHON}" ]]; then
  REMOTE_PYTHON="${REMOTE_VENV}/bin/python"
fi
if [[ -z "${HISTORY_DB}" ]]; then
  HISTORY_DB="${REMOTE_ROOT}/mesh_dashboard_history.sqlite3"
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

UI_PROFILE="$(normalize_ui_profile "${UI_PROFILE}")"

if [[ "${FILE_TRANSFER_ENABLE_SET}" -eq 0 ]]; then
  existing_file_transfer_enable="$(read_existing_dashboard_env_value "MESH_DASH_FILE_TRANSFER_ENABLE")"
  if [[ -n "${existing_file_transfer_enable}" ]]; then
    FILE_TRANSFER_ENABLE="${existing_file_transfer_enable}"
  fi
fi

if [[ "${FILE_TRANSFER_MAX_BYTES_SET}" -eq 0 ]]; then
  existing_file_transfer_max_bytes="$(read_existing_dashboard_env_value "MESH_DASH_FILE_TRANSFER_MAX_BYTES")"
  if [[ -n "${existing_file_transfer_max_bytes}" ]]; then
    FILE_TRANSFER_MAX_BYTES="${existing_file_transfer_max_bytes}"
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

if is_truthy "${FILE_TRANSFER_ENABLE}" && ! is_truthy "${ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER}"; then
  echo "file transfer enablement requires disclaimer acceptance." >&2
  echo "Re-run with --accept-file-transfer-traffic-disclaimer or set" >&2
  echo "MESH_DASH_DEPLOY_ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER=1." >&2
  exit 2
fi

echo "[deploy] target=${TARGET}"
echo "[deploy] app_dir=${APP_DIR} config_dir=${CONFIG_DIR} logs_dir=${LOG_DIR}"
echo "[deploy] service=${SERVICE_NAME} bootstrap=${BOOTSTRAP} clean_app_dir=${CLEAN_APP_DIR}"
echo "[deploy] service_user=${SERVICE_USER} service_group=${SERVICE_GROUP}"
if [[ -n "${MESH_HOST}" ]]; then
  echo "[deploy] mesh=${MESH_HOST}:${MESH_PORT} dash=${DASH_HOST}:${DASH_PORT} refresh_ms=${REFRESH_MS}"
fi
if [[ -n "${SERIAL_PATH}" ]]; then
  echo "[deploy] mesh_serial_path=${SERIAL_PATH} dash=${DASH_HOST}:${DASH_PORT} refresh_ms=${REFRESH_MS}"
fi
if [[ -n "${UI_PROFILE}" ]]; then
  echo "[deploy] ui_profile=${UI_PROFILE}"
fi
echo "[deploy] file_transfer_enable=${FILE_TRANSFER_ENABLE} file_transfer_max_bytes=${FILE_TRANSFER_MAX_BYTES}"

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
MESH_DASH_UI_PROFILE=${UI_PROFILE}
MESH_DASH_HISTORY_DB=${HISTORY_DB}
MESH_DASH_FILE_TRANSFER_ENABLE=${FILE_TRANSFER_ENABLE}
MESH_DASH_FILE_TRANSFER_MAX_BYTES=${FILE_TRANSFER_MAX_BYTES}
MESH_DASH_ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER=${ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER}
PYTHONUNBUFFERED=${PYTHON_UNBUFFERED}
EOF"
fi

if ! ssh_cmd "${TARGET}" "test -x '${REMOTE_PYTHON}'"; then
  echo "remote python not found at ${REMOTE_PYTHON}; rerun with --bootstrap" >&2
  exit 1
fi

if [[ "${BOOTSTRAP}" -eq 1 ]]; then
  ssh_cmd -tt "${TARGET}" "\
'${REMOTE_PYTHON}' -m compileall -q '${APP_DIR}' && \
sudo systemctl enable --now '${SERVICE_NAME}' && \
SYSTEMD_PAGER=cat sudo systemctl --no-pager -l status '${SERVICE_NAME}'"
else
  if ! ssh_cmd "${TARGET}" "systemctl list-unit-files --type=service --all | grep -q '^${SERVICE_NAME}\.service'"; then
    echo "service ${SERVICE_NAME}.service is not installed on target; rerun with --bootstrap" >&2
    exit 1
  fi
  ssh_cmd -tt "${TARGET}" "\
'${REMOTE_PYTHON}' -m compileall -q '${APP_DIR}' && \
sudo systemctl restart '${SERVICE_NAME}' && \
SYSTEMD_PAGER=cat sudo systemctl --no-pager -l status '${SERVICE_NAME}'"
fi

target_host="${TARGET#*@}"
echo "[deploy] complete"
echo "[deploy] open: http://${target_host}:${DASH_PORT}"
