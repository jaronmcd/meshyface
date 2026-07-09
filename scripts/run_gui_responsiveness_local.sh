#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${MESH_GUI_BENCH_PORT:-8877}"
URL="${MESH_GUI_BENCH_URL:-http://127.0.0.1:${PORT}/}"
DEFAULT_LOCAL_URL="http://127.0.0.1:8877/"
OUTPUT="${MESH_GUI_BENCH_OUTPUT:-${ROOT_DIR}/benchmarks/gui_responsiveness/results/local-gui-responsiveness.json}"
THRESHOLDS="${MESH_GUI_BENCH_THRESHOLDS:-${ROOT_DIR}/benchmarks/gui_responsiveness/local_thresholds.json}"
SERVER_LOG="${MESH_GUI_BENCH_SERVER_LOG:-${TMPDIR:-/tmp}/mesh_gui_bench_local_server.log}"
HISTORY_DB="${MESH_GUI_BENCH_HISTORY_DB:-${TMPDIR:-/tmp}/mesh_gui_bench_history.sqlite3}"
SERVER_PID=""

refuse_if_local_server_responds() {
  local probe_url="$1"
  if curl -sS --max-time 2 -o /dev/null "${probe_url}" >/dev/null 2>&1; then
    {
      echo "Existing local server detected at ${probe_url}."
      echo "Refusing to run the local GUI benchmark while another server is active."
      echo "Stop the local server first, then rerun the benchmark."
    } >&2
    exit 2
  fi
}

is_local_url() {
  case "$1" in
    http://127.*|https://127.*|http://localhost*|https://localhost*|http://[[]::1[]]*|https://[[]::1[]]*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

require_no_existing_local_server() {
  refuse_if_local_server_responds "${DEFAULT_LOCAL_URL}"
  if [[ "${URL}" != "${DEFAULT_LOCAL_URL}" ]] && is_local_url "${URL}"; then
    refuse_if_local_server_responds "${URL}"
  fi
}

cleanup() {
  if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
    wait "${SERVER_PID}" || true
  fi
}
trap cleanup EXIT

require_no_existing_local_server

if [[ -z "${MESH_GUI_BENCH_URL:-}" ]]; then
  if curl -fsS "${URL}api/version" >/dev/null 2>&1; then
    cat >&2 <<EOF
Refusing to start GUI benchmark: ${URL}api/version already responds.
Set MESH_GUI_BENCH_URL=${URL} to intentionally benchmark that running server,
or set MESH_GUI_BENCH_PORT to a free port for an isolated benchmark server.
EOF
    exit 1
  fi

  python "${ROOT_DIR}/mesh_dashboard.py" \
    --mesh-host 127.0.0.1 \
    --mesh-tcp-port 1 \
    --http-host 127.0.0.1 \
    --http-port "${PORT}" \
    --refresh-ms "${MESH_GUI_BENCH_REFRESH_MS:-3000}" \
    --history-db "${HISTORY_DB}" \
    >"${SERVER_LOG}" 2>&1 &
  SERVER_PID="$!"

  for _ in $(seq 1 60); do
    if curl -fsS "${URL}api/version" >/dev/null 2>&1; then
      break
    fi
    if ! kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
      tail -n 120 "${SERVER_LOG}" || true
      exit 1
    fi
    sleep 1
  done
  curl -fsS "${URL}api/version" >/dev/null
fi

BROWSER_ARGS=()
if [[ -n "${MESH_GUI_BENCH_BROWSER_ARG:-}" ]]; then
  BROWSER_ARGS+=("--browser-arg=${MESH_GUI_BENCH_BROWSER_ARG}")
elif [[ "$(uname -s)" == "Linux" ]]; then
  BROWSER_ARGS+=("--browser-arg=--no-sandbox")
fi

python "${ROOT_DIR}/scripts/benchmark_gui_responsiveness.py" \
  --url "${URL}" \
  --views "${MESH_GUI_BENCH_VIEWS:-chat,network:map,network:graph,network:sensors,history,settings,console}" \
  --iterations "${MESH_GUI_BENCH_ITERATIONS:-1}" \
  --warmup "${MESH_GUI_BENCH_WARMUP:-1}" \
  --no-selection \
  --no-cached-poll \
  --virtual-time-budget-ms "${MESH_GUI_BENCH_VIRTUAL_TIME_BUDGET_MS:-180000}" \
  --timeout "${MESH_GUI_BENCH_TIMEOUT:-240}" \
  --output-json "${OUTPUT}" \
  --thresholds "${THRESHOLDS}" \
  "${BROWSER_ARGS[@]}"
