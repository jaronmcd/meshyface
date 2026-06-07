#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${MESH_GUI_BENCH_PORT:-8877}"
URL="${MESH_GUI_BENCH_URL:-http://127.0.0.1:${PORT}/}"
OUTPUT="${MESH_GUI_BENCH_OUTPUT:-${ROOT_DIR}/benchmarks/gui_responsiveness/results/ci-gui-responsiveness.json}"
THRESHOLDS="${MESH_GUI_BENCH_THRESHOLDS:-${ROOT_DIR}/benchmarks/gui_responsiveness/ci_thresholds.json}"
SERVER_LOG="${MESH_GUI_BENCH_SERVER_LOG:-${TMPDIR:-/tmp}/mesh_gui_bench_server.log}"
HISTORY_DB="${MESH_GUI_BENCH_HISTORY_DB:-${TMPDIR:-/tmp}/mesh_gui_bench_history.sqlite3}"
SERVER_PID=""

cleanup() {
  if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
    wait "${SERVER_PID}" || true
  fi
}
trap cleanup EXIT

if [[ -z "${MESH_GUI_BENCH_URL:-}" ]]; then
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
